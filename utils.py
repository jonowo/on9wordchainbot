import random
from typing import List, Set, Any, Optional

from aiogram import types

from constants import bot, on9bot, pool, ADMIN_GROUP_ID, VIP, get_words_all, get_words_set, get_words_li


def check_word_existence(word: str) -> bool:
    return word in get_words_set()[word[0]]


def filter_words(
    min_len: int = 1,
    starting_letter: Optional[str] = None,
    banned_letters: Optional[List[int]] = None,
    required_letter: Optional[str] = None,
    exclude_words: Optional[Set[str]] = None,
) -> List[str]:
    if starting_letter:
        words = get_words_li()[starting_letter]
    else:
        words = get_words_all()

    def f(word):  # Filter
        if len(word) < min_len:
            return False
        if banned_letters and any(i in word for i in banned_letters):
            return False
        if required_letter and required_letter not in word:
            return False
        if exclude_words and word in exclude_words:
            return False
        return True

    return [w for w in words if f(w)]


def get_random_word(
    min_len: int = 1,
    starting_letter: Optional[str] = None,
    banned_letters: Optional[List[int]] = None,
    required_letter: Optional[str] = None,
    exclude_words: Optional[Set[str]] = None,
) -> Optional[str]:
    words = filter_words(min_len, starting_letter, banned_letters, required_letter, exclude_words)
    if words:
        return random.choice(words)
    else:
        return None


async def send_admin_group(*args: Any, **kwargs: Any) -> types.Message:
    return await bot.send_message(ADMIN_GROUP_ID, *args, disable_web_page_preview=True, **kwargs)


async def amt_donated(user_id: int) -> int:
    async with pool.acquire() as conn:
        amt = await conn.fetchval("SELECT SUM(amount) FROM donation WHERE user_id = $1;", user_id)
        return amt or 0


async def has_star(user_id: int) -> bool:
    return user_id in VIP or user_id == on9bot.id or await amt_donated(user_id)

# TODO: Make decorator for group-only / running-game-only command (with message saying group only)
