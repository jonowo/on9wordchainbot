import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Any

import aiofiles
import aiofiles.os
import matplotlib.pyplot as plt
from aiocache import cached
from aiogram import Router, types, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from asyncpg import Record
from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator

from on9wordchainbot.constants import STAR
from on9wordchainbot.resources import get_pool
from on9wordchainbot.filters import IsOwner
from on9wordchainbot.utils import has_star, send_groups_only_message

router = Router(name=__name__)


@router.message(Command("stat", "stats", "stalk"))
async def cmd_stats(message: types.Message) -> None:
    rmsg = message.reply_to_message
    user = (rmsg.forward_from or rmsg.from_user) if rmsg else message.from_user

    name = user.full_name
    if await has_star(user.id):
        name += f" {STAR}"
    mention = user.mention_html(name=name)

    pool = get_pool()
    async with pool.acquire() as conn:
        res = await conn.fetchrow("SELECT * FROM player WHERE user_id = $1;", user.id)

    if not res:
        await message.reply(
            f"No statistics for {mention}!",
            parse_mode=ParseMode.HTML
        )
        return

    text = (
        f"\U0001f4ca Statistics for {mention}:\n"
        f"<b>{res['game_count']}</b> games played\n"
        f"<b>{res['win_count']} ({res['win_count'] / res['game_count']:.0%})</b> games won\n"
        f"<b>{res['word_count']}</b> total words played\n"
        f"<b>{res['letter_count']}</b> total letters played"
    )
    if res["longest_word"]:
        text += f"\nLongest word: <b>{res['longest_word'].capitalize()}</b>"
    await message.reply(text, parse_mode=ParseMode.HTML)


@router.message(Command("groupstats"))
@send_groups_only_message
async def cmd_groupstats(message: types.Message) -> None:
    # TODO: Add top players in group (max 5) to message
    pool = get_pool()
    async with pool.acquire() as conn:
        player_cnt, game_cnt, word_cnt, letter_cnt = await conn.fetchrow(
            """\
            SELECT COUNT(DISTINCT user_id), COUNT(DISTINCT game_id), SUM(word_count), SUM(letter_count)
                FROM gameplayer
                WHERE group_id = $1;""",
            message.chat.id
        )
    await message.reply(
        (
            f"\U0001f4ca Statistics for <b>{html.quote(message.chat.title)}</b>\n"
            f"<b>{player_cnt}</b> players\n"
            f"<b>{game_cnt}</b> games played\n"
            f"<b>{word_cnt}</b> total words played\n"
            f"<b>{letter_cnt}</b> total letters played"
        ),
        parse_mode=ParseMode.HTML
    )


@cached(ttl=5)
async def get_global_stats() -> str:
    pool = get_pool()

    async def get_cnt_1() -> tuple[int, int]:
        async with pool.acquire() as conn:
            group_cnt, game_cnt = await conn.fetchrow(
                "SELECT COUNT(DISTINCT group_id), COUNT(*) FROM game;"
            )
        return group_cnt, game_cnt

    async def get_cnt_2() -> tuple[int, int, int]:
        async with pool.acquire() as conn:
            player_cnt, word_cnt, letter_cnt = await conn.fetchrow(
                "SELECT COUNT(*), SUM(word_count), SUM(letter_count) FROM player;"
            )
            return player_cnt, word_cnt, letter_cnt

    get_cnt_1_task = asyncio.create_task(get_cnt_1())
    get_cnt_2_task = asyncio.create_task(get_cnt_2())
    group_cnt, game_cnt = await get_cnt_1_task
    player_cnt, word_cnt, letter_cnt = await get_cnt_2_task

    return (
        "\U0001f4ca Global statistics\n"
        f"*{group_cnt}* groups\n"
        f"*{player_cnt}* players\n"
        f"*{game_cnt}* games played\n"
        f"*{word_cnt}* total words played\n"
        f"*{letter_cnt}* total letters played"
    )


@router.message(Command("globalstats"))
async def cmd_globalstats(message: types.Message) -> None:
    await message.reply(await get_global_stats())


