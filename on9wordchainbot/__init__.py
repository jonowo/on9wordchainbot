import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict

import aiohttp
import asyncpg
from aiogram import Bot, types, Dispatcher

from .constants import DB_URI, TOKEN, ON9BOT_TOKEN
from .filters import filters
from .words import Words

if TYPE_CHECKING:
    from .models import ClassicGame

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import uvloop
except ImportError:
    logger.info(r"uvloop unavailable ¯\_(ツ)_/¯")
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

loop = asyncio.get_event_loop()
bot = Bot(TOKEN, loop, parse_mode=types.ParseMode.MARKDOWN)
on9bot = Bot(ON9BOT_TOKEN, loop)
dp = Dispatcher(bot, loop)
session = aiohttp.ClientSession(loop=loop)
pool: asyncpg.pool.Pool


class GlobalState:
    build_time = datetime.now().replace(microsecond=0)
    maint_mode = False
    games: Dict[int, "ClassicGame"] = {}  # Group id mapped to game instance


async def init() -> None:
    global pool
    logger.info("Connecting to database")
    pool = await asyncpg.create_pool(DB_URI, loop=loop)
    await Words.update()


loop.run_until_complete(init())

for f in filters:  # Need to bind filters before adding handlers
    dp.filters_factory.bind(f)

from .handlers import *
