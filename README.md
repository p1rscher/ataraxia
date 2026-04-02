# Ataraxia Discord Bot

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)

A feature-rich Discord bot with a comprehensive XP & leveling system, voice activity tracking, and a modern web dashboard.

## ✨ Features

### 🎯 Core Features
- **Advanced XP & Leveling System** with configurable settings
- **Voice XP** with flexible requirements (AFK, deafened, muted, alone)
- **Channel & Role Multipliers** for customized XP rates
- **Automated Level Roles** assigned at specific levels
- **Real-time Leaderboards** accessible in Discord and dashboard

### 🎤 Voice Features
- **Temporary Voice Channels** - Users can create personal voice channels
- **Voice Activity Logging** - Track joins, leaves, and switches
- **Smart Session Management** - Handles bot restarts seamlessly

### 🔐 Security & Moderation
- **Reaction-Based Verification** system
- **Comprehensive Message Logging** with edit/delete tracking
- **Message Cleanup Commands** with filters

### 🤖 Automation
- **Auto-Roles** on member join
- **Parent Roles** with automatic child role assignment
- **Bump Reminders** for server promotion
- **Dynamic Stat Channels** (member count, bot count, etc.)

### 🌐 Web Dashboard
- Modern Next.js interface
- Discord OAuth authentication
- Real-time configuration changes
- Server analytics and insights

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL database (or Supabase account)
- Discord Bot Application

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ataraxia.git
   cd ataraxia/Ataraxia
   ```

2. **Install Python dependencies**
   ```bash
   pip install discord.py python-dotenv asyncpg
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and database URL
   ```

4. **Start the bot**
   ```bash
   python main.py
   ```

For detailed setup instructions, see [SETUP.md](SETUP.md).

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Complete installation and configuration guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and data flow
- **[FEATURES.md](FEATURES.md)** - Comprehensive feature list
- **[COMMANDS.md](COMMANDS.md)** - All available commands
- **[API.md](API.md)** - API reference and endpoints
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development guide and code standards

## 🎮 Commands Overview

Ataraxia uses Discord's slash command system. Here are some key commands:

```
/xp info                          - View XP settings
/xp cooldown [seconds]           - Set message XP cooldown
/multiplier channel [channel] [x] - Set channel multiplier
/voicexp-requirements view        - View voice XP requirements
/level-roles add [level] [role]  - Add level role
/leaderboard [limit]             - View server leaderboard
/tempvoice setup                 - Setup temp voice system
/verification setup              - Setup verification
```

See [COMMANDS.md](COMMANDS.md) for the complete command list.

## 🏗️ Architecture

Ataraxia consists of three main components:

1. **Discord Bot** (Python) - Handles Discord events and commands
2. **FastAPI Backend** (Python) - REST API for the dashboard
3. **Next.js Dashboard** (TypeScript) - Web interface for configuration

All components share a PostgreSQL database for data persistence.

```
Discord Bot ←→ PostgreSQL Database ←→ FastAPI Backend ←→ Next.js Dashboard
```

For details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 🌐 Dashboard

The web dashboard provides a user-friendly interface for:
- Configuring XP settings
- Managing multipliers and level roles
- Viewing leaderboards
- Configuring voice XP requirements
- Server analytics

### Starting the Dashboard

```bash
# Start FastAPI backend
cd api
uvicorn main:app --reload

# Start Next.js dashboard (in another terminal)
cd dashboard
npm install
npm run dev
```

Visit `http://localhost:3000` to access the dashboard.

## 🛠️ Development

### Adding New Features

1. Create a new cog in `cogs/`
2. Add database functions in `core/database_pg.py`
3. Add API endpoints in `api/main.py`
4. Create dashboard pages in `dashboard/app/`

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development guidelines.

### Project Structure

```
Ataraxia/
├── main.py              # Bot entry point
├── cogs/                # Discord commands
├── events/              # Event handlers
├── utils/               # Helper functions
├── core/                # Database & core logic
├── api/                 # FastAPI backend
└── dashboard/           # Next.js dashboard
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

See [DEVELOPMENT.md](DEVELOPMENT.md) for contribution guidelines.

## 📝 License

This project is licensed under the **AGPLv3 License**.

**What this means:**
- ✅ Free to use, modify, and distribute
- ✅ Can be used commercially
- ⚠️ Must disclose source code of any modifications
- ⚠️ Network use counts as distribution (AGPLv3 requirement)
- ⚠️ Must include copyright notice
- ⚠️ No warranty provided

See [LICENSE](LICENSE) for full details.

### Third-Party Licenses

This project uses open-source libraries. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for details.