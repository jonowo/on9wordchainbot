import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import aiohttp
import asyncpg
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from on9wordchainbot.constants import TOKEN, ON9BOT_TOKEN, DB_URI

if TYPE_CHECKING:
    from on9wordchainbot.models import ClassicGame


logger = logging.getLogger(__name__)


class GlobalState:
    build_time = datetime.now().replace(microsecond=0)
    maint_mode = False

    games: dict[int, "ClassicGame"] = {}  # group id -> game instance
    games_lock: asyncio.Lock = asyncio.Lock()


bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN,
        allow_sending_without_reply=True,
        link_preview_is_disabled=True,
    )
)
on9bot = Bot(ON9BOT_TOKEN)


# Initialized on startup
session: Optional[aiohttp.ClientSession] = None
pool: Optional[asyncpg.pool.Pool] = None


def get_session() -> aiohttp.ClientSession:
    if session is None:
        raise RuntimeError("session is not initialized!")
    return session


def get_pool() -> asyncpg.pool.Pool:
    if pool is None:
        raise RuntimeError("pool is not initialized!")
    return pool


async def init_resources() -> None:
    global session, pool

    session = aiohttp.ClientSession()

    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(DB_URI)


async def close_resources() -> None:
    global session, pool
    await asyncio.gather(session.close(), pool.close())
