# Ataraxia Bot - Development Guide

## 🛠️ Development Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or Supabase account)
- Git
- Code editor (VS Code recommended)

### Recommended VS Code Extensions
- Python
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- GitLens

### Initial Setup

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate venv:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Install Python dependencies: `pip install -r requirements.txt`
5. Install dashboard dependencies: `cd dashboard && npm install`
6. Copy `.env.example` to `.env` and configure
7. Copy `dashboard/.env.example` to `dashboard/.env.local` and configure

---

## 📁 Project Structure

```
Ataraxia/
├── main.py                 # Bot entry point
├── .env                    # Environment variables (not in git)
├── requirements.txt        # Python dependencies
│
├── cogs/                   # Discord commands (slash commands)
│   ├── __init__.py
│   ├── about.py           # /about command
│   ├── xp_settings.py     # /xp and /multiplier commands
│   ├── voice_xp_requirements.py  # /voicexp-requirements commands
│   ├── level_roles.py     # /level-roles commands
│   ├── autorole.py        # /autorole commands
│   ├── parent_roles.py    # /parent-role commands
│   ├── verification.py    # /verification commands
│   ├── temp_voice.py      # /tempvoice commands
│   ├── log_config.py      # /log-config commands
│   ├── serverstats.py     # /serverstats command
│   ├── counting.py        # /counting commands
│   ├── cleanup_channel.py # /cleanup-channel command
│   ├── ai.py              # /ask and /clear-history commands
│   ├── math.py            # /math commands
│   ├── say.py             # /say command
│   ├── insights.py        # /insights command
│   ├── admin_stats.py     # /admin-stats command
│   ├── premium.py         # /premium commands (planned)
│   ├── bump_reminder.py   # /bump commands
│   ├── hello.py           # /hello command
│   ├── fun.py             # Fun commands
│   └── shutdown.py        # /shutdown command (dev only)
│
├── events/                 # Discord event handlers
│   ├── on_ready.py        # Bot startup
│   ├── on_message.py      # Message events for XP
│   ├── on_message_edit.py # Message edit logging
│   ├── on_message_delete.py # Message delete logging
│   ├── on_raw_message_edit.py # Raw edit events
│   ├── on_raw_message_delete.py # Raw delete events
│   ├── on_raw_reaction_add.py # Verification reactions
│   ├── on_voice_state_update.py # Voice XP & temp channels
│   ├── on_member_join.py  # Auto-roles & logging
│   ├── on_member_update.py # Parent role assignments
│   ├── on_guild_join.py   # New guild setup
│   ├── on_interaction.py  # Interaction logging
│   └── on_app_command_completion.py # Command usage tracking
│
├── utils/                  # Helper functions
│   ├── __init__.py
│   ├── voice_xp.py        # Voice XP granting loop
│   ├── xp_calculator.py   # XP calculation & level-up checks
│   ├── backfill.py        # Message history backfill
│   ├── process_missed_verifications.py # Verification sync
│   ├── sync_voice_sessions.py # Voice session sync on startup
│   ├── stats_updater.py   # Stats JSON export
│   ├── process_lock.py    # Single-instance lock
│   ├── close.py           # Graceful shutdown
│   ├── embeds.py          # Embed helpers
│   └── diff.py            # Message diff for logging
│
├── core/                   # Core functionality
│   ├── database_pg.py     # Database functions (PostgreSQL)
│   └── data/              # Static data files
│
├── api/                    # FastAPI backend
│   ├── main.py            # API entry point
│   ├── requirements.txt   # API dependencies
│   └── README.md
│
└── dashboard/              # Next.js dashboard
    ├── app/               # App Router pages
    │   ├── page.tsx       # Home page
    │   ├── layout.tsx     # Root layout
    │   ├── api/           # API routes (proxy to FastAPI)
    │   ├── dashboard/     # Dashboard pages
    │   ├── components/    # React components
    │   ├── contexts/      # React contexts
    │   └── lib/           # Utilities & API client
    ├── public/            # Static assets
    ├── types/             # TypeScript types
    ├── .env.local         # Environment variables (not in git)
    ├── package.json
    ├── tsconfig.json
    └── next.config.ts
```

---

## 🔨 Adding New Features

### Adding a New Slash Command

1. **Create a new cog file** in `cogs/`

