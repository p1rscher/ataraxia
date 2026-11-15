"""Sessions and permission checks.

Login is Discord OAuth2. The browser only ever holds an opaque random session
ID (HttpOnly cookie); Discord tokens stay on the server. Every guild route
checks on each request that the user still is an administrator of that guild
according to Discord, and that the bot is a member of it.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request

from .db import Database
from .discord_client import DiscordClient, DiscordError, is_admin

logger = logging.getLogger(__name__)

SESSION_COOKIE = "ataraxia_session"
STATE_COOKIE = "ataraxia_oauth_state"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "ataraxia-dashboard"
USER_GUILDS_TTL = 60.0


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry(payload: dict[str, Any]) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 3600)))


class SessionManager:
    def __init__(self, db: Database, discord: DiscordClient):
        self.db = db
        self.discord = discord
        self._guild_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def create(self, user: dict[str, Any], tokens: dict[str, Any], ttl_days: int) -> str:
        token = new_token()
        await self.db.create_session(
            hash_token(token), user, tokens["access_token"], tokens.get("refresh_token"),
            token_expiry(tokens), datetime.now(timezone.utc) + timedelta(days=ttl_days),
        )
        return token

    async def destroy(self, session: dict[str, Any]):
        self._guild_cache.pop(session["token_hash"], None)
        await self.db.delete_session(session["token_hash"])
        try:
            await self.discord.revoke_token(session["access_token"])
        except DiscordError:
            pass

    async def _refresh(self, session: dict[str, Any]) -> bool:
        if not session.get("refresh_token"):
            return False
        try:
            tokens = await self.discord.refresh_token(session["refresh_token"])
        except DiscordError as exc:
            logger.info("Token refresh failed for user %s: %s", session["user_id"], exc)
            return False
        session["access_token"] = tokens["access_token"]
        session["refresh_token"] = tokens.get("refresh_token") or session["refresh_token"]
        session["token_expires_at"] = token_expiry(tokens)
        await self.db.update_session_tokens(
            session["token_hash"], session["access_token"], tokens.get("refresh_token"),
            session["token_expires_at"],
        )
        return True

    async def user_guilds(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        """Guilds of the logged-in user, straight from Discord (cached for a minute)."""
        key = session["token_hash"]
        cached = self._guild_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        if session["token_expires_at"] <= datetime.now(timezone.utc) + timedelta(seconds=60):
            if not await self._refresh(session):
                await self._expire(session)

        try:
            guilds = await self.discord.get_user_guilds(session["access_token"])
        except DiscordError as exc:
            if exc.status == 401:
                if not await self._refresh(session):
                    await self._expire(session)
                try:
                    guilds = await self.discord.get_user_guilds(session["access_token"])
                except DiscordError:
                    await self._expire(session)
            elif cached:
                # Rate limited or Discord is down: a slightly stale answer beats none.
                return cached[1]
            else:
                raise HTTPException(503, "Discord is not reachable right now. Try again in a moment.")

        self._guild_cache[key] = (time.monotonic() + USER_GUILDS_TTL, guilds)
        return guilds

    async def _expire(self, session: dict[str, Any]):
        self._guild_cache.pop(session["token_hash"], None)
        await self.db.delete_session(session["token_hash"])
        raise HTTPException(401, "Your Discord login has expired. Please log in again.")


# ------------------------------------------------------------- dependencies

async def current_session(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not logged in")
    session = await request.app.state.db.get_session(hash_token(token))
    if not session:
        raise HTTPException(401, "Not logged in")
    return session


async def csrf_protect(request: Request):
    """Reject state-changing requests that do not come from the dashboard itself.

    Browsers refuse to add a custom header to a cross-site request unless CORS
    allows it, and this API allows no cross-origin access.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
        raise HTTPException(403, "Missing X-Requested-With header")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != request.app.state.settings.origin:
        raise HTTPException(403, "Cross-origin request rejected")


def parse_snowflake(value: str, what: str = "ID") -> int:
    if not isinstance(value, str) or not value.isdigit() or not 15 <= len(value) <= 20:
        raise HTTPException(422, f"Invalid {what}")
    return int(value)


class GuildAccess:
    """A guild the current user may administer, plus the bot's view of it."""

    def __init__(self, guild_id: int, user_id: int, meta: dict[str, Any]):
        self.guild_id = guild_id
        self.user_id = user_id
        self.meta = meta
        self._roles = {r["id"]: r for r in meta["roles"]}
        self._channels = {c["id"]: c for c in meta["channels"]}

    def require_channel(self, channel_id: int, kinds: Optional[tuple[str, ...]] = None) -> int:
        channel = self._channels.get(str(channel_id))
        if channel is None:
            raise HTTPException(422, f"Channel {channel_id} does not exist in this server")
        if kinds and channel["type"] not in kinds:
            raise HTTPException(422, f"#{channel['name']} is not a {' or '.join(kinds)} channel")
        return channel_id

    def require_role(self, role_id: int, assignable: bool = False) -> int:
        role = self._roles.get(str(role_id))
        if role is None:
            raise HTTPException(422, f"Role {role_id} does not exist in this server")
        if assignable and not role["assignable"]:
            raise HTTPException(
                422,
                f"The bot cannot assign @{role['name']}: it is managed by an integration, "
                "is @everyone, or sits above the bot's highest role",
            )
        return role_id


async def guild_access(
    guild_id: str,
    request: Request,
    session: dict[str, Any] = Depends(current_session),
    _: None = Depends(csrf_protect),
) -> GuildAccess:
    gid = parse_snowflake(guild_id, "server ID")
    guilds = await request.app.state.sessions.user_guilds(session)
    guild = next((g for g in guilds if str(g["id"]) == str(gid)), None)
    if guild is None or not is_admin(guild):
        raise HTTPException(403, "You need to be an administrator of this server")
    try:
        meta = await request.app.state.discord.get_guild(gid)
    except DiscordError as exc:
        if exc.status == 404:
            raise HTTPException(404, "The bot is not in this server")
        raise HTTPException(503, "Discord is not reachable right now. Try again in a moment.")
    return GuildAccess(gid, int(session["user_id"]), meta)
