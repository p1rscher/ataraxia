"""Local dashboard with a fake Discord, for trying the web UI without real credentials.

    TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/ataraxia_test \
        .venv/bin/python tests/dev_server.py

Then open http://127.0.0.1:8765/ and press "Log in with Discord". Never point
this at the production database: it creates tables and test data.
"""
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "bot"), str(ROOT / "tests")]

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402

PORT = 8765


def main():
    url = os.environ["TEST_DATABASE_URL"]
    assert urlparse(url).hostname in ("127.0.0.1", "localhost"), "local databases only"
    os.environ["DATABASE_URL"] = url

    from core import database_pg as botdb
    from test_api import GUILD_A, FakeDiscord
    from api.config import Settings
    from api.main import create_app

    async def prepare():
        await botdb.init_db()
        async with botdb._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO discord_servers (guild_id, server_name) VALUES ($1, 'Alpha') ON CONFLICT DO NOTHING",
                int(GUILD_A))
        await botdb.add_xp(42, int(GUILD_A), 900)
        await botdb.close_db()

    asyncio.run(prepare())
    base = f"http://127.0.0.1:{PORT}"
    app = create_app(
        Settings(database_url=url, bot_token="bot-token", client_id="123456789012345678", client_secret="secret",
                 base_url=base, discord_api_base="https://discord.test/api/v10",
                 discord_authorize_url=f"{base}/fake-discord/authorize"),
        discord_transport=httpx.MockTransport(FakeDiscord()),
    )

    @app.get("/fake-discord/authorize")
    async def fake_authorize(state: str):
        return RedirectResponse(f"{base}/auth/callback?code=good-code&state={state}")

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
