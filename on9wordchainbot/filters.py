from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter
from aiogram.utils.chat_member import ADMINS

from on9wordchainbot.constants import OWNER_ID, VIP
from on9wordchainbot.resources import GlobalState


class IsOwner(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id == OWNER_ID


class IsVIP(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in VIP


class IsAdmin(Filter):
    async def __call__(self, message: types.Message) -> bool:
        if message.from_user.id == OWNER_ID:
            return True

        try:
            member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        except TelegramBadRequest as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                return False
            else:
                raise e
        else:
            return isinstance(member, ADMINS)


class HasGameInstance(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return message.chat.id in GlobalState.games


filters = [IsOwner, IsVIP, IsAdmin, HasGameInstance]
