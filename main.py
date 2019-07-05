import logging
from random import seed
from string import ascii_lowercase
from time import time

from aiogram import executor, types
from aiogram.utils.exceptions import TelegramAPIError

from constants import bot, dp, BOT_ID, ADMIN_GROUP_ID, GAMES, WORDS, GameState
from game import ClassicGame, ChaosGame, ChosenFirstLetterGame, BannedLettersGame

seed(time())
logging.basicConfig(level=logging.INFO)
MAINT_MODE = False


async def games_group_only(message: types.Message) -> None:
    await message.reply(
        "Games are only available in groups.", reply_markup=types.InlineKeyboardMarkup([[
            types.InlineKeyboardButton("Add me to a group!", url="https://t.me/on9wordchainbot?startgroup=_")
        ]])
    )


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message) -> None:
    if message.chat.id > 0:
        await message.reply("Bruh")


@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message) -> None:
    await message.reply(
        "I provide a variation of the game _Word Chain_ in which players come up with words that begin with the last "
        "letter of the previous word. Players unable to come up with a word in time are eliminated from the game. The "
        "first word is randomly chosen. The time limit decreases from 40 to 20 seconds and the minimum word length"
        "limit increases from 3 to 10 letters throughout the game to level up the difficulty.\n\n"
        "/startgame - Classic game\n"
        "Classic gameplay.\n\n"
        "/startchaos - Chaos game\n"
        "No turn order, players are selected to answer randomly.\n\n"
        "/startcfl - Chosen first letter game\n"
        "Players come up with words starting with a specific letter randomly chosen at the beginning of the game.\n\n"
        "/startbl - Banned letters game\n"
        "2-4 letters (incl. max one vowel) are randomly chosen to be banned and cannot be present in words.\n\n"
        "Please contact [Trainer Jono](https://t.me/Trainer_Jono) for enquiries, feedback and suggestions.\n"
        "GitHub repo: [Tr-Jono/on9wordchainbot](https://github.com/Tr-Jono/on9wordchainbot)",
        disable_web_page_preview=True
    )


@dp.message_handler(commands=["ping"])
async def cmd_ping(message: types.Message) -> None:
    t = time()
    msg = await message.reply("Pong!")
    await msg.edit_text(f"Pong!\nSeconds used: `{time() - t:.3f}`")


@dp.message_handler(commands=["runinfo"])
async def cmd_runinfo(message: types.Message) -> None:
    await message.reply(
        f"Total games: {len(GAMES)}\n"
        f"Running games: {len([g for g in GAMES.values() if g.state == GameState.RUNNING])}\n"
        f"Players: {sum([len(g.players) for g in GAMES.values()])}"
    )


@dp.message_handler(commands=["exist", "exists"])
async def cmd_exists(message: types.Message) -> None:
    word = message.text.partition(" ")[2].lower()
    if not word or not all([c in ascii_lowercase for c in word]):
        rmsg = message.reply_to_message
        if rmsg and rmsg.text and all([c in ascii_lowercase for c in rmsg.text.lower()]):
            word = message.reply_to_message.text.lower()
        else:
            await message.reply("Usage example: `/exists astrophotographer`")
            return
    if word in WORDS[word[0]]:
        await message.reply(f"*{word.capitalize()}* EXISTS in my list of words.")
        return
    await message.reply(f"*{word.capitalize()}* DOES NOT EXIST in my list of words.")


@dp.message_handler(commands=["startclassic"])
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


@dp.message_handler(commands=["startchaos"])
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


@dp.message_handler(commands=["startcfl"])
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


@dp.message_handler(commands=["startbl"])
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


@dp.message_handler(commands=["join", "john", "disaster"])
async def cmd_join(message: types.Message) -> None:
    if message.chat.id > 0:
        await games_group_only(message)
        return
    rmsg = message.reply_to_message
    if not message.get_command().partition("@")[2] and (not rmsg or rmsg.from_user.id != BOT_ID):
        return
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].join(message)


@dp.message_handler(is_group=True, is_owner_or_admin=True, commands=["forcejoin", "forcejohn", "forcedisaster"])
async def cmd_forcejoin(message: types.Message) -> None:
    group_id = message.chat.id
    rmsg = message.reply_to_message
    if group_id in GAMES and rmsg and not rmsg.from_user.is_bot:
        await GAMES[message.chat.id].forcejoin(message)


@dp.message_handler(is_group=True, commands=["extend"])
async def cmd_extend(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].extend(message)


@dp.message_handler(is_group=True, is_owner_or_admin=True, commands=["forcestart"])
async def cmd_forcestart(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES and GAMES[group_id].state == GameState.JOINING:
        GAMES[group_id].time_left = -99999


@dp.message_handler(is_group=True, commands=["flee"])
async def cmd_flee(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].flee(message)


@dp.message_handler(is_group=True, is_owner=True, commands=["forceflee"])
async def cmd_forceflee(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        await GAMES[group_id].forceflee(message)


@dp.message_handler(is_group=True, is_owner=True, commands=["killgame", "killgaym"])
async def cmd_killgame(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES:
        GAMES[group_id].state = GameState.KILLGAME


@dp.message_handler(is_group=True, is_owner=True, commands=["forceskip"])
async def cmd_forceskip(message: types.Message) -> None:
    group_id = message.chat.id
    if group_id in GAMES and GAMES[group_id].state == GameState.RUNNING and not GAMES[group_id].answered:
        GAMES[group_id].time_left = -99999


@dp.message_handler(is_owner=True, commands=["maintmode"])
async def cmd_maintmode(message: types.Message) -> None:
    global MAINT_MODE
    MAINT_MODE = not MAINT_MODE
    await message.reply(f"Maintenance mode has been switched {'on' if MAINT_MODE else 'off'}.")


@dp.message_handler(is_group=True, regexp="^\w+$")
async def message_handler(message: types.Message) -> None:
    group_id = message.chat.id
    if (group_id in GAMES and GAMES[group_id].players_in_game
            and message.from_user.id == GAMES[group_id].players_in_game[0].user_id and not GAMES[group_id].answered):
        await GAMES[group_id].handle_answer(message)


@dp.errors_handler(exception=TelegramAPIError)
async def error_handler(update: types.Update, error: TelegramAPIError) -> None:
    await bot.send_message(ADMIN_GROUP_ID, f"`{error.__class__.__name__} @ {update.message.chat.id}`:\n`{str(error)}`")
    await bot.send_message(update.message.chat.id, "Error occurred. My owner has been notified.")


def main() -> None:
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()

# TODO: VP?
