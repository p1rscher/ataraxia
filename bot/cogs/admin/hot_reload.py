# cogs/admin/hot_reload.py
import os
import importlib
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class HotReloadCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------ helpers

    def _discover_extensions(self) -> set[str]:
        """Walk the cogs directory and return every valid extension module path."""
        # __file__ is  bot/cogs/admin/hot_reload.py
        # so bot_dir  is  bot/
        bot_dir  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cogs_dir = os.path.join(bot_dir, "cogs")

        extensions: set[str] = set()
        for root, dirs, files in os.walk(cogs_dir):
            dirs[:] = [d for d in dirs if not d.startswith("_")]
            for filename in files:
                if filename.endswith(".py") and not filename.startswith("_"):
                    rel = os.path.relpath(os.path.join(root, filename), bot_dir)
                    extensions.add(rel.replace(os.sep, ".")[:-3])  # strip .py

        return extensions

    # ----------------------------------------------------------------- command

    @commands.command(name="reload", hidden=True)
    async def reload_cogs(self, ctx: commands.Context, sync: bool = False):
        """Hot-reload all cogs: reloads existing ones and loads any new ones.

        Usage:
            Atx.reload         – reload/load all cogs
            Atx.reload True    – reload/load all cogs AND sync the slash-command tree
        
        Owner-only. Does not restart the bot process.
        """
        if not await self.bot.is_owner(ctx.author):
            return

        discovered = self._discover_extensions()
        loaded     = set(self.bot.extensions.keys())

        reloaded:     list[str] = []
        newly_loaded: list[str] = []
        failed:       list[str] = []

        # Reload cogs that are already loaded
        for ext in sorted(discovered & loaded):
            try:
                await self.bot.reload_extension(ext)
                reloaded.append(ext)
                logger.info(f"🔄 Reloaded: {ext}")
            except Exception as e:
                failed.append(f"{ext}: {e}")
                logger.error(f"Failed to reload {ext}: {e}", exc_info=True)

        # Load cogs that are new (not yet loaded)
        for ext in sorted(discovered - loaded):
            try:
                await self.bot.load_extension(ext)
                newly_loaded.append(ext)
                logger.info(f"🆕 Loaded new: {ext}")
            except Exception as e:
                failed.append(f"{ext}: {e}")
                logger.error(f"Failed to load new {ext}: {e}", exc_info=True)

        # Optional slash-command tree sync
        synced_count: int | None = None
        if sync:
            try:
                synced = await self.bot.tree.sync()
                synced_count = len(synced)
                logger.info(f"Synced {synced_count} slash commands")
            except Exception as e:
                failed.append(f"tree.sync: {e}")
                logger.error(f"tree.sync failed: {e}", exc_info=True)

        # Build response embed
        color = discord.Color.green() if not failed else discord.Color.orange()
        embed = discord.Embed(title="🔄 Hot Reload", color=color)

        if reloaded:
            embed.add_field(
                name=f"✅ Reloaded ({len(reloaded)})",
                value="\n".join(f"`{e}`" for e in reloaded),
                inline=False,
            )
        if newly_loaded:
            embed.add_field(
                name=f"🆕 Newly Loaded ({len(newly_loaded)})",
                value="\n".join(f"`{e}`" for e in newly_loaded),
                inline=False,
            )
        if synced_count is not None:
            embed.add_field(
                name="⚡ Slash Commands Synced",
                value=str(synced_count),
                inline=True,
            )
        if failed:
            # Truncate long error messages so the embed stays readable
            lines = [f[:120] for f in failed[:10]]
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(
            text=f"{len(reloaded)} reloaded · {len(newly_loaded)} new · {len(failed)} failed"
        )

        await ctx.send(embed=embed, ephemeral=True)
        logger.info(
            f"Hot reload by {ctx.author}: "
            f"{len(reloaded)} reloaded, {len(newly_loaded)} new, {len(failed)} failed"
        )

    # ----------------------------------------------------------------- db reload

    @commands.command(name="reloaddb", hidden=True)
    async def reload_db(self, ctx: commands.Context):
        """Hot-reload the database module without restarting the bot.

        Usage:
            Atx.reloaddb

        Sequence:
          1. Close the live connection pool gracefully.
          2. importlib.reload() the database module (fresh function objects, _pool reset to None).
          3. Call init_db() to open a new pool and run schema migrations.
          4. Re-inject the new module reference into every module that holds a db reference.

        Owner-only. In-flight DB calls on other coroutines will get a pool-closed error
        during the brief window between close and re-open — this is expected and unavoidable
        without a more complex swap strategy.
        """
        if not await self.bot.is_owner(ctx.author):
            return

        old_db = self.bot.db
        errors: list[str] = []

        # 1. Close the old pool
        try:
            await old_db.close_db()
            logger.info("reloaddb: old pool closed")
        except Exception as e:
            errors.append(f"close_db: {e}")
            logger.error(f"reloaddb: close_db failed: {e}", exc_info=True)

        # 2. Reload the module
        try:
            new_db = importlib.reload(old_db)
            logger.info("reloaddb: module reloaded")
        except Exception as e:
            errors.append(f"importlib.reload: {e}")
            await ctx.send(f"❌ Fatal: could not reload db module: {e}", ephemeral=True)
            return

        # 3. Initialise a fresh pool + run migrations
        try:
            await new_db.init_db()
            logger.info("reloaddb: init_db complete")
        except Exception as e:
            errors.append(f"init_db: {e}")
            await ctx.send(f"❌ Fatal: init_db failed: {e}", ephemeral=True)
            return

        # 4. Update bot.db — cogs and events read db from self.bot.db at call time
        self.bot.db = new_db
        logger.info("reloaddb: bot.db updated")

        # Build response
        color = discord.Color.green() if not errors else discord.Color.orange()
        embed = discord.Embed(title="🗄️ DB Module Reloaded", color=color)
        embed.add_field(name="Pool", value="Closed → Reopened", inline=True)
        embed.add_field(name="Migrations", value="Run (IF NOT EXISTS)", inline=True)
        embed.add_field(
            name="Reference updated",
            value="bot.db",
            inline=True,
        )
        if errors:
            embed.add_field(
                name=f"⚠️ Warnings ({len(errors)})",
                value="\n".join(e[:120] for e in errors[:8]),
                inline=False,
            )

        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"DB hot-reload by {ctx.author}: {len(errors)} warnings")


async def setup(bot: commands.Bot):
    await bot.add_cog(HotReloadCog(bot))
