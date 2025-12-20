import asyncio
import random
import time
from decimal import ROUND_HALF_UP, getcontext

from on9wordchainbot import dp
from on9wordchainbot.resources import bot

random.seed(time.time())
getcontext().rounding = ROUND_HALF_UP


async def main() -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
