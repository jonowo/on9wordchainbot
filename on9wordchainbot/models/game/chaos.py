import random
from datetime import datetime

from aiogram import types

from .classic import ClassicGame
from ...utils import get_random_word


class ChaosGame(ClassicGame):
    name = "chaos game"
    command = "startchaos"

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention}\n"
                f"Your word must start with <i>{self.current_word[-1].upper()}</i> and "
                f"contain <b>at least {self.min_letters_limit} letters</b>.\n"
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

    async def running_initialization(self) -> None:
        # Random starting word
        self.current_word = get_random_word(min_len=self.min_letters_limit)
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)

        # No turn order
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.")

    async def running_phase_tick(self) -> bool:
        if self.answered:
            # Move player who just answered to the end of queue
            self.players_in_game.append(self.players_in_game.pop(0))

            # Choose random player excluding the one who just answered
            player = self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 2))
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return False

            # Timer ran out
            self.accepting_answers = False
            await self.send_message(
                f"{self.players_in_game[0].mention} ran out of time! They have been eliminated.",
                parse_mode=types.ParseMode.HTML
            )
            del self.players_in_game[0]

            if len(self.players_in_game) == 1:
                await self.handle_game_end()
                return True

            # Choose random player
            player = self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 1))

        # Move player to start of queue
        self.players_in_game.insert(0, player)
        await self.send_turn_message()
        return False
