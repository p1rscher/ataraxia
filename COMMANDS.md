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

**`/xp embed`** 🟠
Open the visual dashboard to customize the level-up embed (same editor style as welcome/traffic embeds).
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

### `/stickymessage` - Bottom Sticky Message

**`/stickymessage set [message_id] [channel]`** 🟠
Keep a bot-authored message reposted at the bottom of a channel.
- **Parameters:**
  - `message_id` - Message ID or Discord link to a bot message; optional if you reply to the bot message
  - `channel` - The target channel; defaults to the current channel

**`/stickymessage clear [channel]`** 🟠
Disable the bottom sticky message for a channel.
- **Parameters:**
  - `channel` - The target channel; defaults to the current channel

**`/stickymessage status [channel]`** 🟢
Show the current sticky message configuration for a channel.
- **Parameters:**
  - `channel` - The target channel; defaults to the current channel

**`/stickymessage refresh [channel]`** 🟠
Immediately delete and repost the sticky message in a channel.
- **Parameters:**
  - `channel` - The target channel; defaults to the current channel

### `/ticket` - Ticket System

**`/ticket setup [category] [support_role] [closer_role] [max_tickets]`** 🟠
Configure the ticket system basics (category, support permissions, limits).

**`/ticket panel [channel]`** 🟠
Open the full Embed Builder and deploy a customizable ticket panel with the ticket button.

**`/ticket paneledit [channel] [message_id]`** 🟠
Open the full Embed Builder for an existing ticket panel message.

**`/ticket panellist`** 🟠
List all registered ticket panel messages with channel, message ID, and jump link.

**`/ticket opendashboard`** 🟠
Open the dashboard for the message sent when a ticket is created.
Supports placeholders like `{server}`, `{server.icon}`, `{server.avatar}`, `{time}`, `{user}`, `{user.avatar}`, `{ticket_id}`, `{support_role}`, `{ticket_channel}`.

**`/ticket openpreview`** 🟠
Show an ephemeral preview of the current ticket-open message configuration (without creating a ticket).

**`/ticket add [user]`** 🟠
Add a user to the current ticket channel.

**`/ticket remove [user]`** 🟠
Remove a user from the current ticket channel.

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

### Reaction Role Panel Colors

Each reaction-role panel has its own embed color. When creating or editing a panel, set it in the **Adjust Text/Image** dialog using `Embed Color (Hex)`, for example `#FF00AA`.

This color is stored only for that panel and does not affect welcome embeds or any other embed type.

### `/settings color` - Individual Embed Colors

**`/settings color set [hex_color] [type]`** 🟠
Set the color of one concrete embed or the explicit global fallback. The `type` selection is required; no color is changed when it is omitted.
- **Examples:**
  - `/settings color set #57F287 traffic_join`
  - `/settings color set #ED4245 traffic_leave`
  - `/settings color set #FEE75C traffic_boost`
- **Traffic logs:** joins, leaves, and boosts use the shared traffic-log channel by default, but can be routed to separate channels and each embed can have its own color.
- **Traffic channels:** the shared traffic channel is optional. Administrators can configure separate channels with `/log set` for `Traffic: Member Joins`, `Traffic: Member Leaves`, and `Traffic: Server Boosts`.
- **Timestamp:** traffic embeds include Discord's message timestamp.
- **Member count:** displayed with the correct ordinal suffix, such as `31st`, `22nd`, or `13th`.

**`/settings color view`** 🟠
View legacy fallback colors and individual embed overrides.

**`/settings color reset`** 🟠
Reset all fallback and individual embed colors.

### Welcome Embed Placeholders

In `/welcome dashboard`, you can use `{time}`, `{member_count}`, and `{member_count_ext}` in text, title, description, and author/footer fields:

- `{time}` - Discord timestamp of the send time. In title, description, and normal fields, full timestamp text is inserted. In the embed footer, the real embed timestamp field is used so Discord renders it naturally (for example as localized relative/full time). Without this placeholder, no timestamp is set.
- `{member_count}` - Number of human members (excluding bots), for example `31`.
- `{member_count_ext}` - Number of human members with English ordinal suffix, for example `31st`, `22nd`, `13th`, or `4th`.

The existing placeholders `{user}`, `{user.name}`, `{user.avatar}`, `{server}`, and `{server.icon}` remain available.

### `/log` - Traffic Log Channels

The shared `User Traffic Logs` channel is optional. Dedicated channels can be configured independently:

- `/log set` → `Traffic: Member Joins`
- `/log set` → `Traffic: Member Leaves`
- `/log set` → `Traffic: Server Boosts`

Use `/log clear` to let an event fall back to the shared traffic channel, or `/log disable` to disable only that event. `/log status` shows all four settings.

