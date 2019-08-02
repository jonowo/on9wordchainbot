import asyncio
from string import ascii_lowercase

import asyncpg
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import BoundFilter

loop = asyncio.get_event_loop()
with open("token.txt") as f:
    TOKEN = f.readline().strip()
bot = Bot(TOKEN, loop, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot)
BOT_ID = int(TOKEN.partition(":")[0])
with open("on9bot_token.txt") as f:
    ON9BOT_TOKEN = f.readline().strip()
on9bot = Bot(ON9BOT_TOKEN, parse_mode=types.ParseMode.MARKDOWN)
ON9BOT_ID = int(ON9BOT_TOKEN.partition(":")[0])
OWNER_ID = 463998526
ADMIN_GROUP_ID = -1001141544515
OFFICIAL_GROUP_ID = -1001333598796
GAMES = {}
with open("dburi.txt") as f:
    DB_URI = f.readline().strip()
pool = None

print("Fetching list of words...")
WORDS_LI = {i: [] for i in ascii_lowercase}
w = requests.get("https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt").text.splitlines()
for i in w:
    WORDS_LI[i[0]].append(i)
WORDS = {i: set(WORDS_LI[i]) for i in ascii_lowercase}
del w


async def f():
    print("Connecting to database...")
    global pool
    pool = await asyncpg.create_pool(DB_URI)


loop.run_until_complete(f())


class GameState:
    JOINING = 0
    RUNNING = 1
    KILLGAME = -1


class GameSettings:
    INITIAL_JOINING_PHASE_SECONDS = 60
    SPECIAL_GAME_INITIAL_JOINING_PHASE_SECONDS = 90
    MAX_JOINING_PHASE_SECONDS = 180
    NORMAL_GAME_MIN_PLAYERS = 2
    SPECIAL_GAME_MIN_PLAYERS = 5
    MAX_PLAYERS = 50
    SPECIAL_GAME_MAX_PLAYERS = 30
    INCREASED_MAX_PLAYERS = 300
    MIN_TURN_SECONDS = 20
    FIXED_TURN_SECONDS = 30
    MAX_TURN_SECONDS = 40
    TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE = 5
    MIN_WORD_LENGTH_LIMIT = 3
    MAX_WORD_LENGTH_LIMIT = 10
    WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE = 1
    TURNS_BETWEEN_LIMITS_CHANGE = 5


class GroupFilter(BoundFilter):
    key = "is_group"

    def __init__(self, is_group: bool) -> None:
        self.is_group = is_group

    async def check(self, message: types.Message) -> bool:
        return message.chat.id < 0 if self.is_group else message.chat.id > 0


class OwnerFilter(BoundFilter):
    key = "is_owner"

    def __init__(self, is_owner: bool) -> None:
        self.is_owner = is_owner

    async def check(self, message: types.Message) -> bool:
        return message.from_user.id == OWNER_ID


class AdminFilter(BoundFilter):
    key = "is_admin"

    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin

    async def check(self, message: types.Message) -> bool:
        return (message.from_user.id == OWNER_ID
                or (await bot.get_chat_member(message.chat.id, message.from_user.id)).is_chat_admin())


dp.filters_factory.bind(GroupFilter)
dp.filters_factory.bind(OwnerFilter)
dp.filters_factory.bind(AdminFilter)
