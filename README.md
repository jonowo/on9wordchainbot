# On9 Word Chain Bot
![On9 Word Chain Bot logo](https://i.imgur.com/B4hjMC5.jpg)

(Epic icon by [@AdriTheDreamer](https://github.com/AdriTheDreamer)) 

On9 Word Chain Bot hosts games of word chain in Telegram groups.

### Telegram Links
- [On9 Word Chain Bot](https://t.me/on9wordchainbot) (Live Version)
- [Official Group](https://t.me/on9wordchain)
- [Word Additions Channel](https://t.me/on9wcwa)

### Roadmap
- Make required letter game more reasonable
- Group leaderboard
- Hyphenated words?
- Switch from Markdown to HTML completely
- Add support for other languages in ClassicGame
- i18n for text strings

## Installation

### Requirements
Python 3.7+ \
PostgreSQL 11+ \
2 Telegram bots

> It is highly recommended that you turn off privacy mode for On9 Word Chain Bot via @BotFather,
> which is on by default. Otherwise, leaving privacy mode on, the bot will only receive players'
> answers when they reply to the bot.

### Configuration
Rename [config_format.json](config_format.json) to `config.json` and edit the following constants:

- `TOKEN`*: A Telegram bot token.
- `ON9BOT_TOKEN`*: Another Telegram bot token for the virtual player bot. Can be the same as `TOKEN`.
- `DB_URI`: A [PostgresSQL database URI](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING).
- `PROVIDER_TOKEN`*#: A Telegram payment provider token.
- `OWNER_ID`: Telegram user id of the bot owner.
- `ADMIN_GROUP_ID`^: Telegram group id of the bot admin group. Error messages and word addition requests are sent here.
- `OFFICIAL_GROUP_ID`^: Telegram group id of the official group of the bot.
- `WORD_ADDITION_CHANNEL_ID`^: Telegram channel id of the channel to announce word additions.
- `VIP`: A list of Telegram user ids designated as VIPs.
- `VIP_GROUP`: A list of Telegram group ids designated as VIP groups.

\*: Obtained via [BotFather](https://t.me/BotFather). \
\#: Optional if payment-related functions are commented out. \
^: Set to the same throwaway group if these features are not used.

### Table Creation
Create the required tables in your PostgreSQL database by running [init.sql](init.sql).

### Deployment
Install and update dependencies with `pip install -U -r requirements.txt`. \
Run `python -m on9wordchainbot`.
