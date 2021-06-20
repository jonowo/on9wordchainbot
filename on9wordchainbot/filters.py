from aiogram import types
from aiogram.dispatcher.filters import BoundFilter

from .constants import OWNER_ID, VIP


class OwnerFilter(BoundFilter):
    key = "is_owner"

    def __init__(self, is_owner: bool) -> None:
        self.is_owner = is_owner

    async def check(self, message: types.Message) -> bool:
        return message.from_user.id == OWNER_ID


class VIPFilter(BoundFilter):
    key = "is_vip"

    def __init__(self, is_vip: bool) -> None:
        self.is_vip = is_vip

    async def check(self, message: types.Message) -> bool:
        return message.from_user.id in VIP


class AdminFilter(BoundFilter):
    key = "is_admin"

    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin

    async def check(self, message: types.Message) -> bool:
        from . import bot

        if message.from_user.id == OWNER_ID:
            return True
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return chat_member.is_chat_admin()


class GameRunningFilter(BoundFilter):
    key = "game_running"

    def __init__(self, game_running: bool) -> None:
        self.game_running = game_running

    async def check(self, message: types.Message) -> bool:
        from . import GlobalState

        # Game running in chat implies chat is a group
        return (
            message.chat.type in (types.ChatType.GROUP, types.ChatType.SUPERGROUP)
            and message.chat.id in GlobalState.games
        )


filters = [
    OwnerFilter,
    VIPFilter,
    AdminFilter,
    GameRunningFilter
]
