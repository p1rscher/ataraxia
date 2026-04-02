# Ataraxia Bot - API Reference

## 🌐 Base Information

**Base URL (Development):** `http://localhost:8000`  
**Base URL (Production):** `https://api.yourbot.com`

**Technology:** FastAPI  
**Documentation:** Available at `/docs` (Swagger UI)  
**Alternative Docs:** Available at `/redoc` (ReDoc)

## 🔐 Authentication

Currently, the API does not require authentication. It is designed to run locally or behind a firewall/VPN.

For production deployment, consider:
- API keys
- OAuth2
- Rate limiting
- IP whitelisting

## 📊 API Endpoints

---

### Health & Status

#### `GET /`
Health check endpoint.

**Response:**
```json
{
  "status": "online",
  "message": "Ataraxia Bot API"
}
```

#### `GET /health`
Detailed health check.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

### XP Settings

#### `GET /api/guilds/{guild_id}/xp/settings`
Get all XP settings for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Response:**
```json
{
  "message_cooldown": 60,
  "voice_interval": 60,
  "message_xp_min": 10,
  "message_xp_max": 20,
  "voice_xp_min": 15,
  "voice_xp_max": 25
}
```

**Default Values:**
- `message_cooldown`: 60 seconds
- `voice_interval`: 60 seconds
- `message_xp_min`: 10
- `message_xp_max`: 20
- `voice_xp_min`: 15
- `voice_xp_max`: 25

---

#### `PUT /api/guilds/{guild_id}/xp/cooldown`
Update message XP cooldown.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "cooldown": 120
}
```

**Response:**
```json
{
  "success": true,
  "cooldown": 120
}
```

---

#### `PUT /api/guilds/{guild_id}/xp/voiceinterval`
Update voice XP interval.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "interval": 90
}
```

**Response:**
```json
{
  "success": true,
  "interval": 90
}
```

---

#### `PUT /api/guilds/{guild_id}/xp/messagexp`
Update message XP range.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "min_xp": 15,
  "max_xp": 25
}
```

**Response:**
```json
{
  "success": true,
  "min_xp": 15,
  "max_xp": 25
}
```

---

#### `PUT /api/guilds/{guild_id}/xp/voicexp`
Update voice XP range.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "min_xp": 20,
  "max_xp": 30
}
```

**Response:**
```json
{
  "success": true,
  "min_xp": 20,
  "max_xp": 30
}
```

---

### Multipliers

#### `GET /api/guilds/{guild_id}/multipliers`
Get all multipliers for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Response:**
```json
{
  "channel_multipliers": [
    {
      "channel_id": 123456789,
      "multiplier": 1.5
    }
  ],
  "role_multipliers": [
    {
      "role_id": 987654321,
      "multiplier": 2.0
    }
  ]
}
```

---

#### `POST /api/guilds/{guild_id}/multipliers/channel`
Add or update a channel multiplier.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "channel_id": 123456789,
  "multiplier": 2.0
}
```

**Response:**
```json
{
  "success": true,
  "channel_id": 123456789,
  "multiplier": 2.0
}
```

---

#### `DELETE /api/guilds/{guild_id}/multipliers/channel/{channel_id}`
Remove a channel multiplier.

**Parameters:**
- `guild_id` (path) - Discord Guild ID
- `channel_id` (path) - Discord Channel ID

**Response:**
```json
{
  "success": true,
  "message": "Channel multiplier removed"
}
```

---

#### `POST /api/guilds/{guild_id}/multipliers/role`
Add or update a role multiplier.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "role_id": 987654321,
  "multiplier": 1.5
}
```

**Response:**
```json
{
  "success": true,
  "role_id": 987654321,
  "multiplier": 1.5
}
```

---

#### `DELETE /api/guilds/{guild_id}/multipliers/role/{role_id}`
Remove a role multiplier.

**Parameters:**
- `guild_id` (path) - Discord Guild ID
- `role_id` (path) - Discord Role ID

**Response:**
```json
{
  "success": true,
  "message": "Role multiplier removed"
}
```

---

### Voice XP Requirements