```python
# cogs/my_feature.py
import discord
from discord import app_commands
from discord.ext import commands
from core import database_pg as db

class MyFeature(commands.Cog):
    """Description of your feature"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="mycommand", description="What it does")
    @app_commands.checks.has_permissions(administrator=True)
    async def my_command(self, interaction: discord.Interaction):
        """Command implementation"""
        await interaction.response.send_message("Hello!")

async def setup(bot):
    await bot.add_cog(MyFeature(bot))
```

2. **Restart the bot** - The cog will be auto-loaded
3. **Test the command** in Discord: `/mycommand`

### Adding a Command Group

```python
my_group = app_commands.Group(
    name="mygroup",
    description="Group description"
)

@my_group.command(name="subcommand", description="Subcommand description")
async def my_subcommand(self, interaction: discord.Interaction):
    await interaction.response.send_message("Subcommand!")
```

Usage: `/mygroup subcommand`

### Adding Database Functions

Add to `core/database_pg.py`:

```python
async def my_database_function(guild_id: int):
    """Get something from database"""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM my_table WHERE guild_id = $1
        """, guild_id)
        return row
```

### Adding a New Event Handler

1. **Create event file** in `events/`

```python
# events/on_my_event.py
import discord
from core import database_pg as db

# Bot reference to be set from main.py
bot = None

async def on_my_event(param):
    """Handle my event"""
    # Your logic here
    pass
```

2. **Register in main.py**

```python
from events import on_my_event

bot.event(on_my_event.on_my_event)
on_my_event.bot = bot
```

### Adding API Endpoints

Add to `api/main.py`:

```python
@app.get("/api/guilds/{guild_id}/my-endpoint")
async def get_my_data(guild_id: int):
    """Get my data"""
    data = await db.my_database_function(guild_id)
    return {"data": data}

@app.put("/api/guilds/{guild_id}/my-endpoint")
async def update_my_data(guild_id: int, data: MyModel):
    """Update my data"""
    await db.update_my_data(guild_id, data)
    return {"success": True}
```

### Adding Dashboard Pages

1. **Create API route** in `dashboard/app/api/`

```typescript
// dashboard/app/api/my-data/route.ts
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const guildId = searchParams.get('guildId');
  
  const response = await fetch(
    `${API_BASE_URL}/api/guilds/${guildId}/my-endpoint`
  );
  
  const data = await response.json();
  return NextResponse.json(data);
}
```

2. **Create page** in `dashboard/app/dashboard/`

```tsx
// dashboard/app/dashboard/my-page/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useServer } from '@/app/contexts/ServerContext';

export default function MyPage() {
  const { selectedServer } = useServer();
  const [data, setData] = useState(null);
  
  useEffect(() => {
    if (selectedServer) {
      fetch(`/api/my-data?guildId=${selectedServer}`)
        .then(res => res.json())
        .then(setData);
    }
  }, [selectedServer]);
  
  return (
    <div>
      <h1>My Feature</h1>
      {/* Your UI here */}
    </div>
  );
}
```

---

## 🗄️ Database Management

### Creating New Tables

Add table creation in `database_pg.py` `init_db()`:

```python
await conn.execute("""
    CREATE TABLE IF NOT EXISTS my_table (
        id SERIAL PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        data TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
""")
```

### Adding Columns (Migration)

```python
try:
    await conn.execute("""
        ALTER TABLE my_table 
        ADD COLUMN IF NOT EXISTS new_column TEXT
    """)
except Exception as e:
    logger.debug(f"Column might already exist: {e}")
```

### Best Practices

- Always use parameterized queries (`$1`, `$2`, etc.)
- Use connection pooling (`async with _pool.acquire()`)
- Handle exceptions properly
- Add indexes for frequently queried columns
- Use `IF NOT EXISTS` for table creation
- Document complex queries

---

## 🧪 Testing

### Manual Testing

1. **Use a test Discord server**
2. **Test each command** with various inputs
3. **Check database** for correct data
4. **Monitor logs** for errors

### Testing Voice XP

1. Join a voice channel
2. Wait for XP interval (default 60s)
3. Check logs for XP grants
4. Verify session in database:
   ```sql
   SELECT * FROM voice_sessions WHERE guild_id = YOUR_GUILD_ID;
   ```

### Testing Dashboard

