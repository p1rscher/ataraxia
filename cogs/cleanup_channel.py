# cogs/clear_logs.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Optional

from core import database_pg as db

class CleanupChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    cleanup_group = app_commands.Group(name="channel", description="Cleanup messages in a channel")

    @cleanup_group.command(name="cleanup", description="Delete messages in a channel based on criteria")
    @app_commands.describe(
        channel="The target text channel (default: current channel)",
        amount="The number of messages (meaning depends on the mode)",
        mode="Mode: 'keep' = keep X latest, 'delete' = delete X latest",
        only_bot="Delete only bot messages? (Default: False)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Keep latest X messages", value="keep"),
        app_commands.Choice(name="Delete latest X messages", value="delete")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def clear_channel(
        self, 
        ctx: discord.Interaction, 
        amount: int = 10,
        mode: str = "delete",
        channel: Optional[discord.TextChannel] = None,
        only_bot: bool = False
    ):
        # Only for admins
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("Only administrators can use this command.", ephemeral=True)
            return

        # Use current channel by default if none is specified
        target_channel = channel or ctx.channel

        # Check if bot has permission to delete messages
        if not target_channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.response.send_message(
                f"I don't have permission to delete messages in {target_channel.mention}.",
                ephemeral=True
            )
            return

        # Dynamic description based on mode
        if mode == "keep":
            description = f"Keep the {amount} latest messages.\n"
        else:  # mode == "delete"
            description = f"Delete the {amount} latest messages.\n"

        # Send initial response
        await ctx.response.send_message(
            f"Starting to delete messages in {target_channel.mention}...\n"
            f"{description}"
            f"{'Deleting only bot messages.' if only_bot else 'Deleting all messages.'}",
            ephemeral=True
        )

        # Collect all messages
        messages_to_delete = []

        # First, retrieve all messages
        async for msg in target_channel.history(limit=None):
            # Check if we should delete the message based on the criteria
            if only_bot and not msg.author.bot:
                continue  # Skip non-bot messages if only_bot=True

            messages_to_delete.append(msg)

        # Sort by date (newest first)
        messages_to_delete.sort(key=lambda m: m.created_at, reverse=True)

        # Select messages based on mode
        if mode == "keep":
            # Keep the latest X, delete the rest
            if len(messages_to_delete) > amount:
                messages_to_delete = messages_to_delete[amount:]  # Skip the latest X
            else:
                # Not enough messages to delete
                await ctx.followup.send(
                    f"There are only {len(messages_to_delete)} messages in the channel, which is less than the {amount} to keep.",
                    ephemeral=True
                )
                return
        else:  # mode == "delete"
            # Delete the latest X
            if len(messages_to_delete) >= amount:
                messages_to_delete = messages_to_delete[:amount]  # Keep only the latest X
            else:
                # Not enough messages to delete
                await ctx.followup.send(
                    f"There are only {len(messages_to_delete)} messages in the channel, all will be deleted.",
                    ephemeral=True
                )

        # Reverse to delete oldest first (for more efficient deletion)
        messages_to_delete.reverse()
        
        total = len(messages_to_delete)
        deleted = 0
        status_msg = await ctx.followup.send(f"Deleting {total} messages...", ephemeral=True)

        # Delete messages in batches of 100 (Discord limit)
        batch_size = 100
        for i in range(0, len(messages_to_delete), batch_size):
            batch = messages_to_delete[i:i+batch_size]
            recent_batch = [m for m in batch if (discord.utils.utcnow() - m.created_at).days < 13]
            old_batch = [m for m in batch if (discord.utils.utcnow() - m.created_at).days >= 13]

            # Bulk delete for recent messages (faster)
            if recent_batch:
                try:
                    await target_channel.delete_messages(recent_batch)
                    deleted += len(recent_batch)

                    for msg in recent_batch:
                        await db.mark_message_deleted(msg.id)

                    # Status update every 500 deleted messages
                    if deleted % 500 == 0 or deleted == total:
                        await status_msg.edit(content=f"Deleted: {deleted}/{total} messages...")

                except discord.HTTPException as e:
                    await ctx.followup.send(f"Error deleting messages in bulk: {e}", ephemeral=True)

            # Delete individually for older messages (> 13 days)
            for old_msg in old_batch:
                try:
                    await old_msg.delete()
                    await db.mark_message_deleted(old_msg.id)
                    deleted += 1
                    
                    # Status update every 50 deleted messages
                    if deleted % 50 == 0 or deleted == total:
                        await status_msg.edit(content=f"Deleted: {deleted}/{total} messages...")
                        
                except discord.HTTPException:
                    pass

                # Short pause to avoid rate limits
                await asyncio.sleep(0.3)

        # Conclusion
        mode_text = f"Kept the latest {amount}." if mode == "keep" else f"Deleted the latest {amount}."
        await status_msg.edit(content=f"Done! Deleted {deleted} messages. {mode_text}")


async def setup(bot):
    await bot.add_cog(CleanupChannelCog(bot))
