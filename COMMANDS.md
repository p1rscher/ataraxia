# Ataraxia Bot - Commands Reference

## 📋 Command Overview

All commands use Discord's slash command system (`/command`). Below is a comprehensive list of all available commands.

> **Permission Levels:**
> - 🟢 Everyone - Any user can use
> - 🟡 Manage Server - Requires "Manage Server" permission
> - 🟠 Administrator - Requires "Administrator" permission  
> - 🔴 Developer - Bot developer only

---

## 📊 XP & Leveling

### `/xp` - XP Configuration Commands

**`/xp cooldown [seconds]`** 🟠
Set the cooldown for message XP (prevents spam).
- **Parameters:** 
  - `seconds` - Cooldown in seconds (e.g., 60)
- **Example:** `/xp cooldown 120`

**`/xp voiceinterval [seconds]`** 🟠
Set how often voice XP is granted.
- **Parameters:**
  - `seconds` - Interval in seconds (e.g., 60)
- **Example:** `/xp voiceinterval 90`

**`/xp messagexp [min] [max]`** 🟠
Set the XP range for messages.
- **Parameters:**
  - `min` - Minimum XP per message
  - `max` - Maximum XP per message
- **Example:** `/xp messagexp 10 20`

**`/xp voicexp [min] [max]`** 🟠
Set the XP range for voice activity.
- **Parameters:**
  - `min` - Minimum XP per interval
  - `max` - Maximum XP per interval
- **Example:** `/xp voicexp 15 25`

**`/xp info`** 🟠
View current XP settings for the server.
- **No parameters**

### `/multiplier` - XP Multiplier Commands

**`/multiplier channel [channel] [multiplier]`** 🟠
Set XP multiplier for a specific channel.
- **Parameters:**
  - `channel` - The channel to apply multiplier to
  - `multiplier` - Multiplier value (e.g., 2.0 for double XP)
- **Example:** `/multiplier channel #general 1.5`

**`/multiplier removechannel [channel]`** 🟠
Remove XP multiplier from a channel.
- **Parameters:**
  - `channel` - The channel to remove multiplier from

**`/multiplier role [role] [multiplier]`** 🟠
Set XP multiplier for a specific role.
- **Parameters:**
  - `role` - The role to apply multiplier to
  - `multiplier` - Multiplier value (e.g., 1.5)
- **Example:** `/multiplier role @Premium 2.0`

**`/multiplier removerole [role]`** 🟠
Remove XP multiplier from a role.
- **Parameters:**
  - `role` - The role to remove multiplier from

**`/multiplier list`** 🟠
List all active XP multipliers (channels and roles).
- **No parameters**

### `/voicexp-requirements` - Voice XP Requirements

**`/voicexp-requirements view`** 🟠
View current Voice XP requirements for the server.
- **No parameters**

**`/voicexp-requirements set-afk [allow]`** 🟠
Set whether AFK users can earn Voice XP.
- **Parameters:**
  - `allow` - True to allow AFK users, False to deny
- **Example:** `/voicexp-requirements set-afk False`

**`/voicexp-requirements set-deaf [allow]`** 🟠
Set whether deafened users can earn Voice XP.
- **Parameters:**
  - `allow` - True to allow deafened users, False to deny
- **Example:** `/voicexp-requirements set-deaf False`

**`/voicexp-requirements set-muted [allow]`** 🟠
Set whether muted users can earn Voice XP.
- **Parameters:**
  - `allow` - True to allow muted users, False to deny
- **Example:** `/voicexp-requirements set-muted True`

**`/voicexp-requirements set-alone [allow]`** 🟠
Set whether users alone in a channel can earn Voice XP.
- **Parameters:**
  - `allow` - True to allow alone users, False to deny
- **Example:** `/voicexp-requirements set-alone False`

**`/voicexp-requirements reset`** 🟠
Reset all Voice XP requirements to defaults.
- **No parameters**

### `/level-roles` - Level Role Commands

**`/level-roles add [level] [role]`** 🟠
Add a role to be granted at a specific level.
- **Parameters:**
  - `level` - The level to grant the role at
  - `role` - The role to grant
- **Example:** `/level-roles add 10 @Level 10`

**`/level-roles remove [level] [role]`** 🟠
Remove a level role.
- **Parameters:**
  - `level` - The level
  - `role` - The role to remove

**`/level-roles list`** 🟠
List all level roles for the server.
- **No parameters**

**`/level-roles clear`** 🟠
Remove all level roles for the server.
- **No parameters**

### `/insights` - User XP Insights

