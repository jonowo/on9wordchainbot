import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP, InvalidOperation
from random import seed
from string import ascii_lowercase
from time import time
from uuid import uuid4

import aiofiles
import aiofiles.os  # necessary
import matplotlib.pyplot as plt
from aiogram import executor, types
from aiogram.types.message import ContentTypes
from aiogram.utils.exceptions import TelegramAPIError, BadRequest, MigrateToChat
from aiogram.utils.markdown import quote_html
from matplotlib.ticker import MaxNLocator

from constants import (bot, dp, BOT_ID, ON9BOT_ID, VIP, VIP_GROUP, ADMIN_GROUP_ID, OFFICIAL_GROUP_ID, GAMES, pool,
                       PROVIDER_TOKEN, WORDS, WORDS_LI, GameState, GameSettings, amt_donated)
from game import (ClassicGame, HardModeGame, ChaosGame, ChosenFirstLetterGame, BannedLettersGame, RequiredLetterGame,
                  EliminationGame, MixedEliminationGame)

seed(time())
getcontext().rounding = ROUND_HALF_UP
build_time = datetime.now().replace(microsecond=0)
MAINT_MODE = False


async def groups_only_command(message: types.Message) -> None:
    await message.reply(
        "You must run this command in a group.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton("Add me to a group!", url="https://t.me/on9wordchainbot?startgroup=_")
        ]])
    )


@dp.message_handler(is_group=False, commands="start")
async def cmd_start(message: types.Message) -> None:
    arg = message.get_args()
    if arg == "help":
        await cmd_help(message)
        return
    elif arg == "donate":
        await send_donate_msg(message)
        return
    await message.reply(
        "Terms of Service\n\n"
        "0. You *MUST* report bugs you encounter to this bot's owner - "
        "[Trainer Jono](https://t.me/Trainer_Jono).\n\n"
        "1. You understand that complaints about missing words are usually ignored since this bot's owner is not "
        "responsible for such issues.\n\n"
        "2. You will forgive this bot's owner in case a game suddenly ends, usually due to him forgetting to check if "
        "there were running games before manually terminating this bot's program.\n\n"
        "By starting this bot, you have agreed to the above terms of service.\n"
        "Add me to a group to start playing games!",
        disable_web_page_preview=True,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton("Add me to a group!", url="https://t.me/on9wordchainbot?startgroup=_")
        ]])
    )


@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member(message: types.Message) -> None:
    if any(user.id == BOT_ID for user in message.new_chat_members):
        await message.reply("Thanks for adding me. Click /startclassic to start a classic game!", reply=False)
    elif message.chat.id == OFFICIAL_GROUP_ID:
        await message.reply("Welcome to the official On9 Word Chain group!\n"
                            "Click /startclassic to start a classic game!")


@dp.message_handler(commands="help")
async def cmd_help(message: types.Message) -> None:
    if message.chat.id < 0:
        await message.reply("Please use this command in private.", reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[
                types.InlineKeyboardButton(
                    "Send help message in private", url="https://t.me/on9wordchainbot?start=help"
                )
            ]]
        ))
        return
    await message.reply(
        "I provide several variations of the English game _Word Chain_.\n\n"
        "/startclassic - Classic game\n"
        "Players come up with words that begin with the last letter of the previous word. Players unable to come up "
        "with a word in time are eliminated from the game. The time limit decreases and the minimum word length limit "
        "increases throughout the game to level up the difficulty.\n\n"
        "/starthard - Hard mode game\n"
        "Classic gameplay starting with the most difficult settings.\n\n"
        "/startchaos - Chaos game\n"
        "Classic gameplay but without turn order, players are selected to answer by random.\n\n"
        "/startcfl - Chosen first letter game\n"
        "Players come up with words starting with the chosen letter.\n\n"
        "/startbl - Banned letters game\n"
        "Classic gameplay but 2-4 letters (incl. max one vowel) are banned and cannot be present in answers.\n\n"
        "/startrl - Required letter game\n"
        "Classic gameplay but a specific letter must be present in answers.\n\n"
        "/startelim - Elimination game\n"
        "Each player has a score, which is their cumulative word length. After each player has played a round, the "
        "player(s) with the lowest score get eliminated from the game.\n\n"
        "/startmelim - Mixed elimination game (Donation reward)\n"
        "Elimination game with four modes: classic, chosen first letter, banned letters and require letter. Modes "
        "switch every round.",
        disable_web_page_preview=True
    )


