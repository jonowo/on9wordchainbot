import asyncio
from re import Match
from typing import Type

from aiogram import types
from aiogram.dispatcher.filters import RegexpCommandsFilter

from .. import GlobalState, dp, on9bot
from ..constants import GameSettings, GameState, VIP, VIP_GROUP
from ..models import ClassicGame, EliminationGame, GAME_MODES, MixedEliminationGame
from ..utils import amt_donated, send_groups_only_message


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
            (
                "Maintenance mode is on. Games are temporarily disabled.\n"
                "This is likely due to a pending bot update."
            ),
            allow_sending_without_reply=True
        )
        return

    await message.chat.update_chat()
    if message.chat.slow_mode_delay:
        await message.reply(
            (
                "Slow mode is enabled in this group, so the bot cannot function properly.\n"
                "If you are a group admin, please disable slow mode to start games."
            ),
            allow_sending_without_reply=True
        )
        return

    if (
        game_type is MixedEliminationGame and message.chat.id not in VIP_GROUP
        and message.from_user.id not in VIP and await amt_donated(message.from_user.id) < 30
    ):
        await message.reply(
            (
                "This game mode is a donation reward.\n"
                "You can try this game mode at @on9wordchain."
            ),
            allow_sending_without_reply=True
        )
        return

    async with GlobalState.games_lock:  # Avoid duplicate game creation
        if group_id in GlobalState.games:
            asyncio.create_task(GlobalState.games[group_id].join(message))
        else:
            game = game_type(message.chat.id)
            GlobalState.games[group_id] = game
            asyncio.create_task(game.main_loop(message))


@dp.message_handler(RegexpCommandsFilter([r"^/(start[a-z]+)"]))
async def cmd_startgame(message: types.Message, regexp_command: Match) -> None:
    command = regexp_command.groups()[0].lower()
    if command == "startgame":
        await start_game(message, ClassicGame)
        return

    for mode in GAME_MODES:
        if mode.command == command:
            await start_game(message, mode)
            return


@dp.message_handler(commands="join")
@send_groups_only_message
async def cmd_join(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GlobalState.games:
        await GlobalState.games[group_id].join(message)


@dp.message_handler(is_owner=True, game_running=True, commands="forcejoin")
async def cmd_forcejoin(message: types.Message) -> None:
    group_id = message.chat.id
    rmsg = message.reply_to_message
    if rmsg and rmsg.from_user.is_bot:  # On9Bot only
        if rmsg.from_user.id == on9bot.id:
            await cmd_addvp(message)
        return
    await GlobalState.games[group_id].forcejoin(message)


@dp.message_handler(game_running=True, commands="extend")
async def cmd_extend(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].extend(message)


@dp.message_handler(is_admin=True, game_running=True, commands="forcestart")
async def cmd_forcestart(message: types.Message) -> None:
    group_id = message.chat.id
    if GlobalState.games[group_id].state == GameState.JOINING:
        GlobalState.games[group_id].time_left = -99999


@dp.message_handler(game_running=True, commands="flee")
async def cmd_flee(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].flee(message)


@dp.message_handler(is_owner=True, game_running=True, commands="forceflee")
async def cmd_forceflee(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].forceflee(message)


@dp.message_handler(is_owner=True, commands=["killgame", "killgaym"])
async def cmd_killgame(message: types.Message) -> None:
    try:
        group_id = int(message.get_args() or message.chat.id)
        assert group_id < 0, "smh"
        assert group_id in GlobalState.games, "no game running"
    except (ValueError, AssertionError) as e:
        await message.reply(f"`{e.__class__.__name__}: {e}`", allow_sending_without_reply=True)
        return

    GlobalState.games[group_id].state = GameState.KILLGAME
    await asyncio.sleep(2)

    # If game is still not terminated
    if group_id in GlobalState.games:
        del GlobalState.games[group_id]
        await message.reply("Game ended forcibly.", allow_sending_without_reply=True)


@dp.message_handler(is_owner=True, game_running=True, commands="forceskip")
async def cmd_forceskip(message: types.Message) -> None:
    group_id = message.chat.id
    if GlobalState.games[group_id].state == GameState.RUNNING and not GlobalState.games[group_id].answered:
        GlobalState.games[group_id].time_left = 0


@dp.message_handler(game_running=True, commands="addvp")
async def cmd_addvp(message: types.Message) -> None:
    group_id = message.chat.id
    if isinstance(GlobalState.games[group_id], EliminationGame):
        await message.reply(
            (
                f"Sorry, [{(await on9bot.me).full_name}](https://t.me/{(await on9bot.me).username}) "
                "can't play elimination games."
            ),
            disable_web_page_preview=True, allow_sending_without_reply=True
        )
        return
    await GlobalState.games[group_id].addvp(message)


@dp.message_handler(game_running=True, commands="remvp")
async def cmd_remvp(message: types.Message) -> None:
    await GlobalState.games[message.chat.id].remvp(message)


@dp.message_handler(is_owner=True, game_running=True, commands="incmaxp")
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
        f"This game can now accommodate {GlobalState.games[group_id].max_players} players.",
        allow_sending_without_reply=True
    )


@dp.message_handler(game_running=True, regexp=r"^[a-zA-Z]+$")
@dp.edited_message_handler(game_running=True, regexp=r"^[a-zA-Z]+$")
async def answer_handler(message: types.Message) -> None:
    # TODO: Modify to support other languages (including regexp)
    group_id = message.chat.id
    if (
        GlobalState.games[group_id].players_in_game
        and message.from_user.id == GlobalState.games[group_id].players_in_game[0].user_id
        and not GlobalState.games[group_id].answered
        and GlobalState.games[group_id].accepting_answers
    ):
        await GlobalState.games[group_id].handle_answer(message)
