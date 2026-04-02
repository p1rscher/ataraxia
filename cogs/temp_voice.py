# cogs/temp_voice.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
import logging
from core import database_pg as db

logger = logging.getLogger(__name__)


class TempVoiceControlView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="🎤 Manage your Voice Channel",
        style=discord.ButtonStyle.blurple,
        custom_id="tempvc_manage"
    )
    async def manage_button(self, ctx: discord.Interaction, button: Button):
        """Button to open the control panel"""
        # Get all temp channels of the user
        member_channels = []
        for channel in ctx.guild.voice_channels:
            owner_id = await db.get_temp_voice_owner(channel.id)
            if owner_id == ctx.user.id:
                member_channels.append(channel)
        
        if not member_channels:
            await ctx.response.send_message(
                "You don't own a temporary voice channel.",
                ephemeral=True
            )
            return
        
        # Wenn nur ein Channel: direkt öffnen
        if len(member_channels) == 1:
            control_view = ChannelControlView(member_channels[0].id)
            
            embed = discord.Embed(
                title="🎤 Voice Channel Control",
                description=f"Manage your channel: {member_channels[0].mention}",
                color=discord.Color.blue()
            )

            await ctx.response.send_message(
                embed=embed,
                view=control_view,
                ephemeral=True
            )
        else:
            # Wenn mehrere Channels: zeige Select mit Optionen
            select_view = ChannelSelectView(member_channels)
            await ctx.response.send_message(
                "Select the channel you want to manage:",
                view=select_view,
                ephemeral=True
            )

class ChannelSelectView(View):
    def __init__(self, channels: list):
        super().__init__(timeout=60)
        
        # Erstelle Select mit den Channels als Optionen
        options = [
            discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                description=f"{len(channel.members)} members"
            )
            for channel in channels[:25]  # Max 25 Optionen
        ]
        
        self.channel_select = Select(
            placeholder="Select your voice channel...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.channel_select.callback = self.select_callback
        self.add_item(self.channel_select)
    
    async def select_callback(self, interaction: discord.Interaction):
        channel_id = int(self.channel_select.values[0])
        
        control_view = ChannelControlView(channel_id)
        
        embed = discord.Embed(
            title="🎤 Voice Channel Control",
            description=f"Manage your channel: <#{channel_id}>",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=control_view,
            ephemeral=True
        )

class ChannelControlView(View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=180)  # 3 Minuten Timeout
        self.channel_id = channel_id
    
    async def interaction_check(self, ctx: discord.Interaction) -> bool:
        """Checks if the user is the owner"""
        owner_id = await db.get_temp_voice_owner(self.channel_id)
        if owner_id != ctx.user.id:
            await ctx.response.send_message(
                "Only the channel owner can do this.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="🔒 Lock", style=discord.ButtonStyle.red, row=0)
    async def lock_button(self, ctx: discord.Interaction, button: Button):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return

        await channel.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.response.send_message("🔒 Channel has been locked.", ephemeral=True)

    @discord.ui.button(label="🔓 Unlock", style=discord.ButtonStyle.green, row=0)
    async def unlock_button(self, ctx: discord.Interaction, button: Button):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return

        await channel.set_permissions(ctx.guild.default_role, connect=True)
        await ctx.response.send_message("🔓 Channel has been unlocked.", ephemeral=True)

    @discord.ui.button(label="👁️ Hide", style=discord.ButtonStyle.gray, row=0)
    async def hide_button(self, ctx: discord.Interaction, button: Button):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return

        await channel.set_permissions(ctx.guild.default_role, view_channel=False)
        await ctx.response.send_message("👁️ Channel has been hidden.", ephemeral=True)

    @discord.ui.button(label="👁️‍🗨️ Show", style=discord.ButtonStyle.gray, row=0)
    async def show_button(self, ctx: discord.Interaction, button: Button):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return

        await channel.set_permissions(ctx.guild.default_role, view_channel=True)
        await ctx.response.send_message("👁️‍🗨️ Channel is now visible.", ephemeral=True)

    @discord.ui.button(label="👤 Limit", style=discord.ButtonStyle.blurple, row=1)
    async def limit_button(self, ctx: discord.Interaction, button: Button):
        modal = UserLimitModal(self.channel_id)
        await ctx.response.send_modal(modal)

    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.blurple, row=1)
    async def rename_button(self, ctx: discord.Interaction, button: Button):
        modal = RenameModal(self.channel_id)
        await ctx.response.send_modal(modal)

    @discord.ui.button(label="➕ Invite", style=discord.ButtonStyle.blurple, row=1)
    async def invite_button(self, ctx: discord.Interaction, button: Button):
        modal = InviteUserModal(self.channel_id)
        await ctx.response.send_modal(modal)

    @discord.ui.button(label="🚫 Kick", style=discord.ButtonStyle.blurple, row=1)
    async def kick_button(self, ctx: discord.Interaction, button: Button):
        modal = KickUserModal(self.channel_id)
        await ctx.response.send_modal(modal)

    @discord.ui.button(label="👑 Transfer", style=discord.ButtonStyle.gray, row=2)
    async def transfer_button(self, ctx: discord.Interaction, button: Button):
        modal = TransferOwnerModal(self.channel_id)
        await ctx.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red, row=2)
    async def delete_button(self, ctx: discord.Interaction, button: Button):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return

        await ctx.response.send_message("Channel is being deleted...", ephemeral=True)

        try:
            await db.remove_temp_voice_channel(channel.id)
            await channel.delete(reason=f"Deleted by {ctx.user}")
        except Exception as e:
            await ctx.followup.send(f"Error: {e}", ephemeral=True)


