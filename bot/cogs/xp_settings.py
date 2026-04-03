# cogs/xp_settings.py
import discord
from discord.ext import commands
from discord import app_commands
from core import database_pg as db
from utils.embeds import get_guild_color

class XPSettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    xp_group = app_commands.Group(name="xp", description="Manage XP settings")

    @xp_group.command(name="cooldown", description="Set the XP cooldown for messages")
    @app_commands.describe(seconds="Cooldown in seconds between XP gains from messages (default: 60)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_xp_cooldown(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0:
            await interaction.response.send_message("❌ Cooldown must be 0 or greater!", ephemeral=True)
            return
        
        if seconds > 3600:
            await interaction.response.send_message("❌ Cooldown cannot be greater than 1 hour (3600 seconds)!", ephemeral=True)
            return
        
        await db.set_xp_cooldown(interaction.guild.id, seconds)
        
        if seconds == 0:
            await interaction.response.send_message(
                "✅ XP cooldown disabled! Users can gain XP from every message.",
                ephemeral=True
            )
        else:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            
            if minutes > 0 and remaining_seconds > 0:
                time_str = f"{minutes} minute(s) and {remaining_seconds} second(s)"
            elif minutes > 0:
                time_str = f"{minutes} minute(s)"
            else:
                time_str = f"{seconds} second(s)"
            
            await interaction.response.send_message(
                f"✅ XP cooldown set to **{time_str}**. Users must wait this long between XP gains from messages.",
                ephemeral=True
            )

    @xp_group.command(name="voiceinterval", description="Set the voice XP grant interval")
    @app_commands.describe(seconds="Interval in seconds between voice XP grants (default: 60 = 1 minute)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_voice_interval(self, interaction: discord.Interaction, seconds: int):
        if seconds < 60:
            await interaction.response.send_message("❌ Voice interval must be at least 60 seconds!", ephemeral=True)
            return
        
        if seconds > 3600:
            await interaction.response.send_message("❌ Voice interval cannot be greater than 1 hour (3600 seconds)!", ephemeral=True)
            return
        
        await db.set_voice_xp_interval(interaction.guild.id, seconds)
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        if minutes > 0 and remaining_seconds > 0:
            time_str = f"{minutes} minute(s) and {remaining_seconds} second(s)"
        elif minutes > 0:
            time_str = f"{minutes} minute(s)"
        else:
            time_str = f"{seconds} second(s)"
        
        await interaction.response.send_message(
            f"✅ Voice XP interval set to **{time_str}**. Users in voice channels will gain XP every {time_str}.",
            ephemeral=True
        )

    @xp_group.command(name="messagexp", description="Set the XP range for messages")
    @app_commands.describe(
        min_xp="Minimum XP per message (default: 40)",
        max_xp="Maximum XP per message (default: 60)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_message_xp(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        if min_xp < 1 or max_xp < 1:
            await interaction.response.send_message("❌ XP values must be at least 1!", ephemeral=True)
            return
        
        if min_xp > max_xp:
            await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP!", ephemeral=True)
            return
        
        if max_xp > 1000:
            await interaction.response.send_message("❌ Maximum XP cannot exceed 1000!", ephemeral=True)
            return
        
        await db.set_message_xp_range(interaction.guild.id, min_xp, max_xp)
        await interaction.response.send_message(
            f"✅ Message XP set to **{min_xp}-{max_xp}** XP per message.",
            ephemeral=True
        )

    @xp_group.command(name="voicexp", description="Set the XP range for voice activity")
    @app_commands.describe(
        min_xp="Minimum XP per interval (default: 15)",
        max_xp="Maximum XP per interval (default: 25)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_voice_xp(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        if min_xp < 1 or max_xp < 1:
            await interaction.response.send_message("❌ XP values must be at least 1!", ephemeral=True)
            return
        
        if min_xp > max_xp:
            await interaction.response.send_message("❌ Minimum XP cannot be greater than maximum XP!", ephemeral=True)
            return
        
        if max_xp > 1000:
            await interaction.response.send_message("❌ Maximum XP cannot exceed 1000!", ephemeral=True)
            return
        
        await db.set_voice_xp_range(interaction.guild.id, min_xp, max_xp)
        await interaction.response.send_message(
            f"✅ Voice XP set to **{min_xp}-{max_xp}** XP per interval.",
            ephemeral=True
        )

    @xp_group.command(name="info", description="View current XP settings")
    @app_commands.guild_only()
    async def xp_info(self, interaction: discord.Interaction):
        settings = await db.get_all_xp_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="⚙️ XP Settings",
            color=await get_guild_color(interaction.guild.id)
        )
        
        # Message cooldown
        cooldown = settings['message_cooldown']
        if cooldown == 0:
            cooldown_str = "**Disabled** - Users gain XP from every message"
        else:
            minutes = cooldown // 60
            remaining_seconds = cooldown % 60
            
            if minutes > 0 and remaining_seconds > 0:
                cooldown_str = f"**{minutes}m {remaining_seconds}s**"
            elif minutes > 0:
                cooldown_str = f"**{minutes}m**"
            else:
                cooldown_str = f"**{cooldown}s**"
        
        embed.add_field(
            name="📝 Message XP Cooldown",
            value=cooldown_str,
            inline=False
        )
        
        # Message XP range
        embed.add_field(
            name="💬 Message XP Range",
            value=f"**{settings['message_xp_min']}-{settings['message_xp_max']}** XP per message",
            inline=True
        )
        
        # Voice interval
        voice_interval = settings['voice_interval']
        v_minutes = voice_interval // 60
        v_seconds = voice_interval % 60
        
        if v_minutes > 0 and v_seconds > 0:
            interval_str = f"**{v_minutes}m {v_seconds}s**"
        elif v_minutes > 0:
            interval_str = f"**{v_minutes}m**"
        else:
            interval_str = f"**{voice_interval}s**"
        
        embed.add_field(
            name="⏱️ Voice XP Interval",
            value=interval_str,
            inline=True
        )
        
        # Voice XP range
        embed.add_field(
            name="🎙️ Voice XP Range",
            value=f"**{settings['voice_xp_min']}-{settings['voice_xp_max']}** XP per interval",
            inline=True
        )

        embed.add_field(
            name="Formular for Level XP",
            value="XP needed for level: 15 * (level ^ 2) + 60 * level + 25"
        )
        
        embed.set_footer(text="Use /xp commands to change settings")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    multiplier_group = app_commands.Group(name="xpmultiplier", description="Manage XP multipliers")

    @multiplier_group.command(name="channel", description="Set XP multiplier for a channel")
    @app_commands.describe(
        channel="The text or voice channel",
        multiplier="XP multiplier (e.g., 1.5 = 150%, 0.5 = 50%, 2.0 = 200%)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_channel_mult(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel, multiplier: float):
        if multiplier < 0:
            await interaction.response.send_message("❌ Multiplier cannot be negative!", ephemeral=True)
            return
        
        if multiplier > 10:
            await interaction.response.send_message("❌ Multiplier cannot exceed 10x!", ephemeral=True)
            return
        
        await db.set_channel_multiplier(interaction.guild.id, channel.id, multiplier)
        await interaction.response.send_message(
            f"✅ Set XP multiplier for {channel.mention} to **{multiplier}x**",
            ephemeral=True
        )

    @multiplier_group.command(name="removechannel", description="Remove XP multiplier from a channel")
    @app_commands.describe(channel="The channel to remove multiplier from")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def remove_channel_mult(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        await db.remove_channel_multiplier(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"✅ Removed XP multiplier from {channel.mention}",
            ephemeral=True
        )

    @multiplier_group.command(name="role", description="Set XP multiplier for a role")
    @app_commands.describe(
        role="The role",
        multiplier="XP multiplier (e.g., 1.5 = 150%, 0.5 = 50%, 2.0 = 200%)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_role_mult(self, interaction: discord.Interaction, role: discord.Role, multiplier: float):
        if multiplier < 0:
            await interaction.response.send_message("❌ Multiplier cannot be negative!", ephemeral=True)
            return
        
        if multiplier > 10:
            await interaction.response.send_message("❌ Multiplier cannot exceed 10x!", ephemeral=True)
            return
        
        await db.set_role_multiplier(interaction.guild.id, role.id, multiplier)
        await interaction.response.send_message(
            f"✅ Set XP multiplier for {role.mention} to **{multiplier}x**",
            ephemeral=True
        )

    @multiplier_group.command(name="removerole", description="Remove XP multiplier from a role")
    @app_commands.describe(role="The role to remove multiplier from")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def remove_role_mult(self, interaction: discord.Interaction, role: discord.Role):
        await db.remove_role_multiplier(interaction.guild.id, role.id)
        await interaction.response.send_message(
            f"✅ Removed XP multiplier from {role.mention}",
            ephemeral=True
        )

    @multiplier_group.command(name="list", description="List all active XP multipliers")
    @app_commands.guild_only()
    async def list_multipliers(self, interaction: discord.Interaction):
        channel_mults = await db.get_all_channel_multipliers(interaction.guild.id)
        role_mults = await db.get_all_role_multipliers(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔢 XP Multipliers",
            color=await get_guild_color(interaction.guild.id)
        )
        
        # Channel multipliers
        if channel_mults:
            channel_text = []
            for channel_id, mult in channel_mults:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channel_text.append(f"{channel.mention}: **{mult}x**")
            
            if channel_text:
                embed.add_field(
                    name="📺 Channel Multipliers",
                    value="\n".join(channel_text),
                    inline=False
                )
        
        # Role multipliers
        if role_mults:
            role_text = []
            for role_id, mult in role_mults:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_text.append(f"{role.mention}: **{mult}x**")
            
            if role_text:
                embed.add_field(
                    name="🎭 Role Multipliers",
                    value="\n".join(role_text),
                    inline=False
                )
        
        if not channel_mults and not role_mults:
            embed.description = "No custom multipliers set."
        
        embed.set_footer(text="Multipliers stack multiplicatively")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(XPSettingsCog(bot))
