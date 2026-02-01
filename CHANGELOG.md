# Changelog

All notable changes to BoBit Discord Bot are documented in this file.

---

## [2.0.0] - 2026-02-01

### 🆕 New Features

#### Anonymous Venting System (`cogs/vent.py`)
- `/ventpanel` command creates vent panel with button
- Users click button to open anonymous vent modal
- Vents posted to configured channel with no identity revealed
- Each vent message includes button for others to vent

---

#### Event Logger (`cogs/logger.py`)
Comprehensive Discord event logging with color-coded embeds:
- **Red**: Message delete, member leave/ban, channel/role delete
- **Orange**: Message edit, nickname/role changes, timeouts
- **Green**: Member join/unban, channel/role create

Events: message delete/edit/bulk, member join/leave/ban/unban, nickname & role changes, timeouts, voice activity, channel & role management, invites, threads, emojis

---

#### Anti-Spam Auto-Slowmode (`cogs/antispam.py`)
- Detects high traffic (5+ messages in 15 seconds)
- Auto-applies 5-second slowmode
- Removes when traffic normalizes (checks every 2 min)
- Persists through bot restarts via MongoDB
- Sends embed notifications when enabled/removed

---

#### Dead Chat Reviver (`cogs/deadchat.py`)
- Monitors general chat for inactivity
- Sends random fun message after 10+ hours of silence
- 29 unique humorous messages
- Won't repeat until someone responds

---

### 🔧 Improvements

#### Codebase Restructuring
- **UI Components** moved to `utils/ui/`
- **Constants** consolidated in `utils/consts.py`
- **Removed all comments** for cleaner code
- **Modular structure** for better maintainability

#### Ticket System Migration
- Migrated from PostgreSQL to MongoDB
- Uses `insert_one`, `find_one`, `update_one`, `delete_one`

#### Error Logging
- Full tracebacks logged to file + terminal
- Command and event errors captured

---

### 📁 Project Structure

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
│   │   ├── ticket.py    # Ticket UI
│   │   └── vent.py      # Vent UI
│   ├── bot.py
│   ├── consts.py        # All constants
│   ├── database.py
│   └── logger.py
└── main.py
```

---

### 🎨 Color Scheme

- **Red** `0xED4245` - Deletions, bans, errors
- **Orange** `0xE67E22` - Edits, warnings
- **Yellow** `0xFEE75C` - Warnings (moderation)
- **Green** `0x57F287` - Success, joins

---

## Configuration

Set these values in `utils/consts.py`:
- `LOG_CHANNEL_ID`
- `WELCOME_CHANNEL_ID`
- `GENERAL_CHAT_ID`
- `VENT_CHANNEL_ID`
