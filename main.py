import asyncio
import logging
from datetime import datetime
from random import seed
from string import ascii_lowercase
from time import time
from uuid import uuid4

from aiogram import executor, types
from aiogram.utils.exceptions import TelegramAPIError, BadRequest

from constants import (bot, dp, BOT_ID, ON9BOT_ID, OWNER_ID, ADMIN_GROUP_ID, OFFICIAL_GROUP_ID, GAMES, pool, WORDS,
                       WORDS_LI, GameState, GameSettings)
from game import ClassicGame, HardModeGame, ChaosGame, ChosenFirstLetterGame, BannedLettersGame, EliminationGame

seed(time())
logging.basicConfig(level=logging.INFO)
build_time = datetime.now().replace(microsecond=0)
MAINT_MODE = False


async def games_group_only(message: types.Message) -> None:
    await message.reply(
        "You must run this command in a group.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton("Add me to a group!", url="https://t.me/on9wordchainbot?startgroup=_")
        ]])
    )


@dp.message_handler(is_group=False, commands="start")
async def cmd_start(message: types.Message) -> None:
    await message.reply(
        "Terms of Service\n\n"
        "0. You must not abuse this bot.\n\n"
        "1. You must report any bugs you encounter to this bot's owner - [Trainer Jono](https://t.me/Trainer_Jono).\n\n"
        "2. You understand that complains about words being missing from this bot's word list are usually ignored "
        "since this bot's owner is not responsible for such issues.\n\n"
        "3. You will forgive this bot's owner in case a game suddenly ends without any notification, usually due to "
        "him forgetting to check if there were running games before manually terminating this bot's program.\n\n"
        "By starting this bot, you have agreed to the above terms of service.\n"
        "Add me to a group to start playing games!",
        disable_web_page_preview=True,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton("Add me to a group!", url="https://t.me/on9wordchainbot?startgroup=_")
        ]])
    )


@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def added_into_group(message: types.Message) -> None:
    if any(user.id == BOT_ID for user in message.new_chat_members):
        await message.reply("Thanks for adding me. Click /startclassic to start a classic game!", reply=False)
    elif message.chat.id == OFFICIAL_GROUP_ID:
        await message.reply("Welcome to the official On9 Word Chain group!\n"
                            "Click /startclassic to start a classic game!")


@dp.message_handler(commands="help")
async def cmd_help(message: types.Message) -> None:
    if message.chat.id < 0:
        await message.reply("Please use this command in private.")
        return
    await message.reply(
        "I provide several variations of the English game _Word Chain_.\n\n"
        "/startclassic - Classic game\n"
        "Players come up with words that begin with the last letter of the previous word. Players unable to come up "
        "with a word in time are eliminated from the game. The time limit decreases and the minimum word length limit "
        "increases throughout the game to level up the difficulty.\n\n"
        "/starthard - Hard mode game\n"
        "Classic gameplay but with the most difficult configurations set initially.\n\n"
        "/startchaos - Chaos game\n"
        "Classic gameplay but without turn order, players are selected to answer by random.\n\n"
        "/startcfl - Chosen first letter game\n"
        "Players come up with words starting with the chosen letter.\n\n"
        "/startbl - Banned letters game\n"
        "Classic gameplay but 2-4 letters (incl. max one vowel) are banned and cannot be present in words.\n\n"
        "/startelim - Elimination game\n"
        "Each player has a score, i.e. their cumulative word length. After each player has played a round, the "
        "player(s) with the lowest score get eliminated from the game. Last standing player wins.",
        disable_web_page_preview=True
    )


@dp.message_handler(commands="info")
async def cmd_info(message: types.Message) -> None:
    await message.reply(
        "Join the [official channel](https://t.me/On9Updates) and the [official group](https://t.me/on9wordchain)!\n"
        "GitHub repo: [Tr-Jono/on9wordchainbot](https://github.com/Tr-Jono/on9wordchainbot)\n"
        "Feel free to PM my owner [Trainer Jono](https://t.me/Trainer_Jono) in English or Cantonese.\n",
        disable_web_page_preview=True
    )


@dp.message_handler(commands="ping")
async def cmd_ping(message: types.Message) -> None:
    t = time()
    msg = await message.reply("Pong!")
    await msg.edit_text(f"Pong!\nSeconds used: `{time() - t:.3f}`")


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
        await games_group_only(message)
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
        await games_group_only(message)
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
        await games_group_only(message)
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
        await games_group_only(message)
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
        await games_group_only(message)
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


