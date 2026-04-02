# Ataraxia Dashboard - Frontend Specification

## 🎯 Projekt-Übersicht

Du baust ein **Web-Dashboard** für einen Discord Bot. User können hier ihre Server-Einstellungen verwalten.

---

## 📋 Was du bauen sollst

### **1. Dashboard Pages**

#### **A) Login-Seite** (`/`)
- Discord OAuth Login Button
- Nach Login → Redirect zu `/dashboard`

#### **B) Server-Auswahl** (`/dashboard`)
- Liste aller Server wo der User Admin ist
- Klick auf Server → `/dashboard/[guild_id]`

#### **C) Server-Dashboard** (`/dashboard/[guild_id]`)
Tabs/Sections:
1. **XP Settings** - XP Einstellungen
2. **Multipliers** - XP Multiplikatoren
3. **Log Channels** - Log-Kanäle
4. **Leaderboard** - Top User
5. **Stats** - Statistiken (optional)

---

## 🔌 API Endpoints (Backend bereitgestellt)

### **Base URL:** `http://localhost:8000`

### **Interaktive Dokumentation:** 
Starte Backend mit `uvicorn api.main:app --reload`
Dann gehe zu: **http://localhost:8000/docs**

Da siehst du ALLE Endpoints mit Beispielen!

---

## 📊 Seiten-Details

### **1. XP Settings Tab**

**Was angezeigt werden soll:**

```
┌─────────────────────────────────────┐
│ XP Settings                         │
├─────────────────────────────────────┤
│ Message XP Cooldown                 │
│ [60] seconds       [Save]           │
│                                     │
│ Voice XP Interval                   │
│ [180] seconds      [Save]           │
│                                     │
│ Message XP Range                    │
│ Min: [10]  Max: [20]   [Save]      │
│                                     │
│ Voice XP Range                      │
│ Min: [15]  Max: [25]   [Save]      │
└─────────────────────────────────────┘
```

**API Calls:**

```javascript
// GET Settings beim Laden
GET /api/guilds/{guild_id}/xp/settings
// Response: { message_cooldown: 60, voice_interval: 180, ... }

// UPDATE Cooldown
PUT /api/guilds/{guild_id}/xp/cooldown
Body: { cooldown: 120 }

// UPDATE Voice Interval
PUT /api/guilds/{guild_id}/xp/voice-interval
Body: { interval: 300 }

// UPDATE Message XP
PUT /api/guilds/{guild_id}/xp/message-xp
Body: { min_xp: 15, max_xp: 30 }

// UPDATE Voice XP
PUT /api/guilds/{guild_id}/xp/voice-xp
Body: { min_xp: 20, max_xp: 40 }
```

---

### **2. Multipliers Tab**

**Was angezeigt werden soll:**

```
┌─────────────────────────────────────┐
│ Channel Multipliers                 │
├─────────────────────────────────────┤
│ #general          2.0x    [Remove]  │
│ #events           1.5x    [Remove]  │
│                                     │
│ [+ Add Channel Multiplier]          │
├─────────────────────────────────────┤
│ Role Multipliers                    │
├─────────────────────────────────────┤
│ @VIP              1.5x    [Remove]  │
│ @Premium          2.0x    [Remove]  │
│                                     │
│ [+ Add Role Multiplier]             │
├─────────────────────────────────────┤
│ 💎 Server Booster Bonus: 1.5x       │
│    (automatic)                      │
└─────────────────────────────────────┘
```

**API Calls:**

```javascript
// GET Channel Multipliers
GET /api/guilds/{guild_id}/multipliers/channels
// Response: [{ channel_id: 123, multiplier: 2.0 }, ...]

// ADD Channel Multiplier
POST /api/guilds/{guild_id}/multipliers/channels
Body: { channel_id: 123456789, multiplier: 2.0 }

// REMOVE Channel Multiplier
DELETE /api/guilds/{guild_id}/multipliers/channels/{channel_id}

// GET Role Multipliers
GET /api/guilds/{guild_id}/multipliers/roles
// Response: [{ role_id: 456, multiplier: 1.5 }, ...]

// ADD Role Multiplier
POST /api/guilds/{guild_id}/multipliers/roles
Body: { role_id: 987654321, multiplier: 1.5 }

// REMOVE Role Multiplier
DELETE /api/guilds/{guild_id}/multipliers/roles/{role_id}
```

**Wichtig:** Channel/Role Namen musst du von Discord API holen (siehe unten)

---

### **3. Log Channels Tab**

**Was angezeigt werden soll:**

```
┌─────────────────────────────────────┐
│ Log Channels                        │
├─────────────────────────────────────┤
│ Message Logs (Edit/Delete)          │
│ [Select Channel ▼] [Save]           │
│ Current: #mod-logs                  │
│                                     │
│ Voice Logs (Join/Leave/Switch)      │
│ [Select Channel ▼] [Save]           │
│ Current: #voice-logs                │
│                                     │
│ Level Up Logs                       │
│ [Select Channel ▼] [Save]           │
│ Current: #level-ups                 │
└─────────────────────────────────────┘
```

**API Calls:**

```javascript
// GET All Log Channels
GET /api/guilds/{guild_id}/logs
// Response: { message_log_channel_id: 123, voice_log_channel_id: 456, ... }

// SET Message Log Channel
PUT /api/guilds/{guild_id}/logs/messages
Body: { channel_id: 123456789 }

// SET Voice Log Channel
PUT /api/guilds/{guild_id}/logs/voice
Body: { channel_id: 123456789 }

// SET Level Log Channel
PUT /api/guilds/{guild_id}/logs/levels
Body: { channel_id: 123456789 }
```

