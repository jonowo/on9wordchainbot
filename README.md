# On9 Word Chain Bot
![On9 Word Chain Bot logo](https://i.imgur.com/B4hjMC5.jpg)

(Epic icon by [@AdriTheDreamer](https://github.com/AdriTheDreamer)) 

On9 Word Chain Bot hosts games of word chain in Telegram groups.

### Statistics
- 500k+ games
- 200k+ players
- 40k+ groups

### Telegram Links
- [On9 Word Chain Bot](https://t.me/on9wordchainbot) (Live Version)
- [Official Group](https://t.me/on9wordchain)
- [Word Additions Channel](https://t.me/on9wcwa)

### Roadmap
- Module restructure
- Add support for other languages in ClassicGame
- i18n for text strings
- /forcestart voting for non-admins

## Installation

### Requirements
Python 3.7+ \
PostgreSQL 11+ \
2 Telegram bots

> It is highly recommended that you turn off privacy mode for On9 Word Chain Bot at @BotFather,
> which is on by default.
> With privacy mode on, the bot will not receive players' answers unless they reply to the bot.

### Configuration
Rename [config_format.json](config_format.json) to `config.json` and edit the constants.

Constants:
- `TOKEN`*: A Telegram bot token.
- `ON9BOT_TOKEN`*: Another Telegram bot token for virtual player bot. Can be the same as `TOKEN`.
- `DB_URI`: A PostgresSQL database URI.
  ([format](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING))
  (Won't work with other databases, why did I write raw SQL)
- `PROVIDER_TOKEN`*#: A Telegram payment provider token.
- `OWNER_ID`: Telegram user id of the bot owner.
- `ADMIN_GROUP_ID`^: Telegram group id of the bot admin group. Error messages and word requests are sent here.
- `OFFICIAL_GROUP_ID`^: Telegram group id of the official group of the bot.
- `WORD_ADDITION_CHANNEL_ID`^: Telegram channel id of the channel to announce word additions.
- `VIP`: A list of Telegram user ids of VIPs.
- `VIP_GROUP`: A list of Telegram group ids of VIP groups.

\*: Obtained via [BotFather](https://t.me/BotFather). \
\#: Optional if the payment commands are commented out.
    Bot currently uses Stripe, other payment providers may not be supported. \
^: Set them to the same throwaway group if you do not need related features.

Make sure all data is valid to prevent errors.

### Table Creation
Create the required tables in your PostgreSQL database by running [init.sql](init.sql).

### Deployment
Install dependencies with `pip install -r requirements.txt`. \
Run `python main.py`.
