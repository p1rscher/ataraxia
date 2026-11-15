"""Database access for the dashboard API.

The API talks to the same PostgreSQL database as the bot and uses the same
tables. Every write records the guild in ``dashboard_changes`` so the running
bot can drop its cached copy of that guild's settings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import asyncpg

LOG_COLUMNS = {
    "message": "message_log_channel_id",
    "say": "say_log_channel_id",
    "level": "level_log_channel_id",
    "voice": "voice_log_channel_id",
    "mod": "mod_log_channel_id",
    "traffic": "traffic_log_channel_id",
    "ticket": "ticket_log_channel_id",
}

XP_DEFAULTS = {
    "message_cooldown": 60,
    "voice_interval": 60,
    "message_xp_min": 10,
    "message_xp_max": 20,
    "voice_xp_min": 15,
    "voice_xp_max": 25,
}

VOICE_REQUIREMENT_DEFAULTS = {
    "require_non_afk": True,
    "require_non_deaf": True,
    "require_non_muted": False,
    "require_others_in_channel": True,
}


class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str, max_size: int = 3) -> "Database":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=max_size)
        database = cls(pool)
        await database.ensure_schema()
        return database

    async def close(self):
        await self.pool.close()

    async def ensure_schema(self):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT NOT NULL,
                    avatar TEXT,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_changes (
                    guild_id BIGINT NOT NULL,
                    scope TEXT NOT NULL,
                    changed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                    changed_by BIGINT,
                    PRIMARY KEY (guild_id, scope)
                )
                """
            )

    async def ping(self) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1

    # ------------------------------------------------------------ sessions

    async def create_session(self, token_hash: str, user: dict, access_token: str,
                             refresh_token: Optional[str], token_expires_at: datetime,
                             expires_at: datetime):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM dashboard_sessions WHERE expires_at < now()")
            await conn.execute(
                """
                INSERT INTO dashboard_sessions
                    (token_hash, user_id, username, avatar, access_token, refresh_token,
                     token_expires_at, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                token_hash, int(user["id"]), user["username"], user.get("avatar"),
                access_token, refresh_token, token_expires_at, expires_at,
            )

    async def get_session(self, token_hash: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM dashboard_sessions WHERE token_hash = $1 AND expires_at > now()",
                token_hash,
            )
        return dict(row) if row else None

    async def update_session_tokens(self, token_hash: str, access_token: str,
                                    refresh_token: Optional[str], token_expires_at: datetime):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE dashboard_sessions
                SET access_token = $2, refresh_token = COALESCE($3, refresh_token), token_expires_at = $4
                WHERE token_hash = $1
                """,
                token_hash, access_token, refresh_token, token_expires_at,
            )

    async def delete_session(self, token_hash: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM dashboard_sessions WHERE token_hash = $1", token_hash)

    # ------------------------------------------------------------- helpers

    @staticmethod
    async def _mark_changed(conn, guild_id: int, scope: str, user_id: Optional[int]):
        await conn.execute(
            """
            INSERT INTO dashboard_changes (guild_id, scope, changed_at, changed_by)
            VALUES ($1, $2, clock_timestamp(), $3)
            ON CONFLICT (guild_id, scope)
            DO UPDATE SET changed_at = clock_timestamp(), changed_by = $3
            """,
            guild_id, scope, user_id,
        )

    async def tracked_guild_ids(self, guild_ids: list[int]) -> set[int]:
        if not guild_ids:
            return set()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT guild_id FROM discord_servers WHERE guild_id = ANY($1::BIGINT[])", guild_ids
            )
        return {int(r["guild_id"]) for r in rows}

    # ------------------------------------------------------------------ XP

    async def get_xp_settings(self, guild_id: int) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM xp_settings WHERE guild_id = $1", guild_id)
        if not row:
            return dict(XP_DEFAULTS)
        return {key: row[key] if row[key] is not None else default for key, default in XP_DEFAULTS.items()}

    async def set_xp_settings(self, guild_id: int, values: dict[str, int], user_id: int):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO xp_settings
                    (guild_id, message_cooldown, voice_interval, message_xp_min, message_xp_max,
                     voice_xp_min, voice_xp_max)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (guild_id) DO UPDATE SET
                    message_cooldown = $2, voice_interval = $3, message_xp_min = $4,
                    message_xp_max = $5, voice_xp_min = $6, voice_xp_max = $7
                """,
                guild_id, values["message_cooldown"], values["voice_interval"],
                values["message_xp_min"], values["message_xp_max"],
                values["voice_xp_min"], values["voice_xp_max"],
            )
            await self._mark_changed(conn, guild_id, "xp", user_id)

    async def get_voice_requirements(self, guild_id: int) -> dict[str, bool]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM voice_xp_requirements WHERE guild_id = $1", guild_id
            )
        if not row:
            return dict(VOICE_REQUIREMENT_DEFAULTS)
        return {key: bool(row[key]) if row[key] is not None else default
                for key, default in VOICE_REQUIREMENT_DEFAULTS.items()}

    async def set_voice_requirements(self, guild_id: int, values: dict[str, bool], user_id: int):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO voice_xp_requirements
                    (guild_id, require_non_afk, require_non_deaf, require_non_muted, require_others_in_channel)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id) DO UPDATE SET
                    require_non_afk = $2, require_non_deaf = $3,
                    require_non_muted = $4, require_others_in_channel = $5
                """,
                guild_id, values["require_non_afk"], values["require_non_deaf"],
                values["require_non_muted"], values["require_others_in_channel"],
            )
            await self._mark_changed(conn, guild_id, "xp", user_id)

    # --------------------------------------------------------- multipliers

    async def get_multipliers(self, guild_id: int) -> dict[str, list[dict[str, Any]]]:
        async with self.pool.acquire() as conn:
            channels = await conn.fetch(
                "SELECT channel_id, multiplier FROM xp_channel_multipliers WHERE guild_id = $1", guild_id
            )
            roles = await conn.fetch(
                "SELECT role_id, multiplier FROM xp_role_multipliers WHERE guild_id = $1", guild_id
            )
        return {
            "channels": [{"id": r["channel_id"], "multiplier": float(r["multiplier"])} for r in channels],
            "roles": [{"id": r["role_id"], "multiplier": float(r["multiplier"])} for r in roles],
        }

    async def set_multiplier(self, guild_id: int, kind: str, target_id: int,
                             multiplier: Optional[float], user_id: int):
        table, column = {
            "channels": ("xp_channel_multipliers", "channel_id"),
            "roles": ("xp_role_multipliers", "role_id"),
        }[kind]
        async with self.pool.acquire() as conn, conn.transaction():
            if multiplier is None:
                await conn.execute(
                    f"DELETE FROM {table} WHERE guild_id = $1 AND {column} = $2", guild_id, target_id
                )
            else:
                await conn.execute(
                    f"""
                    INSERT INTO {table} (guild_id, {column}, multiplier) VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, {column}) DO UPDATE SET multiplier = $3
                    """,
                    guild_id, target_id, multiplier,
                )
            await self._mark_changed(conn, guild_id, "multipliers", user_id)

    # ---------------------------------------------------------------- logs

    async def get_log_channels(self, guild_id: int) -> dict[str, Optional[int]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
        return {name: (row[column] if row else None) for name, column in LOG_COLUMNS.items()}

    async def set_log_channels(self, guild_id: int, values: dict[str, Optional[int]], user_id: int):
        if not values:
            return
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO guild_settings (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
                guild_id,
            )
            for name, channel_id in values.items():
                column = LOG_COLUMNS[name]  # whitelisted, never user-supplied SQL
                await conn.execute(
                    f"UPDATE guild_settings SET {column} = $2 WHERE guild_id = $1", guild_id, channel_id
                )
            await self._mark_changed(conn, guild_id, "logs", user_id)

    # --------------------------------------------------------- level roles

    async def get_level_roles(self, guild_id: int) -> list[dict[str, int]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT level, role_id FROM level_roles WHERE guild_id = $1 ORDER BY level", guild_id
            )
        return [{"level": r["level"], "role_id": r["role_id"]} for r in rows]

    async def set_level_role(self, guild_id: int, level: int, role_id: Optional[int], user_id: int):
        async with self.pool.acquire() as conn, conn.transaction():
            if role_id is None:
                await conn.execute(
                    "DELETE FROM level_roles WHERE guild_id = $1 AND level = $2", guild_id, level
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO level_roles (guild_id, level, role_id) VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, level) DO UPDATE SET role_id = $3
                    """,
                    guild_id, level, role_id,
                )
            await self._mark_changed(conn, guild_id, "level_roles", user_id)

    # ---------------------------------------------------------- auto roles

    async def get_auto_roles(self, guild_id: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT enabled, user_role_ids, bot_role_ids FROM autorole_settings WHERE guild_id = $1",
                guild_id,
            )
        if not row:
            return {"enabled": False, "user_role_ids": [], "bot_role_ids": []}
        return {
            "enabled": bool(row["enabled"]),
            "user_role_ids": list(row["user_role_ids"] or []),
            "bot_role_ids": list(row["bot_role_ids"] or []),
        }

    async def set_auto_roles(self, guild_id: int, enabled: bool, user_role_ids: list[int],
                             bot_role_ids: list[int], user_id: int):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO autorole_settings (guild_id, enabled, user_role_ids, bot_role_ids)
                VALUES ($1, $2, $3::BIGINT[], $4::BIGINT[])
                ON CONFLICT (guild_id) DO UPDATE SET
                    enabled = $2, user_role_ids = $3::BIGINT[], bot_role_ids = $4::BIGINT[]
                """,
                guild_id, enabled, user_role_ids, bot_role_ids,
            )
            await self._mark_changed(conn, guild_id, "auto_roles", user_id)

    # --------------------------------------------------------- leaderboard

    async def get_leaderboard(self, guild_id: int, limit: int, offset: int) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM user_levels WHERE guild_id = $1", guild_id
            )
            rows = await conn.fetch(
                """
                SELECT l.user_id, l.xp, l.level, u.username, u.global_name
                FROM user_levels l
                LEFT JOIN discord_users u ON u.user_id = l.user_id
                WHERE l.guild_id = $1
                ORDER BY l.xp DESC, l.user_id
                LIMIT $2 OFFSET $3
                """,
                guild_id, limit, offset,
            )
        return {
            "total": int(total or 0),
            "entries": [
                {
                    "rank": offset + index + 1,
                    "user_id": r["user_id"],
                    "username": r["global_name"] or r["username"],
                    "xp": r["xp"],
                    "level": r["level"],
                }
                for index, r in enumerate(rows)
            ],
        }
