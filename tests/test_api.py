"""End-to-end tests of the dashboard API against a real PostgreSQL database.

Discord is replaced by a fake; the database schema is created by the bot's own
``init_db`` and results are read back through the bot's own database
functions, so these tests prove that the bot sees what the dashboard writes.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio

from api.auth import CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE
from api.config import Settings
from api.main import create_app

BOT_ID = "900000000000000001"
GUILD_A = "1508769238557659218"      # user is admin, bot is in it (ID beyond JS number precision)
GUILD_B = "1508769238557659219"      # user is a normal member, bot is in it
GUILD_C = "1508769238557659220"      # user is owner, bot is NOT in it
GUILD_D = "1508769238557659221"      # user is not a member at all, bot is in it
USER = {"id": "700000000000000007", "username": "admin", "avatar": None}

ROLE_EVERYONE = GUILD_A
ROLE_LOW = "800000000000000001"
ROLE_HIGH = "800000000000000002"     # above the bot
ROLE_MANAGED = "800000000000000003"
ROLE_BOT = "800000000000000004"
CH_TEXT = "810000000000000001"
CH_VOICE = "810000000000000002"
CH_OTHER_GUILD = "810000000000000099"

H = {CSRF_HEADER: CSRF_VALUE}


class FakeDiscord:
    def __init__(self):
        self.valid_tokens = {"access-1"}
        self.refreshable = True
        self.calls = []

    def guild(self, gid):
        return {
            "id": gid, "name": f"Guild {gid[-1]}", "icon": None,
            "roles": [
                {"id": gid, "name": "@everyone", "position": 0, "managed": False, "color": 0},
                {"id": ROLE_LOW, "name": "member", "position": 1, "managed": False, "color": 0},
                {"id": ROLE_MANAGED, "name": "booster", "position": 2, "managed": True, "color": 0},
                {"id": ROLE_BOT, "name": "Ataraxia", "position": 3, "managed": True, "color": 0},
                {"id": ROLE_HIGH, "name": "owner", "position": 4, "managed": False, "color": 0},
            ],
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v10")
        auth = request.headers.get("authorization", "")
        self.calls.append((request.method, path))

        if path == "/oauth2/token":
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"] and form["code"] == ["good-code"]:
                return httpx.Response(200, json={"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3600})
            if form["grant_type"] == ["refresh_token"] and self.refreshable:
                self.valid_tokens.add("access-2")
                return httpx.Response(200, json={"access_token": "access-2", "refresh_token": "refresh-2", "expires_in": 3600})
            return httpx.Response(400, json={"error": "invalid_grant"})
        if path == "/oauth2/token/revoke":
            return httpx.Response(200, json={})

        if auth.startswith("Bearer "):
            if auth.removeprefix("Bearer ") not in self.valid_tokens:
                return httpx.Response(401, json={"message": "401: Unauthorized"})
            if path == "/users/@me":
                return httpx.Response(200, json=USER)
            if path == "/users/@me/guilds":
                return httpx.Response(200, json=[
                    {"id": GUILD_A, "name": "Alpha", "icon": None, "owner": False, "permissions": str(0x8 | 0x400)},
                    {"id": GUILD_B, "name": "Beta", "icon": None, "owner": False, "permissions": str(0x400 | 0x20)},
                    {"id": GUILD_C, "name": "Gamma", "icon": None, "owner": True, "permissions": "0"},
                ])

        if auth == "Bot bot-token":
            if path == "/users/@me":
                return httpx.Response(200, json={"id": BOT_ID})
            match = re.fullmatch(r"/guilds/(\d+)(/channels|/members/\d+)?", path)
            if match:
                gid, sub = match.groups()
                if gid == GUILD_C:
                    return httpx.Response(404, json={"message": "Unknown Guild"})
                if sub is None:
                    return httpx.Response(200, json=self.guild(gid))
                if sub == "/channels":
                    return httpx.Response(200, json=[
                        {"id": CH_TEXT, "name": "general", "type": 0, "position": 0},
                        {"id": CH_VOICE, "name": "Voice", "type": 2, "position": 1},
                    ])
                return httpx.Response(200, json={"roles": [ROLE_BOT]})
        return httpx.Response(404, json={"message": "not found"})


@pytest_asyncio.fixture
async def env(test_database_url):
    # The bot's database module loads .env on import. Make sure it can only
    # ever see the test database.
    os.environ["DATABASE_URL"] = test_database_url
    from core import database_pg as botdb

    await botdb.init_db()
    assert botdb._pool is not None
    async with botdb._pool.acquire() as conn:
        assert await conn.fetchval("SELECT current_database()") == urlparse(test_database_url).path.lstrip("/")
        await conn.execute(
            "TRUNCATE xp_settings, voice_xp_requirements, xp_channel_multipliers, xp_role_multipliers, "
            "guild_settings, level_roles, autorole_settings, user_levels, discord_users, discord_servers, "
            "dashboard_changes"
        )
        await conn.execute("DROP TABLE IF EXISTS dashboard_sessions")
        await conn.executemany(
            "INSERT INTO discord_servers (guild_id, server_name) VALUES ($1, $2)",
            [(int(GUILD_A), "Alpha"), (int(GUILD_B), "Beta"), (int(GUILD_D), "Delta")],
        )

    discord = FakeDiscord()
    settings = Settings(
        database_url=test_database_url, bot_token="bot-token", client_id="123456789012345678",
        client_secret="secret", base_url="http://dash.test", discord_api_base="https://discord.test/api/v10",
    )
    app = create_app(settings, discord_transport=httpx.MockTransport(discord))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://dash.test") as client:
            yield type("Env", (), {"client": client, "discord": discord, "botdb": botdb, "app": app})
    await botdb.close_db()


async def login(env):
    response = await env.client.get("/auth/login")
    assert response.status_code == 302
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    response = await env.client.get("/auth/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 302 and response.headers["location"] == "http://dash.test/"
    assert env.client.cookies.get(SESSION_COOKIE)


@pytest.mark.asyncio
async def test_everything_requires_login(env):
    for path in ("/api/me", "/api/guilds", f"/api/guilds/{GUILD_A}", f"/api/guilds/{GUILD_A}/xp"):
        assert (await env.client.get(path)).status_code == 401, path
    response = await env.client.put(f"/api/guilds/{GUILD_A}/xp", json={}, headers=H)
    assert response.status_code == 401
    assert (await env.client.get("/health")).json()["database"] is True


@pytest.mark.asyncio
async def test_login_flow(env):
    response = await env.client.get("/auth/login")
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["client_id"] == ["123456789012345678"]
    assert query["redirect_uri"] == ["http://dash.test/auth/callback"]
    assert query["scope"] == ["identify guilds"]
    assert "httponly" in response.headers["set-cookie"].lower()

    # A forged state must not create a session.
    response = await env.client.get("/auth/callback", params={"code": "good-code", "state": "forged"})
    assert response.headers["location"].endswith("?login=failed")
    assert not env.client.cookies.get(SESSION_COOKIE)

    # A rejected code must not create a session either.
    response = await env.client.get("/auth/login")
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    response = await env.client.get("/auth/callback", params={"code": "bad", "state": state})
    assert response.headers["location"].endswith("?login=failed")
    assert not env.client.cookies.get(SESSION_COOKIE)

    await login(env)
    me = (await env.client.get("/api/me")).json()
    assert me == {"id": USER["id"], "username": "admin", "avatar": None}

    # Only a hash of the session ID is stored.
    async with env.botdb._pool.acquire() as conn:
        stored = await conn.fetchval("SELECT token_hash FROM dashboard_sessions")
    assert stored != env.client.cookies.get(SESSION_COOKIE) and len(stored) == 64

    assert (await env.client.post("/auth/logout", headers=H)).status_code == 200
    assert (await env.client.get("/api/me")).status_code == 401


@pytest.mark.asyncio
async def test_guild_list_and_access_control(env):
    await login(env)
    data = (await env.client.get("/api/guilds")).json()
    assert [(g["id"], g["bot_present"]) for g in data["guilds"]] == [(GUILD_A, True), (GUILD_C, False)]

    assert (await env.client.get(f"/api/guilds/{GUILD_A}/xp")).status_code == 200
    # member without administrator (has Manage Server only)
    assert (await env.client.get(f"/api/guilds/{GUILD_B}/xp")).status_code == 403
    # not a member at all
    assert (await env.client.get(f"/api/guilds/{GUILD_D}/xp")).status_code == 403
    # owner, but the bot is not there
    assert (await env.client.get(f"/api/guilds/{GUILD_C}/xp")).status_code == 404
    assert (await env.client.get("/api/guilds/abc/xp")).status_code == 422

    body = {"message_cooldown": 5, "voice_interval": 60, "message_xp_min": 1, "message_xp_max": 2,
            "voice_xp_min": 1, "voice_xp_max": 2}
    for gid in (GUILD_B, GUILD_D):
        assert (await env.client.put(f"/api/guilds/{gid}/xp", json=body, headers=H)).status_code == 403
        assert await env.botdb.get_xp_cooldown(int(gid)) == 60  # untouched

    meta = (await env.client.get(f"/api/guilds/{GUILD_A}")).json()
    assert meta["id"] == GUILD_A
    assignable = {r["name"]: r["assignable"] for r in meta["roles"]}
    assert assignable == {"owner": False, "Ataraxia": False, "booster": False, "member": True, "@everyone": False}
    assert [c["type"] for c in meta["channels"]] == ["text", "voice"]


@pytest.mark.asyncio
async def test_csrf_protection(env):
    await login(env)
    body = {"message_cooldown": 5, "voice_interval": 60, "message_xp_min": 1, "message_xp_max": 2,
            "voice_xp_min": 1, "voice_xp_max": 2}
    url = f"/api/guilds/{GUILD_A}/xp"
    assert (await env.client.put(url, json=body)).status_code == 403
    assert (await env.client.put(url, json=body, headers={**H, "Origin": "https://evil.example"})).status_code == 403
    assert (await env.client.post("/auth/logout")).status_code == 403
    assert (await env.client.put(url, json=body, headers={**H, "Origin": "http://dash.test"})).status_code == 200


@pytest.mark.asyncio
async def test_xp_settings_reach_the_bot(env):
    await login(env)
    url = f"/api/guilds/{GUILD_A}/xp"
    assert (await env.client.get(url)).json() == {
        "message_cooldown": 60, "voice_interval": 60, "message_xp_min": 10, "message_xp_max": 20,
        "voice_xp_min": 15, "voice_xp_max": 25}

    body = {"message_cooldown": 30, "voice_interval": 120, "message_xp_min": 5, "message_xp_max": 50,
            "voice_xp_min": 3, "voice_xp_max": 9}
    response = await env.client.put(url, json=body, headers=H)
    assert response.status_code == 200 and response.json() == body

    seen_by_bot = await env.botdb.get_all_xp_settings(int(GUILD_A))
    assert {k: seen_by_bot[k] for k in body} == body
    assert await env.botdb.get_message_xp_range(int(GUILD_A)) == (5, 50)

    for bad in (
        {**body, "message_xp_min": 60},            # min > max
        {**body, "voice_interval": 10},            # too short
        {**body, "message_cooldown": -1},
        {**body, "message_xp_max": 5000},
        {**body, "message_xp_max": "many"},
        {**body, "unknown": 1},
        {k: v for k, v in body.items() if k != "voice_xp_max"},
    ):
        response = await env.client.put(url, json=bad, headers=H)
        assert response.status_code == 422 and isinstance(response.json()["detail"], str), bad
    assert (await env.client.get(url)).json() == body


@pytest.mark.asyncio
async def test_voice_requirements(env):
    await login(env)
    url = f"/api/guilds/{GUILD_A}/voice-requirements"
    body = {"require_non_afk": False, "require_non_deaf": False, "require_non_muted": True,
            "require_others_in_channel": False}
    assert (await env.client.put(url, json=body, headers=H)).json() == body
    assert await env.botdb.get_voice_xp_requirements(int(GUILD_A)) == body


@pytest.mark.asyncio
async def test_multipliers(env):
    await login(env)
    base = f"/api/guilds/{GUILD_A}/multipliers"
    response = await env.client.put(f"{base}/channels/{CH_TEXT}", json={"multiplier": 2.5}, headers=H)
    assert response.json()["channels"] == [{"id": CH_TEXT, "multiplier": 2.5}]
    await env.client.put(f"{base}/roles/{ROLE_LOW}", json={"multiplier": 1.5}, headers=H)

    assert await env.botdb.get_channel_multiplier(int(GUILD_A), int(CH_TEXT)) == 2.5
    assert await env.botdb.get_all_role_multipliers(int(GUILD_A)) == [(int(ROLE_LOW), 1.5)]

    # channels/roles of other servers are refused
    assert (await env.client.put(f"{base}/channels/{CH_OTHER_GUILD}", json={"multiplier": 2}, headers=H)).status_code == 422
    assert (await env.client.put(f"{base}/roles/{CH_TEXT}", json={"multiplier": 2}, headers=H)).status_code == 422
    assert (await env.client.put(f"{base}/channels/{CH_TEXT}", json={"multiplier": 11}, headers=H)).status_code == 422
    assert (await env.client.put(f"{base}/users/{CH_TEXT}", json={"multiplier": 2}, headers=H)).status_code == 404

    response = await env.client.delete(f"{base}/channels/{CH_TEXT}", headers=H)
    assert response.json()["channels"] == []
    assert await env.botdb.get_channel_multiplier(int(GUILD_A), int(CH_TEXT)) == 1.0


@pytest.mark.asyncio
async def test_log_channels(env):
    await login(env)
    url = f"/api/guilds/{GUILD_A}/logs"
    response = await env.client.put(url, json={"message": CH_TEXT, "mod": CH_TEXT}, headers=H)
    assert response.status_code == 200
    assert response.json()["message"] == CH_TEXT and response.json()["voice"] is None
    assert await env.botdb.get_log_channel_id(int(GUILD_A)) == int(CH_TEXT)
    assert await env.botdb.get_mod_log_channel_id(int(GUILD_A)) == int(CH_TEXT)

    # partial update leaves the rest alone; null clears
    response = await env.client.put(url, json={"message": None}, headers=H)
    assert response.json()["message"] is None and response.json()["mod"] == CH_TEXT
    assert await env.botdb.get_log_channel_id(int(GUILD_A)) is None

    assert (await env.client.put(url, json={"voice": CH_VOICE}, headers=H)).status_code == 422
    assert (await env.client.put(url, json={"voice": CH_OTHER_GUILD}, headers=H)).status_code == 422
    assert (await env.client.put(url, json={"voice": int(CH_TEXT)}, headers=H)).status_code == 422  # IDs are strings

    response = await env.client.put(url, json={"level_disabled": True}, headers=H)
    assert response.json()["level_disabled"] is True and response.json()["level"] is None
    assert await env.botdb.get_level_log_channel_id(int(GUILD_A)) == 0   # what the bot treats as "off"
    response = await env.client.put(url, json={"level_disabled": False}, headers=H)
    assert response.json()["level_disabled"] is False
    assert await env.botdb.get_level_log_channel_id(int(GUILD_A)) is None


@pytest.mark.asyncio
async def test_level_roles(env):
    await login(env)
    base = f"/api/guilds/{GUILD_A}/level-roles"
    response = await env.client.put(f"{base}/5", json={"role_id": ROLE_LOW}, headers=H)
    assert response.json() == [{"level": 5, "role_id": ROLE_LOW}]
    assert await env.botdb.get_level_role(int(GUILD_A), 5) == int(ROLE_LOW)

    for role in (ROLE_HIGH, ROLE_MANAGED, ROLE_EVERYONE, CH_TEXT):
        response = await env.client.put(f"{base}/6", json={"role_id": role}, headers=H)
        assert response.status_code == 422, role
    assert (await env.client.put(f"{base}/0", json={"role_id": ROLE_LOW}, headers=H)).status_code == 422

    assert (await env.client.delete(f"{base}/5", headers=H)).json() == []
    assert await env.botdb.get_all_level_roles(int(GUILD_A)) == []


@pytest.mark.asyncio
async def test_auto_roles(env):
    await login(env)
    url = f"/api/guilds/{GUILD_A}/auto-roles"
    assert (await env.client.get(url)).json() == {"enabled": False, "user_role_ids": [], "bot_role_ids": []}
    body = {"enabled": True, "user_role_ids": [ROLE_LOW, ROLE_LOW], "bot_role_ids": []}
    response = await env.client.put(url, json=body, headers=H)
    assert response.json() == {"enabled": True, "user_role_ids": [ROLE_LOW], "bot_role_ids": []}

    seen_by_bot = await env.botdb.get_autorole_settings(int(GUILD_A))
    assert seen_by_bot["enabled"] is True and list(seen_by_bot["user_role_ids"]) == [int(ROLE_LOW)]

    bad = {"enabled": True, "user_role_ids": [ROLE_HIGH], "bot_role_ids": []}
    assert (await env.client.put(url, json=bad, headers=H)).status_code == 422

    # the bot's own commands keep working on what the dashboard wrote
    await env.botdb.remove_autorole(int(GUILD_A), int(ROLE_LOW), "user")
    assert (await env.client.get(url)).json()["user_role_ids"] == []


@pytest.mark.asyncio
async def test_leaderboard(env):
    await login(env)
    big_user = 1508769238557659999
    await env.botdb.add_xp(big_user, int(GUILD_A), 500)
    await env.botdb.add_xp(42, int(GUILD_A), 900)
    await env.botdb.add_xp(43, int(GUILD_B), 9999)
    async with env.botdb._pool.acquire() as conn:
        await conn.execute("INSERT INTO discord_users (user_id, username, global_name) VALUES ($1, 'bigu', 'Big U')", big_user)
    data = (await env.client.get(f"/api/guilds/{GUILD_A}/leaderboard", params={"limit": 10})).json()
    assert data["total"] == 2
    assert [(e["rank"], e["user_id"], e["username"], e["xp"]) for e in data["entries"]] == [
        (1, "42", None, 900), (2, str(big_user), "Big U", 500)]
    assert (await env.client.get(f"/api/guilds/{GUILD_A}/leaderboard", params={"limit": 1000})).status_code == 422


@pytest.mark.asyncio
async def test_bot_drops_its_cache_after_a_dashboard_change(env):
    from cogs.core.dashboard_sync import DashboardSyncCog

    class FakeCache:
        def __init__(self):
            self.settings, self.multipliers = [], []
        def invalidate_guild_settings(self, guild_id):
            self.settings.append(guild_id)
        def invalidate_multiplier_cache(self, guild_id):
            self.multipliers.append(guild_id)

    cache = FakeCache()
    cog = DashboardSyncCog(type("Bot", (), {"leveling_cache": cache})())
    assert await cog.poll_once() == 0          # first poll only sets the starting point

    await login(env)
    body = {"message_cooldown": 30, "voice_interval": 120, "message_xp_min": 5, "message_xp_max": 50,
            "voice_xp_min": 3, "voice_xp_max": 9}
    await env.client.put(f"/api/guilds/{GUILD_A}/xp", json=body, headers=H)
    await env.client.put(f"/api/guilds/{GUILD_A}/multipliers/roles/{ROLE_LOW}", json={"multiplier": 2}, headers=H)

    await cog.poll_once()
    assert set(cache.settings) == {int(GUILD_A)} and set(cache.multipliers) == {int(GUILD_A)}

    async with env.botdb._pool.acquire() as conn:
        who = await conn.fetchval("SELECT changed_by FROM dashboard_changes WHERE scope = 'xp'")
    assert who == int(USER["id"])


@pytest.mark.asyncio
async def test_expired_discord_token_is_refreshed_or_logs_out(env):
    await login(env)
    assert (await env.client.get("/api/guilds")).status_code == 200

    # Discord invalidates the access token; the refresh token still works.
    env.discord.valid_tokens.discard("access-1")
    env.app.state.sessions._guild_cache.clear()
    assert (await env.client.get("/api/guilds")).status_code == 200
    async with env.botdb._pool.acquire() as conn:
        assert await conn.fetchval("SELECT access_token FROM dashboard_sessions") == "access-2"

    # Access revoked completely: the session ends.
    env.discord.valid_tokens.clear()
    env.discord.refreshable = False
    env.app.state.sessions._guild_cache.clear()
    assert (await env.client.get("/api/guilds")).status_code == 401
    assert (await env.client.get("/api/me")).status_code == 401


@pytest.mark.asyncio
async def test_losing_admin_rights_locks_the_user_out(env):
    await login(env)
    assert (await env.client.get(f"/api/guilds/{GUILD_A}/xp")).status_code == 200

    def demoted(request):
        response = FakeDiscord.__call__(env.discord, request)
        if request.url.path.endswith("/users/@me/guilds"):
            return httpx.Response(200, json=[{"id": GUILD_A, "name": "Alpha", "owner": False, "permissions": "1024"}])
        return response
    env.app.state.discord.http._transport = httpx.MockTransport(demoted)
    env.app.state.sessions._guild_cache.clear()
    assert (await env.client.get(f"/api/guilds/{GUILD_A}/xp")).status_code == 403


@pytest.mark.asyncio
async def test_session_expiry(env):
    await login(env)
    async with env.botdb._pool.acquire() as conn:
        await conn.execute("UPDATE dashboard_sessions SET expires_at = $1", datetime.now(timezone.utc) - timedelta(seconds=1))
    assert (await env.client.get("/api/me")).status_code == 401
