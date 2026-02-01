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
git clone https://github.com/yourusername/BoBit.git
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

## Project Structure

```
BoBit/
├── cogs/
│   ├── antispam.py      # Auto-slowmode
│   ├── deadchat.py      # Dead chat reviver
│   ├── leetcode_daily.py
│   ├── listeners.py     # Welcome messages
│   ├── logger.py        # Event logging
│   ├── moderation.py    # Mod commands
│   ├── ticket.py        # Ticket command
│   └── vent.py          # Vent command
├── utils/
│   ├── ui/
│   │   ├── ticket.py    # Ticket UI components
│   │   └── vent.py      # Vent UI components
│   ├── bot.py           # Bot class
│   ├── consts.py        # Constants
│   ├── database.py      # MongoDB connection
│   └── logger.py        # Console logger
├── logs/                # Log files
├── main.py              # Entry point
└── .env                 # Environment variables
```

## Commands

| Command | Description |
|---------|-------------|
| `.ticket` | Create ticket panel (Admin) |
| `/ventpanel` | Create vent panel (Admin) |
| `.kick <user> [reason]` | Kick a member |
| `.ban <user> [reason]` | Ban a member |
| `.timeout <user> <minutes> [reason]` | Timeout a member |
| `.warn <user> <reason>` | Warn a member |
| `.warns <user>` | View warnings |
| `.warnremove <user> <index>` | Remove warning |
| `.warnclear <user>` | Clear all warnings |
| `.slowmode [seconds]` | Set channel slowmode |

## Tech Stack

- **discord.py** - Discord API wrapper
- **MongoDB** - Database
- **Jishaku** - Bot debugging
- **colorama** - Colored console output

## License

MIT License
