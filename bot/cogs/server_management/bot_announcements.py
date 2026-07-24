# cogs/server_management/bot_announcements.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class BotAnnouncementsCog(commands.Cog):
    """Lets server administrators configure a channel to receive bot-wide
    announcements (maintenance notices, updates, etc.)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="botannouncements",
        description="Configure the bot announcement channel for this server",
    )
    async def announcements_group(self, ctx: commands.Context):
        pass

    # ── /botannouncements set ──────────────────────────────
    @announcements_group.command(
        name="set",
        description="Set the channel where bot announcements will be posted",
    )
    @app_commands.describe(
        channel="The text channel to receive bot announcements"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
    ):
        assert ctx.guild is not None

        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "❌ You need **Administrator** permissions to use this command.",
                ephemeral=True,
            )
            return

        # Verify the bot can send messages in the target channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(
                f"❌ I don't have permission to send messages in {channel.mention}.",
                ephemeral=True,
            )
            return

        await db.set_announcement_channel(ctx.guild.id, channel.id)

        embed = discord.Embed(
            title="✅ Bot Announcements Configured",
            description=(
                f"Bot announcements will now be posted in {channel.mention}.\n\n"
                "This channel will receive important notices like **maintenance windows**, "
                "**feature updates**, and **downtime alerts** from the bot developers."
            ),
            color=await get_guild_color(ctx.guild.id),
        )
        embed.set_footer(text="Use /botannouncements clear to disable.")
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(
            f"Guild {ctx.guild.id} set announcement channel to {channel.id}"
        )

    # ── /botannouncements clear ────────────────────────────
    @announcements_group.command(
        name="clear",
        description="Stop receiving bot announcements in this server",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def clear_channel(self, ctx: commands.Context):
        assert ctx.guild is not None

        if not ctx.author.guild_permissions.administrator:
            await ctx.send(
                "❌ You need **Administrator** permissions to use this command.",
                ephemeral=True,
            )
            return

        await db.clear_announcement_channel(ctx.guild.id)

        embed = discord.Embed(
            title="✅ Bot Announcements Disabled",
            description="This server will no longer receive bot announcements.",
            color=await get_guild_color(ctx.guild.id),
        )
        await ctx.send(embed=embed, ephemeral=True)
        logger.info(f"Guild {ctx.guild.id} cleared announcement channel")

    # ── /botannouncements status ───────────────────────────
    @announcements_group.command(
        name="status",
        description="Check the current bot announcement channel",
    )
    @commands.guild_only()
    async def status(self, ctx: commands.Context):
        assert ctx.guild is not None

        channel_id = await db.get_announcement_channel_id(ctx.guild.id)

        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                description = f"Bot announcements are being sent to {channel.mention}."
            else:
                description = (
                    f"⚠️ The configured channel (`{channel_id}`) no longer exists.\n"
                    "Use `/botannouncements set` to configure a new channel."
                )
        else:
            description = (
                "No announcement channel is configured for this server.\n"
                "Use `/botannouncements set` to start receiving bot announcements."
            )

        embed = discord.Embed(
            title="📢 Bot Announcements Status",
            description=description,
            color=await get_guild_color(ctx.guild.id),
        )
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotAnnouncementsCog(bot))
