from on9wordchainbot.handlers import donation, gameplay, info, misc, stats, wordlist

routers = [
    donation.router,
    gameplay.router,
    info.router,
    misc.router,
    stats.router,
    wordlist.router
]

__all__ = (
    "donation",
    "gameplay",
    "info",
    "misc",
    "stats",
    "wordlist",
    "routers"
)