---

### **4. Leaderboard Tab**

**Was angezeigt werden soll:**

```
┌─────────────────────────────────────┐
│ Top 10 Users                        │
├─────────────────────────────────────┤
│ 1. 👑 Username#1234                 │
│    Level 25 | 12,450 XP             │
│                                     │
│ 2. Username#5678                    │
│    Level 22 | 10,230 XP             │
│                                     │
│ ... (10 entries)                    │
└─────────────────────────────────────┘
```

**API Calls:**

```javascript
// GET Leaderboard
GET /api/guilds/{guild_id}/leaderboard?limit=10
// Response: [{ user_id: 123, xp: 12450, level: 25 }, ...]
```

**Wichtig:** User Namen musst du von Discord API holen (siehe unten)

---

## 🔐 Discord API (für Channel/Role/User Namen)

**Du brauchst die Discord Bot Guild API:**

```javascript
// Channels im Server
GET https://discord.com/api/v10/guilds/{guild_id}/channels
Headers: { Authorization: "Bot YOUR_BOT_TOKEN" }

// Roles im Server
GET https://discord.com/api/v10/guilds/{guild_id}/roles
Headers: { Authorization: "Bot YOUR_BOT_TOKEN" }

// User Info
GET https://discord.com/api/v10/users/{user_id}
Headers: { Authorization: "Bot YOUR_BOT_TOKEN" }
```

**Alternative:** Ich kann dir einen Proxy-Endpoint bauen, dann musst du nicht direkt mit Discord API arbeiten.

---

## 🎨 Design

**Empfohlene UI Libraries:**
- **Tailwind CSS** (Styling)
- **shadcn/ui** oder **DaisyUI** (Components)
- **Lucide Icons** (Icons)

**Farbschema:**
- Primary: Discord Blurple (#5865F2)
- Dark Theme (Discord-ähnlich)

---

## 🔧 Tech Stack

**Was du nutzen sollst:**
- **Next.js 14** (React Framework)
- **TypeScript** (empfohlen, aber optional)
- **Tailwind CSS** (Styling)
- **Axios** oder **fetch** (API Calls)

**Installation:**
```bash
npx create-next-app@latest ataraxia-dashboard
cd ataraxia-dashboard
npm install axios
npm run dev
```

---

## 📝 Code-Beispiele

### **API Call mit Axios:**

```typescript
// lib/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api'
})

// Get XP Settings
export async function getXPSettings(guildId: string) {
  const { data } = await api.get(`/guilds/${guildId}/xp/settings`)
  return data
}

// Update Cooldown
export async function updateCooldown(guildId: string, cooldown: number) {
  const { data } = await api.put(`/guilds/${guildId}/xp/cooldown`, { cooldown })
  return data
}
```

### **React Component Beispiel:**

```typescript
// components/XPSettings.tsx
import { useState, useEffect } from 'react'
import { getXPSettings, updateCooldown } from '@/lib/api'

export default function XPSettings({ guildId }) {
  const [settings, setSettings] = useState(null)
  const [cooldown, setCooldown] = useState(60)

  useEffect(() => {
    // Load settings when component mounts
    getXPSettings(guildId).then(data => {
      setSettings(data)
      setCooldown(data.message_cooldown)
    })
  }, [guildId])

  const handleSave = async () => {
    await updateCooldown(guildId, cooldown)
    alert('Saved!')
  }

  if (!settings) return <div>Loading...</div>

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">XP Settings</h2>
      
      <div className="mb-4">
        <label className="block mb-2">Message XP Cooldown (seconds)</label>
        <input
          type="number"
          value={cooldown}
          onChange={(e) => setCooldown(Number(e.target.value))}
          className="border p-2 rounded"
        />
        <button onClick={handleSave} className="ml-2 bg-blue-500 text-white px-4 py-2 rounded">
          Save
        </button>
      </div>
      
      {/* Add more settings here */}
    </div>
  )
}
```

---

## 🚀 Nächste Schritte

1. **Starte Backend:**
   ```bash
   cd Ataraxia
   uvicorn api.main:app --reload
   ```
   Gehe zu http://localhost:8000/docs

2. **Erstelle Next.js Projekt:**
   ```bash
   npx create-next-app@latest ataraxia-dashboard
   ```

3. **Baue eine Page nach der anderen:**
   - Start mit XP Settings (einfachste)
   - Dann Multipliers
   - Dann Log Channels
   - Dann Leaderboard

4. **Test mit echten Daten:**
   - Nutze deine echte Guild ID
   - Teste alle API Endpoints

---

## 📞 Support

Wenn du Fragen hast:
1. Schau in `/docs` (interaktive API Doku)
2. Teste Endpoints mit Postman/Insomnia
3. Frag mich (ich helfe bei Backend/API)

---

## ✅ Checkliste

- [ ] Next.js Setup
- [ ] API Client erstellt (lib/api.ts)
- [ ] Login Page (Discord OAuth)
- [ ] Server Selector
- [ ] XP Settings Tab
- [ ] Multipliers Tab
- [ ] Log Channels Tab
- [ ] Leaderboard Tab
- [ ] Styling/Design
- [ ] Mobile Responsive
- [ ] Deployment

**Viel Erfolg! 🚀**
