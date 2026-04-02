# Ataraxia Bot - Architecture

## 🏗️ System Architecture

Ataraxia is a multi-component Discord bot system consisting of three main parts:

```
┌─────────────────────────────────────────────────────────────┐
│                         Users                                │
└────────┬──────────────────────────────┬─────────────────────┘
         │                              │
         │ Discord                      │ Web Browser
         │                              │
    ┌────▼────────┐              ┌─────▼──────────┐
    │             │              │                 │
    │  Discord    │              │   Next.js       │
    │    Bot      │◄─────────────┤   Dashboard     │
    │  (Python)   │   REST API   │  (TypeScript)   │
    │             │              │                 │
    └────┬────────┘              └─────┬───────────┘
         │                              │
         │                              │
    ┌────▼────────┐              ┌─────▼───────────┐
    │             │              │                  │
    │   FastAPI   │◄─────────────┤   API Routes    │
    │   Backend   │              │   (Next.js)      │
    │  (Python)   │              │                  │
    │             │              │                  │
    └────┬────────┘              └──────────────────┘
         │
         │
    ┌────▼────────────────────────────────────────┐
    │                                              │
    │         PostgreSQL Database                  │
    │         (Supabase)                          │
    │                                              │
    └──────────────────────────────────────────────┘
```

## 📦 Components

### 1. Discord Bot (`main.py` + `cogs/` + `events/`)

**Technology:** Python 3.11+ with discord.py

**Responsibilities:**
- Handle Discord events (messages, voice state, reactions, etc.)
- Process slash commands
- Grant XP for messages and voice activity
- Manage temporary voice channels
- Handle verification, autoroles, level roles
- Logging (message, voice, level logs)

**Key Directories:**
- `main.py` - Bot entry point, loads cogs and starts event loop
- `cogs/` - All slash commands organized by feature
- `events/` - Event handlers (on_message, on_voice_state_update, etc.)
- `utils/` - Helper functions (XP calculation, backfill, etc.)

### 2. FastAPI Backend (`api/main.py`)

**Technology:** Python 3.11+ with FastAPI

**Responsibilities:**
- REST API for the web dashboard
- Read/write guild settings from database
- Expose XP data, leaderboards, multipliers
- Manage voice XP requirements
- Handle log channel configurations

**Base URL:** `http://localhost:8000` (development)

**Key Features:**
- Auto-generated OpenAPI docs at `/docs`
- CORS enabled for frontend communication
- Shared database connection with Discord bot

### 3. Next.js Dashboard (`dashboard/`)

**Technology:** Next.js 14+ with TypeScript, React, Tailwind CSS

**Responsibilities:**
- Web interface for server admins
- View and edit bot settings
- View leaderboards and analytics
- Discord OAuth authentication
- Real-time stats display

**Key Directories:**
- `app/` - Next.js 14 App Router pages
- `app/api/` - API route handlers (proxy to FastAPI)
- `app/dashboard/` - Dashboard pages
- `app/components/` - React components
- `app/lib/` - Utility functions and API client

### 4. PostgreSQL Database (Supabase)

**Technology:** PostgreSQL 14+

**Responsibilities:**
- Store all persistent data
- Guild settings, user XP, level roles
- Message history, voice sessions
- Multipliers, logs, verification settings

## 🔄 Data Flow

### Example: User sends a message

```
1. User sends message in Discord
   ↓
2. Discord Bot receives on_message event
   ↓
3. Check XP cooldown in database
   ↓
4. Calculate XP with multipliers
   ↓
5. Save XP to database (xp table)
   ↓
6. Check if user leveled up
   ↓
7. Send level-up message if applicable
   ↓
8. Save message to message history
```

### Example: Admin changes XP settings via Dashboard

```
1. Admin opens dashboard in browser
   ↓
2. Next.js dashboard loads settings
   ↓
3. Dashboard calls Next.js API route
   ↓
4. API route proxies to FastAPI backend
   ↓
5. FastAPI updates database
   ↓
6. Changes take effect immediately for bot
   (bot reads from same database)
```

## 🗄️ Database Schema Overview

### Core Tables

**xp** - User XP and levels per guild
- `user_id`, `guild_id`, `xp`, `level`

**xp_settings** - Guild-specific XP configuration
- `guild_id`, `message_cooldown`, `voice_interval`, `message_xp_min/max`, `voice_xp_min/max`

**voice_xp_requirements** - Voice XP conditions per guild
- `guild_id`, `require_non_afk`, `require_non_deaf`, `require_non_muted`, `require_others_in_channel`

**voice_sessions** - Active voice sessions for XP tracking
- `user_id`, `guild_id`, `channel_id`, `joined_at`, `last_xp_grant`

