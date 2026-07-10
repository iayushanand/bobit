# BoBit Discord Bot

A feature-rich Discord bot built for the BIT Discord server with moderation, ticketing, event logging, and community engagement features.

## Setup

### Prerequisites
- Python 3.11+
- MongoDB database
- Discord Bot Token

### Installation

1. Clone the repository
```bash
git clone https://github.com/iayushanand/BoBit.git
cd BoBit
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Create `.env` file
```env
TOKEN=your_discord_bot_token
MONGOURI=your_mongodb_connection_string
```

4. Configure channel IDs in `utils/consts.py`
```python
LOG_CHANNEL_ID = 0        # Event logging channel
WELCOME_CHANNEL_ID = 0    # Welcome messages channel
GENERAL_CHAT_ID = 0       # Dead chat monitor channel
VENT_CHANNEL_ID = 0       # Anonymous vents channel
```

5. Run the bot
```bash
python main.py
```

## Tech Stack

- **discord.py** - Discord API wrapper
- **MongoDB** - Database

## License

GNU GENERAL PUBLIC LICENSE

__NOTE__:
- Spotify and Lyrics commands is taken from [`the-coding-realm/coding-bot-v6`](https://github.com/the-coding-realm/coding-bot-v6) under [`Apache License 2.0`](https://github.com/iayushanand/coding-bot-v6/blob/master/LICENSE), the code is written and modified by [**Ayu**](https://github.com/iayushanand)
- Faculty command data is stored in [bit.json](assets/data/bit.json) and it is generated from using the scraper - [`iayushanand/BIT Scraper`](https://github.com/iayushanand/BIT-Scraper) under [`General Public License v3`](https://github.com/iayushanand/BIT-Scraper/blob/main/LICENSE), the code is written and modified by [**Ayu**](https://github.com/iayushanand)