#### `GET /api/guilds/{guild_id}/voicexp/requirements`
Get Voice XP requirements for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Response:**
```json
{
  "require_non_afk": true,
  "require_non_deaf": true,
  "require_non_muted": false,
  "require_others_in_channel": true
}
```

**Default Values:**
- `require_non_afk`: true (AFK users don't get XP)
- `require_non_deaf`: true (Deafened users don't get XP)
- `require_non_muted`: false (Muted users get XP)
- `require_others_in_channel`: true (Users alone don't get XP)

---

#### `PUT /api/guilds/{guild_id}/voicexp/requirements`
Update all Voice XP requirements at once.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "require_non_afk": true,
  "require_non_deaf": false,
  "require_non_muted": true,
  "require_others_in_channel": false
}
```

**Response:**
```json
{
  "success": true,
  "requirements": {
    "require_non_afk": true,
    "require_non_deaf": false,
    "require_non_muted": true,
    "require_others_in_channel": false
  }
}
```

---

#### `PATCH /api/guilds/{guild_id}/voicexp/requirements`
Update a single Voice XP requirement.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "requirement": "require_non_afk",
  "value": false
}
```

**Valid requirement names:**
- `require_non_afk`
- `require_non_deaf`
- `require_non_muted`
- `require_others_in_channel`

**Response:**
```json
{
  "success": true,
  "requirement": "require_non_afk",
  "value": false
}
```

---

### Logs

#### `GET /api/guilds/{guild_id}/logs`
Get all log channel configurations for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Response:**
```json
{
  "message_log_channel_id": 123456789,
  "voice_log_channel_id": 234567890,
  "level_log_channel_id": 345678901
}
```

**Note:** `null` values indicate no log channel is configured.

---

#### `PUT /api/guilds/{guild_id}/logs/messages`
Set message log channel.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "channel_id": 123456789
}
```

**Response:**
```json
{
  "success": true,
  "channel_id": 123456789
}
```

---

#### `PUT /api/guilds/{guild_id}/logs/voice`
Set voice log channel.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "channel_id": 234567890
}
```

**Response:**
```json
{
  "success": true,
  "channel_id": 234567890
}
```

---

#### `PUT /api/guilds/{guild_id}/logs/levels`
Set level log channel.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Request Body:**
```json
{
  "channel_id": 345678901
}
```

**Response:**
```json
{
  "success": true,
  "channel_id": 345678901
}
```

---

### Leaderboard

#### `GET /api/guilds/{guild_id}/leaderboard`
Get XP leaderboard for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID
- `limit` (query, optional) - Number of users to return (default: 10)

**Example:** `/api/guilds/123456789/leaderboard?limit=25`

**Response:**
```json
[
  {
    "user_id": 111111111,
    "xp": 15000,
    "level": 25
  },
  {
    "user_id": 222222222,
    "xp": 12000,
    "level": 22
  }
]
```

---

### Statistics

#### `GET /api/guilds/{guild_id}/stats`
Get general statistics for a guild.

**Parameters:**
- `guild_id` (path) - Discord Guild ID

**Response:**
```json
{
  "total_users": 150,
  "total_messages": 50000,
  "total_xp_granted": 250000,
  "active_voice_sessions": 5
}
```

**Note:** This endpoint is planned for future implementation.

---

## 🔧 Error Responses

All endpoints return standard HTTP status codes:

**200 OK** - Request successful
```json
{
  "success": true,
  "data": {}
}
```

**400 Bad Request** - Invalid parameters
```json
{
  "detail": "Invalid parameter: multiplier must be positive"
}
```

**404 Not Found** - Resource not found
```json
{
  "detail": "Guild not found"
}
```

**500 Internal Server Error** - Server error
```json
{
  "detail": "Internal server error"
}
```

---

## 📚 Data Models

### XPSettings
```typescript
{
  message_cooldown: number      // Seconds between message XP grants
  voice_interval: number         // Seconds between voice XP grants
  message_xp_min: number         // Minimum XP per message
  message_xp_max: number         // Maximum XP per message
  voice_xp_min: number           // Minimum XP per voice interval
  voice_xp_max: number           // Maximum XP per voice interval
}
```

### VoiceXPRequirements
```typescript
{
  require_non_afk: boolean              // Must user be non-AFK?
  require_non_deaf: boolean             // Must user be non-deafened?
  require_non_muted: boolean            // Must user be non-muted?
  require_others_in_channel: boolean    // Must there be others in channel?
}
```

### ChannelMultiplier
```typescript
{
  channel_id: number       // Discord Channel ID
  multiplier: number       // Multiplier value (e.g., 1.5, 2.0)
}
```

### RoleMultiplier
```typescript
{
  role_id: number          // Discord Role ID
  multiplier: number       // Multiplier value (e.g., 1.5, 2.0)
}
```

### LeaderboardEntry
```typescript
{
  user_id: number          // Discord User ID
  xp: number               // Total XP
  level: number            // Current level
}
```

---

## 🚀 Usage Examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"
GUILD_ID = "123456789"

# Get XP settings
response = requests.get(f"{BASE_URL}/api/guilds/{GUILD_ID}/xp/settings")
settings = response.json()
print(settings)

# Update message XP cooldown
response = requests.put(
    f"{BASE_URL}/api/guilds/{GUILD_ID}/xp/cooldown",
    json={"cooldown": 120}
)
print(response.json())

# Get leaderboard
response = requests.get(
    f"{BASE_URL}/api/guilds/{GUILD_ID}/leaderboard",
    params={"limit": 10}
)
leaderboard = response.json()
for entry in leaderboard:
    print(f"User {entry['user_id']}: Level {entry['level']} ({entry['xp']} XP)")
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000";
const GUILD_ID = "123456789";

// Get XP settings
const settings = await fetch(`${BASE_URL}/api/guilds/${GUILD_ID}/xp/settings`)
  .then(res => res.json());
console.log(settings);

// Update voice XP requirements
await fetch(`${BASE_URL}/api/guilds/${GUILD_ID}/voicexp/requirements`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    require_non_afk: true,
    require_non_deaf: false,
    require_non_muted: false,
    require_others_in_channel: true
  })
});

