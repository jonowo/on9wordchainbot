import asyncio
import traceback

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.exceptions import (TelegramBadRequest, TelegramForbiddenError, TelegramMigrateToChat,
                                TelegramRetryAfter, TelegramAPIError, TelegramUnauthorizedError)

from on9wordchainbot.resources import GlobalState, get_pool
from on9wordchainbot.constants import GameState
from on9wordchainbot.utils import awaitable_to_coroutine, send_admin_group


async def error_handler(event: types.ErrorEvent) -> None:
    update = event.update
    error = event.exception

    if update is not None:
        if update.message is not None and update.message.chat is not None:
            group_id = update.message.chat.id
            if group_id in GlobalState.games:
                asyncio.create_task(GlobalState.games[group_id].scan_for_stale_timer())

        # TODO: let's get these errors sent to the admin group for now, revisit later
        # if isinstance(error, TelegramBadRequest) and str(error) in (
        #     "Have no rights to send a message",
        #     "Not enough rights to send text messages to the chat",
        #     "Group chat was deactivated",
        #     "Chat_write_forbidden",
        #     "Channel_private"
        # ):
        #     return
        # if isinstance(error, TelegramUnauthorizedError):
        #     if str(error).startswith("Forbidden: bot is not a member"):
        #         return
        #     if str(error).startswith("Forbidden: bot was kicked"):
        #         return
        # if str(error).startswith("Internal Server Error: sent message was immediately deleted"):
        #     return

        if isinstance(error, TelegramMigrateToChat):  # TODO: Test
            # Migrate group running game and statistics
            if group_id in GlobalState.games:
                GlobalState.games[error.migrate_to_chat_id] = GlobalState.games.pop(group_id)
                GlobalState.games[error.migrate_to_chat_id].group_id = error.migrate_to_chat_id
                asyncio.create_task(
                    awaitable_to_coroutine(send_admin_group(f"Game moved from {group_id} to {error.migrate_to_chat_id}."))
                )

            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE game SET group_id = $1 WHERE group_id = $2;",
                    error.migrate_to_chat_id, group_id
                )
                await conn.execute(
                    "UPDATE gameplayer SET group_id = $1 WHERE group_id = $2;",
                    error.migrate_to_chat_id, group_id
                )

            await send_admin_group(f"Group statistics migrated from {group_id} to {error.migrate_to_chat_id}.")
            return

        send_admin_msg = await send_admin_group(
            (
                f"<code>{error.__class__.__name__} @ "
                f"{group_id if update.message and update.message.chat else 'idk'}</code>:\n"
                f"<pre>{str(error)}</pre>"
            ) if isinstance(error, TelegramRetryAfter) else (
                "<pre>"
                + "".join(traceback.format_exception(error))
                + f"@ {group_id if update.message and update.message.chat else 'idk'}</pre>"
            ),
            parse_mode=ParseMode.HTML
        )
        if update.message and update.message.chat:
            asyncio.create_task(
                awaitable_to_coroutine(update.message.reply(
                    f"Error occurred (`{error.__class__.__name__}`). My owner has been notified."
                ))
            )

            if group_id in GlobalState.games:
                asyncio.create_task(
                    awaitable_to_coroutine(send_admin_msg.reply(f"Killing game in {group_id} consequently."))
                )
                GlobalState.games[group_id].state = GameState.KILLGAME
                await asyncio.sleep(2)

                # If game is still not terminated
                if group_id in GlobalState.games:
                    del GlobalState.games[group_id]
                    await update.message.reply("Game ended forcibly.")
    else:  # TODO: update is None, what to do?
        pass

    raise error from None
