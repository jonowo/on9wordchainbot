import random
from datetime import datetime
from string import ascii_lowercase

from aiogram import types

from .classic import ClassicGame


class ChosenFirstLetterGame(ClassicGame):
    name = "chosen first letter game"
    command = "startcfl"

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
                f"Your word must start with <i>{self.current_word.upper()}</i> and "
                f"contain <b>at least {self.min_letters_limit} letters</b>.\n"
                f"You have <b>{self.time_limit}s</b> to answer.\n"
                f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
                f"Total words: {self.turns}"
            ),
            parse_mode=types.ParseMode.HTML,
        )

        # Reset per-turn attributes
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

        if self.players_in_game[0].is_vp:
            await self.vp_answer()

    async def running_initialization(self) -> None:
        # Instead of storing the last used word like in other game modes,
        # self.current_word stores in the chosen first letter which is constant throughout the game
        self.current_word = random.choice(ascii_lowercase)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            (
                f"The chosen first letter is <i>{self.current_word.upper()}</i>.\n\n"
                "Turn order:\n"
                + "\n".join(p.mention for p in self.players_in_game)
            ),
            parse_mode=types.ParseMode.HTML
        )
