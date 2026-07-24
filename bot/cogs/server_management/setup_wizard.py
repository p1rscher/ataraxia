import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

class SetupWizardView(discord.ui.View):
    def __init__(self, ctx: commands.Context, color: discord.Color):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.color = color
        self.message: Optional[discord.Message] = None
        
        self.state = {
            'log_channel': None,
            'welcome_channel': None,
            'autorole': None,
            'xp_enabled': False,
            'ticket_channel': None
        }
        
        self.steps = [
            self.step_intro,
            self.step_logging,
            self.step_welcome,
            self.step_autorole,
            self.step_xp,
            self.step_tickets,
            self.step_finish
        ]
        self.current_step_idx = 0

    def _resolve_text_channel(self, selected_channel) -> Optional[discord.TextChannel]:
        channel_id = getattr(selected_channel, 'id', None)
        if channel_id is None:
            return None

        channel = self.ctx.guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    def _resolve_role(self, selected_role) -> Optional[discord.Role]:
        role_id = getattr(selected_role, 'id', None)
        if role_id is None:
            return None
        return self.ctx.guild.get_role(role_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This setup wizard is not for you.", ephemeral=True)
            return False
        return True

    async def update_view(self, interaction: discord.Interaction):
        await getattr(self, self.steps[self.current_step_idx].__name__)(interaction)

    async def step_intro(self, interaction: discord.Interaction = None):
        self.clear_items()
        
        embed = discord.Embed(
            title="🌸 Ataraxia Quick Setup Wizard",
            description=(
                "Welcome to the Ataraxia setup! This interactive wizard will help you configure the core features of the bot in under a minute.\n\n"
                "We will go through the following modules:\n"
                "1. **Server Logging** 📝\n"
                "2. **Welcome Messages** 👋\n"
                "3. **Auto-Role** 🛡️\n"
                "4. **Leveling & XP** 📈\n"
                "5. **Support Tickets** 🎫\n\n"
                "You can skip any module if you don't need it. Ready?"
            ),
            color=self.color
        )
        
        btn = discord.ui.Button(label="Start Setup", style=discord.ButtonStyle.success)
        async def callback(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn.callback = callback
        self.add_item(btn)
        
        btn_cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        async def cancel_cb(i: discord.Interaction):
            await i.response.edit_message(content="Setup cancelled.", embed=None, view=None)
            self.stop()
        btn_cancel.callback = cancel_cb
        self.add_item(btn_cancel)
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            if self.ctx.interaction:
                await self.ctx.interaction.response.send_message(embed=embed, view=self, ephemeral=True)
                self.message = await self.ctx.interaction.original_response()
            else:
                self.message = await self.ctx.send(embed=embed, view=self)

    async def on_timeout(self):
        self.clear_items()
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                logger.debug("Failed to clear quicksetup view after timeout", exc_info=True)

    async def step_logging(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="Step 1: Server Logging 📝",
            description=(
                "Select a channel where Ataraxia should send moderation, server, and system logs.\n\n"
                "If you select a channel, it will be used for all log types. You can refine this later with `/log set`."
            ),
            color=self.color
        )
        
        select = discord.ui.ChannelSelect(
            placeholder="Select a log channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        
        async def select_cb(i: discord.Interaction):
            self.state['log_channel'] = select.values[0]
            self.current_step_idx += 1
            await self.update_view(i)
            
        select.callback = select_cb
        self.add_item(select)
        
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def skip_cb(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn_skip.callback = skip_cb
        self.add_item(btn_skip)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_welcome(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="Step 2: Welcome System 👋",
            description=(
                "Select a channel where Ataraxia will greet new members with beautiful welcome cards.\n\n"
                "You can configure the card design later with `/welcome setup`."
            ),
            color=self.color
        )
        
        select = discord.ui.ChannelSelect(
            placeholder="Select a welcome channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        
        async def select_cb(i: discord.Interaction):
            self.state['welcome_channel'] = select.values[0]
            self.current_step_idx += 1
            await self.update_view(i)
            
        select.callback = select_cb
        self.add_item(select)
        
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def skip_cb(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn_skip.callback = skip_cb
        self.add_item(btn_skip)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_autorole(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="Step 3: Auto-Role 🛡️",
            description="Select a default role that Ataraxia should automatically give to users when they join your server.",
            color=self.color
        )
        
        select = discord.ui.RoleSelect(
            placeholder="Select an auto-role...",
            min_values=1,
            max_values=1
        )
        
        async def select_cb(i: discord.Interaction):
            self.state['autorole'] = select.values[0]
            self.current_step_idx += 1
            await self.update_view(i)
            
        select.callback = select_cb
        self.add_item(select)
        
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def skip_cb(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn_skip.callback = skip_cb
        self.add_item(btn_skip)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_xp(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="Step 4: Leveling & XP 📈",
            description=(
                "Do you want to enable the global leveling and XP system for your server? "
                "Members will earn XP for chatting and participating in voice channels."
            ),
            color=self.color
        )
        
        btn_enable = discord.ui.Button(label="Enable Leveling", style=discord.ButtonStyle.success)
        async def enable_cb(i: discord.Interaction):
            self.state['xp_enabled'] = True
            self.current_step_idx += 1
            await self.update_view(i)
        btn_enable.callback = enable_cb
        self.add_item(btn_enable)
        
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def skip_cb(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn_skip.callback = skip_cb
        self.add_item(btn_skip)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_tickets(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="Step 5: Support Tickets 🎫",
            description=(
                "Select a channel where Ataraxia will deploy the 'Create Ticket' panel.\n\n"
                "Ataraxia will automatically create a 'Support Tickets' category to manage open tickets."
            ),
            color=self.color
        )
        
        select = discord.ui.ChannelSelect(
            placeholder="Select a panel channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        
        async def select_cb(i: discord.Interaction):
            self.state['ticket_channel'] = select.values[0]
            self.current_step_idx += 1
            await self.update_view(i)
            
        select.callback = select_cb
        self.add_item(select)
        
        btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def skip_cb(i: discord.Interaction):
            self.current_step_idx += 1
            await self.update_view(i)
        btn_skip.callback = skip_cb
        self.add_item(btn_skip)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_finish(self, interaction: discord.Interaction):
        self.clear_items()
        
        embed = discord.Embed(
            title="🌸 Finalizing Setup...",
            description="Please wait while we apply your configurations...",
            color=self.color
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        guild_id = self.ctx.guild.id
        summary = []
        
        # 1. Logging
        if self.state['log_channel']:
            channel = self._resolve_text_channel(self.state['log_channel'])
        else:
            channel = None

        if channel:
            await db.set_log_channel(guild_id, channel.id)
            await db.set_say_log_channel(guild_id, channel.id)
            await db.set_voice_log_channel(guild_id, channel.id)
            await db.set_mod_log_channel(guild_id, channel.id)
            await db.set_traffic_log_channel(guild_id, channel.id)
            await db.set_ticket_log_channel(guild_id, channel.id)
            summary.append(f"✅ **Logging:** Unified logs routed to {channel.mention}")
        else:
            summary.append("⏭️ **Logging:** Skipped")

        # 2. Welcome
        if self.state['welcome_channel']:
            channel = self._resolve_text_channel(self.state['welcome_channel'])
        else:
            channel = None

        if channel:
            await db.get_or_create_welcome_message(guild_id)
            await db.update_welcome_message(guild_id, channel_id=channel.id)
            summary.append(f"✅ **Welcome:** Set to {channel.mention}")
        else:
            summary.append("⏭️ **Welcome:** Skipped")

        # 3. Autorole
        if self.state['autorole']:
            role = self._resolve_role(self.state['autorole'])
        else:
            role = None

        if role:
            await db.set_autorole_enabled(guild_id, True)
            await db.add_autorole(guild_id, role.id, 'user')
            summary.append(f"✅ **Auto-Role:** Set to {role.mention}")
        else:
            summary.append("⏭️ **Auto-Role:** Skipped")

        # 4. Leveling
        if self.state['xp_enabled']:
            # Set default ranges in db just to ensure they exist (these are created on-the-fly usually but this initializes it cleanly)
            await db.set_message_xp_range(guild_id, 15, 25)
            await db.set_xp_cooldown(guild_id, 60)
            summary.append("✅ **Leveling:** Initialized default XP system")
        else:
            summary.append("⏭️ **Leveling:** Skipped")

        # 5. Tickets
        if self.state['ticket_channel']:
            channel = self._resolve_text_channel(self.state['ticket_channel'])
        else:
            channel = None
            
        if channel:
            try:
                # Create a category
                category = await self.ctx.guild.create_category("Support Tickets", reason="Ataraxia Auto-Setup")
                
                # Save settings (category_id, support_role_id=None, closer_role_id=None, max_tickets=1)
                await db.set_ticket_settings(guild_id, category.id, None, None, 1)
                
                # Post panel
                from cogs.server_management.ticket import TicketPanelView
                panel_embed = discord.Embed(
                    title="Support Tickets",
                    description="Click the button below to open a private ticket.",
                    color=self.color
                )
                msg = await channel.send(embed=panel_embed, view=TicketPanelView())
                await db.add_ticket_panel(msg.id, guild_id, channel.id, "Support Tickets", "Click the button below to open a private ticket.")
                
                summary.append(f"✅ **Tickets:** Panel deployed in {channel.mention}")
            except Exception as e:
                logger.error(f"Failed to setup ticket system in wizard: {e}")
                summary.append(f"❌ **Tickets:** Failed to create panel ({e})")
        else:
            summary.append("⏭️ **Tickets:** Skipped")

        final_embed = discord.Embed(
            title="🎉 Setup Complete!",
            description="Your server has been successfully configured. Here's what we did:\n\n" + "\n".join(summary) + "\n\nEnjoy using Ataraxia!",
            color=self.color
        )
        await interaction.edit_original_response(embed=final_embed, view=None)


class SetupWizardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="quicksetup", description="[ADMIN] Step-by-step interactive setup wizard for your server")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def quicksetup_command(self, ctx: commands.Context):
        color = await get_guild_color(ctx.guild.id)
        view = SetupWizardView(ctx, color)
        await view.step_intro(None)

async def setup(bot):
    await bot.add_cog(SetupWizardCog(bot))
