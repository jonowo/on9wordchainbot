# On9 Word Chain Bot
![On9 Word Chain Bot logo](https://i.imgur.com/B4hjMC5.jpg)

(Epic icon by @AdriTheDreamer) 

On9 Word Chain Bot hosts games of word chain in Telegram groups.

Statistics:
- 380k+ games
- 140k+ players
- 36k+ groups

Links:
- [On9 Word Chain Bot](https://t.me/on9wordchainbot) (Live Version)
- [Official Group](https://t.me/on9wordchain)
- [Word Additions Channel](https://t.me/on9wcwa)

## Installation

### Requirements
Python 3.7+
PostgreSQL 11+

### Configuration
Create `config.json` in the format described in [config_format.json](config_format.json).

Constants:
- `TOKEN`*: A Telegram bot token.
- `ON9BOT_TOKEN`*: Another Telegram bot token for virtual player bot. Can be the same as `TOKEN`.
- `DB_URI`: A PostresSQL database URI.
  ([format](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING))
  (Won't work with other databases, why did I write raw SQL)
- `PROVIDER_TOKEN`*#: A Telegram payment provider token.
- `OWNER_ID`: Telegram user id of the bot owner.
- `ADMIN_GROUP_ID`^: Telegram group id of the bot admin group. Error messages and word requests are sent here.
- `OFFICIAL_GROUP_ID`^: Telegram group id of the offical group of the bot.
- `WORD_ADDITION_CHANNEL_ID`^: Telegram channel id of the channel to announce word additions.
- `VIP`: A list of Telegram user ids of VIPs.
- `VIP_GROUP`: A list of Telegram group ids of VIP groups.

\*: Obtained by contacting [BotFather](https://t.me/BotFather).

\#: Optional if the payment commands are removed.
    Bot currently uses Stripe, other payment providers may not be supported.

^: Set all of these to the same group id for ultimate laziness.

Make sure all of the data is valid to prevent errors.

### Table Creation
Create the required tables in your PostgreSQL database by running [init.sql](init.sql).

### Deployment
Install the dependencies with `pip install -r requirements.txt`.

Run `python main.py`.
