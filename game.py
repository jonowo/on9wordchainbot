import asyncio
import random
from datetime import datetime
from functools import lru_cache
from string import ascii_lowercase
from typing import Optional, Any

from aiogram import types
from aiogram.utils.markdown import escape_md
from aiogram.utils.exceptions import BadRequest

from constants import bot, on9bot, ON9BOT_ID, VIP, GAMES, pool, WORDS, WORDS_LI, GameState, GameSettings, amt_donated


class Player:
    def __init__(self, user: Optional[types.User] = None, vp: bool = False, donor=False) -> None:
        if vp:  # VP - On9Bot
            self.user_id = ON9BOT_ID
            self.name = "[On9Bot \u2b50\ufe0f](https://t.me/On9Bot)"
            self.mention = f"[On9Bot \u2b50\ufe0f](tg://user?id={self.user_id})"
        else:
            self.user_id = user.id
            if donor:
                if user.username:
                    self.name = f"[{escape_md(user.full_name)} \u2b50\ufe0f](https://t.me/{user.username})"
                else:
                    self.name = f"*{escape_md(user.full_name)} \u2b50\ufe0f*"
                self.mention = f"[{escape_md(user.full_name)} \u2b50\ufe0f]({user.url})"
            else:
                if user.username:
                    self.name = f"[{escape_md(user.full_name)}](https://t.me/{user.username})"
                else:
                    self.name = f"*{escape_md(user.full_name)}*"
                self.mention = f"[{escape_md(user.full_name)}]({user.url})"
        self.word_count = 0
        self.letter_count = 0
        self.longest_word = ""


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
        self.start_time = None
        self.end_time = None

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
        player = Player(user, donor=user.id in VIP or bool(await amt_donated(user.id)))
        self.players.append(player)
        await message.reply(f"{player.name} joined. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def forcejoin(self, message: types.Message) -> None:
        if self.state == GameState.KILLGAME or len(self.players) >= self.max_players:
            return
        rmsg = message.reply_to_message
        user = message.reply_to_message.from_user if rmsg else message.from_user
        for p in self.players:
            if p.user_id == user.id:
                return
        player = Player(user, donor=user.id in VIP or bool(await amt_donated(user.id)))
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
        if self.state != GameState.JOINING:
            return
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        else:
            return
        await message.reply(f"{player.name} fled. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)

    async def forceflee(self, message: types.Message) -> None:
        if self.state != GameState.JOINING or not message.reply_to_message:
            return
        user_id = message.reply_to_message.from_user.id
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        else:
            return
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
            await message.reply(f"The joining phase has been extended by "
                                f"{min(n, GameSettings.MAX_JOINING_PHASE_SECONDS)}s.\n"
                                f"You have {self.time_left}s to /join.")

    async def addvp(self, message: types.Message) -> None:
        try:
            vp = await bot.get_chat_member(self.group_id, ON9BOT_ID)
            assert vp.is_chat_member() or vp.is_chat_admin()
        except (BadRequest, AssertionError):
            await self.send_message(f"You have to add [On9Bot](tg://user?id={ON9BOT_ID}) "
                                    "into this group before using /addvp.",
                                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
                                        types.InlineKeyboardButton("Add On9Bot to this group!",
                                                                   url="https://t.me/On9Bot?startgroup=_")
                                    ]]))
            return
        if self.state != GameState.JOINING or len(self.players) >= self.max_players:
            return
        for p in self.players:
            if p.user_id == ON9BOT_ID:
                return
        vp = Player(vp=True)
        self.players.append(vp)
        await on9bot.send_message(self.group_id, "/join@on9wordchainbot")
        await message.reply(f"{vp.name} joined. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def remvp(self, message: types.Message) -> None:
        if self.state != GameState.JOINING:
            return
        for i in range(len(self.players)):
            if self.players[i].user_id == ON9BOT_ID:
                vp = self.players.pop(i)
                break
        else:
            return
        await on9bot.send_message(self.group_id, "/flee@on9wordchainbot")
        await message.reply(f"{vp.name} fled. There {'is' if len(self.players) == 1 else 'are'} "
                            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
                            disable_web_page_preview=True)

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with _{self.current_word[-1].upper()}_ "
            f"and include *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit
        if self.players_in_game[0].user_id != ON9BOT_ID:
            return
        li = WORDS_LI[self.current_word[-1]][:]
        random.shuffle(li)
        for word in li:
            if len(word) >= self.min_letters_limit and word not in self.used_words:
                await on9bot.send_message(self.group_id, word.capitalize())
                self.used_words.add(word)
                self.turns += 1
                self.current_word = word
                self.players_in_game[0].word_count += 1
                self.players_in_game[0].letter_count += len(word)
                if len(word) > len(self.longest_word):
                    self.longest_word = word
                    self.longest_word_sender_id = ON9BOT_ID
                self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
                text = f"_{word.capitalize()}_ is accepted.\n\n"
                if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
                    if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                        self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                        text += (f"Time limit decreased from "
                                 f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                                 f"*{self.time_limit}s*.\n")
                    if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                        self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                        text += (
                            f"Minimum letters per word increased from "
                            f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                            f"to *{self.min_letters_limit}*.\n"
                        )
                self.answered = True
                self.accepting_answers = False
                await self.send_message(text.rstrip())
                break
        else:
            await on9bot.send_message(self.group_id, "/forceskip I'm done")
            await asyncio.sleep(1)
            self.time_left = 0

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"_{word.capitalize()}_ has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.current_word = word
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        text = f"_{word.capitalize()}_ is accepted.\n\n"
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
        self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.\n\n"
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
                self.end_time = datetime.now().replace(microsecond=0)
                td = self.end_time - self.start_time
                await self.send_message(
                    f"{self.players_in_game[0].mention} won the game out of {len(self.players)} players!\n"
                    f"Total words: {self.turns}"
                    + (f"\nLongest word: _{self.longest_word.capitalize()}_ from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                    + f"\nGame length: `{str(int(td.total_seconds()) // 3600).zfill(2)}{str(td)[-6:]}`"
                )
                del GAMES[self.group_id]
                return True
        await self.send_turn_message()

    async def update_db(self) -> None:
        async with pool.acquire() as conn:
            await conn.execute("""\
INSERT INTO game (group_id, players, game_mode, winner, start_time, end_time)
VALUES
    ($1, $2, $3, $4, $5, $6);""",
                               self.group_id, len(self.players), self.__class__.__name__,
                               self.players_in_game[0].user_id if self.players_in_game else None,
                               self.start_time, self.end_time)
            game_id = await conn.fetchval("SELECT id FROM game WHERE group_id = $1 AND start_time = $2",
                                          self.group_id, self.start_time)
            stmt = await conn.prepare("SELECT * FROM player WHERE user_id = $1")
            for p in self.players:
                if not await stmt.fetchval(p.user_id):
                    await conn.execute("""\
INSERT INTO player (user_id, game_count, win_count, word_count, letter_count, longest_word)
VALUES
    ($1, 1, $2, $3, $4, $5::TEXT)""",
                                       p.user_id, int(p in self.players_in_game), p.word_count, p.letter_count,
                                       p.longest_word or None)
                else:
                    await conn.execute("""\
UPDATE player
SET game_count = game_count + 1,
    win_count = win_count + $1,
    word_count = word_count + $2,
    letter_count = letter_count + $3,
    longest_word = CASE WHEN longest_word IS NULL THEN $4::TEXT
                        WHEN $4::TEXT IS NULL THEN longest_word
                        WHEN LENGTH($4::TEXT) > LENGTH(longest_word) THEN $4::TEXT
                        ELSE longest_word
                   END
WHERE user_id = $5;""",
                                       int(p in self.players_in_game),
                                       p.word_count, p.letter_count, p.longest_word or None, p.user_id)
                await conn.execute("""\
INSERT INTO gameplayer (user_id, group_id, game_id, won, word_count, letter_count, longest_word)
VALUES
    ($1, $2, $3, $4, $5, $6, $7);""",
                                   p.user_id, self.group_id, game_id, p in self.players_in_game,
                                   p.word_count, p.letter_count, p.longest_word or None)

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
                        random.shuffle(self.players)
                        self.players_in_game = self.players[:]
                        await self.running_initialization()
                        await self.send_turn_message()
            elif self.state == GameState.RUNNING:
                if await self.running_phase():
                    await self.update_db()
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
            f"Your word must start with _{self.current_word[-1].upper()}_ "
            f"and contain *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit
        if self.players_in_game[0].user_id != ON9BOT_ID:
            return
        li = WORDS_LI[self.current_word[-1]][:]
        random.shuffle(li)
        for word in li:
            if len(word) >= self.min_letters_limit and word not in self.used_words:
                await on9bot.send_message(self.group_id, word.capitalize())
                self.used_words.add(word)
                self.turns += 1
                self.current_word = word
                self.players_in_game[0].word_count += 1
                self.players_in_game[0].letter_count += len(word)
                if len(word) > len(self.longest_word):
                    self.longest_word = word
                    self.longest_word_sender_id = ON9BOT_ID
                text = f"_{word.capitalize()}_ is accepted.\n\n"
                if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
                    if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                        self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                        text += (f"Time limit decreased from "
                                 f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                                 f"*{self.time_limit}s*.\n")
                    if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                        self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                        text += (
                            f"Minimum letters per word increased from "
                            f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                            f"to *{self.min_letters_limit}*.\n"
                        )
                self.answered = True
                self.accepting_answers = False
                await self.send_message(text.rstrip())
                break
        else:
            await on9bot.send_message(self.group_id, "/forceskip I'm done")
            await asyncio.sleep(1)
            self.time_left = 0

    async def running_initialization(self) -> None:
        self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.")

    async def running_phase(self) -> Optional[bool]:
        if self.answered:
            self.players_in_game.append(self.players_in_game.pop(0))
            self.players_in_game.insert(0, self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 2)))
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return
            self.accepting_answers = False
            await self.send_message(f"{self.players_in_game[0].mention} ran out of time! Out!")
            del self.players_in_game[0]
            if len(self.players_in_game) == 1:
                self.end_time = datetime.now().replace(microsecond=0)
                td = self.end_time - self.start_time
                await self.send_message(
                    f"{self.players_in_game[0].mention} won the game out of {len(self.players)} players!\n"
                    f"Total words: {self.turns}"
                    + (f"\nLongest word: _{self.longest_word.capitalize()}_ from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                    + f"\nGame length: `{str(int(td.total_seconds()) // 3600).zfill(2)}{str(td)[-6:]}`"
                )
                del GAMES[self.group_id]
                return True
            self.players_in_game.insert(0, self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 2)))
        await self.send_turn_message()


