from string import ascii_lowercase

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import BoundFilter

with open("token.txt") as f:
    TOKEN = f.read().strip()
bot = Bot(TOKEN, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot)
BOT_ID = int(TOKEN.partition(":")[0])
OWNER_ID = 463998526
ADMIN_GROUP_ID = -1001141544515
GAMES = {}

WORDS = {i: set() for i in ascii_lowercase}
words_li = requests.get("https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt").text.splitlines()
for i in words_li:
    WORDS[i[0]].add(i)
del words_li


class GameState:
    JOINING = 0
    RUNNING = 1
    KILLGAME = -1


class GameSettings:
    INITIAL_JOINING_PHASE_SECONDS = 60
    MAX_JOINING_PHASE_SECONDS = 180
    MAX_PLAYERS = 50
    INCREASED_MAX_PLAYERS = 300
    MIN_TURN_SECONDS = 20
    MAX_TURN_SECONDS = 40
    TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE = 5
    MIN_WORD_LENGTH_LIMIT = 3
    MAX_WORD_LENGTH_LIMIT = 10
    WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE = 1
    TURNS_BETWEEN_LIMITS_CHANGE = 5


class GroupFilter(BoundFilter):
    key = "is_group"

    def __init__(self, is_group: bool) -> None:
        self.is_group = is_group

    async def check(self, message: types.Message) -> bool:
        return message.chat.id < 0 if self.is_group else message.chat.id > 0


class OwnerFilter(BoundFilter):
    key = "is_owner"

    def __init__(self, is_owner: bool) -> None:
        self.is_owner = is_owner

    async def check(self, message: types.Message) -> bool:
        return message.from_user.id == OWNER_ID


class OwnerOrAdminFilter(BoundFilter):
    key = "is_owner_or_admin"

    def __init__(self, is_owner_or_admin: bool) -> None:
        self.is_owner_or_admin = is_owner_or_admin

    async def check(self, message: types.Message) -> bool:
        return (message.from_user.id == OWNER_ID
                or (await bot.get_chat_member(message.chat.id, message.from_user.id)).is_chat_admin())


dp.filters_factory.bind(GroupFilter)
dp.filters_factory.bind(OwnerFilter)
dp.filters_factory.bind(OwnerOrAdminFilter)