### `/log embed` - Customize Traffic Embeds Visually

With `/log embed`, an administrator can open the same visual embed builder as `/welcome dashboard` for **Member Join**, **Member Leave**, or **Server Boost**. The preview updates live while you use buttons and modals.

All dashboard editors using this builder (Welcome, Traffic, Trigger, Level-Up, Ticket Open) include the **Embed Enabled / Embed Disabled** toggle. If set to *disabled*, only outside text is sent (content-only mode).

- Title
- Description
- Author and author icon
- Footer and footer icon
- Thumbnail
- Large image
- The same text placeholders as the welcome dashboard
- `{time}` through existing timestamp logic

Available placeholders include `{user}`, `{user.name}`, `{user.avatar}`, `{server}`, `{server.icon}`, `{member_count}`, `{member_count_ext}`, `{time}`, `{account_created}`, `{joined_at}`, and `{event}`.

With `/log embed-reset`, a single traffic embed can be reset to its default configuration. Color is configured separately via `/settings color set`, so traffic colors do not accidentally overwrite welcome colors.

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

### `/triggerembed` - Trigger Embeds

Administrators can create fully configurable messages with text **outside the embed** and an optional embed. When an exact trigger word is typed, both parts are sent automatically in the current channel.

- `/triggerembed create trigger:.partnership` - opens the visual embed builder
- `/triggerembed edit trigger:.partnership` - edits an existing trigger embed
- `/triggerembed list` - lists all trigger embeds
- `/triggerembed delete trigger:.partnership` - removes one trigger embed

The editor uses the same dashboard and preview concept as `/welcome dashboard` and traffic embeds. The **Edit Trigger Text** button configures both outside text and embed title/description. You can also customize author, footer, images, fields, and timestamp.

All embed editors use the same field editor. With **Edit Fields**, you can add multiple fields, edit selected fields, remove selected fields, or clear all fields. A footer icon can also be saved without footer text.

The trigger word must appear as its own whitespace-delimited token. This prevents `.partnership` from triggering accidentally on `.partnerships`.

### `/chatpersona` - Random Chat Personality

The bot can learn a chat personality from real user messages (words, emojis, GIF links, sticker names) and reply randomly in chat.

- Messages are **not time-based**. They trigger on new user messages with a configurable random chance.
- If someone replies to a bot message, `replymode` can force a response with 100% probability.
- Optionally, a **strictly limited AI refinement** can be enabled (daily limit + separate chance), so most responses stay natural and not overly "AI-like".

**Admin commands:**
- `/chatpersona status` - show current settings and learned top words/emojis
- `/chatpersona enable enabled:true|false` - enable/disable the feature
- `/chatpersona chance percent:1-100` - set random chance for text replies
- `/chatpersona gifchance percent:0-100` - set random chance for GIF links
- `/chatpersona stickerchance percent:0-100` - set random chance for stickers
- `/chatpersona cooldown seconds:0-3600` - minimum delay between spontaneous bot messages
- `/chatpersona stickercooldown seconds:0-7200` - minimum delay between sticker messages per channel
- `/chatpersona blacklist mode target:text|gif|sticker|all mode:blacklist|whitelist` - choose mode: blacklist = block listed channels, whitelist = allow only listed channels
- `/chatpersona blacklist add channel:#chat target:text|gif|sticker|all` - add channel to the selected list
- `/chatpersona blacklist remove channel:#chat target:text|gif|sticker|all` - remove channel from the selected list
- `/chatpersona blacklist list` - show current modes and channel lists for text, GIF, and sticker outputs
- `/chatpersona blacklist clear target:text|gif|sticker|all` - clear channel list for one or all targets
- `/chatpersona language mode:auto|default_en` - language mode: auto-detect or force English default
- `/chatpersona traits nice:0-100 romantic:0-100 funny:0-100 chaotic:0-100` - tune personality traits
- `/chatpersona profanity enabled:true|false` - allow/disallow strong language
- `/chatpersona ai enabled:true|false chance_percent:1-100 daily_limit:1-500` - configure limited AI refinement
- `/chatpersona replymode enabled:true|false` - force 100% replies when users reply to bot messages
- `/chatpersona resetlearning confirm:RESET` - reset learned data
- `/chatpersona test` - preview a generated message

### `/steal` - Copy a Custom Emoji or Sticker

**`/steal [message_id] [name]`** 🟠
Copy a custom Discord emoji or sticker from a message in the current channel to the server.
- **Parameters:**
  - `message_id` - ID of a message containing exactly one custom emoji or sticker
  - `name` - Optional new name for the copied emoji or sticker
- **Example:** `/steal 123456789012345678 party_time`
- **Bot permission:** Requires "Create Expressions" or "Manage Expressions"

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