@dp.message_handler(commands="info")
async def cmd_info(message: types.Message) -> None:
    await message.reply(
        "[Official channel](https://t.me/On9Updates)\n"
        "[Official group](https://t.me/on9wordchain)\n"
        "[GitHub repo: Tr-Jono/on9wordchainbot](https://github.com/Tr-Jono/on9wordchainbot)\n"
        "Feel free to PM my owner [Trainer Jono](https://t.me/Trainer_Jono) in English or Cantonese.\n",
        disable_web_page_preview=True
    )


@dp.message_handler(commands="ping")
async def cmd_ping(message: types.Message) -> None:
    t = time()
    msg = await message.reply("Pong!")
    await msg.edit_text(f"Pong! `{time() - t:.3f}s`")


@dp.message_handler(commands="runinfo")
async def cmd_runinfo(message: types.Message) -> None:
    uptime = datetime.now().replace(microsecond=0) - build_time
    await message.reply(
        f"Build time: `{'{0.day}/{0.month}/{0.year}'.format(build_time)} {str(build_time).split()[1]} HKT`\n"
        f"Uptime: `{uptime.days}.{str(uptime).rsplit(maxsplit=1)[-1]}`\n"
        f"Total games: `{len(GAMES)}`\n"
        f"Running games: `{len([g for g in GAMES.values() if g.state == GameState.RUNNING])}`\n"
        f"Players: `{sum([len(g.players) for g in GAMES.values()])}`"
    )


@dp.message_handler(is_owner=True, commands="playinggroups")
async def cmd_playinggroups(message: types.Message) -> None:
    if not GAMES:
        await message.reply("No groups are playing games.")
        return
    groups = []
    for group_id in GAMES:
        group = await bot.get_chat(group_id)
        url = await group.get_url()
        if url:
            groups.append(f"[{group.title}]({url})")
        else:
            groups.append(f"{group.title} {group.id}")
    await message.reply("\n".join(groups), disable_web_page_preview=True)


@dp.message_handler(commands=["exist", "exists"])
async def cmd_exists(message: types.Message) -> None:
    word = message.text.partition(" ")[2].lower()
    if not word or any(c not in ascii_lowercase for c in word):
        rmsg = message.reply_to_message
        if rmsg and rmsg.text and all([c in ascii_lowercase for c in rmsg.text.lower()]):
            word = message.reply_to_message.text.lower()
        else:
            await message.reply("Usage example: `/exists astrophotographer`")
            return
    if word in WORDS[word[0]]:
        await message.reply(f"_{word.capitalize()}_ EXISTS in my list of words.")
        return
    await message.reply(f"_{word.capitalize()}_ DOES NOT EXIST in my list of words.")


