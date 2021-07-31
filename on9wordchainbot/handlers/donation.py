import asyncio
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter, CommandStart
from aiogram.types.message import ContentTypes
from aiogram.utils.deep_linking import get_start_link
from aiogram.utils.exceptions import BadRequest

from .. import bot, dp, pool
from ..constants import PROVIDER_TOKEN
from ..utils import inline_keyboard_from_button, send_admin_group


@dp.message_handler(commands="donate")
async def cmd_donate(message: types.Message) -> None:
    if message.chat.id < 0:
        await message.reply(
            "You can only donate in private.",
            allow_sending_without_reply=True,
            reply_markup=inline_keyboard_from_button(
                types.InlineKeyboardButton("Donate in private", url=await get_start_link("donate"))
            )
        )
        return

    arg = message.get_args()
    if not arg:
        await send_donate_msg(message)
    else:
        try:
            amt = int(Decimal(arg).quantize(Decimal("1.00")) * 100)
            assert amt > 0
            await send_donate_invoice(message.chat.id, amt)
        except (ValueError, InvalidOperation, AssertionError):
            await message.reply(
                "Invalid amount.\nPlease enter a positive number.",
                allow_sending_without_reply=True
            )
        except BadRequest as e:
            if str(e) == "Currency_total_amount_invalid":
                await message.reply(
                    (
                        "Sorry, the entered amount was out of range.\n"
                        "Please enter another amount."
                    ),
                    allow_sending_without_reply=True
                )
                return
            raise


@dp.message_handler(CommandStart("donate"), ChatTypeFilter([types.ChatType.PRIVATE]))
async def send_donate_msg(message: types.Message) -> None:
    await message.reply(
        (
            "Donate to support this project! \u2764\ufe0f\n"
            "Donations are accepted in HKD (10 HKD ≈ 1.3 USD).\n"
            "Choose one of the following options or type in the desired amount in HKD (e.g. `/donate 69.69`).\n\n"
            "Donation rewards:\n"
            "Any amount: \u2b50\ufe0f is displayed next to your name\n"
            "10 HKD (cumulative): Search word list in inline queries "
            f"(e.g. `@{(await bot.me).username} test`)\n"
            "30 HKD (cumulative): Start mixed elimination games in any group (`/startmelim`)\n"
        ),
        allow_sending_without_reply=True,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton("10 HKD", callback_data="donate:10"),
                    types.InlineKeyboardButton("30 HKD", callback_data="donate:30")
                ],
                [
                    types.InlineKeyboardButton("50 HKD", callback_data="donate:50"),
                    types.InlineKeyboardButton("100 HKD", callback_data="donate:100")
                ]
            ]
        )
    )


async def send_donate_invoice(user_id: int, amt: int) -> None:
    await bot.send_invoice(
        chat_id=user_id,
        title="On9 Word Chain Bot Donation",
        description="Support bot development",
        payload=f"on9wordchainbot_donation:{user_id}",
        provider_token=PROVIDER_TOKEN,
        start_parameter="donate",
        currency="HKD",
        prices=[types.LabeledPrice("Donation", amt)]
    )


@dp.pre_checkout_query_handler()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery) -> None:
    if pre_checkout_query.invoice_payload == f"on9wordchainbot_donation:{pre_checkout_query.from_user.id}":
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Donation unsuccessful. Please try again later."
        )


@dp.message_handler(content_types=ContentTypes.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message) -> None:
    payment = message.successful_payment
    donation_id = str(uuid4())[:8]
    amt = Decimal(payment.total_amount) / 100
    dt = datetime.now().replace(microsecond=0)
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
        message.answer(
            (
                f"Your donation of {amt} HKD is successful.\n"
                "Thank you for your support! :D\n"
                f"Donation id: #on9wcbot_{donation_id}"
            ),
            parse_mode=types.ParseMode.HTML
        )
    )
    asyncio.create_task(
        send_admin_group(
            (
                f"Received donation of {amt} HKD from {message.from_user.get_mention(as_html=True)} "
                f"(id: <code>{message.from_user.id}</code>).\n"
                f"Donation id: #on9wcbot_{donation_id}"
            ),
            parse_mode=types.ParseMode.HTML
        )
    )
