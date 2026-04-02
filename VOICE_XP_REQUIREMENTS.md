# Voice XP Requirements - Neue Features

## 🎯 Übersicht

Ich habe ein komplett konfigurierbares System für Voice XP Anforderungen implementiert. Admins können jetzt genau steuern, unter welchen Bedingungen User Voice XP bekommen.

## 📊 Was wurde hinzugefügt?

### 1. **Neue Datenbank-Tabelle**
- `voice_xp_requirements` - Speichert pro Server die Einstellungen
- 4 Konfigurationsoptionen:
  - `require_non_afk` - Müssen User nicht-AFK sein?
  - `require_non_deaf` - Müssen User nicht-taub sein?
  - `require_non_muted` - Müssen User nicht-stumm sein?
  - `require_others_in_channel` - Müssen andere User im Channel sein?

### 2. **Neue Discord Commands**
Alle Commands unter `/voicexp-requirements`:

- `/voicexp-requirements view` - Zeigt aktuelle Einstellungen
- `/voicexp-requirements set-afk [allow]` - AFK-User XP erlauben/verbieten
- `/voicexp-requirements set-deaf [allow]` - Tauben-User XP erlauben/verbieten
- `/voicexp-requirements set-muted [allow]` - Stummen-User XP erlauben/verbieten
- `/voicexp-requirements set-alone [allow]` - Allein-im-Channel XP erlauben/verbieten
- `/voicexp-requirements reset` - Auf Standardeinstellungen zurücksetzen

### 3. **API-Endpunkte**
- `GET /api/guilds/{guild_id}/voicexp/requirements` - Aktuelle Einstellungen abrufen
- `PUT /api/guilds/{guild_id}/voicexp/requirements` - Alle Einstellungen auf einmal ändern
- `PATCH /api/guilds/{guild_id}/voicexp/requirements` - Einzelne Einstellung ändern

### 4. **Dashboard-Integration**
- Neue Route: `/dashboard/app/api/voicexp/requirements/route.ts`
- Unterstützt Mock-Modus für lokale Entwicklung
- Bereit für Frontend-Integration

## 🔧 Technische Details

### Datenbank-Funktionen (database_pg.py)
```python
await db.get_voice_xp_requirements(guild_id)  # Einstellungen abrufen
await db.set_voice_xp_requirement(guild_id, 'require_non_afk', True)  # Einzeln setzen
await db.set_all_voice_xp_requirements(guild_id, ...)  # Alle auf einmal setzen
```

### Standard-Einstellungen
- ✅ `require_non_afk` = True (AFK-User bekommen KEINE XP)
- ✅ `require_non_deaf` = True (Taube User bekommen KEINE XP)
- ❌ `require_non_muted` = False (Stumme User bekommen XP)
- ✅ `require_others_in_channel` = True (Allein-im-Channel = KEINE XP)

### Bug-Fixes inklusive!
Das System behebt auch den ursprünglichen Bug:
- Wenn eine 2. Person einem Channel beitritt, bekommt die erste Person jetzt auch XP
- Wenn jemand einen Channel verlässt und nur 1 Person übrig bleibt, wird deren Session beendet
- Bots werden korrekt ignoriert
- **Beim Bot-Restart werden alle Voice Sessions synchronisiert** - User die bereits in Voice Channels sind bekommen automatisch Sessions erstellt

## 🚀 Verwendung

### Als Discord Admin:
```
1. /voicexp-requirements view
   → Zeigt aktuelle Einstellungen

2. /voicexp-requirements set-alone true
   → User bekommen jetzt auch XP wenn sie alleine sind

3. /voicexp-requirements set-deaf false
   → Taube User bekommen jetzt KEINE XP mehr

4. /voicexp-requirements reset
   → Zurück zu den Standardeinstellungen
```

### Als API-Nutzer:
```bash
# Einstellungen abrufen
GET http://localhost:8000/api/guilds/123456789/voicexp/requirements

# Einzelne Einstellung ändern
PATCH http://localhost:8000/api/guilds/123456789/voicexp/requirements
{
  "requirement": "require_non_afk",
  "value": false
}

# Alle Einstellungen ändern
PUT http://localhost:8000/api/guilds/123456789/voicexp/requirements
{
  "require_non_afk": true,
  "require_non_deaf": true,
  "require_non_muted": false,
  "require_others_in_channel": true
}
```

## 📝 Geänderte Dateien

1. ✅ `core/database_pg.py` - Neue Tabelle + Funktionen
2. ✅ `events/on_voice_state_update.py` - Bug-Fixes + Requirements-Check
3. ✅ `utils/voice_xp.py` - Requirements-basierte XP-Vergabe
4. ✅ `cogs/voice_xp_requirements.py` - Neuer Command-Cog
5. ✅ `api/main.py` - Neue API-Endpunkte
6. ✅ `dashboard/app/api/voicexp/requirements/route.ts` - Dashboard-Route

## ✨ Next Steps

Für das Dashboard brauchst du noch:
1. Frontend-Komponente für die Einstellungen
2. Integration in die XP-Settings-Seite
3. Toggle-Switches für die 4 Optionen

Möchtest du, dass ich das auch noch erstelle?
