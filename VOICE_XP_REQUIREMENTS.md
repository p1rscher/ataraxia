# Voice XP Requirements - New Features

## 🎯 Overview

I implemented a fully configurable system for Voice XP requirements. Admins can now control exactly which conditions users must meet to earn Voice XP.

## 📊 What Was Added?

### 1. **New Database Table**
- `voice_xp_requirements` - Stores the settings for each server
- 4 configuration options:
  - `require_non_afk` - Must users be non-AFK?
  - `require_non_deaf` - Must users be non-deafened?
  - `require_non_muted` - Must users be non-muted?
  - `require_others_in_channel` - Must other users be in the channel?

### 2. **New Discord Commands**
All commands are available under `/voicexp-requirements`:

- `/voicexp-requirements view` - Shows the current settings
- `/voicexp-requirements set-afk [allow]` - Allow or deny XP for AFK users
- `/voicexp-requirements set-deaf [allow]` - Allow or deny XP for deafened users
- `/voicexp-requirements set-muted [allow]` - Allow or deny XP for muted users
- `/voicexp-requirements set-alone [allow]` - Allow or deny XP when alone in a channel
- `/voicexp-requirements reset` - Reset to the default settings

### 3. **API Endpoints**
- `GET /api/guilds/{guild_id}/voicexp/requirements` - Retrieve the current settings
- `PUT /api/guilds/{guild_id}/voicexp/requirements` - Change all settings at once
- `PATCH /api/guilds/{guild_id}/voicexp/requirements` - Change a single setting

### 4. **Dashboard Integration**
- New route: `/dashboard/app/api/voicexp/requirements/route.ts`
- Supports mock mode for local development
- Ready for frontend integration

## 🔧 Technical Details

### Database Functions (database_pg.py)
```python
await db.get_voice_xp_requirements(guild_id)  # Retrieve settings
await db.set_voice_xp_requirement(guild_id, 'require_non_afk', True)  # Set one setting
await db.set_all_voice_xp_requirements(guild_id, ...)  # Set all settings at once
```

### Default Settings
- ✅ `require_non_afk` = True (AFK users do NOT earn XP)
- ✅ `require_non_deaf` = True (Deafened users do NOT earn XP)
- ❌ `require_non_muted` = False (Muted users earn XP)
- ✅ `require_others_in_channel` = True (Alone in a channel = NO XP)

### Bug Fixes Included!
The system also fixes the original bug:
- When a second person joins a channel, the first person now earns XP as well
- When someone leaves a channel and only one person remains, their session is ended
- Bots are correctly ignored
- **All voice sessions are synchronized when the bot restarts** - users who are already in voice channels automatically receive sessions

## 🚀 Usage

### As a Discord Admin:
```
1. /voicexp-requirements view
   → Shows the current settings

2. /voicexp-requirements set-alone true
   → Users now earn XP when they are alone

3. /voicexp-requirements set-deaf false
   → Deafened users no longer earn XP

4. /voicexp-requirements reset
   → Returns to the default settings
```

### As an API User:
```bash
# Retrieve settings
GET http://localhost:8000/api/guilds/123456789/voicexp/requirements

# Change a single setting
PATCH http://localhost:8000/api/guilds/123456789/voicexp/requirements
{
  "requirement": "require_non_afk",
  "value": false
}

# Change all settings
PUT http://localhost:8000/api/guilds/123456789/voicexp/requirements
{
  "require_non_afk": true,
  "require_non_deaf": true,
  "require_non_muted": false,
  "require_others_in_channel": true
}
```

## 📝 Changed Files

1. ✅ `core/database_pg.py` - New table + functions
2. ✅ `events/on_voice_state_update.py` - Bug fixes + requirements check
3. ✅ `utils/voice_xp.py` - Requirements-based XP allocation
4. ✅ `cogs/voice_xp_requirements.py` - New command cog
5. ✅ `api/main.py` - New API endpoints
6. ✅ `dashboard/app/api/voicexp/requirements/route.ts` - Dashboard route

## ✨ Next Steps

For the dashboard, you still need:
1. A frontend component for the settings
2. Integration into the XP settings page
3. Toggle switches for the 4 options

Would you like me to create those as well?
