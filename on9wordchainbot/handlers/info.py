import asyncio
import time
from datetime import datetime

from aiogram import Router, F, types, html
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link

from on9wordchainbot.resources import GlobalState
from on9wordchainbot.constants import GameState
from on9wordchainbot.utils import inline_keyboard_from_button, send_private_only_message
from on9wordchainbot.filters import IsOwner
from on9wordchainbot.words import Words

router = Router(name=__name__)


@router.message(CommandStart(deep_link=True, magic=F.args == "help"), F.chat.type == ChatType.PRIVATE)
@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    if message.chat.id < 0:
        start_link = await create_start_link(message.bot, "help")
        await message.reply(
            "Please use this command in private.",
            reply_markup=inline_keyboard_from_button(
                types.InlineKeyboardButton(text="Help message", url=start_link)
            )
        )
        return

    await message.reply(
        "/gameinfo - Game mode descriptions\n"
        "/troubleshoot - Resolve common issues\n"
        "/reqaddword - Request addition of words\n"
        "/feedback - Send feedback to bot owner\n\n"
        "You may message [Jono](tg://user?id=463998526) "
        "in *English / Cantonese* if you have issues with the bot.\n"
        "Official Group: https://t.me/+T30aTNo-2Xx2kc52\n"
        "Word Additions Channel (with status updates): @on9wcwa\n"
        "Source Code: [jonowo/on9wordchainbot](https://github.com/jonowo/on9wordchainbot)\n"
        "Epic icon designed by [Adri](tg://user?id=303527690)"
    )


@router.message(Command("gameinfo"))
@send_private_only_message
async def cmd_gameinfo(message: types.Message) -> None:
    await message.reply(
        "/startclassic - Classic game\n"
        "Players take turns to send words starting with the last letter of the previous word.\n\n"
        "Variants:\n"
        "/starthard - Hard mode game\n"
        "/startchaos - Chaos game (random turn order)\n"
        "/startcfl - Chosen first letter game\n"
        "/startrfl - Random first letter game\n"
        "/startbl - Banned letters game\n"
        "/startrl - Required letter game\n\n"
        "/startelim - Elimination game\n"
        "Each player's score is their cumulative word length. "
        "The lowest scoring players are eliminated after each round.\n\n"
        "/startmelim - Mixed elimination game (donation reward)\n"
        "Elimination game with different modes. Try at the [official group](https://t.me/+T30aTNo-2Xx2kc52)."
    )


@router.message(Command("troubleshoot"))
@send_private_only_message
async def cmd_troubleshoot(message: types.Message) -> None:
    await message.reply(
        (
            "These steps assume you have admin privileges. "
            "If you do not, please ask a group admin to check instead.\n\n"
            "<b>If the bot does not respond to <code>/start[mode]</code></b>, check if:\n"
            "1. The bot is absent from / muted in your group "
            "\u27a1\ufe0f Add the bot to your group / Unmute the bot\n"
            "2. Slow mode is enabled \u27a1\ufe0f Disable slow mode\n"
            "3. Someone spammed commands in your group recently "
            "\u27a1\ufe0f The bot is rate limited in your group, wait patiently\n"
            "4. The bot does not respond to <code>/ping</code> "
            "\u27a1\ufe0f The bot is likely offline, check @on9wcwa for status updates\n\n"
            "<b>If the bot cannot be added to your group</b>:\n"
            "1. There can be at most 20 bots in a group. Check if this limit is reached.\n\n"
            "If you encounter other issues, please contact <a href='tg://user?id=463998526'>my owner</a>."
        ),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("ping"))
async def cmd_ping(message: types.Message) -> None:
    t = time.time()
    msg = await message.reply("Pong!")
    await msg.edit_text(f"Pong! `{time.time() - t:.3f}s`")


@router.message(Command("chatid"))
async def cmd_chatid(message: types.Message) -> None:
    await message.reply(f"`{message.chat.id}`")


@router.message(Command("runinfo"))
async def cmd_runinfo(message: types.Message) -> None:
    build_time_str = (
        "{0.day}/{0.month}/{0.year}".format(GlobalState.build_time)
        + " "
        + str(GlobalState.build_time.time())
        + " HKT"
    )
    uptime = datetime.now().replace(microsecond=0) - GlobalState.build_time
    await message.reply(
        f"Build time: `{build_time_str}`\n"
        f"Uptime: `{uptime.days}.{str(uptime).rsplit(maxsplit=1)[-1]}`\n"
        f"Words in dictionary: `{Words.count}`\n"
        f"Total games: `{len(GlobalState.games)}`\n"
        f"Running games: `{len([g for g in GlobalState.games.values() if g.state == GameState.RUNNING])}`\n"
        f"Players: `{sum(len(g.players) for g in GlobalState.games.values())}`"
    )


@router.message(IsOwner(), Command("playinggroups"))
async def cmd_playinggroups(message: types.Message) -> None:
    if not GlobalState.games:
        await message.reply("No groups are playing games.")
        return

    # TODO: return and gather the result instead of doing append
    groups = []

    async def append_group(group_id: int) -> None:
        try:
            group = await message.bot.get_chat(group_id)
        except Exception as e:
            text = f"<code>[{e.__class__.__name__}: {e}]</code>"
        else:
            if group.username:
                text = f"<a href='https://t.me/{group.username}'>{html.quote(group.title)}</a>"
            else:
                text = f"<b>{group.title}</b>"

        if group_id not in GlobalState.games:  # In case the game ended during API calls
            return

        game = GlobalState.games[group_id]
        groups.append(
            text + (
                f" <code>{group_id}</code> "
                f"{len(game.players_in_game)}/{len(game.players)}P "
                f"{game.turns}W {game.time_left}s"
            )
        )

    await asyncio.gather(*[append_group(gid) for gid in GlobalState.games])
    await message.reply("\n".join(groups), parse_mode=ParseMode.HTML)