class ChosenFirstLetterGame(ClassicGame):
    name = "chosen first letter game"

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with _{self.current_word.upper()}_ "
            f"and contain *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit
        if self.players_in_game[0].user_id != ON9BOT_ID:
            return
        li = WORDS_LI[self.current_word][:]
        random.shuffle(li)
        for word in li:
            if len(word) >= self.min_letters_limit and word not in self.used_words:
                await on9bot.send_message(self.group_id, word.capitalize())
                self.used_words.add(word)
                self.turns += 1
                self.players_in_game[0].word_count += 1
                self.players_in_game[0].letter_count += len(word)
                if len(word) > len(self.longest_word):
                    self.longest_word = word
                    self.longest_word_sender_id = ON9BOT_ID
                self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
                text = f"_{word.capitalize()}_ is accepted.\n\n"
                if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
                    if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                        self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                        text += (f"Time limit decreased from "
                                 f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                                 f"*{self.time_limit}s*.\n")
                    if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                        self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                        text += (
                            f"Minimum letters per word increased from "
                            f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                            f"to *{self.min_letters_limit}*.\n"
                        )
                self.answered = True
                self.accepting_answers = False
                await self.send_message(text.rstrip())
                break
        else:
            await on9bot.send_message(self.group_id, "/forceskip I'm done")
            await asyncio.sleep(1)
            self.time_left = 0

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if word[0] != self.current_word:
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word.upper()}_.")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"_{word.capitalize()}_ has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        text = f"_{word.capitalize()}_ is accepted.\n\n"
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
        self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The chosen first letter is _{self.current_word.upper()}_.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))


