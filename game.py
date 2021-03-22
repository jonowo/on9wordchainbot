import asyncio
import random
from datetime import datetime
from string import ascii_lowercase
from typing import Any, Optional

from aiocache import cached
from aiogram import types
from aiogram.utils.exceptions import BadRequest
from aiogram.utils.markdown import quote_html

from constants import GAMES, STAR, GameSettings, GameState, bot, on9bot, pool, OWNER_ID
from utils import get_random_word, send_admin_group, check_word_existence, has_star


class Player:
    def __init__(self, user: Optional[types.User] = None, vp: bool = False) -> None:
        if vp:  # VP: On9Bot
            self.user_id = on9bot.id
            self.name = f"<a href='https://t.me/On9Bot'>On9Bot {STAR}</a>"
            self.mention = f"<a href='tg://user?id={on9bot.id}'>On9Bot {STAR}</a>"
            self.is_vp = True
        else:
            self.user_id = user.id
            if user.username:
                self.name = f"<a href='https://t.me/{user.username}'>{quote_html(user.full_name)}</a>"
            else:
                self.name = f"<b>{quote_html(user.full_name)}</b>"
            self.mention = user.get_mention(as_html=True)
            self.is_vp = False

        self.word_count = 0
        self.letter_count = 0
        self.longest_word = ""

        # For elimination games only
        # Though generally score = letter count,
        # there is turn score increment ceiling for more balanced gameplay
        self.score = 0

    async def update_donor_status(self, user: types.User) -> None:
        # When you can't use async functions in __init__
        if not await has_star(user.id):
            return

        if user.username:
            self.name = f"<a href='https://t.me/{user.username}'>{quote_html(user.full_name)} {STAR}</a>"
        else:
            self.name = f"<b>{quote_html(user.full_name)} {STAR}</b>"
        self.mention = user.get_mention(name=f"{user.full_name} {STAR}", as_html=True)