@dp.message_handler(commands="startclassic")
async def cmd_startclassic(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = ClassicGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="starthard")
async def cmd_starthard(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = HardModeGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startchaos")
async def cmd_startchaos(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = ChaosGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startcfl")
async def cmd_startcfl(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = ChosenFirstLetterGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startbl")
async def cmd_startbl(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = BannedLettersGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startrl")
async def cmd_startrl(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = RequiredLetterGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startelim")
async def cmd_startelim(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = EliminationGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="startmelim")
async def cmd_startmixedelim(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    if (message.chat.id not in VIP_GROUP and message.from_user.id not in VIP
            and (await amt_donated(message.from_user.id)) < 30):
        await message.reply("Ability to start this mode is rewarded for donating.")
        return
    if MAINT_MODE:
        await message.reply("Maintenance mode is on. Games are temporarily disabled.")
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
        return
    game = MixedEliminationGame(message.chat.id)
    GAMES[group_id] = game
    await game.main_loop(message)


@dp.message_handler(commands="join")
async def cmd_join(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
    # Due to privacy settings, no reply is given when there is no running game


@dp.message_handler(is_group=True, is_owner=True, commands="forcejoin")
async def cmd_forcejoin(message: types.Message) -> None:
    group_id = message.chat.id
    rmsg = message.reply_to_message
    if group_id not in GAMES:
        return
    if rmsg and rmsg.from_user.is_bot:
        if rmsg.from_user.id != ON9BOT_ID:
            return
        if isinstance(GAMES[group_id], EliminationGame):
            await message.reply("Sorry, [On9Bot](https://t.me/On9Bot) can't play elimination games.",
                                disable_web_page_preview=True)
            return
    await GAMES[message.chat.id].forcejoin(message)


@dp.message_handler(is_group=True, commands="extend")
async def cmd_extend(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].extend(message)


@dp.message_handler(is_group=True, is_admin=True, commands="forcestart")
async def cmd_forcestart(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES and GAMES[group_id].state == GameState.JOINING:
        GAMES[group_id].time_left = -99999


@dp.message_handler(is_group=True, commands="flee")
async def cmd_flee(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].flee(message)


@dp.message_handler(is_group=True, is_owner=True, commands="forceflee")
async def cmd_forceflee(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].forceflee(message)


@dp.message_handler(is_group=True, is_owner=True, commands=["killgame", "killgaym"])
async def cmd_killgame(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        GAMES[group_id].state = GameState.KILLGAME


@dp.message_handler(is_group=True, is_owner=True, commands="forceskip")
async def cmd_forceskip(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES and GAMES[group_id].state == GameState.RUNNING and not GAMES[group_id].answered:
        GAMES[group_id].time_left = 0


@dp.message_handler(is_group=True, commands="addvp")
async def addvp(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id not in GAMES:
        return
    if isinstance(GAMES[group_id], EliminationGame):
        await message.reply("Sorry, [On9Bot](https://t.me/On9Bot) can't play elimination games.",
                            disable_web_page_preview=True)
        return
    await GAMES[group_id].addvp(message)


@dp.message_handler(is_group=True, commands="remvp")
async def remvp(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].remvp(message)


@dp.message_handler(is_group=True, is_owner=True, commands="incmaxp")
async def cmd_incmaxp(message: types.Message) -> None:
    group_id = message.chat.id
    if (group_id not in GAMES or GAMES[group_id].state != GameState.JOINING
            or GAMES[group_id].max_players == GameSettings.INCREASED_MAX_PLAYERS):
        return
    await message.reply(f"Max players for this game increased from {GAMES[group_id].max_players} to "
                        f"{GameSettings.INCREASED_MAX_PLAYERS}.")
    GAMES[group_id].max_players = GameSettings.INCREASED_MAX_PLAYERS


@dp.message_handler(is_owner=True, commands="maintmode")
async def cmd_maintmode(message: types.Message) -> None:
    global MAINT_MODE
    MAINT_MODE = not MAINT_MODE
    await message.reply(f"Maintenance mode has been switched {'on' if MAINT_MODE else 'off'}.")


@dp.message_handler(is_group=True, is_owner=True, commands="leave")
async def cmd_leave(message: types.Message) -> None:
    await message.chat.leave()


@dp.message_handler(commands="stats")
async def cmd_stats(message: types.Message) -> None:
    rmsg = message.reply_to_message
    if (message.chat.id < 0 and not message.get_command().partition("@")[2]
            or rmsg and (rmsg.from_user.is_bot and rmsg.from_user.id != ON9BOT_ID
                         or rmsg.forward_from and rmsg.forward_from.is_bot and rmsg.forward_from.id != ON9BOT_ID)):
        return
    user = rmsg.forward_from or rmsg.from_user if rmsg else message.from_user
    async with pool.acquire() as conn:
        res = await conn.fetchrow("SELECT * FROM player WHERE user_id = $1;", user.id)
    if not res:
        await message.reply(f"No statistics for {user.get_mention(as_html=True)}!", parse_mode=types.ParseMode.HTML)
        return
    await message.reply(
        f"\U0001f4ca Statistics for "
        + user.get_mention(name=user.full_name + (" \u2b50\ufe0f" if user.id in VIP or bool(await amt_donated(user.id))
                                                  else ""), as_html=True)
        + f":\n"
          f"<b>{res['game_count']}</b> games played\n"
          f"<b>{res['win_count']} ("
          f"{'0%' if not res['win_count'] else format(res['win_count'] / res['game_count'], '.0%')})</b> games won\n"
          f"<b>{res['word_count']}</b> total words played\n"
          f"<b>{res['letter_count']}</b> total letters played"
        + (f"\nLongest word used: <b>{res['longest_word'].capitalize()}</b>" if res["longest_word"] else ""),
        parse_mode=types.ParseMode.HTML
    )


@dp.message_handler(commands="groupstats")
async def cmd_groupstats(message: types.Message) -> None:
    if message.chat.id > 0:
        await groups_only_command(message)
        return
    async with pool.acquire() as conn:
        player_count, game_count, word_count, letter_count = await conn.fetchrow("""\
SELECT COUNT(DISTINCT user_id), COUNT(DISTINCT game_id), SUM(word_count), SUM(letter_count)
    FROM gameplayer
    WHERE group_id = $1;""", message.chat.id)
    await message.reply(f"\U0001f4ca Statistics for <b>{quote_html(message.chat.title)}</b>\n"
                        f"<b>{player_count}</b> players\n"
                        f"<b>{game_count}</b> games played\n"
                        f"<b>{word_count}</b> total words played\n"
                        f"<b>{letter_count}</b> total letters played",
                        parse_mode=types.ParseMode.HTML)


@dp.message_handler(commands="globalstats")
async def cmd_globalstats(message: types.Message) -> None:
    async with pool.acquire() as conn:
        group_count, game_count = await conn.fetchrow("SELECT COUNT(DISTINCT group_id), COUNT(*) FROM game;")
        player_count, word_count, letter_count = await conn.fetchrow(
            "SELECT COUNT(*), SUM(word_count), SUM(letter_count) FROM player;"
        )
    await message.reply("\U0001f4ca Global statistics\n"
                        f"*{group_count}* groups\n"
                        f"*{player_count}* players\n"
                        f"*{game_count}* games played\n"
                        f"*{word_count}* total words played\n"
                        f"*{letter_count}* total letters played")


@dp.message_handler(is_vip=True, commands=["trend", "trends"])
async def cmd_trends(message: types.Message) -> None:
    try:
        days = int(message.get_args() or 7)
        assert days > 1, "smh"
    except (ValueError, AssertionError) as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`")
        return
    d = datetime.now().date()
    tp = [d - timedelta(days=i) for i in range(days - 1, -1, -1)]
    tp_str = [f"{i.day}/{i.month}" for i in tp]
    async with pool.acquire() as conn:
        daily_games = dict(await conn.fetch("""\
SELECT start_time::DATE d, COUNT(start_time::DATE)
    FROM game
    WHERE start_time::DATE >= $1
    GROUP BY d
    ORDER BY d;""", d - timedelta(days=days - 1)))
        active_players = dict(await conn.fetch("""\
SELECT game.start_time::DATE d, COUNT(DISTINCT gameplayer.user_id)
    FROM gameplayer
    INNER JOIN game ON gameplayer.game_id = game.id
    WHERE game.start_time::DATE >= $1
    GROUP BY d
    ORDER BY d;""", d - timedelta(days=days - 1)))
        active_groups = dict(await conn.fetch("""\
SELECT start_time::DATE d, COUNT(DISTINCT group_id)
    FROM game
    WHERE game.start_time::DATE >= $1
    GROUP BY d
    ORDER BY d;""", d - timedelta(days=days - 1)))
        cumulative_groups = dict(await conn.fetch("""\
SELECT *
    FROM (
        SELECT d, SUM(count) OVER (ORDER BY d)
            FROM (
                SELECT d, COUNT(group_id)
                    FROM (
                        SELECT DISTINCT group_id, MIN(start_time::DATE) d
                            FROM game
                            GROUP BY group_id
                    ) gd
                    GROUP BY d
            ) dg
    ) ds
    WHERE d >= $1;""", d - timedelta(days=days - 1)))
        dt = d - timedelta(days=days)
        for i in range(days):
            dt += timedelta(days=1)
            if dt not in cumulative_groups:
                if not i:
                    cumulative_groups[dt] = await conn.fetchval(
                        "SELECT COUNT(DISTINCT group_id) FROM game WHERE start_time::DATE <= $1;", dt
                    )
                else:
                    cumulative_groups[dt] = cumulative_groups[dt - timedelta(days=1)]
        cumulative_players = dict(await conn.fetch("""\
SELECT *
    FROM (
        SELECT d, SUM(count) OVER (ORDER BY d)
            FROM (
                SELECT d, COUNT(user_id)
                    FROM (
                        SELECT DISTINCT user_id, MIN(start_time::DATE) d
                            FROM gameplayer
                            INNER JOIN game ON game_id = game.id
                            GROUP BY user_id
                    ) ud
                    GROUP BY d
            ) du
    ) ds
    WHERE d >= $1;""", d - timedelta(days=days - 1)))
        dt = d - timedelta(days=days)
        for i in range(days):
            dt += timedelta(days=1)
            if dt not in cumulative_players:
                if not i:
                    cumulative_players[dt] = await conn.fetchval("""\
    SELECT COUNT(DISTINCT user_id)
        FROM gameplayer
        INNER JOIN game ON game_id = game.id
        WHERE start_time <= $1;""", dt)
                else:
                    cumulative_players[dt] = cumulative_players[dt - timedelta(days=1)]
        game_mode_play_cnt = await conn.fetch("""\
SELECT COUNT(game_mode), game_mode
    FROM game
    WHERE start_time::DATE >= $1
    GROUP BY game_mode
    ORDER BY count;""", d - timedelta(days=days - 1))
        total_games = sum(i[0] for i in game_mode_play_cnt)
    plt.figure(figsize=(15, 8))
    plt.suptitle(f"Trends in the Past {days} Days", size=25)
    sp = plt.subplot(231)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))  # Force y-axis intervals to be integral
    plt.title("Games Played", size=18)
    plt.plot(tp_str, [daily_games.get(i, 0) for i in tp])
    plt.ylim(ymin=0)
    sp = plt.subplot(232)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.title("Active Groups", size=18)
    plt.plot(tp_str, [active_groups.get(i, 0) for i in tp])
    plt.ylim(ymin=0)
    sp = plt.subplot(233)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.title("Active Players", size=18)
    plt.plot(tp_str, [active_players.get(i, 0) for i in tp])
    plt.ylim(ymin=0)
    plt.subplot(234)
    labels = [i[1] for i in game_mode_play_cnt]
    colors = ["dark maroon", "dark peach", "orange", "leather", "mustard", "teal", "french blue", "booger"][
             8 - len(game_mode_play_cnt):]
    slices, text = plt.pie([i[0] for i in game_mode_play_cnt],
                           labels=[f"{i[0] / total_games:.1%} ({i[0]})" if i[0] / total_games >= 0.03
                                   else "" for i in game_mode_play_cnt],
                           colors=["xkcd:" + c for c in colors], startangle=90)
    plt.legend(slices, labels, title="Game Modes Played", fontsize="x-small", loc="best")
    plt.axis("equal")
    sp = plt.subplot(235)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.title("Cumulative Groups", size=18)
    plt.plot(tp_str, [cumulative_groups[i] for i in tp])
    sp = plt.subplot(236)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.title("Cumulative Players", size=18)
    plt.plot(tp_str, [cumulative_players[i] for i in tp])
    while os.path.exists("trends.jpg"):
        await asyncio.sleep(0.1)
    plt.savefig("trends.jpg", bbox_inches="tight")
    async with aiofiles.open("trends.jpg", "rb") as f:
        await message.reply_photo(f)
    await aiofiles.os.remove("trends.jpg")


@dp.message_handler(commands="donate")
async def cmd_donate(message: types.Message) -> None:
    if message.chat.id < 0:
        await message.reply("Please donate in private.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton("Donate in private", url="https://t.me/on9wordchainbot?start=donate")
        ]]))
        return
    arg = message.get_args()
    if not arg:
        await send_donate_msg(message)
    else:
        try:
            amt = int(Decimal(arg).quantize(Decimal("1.00")) * 100)
            assert amt > 0
            await send_donate_invoice(message.chat.id, amt)
        except (ValueError, InvalidOperation, AssertionError):
            await message.reply("Invalid amount.\nPlease enter a positive number.")
        except BadRequest as e:
            if str(e) == "Currency_total_amount_invalid":
                await message.reply("Sorry, the entered amount was not within 1-10000 USD. Please try another amount.")
                return
            raise


async def send_donate_msg(message: types.Message) -> None:
    await message.reply(
        "Donate to support this project! \u2764\ufe0f\n"
        "Donations are accepted in HKD (1 USD ≈ 7.84 HKD).\n"
        "Select one of the following options or type in the desired amount in HKD (e.g. `/donate 42.42`).\n\n"
        "Donation rewards:\n"
        "Any amount: \u2b50\ufe0f is displayed next to your name during games.\n"
        "10 HKD (cumulative): Search words in inline queries (e.g. `@on9wordchainbot test`)\n"
        "30 HKD (cumulative): Start mixed elimination games (`/startmelim`)\n",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton("10 HKD", callback_data="donate:10"),
                types.InlineKeyboardButton("20 HKD", callback_data="donate:20"),
                types.InlineKeyboardButton("30 HKD", callback_data="donate:30")
            ],
            [
                types.InlineKeyboardButton("50 HKD", callback_data="donate:50"),
                types.InlineKeyboardButton("100 HKD", callback_data="donate:100")
            ]
        ])
    )


async def send_donate_invoice(user_id: int, amt: int) -> None:
    await bot.send_invoice(
        chat_id=user_id,
        title="On9 Word Chain Bot Donation",
        description="Support bot development",
        payload=f"on9wordchainbot_donation:{user_id}",
        provider_token=PROVIDER_TOKEN,
        start_parameter="donate",
        currency="HKD",
        prices=[types.LabeledPrice("Donation", amt)]
    )


@dp.pre_checkout_query_handler()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery) -> None:
    if pre_checkout_query.invoice_payload == f"on9wordchainbot_donation:{pre_checkout_query.from_user.id}":
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id, ok=False,
            error_message="Donation unsuccessful. No money was deducted from your credit card. "
                          "Mind requesting a new invoice and try again? :D"
        )


@dp.message_handler(content_types=ContentTypes.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message) -> None:
    payment = message.successful_payment
    donation_id = str(uuid4())[:8]
    amt = Decimal(payment.total_amount) / 100
    dt = datetime.now().replace(microsecond=0)
    async with pool.acquire() as conn:
        await conn.execute("""\
INSERT INTO donation (donation_id, user_id, amount, donate_time, telegram_payment_charge_id, provider_payment_charge_id)
VALUES
    ($1, $2, $3::NUMERIC, $4, $5, $6)""",
                           donation_id, message.from_user.id, str(amt), dt,
                           payment.telegram_payment_charge_id, payment.provider_payment_charge_id)
    await message.reply(f"Your donation of {amt} HKD is successful.\n"
                        "Thank you for your support! \u2764\ufe0f\n"
                        f"Donation id: #on9wcbot\_{donation_id}",
                        reply=False)
    await bot.send_message(ADMIN_GROUP_ID,
                           f"Received donation of {amt} HKD from {message.from_user.get_mention(as_html=True)} "
                           f"(id: <code>{message.from_user.id}</code>).\n"
                           f"Donation id: #on9wcbot\_{donation_id}",
                           parse_mode=types.ParseMode.HTML)


@dp.message_handler(is_owner=True, commands="sql")
async def cmd_sql(message: types.Message) -> None:
    try:
        async with pool.acquire() as conn:
            res = await conn.fetch(message.get_full_command()[1])
    except Exception as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`")
        return
    if not res:
        await message.reply("No results returned.")
        return
    text = ["*" + " - ".join(res[0].keys()) + "*"]
    for r in res:
        text.append("`" + " - ".join([str(i) for i in r.values()]) + "`")
    await message.reply("\n".join(text))


@dp.message_handler(commands="feedback")
async def cmd_feedback(message: types.Message) -> None:
    rmsg = message.reply_to_message
    if (message.chat.id < 0 and not message.get_command().partition("@")[2]
            and (not rmsg or rmsg.from_user.id != BOT_ID)):
        return
    arg = message.get_full_command()[1]
    if not arg:
        await message.reply("Send feedback to my owner using this function.\n"
                            "Usage example: `/feedback@on9wordchainbot JS is very on9`")
        return
    await message.forward(ADMIN_GROUP_ID)
    await message.reply("Feedback sent successfully.")


@dp.message_handler(is_group=True, regexp="^\w+$")
@dp.edited_message_handler(is_group=True, regexp="^\w+$")
async def message_handler(message: types.Message) -> None:
    group_id = message.chat.id
    if (group_id in GAMES and GAMES[group_id].players_in_game
            and message.from_user.id == GAMES[group_id].players_in_game[0].user_id
            and not GAMES[group_id].answered and GAMES[group_id].accepting_answers
            and all([c in ascii_lowercase for c in message.text.lower()])):
        await GAMES[group_id].handle_answer(message)


@dp.inline_handler()
async def inline_handler(inline_query: types.InlineQuery):
    text = inline_query.query.lower()
    if not text or inline_query.from_user.id not in VIP and (await amt_donated(inline_query.from_user.id)) < 10:
        await inline_query.answer([
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a classic game", description="/startclassic@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startclassic@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a hard mode game", description="/starthard@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/starthard@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a chaos game", description="/startchaos@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startchaos@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a chosen first letter game", description="/startcfl@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startcfl@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a banned letters game", description="/startbl@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startbl@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start a required letter game", description="/startrl@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startrl@on9wordchainbot")
            ),
            types.InlineQueryResultArticle(
                id=str(uuid4()), title="Start an elimination game", description="/startelim@on9wordchainbot",
                input_message_content=types.InputTextMessageContent("/startelim@on9wordchainbot")
            )
        ], is_personal=not text)
        return
    if any(c not in ascii_lowercase for c in text):
        await inline_query.answer([types.InlineQueryResultArticle(
            id=str(uuid4()), title="A query may only consist of alphabets", description="Try a different query",
            input_message_content=types.InputTextMessageContent(r"¯\\_(ツ)\_/¯")
        )], is_personal=True)
        return
    res = []
    for i in WORDS_LI[text[0]]:
        if i.startswith(text):
            i = i.capitalize()
            res.append(types.InlineQueryResultArticle(id=str(uuid4()), title=i,
                                                      input_message_content=types.InputTextMessageContent(i)))
            if len(res) == 50:
                break
    if not res:
        res.append(types.InlineQueryResultArticle(
            id=str(uuid4()), title="No results found", description="Try a different query",
            input_message_content=types.InputTextMessageContent(r"¯\\_(ツ)\_/¯")
        ))
    await inline_query.answer(res, is_personal=True)


@dp.callback_query_handler()
async def callback_query_handler(callback_query: types.CallbackQuery) -> None:
    text = callback_query.data
    if text.startswith("donate"):
        await send_donate_invoice(callback_query.from_user.id, int(text.split(":")[1]) * 100)
    await callback_query.answer()


@dp.errors_handler(exception=TelegramAPIError)
async def error_handler(update: types.Update, error: TelegramAPIError) -> None:
    if isinstance(error, BadRequest) and str(error) == "Reply message not found":
        return
    if isinstance(error, MigrateToChat):
        if update.message.chat.id in GAMES:
            GAMES[error.migrate_to_chat_id] = GAMES.pop(update.message.chat.id)
            GAMES[error.migrate_to_chat_id].group_id = error.migrate_to_chat_id
        async with pool.acquire() as conn:
            await conn.execute("UPDATE game SET group_id = $1 WHERE group_id = $2;\n"
                               "UPDATE gameplayer SET group_id = $1 WHERE group_id = $2;",
                               error.migrate_to_chat_id, update.message.chat.id)
        return
    await bot.send_message(ADMIN_GROUP_ID,
                           f"`{error.__class__.__name__} @ "
                           f"{update.message.chat.id if update.message and update.message.chat else 'idk'}`:\n"
                           f"`{str(error)}`")
    if not update.message or not update.message.chat:
        return
    try:
        await update.message.reply("Error occurred. My owner has been notified.")
    except TelegramAPIError:
        pass
    if update.message.chat.id in GAMES:
        GAMES[update.message.chat.id].state = GameState.KILLGAME
        await asyncio.sleep(2)
        try:
            del GAMES[update.message.chat.id]
            await update.message.reply("Game ended forcibly.")
        except (KeyError, TelegramAPIError):
            pass


def main() -> None:
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()

# TODO: achv