@router.message(IsOwner(), Command("trend", "trends"))
async def cmd_trends(message: types.Message, command: CommandObject) -> None:
    args = command.args
    try:
        days = int(args or 14)
        assert days > 1, "smh"
    except (ValueError, AssertionError) as e:
        await message.reply(f"`{e.__class__.__name__}: {str(e)}`")
        return

    t = time.time()  # Measure time used to generate graphs
    today = datetime.now().date()
    pool = get_pool()

    async def get_daily_games() -> dict[str, Any]:
        async with pool.acquire() as conn:
            return dict(
                await conn.fetch(
                    """\
                    SELECT start_time::DATE d, COUNT(start_time::DATE)
                        FROM game
                        WHERE start_time::DATE >= $1
                        GROUP BY d
                        ORDER BY d;""",
                    today - timedelta(days=days - 1)
                )
            )

    async def get_active_players() -> dict[str, Any]:
        async with pool.acquire() as conn:
            return dict(
                await conn.fetch(
                    """\
                    SELECT game.start_time::DATE d, COUNT(DISTINCT gameplayer.user_id)
                        FROM gameplayer
                        INNER JOIN game ON gameplayer.game_id = game.id
                        WHERE game.start_time::DATE >= $1
                        GROUP BY d
                        ORDER BY d;""",
                    today - timedelta(days=days - 1)
                )
            )

    async def get_active_groups() -> dict[str, Any]:
        async with pool.acquire() as conn:
            return dict(
                await conn.fetch(
                    """\
                    SELECT start_time::DATE d, COUNT(DISTINCT group_id)
                        FROM game
                        WHERE game.start_time::DATE >= $1
                        GROUP BY d
                        ORDER BY d;""",
                    today - timedelta(days=days - 1)
                )
            )

    async def get_cumulative_groups() -> dict[str, Any]:
        async with pool.acquire() as conn:
            return dict(
                await conn.fetch(
                    """\
                    SELECT *
                        FROM (
                            SELECT d, SUM(count) OVER (ORDER BY d)
                                FROM (
                                    SELECT d, COUNT(group_id)
                                        FROM (
                                            SELECT DISTINCT group_id, MIN(start_time::DATE) d
                                                FROM game
                                                GROUP BY group_id
                                        ) gd
                                        GROUP BY d
                                ) dg
                        ) ds
                        WHERE d >= $1;""",
                    today - timedelta(days=days - 1)
                )
            )

    async def get_cumulative_players() -> dict[str, Any]:
        async with pool.acquire() as conn:
            return dict(
                await conn.fetch(
                    """\
                    SELECT *
                        FROM (
                            SELECT d, SUM(count) OVER (ORDER BY d)
                                FROM (
                                    SELECT d, COUNT(user_id)
                                        FROM (
                                            SELECT DISTINCT user_id, MIN(start_time::DATE) d
                                                FROM gameplayer
                                                INNER JOIN game ON game_id = game.id
                                                GROUP BY user_id
                                        ) ud
                                        GROUP BY d
                                ) du
                        ) ds
                        WHERE d >= $1;""",
                    today - timedelta(days=days - 1)
                )
            )

    async def get_game_mode_play_cnt() -> list[Record]:
        async with pool.acquire() as conn:
            return await conn.fetch(
                """\
                SELECT COUNT(game_mode), game_mode
                    FROM game
                    WHERE start_time::DATE >= $1
                    GROUP BY game_mode
                    ORDER BY count;""",
                today - timedelta(days=days - 1)
            )

    # Execute multiple db queries at once for speed
    (
        daily_games,
        active_players,
        active_groups,
        cumulative_groups,
        cumulative_players,
        game_mode_play_cnt
    ) = await asyncio.gather(
        get_daily_games(),
        get_active_players(),
        get_active_groups(),
        get_cumulative_groups(),
        get_cumulative_players(),
        get_game_mode_play_cnt()
    )

    # Handle the possible issue of no games played in a day,
    # so there are no gaps in the cumulative graphs
    # (probably never happens)

    dt = today - timedelta(days=days)
    for i in range(days):
        dt += timedelta(days=1)
        if dt not in cumulative_groups:
            if i == 0:
                async with pool.acquire() as conn:
                    cumulative_groups[dt] = await conn.fetchval(
                        "SELECT COUNT(DISTINCT group_id) FROM game WHERE start_time::DATE <= $1;", dt
                    )
            else:
                cumulative_groups[dt] = cumulative_groups[dt - timedelta(days=1)]

    dt = today - timedelta(days=days)
    for i in range(days):
        dt += timedelta(days=1)
        if dt not in cumulative_players:
            if i == 0:
                async with pool.acquire() as conn:
                    cumulative_players[dt] = await conn.fetchval(
                        """\
                        SELECT COUNT(DISTINCT user_id)
                            FROM gameplayer
                            INNER JOIN game ON game_id = game.id
                            WHERE start_time <= $1;""",
                        dt
                    )
            else:
                cumulative_players[dt] = cumulative_players[dt - timedelta(days=1)]

    while os.path.exists("trends.jpg"):  # Another /trend command has not finished processing
        await asyncio.sleep(0.1)

    # Draw graphs

    plt.figure(figsize=(15, 8))
    plt.subplots_adjust(hspace=0.4)
    plt.suptitle(f"Trends in the Past {days} Days", size=25)

    tp = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    f = DateFormatter("%b %d" if days < 180 else "%b" if days < 335 else "%b %Y")

    sp = plt.subplot(231)
    sp.xaxis.set_major_formatter(f)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))  # Force y-axis intervals to be integral
    plt.setp(sp.xaxis.get_majorticklabels(), rotation=45, horizontalalignment="right")
    plt.title("Games Played", size=18)
    plt.plot(tp, [daily_games.get(i, 0) for i in tp])
    plt.ylim(ymin=0)

    sp = plt.subplot(232)
    sp.xaxis.set_major_formatter(f)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.setp(sp.xaxis.get_majorticklabels(), rotation=45, horizontalalignment="right")
    plt.title("Active Groups", size=18)
    plt.plot(tp, [active_groups.get(i, 0) for i in tp])
    plt.ylim(ymin=0)

    sp = plt.subplot(233)
    sp.xaxis.set_major_formatter(f)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.setp(sp.xaxis.get_majorticklabels(), rotation=45, horizontalalignment="right")
    plt.title("Active Players", size=18)
    plt.plot(tp, [active_players.get(i, 0) for i in tp])
    plt.ylim(ymin=0)

    plt.subplot(234)
    labels = [i[1] for i in game_mode_play_cnt]
    colors = [
        "dark maroon",
        "dark peach",
        "orange",
        "leather",
        "mustard",
        "teal",
        "french blue",
        "booger",
        "pink"
    ]
    total_games = sum(i[0] for i in game_mode_play_cnt)
    slices, text = plt.pie(
        [i[0] for i in game_mode_play_cnt],
        labels=[
            f"{i[0] / total_games:.1%} ({i[0]})" if i[0] / total_games >= 0.03 else ""
            for i in game_mode_play_cnt
        ],
        colors=["xkcd:" + c for c in colors[len(colors) - len(game_mode_play_cnt):]],
        startangle=90
    )
    plt.legend(slices, labels, title="Game Modes Played", fontsize="x-small", loc="best")
    plt.axis("equal")

    sp = plt.subplot(235)
    sp.xaxis.set_major_formatter(f)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.setp(sp.xaxis.get_majorticklabels(), rotation=45, horizontalalignment="right")
    plt.title("Cumulative Groups", size=18)
    plt.plot(tp, [cumulative_groups[i] for i in tp])

    sp = plt.subplot(236)
    sp.xaxis.set_major_formatter(f)
    sp.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.setp(sp.xaxis.get_majorticklabels(), rotation=45, horizontalalignment="right")
    plt.title("Cumulative Players", size=18)
    plt.plot(tp, [cumulative_players[i] for i in tp])

    # Save the plot as a jpg and send it
    plt.savefig("trends.jpg", bbox_inches="tight")
    plt.close("all")
    await message.reply_photo(types.FSInputFile("trends.jpg"), caption=f"Generation time: `{time.time() - t:.3f}s`")
    await aiofiles.os.remove("trends.jpg")
