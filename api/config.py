"""Configuration for the dashboard API, read from the environment / .env."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]


def _client_id_from_token(token: str) -> Optional[str]:
    """A bot token starts with the base64-encoded application ID."""
    try:
        head = token.split(".", 1)[0]
        decoded = base64.b64decode(head + "=" * (-len(head) % 4)).decode()
        return decoded if decoded.isdigit() else None
    except Exception:
        return None


@dataclass(frozen=True)
class Settings:
    database_url: str
    bot_token: str
    client_id: str
    client_secret: str
    base_url: str
    discord_api_base: str = "https://discord.com/api/v10"
    discord_authorize_url: str = "https://discord.com/oauth2/authorize"
    session_ttl_days: int = 7
    db_pool_max: int = 3

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}/auth/callback"

    @property
    def origin(self) -> str:
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def cookie_path(self) -> str:
        return urlparse(self.base_url).path or "/"

    @property
    def cookie_secure(self) -> bool:
        return self.base_url.startswith("https://")

    @property
    def oauth_ready(self) -> bool:
        return bool(self.client_id and self.client_secret)


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")
    bot_token = os.getenv("BOT_TOKEN", "")
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return Settings(
        database_url=database_url,
        bot_token=bot_token,
        client_id=os.getenv("DISCORD_CLIENT_ID") or _client_id_from_token(bot_token) or "",
        client_secret=os.getenv("DISCORD_CLIENT_SECRET", ""),
        base_url=os.getenv("DASHBOARD_BASE_URL", "http://localhost:8000").rstrip("/"),
        discord_api_base=os.getenv("DISCORD_API_BASE", "https://discord.com/api/v10").rstrip("/"),
        discord_authorize_url=os.getenv("DISCORD_AUTHORIZE_URL", "https://discord.com/oauth2/authorize"),
        session_ttl_days=int(os.getenv("DASHBOARD_SESSION_DAYS", "7")),
        db_pool_max=int(os.getenv("API_DB_POOL_MAX", "3")),
    )
