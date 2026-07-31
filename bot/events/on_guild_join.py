# events/on_guild_join.py
import discord
import asyncio
import logging
from typing import Optional
from utils import backfill_guild_messages

logger = logging.getLogger(__name__)

# set bot reference from main.py
bot: Optional[discord.Client] = None


async def initialize_guild_join_state(
    guild: discord.Guild,
    *,
    run_intro: bool = True,
    run_backfill: bool = True,
    run_command_sync: bool = True,
):
    """Apply new-guild initialization steps; reusable for startup reconciliation."""
    from core import database_pg as db

    try:
        await db.upsert_server(guild)
        # Disable level-up notifications by default for newly joined servers.
        # Admins can still enable them explicitly via /log set type:Level Logs.
        await db.disable_level_log_channel(guild.id)
        logger.info(f"Upserted new guild {guild.name} into database.")
    except Exception as e:
        logger.error(f"Failed to upsert new guild {guild.name} to DB: {e}")

    if run_intro:
        try:
            channel = None
            if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                channel = guild.system_channel
            else:
                keywords = ['general', 'chat', 'main', 'welcome', 'lounge']
                for c in guild.text_channels:
                    if c.permissions_for(guild.me).send_messages:
                        if any(k in c.name.lower() for k in keywords):
                            channel = c
                            break
                if not channel:
                    for c in guild.text_channels:
                        if c.permissions_for(guild.me).send_messages:
                            channel = c
                            break

            if channel:
                embed = discord.Embed(
                    title="🌸 Thanks for adding Ataraxia!",
                    description=(
                        f"Hi there! I'm **Ataraxia**, your all-in-one server management, moderation, and community bot.\n\n"
                        "**To get started flawlessly, I highly recommend running:**\n"
                        "`/quicksetup`\n\n"
                        "This interactive wizard will help you configure everything from Logging and Welcome Messages to Auto-Roles and Support Tickets in just a few clicks!\n\n"
                        "For a full list of my commands, try `/help` or visit [ataraxia-bot.com](https://ataraxia-bot.com)."
                    ),
                    color=discord.Color.from_rgb(255, 153, 204)
                )
                await channel.send(embed=embed)
                logger.info(f"Sent introduction message to {guild.name} in #{channel.name}")
        except Exception as e:
            logger.error(f"Failed to send intro message to {guild.name}: {e}")

    if run_backfill:
        await asyncio.sleep(20)
        try:
            await backfill_guild_messages(guild, backfill_hours=24*7*4)
            logger.info(f"Backfill completed for {guild.name}")
        except Exception as e:
            logger.error(f"Backfill failed for {guild.name}: {e}")

    if run_command_sync:
        try:
            synced = await bot.tree.sync(guild=discord.Object(id=guild.id))
            logger.info(f"Synced {len(synced)} commands to {guild.name}")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

async def on_guild_join(guild: discord.Guild):
    """Wird getriggert wenn der Bot einem neuen Server beitritt"""
    logger.info(f"Bot joined new guild: {guild.name} (ID: {guild.id})")
    await initialize_guild_join_state(guild)

