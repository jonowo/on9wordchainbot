from aiogram import types, html

from on9wordchainbot.resources import on9bot
from on9wordchainbot.constants import STAR
from on9wordchainbot.utils import has_star


class Player:
    __slots__ = (
        "_username", "_name", "user_id", "is_vp", "word_count", "letter_count", "longest_word", "score"
    )

    def __init__(self, user: types.User) -> None:
        self._username = user.username
        self._name = user.full_name
        self.user_id = user.id

        self.is_vp = user.id == on9bot.id
        self.word_count = 0
        self.letter_count = 0
        self.longest_word = ""

        # For elimination games only
        # Though generally score = letter count,
        # there is turn score increment ceiling for more balanced gameplay
        self.score = 0

    @property
    def name(self) -> str:
        if self._username:
            return f"<a href='https://t.me/{self._username}'>{html.quote(self._name)}</a>"
        else:
            return f"<b>{html.quote(self._name)}</b>"

    @property
    def mention(self) -> str:
        return f"<a href='tg://user?id={self.user_id}'>{html.quote(self._name)}</a>"

    @classmethod
    async def create(cls, user: types.User) -> "Player":
        player = Player(user)
        if await has_star(user.id):  # Donation reward
            player._name += " " + STAR
        return player

    @classmethod
    async def vp(cls) -> "Player":
        on9bot_user = await on9bot.me()
        vp = Player(on9bot_user)
        vp._name += " " + STAR
        return vp