1. Start all components (bot, API, dashboard)
2. Login to dashboard
3. Select your test server
4. Test each feature/page
5. Check API logs for requests
6. Verify changes in database

### Database Queries for Testing

```sql
-- View XP settings
SELECT * FROM xp_settings WHERE guild_id = YOUR_GUILD_ID;

-- View leaderboard
SELECT user_id, xp, level FROM xp WHERE guild_id = YOUR_GUILD_ID ORDER BY xp DESC LIMIT 10;

-- View multipliers
SELECT * FROM xp_channel_multipliers WHERE guild_id = YOUR_GUILD_ID;
SELECT * FROM xp_role_multipliers WHERE guild_id = YOUR_GUILD_ID;

-- View voice sessions
SELECT * FROM voice_sessions WHERE guild_id = YOUR_GUILD_ID;

-- View voice XP requirements
SELECT * FROM voice_xp_requirements WHERE guild_id = YOUR_GUILD_ID;
```

---

## 📝 Code Style Guidelines

### Python (PEP 8)

- Use 4 spaces for indentation
- Max line length: 120 characters
- Use snake_case for functions and variables
- Use PascalCase for classes
- Add docstrings to all functions
- Type hints recommended

```python
async def my_function(guild_id: int, user_id: int) -> dict:
    """
    Description of what the function does.
    
    Args:
        guild_id: Discord Guild ID
        user_id: Discord User ID
    
    Returns:
        Dictionary with results
    """
    # Implementation
    pass
```

### TypeScript

- Use 2 spaces for indentation
- Use camelCase for variables and functions
- Use PascalCase for types and interfaces
- Always use TypeScript types (avoid `any`)
- Prefer `const` over `let`

```typescript
interface MyData {
  id: number;
  name: string;
}

const fetchMyData = async (guildId: string): Promise<MyData> => {
  // Implementation
};
```

### Git Commits

- Use conventional commits format:
  - `feat:` - New feature
  - `fix:` - Bug fix
  - `docs:` - Documentation
  - `style:` - Code style changes
  - `refactor:` - Code refactoring
  - `test:` - Tests
  - `chore:` - Maintenance

Examples:
```
feat: add voice XP requirements system
fix: resolve voice session sync issue on restart
docs: update API documentation
refactor: reorganize database functions
```

---

## 🐛 Debugging

### Bot Debugging

**Enable debug logging:**
```python
# main.py
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Common issues:**
- Commands not appearing: Check intents, check command sync in `on_ready`
- XP not granted: Check cooldowns, check multipliers, check database
- Voice XP issues: Check requirements, check active sessions

### API Debugging

**Check FastAPI logs:**
```bash
uvicorn main:app --reload --log-level debug
```

**Test endpoints directly:**
- Visit `http://localhost:8000/docs`
- Try endpoints in the Swagger UI
- Check response codes and bodies

### Dashboard Debugging

**Check browser console:**
- F12 in browser
- Look for API errors
- Check network tab for failed requests

**Check Next.js logs:**
```bash
npm run dev
# Logs appear in terminal
```

**Use mock data mode:**
```env
NEXT_PUBLIC_USE_MOCK_DATA=true
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Set all environment variables correctly
- [ ] Use production database (not development)
- [ ] Change `NEXT_PUBLIC_API_URL` to production URL
- [ ] Disable debug logging
- [ ] Enable SSL/TLS
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Set up domain names
- [ ] Update CORS settings
- [ ] Test all features thoroughly

### Deployment Platforms

**Bot + API:**
- Railway (recommended)
- Render
- DigitalOcean
- AWS EC2
- Heroku (legacy)

**Dashboard:**
- Vercel (recommended)
- Netlify
- Cloudflare Pages

**Database:**
- Supabase (recommended)
- Railway
- AWS RDS
- DigitalOcean Managed Databases

---

## 📚 Resources

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Discord Developer Portal](https://discord.com/developers)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test thoroughly
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create a Pull Request

### Pull Request Guidelines

- Clear description of changes
- Screenshots for UI changes
- Test results included
- Documentation updated
- No merge conflicts
- Passes all checks

---

## 🆘 Getting Help

- Check existing documentation first
- Search GitHub issues
- Ask in Discord community (if available)
- Create detailed bug reports with:
  - Steps to reproduce
  - Expected vs actual behavior
  - Logs/error messages
  - Environment info (OS, Python version, etc.)
