import random
from datetime import datetime
from string import ascii_lowercase

from aiogram import types

from .banned_letters import BannedLettersGame
from .chosen_first_letter import ChosenFirstLetterGame
from .classic import ClassicGame
from .elimination import EliminationGame
from .required_letter import RequiredLetterGame
from ...utils import check_word_existence, get_random_word


class MixedEliminationGame(EliminationGame):
    # Implementing this game mode was a misteak
    # self.current_word does not store the chosen first letter
    # but the whole word during ChosenFirstLetterGame here
    # for easier transition of game modes

    name = "mixed elimination game"
    command = "startmelim"
    game_modes = [
        ClassicGame,
        ChosenFirstLetterGame,
        BannedLettersGame,
        RequiredLetterGame
    ]

    __slots__ = ("game_mode", "banned_letters", "required_letter")

    def __init__(self, group_id):
        super().__init__(group_id)
        self.game_mode = None
        self.banned_letters = []
        self.required_letter = None

    async def send_turn_message(self) -> None:
        text = f"Turn: {self.players_in_game[0].mention}"
        if self.turns_until_elimination > 1:
            text += f" (Next: {self.players_in_game[1].name})"
        text += "\n"

        if self.game_mode is ChosenFirstLetterGame:
            starting_letter = self.current_word[0]
        else:
            starting_letter = self.current_word[-1]
        text += f"Your word must start with <i>{starting_letter.upper()}</i>"

        if self.game_mode is BannedLettersGame:
            text += f" and <b>exclude</b> <i>{', '.join(c.upper() for c in self.banned_letters)}</i>"
        elif self.game_mode is RequiredLetterGame:
            text += f" and <b>include</b> <i>{self.required_letter.upper()}</i>"
        text += ".\n"

        text += f"You have <b>{self.time_limit}s</b> to answer.\n\n"
        text += "Leaderboard:\n" + self.get_leaderboard(show_player=self.players_in_game[0])
        await self.send_message(text, parse_mode=types.ParseMode.HTML)

        # Reset per-turn attributes
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def additional_answer_checkers(self, word: str, message: types.Message) -> bool:
        if self.game_mode is BannedLettersGame:
            return await BannedLettersGame.additional_answer_checkers(self, word, message)
        elif self.game_mode is RequiredLetterGame:
            return await RequiredLetterGame.additional_answer_checkers(self, word, message)
        return True

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()

        # Starting letter
        if self.game_mode is ChosenFirstLetterGame:
            if not word.startswith(self.current_word[0]):
                await message.reply(
                    f"_{word.capitalize()}_ does not start with _{self.current_word[0].upper()}_.",
                    allow_sending_without_reply=True
                )
                return
        elif not word.startswith(self.current_word[-1]):
            await message.reply(
                f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.",
                allow_sending_without_reply=True
            )
            return

        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.", allow_sending_without_reply=True)
            return
        if not check_word_existence(word):
            await message.reply(
                f"_{word.capitalize()}_ is not in my list of words.",
                allow_sending_without_reply=True
            )
            return
        if not await self.additional_answer_checkers(word, message):
            return

        self.post_turn_processing(word)
        await self.send_post_turn_message(word)

    def post_turn_processing(self, word: str) -> None:
        super().post_turn_processing(word)
        if self.game_mode is RequiredLetterGame:
            RequiredLetterGame.change_required_letter(self)

    async def running_initialization(self) -> None:
        self.start_time = datetime.now().replace(microsecond=0)
        self.turns_until_elimination = len(self.players_in_game)
        self.game_mode = random.choice(self.game_modes)

        # First round is special since first word has to be set

        # Set starting word and mode-based attributes
        if self.game_mode is BannedLettersGame:
            BannedLettersGame.set_banned_letters(self)
            self.current_word = get_random_word(banned_letters=self.banned_letters)
        elif self.game_mode is ChosenFirstLetterGame:
            # Ensure uniform probability of each letter as the starting letter
            self.current_word = get_random_word(prefix=random.choice(ascii_lowercase))
        else:
            self.current_word = get_random_word()
        if self.game_mode is RequiredLetterGame:
            RequiredLetterGame.change_required_letter(self)
        self.used_words.add(self.current_word)

        await self.send_message(
            (
                f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
                "Turn order:\n"
                + "\n".join(p.mention for p in self.players_in_game)
            ),
            parse_mode=types.ParseMode.HTML
        )

        round_text = f"Round 1 is starting...\nMode: <b>{self.game_mode.name.capitalize()}</b>"
        if self.game_mode is ChosenFirstLetterGame:
            round_text += f"\nThe chosen first letter is <i>{self.current_word[0].upper()}</i>."
        elif self.game_mode is BannedLettersGame:
            round_text += f"\nBanned letters: <i>{', '.join(c.upper() for c in self.banned_letters)}</i>"
        round_text += "\n\nLeaderboard:\n" + self.get_leaderboard()
        await self.send_message(round_text, parse_mode=types.ParseMode.HTML)

    def set_game_mode(self) -> None:
        # Random game mode without having the same mode twice in a row
        modes = self.game_modes[:]
        if self.game_mode:
            modes.remove(self.game_mode)
        self.game_mode = random.choice(modes)

        # Set mode-based attributes
        if self.game_mode is BannedLettersGame:
            BannedLettersGame.set_banned_letters(self)
        elif self.game_mode is RequiredLetterGame:
            RequiredLetterGame.change_required_letter(self)

    async def handle_round_start(self) -> None:
        self.turns_until_elimination = len(self.players_in_game)
        self.set_game_mode()

        round_text = f"Round {self.round} is starting...\nMode: <b>{self.game_mode.name.capitalize()}</b>"
        if self.game_mode is ChosenFirstLetterGame:
            # The last letter of the current word becomes the chosen first letter
            self.current_word = self.current_word[-1]
            round_text += f"\nThe chosen first letter is <i>{self.current_word.upper()}</i>."
        elif self.game_mode is BannedLettersGame:
            round_text += f"\nBanned letters: <i>{', '.join(c.upper() for c in self.banned_letters)}</i>"
        round_text += "\n\nLeaderboard:\n" + self.get_leaderboard()
        await self.send_message(round_text, parse_mode=types.ParseMode.HTML)
