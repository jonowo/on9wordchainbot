import asyncio
import re
from typing import Type

from aiogram import Router, types
from aiogram.filters import Command, CommandObject

from on9wordchainbot.constants import GameSettings, GameState, VIP, VIP_GROUP
from on9wordchainbot.filters import HasGameInstance, IsAdmin, IsOwner
from on9wordchainbot.models import ClassicGame, EliminationGame, GAME_MODES, MixedEliminationGame
from on9wordchainbot.resources import GlobalState, on9bot
from on9wordchainbot.utils import amt_donated, send_groups_only_message

router = Router(name=__name__)


@send_groups_only_message
async def start_game(message: types.Message, game_type: Type[ClassicGame]) -> None:
    group_id = message.chat.id
    if group_id in GlobalState.games:
        # There is already a game running in the group
        await GlobalState.games[group_id].join(message)
        return

    if GlobalState.maint_mode:
        # Only stop people from starting games, not joining
        await message.reply(
            "Maintenance mode is on. Games are temporarily disabled.\n"
            "This is likely due to a pending bot update."
        )
        return

    chat = await message.bot.get_chat(message.chat.id)
    if chat.slow_mode_delay:
        await message.reply(
            "Slow mode is enabled in this group, so the bot cannot function properly.\n"
            "If you are a group admin, please disable slow mode to start games."
        )
        return

    if (
        game_type is MixedEliminationGame and message.chat.id not in VIP_GROUP
        and message.from_user.id not in VIP and await amt_donated(message.from_user.id) < 30
    ):
        await message.reply(
            "This game mode is a donation reward.\n"
            "You can try this game mode at the [official group](https://t.me/+T30aTNo-2Xx2kc52)."
        )
        return

    async with GlobalState.games_lock:  # Avoid duplicate game creation
        if group_id in GlobalState.games:
            asyncio.create_task(GlobalState.games[group_id].join(message))
        else:
            game = game_type(message.chat.id)
            GlobalState.games[group_id] = game
            asyncio.create_task(game.main_loop(message))


@router.message(Command(re.compile(r"^(start[a-z]+)$")))
async def cmd_startgame(message: types.Message, command: CommandObject) -> None:
    command_name = command.command.lower()
    if command_name == "startgame":
        await start_game(message, ClassicGame)
        return

    for mode in GAME_MODES:
        if mode.command == command_name:
            await start_game(message, mode)
            return


@router.message(Command("join"))
@send_groups_only_message
async def cmd_join(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GlobalState.games:
        await GlobalState.games[group_id].join(message)


@router.message(Command("forcejoin"), IsOwner(), HasGameInstance())
async def cmd_forcejoin(message: types.Message) -> None:
    group_id = message.chat.id
    rmsg = message.reply_to_message
    if rmsg and rmsg.from_user.is_bot:  # On9Bot only
        if rmsg.from_user.id == on9bot.id:
            await cmd_addvp(message)
        return
    await GlobalState.games[group_id].forcejoin(message)


@router.message(Command("extend"), HasGameInstance())
async def cmd_extend(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].extend(message)


@router.message(Command("forcestart"), IsAdmin(), HasGameInstance())
async def cmd_forcestart(message: types.Message) -> None:
    group_id = message.chat.id
    if GlobalState.games[group_id].state == GameState.JOINING:
        GlobalState.games[group_id].time_left = -99999


@router.message(Command("flee"), HasGameInstance())
async def cmd_flee(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].flee(message)


@router.message(Command("forceflee"), IsOwner(), HasGameInstance())
async def cmd_forceflee(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].forceflee(message)


@router.message(Command("killgame", "killgaym"), IsOwner())
async def cmd_killgame(message: types.Message, command: CommandObject) -> None:
    try:
        group_id = int(command.args or message.chat.id)
        assert group_id < 0, "smh"
        assert group_id in GlobalState.games, "no game running"
    except (ValueError, AssertionError) as e:
        await message.reply(f"`{e.__class__.__name__}: {e}`")
        return

    GlobalState.games[group_id].state = GameState.KILLGAME
    await asyncio.sleep(2)

    # If game is still not terminated
    if group_id in GlobalState.games:
        del GlobalState.games[group_id]
        await message.reply("Game ended forcibly.")


@router.message(Command("forceskip"), IsOwner(), HasGameInstance())
async def cmd_forceskip(message: types.Message) -> None:
    group_id = message.chat.id
    if GlobalState.games[group_id].state == GameState.RUNNING and not GlobalState.games[group_id].answered:
        GlobalState.games[group_id].time_left = 0


@router.message(Command("addvp"), HasGameInstance())
async def cmd_addvp(message: types.Message) -> None:
    group_id = message.chat.id
    on9bot_user = await on9bot.me()
    if isinstance(GlobalState.games[group_id], EliminationGame):
        await message.reply(
            f"Sorry, [{on9bot_user.full_name}](https://t.me/{on9bot_user.username}) "
            "can't play elimination games."
        )
        return
    await GlobalState.games[group_id].addvp(message)


@router.message(Command("remvp"), HasGameInstance())
async def cmd_remvp(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].remvp(message)


@router.message(IsOwner(), HasGameInstance(), Command("incmaxp"))
async def cmd_incmaxp(message: types.Message) -> None:
    # Thought this could be useful when I implemented this
    # It is not
    group_id = message.chat.id
    if (
        GlobalState.games[group_id].state != GameState.JOINING
        or GlobalState.games[group_id].max_players == GameSettings.INCREASED_MAX_PLAYERS
    ):
        await message.reply("smh")
        return

    if isinstance(GlobalState.games[group_id], EliminationGame):
        GlobalState.games[group_id].max_players = GameSettings.ELIM_INCREASED_MAX_PLAYERS
    else:
        GlobalState.games[group_id].max_players = GameSettings.INCREASED_MAX_PLAYERS
    await message.reply(
        f"This game can now accommodate {GlobalState.games[group_id].max_players} players."
    )


@router.message(HasGameInstance())
@router.edited_message(HasGameInstance())
async def answer_handler(message: types.Message) -> None:
    if message.text is None or not re.match(r"^[a-zA-Z]{1,100}$", message.text):
        return

    game = GlobalState.games[message.chat.id]
    if (
        game.players_in_game
        and message.from_user.id == game.players_in_game[0].user_id
        and not game.answered
        and game.accepting_answers
    ):
        await game.handle_answer(message)
