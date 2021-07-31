import random
from datetime import datetime

from aiogram import types

from .classic import ClassicGame
from ...utils import get_random_word


class RandomFirstLetterGame(ClassicGame):
    name = "random first letter game"
    command = "startrfl"

    def change_first_letter(self) -> None:
        self.current_word = random.choice(self.current_word)

    def post_turn_processing(self, word: str) -> None:
        super().post_turn_processing(word)
        self.change_first_letter()

    async def running_initialization(self) -> None:
        self.current_word = get_random_word(min_len=self.min_letters_limit)
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
            "Turn order:\n"
            + "\n".join(p.mention for p in self.players_in_game),
            parse_mode=types.ParseMode.HTML
        )

        self.change_first_letter()
