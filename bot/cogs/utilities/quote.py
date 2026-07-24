import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class QuoteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Add a context menu command for messages
        self.ctx_menu = app_commands.ContextMenu(
            name='Quote Message',
            callback=self.quote_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @commands.hybrid_command(name="quoteset", description="Set the channel where quotes will be sent.")
    @app_commands.describe(channel="The channel to send quotes to. Leave empty to disable.")
    @commands.has_permissions(administrator=True)
    async def quoteset(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        if channel:
            await db.set_quote_channel(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Quotes will now be sent to {channel.mention}.", ephemeral=True)
        else:
            await db.clear_quote_channel(ctx.guild.id)
            await ctx.send("✅ Quotes feature has been disabled.", ephemeral=True)

    async def quote_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        await self._process_quote(interaction, message)

    @commands.hybrid_command(name="quote", description="Quote a message to the configured quotes channel.")
    @app_commands.describe(message_id="The ID or link of the message to quote (optional if replying)")
    async def quote_cmd(self, ctx: commands.Context, message_id: Optional[str] = None):
        # Determine the message to quote
        target_message = None

        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                # Fetch message if replied
                target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.HTTPException:
                pass
        
        if not target_message and message_id:
            # Check if it's a link
            if "discord.com/channels/" in message_id:
                parts = message_id.split("/")
                try:
                    ch_id = int(parts[-2])
                    msg_id = int(parts[-1])
                    channel = self.bot.get_channel(ch_id)
                    if channel:
                        target_message = await channel.fetch_message(msg_id)
                except (ValueError, IndexError, discord.HTTPException, AttributeError):
                    pass
            else:
                try:
                    target_message = await ctx.channel.fetch_message(int(message_id))
                except (ValueError, discord.HTTPException):
                    pass

        if not target_message:
            await ctx.send("❌ Could not find the message to quote. Please reply to a message or provide a valid message ID/link.", ephemeral=True)
            return

        # Use the interaction if it's a slash command, or ctx if it's a text command
        target = ctx.interaction if ctx.interaction else ctx
        await self._process_quote(target, target_message)

    async def _process_quote(self, ctx_or_interaction, message: discord.Message):
        guild = message.guild
        if not guild:
            await self._send_response(ctx_or_interaction, "❌ This command can only be used in a server.", ephemeral=True)
            return

        quote_channel_id = await db.get_quote_channel_id(guild.id)
        if not quote_channel_id:
            await self._send_response(ctx_or_interaction, "❌ A quote channel hasn't been configured. Administrators can use `/quoteset` to set it up.", ephemeral=True)
            return

        quote_channel = guild.get_channel(quote_channel_id)
        if not quote_channel:
            try:
                quote_channel = await guild.fetch_channel(quote_channel_id)
            except discord.HTTPException:
                pass
            
        if not quote_channel or not isinstance(quote_channel, discord.TextChannel):
            await self._send_response(ctx_or_interaction, "❌ The configured quote channel is missing or invalid. Please update it with `/quoteset`.", ephemeral=True)
            return

        # Check permissions to send messages
        me = guild.me if guild else None
        if me and not quote_channel.permissions_for(me).send_messages:
            await self._send_response(ctx_or_interaction, f"❌ I don't have permission to send messages in {quote_channel.mention}.", ephemeral=True)
            return

        # Build embed
        color = await get_guild_color(guild.id)
        embed = discord.Embed(
            description=message.content,
            color=color,
            timestamp=message.created_at
        )
        
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        
        # Add jump URL
        embed.add_field(name="\u200b", value=f"[**Jump to message**]({message.jump_url})", inline=False)

        # Handle attachments
        if message.attachments:
            # Prioritize images
            image_attachment = next((a for a in message.attachments if a.content_type and a.content_type.startswith('image/')), None)
            if image_attachment:
                embed.set_image(url=image_attachment.url)
            else:
                embed.add_field(name="Attachment", value=message.attachments[0].url)
                
        embed.set_footer(text=f"Quoted from #{message.channel.name}")

        try:
            await quote_channel.send(embed=embed)
            await self._send_response(ctx_or_interaction, f"✅ Message quoted successfully in {quote_channel.mention}!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send quote: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while sending the quote.", ephemeral=True)

    async def _send_response(self, ctx_or_interaction, content: str, ephemeral: bool = False):
        if isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(content, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await ctx_or_interaction.send(content, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(QuoteCog(bot))
