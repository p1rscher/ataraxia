# Ataraxia Bot - Setup Guide

## 📋 Prerequisites

Before setting up Ataraxia, make sure you have:

- **Python 3.11 or higher** - [Download here](https://www.python.org/downloads/)
- **Node.js 18+ and npm** - [Download here](https://nodejs.org/)
- **PostgreSQL Database** - We recommend [Supabase](https://supabase.com/) (free tier available)
- **Discord Bot Application** - [Create one here](https://discord.com/developers/applications)
- **Git** - [Download here](https://git-scm.com/)

## 🤖 Step 1: Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to "Bot" tab and click "Add Bot"
4. **Important:** Enable these Privileged Gateway Intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent
5. Copy your Bot Token (keep it secret!)
6. Go to "OAuth2" → "URL Generator"
7. Select scopes: `bot` and `applications.commands`
8. Select bot permissions (recommended: Administrator for full functionality)
9. Copy the generated URL and use it to invite the bot to your server

## 🗄️ Step 2: Setup Database

### Option A: Supabase (Recommended for beginners)

1. Go to [Supabase](https://supabase.com/) and create an account
2. Create a new project
3. Go to "Settings" → "Database"
4. Copy your connection string (starts with `postgresql://`)
5. The format should be:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
   ```

### Option B: Local PostgreSQL

1. Install PostgreSQL on your machine
2. Create a database: `createdb ataraxia`
3. Your connection string will be:
   ```
   postgresql://username:password@localhost:5432/ataraxia
   ```

## 📥 Step 3: Clone Repository

```bash
git clone https://github.com/yourusername/ataraxia.git
cd ataraxia/Ataraxia
```

## 🔧 Step 4: Setup Discord Bot

### 4.1 Install Python Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install discord.py python-dotenv asyncpg
```

### 4.2 Configure Environment Variables

Create a `.env` file in the `Ataraxia` directory:

```env
# Discord Bot Token
BOT_TOKEN=your_bot_token_here

# Database Connection
DATABASE_URL=postgresql://your_connection_string_here

# AI Features (Optional - for AI commands)
GROQ_API_KEY=your_groq_api_key_here
AI_ENABLED=true
MAX_DAILY_COST=10.0

# Developer ID (for admin commands)
MAIN_DEV_ID=your_discord_user_id
```

### 4.3 Start the Bot

```bash
python main.py
```

You should see:
```
✅ Loaded extension: cogs.about
✅ Loaded extension: cogs.admin_stats
...
📦 Loaded 20 cogs (0 failed)
Starting bot...
Logged in as YourBotName (id=123456789)
on_ready: Startup completed - bot is now fully ready!
```

## 🌐 Step 5: Setup FastAPI Backend

### 5.1 Install API Dependencies

```bash
cd api
pip install fastapi uvicorn
```

### 5.2 Start the API

```bash
# From the api/ directory
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or run from the Ataraxia root directory:
```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## 📊 Step 6: Setup Next.js Dashboard

### 6.1 Install Dashboard Dependencies

```bash
cd dashboard
npm install
```

### 6.2 Configure Dashboard Environment

Create `dashboard/.env.local`:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK_DATA=false

# Discord OAuth
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret

# NextAuth
NEXTAUTH_SECRET=generate_a_random_secret_here
NEXTAUTH_URL=http://localhost:3000

# Bot Token (for API calls)
DISCORD_BOT_TOKEN=your_bot_token_here
```

**How to get Discord OAuth credentials:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application
3. Go to "OAuth2" tab
4. Copy Client ID and Client Secret
5. Add redirect URL: `http://localhost:3000/api/auth/callback/discord`

**Generate NEXTAUTH_SECRET:**
```bash
openssl rand -base64 32
```

### 6.3 Start the Dashboard

```bash
npm run dev
```

The dashboard will be available at: http://localhost:3000

## ✅ Step 7: Verify Everything Works

### Test Bot
1. Go to your Discord server
2. Try a command: `/about` or `/voicexp-requirements view`
3. Check console for logs

### Test API
1. Visit http://localhost:8000/docs
2. Try the `/health` endpoint
3. Try getting XP settings: `/api/guilds/{your_guild_id}/xp/settings`

### Test Dashboard
1. Visit http://localhost:3000
2. Click "Login with Discord"
3. Select your server
4. Navigate through the dashboard pages

## 🚀 Running All Components

You'll need **3 terminal windows** running:

**Terminal 1 - Discord Bot:**
```bash
cd Ataraxia
python main.py
```

**Terminal 2 - FastAPI Backend:**
```bash
cd Ataraxia/api
uvicorn main:app --reload
```

**Terminal 3 - Next.js Dashboard:**
```bash
cd Ataraxia/dashboard
npm run dev
```

## 🔍 Troubleshooting

### Bot won't start

**Error: `BOT_TOKEN not found`**
- Check your `.env` file exists in the `Ataraxia` directory
- Make sure it contains `BOT_TOKEN=...`

**Error: `DATABASE_URL not found`**
- Add `DATABASE_URL` to your `.env` file
- Verify the connection string is correct

**Error: `asyncpg` module not found**
- Install dependencies: `pip install asyncpg`

### API won't start

**Error: `Port 8000 already in use`**
- Stop any other processes using port 8000
- Or use a different port: `uvicorn main:app --port 8001`

**Error: Can't connect to database**
- Verify `DATABASE_URL` in `.env` is correct
- Check if database is accessible (Supabase project is running)

### Dashboard won't start

**Error: `Cannot find module`**
- Run `npm install` in the dashboard directory

**Error: `NEXTAUTH_SECRET is required`**
- Add all required environment variables to `.env.local`
- Make sure `.env.local` is in the `dashboard/` directory

**Error: Cannot reach API**
- Verify FastAPI is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Try mock mode: set `NEXT_PUBLIC_USE_MOCK_DATA=true`

### Voice XP not working

**Users not getting XP in voice**
- Check if users meet voice XP requirements
- Use `/voicexp-requirements view` to see settings
- Check console logs for voice session creation

**Bot restart issues**
- Voice sessions are synced on startup automatically
- Check logs for "Voice session sync complete"

## 🎯 Quick Start (All in One)

If you want to start all components at once, create a `start.bat` (Windows) or `start.sh` (Linux/Mac):

**Windows (`start.bat`):**
```batch
@echo off
start cmd /k "cd Ataraxia && python main.py"
start cmd /k "cd Ataraxia\api && uvicorn main:app --reload"
start cmd /k "cd Ataraxia\dashboard && npm run dev"
```

**Linux/Mac (`start.sh`):**
```bash
#!/bin/bash
cd Ataraxia && python main.py &
cd Ataraxia/api && uvicorn main:app --reload &
cd Ataraxia/dashboard && npm run dev &
```

## 📦 Production Deployment

For production deployment, see:
- [Railway](https://railway.app/) for bot + API
- [Vercel](https://vercel.com/) for Next.js dashboard
- [DigitalOcean](https://www.digitalocean.com/) for VPS hosting

Production considerations:
- Use proper process managers (PM2, systemd)
- Enable SSL/TLS certificates
- Set up monitoring and logging
- Use environment-specific configs
- Enable CORS only for your domain
- Regular database backups

## 🆘 Need Help?

- Check the logs in the console
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
- Review [DEVELOPMENT.md](DEVELOPMENT.md) for development guide
- Open an issue on GitHub
