import asyncio
import logging

from dawg import CompletionDAWG

from on9wordchainbot.constants import WORDLIST_SOURCE
from on9wordchainbot.resources import get_pool, get_session

logger = logging.getLogger(__name__)


class Words:
    # Directed acyclic word graph (DAWG)
    dawg: CompletionDAWG
    count: int

    @staticmethod
    async def update() -> None:
        # Words retrieved from online repo and database table with additional approved words
        logger.info("Retrieving words")

        async def get_words_from_source() -> list[str]:
            session = get_session()
            async with session.get(WORDLIST_SOURCE) as resp:
                text = await resp.text()
                return text.splitlines()

        async def get_words_from_db() -> list[str]:
            pool = get_pool()
            async with pool.acquire() as conn:
                res = await conn.fetch("SELECT word from wordlist WHERE accepted;")
                return [row[0] for row in res]

        source_task = asyncio.create_task(get_words_from_source())
        db_task = asyncio.create_task(get_words_from_db())
        wordlist = await source_task + await db_task

        logger.info("Processing words")

        wordlist = [w.lower() for w in wordlist if w.isalpha()]
        Words.dawg = CompletionDAWG(wordlist)
        Words.count = len(Words.dawg.keys())

        logger.info("DAWG updated")
