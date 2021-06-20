import json
import logging
import os

logger = logging.getLogger(__name__)

# Load constants from config file
filename = "config_beta.json" if os.getenv("BETA") else "config.json"
logger.info("Loading constants from config file")
with open(filename) as f:
    config = json.load(f)

TOKEN = config["TOKEN"]
ON9BOT_TOKEN = config["ON9BOT_TOKEN"]
DB_URI = config["DB_URI"]
PROVIDER_TOKEN = config["PROVIDER_TOKEN"]
OWNER_ID = config["OWNER_ID"]
ADMIN_GROUP_ID = config["ADMIN_GROUP_ID"]
OFFICIAL_GROUP_ID = config["OFFICIAL_GROUP_ID"]
WORD_ADDITION_CHANNEL_ID = config["WORD_ADDITION_CHANNEL_ID"]
VIP = config["VIP"]
VIP_GROUP = config["VIP_GROUP"]

WORDLIST_SOURCE = "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt"

STAR = "\u2b50\ufe0f"


class GameState:
    JOINING = 0
    RUNNING = 1
    KILLGAME = -1


class GameSettings:
    JOINING_PHASE_SECONDS = 60
    MAX_JOINING_PHASE_SECONDS = 180
    MIN_PLAYERS = 2
    MAX_PLAYERS = 50
    INCREASED_MAX_PLAYERS = 300
    MIN_TURN_SECONDS = 20
    MAX_TURN_SECONDS = 40
    TURN_SECONDS_REDUCTION_PER_LIMIT_CHANGE = 5
    MIN_WORD_LENGTH_LIMIT = 3
    MAX_WORD_LENGTH_LIMIT = 10
    WORD_LENGTH_LIMIT_INCREASE_PER_LIMIT_CHANGE = 1
    TURNS_BETWEEN_LIMITS_CHANGE = 5

    ELIM_JOINING_PHASE_SECONDS = 90
    ELIM_MIN_PLAYERS = 5
    ELIM_MAX_PLAYERS = 30
    ELIM_INCREASED_MAX_PLAYERS = 50
    ELIM_TURN_SECONDS = 30
    ELIM_MAX_TURN_SCORE = 20