class BannedLettersGame(ClassicGame):
    name = "banned letters game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.banned_letters = []

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with _{self.current_word[-1].upper()}_, "
            f"*exclude* _{', '.join(c.upper() for c in self.banned_letters)}_ "
            f"and include *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit
        if self.players_in_game[0].user_id != ON9BOT_ID:
            return
        li = WORDS_LI[self.current_word[-1]][:]
        random.shuffle(li)
        for word in li:
            if (len(word) >= self.min_letters_limit and word not in self.used_words
                    and all([c not in word for c in self.banned_letters])):
                await on9bot.send_message(self.group_id, word.capitalize())
                self.used_words.add(word)
                self.turns += 1
                self.current_word = word
                self.players_in_game[0].word_count += 1
                self.players_in_game[0].letter_count += len(word)
                if len(word) > len(self.longest_word):
                    self.longest_word = word
                    self.longest_word_sender_id = ON9BOT_ID
                self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
                text = f"_{word.capitalize()}_ is accepted.\n\n"
                if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
                    if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                        self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                        text += (f"Time limit decreased from "
                                 f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                                 f"*{self.time_limit}s*.\n")
                    if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                        self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                        text += (
                            f"Minimum letters per word increased from "
                            f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                            f"to *{self.min_letters_limit}*.\n"
                        )
                self.answered = True
                self.accepting_answers = False
                await self.send_message(text.rstrip())
                break
        else:
            await on9bot.send_message(self.group_id, "/forceskip I'm done")
            await asyncio.sleep(1)
            self.time_left = 0

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if any(c for c in self.banned_letters if c in word):
            await message.reply(f"_{word.capitalize()}_ include banned letters "
                                f"({', '.join(c.upper() for c in self.banned_letters if c in word)}).")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"_{word.capitalize()}_ has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.current_word = word
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        text = f"_{word.capitalize()}_ is accepted.\n\n"
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
        for i in range(random.randint(2, 4)):
            self.banned_letters.append(random.choice(alphabets))
            if self.banned_letters[-1] in "aeiou":
                alphabets = [c for c in alphabets if c not in "aeiou"]
            else:
                alphabets.remove(self.banned_letters[-1])
        self.banned_letters.sort()
        unbanned = "".join([c for c in ascii_lowercase if c not in self.banned_letters])
        self.current_word = random.choice(WORDS_LI[random.choice(unbanned)])
        while (len(self.current_word) < self.min_letters_limit
               or any(c in self.current_word for c in self.banned_letters)):
            self.current_word = random.choice(WORDS_LI[random.choice(unbanned)])
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.\n"
                                f"Banned letters: _{', '.join(c.upper() for c in self.banned_letters)}_\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))