**`/insights [user]`** 🟢
View detailed XP statistics for a user.
- **Parameters:**
  - `user` - The user to view (optional, defaults to yourself)
- **Example:** `/insights @Username`

---

## 🎤 Voice Features

### `/tempvoice` - Temporary Voice Channels

**`/tempvoice setup`** 🟠
Set up the temporary voice channel system.
- **Interactive setup via buttons**

**`/tempvoice reset`** 🟠
Remove the temporary voice channel system.
- **No parameters**

**`/tempvoice remove [channel]`** 🟠
Delete a Creator-Channel from the system.
- **Parameters:**
  - `channel` - The creator channel to remove

**`/tempvoice info`** 🟠
Show the current temporary voice configuration.
- **No parameters**

---

## 🔐 Security & Moderation

### `/verification` - Verification System

**`/verification setup [channel] [role] [message]`** 🟠
Set up reaction-based verification.
- **Parameters:**
  - `channel` - Channel to send verification message
  - `role` - Role to grant on verification
  - `message` - Verification message text
- **Example:** `/verification setup #verify @Member Welcome!`

**`/verification remove`** 🟠
Remove verification system.
- **No parameters**

### `/cleanup-channel` - Message Cleanup

**`/cleanup-channel [limit] [user] [contains]`** 🟠
Delete messages in the current channel.
- **Parameters:**
  - `limit` - Number of messages to check (max 1000)
  - `user` - Only delete messages from this user (optional)
  - `contains` - Only delete messages containing text (optional)
- **Example:** `/cleanup-channel 100 @User spam`

---

## 🤖 Automation

### `/autorole` - Auto-Role System

**`/autorole enable`** 🟡
Enable auto-role system for the server.
- **No parameters**

**`/autorole disable`** 🟡
Disable auto-role system for the server.
- **No parameters**

**`/autorole add [role]`** 🟡
Add a role to be auto-assigned on join.
- **Parameters:**
  - `role` - The role to auto-assign
- **Example:** `/autorole add @Member`

**`/autorole remove [role]`** 🟡
Remove a role from auto-assign list.
- **Parameters:**
  - `role` - The role to remove

**`/autorole list`** 🟡
List all auto-assigned roles.
- **No parameters**

**`/autorole clear`** 🟡
Clear all auto-assigned roles.
- **No parameters**

### `/parent-role` - Parent Role System

