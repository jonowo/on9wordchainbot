import asyncio
import random
import time
from decimal import ROUND_HALF_UP, getcontext

from aiogram import executor
from periodic import Periodic

from on9wordchainbot import dp, loop, pool, session
from on9wordchainbot.words import Words

random.seed(time.time())
getcontext().rounding = ROUND_HALF_UP


async def on_startup(_) -> None:
    await Words.update()

    # Update word list every 3 hours
    task = Periodic(3 * 60 * 60, Words.update)
    await task.start()


async def on_shutdown(_) -> None:
    await asyncio.gather(session.close(), pool.close())


def main() -> None:
    executor.start_polling(
        dp, loop=loop, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True
    )


if __name__ == "__main__":
    main()
