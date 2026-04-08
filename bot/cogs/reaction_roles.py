import logging
from typing import Optional, List, Dict, Any

import discord
import emoji as emoji_lib
from discord import app_commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)


def normalize_emoji(raw_emoji: str) -> str:
    value = raw_emoji.strip()
    alias_converted = emoji_lib.emojize(value, language="alias")
    if alias_converted != value:
        value = alias_converted

    partial = discord.PartialEmoji.from_str(value)
    if partial.id is not None:
        return str(partial)

    return value if value else ""


def format_emoji_for_option(emoji_value: str):
    if not emoji_value:
        return None
    partial = discord.PartialEmoji.from_str(emoji_value)
    if partial.id is not None:
        return partial
    return emoji_value


# ==========================================
# DYNAMIC INTERACTIVE V2 ENGINE
# ==========================================

async def update_member_roles(interaction: discord.Interaction, panel: dict, role_id: int):
    guild = interaction.guild
    member = interaction.user
    if not guild or not member:
        return None, "Error: Unknown environment."

    req_role_id = panel.get('required_role_id')
    if req_role_id:
        if not member.get_role(req_role_id):
            req_role = guild.get_role(req_role_id)
            return None, f"You must have the {req_role.mention if req_role else 'required'} role to use this."

    role = guild.get_role(role_id)
    if not role:
        return None, "That role no longer exists."

    has_role = member.get_role(role_id) is not None
    role_removal = panel.get('role_removal', True)
    multiple_slots = panel.get('multiple_slots', True)

    if has_role:
        if not role_removal:
            return None, "Role removal is disabled for this panel."
        try:
            await member.remove_roles(role, reason="Reaction Role Dashboard")
            return "removed", role
        except discord.Forbidden:
            return None, "I lack permissions to remove this role."
    else:
        # If single slot only, remove other roles from this panel
        if not multiple_slots:
            entries = await db.get_reaction_role_entries(panel['message_id'])
            panel_roles = [e['role_id'] for e in entries if e['role_id'] != role_id]
            roles_to_remove = [guild.get_role(r) for r in panel_roles if member.get_role(r) and guild.get_role(r)]
            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="Reaction Role Single Slot")
                except discord.Forbidden:
                    pass

        try:
            await member.add_roles(role, reason="Reaction Role Dashboard")
            return "added", role
        except discord.Forbidden:
            return None, "I lack permissions to assign this role."


class DynamicRoleButton(discord.ui.Button):
    def __init__(self, panel: dict, entry: dict, guild: discord.Guild):
        self.panel = panel
        self.entry = entry
        
        label = entry.get('label') or ""
        if panel.get('show_counters', False) and guild:
            role = guild.get_role(entry['role_id'])
            count = len(role.members) if role else 0
            label = f"{label} | {count}" if label else str(count)

        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label if label else "\u200b",
            emoji=format_emoji_for_option(entry['emoji']),
            custom_id=f"rrbtn_{panel['message_id']}_{entry['role_id']}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        action, ctx_response = await update_member_roles(interaction, self.panel, self.entry['role_id'])
        
        if not action:
            await interaction.followup.send(ctx_response, ephemeral=True)
            return

        msg = f"✅ You have been given {ctx_response.mention}." if action == "added" else f"❌ You removed {ctx_response.mention}."
        await interaction.followup.send(msg, ephemeral=True)
        
        # Increment/Decrement counter smoothly if enabled
        if self.panel.get('show_counters', False):
            # Tell the view to re-render the message
            if hasattr(self.view, "refresh_counters"):
                await self.view.refresh_counters(interaction)


