# 📦 BoBit v2.0.0 Update

## 🆕 New Features

**Anonymous Venting System**
- `/ventpanel` - Creates vent panel with button
- Click to open anonymous vent modal
- 100% anonymous - no identity revealed
- Each vent includes button for others to vent

---

**Event Logger**
Color-coded Discord event logging:
- 🔴 **Red**: Deletions, bans, kicks, leaves
- 🟠 **Orange**: Edits, moves, timeouts
- 🟢 **Green**: Joins, unbans, creates

Events: message delete/edit, member join/leave/ban, role changes, timeouts, voice, channels, roles, invites, threads, emojis

---

**Anti-Spam Auto-Slowmode**
- Detects 5+ msgs in 15 sec → applies 5s slowmode
- Removes when traffic normalizes
- Persists through bot restarts
- Ignores channels with existing slowmode

---

**Dead Chat Reviver**
- Sends random fun message after 10+ hrs silence
- 29 unique messages
- Won't repeat until someone responds

---

## 🔧 Improvements

**Codebase Restructuring**
- UI components → `utils/ui/`
- Constants → `utils/consts.py`
- Removed all comments
- Modular structure

**Ticket System**
- Migrated to MongoDB

**Error Logging**
- Full tracebacks to file + terminal

---

## 📁 Files

**New:**
- `utils/ui/vent.py`
- `cogs/logger.py`
- `cogs/antispam.py`
- `cogs/deadchat.py`
- `cogs/vent.py`

**Modified:**
- All cogs cleaned up
- All utils reformatted
