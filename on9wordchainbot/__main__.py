import asyncio
import random
import time
from decimal import getcontext, ROUND_HALF_UP

from aiogram import executor

from on9wordchainbot import loop, dp, session, pool

random.seed(time.time())
getcontext().rounding = ROUND_HALF_UP


async def on_shutdown(_) -> None:
    await asyncio.gather(session.close(), pool.close())


def main() -> None:
    executor.start_polling(dp, loop=loop, on_shutdown=on_shutdown, skip_updates=True)


if __name__ == "__main__":
    main()
