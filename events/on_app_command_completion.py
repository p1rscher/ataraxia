# events/on_app_command_completion.py
import discord
import logging

logger = logging.getLogger(__name__)

db = None

async def on_app_command_completion(ctx: discord.Interaction, command):
    """Track slash command usage"""
    try:
        await db.log_command_usage(
            command_name=command.name,
            user_id=ctx.user.id,
            guild_id=ctx.guild.id if ctx.guild else None
        )
    except Exception as e:
        logger.error(f"Failed to log command usage: {e}", exc_info=True)