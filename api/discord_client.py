"""Thin async client for the parts of the Discord HTTP API the dashboard needs."""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .config import Settings

ADMINISTRATOR = 0x8
CHANNEL_TYPES = {0: "text", 2: "voice", 4: "category", 5: "announcement", 13: "stage", 15: "forum"}


class DiscordError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(f"Discord API error {status}: {message}")
        self.status = status


class DiscordClient:
    def __init__(self, settings: Settings, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.discord_api_base,
            timeout=10.0,
            transport=transport,
            headers={"User-Agent": "DiscordBot (dashboard-api, 1.0)"},
        )
        self._guild_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._bot_user_id: Optional[str] = None
        self.guild_ttl = 30.0

    async def close(self):
        await self.http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = await self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DiscordError(503, str(exc)) from exc
        if response.status_code >= 400:
            raise DiscordError(response.status_code, response.text[:200])
        return response.json() if response.content else None

    # ---------------------------------------------------------------- OAuth

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/oauth2/token",
            data={"grant_type": "authorization_code", "code": code,
                  "redirect_uri": self.settings.redirect_uri},
            auth=(self.settings.client_id, self.settings.client_secret),
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/oauth2/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(self.settings.client_id, self.settings.client_secret),
        )

    async def revoke_token(self, token: str):
        await self._request(
            "POST", "/oauth2/token/revoke",
            data={"token": token},
            auth=(self.settings.client_id, self.settings.client_secret),
        )

    async def get_user(self, access_token: str) -> dict[str, Any]:
        return await self._request(
            "GET", "/users/@me", headers={"Authorization": f"Bearer {access_token}"}
        )

    async def get_user_guilds(self, access_token: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET", "/users/@me/guilds", headers={"Authorization": f"Bearer {access_token}"}
        )

    # ------------------------------------------------------------ bot token

    def _bot_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self.settings.bot_token}"}

    async def _bot_id(self) -> str:
        if self._bot_user_id is None:
            me = await self._request("GET", "/users/@me", headers=self._bot_headers())
            self._bot_user_id = str(me["id"])
        return self._bot_user_id

    async def get_guild(self, guild_id: int, force: bool = False) -> dict[str, Any]:
        """Guild name, roles and channels as seen by the bot. Raises DiscordError(404)
        if the bot is not a member of the guild."""
        cached = self._guild_cache.get(guild_id)
        if cached and not force and cached[0] > time.monotonic():
            return cached[1]

        headers = self._bot_headers()
        try:
            guild = await self._request("GET", f"/guilds/{guild_id}", headers=headers)
            channels = await self._request("GET", f"/guilds/{guild_id}/channels", headers=headers)
            member = await self._request(
                "GET", f"/guilds/{guild_id}/members/{await self._bot_id()}", headers=headers
            )
        except DiscordError as exc:
            if exc.status in (403, 404):
                self._guild_cache.pop(guild_id, None)
                raise DiscordError(404, "The bot is not in this server") from exc
            raise

        roles = guild.get("roles", [])
        bot_role_ids = set(member.get("roles", []))
        bot_top = max((r["position"] for r in roles if r["id"] in bot_role_ids), default=0)

        data = {
            "id": str(guild["id"]),
            "name": guild["name"],
            "icon": guild.get("icon"),
            "roles": sorted(
                (
                    {
                        "id": str(r["id"]),
                        "name": r["name"],
                        "color": r.get("color", 0),
                        "position": r["position"],
                        "managed": bool(r.get("managed")),
                        "everyone": str(r["id"]) == str(guild["id"]),
                        # Roles the bot is able to hand out.
                        "assignable": not r.get("managed")
                        and str(r["id"]) != str(guild["id"])
                        and r["position"] < bot_top,
                    }
                    for r in roles
                ),
                key=lambda r: -r["position"],
            ),
            "channels": sorted(
                (
                    {
                        "id": str(c["id"]),
                        "name": c.get("name") or "",
                        "type": CHANNEL_TYPES[c["type"]],
                        "parent_id": str(c["parent_id"]) if c.get("parent_id") else None,
                        "position": c.get("position", 0),
                    }
                    for c in channels
                    if c.get("type") in CHANNEL_TYPES
                ),
                key=lambda c: c["position"],
            ),
        }
        self._guild_cache[guild_id] = (time.monotonic() + self.guild_ttl, data)
        return data


def is_admin(guild: dict[str, Any]) -> bool:
    """True if the logged-in user owns the guild or has the Administrator permission."""
    if guild.get("owner"):
        return True
    try:
        return bool(int(guild.get("permissions", 0)) & ADMINISTRATOR)
    except (TypeError, ValueError):
        return False
