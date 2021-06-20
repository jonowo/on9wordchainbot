import asyncio
import logging
from string import ascii_lowercase
from typing import List, Dict, Set

from .constants import WORDLIST_SOURCE

logger = logging.getLogger(__name__)


class Words:  # TODO: Switch to Trie
    list: List[str] = []  # List of all words
    map: Dict[str, List[str]] = {}  # Letter mapped to list of words starting with letter
    set: Dict[str, Set[str]] = {}  # Letter mapped to set of words starting with letter

    @staticmethod
    async def update() -> None:
        # Words retrieved from online repo and database table with additional approved words
        logger.info("Retrieving words")

        async def get_words_from_source() -> List[str]:
            from . import session

            async with session.get(WORDLIST_SOURCE) as resp:
                return (await resp.text()).splitlines()

        async def get_words_from_db() -> List[str]:
            from . import pool

            async with pool.acquire() as conn:
                res = await conn.fetch("SELECT word from wordlist WHERE accepted;")
                return [row[0] for row in res]

        source_task = asyncio.create_task(get_words_from_source())
        db_task = asyncio.create_task(get_words_from_db())
        wordlist = await source_task + await db_task

        logger.info("Processing words")

        # Sanitize words
        wordlist = [w.lower() for w in wordlist if w.isalpha()]
        wordlist = sorted(set(wordlist))

        Words.list = wordlist
        Words.map = {i: [] for i in ascii_lowercase}
        for w in wordlist:
            Words.map[w[0]].append(w)
        Words.set = {i: set(Words.map[i]) for i in ascii_lowercase}