**`/parent-role create [name] [color]`** 🟡
Create a parent role (automatically truncates name).
- **Parameters:**
  - `name` - Role name (will be truncated to 50 chars)
  - `color` - Role color in hex (e.g., #FF5733)
- **Example:** `/parent-role create VIP #FFD700`

**`/parent-role add-child [parent] [child]`** 🟡
Add a child role to a parent role.
- **Parameters:**
  - `parent` - The parent role
  - `child` - The child role to add
- **Example:** `/parent-role add-child @VIP @VIP-Benefits`

**`/parent-role remove-child [parent] [child]`** 🟡
Remove a child role from a parent role.
- **Parameters:**
  - `parent` - The parent role
  - `child` - The child role to remove

**`/parent-role delete [parent]`** 🟡
Delete a parent role configuration.
- **Parameters:**
  - `parent` - The parent role to delete

**`/parent-role list`** 🟡
List all parent roles and their children.
- **No parameters**

### `/welcome` - Welcome Message System

**`/welcome set [channel] [message]`** 🟠
Set the welcome message for new members joining the server.
- **Parameters:**
  - `channel` - Channel where the welcome message will be sent
  - `message` - The welcome message text. Use `{user}` to mention the new member and `{server}` for the server name.
- **Example:** `/welcome set #welcome Welcome to {server}, {user}!`

**`/welcome show`** 🟠
Show the current welcome message configuration.
- **No parameters**

---

### `/bump` - Bump Reminder System

**`/bump setup [role] [channel]`** 🟠
Set up bump reminders.
- **Parameters:**
  - `role` - Role to ping for reminders
  - `channel` - Channel to send reminders in
- **Example:** `/bump setup @Bumpers #general`

**`/bump disable`** 🟠
Disable bump reminders.
- **No parameters**

---

## 📈 Server Statistics

### `/serverstats` - Server Statistics Channels

**`/serverstats [type]`** 🟠
Set up a channel for server statistics.
- **Parameters:**
  - `type` - Stat type: `members`, `bots`, `total`
- **Example:** `/serverstats members`

---

## 🎮 Fun & Engagement

### `/counting` - Counting Game

**`/counting setup [channel]`** 🟠
Set up the counting game in a channel.
- **Parameters:**
  - `channel` - Channel for counting game
- **Example:** `/counting setup #counting`

**`/counting disable`** 🟠
Disable the counting game.
- **No parameters**

**`/counting stats`** 🟢
View counting game statistics.
- **No parameters**

### `/ask` - AI Chat (Optional)

**`/ask [question]`** 🟢
Ask the AI a question.
- **Parameters:**
  - `question` - Your question
- **Example:** `/ask What is the meaning of life?`

**`/clear-history`** 🟢
Clear your conversation history with the AI.
- **No parameters**

### `/math` - Math Commands

**`/math calculate [expression]`** 🟢
Calculate a math expression.
- **Parameters:**
  - `expression` - Math expression (e.g., 2+2*5)
- **Example:** `/math calculate 10 * 5 + 3`

---

## ⚙️ Configuration

### `/log-config` - Logging Configuration

**`/log-config set-message [channel]`** 🟠
Set the message log channel.
- **Parameters:**
  - `channel` - Channel for message logs
- **Example:** `/log-config set-message #logs`

**`/log-config set-voice [channel]`** 🟠
Set the voice log channel.
- **Parameters:**
  - `channel` - Channel for voice logs
- **Example:** `/log-config set-voice #voice-logs`

**`/log-config set-level [channel]`** 🟠
Set the level log channel.
- **Parameters:**
  - `channel` - Channel for level-up notifications
- **Example:** `/log-config set-level #levels`

**`/log-config clear-message`** 🟠
Remove message log channel.
- **No parameters**

**`/log-config clear-voice`** 🟠
Remove voice log channel.
- **No parameters**

**`/log-config clear-level`** 🟠
Remove level log channel.
- **No parameters**

**`/log-config view`** 🟠
View current log channel configuration.
- **No parameters**

---

## 📊 Information & Stats

### `/about` - Bot Information

**`/about`** 🟢
Display information about the bot.
- **No parameters**

### `/hello` - Greeting

**`/hello`** 🟢
Get a friendly greeting from the bot.
- **No parameters**

### `/admin-stats` - Admin Statistics

**`/admin-stats`** 🟠
View admin statistics (command usage, top users, etc.).
- **No parameters**

---

## 🔧 Utility

### `/say` - Make Bot Say

**`/say [message] [embed]`** 🟠
Make the bot send a message.
- **Parameters:**
  - `message` - The message to send
  - `embed` - Send as embed (True/False, default False)
- **Example:** `/say Hello everyone! False`

### `/premium` - Premium System (Planned)

**`/premium`** 🟢
View premium tiers and benefits.
- **No parameters**

**`/premium redeem [code]`** 🟢
Redeem a premium code.
- **Parameters:**
  - `code` - Your premium code

**`/premium grant [user] [tier] [days]`** 🔴
Grant premium to a user (Developer only).
- **Parameters:**
  - `user` - User to grant premium to
  - `tier` - Premium tier (premium/premium_plus)
  - `days` - Duration in days

---

## 🎛️ Developer Commands

### `/shutdown` - Shutdown Bot

**`/shutdown`** 🔴
Safely shutdown the bot (Developer only).
- **No parameters**

---

## 💡 Tips & Tricks

### Using Commands Efficiently

1. **Auto-complete:** Discord will show suggestions as you type
2. **Permissions:** Check command color to see if you have permission
3. **Help:** Use `/about` to see bot information and links
4. **Modifiers:** Most commands have optional parameters for flexibility

### Common Command Combinations

**Setting up a new server:**
```
1. /autorole enable
2. /autorole add @Member
3. /welcome set #welcome Welcome to {server}, {user}!
4. /verification setup #verify @Member Welcome!
5. /log-config set-message #logs
6. /log-config set-level #level-ups
7. /xp info (check default settings)
8. /tempvoice setup
```

**Configuring XP system:**
```
1. /xp cooldown 60
2. /xp messagexp 10 20
3. /xp voicexp 15 25
4. /multiplier channel #general 1.5
5. /multiplier role @Premium 2.0
6. /voicexp-requirements view
7. /level-roles add 10 @Level 10
```

### Command Shortcuts

- Most commands have subcommands organized by feature
- Use Tab to auto-complete command names
- Command groups: `/xp`, `/multiplier`, `/voicexp-requirements`, `/level-roles`, etc.

### Getting Help

- Use `/about` for bot information
- Check the dashboard for visual configuration
- See [FEATURES.md](FEATURES.md) for detailed feature descriptions
- See [SETUP.md](SETUP.md) for setup instructions