// Get leaderboard
const leaderboard = await fetch(
  `${BASE_URL}/api/guilds/${GUILD_ID}/leaderboard?limit=10`
).then(res => res.json());
leaderboard.forEach(entry => {
  console.log(`User ${entry.user_id}: Level ${entry.level} (${entry.xp} XP)`);
});
```

### cURL

```bash
# Get XP settings
curl http://localhost:8000/api/guilds/123456789/xp/settings

# Update message XP range
curl -X PUT http://localhost:8000/api/guilds/123456789/xp/messagexp \
  -H "Content-Type: application/json" \
  -d '{"min_xp": 15, "max_xp": 25}'

# Add channel multiplier
curl -X POST http://localhost:8000/api/guilds/123456789/multipliers/channel \
  -H "Content-Type: application/json" \
  -d '{"channel_id": 111111111, "multiplier": 2.0}'

# Get leaderboard
curl "http://localhost:8000/api/guilds/123456789/leaderboard?limit=5"
```

---

## 🔄 CORS Configuration

The API allows requests from:
- `http://localhost:3000` (Next.js dashboard development)
- `http://localhost:5173` (Vite development)

For production, update `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.yourbot.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📝 Notes

- All Discord IDs are stored as `BIGINT` in the database but sent as `number` in JSON
- Timestamps are in ISO 8601 format with timezone
- The API shares the same database connection pool as the Discord bot
- Changes via API take effect immediately for the bot (no restart required)
- The API runs independently of the bot and can be scaled separately

---

## 🔮 Future Endpoints (Planned)

- `POST /api/guilds/{guild_id}/xp/grant` - Manually grant XP to a user
- `DELETE /api/guilds/{guild_id}/xp/reset` - Reset all XP for a guild
- `GET /api/guilds/{guild_id}/users/{user_id}/xp` - Get specific user's XP
- `GET /api/guilds/{guild_id}/analytics` - Advanced analytics and charts
- `GET /api/guilds/{guild_id}/logs/recent` - Get recent log entries
- `POST /api/guilds/{guild_id}/backup` - Export guild data
- `POST /api/guilds/{guild_id}/restore` - Restore guild data from backup
