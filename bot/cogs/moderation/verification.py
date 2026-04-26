# cogs/verification.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="verification", description="Manage verification system")
    async def verification_group(self, ctx: commands.Context):
        pass

    @verification_group.command(name="setup", description="Create a verification message")
    @app_commands.describe(
        channel="Which channel should the verification message be posted in?",
        role="Which role should be assigned after verification?",
        title="The title of the verification message (optional)",
        message="The text of the verification message (optional)",
        footer="The footer text of the verification message (optional)",
        hex_color="Optional custom hex color for this embed (e.g. #FF5733)"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup_verification(
        self, 
        ctx: commands.Context, 
        channel: discord.TextChannel, 
        role: discord.Role,
        title: str = "Verification",
        message: str = "React with ✅ to get verified.",
        footer: str = "",
        hex_color: str = None
    ):
        # Check permissions
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Only administrators can use this command.", ephemeral=True)
            return

        # Check if bot can assign the role
        if role.position >= ctx.guild.me.top_role.position:
            await ctx.send(
                f"The role {role.mention} is higher than my highest role. "
                "I cannot assign this role.", ephemeral=True
            )
            return

        # Check if old verification message exists and delete it
        old_verification = await db.get_verification(ctx.guild.id)
        if old_verification:
            old_message_id, old_channel_id, old_role_id = old_verification
            try:
                old_channel = ctx.guild.get_channel(old_channel_id)
                if old_channel:
                    old_message = await old_channel.fetch_message(old_message_id)
                    await old_message.delete()
                    logger.info(f"Deleted old verification message {old_message_id} in guild {ctx.guild.id}")
            except discord.NotFound:
                logger.debug(f"Old verification message {old_message_id} not found (already deleted)")
            except Exception as e:
                logger.error(f"Error deleting old verification message: {e}")

        # Determine Embed Color
        if hex_color:
            try:
                embed_color = discord.Color.from_str(hex_color)
            except ValueError:
                embed_color = await get_guild_color(ctx.guild.id, 'color_verification')
        else:
            embed_color = await get_guild_color(ctx.guild.id, 'color_verification')

        # Create Embed
        embed = discord.Embed(
            title=title,
            description=message,
            color=embed_color
        )

        if footer:
            embed.set_footer(text=f"{footer}")

        # Send message
        await ctx.send(
            f"Verification message will be created in {channel.mention}...", ephemeral=True
        )
        verification_msg = await channel.send(embed=embed)

        # Add reaction
        await verification_msg.add_reaction("✅")

        # Save to DB
        await db.set_verification(
            ctx.guild.id,
            verification_msg.id,
            channel.id,
            role.id
        )

        # Confirm setup
        try:
            await ctx.send(
                f"Verification system set up in {channel.mention}!\n"
                f"Role after verification: {role.mention}", ephemeral=True
            )
        except:
            pass

async def setup(bot):
    await bot.add_cog(VerificationCog(bot))
