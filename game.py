import asyncio
from functools import lru_cache
from operator import attrgetter
from random import choice, sample, shuffle, randint
from string import ascii_lowercase
from typing import Optional, Any

from aiogram import types

from constants import bot, GAMES, WORDS, GameState, GameSettings


class Player:
    def __init__(self, user: types.User) -> None:
        self.user_id = user.id
        self.name = f"[{user.full_name}](https://t.me/{user.username})" if user.username else f"*{user.full_name}*"
        self.mention = user.get_mention()
        self.total_letters = 0  # For elimination game only


class ClassicGame:
    name = "classic game"

    def __init__(self, group_id: int) -> None:
        self.group_id = group_id
        self.players = []
        self.players_in_game = []
        self.state = GameState.JOINING
        self.min_players = GameSettings.NORMAL_GAME_MIN_PLAYERS
        self.max_players = GameSettings.MAX_PLAYERS
        self.time_left = GameSettings.INITIAL_JOINING_PHASE_SECONDS
        self.time_limit = GameSettings.MAX_TURN_SECONDS
        self.min_letters_limit = GameSettings.MIN_WORD_LENGTH_LIMIT
        self.current_word = None
        self.longest_word = ""
        self.longest_word_sender_id = None
        self.answered = False
        self.accepting_answers = False
        self.turns = 0
        self.used_words = set()

    async def send_message(self, *args: Any, **kwargs: Any) -> types.Message:
        return await bot.send_message(self.group_id, *args, disable_web_page_preview=True, **kwargs)

    @lru_cache(maxsize=5)
    async def is_admin(self, user_id: int) -> bool:
        return (await bot.get_chat_member(self.group_id, user_id)).is_chat_admin()

    async def join(self, message: types.Message) -> None:
        if self.state != GameState.JOINING or len(self.players) >= self.max_players:
            return
        user = message.from_user
        for p in self.players:
            if p.user_id == user.id:
                return
        player = Player(user)
        self.players.append(player)
        await message.reply(f"{player.name} joined. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def forcejoin(self, message: types.Message) -> None:
        if self.state == GameState.KILLGAME or len(self.players) >= self.max_players:
            return
        user = message.reply_to_message.from_user
        for p in self.players:
            if p.user_id == user.id:
                return
        player = Player(user)
        self.players.append(player)
        if self.state == GameState.RUNNING:
            self.players_in_game.append(player)
        await message.reply(f"{player.name} has been joined. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def flee(self, message: types.Message) -> None:
        user_id = message.from_user.id
        if self.state != GameState.JOINING or user_id not in [p.user_id for p in self.players]:
            return
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        await message.reply(f"{player.name} fled. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)

    async def forceflee(self, message: types.Message) -> None:
        if self.state != GameState.JOINING or not message.reply_to_message:
            return
        user_id = message.reply_to_message.from_user.id
        if user_id not in [p.user_id for p in self.players]:
            return
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        await message.reply(
            f"{player.name} has been fled. There {'is' if len(self.players) == 1 else 'are'} {len(self.players)} "
            f"player{'' if len(self.players) == 1 else 's'}.", disable_web_page_preview=True
        )

    async def extend(self, message: types.Message) -> None:
        if self.state != GameState.JOINING:
            return
        arg = message.text.partition(" ")[2]
        if arg and arg[0] == "-" and arg[1:] != "0" and arg[1:].isdecimal() and self.is_admin(message.from_user.id):
            n = int(arg[1:])
            if n >= self.time_left:
                self.time_left = -99999
            else:
                self.time_left = self.time_left - n
                await message.reply(f"The joining phase has been reduced by {n}s.\n"
                                    f"You have {self.time_left}s to /join.")
        else:
            n = int(arg) if arg.isdecimal() and int(arg) else 30
            self.time_left = min(self.time_left + n, GameSettings.MAX_JOINING_PHASE_SECONDS)
            await message.reply(f"The joining phase has been extended by {n}s.\nYou have {self.time_left}s to /join.")

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with *{self.current_word[-1].upper()}* "
            f"and include *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"*{word.capitalize()}* does not start with *{self.current_word[-1].upper()}*.")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"*{word.capitalize()}* has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"*{word.capitalize()}* has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"*{word.capitalize()}* is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.current_word = word
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        text = f"*{word.capitalize()}* is accepted.\n\n"
        if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
            if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                text += (f"Time limit decreased from "
                         f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                         f"*{self.time_limit}s*.\n")
            if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                text += (f"Minimum letters per word increased from "
                         f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                         f"to *{self.min_letters_limit}*.\n")
        self.answered = True
        self.accepting_answers = False
        await self.send_message(text.rstrip())

    async def running_initialization(self) -> None:
        self.current_word = sample(WORDS[choice(ascii_lowercase)], 1)[0]
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = sample(WORDS[choice(ascii_lowercase)], 1)[0]
        self.used_words.add(self.current_word)
        await self.send_message(f"The first word is *{self.current_word.capitalize()}*.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))

    async def running_phase(self) -> Optional[bool]:
        if self.answered:
            self.players_in_game.append(self.players_in_game.pop(0))
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return
            self.accepting_answers = False
            await self.send_message(f"{self.players_in_game[0].mention} ran out of time! Out!")
            del self.players_in_game[0]
            if len(self.players_in_game) == 1:
                await self.send_message(
                    f"{self.players_in_game[0].mention} won the game out of {len(self.players)} players!\n"
                    f"Total words: {self.turns}"
                    + (f"\nLongest word: *{self.longest_word.capitalize()}* from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                )
                del GAMES[self.group_id]
                return True
        await self.send_turn_message()

    async def main_loop(self, message: types.Message) -> None:
        await self.send_message(f"A{'n' if self.name[0] in 'aeiou' else ''} {self.name} is starting.\n"
                                f"{self.min_players}-{self.max_players} players are needed.\n"
                                f"You have {self.time_left}s to /join.")
        await self.join(message)
        while True:
            await asyncio.sleep(1)
            if self.state == GameState.JOINING:
                if self.time_left > 0:
                    self.time_left -= 1
                    if self.time_left in (15, 30, 60):
                        await self.send_message(f"{self.time_left}s left to /join.")
                else:
                    if len(self.players) < self.min_players:
                        await self.send_message("Not enough players. Game terminated.")
                        del GAMES[self.group_id]
                        return
                    else:
                        self.state = GameState.RUNNING
                        await self.send_message("Game is starting...")
                        shuffle(self.players)
                        self.players_in_game = self.players[:]
                        await self.running_initialization()
                        await self.send_turn_message()
            elif self.state == GameState.RUNNING:
                if await self.running_phase():
                    return
            elif self.state == GameState.KILLGAME:
                await self.send_message("Game ended forcibly.")
                del GAMES[self.group_id]
                return


class HardModeGame(ClassicGame):
    name = "hard mode game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.time_limit = GameSettings.MIN_TURN_SECONDS
        self.min_letters_limit = GameSettings.MAX_WORD_LENGTH_LIMIT


class ChaosGame(ClassicGame):
    name = "chaos game"

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention}\n"
            f"Your word must start with *{self.current_word[-1].upper()}* "
            f"and contain *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def running_initialization(self) -> None:
        self.current_word = sample(WORDS[choice(ascii_lowercase)], 1)[0]
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = sample(WORDS[choice(ascii_lowercase)], 1)[0]
        self.used_words.add(self.current_word)
        await self.send_message(f"The first word is *{self.current_word.capitalize()}*.")

    async def running_phase(self) -> Optional[bool]:
        if self.answered:
            self.players_in_game.append(self.players_in_game.pop(0))
            self.players_in_game.insert(0, self.players_in_game.pop(randint(0, len(self.players_in_game) - 2)))
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return
            self.accepting_answers = False
            await self.send_message(f"{self.players_in_game[0].mention} ran out of time! Out!")
            del self.players_in_game[0]
            if len(self.players_in_game) == 1:
                await self.send_message(
                    f"{self.players_in_game[0].mention} won the game out of {len(self.players)} players!\n"
                    f"Unique words: {self.turns}" +
                    (f"\nLongest word: *{self.longest_word.capitalize()}* from "
                     f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                     if self.longest_word else "")
                )
                del GAMES[self.group_id]
                return True
            self.players_in_game.insert(0, self.players_in_game.pop(randint(0, len(self.players_in_game) - 2)))
        await self.send_turn_message()


class ChosenFirstLetterGame(ClassicGame):
    name = "chosen first letter game"

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with *{self.current_word.upper()}* "
            f"and contain *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word):
            await message.reply(f"*{word.capitalize()}* does not start with *{self.current_word.upper()}*.")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"*{word.capitalize()}* has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"*{word.capitalize()}* has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"*{word.capitalize()}* is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        text = f"*{word.capitalize()}* is accepted.\n\n"
        if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
            if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                text += (f"Time limit decreased from "
                         f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                         f"*{self.time_limit}s*.\n")
            if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                text += (f"Minimum letters per word increased from "
                         f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                         f"to *{self.min_letters_limit}*.\n")
        self.answered = True
        self.accepting_answers = False
        await self.send_message(text.rstrip())

    async def running_initialization(self) -> None:
        self.current_word = choice(ascii_lowercase)
        await self.send_message(f"The chosen first letter is *{self.current_word.upper()}*.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))


class BannedLettersGame(ClassicGame):
    name = "banned letters game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.banned_letters = []

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with *{self.current_word[-1].upper()}*, "
            f"*exclude letters {', '.join(c.upper() for c in self.banned_letters)}* "
            f"and include *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"*{word.capitalize()}* does not start with *{self.current_word[-1].upper()}*.")
            return
        if any([c for c in self.banned_letters if c in word]):
            await message.reply(f"*{word.capitalize()}* include banned letters "
                                f"({', '.join(c.upper() for c in self.banned_letters if c in word)}).")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"*{word.capitalize()}* has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"*{word.capitalize()}* has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"*{word.capitalize()}* is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.current_word = word
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        text = f"*{word.capitalize()}* is accepted.\n\n"
        if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
            if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                text += (f"Time limit decreased from "
                         f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                         f"*{self.time_limit}s*.\n")
            if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                text += (f"Minimum letters per word increased from "
                         f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                         f"to *{self.min_letters_limit}*.\n")
        self.answered = True
        self.accepting_answers = False
        await self.send_message(text.rstrip())

    async def running_initialization(self) -> None:
        alphabets = list(ascii_lowercase)
        for i in range(randint(2, 4)):
            self.banned_letters.append(choice(alphabets))
            if self.banned_letters[-1] in "aeiou":
                alphabets = [c for c in alphabets if c not in "aeiou"]
            else:
                alphabets.remove(self.banned_letters[-1])
        self.banned_letters.sort()
        unbanned = "".join([c for c in ascii_lowercase if c not in self.banned_letters])
        n = 1
        self.current_word = sample(WORDS[choice(unbanned)], 1)[0]
        while (len(self.current_word) < self.min_letters_limit
               or any([c in self.current_word for c in self.banned_letters])):
            self.current_word = sample(WORDS[choice(unbanned)], 1)[0]
            n += 1
        self.used_words.add(self.current_word)
        print(f"Tried {n} time(s) to find word without letters {', '.join(self.banned_letters)}: {self.current_word}")
        await self.send_message(f"The first word is *{self.current_word.capitalize()}*.\n"
                                f"Banned letters: *{', '.join(c.upper() for c in self.banned_letters)}*\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))


class EliminationGame(ClassicGame):
    name = "elimination game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.min_players = GameSettings.SPECIAL_GAME_MIN_PLAYERS
        self.max_players = GameSettings.SPECIAL_GAME_MAX_PLAYERS
        self.time_left = GameSettings.SPECIAL_GAME_INITIAL_JOINING_PHASE_SECONDS
        self.time_limit = GameSettings.FIXED_TURN_SECONDS
        self.min_letters_limit = 0
        self.round = 1
        self.turns_until_elimination = 0

    async def forcejoin(self, message: types.Message):
        if self.state == GameState.JOINING:
            await super().forcejoin(message)

    def get_leaderboard(self, show_player: Optional[Player] = None) -> str:
        players = self.players_in_game[:]
        players.sort(key=attrgetter("total_letters"), reverse=True)
        text = ""
        if show_player:
            if len(players) <= 10:
                for i, p in enumerate(players, start=1):
                    t = f"{i}. {p.name}: {p.total_letters}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
            elif players.index(show_player) <= 5 or players.index(show_player) >= len(players) - 4:
                for i, p in enumerate(players[:5], start=1):
                    t = f"{i}. {p.name}: {p.total_letters}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
                text += "...\n"
                for i, p in enumerate(players[-5:], start=len(players) - 4):
                    t = f"{i}. {p.name}: {p.total_letters}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
            else:
                for i, p in enumerate(players[:5], start=1):
                    text += f"{i}. {p.name}: {p.total_letters}\n"
                text += f"...\n> {players.index(show_player) + 1}. {show_player.name}: {p.total_letters}\n...\n"
                for i, p in enumerate(players[-5:], start=len(players) - 4):
                    text += f"{i}. {p.name}: {p.total_letters}\n"
        else:
            for i, p in enumerate(players, start=1):
                text += f"{i}. {p.name}: {p.total_letters}\n"
        return text[:-1]

    async def send_turn_message(self) -> None:
        await self.send_message(
            (f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
             if self.turns_until_elimination > 1 else f"Turn: {self.players_in_game[0].mention}\n")
            + f"Your word must start with *{self.current_word[-1].upper()}*.\n"
              f"You have *{self.time_limit}s* to answer.\n\n" + "Leaderboard:\n"
            + self.get_leaderboard(show_player=self.players_in_game[0])
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"*{word.capitalize()}* does not start with *{self.current_word[-1].upper()}*.")
            return
        if word in self.used_words:
            await message.reply(f"*{word.capitalize()}* has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"*{word.capitalize()}* is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.players_in_game[0].total_letters += len(word)
        self.current_word = word
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.answered = True
        self.accepting_answers = False
        await self.send_message(f"*{word.capitalize()}* is accepted.")

    async def running_initialization(self) -> None:
        self.turns_until_elimination = len(self.players)
        self.current_word = sample(WORDS[choice(ascii_lowercase)], 1)[0]
        self.used_words.add(self.current_word)
        await self.send_message(f"The first word is *{self.current_word.capitalize()}*.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))
        await self.send_message("Round 1 is starting...")

    async def running_phase(self) -> Optional[bool]:
        if not self.answered:
            self.time_left -= 1
            if self.time_left > 0:
                return
            self.accepting_answers = False
            await self.send_message(f"{self.players_in_game[0].mention} ran out of time!")
        self.players_in_game.append(self.players_in_game.pop(0))
        self.turns_until_elimination -= 1
        if not self.turns_until_elimination:
            min_score = min(p.total_letters for p in self.players_in_game)
            eliminated = [p for p in self.players_in_game if p.total_letters == min_score]
            await self.send_message(
                f"Round {self.round} completed.\n\n"
                + "Leaderboard:\n" + self.get_leaderboard() + "\n\n"
                + ", ".join(p.mention for p in eliminated) + " " + ("is" if len(eliminated) == 1 else "are")
                + f" eliminated for having the lowest score of {min_score}."
            )
            self.players_in_game = [p for p in self.players_in_game if p not in eliminated]
            if len(self.players_in_game) <= 1:
                await self.send_message(
                    f"{(self.players_in_game[0].mention if self.players_in_game else 'No one')} won the game out of "
                    f"{len(self.players)} players!\nTotal words: {self.turns}"
                    + (f"\nLongest word: *{self.longest_word.capitalize()}* from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                )
                del GAMES[self.group_id]
                return True
            self.round += 1
            self.turns_until_elimination = len(self.players_in_game)
            await self.send_message(f"Round {self.round} is starting...\n\nLeaderboard:" + self.get_leaderboard())
        await self.send_turn_message()
