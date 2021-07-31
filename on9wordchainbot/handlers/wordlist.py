import asyncio
import time

from aiogram import types

from .. import bot, dp, pool
from ..constants import WORD_ADDITION_CHANNEL_ID
from ..utils import check_word_existence, has_star, is_word, send_admin_group
from ..words import Words


@dp.message_handler(commands=["exist", "exists"])
async def cmd_exists(message: types.Message) -> None:
    word = message.text.partition(" ")[2].lower()
    if not word or not is_word(word):  # No proper argument given
        rmsg = message.reply_to_message
        if not rmsg or not rmsg.text or not is_word(rmsg.text.lower()):
            await message.reply(
                (
                    "Function: Check if a word is in my dictionary. "
                    "Use /reqaddword if you want to request addition of new words.\n"
                    "Usage: `/exists word`"
                ),
                allow_sending_without_reply=True
            )
            return
        word = rmsg.text.lower()

    await message.reply(
        f"_{word.capitalize()}_ is *{'' if check_word_existence(word) else 'not '}in* my dictionary.",
        allow_sending_without_reply=True
    )


@dp.message_handler(commands=["reqaddword", "reqaddwords"])
async def cmd_reqaddword(message: types.Message) -> None:
    if message.forward_from:
        return

    words_to_add = [w for w in set(message.get_args().lower().split()) if is_word(w)]
    if not words_to_add:
        await message.reply(
            (
                "Function: Request new words. Check @on9wcwa for word list updates.\n"
                "Before requesting a new word, please check that:\n"
                "- It is an English word (\u274c other languages)\n"
                "- It is spelled correctly\n"
                "- It is not a [proper noun](https://simple.wikipedia.org/wiki/Proper_noun) "
                "(\u274c names)\n"
                "  (existing proper nouns in the word list and nationalities are exempt)\n"
                "Usage: `/reqaddword word1 word2 ...`"
            ),
            disable_web_page_preview=True,
            allow_sending_without_reply=True
        )
        return

    existing = []
    rejected = []
    rejected_with_reason = []
    for w in words_to_add[:]:  # Iterate through a copy so removal of elements is possible
        if check_word_existence(w):
            existing.append("_" + w.capitalize() + "_")
            words_to_add.remove(w)

    async with pool.acquire() as conn:
        rej = await conn.fetch("SELECT word, reason FROM wordlist WHERE NOT accepted;")
    for word, reason in rej:
        if word not in words_to_add:
            continue
        words_to_add.remove(word)
        word = "_" + word.capitalize() + "_"
        if reason:
            rejected_with_reason.append((word, reason))
        else:
            rejected.append(word)

    text = ""
    if words_to_add:
        text += f"Submitted {', '.join(['_' + w.capitalize() + '_' for w in words_to_add])} for approval.\n"
        asyncio.create_task(
            send_admin_group(
                message.from_user.get_mention(
                    name=message.from_user.full_name
                         + (" \u2b50\ufe0f" if await has_star(message.from_user.id) else ""),
                    as_html=True
                )
                + " is requesting the addition of "
                + ", ".join(["<i>" + w.capitalize() + "</i>" for w in words_to_add])
                + " to the word list. #reqaddword",
                parse_mode=types.ParseMode.HTML
            )
        )
    if existing:
        text += f"{', '.join(existing)} {'is' if len(existing) == 1 else 'are'} already in the word list.\n"
    if rejected:
        text += f"{', '.join(rejected)} {'was' if len(rejected) == 1 else 'were'} rejected.\n"
    for word, reason in rejected_with_reason:
        text += f"{word} was rejected. Reason: {reason}.\n"
    await message.reply(text, allow_sending_without_reply=True)


@dp.message_handler(is_owner=True, commands=["addword", "addwords"])
async def cmd_addwords(message: types.Message) -> None:
    words_to_add = [w for w in set(message.get_args().lower().split()) if is_word(w)]
    if not words_to_add:
        await message.reply("where words", allow_sending_without_reply=True)
        return

    existing = []
    rejected = []
    rejected_with_reason = []
    for w in words_to_add[:]:  # Cannot iterate while deleting
        if check_word_existence(w):
            existing.append("_" + w.capitalize() + "_")
            words_to_add.remove(w)

    async with pool.acquire() as conn:
        rej = await conn.fetch("SELECT word, reason FROM wordlist WHERE NOT accepted;")
    for word, reason in rej:
        if word not in words_to_add:
            continue
        words_to_add.remove(word)
        word = "_" + word.capitalize() + "_"
        if reason:
            rejected_with_reason.append((word, reason))
        else:
            rejected.append(word)

    text = ""
    if words_to_add:
        async with pool.acquire() as conn:
            await conn.copy_records_to_table("wordlist", records=[(w, True, None) for w in words_to_add])
        text += f"Added {', '.join(['_' + w.capitalize() + '_' for w in words_to_add])} to the word list.\n"
    if existing:
        text += f"{', '.join(existing)} {'is' if len(existing) == 1 else 'are'} already in the word list.\n"
    if rejected:
        text += f"{', '.join(rejected)} {'was' if len(rejected) == 1 else 'were'} rejected.\n"
    for word, reason in rejected_with_reason:
        text += f"{word} was rejected. Reason: {reason}.\n"
    msg = await message.reply(text, allow_sending_without_reply=True)

    if not words_to_add:
        return

    t = time.time()
    await Words.update()
    asyncio.create_task(
        msg.edit_text(msg.md_text + f"\n\nWord list updated. Time taken: `{time.time() - t:.3f}s`")
    )
    asyncio.create_task(
        bot.send_message(
            WORD_ADDITION_CHANNEL_ID,
            f"Added {', '.join(['_' + w.capitalize() + '_' for w in words_to_add])} to the word list.",
            disable_notification=True
        )
    )


@dp.message_handler(is_owner=True, commands="rejword")
async def cmd_rejword(message: types.Message) -> None:
    arg = message.get_args()
    word, _, reason = arg.partition(" ")
    if not word:
        return

    word = word.lower()
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT accepted, reason FROM wordlist WHERE word = $1;", word)
        if r is None:
            await conn.execute(
                "INSERT INTO wordlist (word, accepted, reason) VALUES ($1, false, $2)",
                word,
                reason.strip() or None
            )

    word = word.capitalize()
    if r is None:
        await message.reply(f"_{word}_ rejected.", allow_sending_without_reply=True)
    elif r["accepted"]:
        await message.reply(f"_{word}_ was accepted.", allow_sending_without_reply=True)
    elif not r["reason"]:
        await message.reply(f"_{word}_ was already rejected.", allow_sending_without_reply=True)
    else:
        await message.reply(
            f"_{word}_ was already rejected. Reason: {r['reason']}.",
            allow_sending_without_reply=True
        )
