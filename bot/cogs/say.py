# cogs/say.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class SayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_say_log(
        self,
        ctx: discord.Interaction,
        sent_message: discord.Message,
        original_message: Optional[str],
        replied_message_id: Optional[str],
        attachment: Optional[discord.Attachment],
    ):
        assert ctx.guild is not None
        assert ctx.guild_id is not None

        log_channel_id = await db.get_say_log_channel_id(ctx.guild_id)
        if log_channel_id is None:
            return

        target_channel = ctx.guild.get_channel(log_channel_id)
        if target_channel is None:
            try:
                target_channel = await ctx.guild.fetch_channel(log_channel_id)
            except Exception:
                logger.warning("Configured /say log channel %s could not be fetched in guild %s", log_channel_id, ctx.guild_id)
                return

        if not isinstance(target_channel, (discord.TextChannel, discord.Thread)):
            return

        source_channel_value = (
            ctx.channel.mention
            if isinstance(ctx.channel, (discord.TextChannel, discord.Thread))
            else f"`{ctx.channel_id}`"
        )

        embed = discord.Embed(
            title="/say Command Used",
            color=await get_guild_color(ctx.guild_id),
            timestamp=ctx.created_at,
        )
        embed.add_field(name="User", value=f"{ctx.user.mention}\n`{ctx.user.id}`", inline=True)
        embed.add_field(name="Source Channel", value=source_channel_value, inline=True)
        embed.add_field(name="Sent Message", value=f"[Jump to message]({sent_message.jump_url})", inline=True)
        embed.add_field(name="Reply Target", value=f"`{replied_message_id}`" if replied_message_id else "None", inline=True)
        embed.add_field(name="Attachment", value=attachment.url if attachment else "None", inline=True)
        embed.add_field(name="Attachment Name", value=attachment.filename if attachment else "None", inline=True)

        if original_message:
            content_value = original_message if len(original_message) <= 1024 else original_message[:1021] + "..."
        else:
            content_value = "No text provided"
        embed.add_field(name="Content", value=content_value, inline=False)

        try:
            await target_channel.send(embed=embed)
        except Exception:
            logger.exception("Failed to send /say usage log in guild %s", ctx.guild_id)

    @app_commands.command(name="say", description="Responds with a message or attachment")
    @app_commands.describe(message="The message to say", message_id="Optional: ID of the message to reply to", attachment="Optional: Attachment to send")
    @app_commands.guild_only()
    async def say(self, ctx: discord.Interaction, message: Optional[str] = None, message_id: Optional[str] = None, attachment: Optional[discord.Attachment] = None):
        assert ctx.guild is not None
        assert isinstance(ctx.user, discord.Member)
        assert isinstance(ctx.channel, (discord.TextChannel, discord.Thread))

        # Check admin permissions
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("❌ You need administrator permissions for this command!", ephemeral=True)
            return
            
        if not message and not attachment:
            await ctx.response.send_message("❌ You must provide either a message or an attachment!", ephemeral=True)
            return
            
        channel: discord.TextChannel | discord.Thread = ctx.channel
        ref = None
        
        if message_id:
            try:
                # Validate the ID
                ref_id = int(message_id)
                ref = discord.MessageReference(message_id=ref_id, channel_id=channel.id)
            except ValueError:
                await ctx.response.send_message("❌ Invalid Message ID provided. It must be a number.", ephemeral=True)
                return
                
        file_to_send = None
        if attachment:
            try:
                file_to_send = await attachment.to_file()
            except discord.HTTPException:
                await ctx.response.send_message("❌ Failed to process the attachment.", ephemeral=True)
                return

        try:
            send_kwargs = {}
            if message is not None:
                send_kwargs["content"] = message
            if ref is not None:
                send_kwargs["reference"] = ref
            if file_to_send is not None:
                send_kwargs["file"] = file_to_send

            sent_message = await channel.send(**send_kwargs)
            await self._send_say_log(ctx, sent_message, message, message_id, attachment)
            await ctx.response.send_message("✅ Message sent silently!", ephemeral=True)
        except discord.HTTPException:
            # Fallback if the message ID was not found
            if ref:
                await ctx.response.send_message("❌ Failed to reply. Is the Message ID correct and in this channel?", ephemeral=True)
            else:
                await ctx.response.send_message("❌ Failed to send message.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and webhooks
        if message.author.bot or not message.guild:
            return
            
        # Catch raw raw text starting with "/say " or "!say " when used as a Discord reply.
        # This handles the case where Discord drops the reply state for slash commands.
        if (message.content.startswith("/say ") or message.content.startswith("!say ")) and message.reference:
            # Enforce the same permission check
            if not isinstance(message.author, discord.Member):
                return
            if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                return
            if not message.author.guild_permissions.administrator:
                return
                
            content = message.content[5:].strip()
            if not content:
                return
                
            try:
                # Fetch the referenced message
                if message.reference.message_id is None:
                    return
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                # Reply to the referenced message
                await ref_msg.reply(content)
                # Delete the user's typing to make it seem like the bot replied seamlessly
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

async def setup(bot):
    await bot.add_cog(SayCog(bot))
