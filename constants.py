import asyncio
import json
import logging
from string import ascii_lowercase

import aiohttp
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import BoundFilter

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

with open("config.json") as f:
    config = json.load(f)
    TOKEN = config["TOKEN"]
    ON9BOT_TOKEN = config["ON9BOT_TOKEN"]
    DB_URI = config["DB_URI"]
    PROVIDER_TOKEN = config["PROVIDER_TOKEN"]
    OWNER_ID = config["OWNER_ID"]
    ADMIN_GROUP_ID = config["ADMIN_GROUP_ID"]
    OFFICIAL_GROUP_ID = config["OFFICIAL_GROUP_ID"]
    VIP = config["VIP"]
    VIP_GROUP = config["VIP_GROUP"]
loop = asyncio.get_event_loop()
BOT_ID = int(TOKEN.partition(":")[0])
ON9BOT_ID = int(ON9BOT_TOKEN.partition(":")[0])
bot = Bot(TOKEN, loop, parse_mode=types.ParseMode.MARKDOWN)
on9bot = Bot(ON9BOT_TOKEN, loop)
dp = Dispatcher(bot)
GAMES = {}
WORDS_LI = WORDS = pool = session = None


def get_words():
    return WORDS


def get_words_li():
    return WORDS_LI


async def update_words():
    global WORDS_LI, WORDS
    async with session.get("https://raw.githubusercontent.com/dwyl/english-words/master/words.txt") as resp:
        w = (await resp.text()).splitlines()
    async with pool.acquire() as conn:
        w += [i[0] for i in await conn.fetch("SELECT word from wordlist WHERE accepted = true;")]
    w = set([i.lower() for i in w])
    WORDS_LI = {i: [] for i in ascii_lowercase}
    for i in w:
        if i.isalpha():
            WORDS_LI[i[0]].append(i)
    WORDS = {i: set(WORDS_LI[i]) for i in ascii_lowercase}


async def init():
    global pool, session
    session = aiohttp.ClientSession(loop=loop)
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(DB_URI)
    logger.info("Fetching word list...")
    await update_words()


loop.run_until_complete(init())


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
    MAX_TURN_SECONDS = 40
    FIXED_TURN_SECONDS = 30
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


class VIPFilter(BoundFilter):
    key = "is_vip"

    def __init__(self, is_vip: bool) -> None:
        self.is_vip = is_vip

    async def check(self, message: types.Message) -> bool:
        return message.from_user.id in VIP


class AdminFilter(BoundFilter):
    key = "is_admin"

    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin

    async def check(self, message: types.Message) -> bool:
        return (message.from_user.id == OWNER_ID
                or (await bot.get_chat_member(message.chat.id, message.from_user.id)).is_chat_admin())


for f in (GroupFilter, OwnerFilter, VIPFilter, AdminFilter):
    dp.filters_factory.bind(f)


async def amt_donated(user_id: int) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT SUM(amount) FROM donation WHERE user_id = $1", user_id) or 0
