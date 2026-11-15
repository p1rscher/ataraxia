"""Applies settings changed through the web dashboard to the running bot.

The dashboard API writes to the same database as the bot. Most settings are
read from the database every time they are needed, but the leveling system
keeps XP settings and multipliers in memory for a few minutes. The API records
every change in ``dashboard_changes``; this cog polls that table and drops the
cached values of the affected guild, so changes take effect within seconds.
"""

import logging
from datetime import timedelta

from discord.ext import commands, tasks

from core import database_pg as db

logger = logging.getLogger(__name__)

POLL_SECONDS = 10
# Re-read a little of the past on every poll: a change can become visible
# slightly after its timestamp. Dropping a cache entry twice is harmless.
OVERLAP = timedelta(seconds=5)


class DashboardSyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cursor = None

    async def cog_load(self):
        self.poll.start()

    async def cog_unload(self):
        self.poll.cancel()

    def apply_change(self, guild_id: int, scope: str):
        cache = getattr(self.bot, "leveling_cache", None)
        if cache is None:
            return
        if scope == "xp":
            cache.invalidate_guild_settings(guild_id)
        elif scope == "multipliers":
            cache.invalidate_multiplier_cache(guild_id)

    async def poll_once(self) -> int:
        if self._cursor is None:
            self._cursor = await db.get_database_time()
            return 0
        changes = await db.get_dashboard_changes(self._cursor - OVERLAP)
        for change in changes:
            self.apply_change(change["guild_id"], change["scope"])
            if change["changed_at"] > self._cursor:
                self._cursor = change["changed_at"]
                logger.info("Dashboard changed %s settings of guild %s", change["scope"], change["guild_id"])
        return len(changes)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll(self):
        try:
            await self.poll_once()
        except Exception:
            logger.warning("Could not check for dashboard changes", exc_info=True)

    @poll.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(DashboardSyncCog(bot))