# Modals
class UserLimitModal(discord.ui.Modal, title="Set User Limit"):
    limit = discord.ui.TextInput(
        label="Max Users",
        placeholder="0 = unlimited, 1-99",
        required=True,
        max_length=2
    )
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
    
    async def on_submit(self, ctx: discord.Interaction):
        try:
            limit = int(self.limit.value)
            if limit < 0 or limit > 99:
                raise ValueError
        except ValueError:
            await ctx.response.send_message(
                "Please enter a number between 0 and 99.",
                ephemeral=True
            )
            return

        channel = ctx.guild.get_channel(self.channel_id)
        if channel:
            await channel.edit(user_limit=limit)
            await ctx.response.send_message(
                f"User limit set to {limit if limit > 0 else 'unlimited'}.",
                ephemeral=True
            )


class RenameModal(discord.ui.Modal, title="Rename Channel"):
    name = discord.ui.TextInput(
        label="New Name",
        placeholder="Enter a new name",
        required=True,
        max_length=100
    )
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
    
    async def on_submit(self, ctx: discord.Interaction):
        channel = ctx.guild.get_channel(self.channel_id)
        if channel:
            await channel.edit(name=self.name.value)
            await ctx.response.send_message(
                f"Channel renamed to: **{self.name.value}**",
                ephemeral=True
            )


class InviteUserModal(discord.ui.Modal, title="Invite User"):
    user = discord.ui.TextInput(
        label="User (ID, @mention or Username)",
        placeholder="123456789, @user or username",
        required=True
    )
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
    
    async def on_submit(self, ctx: discord.Interaction):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return
        
        # Parse User
        user_input = self.user.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        
        member = None
        
        # Try as ID
        try:
            user_id = int(user_input)
            member = ctx.guild.get_member(user_id)
        except ValueError:
            # Try as Username
            member = discord.utils.get(ctx.guild.members, name=user_input)
            if not member:
                member = discord.utils.get(ctx.guild.members, display_name=user_input)
        
        if not member:
            await ctx.response.send_message("User not found.", ephemeral=True)
            return
        
        await channel.set_permissions(member, connect=True)
        await ctx.response.send_message(
            f"✅ {member.mention} has been invited.",
            ephemeral=True
        )


class KickUserModal(discord.ui.Modal, title="Kick User"):
    user = discord.ui.TextInput(
        label="User (ID, @mention or Username)",
        placeholder="123456789, @user or username",
        required=True
    )
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
    
    async def on_submit(self, ctx: discord.Interaction):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return
        
        user_input = self.user.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        
        member = None
        
        try:
            user_id = int(user_input)
            member = ctx.guild.get_member(user_id)
        except ValueError:
            member = discord.utils.get(ctx.guild.members, name=user_input)
            if not member:
                member = discord.utils.get(ctx.guild.members, display_name=user_input)

        if not member:
            await ctx.response.send_message("User not found.", ephemeral=True)
            return

        # Disconnect if in channel
        if member.voice and member.voice.channel.id == self.channel_id:
            await member.move_to(None)

        # Remove connect permission
        await channel.set_permissions(member, connect=False)
        await ctx.response.send_message(
            f"🚫 {member.mention} has been kicked.",
            ephemeral=True
        )


