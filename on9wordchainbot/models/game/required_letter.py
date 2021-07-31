import random
from datetime import datetime
from string import ascii_lowercase
from typing import Optional

from aiogram import types

from .classic import ClassicGame
from ...utils import get_random_word


class RequiredLetterGame(ClassicGame):
    name = "required letter game"
    command = "startrl"

    __slots__ = ("required_letter",)

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        # Answer must contain required letter.
        # Required letter cannot be the ending letter of self.current_word so as to annoy the player.
        self.required_letter: Optional[str] = None  # Changes every turn

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
                f"Your word must start with <i>{self.current_word[-1].upper()}</i>, "
                f"<b>include</b> <i>{self.required_letter.upper()}</i> and "
                f"<b>at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}</b>.\n"
                f"You have <b>{self.time_limit}s</b> to answer.\n"
                f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
                f"Total words: {self.turns}"
            ),
            parse_mode=types.ParseMode.HTML
        )

        # Reset per-turn attributes
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

        if self.players_in_game[0].is_vp:
            await self.vp_answer()

    def get_random_valid_answer(self) -> Optional[str]:
        return get_random_word(
            min_len=self.min_letters_limit,
            prefix=self.current_word[-1],
            required_letter=self.required_letter,
            exclude_words=self.used_words
        )

    async def additional_answer_checkers(self, word: str, message: types.Message) -> bool:
        if self.required_letter not in word:
            await message.reply(
                f"_{word.capitalize()}_ does not include _{self.required_letter.upper()}_.",
                allow_sending_without_reply=True
            )
            return False
        return True

    def change_required_letter(self) -> None:
        letters = list(ascii_lowercase)
        letters.remove(self.current_word[-1])
        self.required_letter = random.choice(letters)

    def post_turn_processing(self, word: str) -> None:
        super().post_turn_processing(word)
        self.change_required_letter()

    async def running_initialization(self) -> None:
        # Random starting word
        self.current_word = get_random_word(min_len=self.min_letters_limit)
        self.used_words.add(self.current_word)
        self.change_required_letter()
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            (
                f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
                "Turn order:\n"
                + "\n".join(p.mention for p in self.players_in_game)
            ),
            parse_mode=types.ParseMode.HTML
        )