class DynamicRoleSelect(discord.ui.Select):
    def __init__(self, panel: dict, entries: list, guild: discord.Guild):
        self.panel = panel
        self.entries = entries
        
        options = []
        for e in entries:
            label = e.get('label') or "Role"
            if panel.get('show_counters', False) and guild:
                role = guild.get_role(e['role_id'])
                count = len(role.members) if role else 0
                label = f"{label} ({count})"
                
            options.append(discord.SelectOption(
                label=label,
                description=e.get('description'),
                emoji=format_emoji_for_option(e['emoji']),
                value=str(e['role_id'])
            ))
            
        super().__init__(
            placeholder="Select a role...",
            options=options,
            min_values=1, # Single select mode, handle logic dynamically
            max_values=1 if not panel.get('multiple_slots', True) else min(len(options), 25),
            custom_id=f"rrsel_{panel['message_id']}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        member = interaction.user
        added_roles = []
        removed_roles = []
        errors = []

        req_role_id = self.panel.get('required_role_id')
        if req_role_id and not member.get_role(req_role_id):
            await interaction.followup.send("You lack the required role to use this menu.", ephemeral=True)
            return

        # Figure out which roles they selected
        selected_ids = [int(v) for v in self.values]
        all_entry_ids = [e['role_id'] for e in self.entries]
        
        for r_id in all_entry_ids:
            role = guild.get_role(r_id)
            if not role:
                continue
                
            has_role = member.get_role(r_id) is not None
            should_have_role = r_id in selected_ids
            
            if should_have_role and not has_role:
                try:
                    await member.add_roles(role, reason="Reaction Role Menu")
                    added_roles.append(role.mention)
                except discord.Forbidden:
                    errors.append(f"Cannot grant {role.mention}")
            elif not should_have_role and has_role:
                if self.panel.get('role_removal', True):
                    try:
                        await member.remove_roles(role, reason="Reaction Role Menu")
                        removed_roles.append(role.mention)
                    except discord.Forbidden:
                        errors.append(f"Cannot remove {role.mention}")

        msgs = []
        if added_roles: msgs.append(f"✅ Added: {', '.join(added_roles)}")
        if removed_roles: msgs.append(f"❌ Removed: {', '.join(removed_roles)}")
        if errors: msgs.append("⚠️ Errors: " + ", ".join(errors))
        
        if not msgs:
            msgs.append("No roles were changed.")
            
        await interaction.followup.send("\n".join(msgs), ephemeral=True)
        
        if self.panel.get('show_counters', False) and hasattr(self.view, "refresh_counters"):
            await self.view.refresh_counters(interaction)


class DynamicRoleView(discord.ui.View):
    def __init__(self, panel: dict, entries: list, guild: discord.Guild):
        super().__init__(timeout=None)
        self.panel = panel
        self.entries = entries
        self.guild = guild
        
        comp_type = panel.get("component_type", "Buttons")
        if comp_type == "Select" and len(entries) > 0:
            self.add_item(DynamicRoleSelect(panel, entries, guild))
        else:
            for entry in entries:
                self.add_item(DynamicRoleButton(panel, entry, guild))

    async def refresh_counters(self, interaction: discord.Interaction):
        new_view = DynamicRoleView(self.panel, self.entries, self.guild)
        try:
            await interaction.message.edit(view=new_view)
        except Exception:
            pass


# ==========================================
# SETUP DASHBOARDS (EDITORS)
# ==========================================

class TextEditorModal(discord.ui.Modal, title="Edit Panel Output"):
    p_title = discord.ui.TextInput(label="Title", max_length=256)
    p_desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False, max_length=2000)
    p_img = discord.ui.TextInput(label="Image URL (Optional)", required=False, placeholder="https://...")

    def __init__(self, editor_view: "DashboardEditorView"):
        super().__init__()
        self.editor_view = editor_view
        self.p_title.default = self.editor_view.panel.get('title') or ""
        self.p_desc.default = self.editor_view.panel.get('description') or ""
        self.p_img.default = self.editor_view.panel.get('image_url') or ""

    async def on_submit(self, interaction: discord.Interaction):
        await db.update_reaction_role_message(
            self.editor_view.message_id,
            title=str(self.p_title),
            description=str(self.p_desc) if str(self.p_desc) else None,
            image_url=str(self.p_img) if str(self.p_img) else None
        )
        await self.editor_view.refresh(interaction)