**xp_channel_multipliers** - Channel-specific XP multipliers
- `guild_id`, `channel_id`, `multiplier`

**xp_role_multipliers** - Role-specific XP multipliers
- `guild_id`, `role_id`, `multiplier`

**level_roles** - Roles to grant at specific levels
- `guild_id`, `level`, `role_id`

### Feature Tables

**guild_settings** - Guild configuration
- `guild_id`, `message_log_channel_id`, `level_log_channel_id`, `voice_log_channel_id`

**messages** - Message history for logging
- `message_id`, `guild_id`, `channel_id`, `author_id`, `content`, `created_at`, `edited_at`, `deleted_at`

**verification** - Verification system settings
- `guild_id`, `message_id`, `channel_id`, `role_id`

**temp_voice_settings** - Temporary voice channel system
- `guild_id`, `join_channel_id`, `category_id`

**temp_voice_channels** - Active temporary voice channels
- `channel_id`, `guild_id`, `owner_id`

**autorole_settings** - Auto-assign roles on join
- `guild_id`, `enabled`, `role_ids[]`

**parent_roles** - Parent-child role relationships
- `guild_id`, `parent_role_id`, `child_role_ids[]`

**bump_settings** - Server bump reminder
- `guild_id`, `enabled`, `bump_role_id`, `reminder_channel_id`, `last_bump_time`

**stat_channels** - Dynamic stat display channels
- `guild_id`, `channel_id`, `stat_type`

## 🔐 Security & Authentication

### Discord Bot
- Bot token stored in `.env` file (`BOT_TOKEN`)
- Never committed to version control
- Required Discord intents: `members`, `message_content`, `presences`

### FastAPI Backend
- No authentication required (runs locally or behind firewall)
- CORS configured for specific origins
- Database connection string in `.env` (`DATABASE_URL`)

### Next.js Dashboard
- Discord OAuth2 for user authentication
- NextAuth.js handles sessions
- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` in `.env.local`
- `NEXTAUTH_SECRET` for session encryption

## 🚀 Deployment Architecture

### Development (Current)
```
localhost:3000  → Next.js Dashboard
localhost:8000  → FastAPI Backend
Discord Bot     → Running in terminal
Supabase        → Cloud PostgreSQL
```

### Production (Recommended)
```
https://dashboard.yourbot.com → Next.js (Vercel/Netlify)
https://api.yourbot.com       → FastAPI (Railway/Render)
Discord Bot                   → VPS (DigitalOcean/AWS)
Supabase                      → Cloud PostgreSQL
```

## 📊 Performance Considerations

### Bot Performance
- Async/await for all I/O operations
- Connection pooling for database (5-20 connections)
- Background tasks for voice XP and stats updates
- Message backfill limited to 256 messages per guild

### API Performance
- FastAPI async endpoints
- Database connection pooling
- No caching (reads directly from database for accuracy)

### Dashboard Performance
- Server-side rendering (Next.js)
- API route caching disabled for real-time data
- Mock mode available for development without backend

## 🔧 Configuration

All configuration is managed through environment variables:

**Bot (`.env`)**
```env
BOT_TOKEN=...
DATABASE_URL=postgresql://...
GROQ_API_KEY=...
MAIN_DEV_ID=...
AI_ENABLED=true
MAX_DAILY_COST=10.0
```

**Dashboard (`dashboard/.env.local`)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK_DATA=false
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
NEXTAUTH_SECRET=...
NEXTAUTH_URL=http://localhost:3000
DISCORD_BOT_TOKEN=...
```

## 🔄 Update Flow

When updating the bot:

1. **Database Changes**: Add migrations in `database_pg.py` init_db()
2. **Bot Logic**: Update cogs/events/utils
3. **API**: Update FastAPI endpoints if needed
4. **Dashboard**: Update frontend to match new features
5. **Restart Bot**: Changes take effect immediately
6. **Test**: Use development mode with mock data first

## 📈 Monitoring & Logging

- Python logging module with timestamps
- Log levels: DEBUG, INFO, WARNING, ERROR
- Separate logs for different components
- Command usage tracked in database
- Stats exported to JSON for dashboard

## 🆘 Common Issues

**Bot can't connect to database**
- Check `DATABASE_URL` in `.env`
- Verify Supabase connection string

**Dashboard can't reach API**
- Ensure FastAPI is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Verify CORS settings in `api/main.py`

**Voice XP not working**
- Check voice sessions table for active sessions
- Verify `grant_voice_xp` background task is running
- Check voice XP requirements settings

**Commands not appearing**
- Bot needs proper intents
- Commands synced in `on_ready` event
- Check bot has application.commands scope
