from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CountingState:
    guild_id: int
    channel_id: Optional[int]
    current_number: int
    high_score: int
    last_user_id: Optional[int]
    is_active: bool
    dirty: bool
    version: int

    def as_settings(self) -> Optional[dict[str, Any]]:
        if not self.is_active or self.channel_id is None:
            return None
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "current_number": self.current_number,
            "high_score": self.high_score,
            "last_user_id": self.last_user_id,
        }


@dataclass(slots=True)
class CountProcessResult:
    status: str
    current_number: int = 0
    expected_number: int = 0
    attempted_number: Optional[int] = None
    high_score: int = 0
    milestone_reached: bool = False
    new_high_score: bool = False


class CountingCacheManager:
    def __init__(self, bot, cache_path: Optional[str] = None, flush_interval: float = 60.0):
        self.bot = bot
        self.flush_interval = flush_interval
        self.cache_path = Path(cache_path) if cache_path else self._default_cache_path()
        self._connection: Optional[sqlite3.Connection] = None
        self._states: dict[int, CountingState] = {}
        self._guild_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._flush_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    @staticmethod
    def _default_cache_path() -> Path:
        root_dir = Path(__file__).resolve().parents[2]
        return root_dir / "runtime" / "counting_cache.sqlite3"

    async def start(self):
        await asyncio.to_thread(self._init_sqlite_sync)
        await self._hydrate_states()
        self._flush_task = asyncio.create_task(self._periodic_flush(), name="counting-cache-flush")
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

    async def get_settings(self, guild_id: int) -> Optional[dict[str, Any]]:
        state = self._states.get(guild_id)
        return state.as_settings() if state else None

    async def set_channel(self, guild_id: int, channel_id: int):
        async with self._guild_locks[guild_id]:
            state = CountingState(
                guild_id=guild_id,
                channel_id=channel_id,
                current_number=0,
                high_score=0,
                last_user_id=None,
                is_active=True,
                dirty=True,
                version=(self._states.get(guild_id).version + 1) if guild_id in self._states else 1,
            )
            self._states[guild_id] = state
            await asyncio.to_thread(self._upsert_state_sync, state)

        await self.flush_pending(guild_id=guild_id)

    async def remove_channel(self, guild_id: int):
        async with self._guild_locks[guild_id]:
            previous = self._states.get(guild_id)
            state = CountingState(
                guild_id=guild_id,
                channel_id=None,
                current_number=0,
                high_score=previous.high_score if previous else 0,
                last_user_id=None,
                is_active=False,
                dirty=True,
                version=(previous.version + 1) if previous else 1,
            )
            self._states[guild_id] = state
            await asyncio.to_thread(self._upsert_state_sync, state)

        await self.flush_pending(guild_id=guild_id)

    async def reset(self, guild_id: int):
        async with self._guild_locks[guild_id]:
            state = self._states.get(guild_id)
            if not state or not state.is_active:
                return
            state.current_number = 0
            state.last_user_id = None
            state.dirty = True
            state.version += 1
            await asyncio.to_thread(self._upsert_state_sync, state)

        await self.flush_pending(guild_id=guild_id)

    async def process_message(self, guild_id: int, channel_id: int, user_id: int, content: str) -> CountProcessResult:
        async with self._guild_locks[guild_id]:
            state = self._states.get(guild_id)
            if not state or not state.is_active or state.channel_id != channel_id:
                return CountProcessResult(status="ignore")

            try:
                number = int(content.strip())
            except ValueError:
                return CountProcessResult(
                    status="invalid",
                    current_number=state.current_number,
                    expected_number=state.current_number + 1,
                    high_score=state.high_score,
                )

            if state.last_user_id == user_id:
                return CountProcessResult(
                    status="same_user",
                    current_number=state.current_number,
                    expected_number=state.current_number + 1,
                    high_score=state.high_score,
                )

            expected_number = state.current_number + 1

            if number == expected_number:
                new_high_score = expected_number > state.high_score
                state.current_number = expected_number
                state.last_user_id = user_id
                if new_high_score:
                    state.high_score = expected_number
                state.dirty = True
                state.version += 1

                await asyncio.to_thread(self._upsert_state_sync, state)
                await asyncio.to_thread(self._add_user_delta_sync, guild_id, user_id, 1)
                self._schedule_flush()

                return CountProcessResult(
                    status="correct",
                    current_number=state.current_number,
                    expected_number=expected_number,
                    high_score=state.high_score,
                    milestone_reached=new_high_score and expected_number % 100 == 0,
                    new_high_score=new_high_score,
                )

            ruined_at = state.current_number
            state.current_number = 0
            state.last_user_id = None
            state.dirty = True
            state.version += 1
            await asyncio.to_thread(self._upsert_state_sync, state)
            self._schedule_flush()

            return CountProcessResult(
                status="wrong",
                current_number=ruined_at,
                expected_number=expected_number,
                attempted_number=number,
                high_score=state.high_score,
            )

    async def flush_pending(self, guild_id: Optional[int] = None):
        async with self._flush_lock:
            dirty_states = await asyncio.to_thread(self._snapshot_dirty_states_sync, guild_id)
            for state in dirty_states:
                try:
                    if state.is_active and state.channel_id is not None:
                        await self.bot.db.upsert_counting_state(
                            state.guild_id,
                            state.channel_id,
                            state.current_number,
                            state.high_score,
                            state.last_user_id,
                        )
                    else:
                        await self.bot.db.remove_counting_channel(state.guild_id)
                    await asyncio.to_thread(self._mark_state_clean_sync, state.guild_id, state.version)
                except Exception:
                    logger.exception("Failed to flush counting state for guild_id=%s", state.guild_id)

            pending_deltas = await asyncio.to_thread(self._snapshot_user_deltas_sync, guild_id)
            if pending_deltas:
                try:
                    await self.bot.db.bulk_increment_user_counting(pending_deltas)
                    await asyncio.to_thread(self._consume_user_deltas_sync, pending_deltas)
                except Exception:
                    logger.exception("Failed to flush counting stats deltas")

    async def _hydrate_states(self):
        db_rows = await self.bot.db.get_all_counting_settings()
        sqlite_rows = await asyncio.to_thread(self._load_states_sync)

        sqlite_map = {row.guild_id: row for row in sqlite_rows}
        db_map: dict[int, CountingState] = {}

        for row in db_rows:
            db_map[row["guild_id"]] = CountingState(
                guild_id=row["guild_id"],
                channel_id=row["channel_id"],
                current_number=row["current_number"],
                high_score=row["high_score"],
                last_user_id=row["last_user_id"],
                is_active=True,
                dirty=False,
                version=0,
            )

        merged = dict(db_map)
        merged.update(sqlite_map)
        self._states = merged

        missing_rows = [state for guild_id, state in db_map.items() if guild_id not in sqlite_map]
        if missing_rows:
            await asyncio.to_thread(self._seed_states_sync, missing_rows)

    async def _periodic_flush(self):
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in counting cache flush loop")

    def _schedule_flush(self):
        # The hot path is crash-safe once SQLite is updated locally.
        # PostgreSQL flushes are retried by the background loop and by
        # explicit flush calls on status-sensitive commands.
        return

    def _init_sqlite_sync(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.cache_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_state (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                current_number INTEGER NOT NULL DEFAULT 0,
                high_score INTEGER NOT NULL DEFAULT 0,
                last_user_id INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                dirty INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_deltas (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                correct_counts_delta INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self._connection.commit()

    def _close_sqlite_sync(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _load_states_sync(self) -> list[CountingState]:
        rows = self._connection.execute(
            "SELECT guild_id, channel_id, current_number, high_score, last_user_id, is_active, dirty, version FROM guild_state"
        ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def _seed_states_sync(self, states: list[CountingState]):
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO guild_state (
                guild_id, channel_id, current_number, high_score, last_user_id, is_active, dirty, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    state.guild_id,
                    state.channel_id,
                    state.current_number,
                    state.high_score,
                    state.last_user_id,
                    int(state.is_active),
                    int(state.dirty),
                    state.version,
                )
                for state in states
            ],
        )
        self._connection.commit()

    def _upsert_state_sync(self, state: CountingState):
        self._connection.execute(
            """
            INSERT INTO guild_state (
                guild_id, channel_id, current_number, high_score, last_user_id, is_active, dirty, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                current_number = excluded.current_number,
                high_score = excluded.high_score,
                last_user_id = excluded.last_user_id,
                is_active = excluded.is_active,
                dirty = excluded.dirty,
                version = excluded.version
            """,
            (
                state.guild_id,
                state.channel_id,
                state.current_number,
                state.high_score,
                state.last_user_id,
                int(state.is_active),
                int(state.dirty),
                state.version,
            ),
        )
        self._connection.commit()

    def _add_user_delta_sync(self, guild_id: int, user_id: int, delta: int):
        self._connection.execute(
            """
            INSERT INTO user_deltas (guild_id, user_id, correct_counts_delta)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                correct_counts_delta = correct_counts_delta + excluded.correct_counts_delta
            """,
            (guild_id, user_id, delta),
        )
        self._connection.commit()

    def _snapshot_dirty_states_sync(self, guild_id: Optional[int]) -> list[CountingState]:
        if guild_id is None:
            rows = self._connection.execute(
                "SELECT guild_id, channel_id, current_number, high_score, last_user_id, is_active, dirty, version FROM guild_state WHERE dirty = 1"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT guild_id, channel_id, current_number, high_score, last_user_id, is_active, dirty, version FROM guild_state WHERE dirty = 1 AND guild_id = ?",
                (guild_id,),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def _mark_state_clean_sync(self, guild_id: int, version: int):
        self._connection.execute(
            "UPDATE guild_state SET dirty = 0 WHERE guild_id = ? AND version = ?",
            (guild_id, version),
        )
        self._connection.commit()

    def _snapshot_user_deltas_sync(self, guild_id: Optional[int]) -> list[tuple[int, int, int]]:
        if guild_id is None:
            rows = self._connection.execute(
                "SELECT guild_id, user_id, correct_counts_delta FROM user_deltas WHERE correct_counts_delta > 0"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT guild_id, user_id, correct_counts_delta FROM user_deltas WHERE correct_counts_delta > 0 AND guild_id = ?",
                (guild_id,),
            ).fetchall()
        return [(row["guild_id"], row["user_id"], row["correct_counts_delta"]) for row in rows]

    def _consume_user_deltas_sync(self, entries: list[tuple[int, int, int]]):
        self._connection.executemany(
            """
            UPDATE user_deltas
            SET correct_counts_delta = correct_counts_delta - ?
            WHERE guild_id = ? AND user_id = ?
            """,
            [(delta, guild_id, user_id) for guild_id, user_id, delta in entries],
        )
        self._connection.execute("DELETE FROM user_deltas WHERE correct_counts_delta <= 0")
        self._connection.commit()

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> CountingState:
        return CountingState(
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            current_number=row["current_number"],
            high_score=row["high_score"],
            last_user_id=row["last_user_id"],
            is_active=bool(row["is_active"]),
            dirty=bool(row["dirty"]),
            version=row["version"],
        )