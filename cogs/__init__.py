"""
Ataraxia Bot - Cogs Module

This directory contains all bot commands (cogs) organized by functionality.

Current Structure:
- Flat structure: All cogs in this directory
- Future: Can be organized into subdirectories by category

Supported Categories (for future organization):
┌─────────────────────────────────────────────────────────────┐
│ MODERATION                                                  │
│ - verification.py    : Reaction-based role verification     │
│ - autorole.py        : Auto-assign roles to new members     │
│ - clear_channel.py   : Bulk message deletion                │
│ - parent_roles.py    : Hierarchical role management         │
├─────────────────────────────────────────────────────────────┤
│ LEVELING & XP                                               │
│ - (future: xp.py, leaderboard.py, rewards.py)               │
├─────────────────────────────────────────────────────────────┤
│ SERVER MANAGEMENT                                           │
│ - serverstats.py     : Real-time stats in voice channels    │
│ - temp_voice.py      : Temporary voice channel system       │
│ - bump_reminder.py   : Server bump reminders                │
│ - log_config.py      : Logging configuration                │
├─────────────────────────────────────────────────────────────┤
│ UTILITIES                                                   │
│ - ai.py              : AI assistant with Ataraxia personality│
│ - say.py             : Echo messages                        │
│ - about.py           : Bot information                      │
│ - fun.py             : Fun commands                         │
│ - hello.py           : Greeting command                     │
├─────────────────────────────────────────────────────────────┤
│ ADMIN & STATS                                               │
│ - admin_stats.py     : Command usage statistics             │
│ - insights.py        : Server insights                      │
│ - shutdown.py        : Bot shutdown command                 │
├─────────────────────────────────────────────────────────────┤
│ PREMIUM                                                     │
│ - premium.py         : Premium tier management              │
└─────────────────────────────────────────────────────────────┘

How to add a new cog:
1. Create a new .py file in this directory (or in a category subdirectory)
2. Define a class that inherits from commands.Cog
3. Add an async setup(bot) function at the end
4. The bot will automatically load it on startup

Example structure for future categorization:
cogs/
├── moderation/
│   ├── verification.py
│   └── autorole.py
├── leveling/
│   └── xp.py
├── utilities/
│   ├── ai.py
│   └── say.py
└── premium/
    └── premium.py

The main.py loader supports both flat and nested structures automatically!
"""
