import asyncio
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from aiogram import Bot, Router, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types.message import ContentType
from aiogram.utils.deep_linking import create_start_link
from aiogram.exceptions import TelegramBadRequest

from on9wordchainbot.resources import get_pool
from on9wordchainbot.constants import PROVIDER_TOKEN, STAR
from on9wordchainbot.utils import awaitable_to_coroutine, inline_keyboard_from_button, send_admin_group

router = Router(name=__name__)


@router.message(Command("donate"))
async def cmd_donate(message: types.Message, command: CommandObject) -> None:
    if message.chat.id < 0:
        start_link = await create_start_link(message.bot, "donate")
        await message.reply(
            "You can only donate in private.",
            reply_markup=inline_keyboard_from_button(
                types.InlineKeyboardButton(text="Donate in private", url=start_link)
            )
        )
        return

    args = command.args
    if not args:
        await send_donate_msg(message)
        return

    try:
        amt = int(Decimal(args).quantize(Decimal("1.00")) * 100)
        assert amt > 0
        await send_donate_invoice(message.bot, message.chat.id, amt)
    except (ValueError, InvalidOperation, AssertionError):
        await message.reply(
            "Invalid amount.\nPlease enter a positive number."
        )
    except TelegramBadRequest as e:
        if str(e) == "Currency_total_amount_invalid":
            await message.reply(
                "Sorry, the entered amount was out of range.\n"
                "Please enter another amount."
            )
            return
        raise


@router.message(CommandStart(deep_link=True, magic=F.args == "donate"), F.chat.type == ChatType.PRIVATE)
async def send_donate_msg(message: types.Message) -> None:
    bot_user = await message.bot.me()
    await message.reply(
        (
            "Donate to support this project! \u2764\ufe0f\n"
            "Donations are accepted in HKD (10 HKD ≈ 1.3 USD).\n"
            "Choose one of the following options or type in the desired amount in HKD (e.g. `/donate 69.69`).\n\n"
            "Donation rewards:\n"
            f"Any amount: {STAR} is displayed next to your name\n"
            "10 HKD (cumulative): Search word list in inline queries "
            f"(e.g. `@{bot_user.username} test`)\n"
            "30 HKD (cumulative): Start mixed elimination games in any group (`/startmelim`)\n"
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="10 HKD", callback_data="donate:10"),
                    types.InlineKeyboardButton(text="30 HKD", callback_data="donate:30")
                ],
                [
                    types.InlineKeyboardButton(text="50 HKD", callback_data="donate:50"),
                    types.InlineKeyboardButton(text="100 HKD", callback_data="donate:100")
                ]
            ]
        )
    )


async def send_donate_invoice(bot: Bot, user_id: int, amt: int) -> None:
    await bot.send_invoice(
        chat_id=user_id,
        title="On9 Word Chain Bot Donation",
        description="Support bot development",
        payload=f"on9wordchainbot_donation:{user_id}",
        provider_token=PROVIDER_TOKEN,
        start_parameter="donate",
        currency="HKD",
        prices=[types.LabeledPrice(label="Donation", amount=amt)]
    )


@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery) -> None:
    bot = pre_checkout_query.bot
    if pre_checkout_query.invoice_payload == f"on9wordchainbot_donation:{pre_checkout_query.from_user.id}":
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Donation unsuccessful. Please try again later."
        )


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message) -> None:
    payment = message.successful_payment
    donation_id = str(uuid4())[:8]
    amt = Decimal(payment.total_amount) / 100
    dt = datetime.now().replace(microsecond=0)

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """\
            INSERT INTO donation (
                donation_id, user_id, amount, donate_time,
                telegram_payment_charge_id, provider_payment_charge_id
            )
            VALUES
                ($1, $2, $3::NUMERIC, $4, $5, $6);""",
            donation_id,
            message.from_user.id,
            str(amt),
            dt,
            payment.telegram_payment_charge_id,
            payment.provider_payment_charge_id
        )

    asyncio.create_task(
        awaitable_to_coroutine(message.answer(
            (
                f"Your donation of {amt} HKD is successful.\n"
                "Thank you for your support! :D\n"
                f"Donation id: #on9wcbot_{donation_id}"
            ),
            parse_mode=ParseMode.HTML
        ))
    )
    asyncio.create_task(
        send_admin_group(
            (
                f"Received donation of {amt} HKD from {message.from_user.mention_html()} "
                f"(id: <code>{message.from_user.id}</code>).\n"
                f"Donation id: #on9wcbot_{donation_id}"
            ),
            parse_mode=ParseMode.HTML
        )
    )