@dp.message_handler(commands=["startelim", "startelimination"])
async def cmd_startelim(message: types.Message) -> None:
    if message.chat.id > 0:
        await games_group_only(message)
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


@dp.message_handler(commands="join")
async def cmd_join(message: types.Message) -> None:
    if message.chat.id > 0:
        await games_group_only(message)
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)
    # Due to privacy settings, no reply is given when there is no running game


@dp.message_handler(is_group=True, is_owner=True, commands="forcejoin")
async def cmd_forcejoin(message: types.Message) -> None:
    group_id = message.chat.id
    rmsg = message.reply_to_message
    if group_id in GAMES and rmsg and (not rmsg.from_user.is_bot or rmsg.from_user.id == ON9BOT_ID):
        if rmsg.from_user.id == ON9BOT_ID and isinstance(GAMES[group_id], EliminationGame):
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
    if group_id in GAMES:
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


@dp.message_handler(is_group=True, commands="stats")
async def cmd_stats(message: types.Message) -> None:
    rmsg = message.reply_to_message
    if (message.chat.id < 0 and not message.get_command().partition("@")[2]
            or rmsg and rmsg.from_user.is_bot and rmsg.from_user.id != ON9BOT_ID):
        return
    user = rmsg.forward_from or rmsg.from_user if rmsg else message.from_user
    async with pool.acquire() as conn:
        res = await conn.fetchrow("SELECT * FROM player WHERE user_id = $1;", user.id)
    if not res:
        await message.reply(f"No statistics for [{user.full_name}](tg://user?id={user.id})!")
        return
    await message.reply(
        f"Statistics for [{user.full_name}](tg://user?id={user.id}):\n"
        f"*{res['game_count']}* games played\n"
        f"*{res['win_count']} ("
        f"{'0%' if res['game_count'] == res['win_count'] == 0 else format(res['win_count'] / res['game_count'], '.0%')}"
        ")* games won\n"
        f"*{res['word_count']}* total words played\n"
        f"*{res['letter_count']}* total letters played"
        + (f"\nLongest word used: *{res['longest_word'].capitalize()}*" if res["longest_word"] else "")
    )


@dp.message_handler(is_group=True, commands="groupstats")
async def cmd_groupstats(message: types.Message) -> None:
    async with pool.acquire() as conn:
        player_count, game_count, word_count, letter_count = await conn.fetchrow("""\
SELECT COUNT(DISTINCT user_id), COUNT(DISTINCT game_id), SUM(word_count), SUM(letter_count)
FROM gameplayer
WHERE group_id = $1;""", message.chat.id)
    await message.reply(
        "Group statistics\n"
        f"*{player_count}* total players\n"
        f"*{game_count}* games played\n"
        f"*{word_count}* total words played\n"
        f"*{letter_count}* total letters played"
    )


@dp.message_handler(commands="globalstats")
async def cmd_globalstats(message: types.Message) -> None:
    async with pool.acquire() as conn:
        group_count, game_count = await conn.fetchrow("SELECT COUNT(DISTINCT group_id), COUNT(*) FROM game;")
        player_count, word_count, letter_count = await conn.fetchrow(
            "SELECT COUNT(player.*), SUM(player.word_count), SUM(player.letter_count) FROM player;"
        )
    await message.reply(
        "Global statistics\n"
        f"*{group_count}* total groups\n"
        f"*{player_count}* total players\n"
        f"*{game_count}* games played\n"
        f"*{word_count}* total words played\n"
        f"*{letter_count}* total letters played"
    )


@dp.message_handler(is_owner=True, commands="sql")
async def cmd_sql(message: types.Message) -> None:
    async with pool.acquire() as conn:
        res = await conn.fetch(message.get_full_command()[1])
    if not res:
        await message.reply("No results returned.")
        return
    text = ["*" + " - ".join(res[0].keys()) + "*"]
    for r in res:
        text.append("`" + " - ".join([str(i) for i in r.values()]) + "`")
    await message.reply("\n".join(text))


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
    if inline_query.from_user.id != OWNER_ID or not text:
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


@dp.errors_handler(exception=TelegramAPIError)
async def error_handler(update: types.Update, error: TelegramAPIError) -> None:
    if error.__class__ == BadRequest and str(error) == "Reply message not found":
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
# TODO: Modes: race game and mixed elimination game based on word length