class RequiredLetterGame(ClassicGame):
    name = "required letter game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.required_letter = None

    async def send_turn_message(self) -> None:
        await self.send_message(
            f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
            f"Your word must start with _{self.current_word[-1].upper()}_, "
            f"*include* _{self.required_letter.upper()}_ "
            f"and *at least {self.min_letters_limit} letter{'' if self.min_letters_limit == 1 else 's'}*.\n"
            f"You have *{self.time_limit}s* to answer.\n"
            f"Players remaining: {len(self.players_in_game)}/{len(self.players)}\n"
            f"Total words: {self.turns}"
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit
        if self.players_in_game[0].user_id != ON9BOT_ID:
            return
        li = WORDS_LI[self.current_word[-1]][:]
        random.shuffle(li)
        for word in li:
            if (len(word) >= self.min_letters_limit and word not in self.used_words
                    and self.required_letter in word):
                await on9bot.send_message(self.group_id, word.capitalize())
                self.used_words.add(word)
                self.turns += 1
                self.current_word = word
                self.players_in_game[0].word_count += 1
                self.players_in_game[0].letter_count += len(word)
                self.required_letter = random.choice([c for c in ascii_lowercase if c != word[-1]])
                if len(word) > len(self.longest_word):
                    self.longest_word = word
                    self.longest_word_sender_id = ON9BOT_ID
                self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
                text = f"_{word.capitalize()}_ is accepted.\n\n"
                if not self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE:
                    if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                        self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                        text += (f"Time limit decreased from "
                                 f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* to "
                                 f"*{self.time_limit}s*.\n")
                    if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                        self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                        text += (
                            f"Minimum letters per word increased from "
                            f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                            f"to *{self.min_letters_limit}*.\n"
                        )
                self.answered = True
                self.accepting_answers = False
                await self.send_message(text.rstrip())
                break
        else:
            await on9bot.send_message(self.group_id, "/forceskip I'm done")
            await asyncio.sleep(1)
            self.time_left = 0

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if self.required_letter not in word:
            await message.reply(f"_{word.capitalize()}_ does not include _{self.required_letter}_.")
            return
        if len(word) < self.min_letters_limit:
            await message.reply(f"_{word.capitalize()}_ has less than {self.min_letters_limit} letters.")
            return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.current_word = word
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        self.required_letter = random.choice([c for c in ascii_lowercase if c != word[-1]])
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        text = f"_{word.capitalize()}_ is accepted.\n\n"
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
        self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        while len(self.current_word) < self.min_letters_limit:
            self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        self.used_words.add(self.current_word)
        self.required_letter = random.choice([c for c in ascii_lowercase if c != self.current_word[-1]])
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.\n\n"
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
        players.sort(key=lambda k: (k.letter_count, k.user_id), reverse=True)
        text = ""
        if show_player:
            if len(players) <= 10:
                for i, p in enumerate(players, start=1):
                    t = f"{i}. {p.name}: {p.letter_count}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
            elif players.index(show_player) <= 5 or players.index(show_player) >= len(players) - 4:
                for i, p in enumerate(players[:5], start=1):
                    t = f"{i}. {p.name}: {p.letter_count}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
                text += "...\n"
                for i, p in enumerate(players[-5:], start=len(players) - 4):
                    t = f"{i}. {p.name}: {p.letter_count}\n"
                    if p == show_player:
                        t = "> " + t
                    text += t
            else:
                for i, p in enumerate(players[:5], start=1):
                    text += f"{i}. {p.name}: {p.letter_count}\n"
                text += f"...\n> {players.index(show_player) + 1}. {show_player.name}: {p.letter_count}\n...\n"
                for i, p in enumerate(players[-5:], start=len(players) - 4):
                    text += f"{i}. {p.name}: {p.letter_count}\n"
        else:
            for i, p in enumerate(players, start=1):
                text += f"{i}. {p.name}: {p.letter_count}\n"
        return text[:-1]

    async def send_turn_message(self) -> None:
        await self.send_message(
            (f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
             if self.turns_until_elimination > 1 else f"Turn: {self.players_in_game[0].mention}\n")
            + f"Your word must start with _{self.current_word[-1].upper()}_.\n"
              f"You have *{self.time_limit}s* to answer.\n\n" + "Leaderboard:\n"
            + self.get_leaderboard(show_player=self.players_in_game[0])
        )
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        self.current_word = word
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        self.answered = True
        self.accepting_answers = False
        await self.send_message(f"_{word.capitalize()}_ is accepted.")

    async def running_initialization(self) -> None:
        self.turns_until_elimination = len(self.players)
        self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))
        await self.send_message("Round 1 is starting...\n\nLeaderboard:\n" + self.get_leaderboard())

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
            min_score = min(p.letter_count for p in self.players_in_game)
            eliminated = [p for p in self.players_in_game if p.letter_count == min_score]
            await self.send_message(
                f"Round {self.round} completed.\n\nLeaderboard:\n" + self.get_leaderboard() + "\n\n"
                + ", ".join(p.mention for p in eliminated) + " " + ("is" if len(eliminated) == 1 else "are")
                + f" eliminated for having the lowest score of {min_score}."
            )
            self.players_in_game = [p for p in self.players_in_game if p not in eliminated]
            if len(self.players_in_game) <= 1:
                self.end_time = datetime.now().replace(microsecond=0)
                td = self.end_time - self.start_time
                await self.send_message(
                    f"{(self.players_in_game[0].mention if self.players_in_game else 'No one')} won the game out of "
                    f"{len(self.players)} players!\n"
                    f"Total words: {self.turns}"
                    + (f"\nLongest word: _{self.longest_word.capitalize()}_ from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                    + f"\nGame length: `{str(int(td.total_seconds()) // 3600).zfill(2)}{str(td)[-6:]}`"
                )
                del GAMES[self.group_id]
                return True
            self.round += 1
            self.turns_until_elimination = len(self.players_in_game)
            await self.send_message(f"Round {self.round} is starting...\n\nLeaderboard:\n" + self.get_leaderboard())
        await self.send_turn_message()


class MixedEliminationGame(EliminationGame):
    name = "mixed elimination game"
    game_modes = [ClassicGame, ChosenFirstLetterGame, BannedLettersGame, RequiredLetterGame]

    def __init__(self, group_id):
        super().__init__(group_id)
        self.game_mode = None
        self.banned_letters = []
        self.required_letter = None

    async def send_turn_message(self) -> None:
        text = f"Turn: {self.players_in_game[0].mention}"
        if self.turns_until_elimination > 1:
            text += f" (Next: {self.players_in_game[1].name})"
        text += (f"\nYour word must start with "
                 f"_{self.current_word[0 if self.game_mode is ChosenFirstLetterGame else -1].upper()}_")
        if self.game_mode is BannedLettersGame:
            text += f" and *exclude* _{', '.join(c.upper() for c in self.banned_letters)}_"
        elif self.game_mode is RequiredLetterGame:
            text += f" and *include* _{self.required_letter.upper()}_"
        text += ".\n" + f"You have *{self.time_limit}s* to answer.\n\n" + "Leaderboard:\n"
        await self.send_message(text + self.get_leaderboard(show_player=self.players_in_game[0]))
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()
        if self.game_mode is ChosenFirstLetterGame:
            if not word.startswith(self.current_word[0]):
                await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[0].upper()}_.")
                return
        elif not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if self.game_mode is BannedLettersGame:
            if any(c for c in self.banned_letters if c in word):
                await message.reply(f"_{word.capitalize()}_ include banned letters "
                                    f"({', '.join(c.upper() for c in self.banned_letters if c in word)}).")
                return
        elif self.game_mode is RequiredLetterGame:
            if self.required_letter not in word:
                await message.reply(f"_{word.capitalize()}_ does not include _{self.required_letter}_.")
                return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if word not in WORDS[word[0]]:
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        self.used_words.add(word)
        self.turns += 1
        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        if self.game_mode is RequiredLetterGame:
            self.required_letter = random.choice([c for c in ascii_lowercase if c != word[-1]])
        self.current_word = word
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = message.from_user.id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=str.__len__)
        self.answered = True
        self.accepting_answers = False
        await self.send_message(f"_{word.capitalize()}_ is accepted.")

    async def running_initialization(self) -> None:
        self.turns_until_elimination = len(self.players)
        self.game_mode = random.choice(self.game_modes)
        text = f"Round 1 is starting...\nMode: *{self.game_mode.name.capitalize()}*"
        if self.game_mode is not BannedLettersGame:
            self.current_word = random.choice(WORDS_LI[random.choice(ascii_lowercase)])
        if self.game_mode is ChosenFirstLetterGame:
            text += f"\nThe chosen first letter is _{self.current_word[0].upper()}_."
        elif self.game_mode is BannedLettersGame:
            alphabets = list(ascii_lowercase)
            for i in range(random.randint(2, 4)):
                self.banned_letters.append(random.choice(alphabets))
                if self.banned_letters[-1] in "aeiou":
                    alphabets = [c for c in alphabets if c not in "aeiou"]
                else:
                    alphabets.remove(self.banned_letters[-1])
            self.banned_letters.sort()
            unbanned = "".join([c for c in ascii_lowercase if c not in self.banned_letters])
            self.current_word = random.choice(WORDS_LI[random.choice(unbanned)])
            while any(c in self.current_word for c in self.banned_letters):
                self.current_word = random.choice(WORDS_LI[random.choice(unbanned)])
            text += f"\nBanned letters: _{', '.join(c.upper() for c in self.banned_letters)}_"
        elif self.game_mode is RequiredLetterGame:
            self.required_letter = random.choice([c for c in ascii_lowercase if c != self.current_word[-1]])
        if self.game_mode is not ChosenFirstLetterGame:
            self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)
        await self.send_message(f"The first word is _{self.current_word.capitalize()}_.\n\n"
                                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]))
        await self.send_message(text + "\n\nLeaderboard:\n" + self.get_leaderboard())

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
            min_score = min(p.letter_count for p in self.players_in_game)
            eliminated = [p for p in self.players_in_game if p.letter_count == min_score]
            await self.send_message(
                f"Round {self.round} completed.\n\nLeaderboard:\n" + self.get_leaderboard() + "\n\n"
                + ", ".join(p.mention for p in eliminated) + " " + ("is" if len(eliminated) == 1 else "are")
                + f" eliminated for having the lowest score of {min_score}."
            )
            self.players_in_game = [p for p in self.players_in_game if p not in eliminated]
            if len(self.players_in_game) <= 1:
                self.end_time = datetime.now().replace(microsecond=0)
                td = self.end_time - self.start_time
                await self.send_message(
                    f"{(self.players_in_game[0].mention if self.players_in_game else 'No one')} won the game out of "
                    f"{len(self.players)} players!\n"
                    f"Total words: {self.turns}"
                    + (f"\nLongest word: _{self.longest_word.capitalize()}_ from "
                       f"{[p.name for p in self.players if p.user_id == self.longest_word_sender_id][0]}"
                       if self.longest_word else "")
                    + f"\nGame length: `{str(int(td.total_seconds()) // 3600).zfill(2)}{str(td)[-6:]}`"
                )
                del GAMES[self.group_id]
                return True
            self.round += 1
            self.turns_until_elimination = len(self.players_in_game)
            self.game_mode = random.choice([i for i in self.game_modes if i is not self.game_mode])
            text = f"Round {self.round} is starting...\nMode: *{self.game_mode.name.capitalize()}*"
            if self.game_mode is ChosenFirstLetterGame:
                self.current_word = self.current_word[-1]
                text += f"\nThe chosen first letter is _{self.current_word[0].upper()}_."
            elif self.game_mode is BannedLettersGame:
                alphabets = list(ascii_lowercase)
                alphabets.remove(self.current_word[-1])
                for i in range(random.randint(2, 4)):
                    self.banned_letters.append(random.choice(alphabets))
                    if self.banned_letters[-1] in "aeiou":
                        alphabets = [c for c in alphabets if c not in "aeiou"]
                    else:
                        alphabets.remove(self.banned_letters[-1])
                self.banned_letters.sort()
                text += f"\nBanned letters: _{', '.join(c.upper() for c in self.banned_letters)}_"
            elif self.game_mode is RequiredLetterGame:
                self.required_letter = random.choice([c for c in ascii_lowercase if c != self.current_word[-1]])
            await self.send_message(text + "\n\nLeaderboard:\n" + self.get_leaderboard())
        await self.send_turn_message()
