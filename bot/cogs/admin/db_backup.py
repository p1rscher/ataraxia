import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
from discord.ext import tasks

logger = logging.getLogger(__name__)


class DatabaseBackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._backup_lock = asyncio.Lock()
        self._auto_backup_loop.start()

    def cog_unload(self):
        self._auto_backup_loop.cancel()

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _backup_dir(self) -> Path:
        path = self._project_root() / "backups" / "database"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _last_backup_marker_path(self) -> Path:
        return self._backup_dir() / "last_backup_at_utc.txt"

    def _get_interval_days(self) -> float:
        raw = (os.getenv("DB_BACKUP_INTERVAL_DAYS", "0") or "0").strip()
        try:
            days = float(raw)
        except ValueError:
            logger.warning("Invalid DB_BACKUP_INTERVAL_DAYS=%r; auto backup disabled.", raw)
            return 0.0
        return max(0.0, days)

    def _bool_env(self, key: str, default: bool = False) -> bool:
        raw = (os.getenv(key, "") or "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    def _int_env(self, key: str, default: int, *, min_value: int, max_value: int) -> int:
        raw = (os.getenv(key, str(default)) or str(default)).strip()
        try:
            value = int(raw)
        except ValueError:
            logger.warning("Invalid %s=%r; using default=%d", key, raw, default)
            value = default
        return max(min_value, min(max_value, value))

    def _write_last_backup_marker(self, when: datetime):
        marker = self._last_backup_marker_path()
        timestamp = when.astimezone(timezone.utc).isoformat()
        marker.write_text(timestamp, encoding="utf-8")

    def _read_last_backup_marker(self) -> Optional[datetime]:
        marker = self._last_backup_marker_path()
        if not marker.exists():
            return None
        try:
            raw = marker.read_text(encoding="utf-8").strip()
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception as exc:
            logger.warning("Failed to read backup marker %s: %s", marker, exc)
            return None

    def _latest_backup_mtime(self) -> Optional[datetime]:
        backup_dir = self._backup_dir()
        files = []
        for pattern in ("postgres_full_*.sql", "postgres_full_*.sql.gz"):
            files.extend(backup_dir.glob(pattern))
        if not files:
            return None
        latest = max(files, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)

    def _resolve_last_backup_time(self) -> Optional[datetime]:
        return self._read_last_backup_marker() or self._latest_backup_mtime()

    def _next_due_time(self) -> Optional[datetime]:
        interval_days = self._get_interval_days()
        if interval_days <= 0:
            return None
        last = self._resolve_last_backup_time()
        if last is None:
            return datetime.now(timezone.utc)
        return last + timedelta(days=interval_days)

    def _is_auto_backup_due(self) -> bool:
        next_due = self._next_due_time()
        if next_due is None:
            return False
        return datetime.now(timezone.utc) >= next_due

    def _cleanup_old_backups(self, backup_dir: Path, keep_last: int) -> tuple[int, int]:
        files = []
        for pattern in ("postgres_full_*.sql", "postgres_full_*.sql.gz"):
            files.extend(backup_dir.glob(pattern))

        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
        kept = max(1, int(keep_last))
        to_delete = files[kept:]

        deleted = 0
        for path in to_delete:
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning("Failed to delete old backup %s: %s", path, exc)

        return deleted, len(files)

    async def _upload_backup_file(
        self,
        ctx: Optional[commands.Context],
        backup_path: Path,
        upload_channel: discord.TextChannel,
    ) -> bool:
        file_size = backup_path.stat().st_size
        guild_filesize_limit = upload_channel.guild.filesize_limit if upload_channel.guild else 8 * 1024 * 1024

        if file_size > guild_filesize_limit:
            message = (
                "Backup created, but upload skipped because the file is larger than Discord's upload limit "
                f"for that server ({file_size / (1024 * 1024):.2f} MB > {guild_filesize_limit / (1024 * 1024):.2f} MB)."
            )
            if ctx is not None:
                await ctx.send(f"⚠️ {message}")
            logger.warning(message)
            return False

        try:
            await upload_channel.send(
                content=(
                    f"🗄️ Database backup from {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
                ),
                file=discord.File(str(backup_path), filename=backup_path.name),
            )
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.error("Failed to upload backup file to channel %s: %s", upload_channel.id, exc)
            if ctx is not None:
                await ctx.send(f"⚠️ Backup created, but upload failed: {exc}")
            return False

    async def _run_backup(
        self,
        *,
        source: str,
        keep_last: int,
        compress: bool,
        upload: bool,
        upload_channel: Optional[discord.TextChannel],
        ctx: Optional[commands.Context],
    ) -> Optional[dict]:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            if ctx is not None:
                await ctx.send("❌ DATABASE_URL is missing. Backup cannot be created.")
            logger.error("%s backup aborted: DATABASE_URL missing.", source)
            return None

        keep_last = max(1, min(int(keep_last or 20), 500))
        compress = bool(compress)
        upload = bool(upload)

        backup_dir = self._backup_dir()
        timestamp = datetime.now(timezone.utc)
        backup_path = backup_dir / f"postgres_full_{timestamp.strftime('%Y%m%d_%H%M%S')}.sql"

        cmd = [
            "pg_dump",
            "--format=plain",
            "--encoding=UTF8",
            "--no-owner",
            "--no-privileges",
            "--blobs",
            "--file",
            str(backup_path),
            database_url,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except FileNotFoundError:
            if ctx is not None:
                await ctx.send("❌ `pg_dump` is not installed or not in PATH on this host.")
            logger.error("%s backup aborted: pg_dump missing.", source)
            return None
        except Exception as exc:
            logger.error("Failed to start pg_dump backup process (%s): %s", source, exc, exc_info=True)
            if ctx is not None:
                await ctx.send(f"❌ Failed to start backup: {exc}")
            return None

        if process.returncode != 0:
            error_text = (stderr or stdout or b"").decode("utf-8", errors="ignore").strip()
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            if ctx is not None:
                await ctx.send(f"❌ Backup failed (exit code {process.returncode}).\n```\n{error_text[:1500]}\n```")
            logger.error("%s backup failed (exit=%s): %s", source, process.returncode, error_text[:1000])
            return None

        final_path = backup_path
        if compress:
            compressed_path = backup_path.with_suffix(".sql.gz")
            try:
                with open(backup_path, "rb") as source_file, gzip.open(compressed_path, "wb", compresslevel=6) as gzip_file:
                    shutil.copyfileobj(source_file, gzip_file)
                backup_path.unlink()
                final_path = compressed_path
            except OSError as exc:
                logger.error("Backup compression failed for %s: %s", backup_path, exc, exc_info=True)
                if ctx is not None:
                    await ctx.send(f"⚠️ Backup created, but compression failed: {exc}")

        deleted_count, _ = self._cleanup_old_backups(backup_dir, keep_last)

        upload_result = None
        if upload:
            target_channel = upload_channel
            if target_channel is None:
                channel_id_env = os.getenv("DB_BACKUP_UPLOAD_CHANNEL_ID", "").strip()
                if channel_id_env.isdigit():
                    channel_obj = self.bot.get_channel(int(channel_id_env))
                    if isinstance(channel_obj, discord.TextChannel):
                        target_channel = channel_obj

            if target_channel is None:
                if ctx is not None:
                    await ctx.send(
                        "⚠️ Upload requested, but no upload channel was provided and DB_BACKUP_UPLOAD_CHANNEL_ID is missing/invalid."
                    )
                logger.warning("%s backup upload requested without valid channel.", source)
                upload_result = False
            else:
                upload_result = await self._upload_backup_file(ctx, final_path, target_channel)

        now_utc = datetime.now(timezone.utc)
        self._write_last_backup_marker(now_utc)

        size_bytes = final_path.stat().st_size if final_path.exists() else 0
        size_mb = size_bytes / (1024 * 1024)
        return {
            "path": final_path,
            "size_mb": size_mb,
            "compress": compress,
            "deleted_count": deleted_count,
            "keep_last": keep_last,
            "upload_requested": upload,
            "upload_result": upload_result,
            "timestamp": now_utc,
        }

    @tasks.loop(minutes=15)
    async def _auto_backup_loop(self):
        interval_days = self._get_interval_days()
        if interval_days <= 0:
            return

        if not self._is_auto_backup_due():
            return

        if self._backup_lock.locked():
            return

        async with self._backup_lock:
            # Re-check due state after lock to avoid races with manual backups.
            if not self._is_auto_backup_due():
                return

            keep_last = self._int_env("DB_BACKUP_KEEP_LAST", 20, min_value=1, max_value=500)
            compress = self._bool_env("DB_BACKUP_COMPRESS", True)
            upload = self._bool_env("DB_BACKUP_AUTO_UPLOAD", False)

            result = await self._run_backup(
                source="auto",
                keep_last=keep_last,
                compress=compress,
                upload=upload,
                upload_channel=None,
                ctx=None,
            )

            if result is None:
                return

            logger.info(
                "Auto database backup completed: path=%s size=%.2fMB keep_last=%d deleted=%d compress=%s upload=%s",
                result["path"],
                result["size_mb"],
                result["keep_last"],
                result["deleted_count"],
                result["compress"],
                result["upload_result"],
            )

    @_auto_backup_loop.before_loop
    async def _before_auto_backup_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="dbbackup", hidden=True)
    async def dbbackup(
        self,
        ctx: commands.Context,
        upload: Optional[bool] = False,
        keep_last: Optional[int] = 20,
        compress: Optional[bool] = True,
        upload_channel: Optional[discord.TextChannel] = None,
    ):
        """Create a full PostgreSQL backup (owner only).

        Usage examples:
        - Atx.dbbackup
        - Atx.dbbackup true
        - Atx.dbbackup true 30 true #backups
        """
        if not await self.bot.is_owner(ctx.author):
            return

        await ctx.send("🗄️ Creating full database backup... this may take a moment.")

        if self._backup_lock.locked():
            await ctx.send("⚠️ A backup is already running. Please wait for it to finish.")
            return

        async with self._backup_lock:
            result = await self._run_backup(
                source="manual",
                keep_last=max(1, min(int(keep_last or 20), 500)),
                compress=bool(compress),
                upload=bool(upload),
                upload_channel=upload_channel,
                ctx=ctx,
            )

        if result is None:
            return

        next_due = self._next_due_time()
        lines = [
            "✅ Database backup created successfully.",
            f"Path: `{result['path']}`",
            f"Size: `{result['size_mb']:.2f} MB`",
            f"Compression: `{'enabled' if result['compress'] else 'disabled'}`",
            f"Retention: kept latest `{result['keep_last']}` file(s), deleted `{result['deleted_count']}` old file(s)",
        ]
        if result["upload_requested"]:
            lines.append(f"Upload: `{'done' if result['upload_result'] else 'skipped/failed'}`")
        if next_due is not None:
            lines.append(f"Next automatic backup due: `{next_due.strftime('%Y-%m-%d %H:%M:%S UTC')}`")

        await ctx.send(
            "\n".join(lines)
        )

    @commands.command(name="dbbackup_status", hidden=True)
    async def dbbackup_status(self, ctx: commands.Context):
        """Show automatic database backup status and schedule (owner only)."""
        if not await self.bot.is_owner(ctx.author):
            return

        interval_days = self._get_interval_days()
        auto_enabled = interval_days > 0
        last_backup = self._resolve_last_backup_time()
        next_due = self._next_due_time()

        keep_last = self._int_env("DB_BACKUP_KEEP_LAST", 20, min_value=1, max_value=500)
        compress = self._bool_env("DB_BACKUP_COMPRESS", True)
        auto_upload = self._bool_env("DB_BACKUP_AUTO_UPLOAD", False)
        upload_channel_env = (os.getenv("DB_BACKUP_UPLOAD_CHANNEL_ID", "") or "").strip()

        now = datetime.now(timezone.utc)
        due_state = "no"
        if next_due is not None and now >= next_due:
            due_state = "yes"

        lines = [
            "🗄️ Database Backup Status",
            f"Auto backup enabled: {'yes' if auto_enabled else 'no'}",
            f"Interval days: {interval_days:.4g}",
            f"Keep last files: {keep_last}",
            f"Compression default: {'enabled' if compress else 'disabled'}",
            f"Auto upload: {'enabled' if auto_upload else 'disabled'}",
            f"Upload channel env: {upload_channel_env or 'not set'}",
            f"Backup currently running: {'yes' if self._backup_lock.locked() else 'no'}",
            f"Last successful backup: {last_backup.strftime('%Y-%m-%d %H:%M:%S UTC') if last_backup else 'never'}",
            f"Next automatic due: {next_due.strftime('%Y-%m-%d %H:%M:%S UTC') if next_due else 'disabled'}",
            f"Due now: {due_state}",
        ]

        await ctx.send("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseBackupCog(bot))