class SlotEditorModal(discord.ui.Modal, title="Edit/Add Role Slot"):
    p_emoji = discord.ui.TextInput(label="Emoji", placeholder="😀 or <:custom:123456>", max_length=100)
    p_label = discord.ui.TextInput(label="Label", placeholder="Optional Label", required=False, max_length=80)
    p_desc = discord.ui.TextInput(label="Description", placeholder="Only for Select Menus", required=False, max_length=100)

    def __init__(self, editor_view: "DashboardEditorView", target_role: discord.Role):
        super().__init__()
        self.editor_view = editor_view
        self.target_role = target_role

    async def on_submit(self, interaction: discord.Interaction):
        emoji_str = normalize_emoji(str(self.p_emoji))
        if not emoji_str:
            await interaction.response.send_message("Invalid emoji.", ephemeral=True)
            return

        await db.add_reaction_role_entry(
            self.editor_view.message_id,
            emoji_str,
            self.target_role.id,
            str(self.p_label) if str(self.p_label) else None,
            str(self.p_desc) if str(self.p_desc) else None
        )
        await self.editor_view.refresh(interaction)


class AddSlotRoleSelectView(discord.ui.View):
    def __init__(self, editor_view: "DashboardEditorView"):
        super().__init__(timeout=300)
        self.editor_view = editor_view

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Choose a role to attach to a slot", max_values=1)
    async def callback(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        # Verify role position
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("That role is too high for me to assign.", ephemeral=True)
            return
            
        await interaction.response.send_modal(SlotEditorModal(self.editor_view, role))


class DashboardEditorView(discord.ui.View):
    def __init__(self, cog: "ReactionRolesCog", interaction: discord.Interaction, message_id: int):
        super().__init__(timeout=600)
        self.cog = cog
        self.orig_interaction = interaction
        self.message_id = message_id
        self.panel = None
        self.entries = []

    async def fetch_state(self):
        self.panel = await db.get_reaction_role_message(self.message_id)
        if self.panel:
            self.entries = await db.get_reaction_role_entries(self.message_id)

    def _build_embed(self) -> discord.Embed:
        emb = discord.Embed(
            title="☑️ Role Message Dashboard",
            description=f"Editing Role Message from channel <#{self.panel['channel_id']}>",
            color=0x5865F2
        )
        
        emb.add_field(name="Title", value=f"```\n{self.panel['title']}\n```", inline=True)
        desc_val = self.panel.get('description')
        emb.add_field(name="Description", value=f"```\n{desc_val[:50] + '...' if desc_val and len(desc_val) > 50 else (desc_val or '<Not Set>')}\n```", inline=True)
        emb.add_field(name="Includes Image", value="🟢 On" if self.panel.get('image_url') else "⚫ Off", inline=True)
        
        # Slots
        slot_text = []
        for e in self.entries:
            role_m = f"<@&{e['role_id']}>"
            lab = f" | {e['label']}" if e.get('label') else ""
            slot_text.append(f"{e['emoji']}{lab} -> {role_m}")
        emb.add_field(name="Slots Configured", value="\n".join(slot_text) if slot_text else "<Not Set>")
        
        req_role = self.panel.get('required_role_id')
        req_txt = f"<@&{req_role}>" if req_role else "<Not Set>"
        emb.add_field(name="Role Requirements", value=req_txt)
        
        p = self.panel
        props = (
            f"• Role removal on toggle: **{'On' if p.get('role_removal', True) else 'Off'}**\n"
            f"• Multiple slots simultaneously: **{'On' if p.get('multiple_slots', True) else 'Off'}**\n"
            f"• Include slot overview: **{'On' if p.get('include_overview', False) else 'Off'}**\n"
            f"• Component Type: **{p.get('component_type', 'Buttons')}**\n"
            f"• Show role counters: **{'On' if p.get('show_counters', False) else 'Off'}**"
        )
        emb.add_field(name="Properties", value=props, inline=False)
        return emb

    async def apply_update(self, **kwargs):
        await db.update_reaction_role_message(self.message_id, **kwargs)

    async def refresh(self, interaction: discord.Interaction):
        await self.fetch_state()
        try:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        except discord.InteractionResponded:
            await interaction.message.edit(embed=self._build_embed(), view=self)

    # 1. Row 1
    @discord.ui.button(label="Adjust Text/Image", style=discord.ButtonStyle.primary, row=0)
    async def btn_adjust_text(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.send_modal(TextEditorModal(self))

    @discord.ui.button(label="Add Slot", style=discord.ButtonStyle.primary, row=0)
    async def btn_add_slot(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.send_message("Select a role to add...", view=AddSlotRoleSelectView(self), ephemeral=True)

    @discord.ui.button(label="Remove Slot", style=discord.ButtonStyle.danger, row=0)
    async def btn_remove_slot(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not self.entries:
            await interaction.response.send_message("No slots to remove.", ephemeral=True)
            return
            
        class RemoveSelectView(discord.ui.View):
            def __init__(self, editor: DashboardEditorView):
                super().__init__(timeout=300)
                options = [discord.SelectOption(label=f"Role {e['role_id']}", value=e['emoji'], emoji=format_emoji_for_option(e['emoji'])) for e in editor.entries]
                self.sel = discord.ui.Select(placeholder="Select slot emoji to drop...", options=options)
                self.sel.callback = self.callback
                self.add_item(self.sel)
                self.editor = editor
                
            async def callback(self, inter: discord.Interaction):
                await db.remove_reaction_role_entry(self.editor.message_id, self.sel.values[0])
                await self.editor.refresh(inter)
                
        await interaction.response.send_message("Select the mapping to drop.", view=RemoveSelectView(self), ephemeral=True)

    # 2. Row 2 (Toggles)
    @discord.ui.button(label="Toggle Role Removal", style=discord.ButtonStyle.secondary, row=1)
    async def btn_role_rem(self, interaction: discord.Interaction, btn: discord.ui.Button):
        current = self.panel.get('role_removal', True)
        await self.apply_update(role_removal=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Toggle Multi-Slot", style=discord.ButtonStyle.secondary, row=1)
    async def btn_multi(self, interaction: discord.Interaction, btn: discord.ui.Button):
        current = self.panel.get('multiple_slots', True)
        await self.apply_update(multiple_slots=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Switch Component Type", style=discord.ButtonStyle.secondary, row=1)
    async def btn_comp(self, interaction: discord.Interaction, btn: discord.ui.Button):
        current = self.panel.get('component_type', 'Buttons')
        new_val = 'Select' if current == 'Buttons' else 'Buttons'
        await self.apply_update(component_type=new_val)
        await self.refresh(interaction)

    @discord.ui.button(label="Toggle Role Counters", style=discord.ButtonStyle.secondary, row=1)
    async def btn_counters(self, interaction: discord.Interaction, btn: discord.ui.Button):
        current = self.panel.get('show_counters', False)
        await self.apply_update(show_counters=not current)
        await self.refresh(interaction)

    # 3. Row 3 
    @discord.ui.button(label="Toggle Slot Overview", style=discord.ButtonStyle.secondary, row=2)
    async def btn_overview(self, interaction: discord.Interaction, btn: discord.ui.Button):
        current = self.panel.get('include_overview', False)
        await self.apply_update(include_overview=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Require Role...", style=discord.ButtonStyle.secondary, row=2)
    async def btn_req_role(self, interaction: discord.Interaction, btn: discord.ui.Button):
        class ReqRoleSelectView(discord.ui.View):
            def __init__(self, editor: DashboardEditorView):
                super().__init__(timeout=300)
                self.editor = editor
            @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select required Role (or none to drop)")
            async def call(self, inter: discord.Interaction, sel: discord.ui.RoleSelect):
                await db.update_reaction_role_message(self.editor.message_id, required_role_id=sel.values[0].id)
                await self.editor.refresh(inter)
            @discord.ui.button(label="Clear Requirement", style=discord.ButtonStyle.danger)
            async def call2(self, inter: discord.Interaction, b: discord.ui.Button):
                await db.update_reaction_role_message(self.editor.message_id, required_role_id=None)
                await self.editor.refresh(inter)
        await interaction.response.send_message("Set requirement:", view=ReqRoleSelectView(self), ephemeral=True)

    @discord.ui.button(label="Submit/Publish >>", style=discord.ButtonStyle.success, row=2)
    async def btn_publish(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await self.cog.publish_panel(self.message_id, interaction)
        self.stop()

    @discord.ui.button(label="Delete/Discard Panel", style=discord.ButtonStyle.danger, row=3, custom_id="btn_delete_panel")
    async def btn_delete(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await db.delete_reaction_role_message(self.message_id)
        
        # Physical teardown if message genuinely exists outside of drafting
        if self.message_id > 0:
            try:
                guild = interaction.guild
                ch = guild.get_channel(self.panel['channel_id']) if guild else None
                if ch:
                    msg = await ch.fetch_message(self.message_id)
                    await msg.delete()
            except Exception:
                pass
                
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(embed=discord.Embed(title="🗑️ Panel Deleted", description="This panel and its database configurations have been entirely removed.", color=0xFF0000), view=self)
        except Exception:
            pass
        self.stop()


class MainDashboardHome(discord.ui.View):
    def __init__(self, cog: "ReactionRolesCog"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Create Role Message", style=discord.ButtonStyle.primary)
    async def btn_create(self, interaction: discord.Interaction, btn: discord.ui.Button):
        # We need a channel target.
        class ChSelectView(discord.ui.View):
            def __init__(self, cog: "ReactionRolesCog"):
                super().__init__()
                self.cog = cog
            @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text])
            async def cb(self, inter: discord.Interaction, sel: discord.ui.ChannelSelect):
                import time
                draft_id = -int(time.time() * 1000)
                
                raw_ch = sel.values[0]
                ch = inter.guild.get_channel(raw_ch.id)
                if not ch:
                    await inter.response.send_message("Could not resolve that channel.", ephemeral=True)
                    return
                    
                await db.create_reaction_role_message(inter.guild_id, ch.id, draft_id, "Reaction Roles", "Use the buttons below to assign yourself roles.", inter.user.id)
                
                editor = DashboardEditorView(self.cog, inter, draft_id)
                await editor.fetch_state()
                await inter.response.edit_message(content=None, embed=editor._build_embed(), view=editor)
                
        await interaction.response.send_message("Where should the panel be posted?", view=ChSelectView(self.cog), ephemeral=True)

    @discord.ui.button(label="Edit Role Messages", style=discord.ButtonStyle.secondary)
    async def btn_edit(self, interaction: discord.Interaction, btn: discord.ui.Button):
        panels = await db.get_reaction_role_messages(interaction.guild_id)
        if not panels:
            await interaction.response.send_message("No panels configured. Create one first.", ephemeral=True)
            return
            
        class EditSelView(discord.ui.View):
            def __init__(self, cog, panels):
                super().__init__()
                opts = [discord.SelectOption(label=f"{p['title']} in <#{p['channel_id']}>", value=str(p['message_id'])) for p in panels[:25]]
                self.sel = discord.ui.Select(options=opts)
                self.sel.callback = self.cb
                self.add_item(self.sel)
                self.cog = cog
            async def cb(self, inter: discord.Interaction):
                editor = DashboardEditorView(self.cog, inter, int(self.sel.values[0]))
                await editor.fetch_state()
                await inter.response.edit_message(content=None, embed=editor._build_embed(), view=editor)
                
        await interaction.response.send_message("Select a panel to edit:", view=EditSelView(self.cog, panels), ephemeral=True)


# ==========================================
# COG IMPLEMENTATION
# ==========================================

class ReactionRolesCog(commands.Cog):
    reactionroles_group = app_commands.Group(name="reactionroles", description="Lawliet-style reaction roles manager")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_message(self, panel):
        guild = self.bot.get_guild(panel['guild_id'])
        if guild is None:
            return None, None
        channel = guild.get_channel(panel['channel_id'])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(panel['channel_id'])
            except Exception:
                return guild, None
        try:
            msg = await channel.fetch_message(panel['message_id'])
            return guild, msg
        except Exception:
            return guild, None

    async def publish_panel(self, message_id: int, interaction: discord.Interaction):
        panel = await db.get_reaction_role_message(message_id)
        if not panel: return
        guild = interaction.guild
        if not guild: return
        channel = guild.get_channel(panel['channel_id'])
        if not channel: return

        entries = await db.get_reaction_role_entries(message_id)
        
        desc = panel.get('description') or ""
        if panel.get('include_overview', False) and entries:
            desc += "\n\n**Roles:**\n"
            for e in entries:
                desc += f"{e['emoji']} -> <@&{e['role_id']}>\n"
                
        embed = discord.Embed(
            title=panel['title'],
            description=desc,
            color=await get_guild_color(panel['guild_id'])
        )
        if panel.get('image_url'):
            try:
                embed.set_image(url=panel['image_url'])
            except Exception:
                pass
                
        if message_id < 0:
            # It's a draft! Send invisible placeholder first to claim a real Message ID
            real_msg = await channel.send("Publishing panel...")
            
            # Update DB mapping
            async with db._pool.acquire() as conn:
                await conn.execute("UPDATE reaction_role_messages SET message_id=$1 WHERE message_id=$2", real_msg.id, message_id)
                await conn.execute("UPDATE reaction_role_entries SET message_id=$1 WHERE message_id=$2", real_msg.id, message_id)
                
            # Render fully mapped custom_ids safely
            panel_dict = dict(panel)
            panel_dict['message_id'] = real_msg.id
            view = DynamicRoleView(panel_dict, entries, guild)
            
            await real_msg.edit(content=None, embed=embed, view=view)
            await interaction.response.send_message(f"✅ Panel published to {channel.mention}!", ephemeral=True)
        else:
            # It's an update to an existing published panel
            try:
                msg = await channel.fetch_message(message_id)
                view = DynamicRoleView(panel, entries, guild)
                await msg.edit(content=None, embed=embed, view=view)
                await interaction.response.send_message("✅ Panel layout updated!", ephemeral=True)
            except Exception:
                await interaction.response.send_message("The original panel message could not be found! It might have been deleted.", ephemeral=True)

    @reactionroles_group.command(name="dashboard", description="Open the main Reaction Roles setup dashboard")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def rp_dashboard(self, interaction: discord.Interaction):
        emb = discord.Embed(
            title="☑️ Reaction Roles",
            description="Create role messages that members can use to obtain or revoke roles. Interactive and fast component system based on modern Discord UI features.",
            color=0x5865F2
        )
        await interaction.response.send_message(embed=emb, view=MainDashboardHome(self), ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        # Hot Restorer for reboot persistence
        # We query all panels, reconstruct the view and attach it explicitly.
        # This allows custom_ids dynamically attached to the view to map gracefully.
        logger.info("Initializing persistent reaction role dashboard buttons...")
        # Since 'get_reaction_role_messages' requires guild_id, we just query ALL.
        async with db._pool.acquire() as conn:
            panels = await conn.fetch("SELECT * FROM reaction_role_messages")
        for p in panels:
            entries = await db.get_reaction_role_entries(p['message_id'])
            guild = self.bot.get_guild(p['guild_id'])
            if guild and entries:
                self.bot.add_view(DynamicRoleView(dict(p), [dict(e) for e in entries], guild), message_id=p['message_id'])


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRolesCog(bot))
