import asyncio
import time
from datetime import datetime

from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter, CommandHelp, CommandStart
from aiogram.utils.deep_linking import get_start_link
from aiogram.utils.markdown import quote_html

from .. import GlobalState, bot, dp
from ..constants import GameState
from ..utils import inline_keyboard_from_button, send_private_only_message
from ..words import Words


@dp.message_handler(CommandStart("help"), ChatTypeFilter([types.ChatType.PRIVATE]))
@dp.message_handler(CommandHelp())
async def cmd_help(message: types.Message) -> None:
    if message.chat.id < 0:
        await message.reply(
            "Please use this command in private.",
            allow_sending_without_reply=True,
            reply_markup=inline_keyboard_from_button(
                types.InlineKeyboardButton("Help message", url=await get_start_link("help"))
            )
        )
        return

    await message.reply(
        (
            "/gameinfo - Game mode descriptions\n"
            "/troubleshoot - Resolve common issues\n"
            "/reqaddword - Request addition of words\n"
            "/feedback - Send feedback to bot owner\n\n"
            "You may message [Jono](tg://user?id=463998526) "
            "in *English / Cantonese* if you have issues with the bot.\n"
            "Official Group: @on9wordchain\n"
            "Word Additions Channel (with status updates): @on9wcwa\n"
            "Source Code: [jonowo/on9wordchainbot](https://github.com/jonowo/on9wordchainbot)\n"
            "Epic icon designed by [Adri](tg://user?id=303527690)"
        ),
        disable_web_page_preview=True,
        allow_sending_without_reply=True
    )


@dp.message_handler(commands="gameinfo")
@send_private_only_message
async def cmd_gameinfo(message: types.Message) -> None:
    await message.reply(
        (
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
            "Elimination game with different modes. Try at @on9wordchain."
        ),
        allow_sending_without_reply=True
    )


@dp.message_handler(commands="troubleshoot")
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
        parse_mode=types.ParseMode.HTML,
        allow_sending_without_reply=True
    )


@dp.message_handler(commands="ping")
async def cmd_ping(message: types.Message) -> None:
    t = time.time()
    msg = await message.reply("Pong!", allow_sending_without_reply=True)
    await msg.edit_text(f"Pong! `{time.time() - t:.3f}s`")


@dp.message_handler(commands="chatid")
async def cmd_chatid(message: types.Message) -> None:
    await message.reply(f"`{message.chat.id}`", allow_sending_without_reply=True)


@dp.message_handler(commands="runinfo")
async def cmd_runinfo(message: types.Message) -> None:
    build_time_str = (
        "{0.day}/{0.month}/{0.year}".format(GlobalState.build_time)
        + " "
        + str(GlobalState.build_time.time())
        + " HKT"
    )
    uptime = datetime.now().replace(microsecond=0) - GlobalState.build_time
    await message.reply(
        (
            f"Build time: `{build_time_str}`\n"
            f"Uptime: `{uptime.days}.{str(uptime).rsplit(maxsplit=1)[-1]}`\n"
            f"Words in dictionary: `{Words.count}`\n"
            f"Total games: `{len(GlobalState.games)}`\n"
            f"Running games: `{len([g for g in GlobalState.games.values() if g.state == GameState.RUNNING])}`\n"
            f"Players: `{sum(len(g.players) for g in GlobalState.games.values())}`"
        ),
        allow_sending_without_reply=True
    )


@dp.message_handler(is_owner=True, commands="playinggroups")
async def cmd_playinggroups(message: types.Message) -> None:
    if not GlobalState.games:
        await message.reply("No groups are playing games.", allow_sending_without_reply=True)
        return

    groups = []

    async def append_group(group_id: int) -> None:
        try:
            group = await bot.get_chat(group_id)
            url = await group.get_url()
            # TODO: weakref exception is aiogram bug, wait fix
        except TypeError as e:
            if str(e) == "cannot create weak reference to 'NoneType' object":
                text = "???"
            else:
                text = f"(<code>{e.__class__.__name__}: {e}</code>)"
        except Exception as e:
            text = f"(<code>{e.__class__.__name__}: {e}</code>)"
        else:
            if url:
                text = f"<a href='{url}'>{quote_html(group.title)}</a>"
            else:
                text = f"<b>{group.title}</b>"

        if group_id not in GlobalState.games:  # In case the game ended during API calls
            return

        groups.append(
            text + (
                f" <code>{group_id}</code> "
                f"{len(GlobalState.games[group_id].players_in_game)}/{len(GlobalState.games[group_id].players)}P "
                f"{GlobalState.games[group_id].turns}W "
                f"{GlobalState.games[group_id].time_left}s"
            )
        )

    await asyncio.gather(*[append_group(gid) for gid in GlobalState.games])
    await message.reply(
        "\n".join(groups), parse_mode=types.ParseMode.HTML,
        disable_web_page_preview=True, allow_sending_without_reply=True
    )