class TransferOwnerModal(discord.ui.Modal, title="Transfer Ownership"):
    user = discord.ui.TextInput(
        label="New Owner (ID, @mention or Username)",
        placeholder="123456789, @user or username",
        required=True
    )
    
    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id
    
    async def on_submit(self, ctx: discord.Interaction):
        channel = ctx.guild.get_channel(self.channel_id)
        if not channel:
            await ctx.response.send_message("Channel not found.", ephemeral=True)
            return
        
        user_input = self.user.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        
        member = None
        
        try:
            user_id = int(user_input)
            member = ctx.guild.get_member(user_id)
        except ValueError:
            member = discord.utils.get(ctx.guild.members, name=user_input)
            if not member:
                member = discord.utils.get(ctx.guild.members, display_name=user_input)

        if not member:
            await ctx.response.send_message("User not found.", ephemeral=True)
            return
        
        # Update Owner in DB
        await db.update_temp_voice_owner(self.channel_id, member.id)
        
        # Optional: Rename channel
        await channel.edit(name=f"{member.display_name}'s Channel")

        await ctx.response.send_message(
            f"👑 Ownership transferred to {member.mention}.",
            ephemeral=True
        )

class TempVoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded"""
        # Register persistent view
        self.bot.add_view(TempVoiceControlView())

    tempvoice_group = app_commands.Group(name="tempvoice", description="Manage temporary voice channel system")

    @tempvoice_group.command(
        name="panel",
        description="Create a control panel for temporary voice channels"
    )
    @app_commands.describe(channel="The text channel for the control panel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def tempvoice_panel(
        self,
        ctx: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message(
                "Only administrators can use this command.",
                ephemeral=True
            )
            return
        
        target_channel = channel or ctx.channel
        
        # Check if old control panel exists and delete it
        old_panel = await db.get_temp_voice_control_channel(ctx.guild.id)
        if old_panel:
            old_channel_id, old_message_id = old_panel
            try:
                old_channel = ctx.guild.get_channel(old_channel_id)
                if old_channel:
                    old_message = await old_channel.fetch_message(old_message_id)
                    await old_message.delete()
                    logger.info(f"Deleted old control panel {old_message_id} in guild {ctx.guild.id}")
            except discord.NotFound:
                logger.debug(f"Old control panel {old_message_id} not found (already deleted)")
            except Exception as e:
                logger.error(f"Error deleting old control panel: {e}")
        
        embed = discord.Embed(
            title="🎤 Temporary Voice Control Panel",
            description=(
                "Click the button below to manage your temporary voice channel.\n\n"
                "**Available Functions:**\n"
                "🔒 **Lock/Unlock** - Lock/Unlock channel\n"
                "👁️ **Hide/Show** - Hide/Show channel\n"
                "👤 **Limit** - Set user limit\n"
                "✏️ **Rename** - Rename channel\n"
                "➕ **Invite** - Invite user\n"
                "🚫 **Kick** - Kick user\n"
                "👑 **Transfer** - Transfer ownership\n"
                "🗑️ **Delete** - Delete channel"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Only channel owners can use these functions")

        view = TempVoiceControlView()
        msg = await target_channel.send(embed=embed, view=view)

        # Save to DB
        await db.set_temp_voice_control_channel(ctx.guild.id, target_channel.id, msg.id)

        await ctx.response.send_message(
            f"Control Panel has been created in {target_channel.mention}!",
            ephemeral=True
        )

    @tempvoice_group.command(name="setup", description="Set up the temporary voice channel system")
    @app_commands.describe(
        creator_channel="The voice channel that creates new temporary channels",
        category="The category in which new channels are created (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def tempvoice_setup(
        self,
        ctx: discord.Interaction,
        creator_channel: discord.VoiceChannel,
        category: discord.CategoryChannel = None
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message(
                "Only administrators can use this command.",
                ephemeral=True
            )
            return

        # Check bot permissions
        perms = ctx.guild.me.guild_permissions
        if not (perms.manage_channels and perms.move_members):
            await ctx.response.send_message(
                "I need the 'Manage Channels' and 'Move Members' permissions for this feature.",
                ephemeral=True
            )
            return

        # Save the configuration
        category_id = category.id if category else creator_channel.category.id if creator_channel.category else None
        await db.set_temp_voice_setup(ctx.guild.id, creator_channel.id, category_id)

        # Success message
        category_info = f" in the category <#{category_id}>" if category_id else ""
        await ctx.response.send_message(
            f"Temp-Voice-System initialized!\n"
            f"Creator Channel: {creator_channel.mention}\n"
            f"Temporary channels will be created{category_info}.",
            ephemeral=True
        )

    @tempvoice_group.command(name="reset", description="Remove the temporary voice channel system")
    @app_commands.describe(
        delete_existing="Should all existing Creator Channels be deleted?"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def tempvoice_reset(
        self,
        ctx: discord.Interaction,
        delete_existing: bool = False
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message(
                "Only administrators can use this command.",
                ephemeral=True
            )
            return

        # Check if a setup exists
        setup = await db.get_temp_voice_setup(ctx.guild.id)
        if not setup:
            await ctx.response.send_message(
                "No temporary voice system is set up.",
                ephemeral=True
            )
            return
        
        await ctx.response.defer(ephemeral=True)
        
        deleted_count = 0
        
        # Optional: Lösche alle bestehenden temporären Channels
        if delete_existing:
            temp_channels = await db.get_all_temp_voice_channels(ctx.guild.id)
            for channel_id, _ in temp_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete(reason="Temp-Voice-System has been reset")
                        deleted_count += 1
                    except discord.Forbidden:
                        logger.warning(f"Permission denied to delete channel {channel_id}")
                    except Exception as e:
                        logger.error(f"Error deleting channel {channel_id}: {e}")

                # Remove from DB
                await db.remove_temp_voice_channel(channel_id)

        # Remove the setup
        await db.remove_temp_voice_setup(ctx.guild.id)

        # Success message
        msg = "Temp-Voice-System has been reset."
        if delete_existing and deleted_count > 0:
            msg += f"\n{deleted_count} temporary channel(s) have been deleted."

        await ctx.followup.send(msg, ephemeral=True)


    @tempvoice_group.command(name="remove", description="Delete a Creator-Channel from the temporary voice system")
    @app_commands.describe(creator_channel="The Creator-Channel to remove")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def tempvoice_remove(
        self,
        ctx: discord.Interaction,
        creator_channel: discord.VoiceChannel
    ):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message("Only admins can use this command.", ephemeral=True)
            return
        
        is_creator = await db.is_temp_voice_creator(creator_channel.id)
        if not is_creator:
            await ctx.response.send_message(
                f"{creator_channel.mention} is not a Creator-Channel.",
                ephemeral=True
            )
            return
        
        await db.remove_temp_voice_creator(creator_channel.id)
        await ctx.response.send_message(
            f"Creator-Channel {creator_channel.mention} has been removed.",
            ephemeral=True
        )

    @tempvoice_group.command(name="info", description="Show the current temporary voice configuration")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def tempvoice_info(self, ctx: discord.Interaction):
        if not ctx.user.guild_permissions.administrator:
            await ctx.response.send_message(
                "Only administrators can use this command.",
                ephemeral=True
            )
            return

        # Get setup - ist jetzt eine LISTE
        setups = await db.get_temp_voice_setup(ctx.guild.id)
        if not setups:
            await ctx.response.send_message(
                "No temporary voice system is set up.\n"
                "Use `/tempvoice_setup` to set it up.",
                ephemeral=True
            )
            return
        
        # Hole aktive temporäre Channels
        temp_channels = await db.get_all_temp_voice_channels(ctx.guild.id)
        
        # Create Embed
        embed = discord.Embed(
            title="🎤 Temporary Voice System Configuration",
            color=discord.Color.blue()
        )

        # Liste alle Creator-Channels auf
        creator_mentions = []
        for creator_channel_id, category_id in setups:
            creator_channel = ctx.guild.get_channel(creator_channel_id)
            if creator_channel:
                creator_mentions.append(creator_channel.mention)
                
        if creator_mentions:
            embed.add_field(
                name="Creator-Channel(s)",
                value="\n".join(creator_mentions),
                inline=False
            )
        
        # Optional: Zeige Kategorien (wenn verwendet)
        categories = set()
        for _, category_id in setups:
            if category_id:
                category = ctx.guild.get_channel(category_id)
                if category:
                    categories.add(category.mention)
        
        if categories:
            embed.add_field(
                name="Categories",
                value="\n".join(categories),
                inline=False
            )
        
        embed.add_field(
            name="Active Temporary Channels",
            value=str(len(temp_channels)),
            inline=False
        )

        await ctx.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TempVoiceCog(bot))
