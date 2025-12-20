import asyncio
import logging
from uuid import uuid4

from aiogram import Router, F, types
from aiogram.enums import ChatType
from aiogram.filters import JOIN_TRANSITION, ChatMemberUpdatedFilter, Command, CommandObject, CommandStart

from on9wordchainbot.resources import GlobalState, get_pool
from on9wordchainbot.constants import ADMIN_GROUP_ID, OFFICIAL_GROUP_ID, VIP
from on9wordchainbot.filters import IsOwner
from on9wordchainbot.handlers.donation import send_donate_invoice
from on9wordchainbot.models import GAME_MODES
from on9wordchainbot.utils import ADD_TO_GROUP_KEYBOARD, amt_donated, awaitable_to_coroutine, is_word
from on9wordchainbot.words import Words

logger = logging.getLogger(__name__)

router = Router(name=__name__)


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message) -> None:
    await message.reply(
        (
            "Hi! I host games of word chain in Telegram groups.\n"
            "Add me to a group to start playing games!"
        ),
        reply_markup=ADD_TO_GROUP_KEYBOARD
    )


@router.message(Command("feedback"))
async def cmd_feedback(message: types.Message, command: CommandObject) -> None:
    if message.forward_from:  # Avoid re-triggering on forward
        return

    args = command.args
    if not args:
        bot_user = await message.bot.me()
        await message.reply(
            "Function: Send feedback to my owner.\n"
            f"Usage: `/feedback@{bot_user.username} feedback`"
        )
        return

    asyncio.gather(
        awaitable_to_coroutine(message.forward(ADMIN_GROUP_ID)),
        awaitable_to_coroutine(message.reply("Feedback sent successfully."))
    )


@router.message(IsOwner(), Command("maintmode"))
async def cmd_maintmode(message: types.Message) -> None:
    GlobalState.maint_mode = not GlobalState.maint_mode
    await message.reply(
        f"Maintenance mode has been switched {'on' if GlobalState.maint_mode else 'off'}."
    )


@router.message(Command("leave"), IsOwner(), F.chat.type.in_((ChatType.GROUP, ChatType.SUPERGROUP)))
async def cmd_leave(message: types.Message) -> None:
    await message.chat.leave()


@router.message(IsOwner(), Command("sql"))
async def cmd_sql(message: types.Message, command: CommandObject) -> None:
    args = command.args
    if not args:
        return

    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            res = await conn.fetch(args)
    except Exception as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`")
        return

    if not res:
        await message.reply("No results returned.")
        return

    text = ["*" + " - ".join(res[0].keys()) + "*"]
    for r in res:
        text.append("`" + " - ".join(str(i) for i in r.values()) + "`")
    await message.reply("\n".join(text))


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def new_member(event: types.ChatMemberUpdated) -> None:
    bot = event.bot
    if event.new_chat_member.user.id == bot.id:  # self added to group
        await event.answer(
            "Thanks for adding me. Start a classic game with /startclassic!"
        )
    elif event.chat.id == OFFICIAL_GROUP_ID:
        await event.answer(
            "Welcome to the official On9 Word Chain group!\n"
            "Start a classic game with /startclassic!"
        )


@router.inline_query()
async def inline_handler(inline_query: types.InlineQuery) -> None:
    bot = inline_query.bot
    text = inline_query.query.lower()
    results: list[types.InlineQueryResultUnion] = []

    if not text or inline_query.from_user.id not in VIP and (await amt_donated(inline_query.from_user.id)) < 10:
        for mode in GAME_MODES:
            bot_user = await bot.me()
            command = f"/{mode.command}@{bot_user.username}"
            results.append(
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Start " + mode.name,
                    description=command,
                    input_message_content=types.InputTextMessageContent(message_text=command)
                )
            )
        await inline_query.answer(results, is_personal=not text)
        return

    if not is_word(text):
        await inline_query.answer(
            [
                types.InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="A query can only consist of alphabets",
                    description="Try a different query",
                    input_message_content=types.InputTextMessageContent(message_text=r"¯\\_(ツ)\_/¯")
                )
            ],
            is_personal=True
        )
        return

    for word in Words.dawg.iterkeys(text):
        word = word.capitalize()
        results.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title=word,
                input_message_content=types.InputTextMessageContent(message_text=word)
            )
        )
        if len(results) == 50:  # Max 50 results
            break

    if not results:  # No results
        results.append(
            types.InlineQueryResultArticle(
                id=str(uuid4()),
                title="No results found",
                description="Try a different query",
                input_message_content=types.InputTextMessageContent(message_text=r"¯\\_(ツ)\_/¯")
            )
        )

    await inline_query.answer(results, is_personal=True)


@router.callback_query()
async def callback_query_handler(callback_query: types.CallbackQuery) -> None:
    text = callback_query.data
    if text.startswith("donate"):
        await send_donate_invoice(callback_query.bot, callback_query.from_user.id, int(text.partition(":")[2]) * 100)
    await callback_query.answer()
