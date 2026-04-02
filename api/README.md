# Ataraxia Bot - REST API

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd api
pip install -r requirements.txt
```

### 2. Start API Server
```bash
# From Ataraxia directory:
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open API Documentation
Go to: **http://localhost:8000/docs**

You'll see interactive API documentation with all endpoints!

---

## 📋 API Endpoints Overview

### **XP Settings**
- `GET /api/guilds/{guild_id}/xp/settings` - Get all XP settings
- `PUT /api/guilds/{guild_id}/xp/cooldown` - Update message cooldown
- `PUT /api/guilds/{guild_id}/xp/voice-interval` - Update voice interval
- `PUT /api/guilds/{guild_id}/xp/message-xp` - Update message XP range
- `PUT /api/guilds/{guild_id}/xp/voice-xp` - Update voice XP range

### **Multipliers**
- `GET /api/guilds/{guild_id}/multipliers/channels` - Get channel multipliers
- `POST /api/guilds/{guild_id}/multipliers/channels` - Add channel multiplier
- `DELETE /api/guilds/{guild_id}/multipliers/channels/{channel_id}` - Remove channel multiplier
- `GET /api/guilds/{guild_id}/multipliers/roles` - Get role multipliers
- `POST /api/guilds/{guild_id}/multipliers/roles` - Add role multiplier
- `DELETE /api/guilds/{guild_id}/multipliers/roles/{role_id}` - Remove role multiplier

### **Log Channels**
- `GET /api/guilds/{guild_id}/logs` - Get all log channels
- `PUT /api/guilds/{guild_id}/logs/messages` - Set message log channel
- `PUT /api/guilds/{guild_id}/logs/voice` - Set voice log channel
- `PUT /api/guilds/{guild_id}/logs/levels` - Set level log channel

### **Leaderboard**
- `GET /api/guilds/{guild_id}/leaderboard?limit=10` - Get top users

---

## 🧪 Testing with cURL

```bash
# Get XP Settings
curl http://localhost:8000/api/guilds/123456789/xp/settings

# Update Cooldown
curl -X PUT http://localhost:8000/api/guilds/123456789/xp/cooldown \
  -H "Content-Type: application/json" \
  -d '{"cooldown": 120}'

# Get Channel Multipliers
curl http://localhost:8000/api/guilds/123456789/multipliers/channels

# Add Channel Multiplier
curl -X POST http://localhost:8000/api/guilds/123456789/multipliers/channels \
  -H "Content-Type: application/json" \
  -d '{"channel_id": 987654321, "multiplier": 2.0}'
```

---

## 🔧 Development

### Run in Dev Mode
```bash
uvicorn api.main:app --reload
```

### Run in Production
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## 📝 Notes

- CORS is configured for `http://localhost:3000` and `http://localhost:5173` (common frontend ports)
- All endpoints require a valid guild_id
- Database connection is initialized on startup
- See `/docs` for interactive API testing and full documentation
