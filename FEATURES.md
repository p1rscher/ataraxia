# Ataraxia Bot - Features

## 🎯 Core Features

### 📊 XP & Leveling System

Ataraxia includes a comprehensive XP and leveling system with full customization.

**Message XP**
- Users earn XP for sending messages
- Configurable cooldown period (default: 60 seconds)
- Configurable XP range (default: 10-20 XP)
- Smart cooldown to prevent spam

**Voice XP**
- Users earn XP for being in voice channels
- Configurable grant interval (default: 60 seconds)
- Configurable XP range (default: 15-25 XP)
- Flexible requirements:
  - Can require non-AFK status
  - Can require non-deafened status
  - Can require non-muted status
  - Can require others in channel
  - All toggleable per-server

**Multipliers**
- Channel-based multipliers (e.g., 2x XP in specific channels)
- Role-based multipliers (e.g., 1.5x XP for premium members)
- Server booster bonus (automatic 1.5x multiplier)
- Multipliers stack multiplicatively

**Level Roles**
- Automatically assign roles when users reach specific levels
- Multiple roles per level supported
- Configurable per server

**Leaderboard**
- View top users by XP
- Server-specific leaderboards
- Accessible via commands and dashboard

### 🎤 Voice Features

**Temporary Voice Channels**
- Users can create personal voice channels
- Channels auto-delete when empty
- Configurable creation channel
- Custom category placement

**Voice Logging**
- Log when users join voice channels
- Log when users leave voice channels
- Log when users switch channels
- Configurable log channel

### 🔐 Security & Moderation

**Verification System**
- Reaction-based verification
- Auto-assign role on verification
- Configurable verification message
- Handles missed verifications on bot restart

**Message Logging**
- Track message edits with version history
- Track message deletions
- Bulk delete logging
- Configurable log channel

### 🤖 Automation

**Auto-Roles**
- Automatically assign roles when users join
- Multiple roles supported
- Enable/disable per server

**Parent Roles**
- Define role hierarchies
- Automatically grant child roles when parent role is assigned
- Multiple parent-child relationships per server

**Bump Reminders**
- Remind server to bump
- Configurable bump role
- Configurable reminder channel
- Tracks last bump time

### 📈 Server Statistics

**Dynamic Stat Channels**
- Member count channel (auto-updates)
- Bot count channel
- Total user count channel
- Configurable channel names

**Admin Statistics**
- View command usage
- View XP distribution
- View active voice sessions
- Export stats for analysis

### 🎮 Fun & Engagement

**Counting Game**
- Users count sequentially in a designated channel
- Auto-delete wrong numbers
- Track highest count reached
- Competitive leaderboard

**AI Chat** (Optional)
- Chat with the bot using AI
- Powered by Groq API
- Cost tracking and limits
- Can be disabled

**Custom Say Command**
- Make the bot say anything
- Supports embeds
- Admin-only

### 🔧 Configuration

**XP Settings**
- Message cooldown
- Voice interval
- Message XP range
- Voice XP range
- All configurable via commands or dashboard

**Voice XP Requirements**
- Toggle AFK requirement
- Toggle deafened requirement
- Toggle muted requirement
- Toggle alone-in-channel requirement

**Log Channels**
- Message log channel
- Voice log channel
- Level log channel
- All separate and configurable

### 📊 Insights & Analytics

**Leaderboard System**
- Top users by XP
- Customizable limit
- API endpoint for external access

**Admin Insights**
- Command usage statistics
- Most active users
- XP gain trends
- Voice activity tracking

## 🎨 Customization

### Per-Server Configuration

Everything is configurable per server:
- XP settings (cooldowns, ranges)
- Voice XP requirements
- Multipliers (channel and role)
- Level roles
- Log channels
- Auto-roles
- Parent roles
- Verification settings
- Temp voice settings

### Global Settings

Some settings are global:
- Bot prefix (`Atx.`)
- AI features (enabled/disabled)
- Max daily AI cost
- Developer ID

## 🌐 Dashboard Features

The web dashboard provides a user-friendly interface for:

**Overview**
- Bot statistics
- Server selection
- Quick links

**XP Management**
- View and edit XP settings
- Manage channel multipliers
- Manage role multipliers
- Configure voice XP requirements

**Leaderboard**
- View server leaderboard
- Search users
- Export data

**Logs**
- Configure log channels
- View recent logs (planned)
- Filter by type (planned)

**Analytics**
- XP gain over time (planned)
- Voice activity (planned)
- Command usage (planned)

**Settings**
- Auto-roles
- Level roles
- Parent roles
- Verification
- Bump reminders

## 🚀 Upcoming Features

Features planned for future releases:

- [ ] Custom commands
- [ ] Moderation tools (kick, ban, timeout)
- [ ] Warning system
- [ ] Ticket system
- [ ] Giveaway system
- [ ] Welcome/goodbye messages
- [ ] Server backups
- [ ] Music player
- [ ] Economy system
- [ ] Achievements/badges
- [ ] Custom embeds
- [ ] Scheduled messages
- [ ] Poll system
- [ ] Suggestion system
- [ ] Starboard

## 💎 Premium Features (Planned)

Premium tier will unlock:

- Increased XP multipliers
- Custom bot status in your server
- Priority support
- Early access to new features
- Increased limits (level roles, multipliers, etc.)
- Custom branding in dashboard

## 📝 Feature Details

### XP Calculator

The XP calculator includes:
- Configurable base XP ranges
- Channel multipliers
- Role multipliers
- Server booster bonus
- Cumulative calculation

### Level Formula

Level calculation uses a progressive formula:
```
XP needed for level N = N * 100 + (N-1) * 50
```

Example:
- Level 1: 100 XP
- Level 2: 250 XP total (150 more)
- Level 3: 450 XP total (200 more)
- etc.

### Voice Session Management

Voice sessions are intelligently managed:
- Created when user joins voice (if requirements met)
- Deleted when user leaves voice
- Synced on bot restart (handles users already in voice)
- Requirements checked every XP grant interval
- Stale sessions cleaned automatically

### Message History

Message history includes:
- Original message content
- Edit history with timestamps
- Deletion timestamp
- Version tracking
- Bulk delete support

### Verification Handling

Verification system:
- Single message with reaction
- Auto-verify on reaction
- Handle missed verifications on restart
- Configurable role assignment
- Works across bot restarts

## 🎭 Command Categories

Commands are organized into categories:

- **General** - About, help, info
- **XP** - Leaderboard, rank, xp settings
- **Voice** - Voice XP requirements, temp voice setup
- **Moderation** - Say, clear channel, logs
- **Configuration** - Auto-roles, level roles, verification
- **Stats** - Server stats, admin stats
- **Fun** - AI chat, counting
- **Utility** - Math commands, insights

## 🔒 Permission Levels

Commands have different permission requirements:

- **Everyone** - Rank, leaderboard, about
- **Manage Server** - Most configuration commands
- **Administrator** - XP settings, log configs, dangerous commands
- **Bot Developer** - Shutdown, premium management

## 🌍 Multi-Language Support

Currently supports:
- English (primary)

Planned:
- German
- Spanish
- French
- More languages based on demand

## 📊 Data Privacy

Ataraxia respects user privacy:
- Only stores necessary data
- Message content only stored if logging enabled
- User IDs only (no personal data)
- Data can be deleted on request
- No data sold to third parties
- See [SECURITY.md](SECURITY.md) for details