class ClassicGame:
    name = "classic game"

    def __init__(self, group_id: int) -> None:
        self.group_id = group_id
        self.players = []
        self.players_in_game = []
        self.state = GameState.JOINING
        self.start_time = None
        self.end_time = None
        # Store user ids rather than Player object since players may quit then join to extend again
        self.extended_user_ids = set()

        # Game settings
        self.min_players = GameSettings.NORMAL_GAME_MIN_PLAYERS
        self.max_players = GameSettings.MAX_PLAYERS
        self.time_left = GameSettings.INITIAL_JOINING_PHASE_SECONDS
        self.time_limit = GameSettings.MAX_TURN_SECONDS
        self.min_letters_limit = GameSettings.MIN_WORD_LENGTH_LIMIT

        # Game attributes
        self.current_word = None
        self.longest_word = ""
        self.longest_word_sender_id = None  # TODO: Change to PLayer object instead of id
        self.answered = False
        self.accepting_answers = False
        self.turns = 0
        self.used_words = set()

    def user_in_game(self, user_id: int) -> bool:
        for p in self.players:
            if p.user_id == user_id:
                return True
        return False

    async def send_message(self, *args: Any, **kwargs: Any) -> types.Message:
        return await bot.send_message(self.group_id, *args, disable_web_page_preview=True, **kwargs)

    @cached(ttl=15)
    async def is_admin(self, user_id: int) -> bool:
        user = await bot.get_chat_member(self.group_id, user_id)
        return user.is_chat_admin()

    async def join(self, message: types.Message) -> None:
        if self.state != GameState.JOINING or len(self.players) >= self.max_players:
            return

        # Try to detect game not starting
        if self.time_left < 0:
            await self.scan_for_stale_timer()
            return

        # Check if user already joined
        user = message.from_user
        if self.user_in_game(user.id):
            return

        player = Player(user)
        self.players.append(player)
        await player.update_donor_status(user)

        await self.send_message(
            f"{player.name} joined. There {'is' if len(self.players) == 1 else 'are'} "
            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
            parse_mode=types.ParseMode.HTML,
        )

        # Start game when max players reached
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def forcejoin(self, message: types.Message) -> None:
        if self.state == GameState.KILLGAME or len(self.players) >= self.max_players:
            return

        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            user = message.from_user

        # Check if user already joined
        if self.user_in_game(user.id):
            return

        if user.id == on9bot.id:
            player = Player(vp=True)
        else:
            player = Player(user)
        self.players.append(player)
        if self.state == GameState.RUNNING:
            self.players_in_game.append(player)
        if user.id != on9bot.id:
            await player.update_donor_status(user)

        await self.send_message(
            f"{player.name} has been joined. There {'is' if len(self.players) == 1 else 'are'} "
            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
            parse_mode=types.ParseMode.HTML,
        )

        # Start game when max players reached
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def flee(self, message: types.Message) -> None:
        if self.state != GameState.JOINING:
            return

        # Find player to remove
        user_id = message.from_user.id
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        else:
            return

        await self.send_message(
            f"{player.name} fled. There {'is' if len(self.players) == 1 else 'are'} "
            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
            parse_mode=types.ParseMode.HTML,
        )

    async def forceflee(self, message: types.Message) -> None:
        # Player to be fled = Sender of replies message
        if self.state != GameState.JOINING or not message.reply_to_message:
            return

        # Find player to remove
        user_id = message.reply_to_message.from_user.id
        for i in range(len(self.players)):
            if self.players[i].user_id == user_id:
                player = self.players.pop(i)
                break
        else:
            return

        await self.send_message(
            f"{player.name} has been fled. There {'is' if len(self.players) == 1 else 'are'} "
            f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}.",
            parse_mode=types.ParseMode.HTML,
        )

    async def extend(self, message: types.Message) -> None:
        if self.state != GameState.JOINING:
            return

        # Check if extender is player/admin/owner
        if (
            message.from_user.id != OWNER_ID
            and not self.user_in_game(message.from_user.id)
            and not await self.is_admin(message.from_user.id)
        ):
            await self.send_message("Imagine not being a player")
            return

        # Each player can only extend once and only for 30 seconds except admins
        if await self.is_admin(message.from_user.id):
            arg = message.text.partition(" ")[2]

            # Check if arg is a valid negative integer
            try:
                n = int(arg)
                is_neg = n < 0
                n = abs(n)
            except ValueError:
                n = 30
                is_neg = False
        elif message.from_user.id in self.extended_user_ids:
            await self.send_message("You can only extend once peasant")
            return
        else:
            self.extended_user_ids.add(message.from_user.id)
            n = 30
            is_neg = False

        if is_neg:
            # Reduce joining phase time (admins only)
            if not await self.is_admin(message.from_user.id):
                await self.send_message("Imagine not being admin")
                return

            if n >= self.time_left:
                # Start game immediately
                self.time_left = -99999
            else:
                self.time_left -= n
                await self.send_message(
                    f"The joining phase has been reduced by {n}s.\n"
                    f"You have {self.time_left}s to /join."
                )
        else:
            # Extend joining phase time
            # Max joining phase duration is capped
            added_duration = min(n, GameSettings.MAX_JOINING_PHASE_SECONDS - self.time_left)
            self.time_left += added_duration
            await self.send_message(
                f"The joining phase has been extended by {added_duration}s.\n"
                f"You have {self.time_left}s to /join."
            )

    async def addvp(self, message: types.Message) -> None:
        if self.state != GameState.JOINING or len(self.players) >= self.max_players:
            return

        # Check if On9Bot already joined
        for p in self.players:
            if p.is_vp:
                return

        # Check if vp adder is player/admin/owner
        if (
            message.from_user.id != OWNER_ID
            and not self.user_in_game(message.from_user.id)
            and not await self.is_admin(message.from_user.id)
        ):
            await self.send_message("Imagine not being a player")
            return

        try:
            vp = await bot.get_chat_member(self.group_id, on9bot.id)
            # VP must be chat member
            assert vp.is_chat_member() or vp.is_chat_admin()
        except (BadRequest, AssertionError):
            await self.send_message(
                f"Add [On9Bot](tg://user?id={on9bot.id}) here to play as a virtual player.",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                "Add On9Bot",
                                url="https://t.me/On9Bot?startgroup=_",
                            )
                        ]
                    ]
                ),
            )
            return

        vp = Player(vp=True)
        self.players.append(vp)

        await on9bot.send_message(self.group_id, "/join@" + (await bot.me).username)
        await self.send_message(
            (
                f"{vp.name} joined. There {'is' if len(self.players) == 1 else 'are'} "
                f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}."
            ),
            parse_mode=types.ParseMode.HTML,
        )

        # Start game when max players reached
        if len(self.players) >= self.max_players:
            self.time_left = -99999

    async def remvp(self, message: types.Message) -> None:
        if self.state != GameState.JOINING:
            return

        # Check if On9Bot has joined
        for i in range(len(self.players)):
            if self.players[i].is_vp:
                vp = self.players.pop(i)
                break
        else:
            return

        # Check if vp remover is player/admin
        if (
            message.from_user.id != OWNER_ID
            and not self.user_in_game(message.from_user.id)
            and not await self.is_admin(message.from_user.id)
        ):
            await self.send_message("Imagine not being a player")
            return

        await on9bot.send_message(self.group_id, "/flee@" + (await bot.me).username)
        await self.send_message(
            (
                f"{vp.name} fled. There {'is' if len(self.players) == 1 else 'are'} "
                f"{len(self.players)} player{'' if len(self.players) == 1 else 's'}."
            ),
            parse_mode=types.ParseMode.HTML,
        )

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
                f"Your word must start with <i>{self.current_word[-1].upper()}</i> and "
                f"include <b>at least {self.min_letters_limit} letters</b>.\n"
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

    def get_random_valid_answer(self) -> Optional[str]:
        return get_random_word(
            min_len=self.min_letters_limit,
            starting_letter=self.current_word[-1],
            exclude_words=self.used_words,
        )

    async def vp_answer(self) -> None:
        # Wait before answering to prevent exceeding 20 msg/min message limit
        # Also simulate thinking/input time like human players, wowzers
        await asyncio.sleep(random.uniform(2, 5))

        word = self.get_random_valid_answer()

        if not word:  # No valid words to choose from
            await on9bot.send_message(self.group_id, "/forceskip bey")
            self.time_left = 0
            return

        await on9bot.send_message(self.group_id, word.capitalize())

        self.post_turn_processing(word)
        await self.send_post_turn_message(word)

    async def additional_answer_checkers(self, word: str, message: types.Message) -> bool:
        # To be overridden by other game modes
        # True/False: valid/invalid answer
        return True

    async def handle_answer(self, message: types.Message) -> None:
        word = message.text.lower()

        # Check if answer is invalid
        if not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return
        if not isinstance(self, EliminationGame):  # No minimum letters limit for elimination game modes
            if len(word) < self.min_letters_limit:
                await message.reply(f"_{word.capitalize()}_ has less than {self.min_letters_limit} letters.")
                return
        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if not check_word_existence(word):
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
            return
        if not await self.additional_answer_checkers(word, message):
            return

        self.post_turn_processing(word)
        await self.send_post_turn_message(word)

    def post_turn_processing(self, word: str) -> None:
        # Update attributes
        self.used_words.add(word)
        self.turns += 1

        # self.current_word is constant for ChosenFirstLetterGame
        if not isinstance(self, ChosenFirstLetterGame):
            self.current_word = word

        self.players_in_game[0].word_count += 1
        self.players_in_game[0].letter_count += len(word)
        if isinstance(self, EliminationGame):
            self.players_in_game[0].score += min(len(word), GameSettings.ELIM_MAX_TURN_SCORE)
            if len(word) > GameSettings.ELIM_MAX_TURN_SCORE:
                self.exceeded_score_limit = True
        if len(word) > len(self.longest_word):
            self.longest_word = word
            self.longest_word_sender_id = self.players_in_game[0].user_id
        self.players_in_game[0].longest_word = max(word, self.players_in_game[0].longest_word, key=len)

        # Set per-turn attributes
        self.answered = True
        self.accepting_answers = False

    async def send_post_turn_message(self, word: str) -> None:
        text = f"_{word.capitalize()}_ is accepted.\n\n"
        # Reduce limits if possible every set number of turns
        if self.turns % GameSettings.TURNS_BETWEEN_LIMITS_CHANGE == 0:
            if self.time_limit > GameSettings.MIN_TURN_SECONDS:
                self.time_limit -= GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE
                text += (
                    f"Time limit decreased from "
                    f"*{self.time_limit + GameSettings.TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE}s* "
                    f"to *{self.time_limit}s*.\n"
                )
            if self.min_letters_limit < GameSettings.MAX_WORD_LENGTH_LIMIT:
                self.min_letters_limit += GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE
                text += (
                    f"Minimum letters per word increased from "
                    f"*{self.min_letters_limit - GameSettings.WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE}* "
                    f"to *{self.min_letters_limit}*.\n"
                )
        await self.send_message(text.rstrip())

    async def running_initialization(self) -> None:
        # Random starting word
        self.current_word = get_random_word(min_len=self.min_letters_limit)
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
            "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]),
            parse_mode=types.ParseMode.HTML,
        )

    async def running_phase_tick(self) -> bool:
        # Return values
        # True: Game has ended
        # False: Game is still ongoing
        if self.answered:
            # Move player who just answered to the end of queue
            self.players_in_game.append(self.players_in_game.pop(0))
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return False

            # Timer ran out
            self.accepting_answers = False
            await self.send_message(
                f"{self.players_in_game[0].mention} ran out of time! They have been eliminated.",
                parse_mode=types.ParseMode.HTML,
            )
            del self.players_in_game[0]

            if len(self.players_in_game) == 1:
                await self.handle_game_end()
                return True

        await self.send_turn_message()
        return False

    async def handle_game_end(self) -> None:
        # Calculate game length
        self.end_time = datetime.now().replace(microsecond=0)
        td = self.end_time - self.start_time
        game_len_str = f"{int(td.total_seconds()) // 3600:02}{str(td)[-6:]}"

        winner = self.players_in_game[0].mention if self.players_in_game else "No one"
        text = f"{winner} won the game out of {len(self.players)} players!\n"
        text += f"Total words: {self.turns}\n"
        if self.longest_word:
            longest_word_sender_name = [p for p in self.players if p.user_id == self.longest_word_sender_id][0].name
            text += f"Longest word: <i>{self.longest_word.capitalize()}</i> from {longest_word_sender_name}\n"
        text += f"Game length: <code>{game_len_str}</code>"
        await self.send_message(text, parse_mode=types.ParseMode.HTML)

        del GAMES[self.group_id]

    async def update_db(self) -> None:
        async with pool.acquire() as conn:
            # Insert game instance
            await conn.execute(
                """\
                INSERT INTO game (group_id, players, game_mode, winner, start_time, end_time)
                    VALUES ($1, $2, $3, $4, $5, $6);""",
                self.group_id,
                len(self.players),
                self.__class__.__name__,
                self.players_in_game[0].user_id if self.players_in_game else None,
                self.start_time,
                self.end_time,
            )
            # Get game id
            game_id = await conn.fetchval(
                "SELECT id FROM game WHERE group_id = $1 AND start_time = $2;",
                self.group_id,
                self.start_time,
            )
        for player in self.players:  # Update db players in parallel
            asyncio.create_task(self.update_db_player(game_id, player))

    async def update_db_player(self, game_id: int, player: Player) -> None:
        async with pool.acquire() as conn:
            player_exists = bool(await conn.fetchval("SELECT id FROM player WHERE user_id = $1;", player.user_id))
            if player_exists:  # Update player in db
                await conn.execute(
                    """\
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
                    int(player in self.players_in_game),  # Support no winner in some game modes
                    player.word_count,
                    player.letter_count,
                    player.longest_word or None,
                    player.user_id,
                )
            else:  # New player, create player in db
                await conn.execute(
                    """\
                    INSERT INTO player (user_id, game_count, win_count, word_count, letter_count, longest_word)
                        VALUES ($1, 1, $2, $3, $4, $5::TEXT);""",
                    player.user_id,
                    int(player in self.players_in_game),  # No winner in some game modes
                    player.word_count,
                    player.letter_count,
                    player.longest_word or None,
                )

            # Create gameplayer in db
            await conn.execute(
                """\
                INSERT INTO gameplayer (user_id, group_id, game_id, won, word_count, letter_count, longest_word)
                    VALUES ($1, $2, $3, $4, $5, $6, $7);""",
                player.user_id,
                self.group_id,
                game_id,
                player in self.players_in_game,
                player.word_count,
                player.letter_count,
                player.longest_word or None,
            )

    async def scan_for_stale_timer(self) -> None:
        # Check if game timer is stuck
        timer = self.time_left
        for _ in range(5):
            await asyncio.sleep(1)
            if timer != self.time_left and timer >= 0:
                return  # Timer not stuck

        await send_admin_group(f"Prolonged stale/negative timer detected in group `{self.group_id}`. Game Terminated.")
        try:
            await self.send_message("Game timer is malfunctioning. Game terminated.")
        except:
            pass

        GAMES.pop(self.group_id, None)

    async def main_loop(self, message: types.Message) -> None:
        # Attempt to fix issue of stuck game with negative timer.
        negative_timer = 0
        try:
            await self.send_message(
                f"A{'n' if self.name[0] in 'aeiou' else ''} {self.name} is starting.\n"
                f"{self.min_players}-{self.max_players} players are needed.\n"
                f"{self.time_left}s to /join."
            )
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
                    # Check for prolonged negative timer
                    if self.time_left < 0:
                        negative_timer += 1
                    if negative_timer >= 5:
                        raise ValueError("Prolonged negative timer.")

                    if await self.running_phase_tick():  # True: Game ended
                        await self.update_db()
                        return
                elif self.state == GameState.KILLGAME:
                    await self.send_message("Game ended forcibly.")
                    del GAMES[self.group_id]
                    return
        except Exception as e:
            GAMES.pop(self.group_id, None)
            try:
                await self.send_message(
                    f"Game ended due to the following error:\n`{e.__class__.__name__}: {e}`.\n"
                    "My owner will be notified."
                )
            except:
                pass
            raise


class HardModeGame(ClassicGame):
    name = "hard mode game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        # Hardest settings available
        self.time_limit = GameSettings.MIN_TURN_SECONDS
        self.min_letters_limit = GameSettings.MAX_WORD_LENGTH_LIMIT


class ChaosGame(ClassicGame):
    name = "chaos game"

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
            parse_mode=types.ParseMode.HTML,
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

    async def running_phase_tick(self) -> Optional[bool]:
        if self.answered:
            # Move player who just answered to the end of queue
            self.players_in_game.append(self.players_in_game.pop(0))

            # Choose random player excluding the one who just answered and move to the start of queue
            player = self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 2))
            self.players_in_game.insert(0, player)
        else:
            self.time_left -= 1
            if self.time_left > 0:
                return

            # Timer ran out
            self.accepting_answers = False
            await self.send_message(
                f"{self.players_in_game[0].mention} ran out of time! They have been eliminated.",
                parse_mode=types.ParseMode.HTML,
            )
            del self.players_in_game[0]

            if len(self.players_in_game) == 1:
                await self.handle_game_end()
                return True  # Game has ended

            # Choose random player and move to the start of queue
            player = self.players_in_game.pop(random.randint(0, len(self.players_in_game) - 1))
            self.players_in_game.insert(0, player)

        await self.send_turn_message()
        return False  # Game is still ongoing


class ChosenFirstLetterGame(ClassicGame):
    name = "chosen first letter game"

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
            # self.current_word[-1] == self.current_word, code reuse go brrr
            await self.vp_answer()

    async def running_initialization(self) -> None:
        # Instead of storing the last used word like in other game modes,
        # self.current_word stores in the chosen first letter which is constant throughout the game
        self.current_word = random.choice(ascii_lowercase)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            f"The chosen first letter is <i>{self.current_word.upper()}</i>.\n\n"
            "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]),
            parse_mode=types.ParseMode.HTML,
        )


class BannedLettersGame(ClassicGame):
    name = "banned letters game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        self.banned_letters = []

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention} (Next: {self.players_in_game[1].name})\n"
                f"Your word must start with <i>{self.current_word[-1].upper()}</i>, "
                f"<b>exclude</b> <i>{', '.join(c.upper() for c in self.banned_letters)}</i> and "
                f"include <b>at least {self.min_letters_limit} "
                f"letter{'' if self.min_letters_limit == 1 else 's'}</b>.\n"
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

    def get_random_valid_answer(self) -> Optional[str]:
        return get_random_word(
            min_len=self.min_letters_limit,
            starting_letter=self.current_word[-1],
            banned_letters=self.banned_letters,
            exclude_words=self.used_words,
        )

    async def additional_answer_checkers(self, word: str, message: types.Message) -> bool:
        used_banned_letters = sorted(set(word) & set(self.banned_letters))
        if used_banned_letters:
            await message.reply(
                f"_{word.capitalize()}_ contains banned letters "
                f"({', '.join(c.upper() for c in used_banned_letters)})."
            )
            return False
        return True

    def set_banned_letters(self) -> None:
        self.banned_letters.clear()  # Mode may occur multiple times in mixed elimination

        # Set banned letters (maximum one vowel)
        alphabets = list(ascii_lowercase)
        for _ in range(random.randint(2, 4)):
            self.banned_letters.append(random.choice(alphabets))
            if self.banned_letters[-1] in "aeiou":
                alphabets = [c for c in alphabets if c not in "aeiou"]
            else:
                alphabets.remove(self.banned_letters[-1])
        self.banned_letters.sort()

    async def running_initialization(self) -> None:
        self.set_banned_letters()

        # Random starting word
        self.current_word = get_random_word(
            min_len=self.min_letters_limit,
            banned_letters=self.banned_letters,
        )
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            f"The first word is <i>{self.current_word.capitalize()}</i>.\n"
            f"Banned letters: <i>{', '.join(c.upper() for c in self.banned_letters)}</i>\n\n"
            "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]),
            parse_mode=types.ParseMode.HTML,
        )


class RequiredLetterGame(ClassicGame):
    name = "required letter game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        # Answer must contain required letter.
        # Required letter cannot be the ending letter of self.current_word so as to annoy the player.
        self.required_letter = None  # Changes every turn

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
            parse_mode=types.ParseMode.HTML,
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
            starting_letter=self.current_word[-1],
            required_letter=self.required_letter,
            exclude_words=self.used_words,
        )

    async def additional_answer_checkers(self, word: str, message: types.Message) -> bool:
        if self.required_letter not in word:
            await message.reply(f"_{word.capitalize()}_ does not include _{self.required_letter}_.")
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
            f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
            "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game]),
            parse_mode=types.ParseMode.HTML,
        )


class EliminationGame(ClassicGame):
    name = "elimination game"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)

        # Elimination game settings
        self.min_players = GameSettings.SPECIAL_GAME_MIN_PLAYERS
        self.max_players = GameSettings.SPECIAL_GAME_MAX_PLAYERS
        self.time_left = GameSettings.SPECIAL_GAME_INITIAL_JOINING_PHASE_SECONDS
        self.time_limit = GameSettings.FIXED_TURN_SECONDS
        # No minimum letters limit (though a word must contain at least one letter by definition)
        # Since answering words with few letters will eventually lead to elimination
        self.min_letters_limit = 1

        # Elimination game attributes
        self.round = 1
        self.turns_until_elimination = 0
        self.exceeded_score_limit = False  # Remind players that there is a turn score increment ceiling

    async def forcejoin(self, message: types.Message):
        # Joining in the middle of an elimination game puts one at a disadvantage since points are cumulative
        if self.state == GameState.JOINING:
            await super().forcejoin(message)

    def get_leaderboard(self, show_player: Optional[Player] = None) -> str:
        # nightmare nightmare nightmare nightmare

        # Make a copy of players in game
        players = self.players_in_game[:]
        # Sort by letter count descending then user id ascending
        # The user id part is to ensure consistent ordering of players with same letter count
        players.sort(key=lambda k: (-k.score, k.user_id))
        text = ""

        if not show_player:
            # Show every player
            for i, p in enumerate(players, start=1):
                text += f"{i}. {p.name}: {p.score}\n"
            return text.rstrip()

        # Highlight player (while showing 10 other players at max)
        if len(players) <= 10:
            # Show every player
            for i, p in enumerate(players, start=1):
                line = f"{i}. {p.name}: {p.score}\n"
                if p is show_player:
                    line = "> " + line
                text += line
        elif players.index(show_player) <= 4 or players.index(show_player) >= len(players) - 5:
            # Player is in first or last 5 places, show those places
            for i, p in enumerate(players[:5], start=1):
                line = f"{i}. {p.name}: {p.score}\n"
                if p is show_player:
                    line = "> " + line
                text += line
            text += "...\n"
            for i, p in enumerate(players[-5:], start=len(players) - 4):
                line = f"{i}. {p.name}: {p.score}\n"
                if p is show_player:
                    line = "> " + line
                text += line
        else:
            # Player not in first or last 5 places, show player in middle
            for i, p in enumerate(players[:5], start=1):
                text += f"{i}. {p.name}: {p.score}\n"
            # Prevent awkward ellipses if player is 6th place from top or bottom
            if players[5] is not show_player:
                text += "...\n"
            text += f"> {players.index(show_player) + 1}. {show_player.name}: {show_player.score}\n"
            if players[-6] is not show_player:
                text += "...\n"
            for i, p in enumerate(players[-5:], start=len(players) - 4):
                text += f"{i}. {p.name}: {p.score}\n"
        return text.rstrip()

    async def send_turn_message(self) -> None:
        await self.send_message(
            (
                f"Turn: {self.players_in_game[0].mention}"
                # Do not show next player on queue if this is last turn of the round
                # Since they could be eliminated
                + (f" (Next: {self.players_in_game[1].name})\n" if self.turns_until_elimination > 1 else "\n")
                + f"Your word must start with <i>{self.current_word[-1].upper()}</i>.\n"
                  f"You have <b>{self.time_limit}s</b> to answer.\n\n"
                  "Leaderboard:\n" + self.get_leaderboard(show_player=self.players_in_game[0])
            ),
            parse_mode=types.ParseMode.HTML,
        )

        # Reset per-turn attributes
        self.answered = False
        self.accepting_answers = True
        self.time_left = self.time_limit

    async def send_post_turn_message(self, word: str) -> None:
        text = f"_{word.capitalize()}_ is accepted."
        if self.exceeded_score_limit:
            text += f"\nThat is a long word! It will only count for {GameSettings.ELIM_MAX_TURN_SCORE} points."
            self.exceeded_score_limit = False
        await self.send_message(text)
        # No limit reduction

    async def running_initialization(self) -> None:
        # Random starting word
        self.current_word = get_random_word()
        self.used_words.add(self.current_word)
        self.start_time = datetime.now().replace(microsecond=0)

        await self.send_message(
            (
                f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game])
            ),
            parse_mode=types.ParseMode.HTML,
        )
        await self.handle_round_start()

    async def running_phase_tick(self) -> bool:
        if not self.answered:
            self.time_left -= 1
            if self.time_left > 0:
                return False
            self.accepting_answers = False
            await self.send_message(
                f"{self.players_in_game[0].mention} ran out of time!",
                parse_mode=types.ParseMode.HTML,
            )

        # Regardless of answering in time or running out of time
        # Elimination happens at the end of the round
        # Move player who just answered to the end of queue
        self.players_in_game.append(self.players_in_game.pop(0))
        self.turns_until_elimination -= 1

        # Handle round transition
        if self.turns_until_elimination == 0:
            await self.handle_round_end()

            if len(self.players_in_game) <= 1:
                await self.handle_game_end()
                return True

            await self.handle_round_start()

        await self.send_turn_message()
        return False

    async def handle_round_start(self) -> None:
        self.turns_until_elimination = len(self.players_in_game)

        await self.send_message(
            f"Round {self.round} is starting...\n\nLeaderboard:\n" + self.get_leaderboard(),
            parse_mode=types.ParseMode.HTML,
        )

    async def handle_round_end(self) -> None:
        # Eliminate player(s) with lowest score
        # Hence the possibility of no winners
        min_score = min(p.score for p in self.players_in_game)
        eliminated = [p for p in self.players_in_game if p.score == min_score]

        await self.send_message(
            (
                f"Round {self.round} completed.\n\nLeaderboard:\n"
                + self.get_leaderboard()
                + "\n\n"
                + ", ".join(p.mention for p in eliminated)
                + " "
                + ("is" if len(eliminated) == 1 else "are")
                + f" eliminated for having the lowest score of {min_score}."
            ),
            parse_mode=types.ParseMode.HTML,
        )

        # Update attributes
        self.players_in_game = [p for p in self.players_in_game if p not in eliminated]
        self.round += 1
        self.turns_until_elimination = len(self.players_in_game)


class MixedEliminationGame(EliminationGame):
    # Implementing this game mode was a misteak
    # self.current_word does not store the chosen first letter
    # but the whole word during ChosenFirstLetterGame here
    # for easier transition of game modes

    name = "mixed elimination game"
    game_modes = [
        ClassicGame,
        ChosenFirstLetterGame,
        BannedLettersGame,
        RequiredLetterGame,
    ]

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
                await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[0].upper()}_.")
                return
        elif not word.startswith(self.current_word[-1]):
            await message.reply(f"_{word.capitalize()}_ does not start with _{self.current_word[-1].upper()}_.")
            return

        if word in self.used_words:
            await message.reply(f"_{word.capitalize()}_ has been used.")
            return
        if not check_word_existence(word):
            await message.reply(f"_{word.capitalize()}_ is not in my list of words.")
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
            self.current_word = get_random_word(starting_letter=random.choice(ascii_lowercase))
        else:
            self.current_word = get_random_word()
        if self.game_mode is RequiredLetterGame:
            RequiredLetterGame.change_required_letter(self)
        self.used_words.add(self.current_word)

        await self.send_message(
            (
                f"The first word is <i>{self.current_word.capitalize()}</i>.\n\n"
                "Turn order:\n" + "\n".join([p.mention for p in self.players_in_game])
            ),
            parse_mode=types.ParseMode.HTML,
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
