# Ataraxia Dashboard API

A small web service (`api/`) that lets server administrators change bot
settings in the browser. It serves both a JSON API and a ready-to-use web page.

* **Login** is Discord OAuth2 (`identify guilds`). The browser only receives an
  opaque session cookie; Discord tokens stay on the server.
* **Per server**: every request for a server checks with Discord that the
  logged-in user is the owner or has the *Administrator* permission there, and
  that the bot is a member. Channel and role IDs are checked against that server.
* **Same database as the bot**: the API reads and writes the bot's PostgreSQL
  tables. Each change is recorded in `dashboard_changes`; the bot
  (`bot/cogs/core/dashboard_sync.py`) checks that table every 10 seconds and
  drops its cached settings for the server, so changes apply within seconds
  and no restart is needed.

## Setup

1. In the [Discord Developer Portal](https://discord.com/developers/applications)
   open the bot's application → **OAuth2**:
   * copy the **Client Secret**
   * add the redirect `<DASHBOARD_BASE_URL>/auth/callback`
     (for example `https://ataraxia-bot.com/dashboard/auth/callback`)
2. Add to `.env` (next to `BOT_TOKEN` and `DATABASE_URL`, which the API also uses):

   ```env
   DISCORD_CLIENT_SECRET=...
   DASHBOARD_BASE_URL=https://ataraxia-bot.com/dashboard
   ```

   Optional: `DISCORD_CLIENT_ID` (default: taken from the bot token),
   `API_DB_POOL_MAX` (default 3 database connections), `DASHBOARD_SESSION_DAYS` (default 7).
3. Install and run:

   ```bash
   python -m venv venv-api && venv-api/bin/pip install -r api/requirements.txt
   venv-api/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```

   For the server there is a systemd unit (`deploy/ataraxia-api.service`) and an
   nginx snippet (`deploy/nginx-dashboard.conf`).

`GET /health` reports whether the database is reachable and whether login is configured.

## Endpoints

All IDs are **strings** in requests and responses (Discord IDs do not fit into
a JavaScript number). Requests that change something must send the header
`X-Requested-With: ataraxia-dashboard`. Errors are `{"detail": "message"}`.
Interactive documentation: `/api/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/login` | Start the Discord login |
| GET | `/auth/callback` | Discord returns here |
| POST | `/auth/logout` | End the session |
| GET | `/api/me` | Logged-in user |
| GET | `/api/guilds` | Servers the user administers, with `bot_present` |
| GET | `/api/guilds/{id}` | Server name, roles (`assignable`), channels |
| GET, PUT | `/api/guilds/{id}/xp` | XP amounts, cooldown, voice interval |
| GET, PUT | `/api/guilds/{id}/voice-requirements` | Conditions for voice XP |
| GET | `/api/guilds/{id}/multipliers` | Channel and role XP multipliers |
| PUT, DELETE | `/api/guilds/{id}/multipliers/{channels\|roles}/{target_id}` | Set (`{"multiplier": 2}`) or remove one |
| GET, PUT | `/api/guilds/{id}/logs` | Log channels; only sent fields change, `null` clears; `level_disabled` turns level-up messages off |
| GET | `/api/guilds/{id}/level-roles` | Level rewards |
| PUT, DELETE | `/api/guilds/{id}/level-roles/{level}` | Set (`{"role_id": "..."}`) or remove one |
| GET, PUT | `/api/guilds/{id}/auto-roles` | `enabled`, `user_role_ids`, `bot_role_ids` |
| GET | `/api/guilds/{id}/leaderboard?limit=&offset=` | XP ranking |

Status codes: `401` not logged in, `403` not an administrator of that server
(or a forged request), `404` the bot is not in that server, `422` invalid
input, `503` Discord or the database is unreachable.

## Tests

```bash
docker run -d --rm --name ataraxia-test-pg --network host -e POSTGRES_PASSWORD=test \
    -e POSTGRES_DB=ataraxia_test postgres:15-alpine -c port=55432 -c listen_addresses=127.0.0.1
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/ataraxia_test .venv/bin/python -m pytest
```

The API tests create the schema with the bot's own `init_db`, talk to a fake
Discord, and read results back through the bot's database functions. They only
run against a database on localhost. `tests/dev_server.py` starts the dashboard
with the fake Discord for trying the web page by hand.

## Adding a setting

1. Add the queries to `api/db.py` and call `_mark_changed` in the same transaction.
2. Add a request model to `api/schemas.py` and the routes to `api/main.py`
   (use the `guild_access` dependency: it does all permission checks).
3. If the bot caches that setting, handle the scope in `DashboardSyncCog.apply_change`.
4. Add a tab in `api/static/app.js`.
