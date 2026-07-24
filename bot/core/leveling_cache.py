from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LevelState:
    user_id: int
    guild_id: int
    xp: int
    level: int
    multiplier: float
    dirty: bool
    version: int

    def as_record(self) -> dict[str, Any]:
        return {
            "xp": self.xp,
            "level": self.level,
            "multiplier": self.multiplier,
        }


@dataclass(slots=True)
class CooldownState:
    user_id: int
    guild_id: int
    last_message_xp_ts: float
    dirty: bool
    version: int


class LevelingCacheManager:
    def __init__(
        self,
        bot,
        cache_path: Optional[str] = None,
        flush_interval: float = 60.0,
        settings_ttl: float = 300.0,
    ):
        self.bot = bot
        self.flush_interval = flush_interval
        self.settings_ttl = settings_ttl
        self.cache_path = Path(cache_path) if cache_path else self._default_cache_path()
        self._connection: Optional[sqlite3.Connection] = None
        self._flush_lock = asyncio.Lock()
        self._user_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._level_states: dict[tuple[int, int], LevelState] = {}
        self._cooldown_states: dict[tuple[int, int], CooldownState] = {}
        self._settings_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._voice_requirements_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._channel_multiplier_cache: dict[int, tuple[float, dict[int, float]]] = {}
        self._role_multiplier_cache: dict[int, tuple[float, dict[int, float]]] = {}
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    @staticmethod
    def _default_cache_path() -> Path:
        root_dir = Path(__file__).resolve().parents[2]
        return root_dir / "runtime" / "leveling_cache.sqlite3"

    async def start(self):
        await asyncio.to_thread(self._init_sqlite_sync)
        self._flush_task = asyncio.create_task(self._periodic_flush(), name="leveling-cache-flush")
        await self.flush_pending()

    async def close(self):
        if self._closed:
            return
        self._closed = True

        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self.flush_pending()
        await asyncio.to_thread(self._close_sqlite_sync)

    def invalidate_guild_settings(self, guild_id: int):
        self._settings_cache.pop(guild_id, None)
        self._voice_requirements_cache.pop(guild_id, None)

    def invalidate_multiplier_cache(self, guild_id: int):
        self._channel_multiplier_cache.pop(guild_id, None)
        self._role_multiplier_cache.pop(guild_id, None)

    async def get_level(self, user_id: int, guild_id: int) -> dict[str, Any]:
        state = await self._get_level_state(user_id, guild_id)
        return state.as_record()

    async def set_level(self, user_id: int, guild_id: int, level: int):
        state = await self._get_level_state(user_id, guild_id)
        async with self._get_user_lock(user_id, guild_id):
            state.level = level
            state.dirty = True
            state.version += 1
            self._level_states[(guild_id, user_id)] = state
            await asyncio.to_thread(self._upsert_level_state_sync, state)

    async def set_xp_and_level(self, user_id: int, guild_id: int, xp: int, level: int):
        state = await self._get_level_state(user_id, guild_id)
        async with self._get_user_lock(user_id, guild_id):
            state.xp = xp
            state.level = level
            state.dirty = True
            state.version += 1
            self._level_states[(guild_id, user_id)] = state
            await asyncio.to_thread(self._upsert_level_state_sync, state)

    async def add_xp(self, user_id: int, guild_id: int, amount: int):
        state = await self._get_level_state(user_id, guild_id)
        async with self._get_user_lock(user_id, guild_id):
            state.xp += amount
            state.dirty = True
            state.version += 1
            self._level_states[(guild_id, user_id)] = state
            await asyncio.to_thread(self._upsert_level_state_sync, state)

    async def can_gain_message_xp(self, user_id: int, guild_id: int) -> bool:
        settings = await self.get_xp_settings(guild_id)
        cooldown_seconds = settings["message_cooldown"]
        if cooldown_seconds <= 0:
            return True

        state = await self._get_cooldown_state(user_id, guild_id)
        if state is None or state.last_message_xp_ts <= 0:
            return True

        time_since = time.time() - state.last_message_xp_ts
        return time_since >= cooldown_seconds

    async def grant_message_xp(self, user_id: int, guild_id: int, amount: int):
        async with self._get_user_lock(user_id, guild_id):
            level_state = await self._get_level_state(user_id, guild_id)
            cooldown_state = await self._get_cooldown_state(user_id, guild_id)
            now_ts = time.time()

            level_state.xp += amount
            level_state.dirty = True
            level_state.version += 1
            self._level_states[(guild_id, user_id)] = level_state

            if cooldown_state is None:
                cooldown_state = CooldownState(
                    user_id=user_id,
                    guild_id=guild_id,
                    last_message_xp_ts=now_ts,
                    dirty=True,
                    version=1,
                )
            else:
                cooldown_state.last_message_xp_ts = now_ts
                cooldown_state.dirty = True
                cooldown_state.version += 1

            self._cooldown_states[(guild_id, user_id)] = cooldown_state

            await asyncio.to_thread(self._upsert_level_state_sync, level_state)
            await asyncio.to_thread(self._upsert_cooldown_state_sync, cooldown_state)

    async def get_message_xp_range(self, guild_id: int) -> tuple[int, int]:
        settings = await self.get_xp_settings(guild_id)
        return settings["message_xp_min"], settings["message_xp_max"]

    async def get_voice_xp_interval(self, guild_id: int) -> int:
        settings = await self.get_xp_settings(guild_id)
        return settings["voice_interval"]

    async def get_voice_xp_range(self, guild_id: int) -> tuple[int, int]:
        settings = await self.get_xp_settings(guild_id)
        return settings["voice_xp_min"], settings["voice_xp_max"]

    async def get_xp_settings(self, guild_id: int) -> dict[str, Any]:
        cached = self._settings_cache.get(guild_id)
        now = time.monotonic()
        if cached and cached[0] > now:
            return dict(cached[1])

        settings = await self.bot.db.get_all_xp_settings(guild_id)
        self._settings_cache[guild_id] = (now + self.settings_ttl, dict(settings))
        return dict(settings)

    async def get_voice_requirements(self, guild_id: int) -> dict[str, Any]:
        cached = self._voice_requirements_cache.get(guild_id)
        now = time.monotonic()
        if cached and cached[0] > now:
            return dict(cached[1])

        requirements = await self.bot.db.get_voice_xp_requirements(guild_id)
        self._voice_requirements_cache[guild_id] = (now + self.settings_ttl, dict(requirements))
        return dict(requirements)

    async def calculate_total_multiplier(self, member, channel_id: int) -> float:
        guild_id = member.guild.id
        state = await self._get_level_state(member.id, guild_id)
        total = state.multiplier

        channel_multipliers = await self._get_channel_multipliers(guild_id)
        total *= channel_multipliers.get(channel_id, 1.0)

        role_multipliers = await self._get_role_multipliers(guild_id)
        role_mults = [role_multipliers[role.id] for role in member.roles if role.id in role_multipliers]
        if role_mults:
            for role_mult in role_mults:
                total *= role_mult

        temp_boost = await self.bot.db.get_active_xp_boost_multiplier(member.id, guild_id)
        total *= temp_boost
        return total

    async def flush_pending(self):
        async with self._flush_lock:
            dirty_levels = await asyncio.to_thread(self._snapshot_dirty_levels_sync)
            if dirty_levels:
                try:
                    await self.bot.db.bulk_upsert_user_levels(dirty_levels)
                    await asyncio.to_thread(self._mark_level_states_clean_sync, dirty_levels)
                except Exception:
                    logger.exception("Failed to flush leveling states")

            dirty_cooldowns = await asyncio.to_thread(self._snapshot_dirty_cooldowns_sync)
            if dirty_cooldowns:
                try:
                    await self.bot.db.bulk_upsert_message_xp_cooldowns(dirty_cooldowns)
                    await asyncio.to_thread(self._mark_cooldowns_clean_sync, dirty_cooldowns)
                except Exception:
                    logger.exception("Failed to flush leveling cooldowns")

    async def _periodic_flush(self):
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in leveling cache flush loop")

    async def _get_level_state(self, user_id: int, guild_id: int) -> LevelState:
        key = (guild_id, user_id)
        cached = self._level_states.get(key)
        if cached is not None:
            return cached

        row = await asyncio.to_thread(self._load_level_state_sync, user_id, guild_id)
        if row is not None:
            self._level_states[key] = row
            return row

        level_row = await self.bot.db.get_level(user_id, guild_id)
        multiplier = await self.bot.db.get_multiplier(user_id, guild_id)
        state = LevelState(
            user_id=user_id,
            guild_id=guild_id,
            xp=level_row["xp"] if level_row else 0,
            level=level_row["level"] if level_row else 0,
            multiplier=multiplier,
            dirty=False,
            version=0,
        )
        self._level_states[key] = state
        await asyncio.to_thread(self._upsert_level_state_sync, state)
        return state

    async def _get_cooldown_state(self, user_id: int, guild_id: int) -> Optional[CooldownState]:
        key = (guild_id, user_id)
        cached = self._cooldown_states.get(key)
        if cached is not None:
            return cached

        row = await asyncio.to_thread(self._load_cooldown_state_sync, user_id, guild_id)
        if row is not None:
            self._cooldown_states[key] = row
            return row

        cooldown_row = await self.bot.db.get_message_xp_cooldown(user_id, guild_id)
        if cooldown_row is None:
            return None

        state = CooldownState(
            user_id=user_id,
            guild_id=guild_id,
            last_message_xp_ts=self._datetime_to_ts(cooldown_row),
            dirty=False,
            version=0,
        )
        self._cooldown_states[key] = state
        await asyncio.to_thread(self._upsert_cooldown_state_sync, state)
        return state

    async def _get_channel_multipliers(self, guild_id: int) -> dict[int, float]:
        cached = self._channel_multiplier_cache.get(guild_id)
        now = time.monotonic()
        if cached and cached[0] > now:
            return dict(cached[1])

        pairs = await self.bot.db.get_all_channel_multipliers(guild_id)
        mapping = {channel_id: multiplier for channel_id, multiplier in pairs}
        self._channel_multiplier_cache[guild_id] = (now + self.settings_ttl, mapping)
        return dict(mapping)

    async def _get_role_multipliers(self, guild_id: int) -> dict[int, float]:
        cached = self._role_multiplier_cache.get(guild_id)
        now = time.monotonic()
        if cached and cached[0] > now:
            return dict(cached[1])

        pairs = await self.bot.db.get_all_role_multipliers(guild_id)
        mapping = {role_id: multiplier for role_id, multiplier in pairs}
        self._role_multiplier_cache[guild_id] = (now + self.settings_ttl, mapping)
        return dict(mapping)

    def _get_user_lock(self, user_id: int, guild_id: int) -> asyncio.Lock:
        key = (guild_id, user_id)
        lock = self._user_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[key] = lock
        return lock

    def _init_sqlite_sync(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.cache_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS level_state (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 0,
                multiplier REAL NOT NULL DEFAULT 1.0,
                dirty INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cooldown_state (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_message_xp_ts REAL NOT NULL DEFAULT 0,
                dirty INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self._connection.commit()

    def _close_sqlite_sync(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _load_level_state_sync(self, user_id: int, guild_id: int) -> Optional[LevelState]:
        row = self._connection.execute(
            "SELECT guild_id, user_id, xp, level, multiplier, dirty, version FROM level_state WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return None
        return LevelState(
            user_id=row["user_id"],
            guild_id=row["guild_id"],
            xp=row["xp"],
            level=row["level"],
            multiplier=row["multiplier"],
            dirty=bool(row["dirty"]),
            version=row["version"],
        )

    def _load_cooldown_state_sync(self, user_id: int, guild_id: int) -> Optional[CooldownState]:
        row = self._connection.execute(
            "SELECT guild_id, user_id, last_message_xp_ts, dirty, version FROM cooldown_state WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return None
        return CooldownState(
            user_id=row["user_id"],
            guild_id=row["guild_id"],
            last_message_xp_ts=row["last_message_xp_ts"],
            dirty=bool(row["dirty"]),
            version=row["version"],
        )

    def _upsert_level_state_sync(self, state: LevelState):
        self._connection.execute(
            """
            INSERT INTO level_state (guild_id, user_id, xp, level, multiplier, dirty, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                xp = excluded.xp,
                level = excluded.level,
                multiplier = excluded.multiplier,
                dirty = excluded.dirty,
                version = excluded.version
            """,
            (
                state.guild_id,
                state.user_id,
                state.xp,
                state.level,
                state.multiplier,
                int(state.dirty),
                state.version,
            ),
        )
        self._connection.commit()

    def _upsert_cooldown_state_sync(self, state: CooldownState):
        self._connection.execute(
            """
            INSERT INTO cooldown_state (guild_id, user_id, last_message_xp_ts, dirty, version)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                last_message_xp_ts = excluded.last_message_xp_ts,
                dirty = excluded.dirty,
                version = excluded.version
            """,
            (
                state.guild_id,
                state.user_id,
                state.last_message_xp_ts,
                int(state.dirty),
                state.version,
            ),
        )
        self._connection.commit()

    def _snapshot_dirty_levels_sync(self) -> list[tuple[int, int, int, int, float, int]]:
        rows = self._connection.execute(
            "SELECT guild_id, user_id, xp, level, multiplier, version FROM level_state WHERE dirty = 1"
        ).fetchall()
        return [
            (row["user_id"], row["guild_id"], row["xp"], row["level"], row["multiplier"], row["version"])
            for row in rows
        ]

    def _snapshot_dirty_cooldowns_sync(self) -> list[tuple[int, int, datetime, int]]:
        rows = self._connection.execute(
            "SELECT guild_id, user_id, last_message_xp_ts, version FROM cooldown_state WHERE dirty = 1"
        ).fetchall()
        return [
            (
                row["user_id"],
                row["guild_id"],
                datetime.fromtimestamp(row["last_message_xp_ts"], tz=timezone.utc).replace(tzinfo=None),
                row["version"],
            )
            for row in rows
        ]

    def _mark_level_states_clean_sync(self, entries: list[tuple[int, int, int, int, float, int]]):
        self._connection.executemany(
            "UPDATE level_state SET dirty = 0 WHERE user_id = ? AND guild_id = ? AND version = ?",
            [(user_id, guild_id, version) for user_id, guild_id, _, _, _, version in entries],
        )
        self._connection.commit()

    def _mark_cooldowns_clean_sync(self, entries: list[tuple[int, int, datetime, int]]):
        self._connection.executemany(
            "UPDATE cooldown_state SET dirty = 0 WHERE user_id = ? AND guild_id = ? AND version = ?",
            [(user_id, guild_id, version) for user_id, guild_id, _, version in entries],
        )
        self._connection.commit()

    @staticmethod
    def _datetime_to_ts(value: datetime) -> float:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()