import asyncio
import io
import logging
import os
from typing import Optional, List, Dict, Any
import urllib.error
import urllib.parse
import urllib.request

import discord
import emoji as emoji_lib
from discord import app_commands
from discord.ext import commands
from discord.ext import commands

from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

REMOVE_PANEL_ROLES_VALUE = "__rr_remove_panel_roles__"



async def _safe_send(inter, *args, **kwargs):
    if hasattr(inter, "response"):
        if not inter.response.is_done():
            return await inter.response.send_message(*args, **kwargs)
        else:
            return await inter.followup.send(*args, **kwargs)
    return await inter.send(*args, **kwargs)


def sanitize_unicode_emoji(emoji_str: str) -> str:
    """Passes emojis cleanly to discord API without stripping variation selectors."""
    return emoji_str


def normalize_emoji(raw_emoji: str) -> str:
    value = raw_emoji.strip()
    
    # Discord-specific alias overrides
    discord_aliases = {
        ":tools:": "🛠️",
        ":gear:": "⚙️",
    }
    if value.lower() in discord_aliases:
        value = discord_aliases[value.lower()]
    
    # Support both :alias: and standard English shortcodes
    try:
        # First try standard English (e.g. :hammer_and_wrench:)
        converted = emoji_lib.emojize(value)
        if converted == value:
            # Then try aliases (e.g. :megaphone:)
            converted = emoji_lib.emojize(value, language="alias")
        
        if converted != value:
            value = converted
    except Exception:
        pass

    return sanitize_unicode_emoji(value)


def normalize_image_url(raw_url: str) -> Optional[str]:
    """Normalize and lightly validate image URLs used in embeds."""
    if not raw_url:
        return None

    url = raw_url.strip()
    if not url:
        return None

    if not (url.startswith("http://") or url.startswith("https://")):
        return None

    # Discord-hosted images render more reliably in embeds when we request a
    # moderate preview size instead of the maximum asset size.
    if "cdn.discordapp.com" in url or "media.discordapp.net" in url:
        sep = "&" if "?" in url else "?"
        if "size=" not in url:
            url = f"{url}{sep}size=1024"

    return url


def _probe_image_url(url: str) -> tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AtaraxiaBot/1.0; +https://ataraxia-bot.com)"
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            final_url = normalize_image_url(response.geturl()) or response.geturl()
            content_type = response.headers.get_content_type()
            content_length_raw = response.headers.get("Content-Length")
            content_length = int(content_length_raw) if content_length_raw and content_length_raw.isdigit() else None
            return final_url, content_type, content_length, None
    except urllib.error.HTTPError as exc:
        return None, None, None, f"The image host returned HTTP {exc.code}."
    except urllib.error.URLError:
        return None, None, None, "The image URL could not be reached."
    except ValueError:
        return None, None, None, "The image response was invalid."


async def validate_image_url(raw_url: str) -> tuple[Optional[str], Optional[str]]:
    normalized = normalize_image_url(raw_url)
    if not normalized:
        return None, "Invalid image URL. Please use a direct http/https image link."

    final_url, content_type, content_length, error = await asyncio.to_thread(_probe_image_url, normalized)
    if error:
        return None, error

    if not content_type or not content_type.startswith("image/"):
        return None, (
            "That link does not resolve to a direct image file. Use the raw image URL, "
            "not a Google result page or image-host landing page."
        )

    if content_length and content_length > 15 * 1024 * 1024:
        return None, "That image is too large for reliable embed loading. Please use a smaller image."

    return final_url, None


def is_discord_hosted_image(url: Optional[str]) -> bool:
    if not url:
        return False
    return "cdn.discordapp.com" in url or "media.discordapp.net" in url


def _download_image_bytes(url: str) -> tuple[Optional[bytes], Optional[str], Optional[str], Optional[str]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AtaraxiaBot/1.0; +https://ataraxia-bot.com)"
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content_type = response.headers.get_content_type() or "application/octet-stream"
            data = response.read()
            final_url = response.geturl()
            return data, content_type, final_url, None
    except urllib.error.HTTPError as exc:
        return None, None, None, f"The image host returned HTTP {exc.code}."
    except urllib.error.URLError:
        return None, None, None, "The image URL could not be reached."
    except ValueError:
        return None, None, None, "The image response was invalid."


async def download_image_for_discord(url: str) -> tuple[Optional[discord.File], Optional[str]]:
    data, content_type, final_url, error = await asyncio.to_thread(_download_image_bytes, url)
    if error:
        return None, error

    if not data:
        return None, "The image downloaded as empty data."

    if not content_type or not content_type.startswith("image/"):
        return None, "That link does not resolve to a direct image file."

    if len(data) > 15 * 1024 * 1024:
        return None, "That image is too large for reliable Discord uploads."

    parsed = urllib.parse.urlparse(final_url or url)
    base_name = os.path.basename(parsed.path) or "reaction-role-image"
    stem, ext = os.path.splitext(base_name)

    if not ext:
        guessed_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }.get(content_type, ".img")
        ext = guessed_ext

    safe_stem = stem[:40] or "reaction-role-image"
    filename = f"{safe_stem}{ext}"
    return discord.File(io.BytesIO(data), filename=filename), None


def format_emoji_for_option(emoji_value: str):
    """Safe formatting for public buttons (only). In menus, we use labels."""
    if not emoji_value:
        return None
    
    # Custom Discord Emoji strings should be converted to PartialEmoji
    if emoji_value.startswith('<') and emoji_value.endswith('>'):
        try:
            return discord.PartialEmoji.from_str(emoji_value)
        except Exception:
            return emoji_value
            
    # Standard Unicode emojis: Return the string character.
    # We attempt to emojize here as well to fix any existing colon-codes in the database.
    try:
        # Discord-specific alias overrides
        discord_aliases = {
            ":tools:": "🛠️",
            ":gear:": "⚙️",
        }
        test_val = emoji_value.lower()
        if test_val in discord_aliases:
            return sanitize_unicode_emoji(discord_aliases[test_val])

        if emoji_value.startswith(':') and emoji_value.endswith(':'):
            converted = emoji_lib.emojize(emoji_value, language="alias")
            if converted == emoji_value:
                converted = emoji_lib.emojize(emoji_value)
            return sanitize_unicode_emoji(converted)
    except Exception:
        pass

    return sanitize_unicode_emoji(emoji_value)


# ==========================================
# DYNAMIC INTERACTIVE V2 ENGINE
# ==========================================

async def update_member_roles(interaction: commands.Context, panel: dict, role_id: int):
    guild = interaction.guild
    member = getattr(interaction, "user", getattr(interaction, "author", None))
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

    async def callback(self, interaction: commands.Context):
        await getattr(interaction, "response", interaction).defer(ephemeral=True)
        action, ctx_response = await update_member_roles(interaction, self.panel, self.entry['role_id'])
        
        if not action:
            await _safe_send(interaction, ctx_response, ephemeral=True)
            return

        msg = f"✅ You have been given {ctx_response.mention}." if action == "added" else f"❌ You removed {ctx_response.mention}."
        await _safe_send(interaction, msg, ephemeral=True)
        
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
            role = guild.get_role(e['role_id']) if guild else None
            role_name = role.name if role else f"Role {e['role_id']}"
            label = e.get('label') or role_name
            emo = format_emoji_for_option(e['emoji'])
            options.append(discord.SelectOption(
                label=label[:100], 
                value=str(e['role_id']),
                description=e.get('description')[:100] if e.get('description') else None,
                emoji=emo
            ))

        if panel.get('role_removal', True):
            options.append(discord.SelectOption(
                label="Remove my roles",
                value=REMOVE_PANEL_ROLES_VALUE,
                description="Remove your currently assigned roles from this panel",
                emoji="❌"
            ))
            
        super().__init__(
            placeholder="Select a role..." if not panel.get('role_removal', True) else "Select a role or remove your roles...",
            options=options,
            min_values=1, # Single select mode, handle logic dynamically
            max_values=1 if not panel.get('multiple_slots', True) else min(len(options), 25),
            custom_id=f"rrsel_{panel['message_id']}"
        )

    async def callback(self, interaction: commands.Context):
        await getattr(interaction, "response", interaction).defer(ephemeral=True)
        
        guild = interaction.guild
        member = getattr(interaction, "user", getattr(interaction, "author", None))
        added_roles = []
        removed_roles = []
        errors = []

        req_role_id = self.panel.get('required_role_id')
        if req_role_id and not member.get_role(req_role_id):
            await _safe_send(interaction, "You lack the required role to use this menu.", ephemeral=True)
            return

        # Figure out which roles they selected
        if REMOVE_PANEL_ROLES_VALUE in self.values:
            if len(self.values) > 1:
                await _safe_send(interaction, "Select role removal by itself.", ephemeral=True)
                return

            for entry in self.entries:
                role = guild.get_role(entry['role_id'])
                if not role or member.get_role(entry['role_id']) is None:
                    continue

                try:
                    await member.remove_roles(role, reason="Reaction Role Menu")
                    removed_roles.append(role.mention)
                except discord.Forbidden:
                    errors.append(f"Cannot remove {role.mention}")

            msgs = []
            if removed_roles: msgs.append(f"❌ Removed: {', '.join(removed_roles)}")
            if errors: msgs.append("⚠️ Errors: " + ", ".join(errors))
            if not msgs:
                msgs.append("You do not currently have any roles from this panel.")

            await _safe_send(interaction, "\n".join(msgs), ephemeral=True)

            if self.panel.get('show_counters', False) and hasattr(self.view, "refresh_counters"):
                await self.view.refresh_counters(interaction)
            return

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
            
        await _safe_send(interaction, "\n".join(msgs), ephemeral=True)
        
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

    async def refresh_counters(self, interaction: commands.Context):
        new_view = DynamicRoleView(self.panel, self.entries, self.guild)
        try:
            await interaction.message.edit(view=new_view)
        except Exception:
            pass


# ==========================================
# SETUP DASHBOARDS (EDITORS)
# ==========================================

class TextEditorModal(discord.ui.Modal, title="Edit Panel Output"):
    p_title = discord.ui.TextInput(label="Title", max_length=256, required=False)
    p_desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False, max_length=2000)
    p_img = discord.ui.TextInput(label="Image URL (Optional)", required=False, placeholder="https://...")

    def __init__(self, editor_view: "DashboardEditorView"):
        super().__init__()
        self.editor_view = editor_view
        self.p_title.default = self.editor_view.panel.get('title') or ""
        self.p_desc.default = self.editor_view.panel.get('description') or ""
        self.p_img.default = self.editor_view.panel.get('image_url') or ""

    async def on_submit(self, interaction: commands.Context):
        title_val = str(self.p_title).strip()
        desc_val = str(self.p_desc).strip()
        raw_image_url = str(self.p_img).strip()
        image_val = None

        if raw_image_url:
            image_val, image_error = await validate_image_url(raw_image_url)
            if image_error:
                await _safe_send(
                    interaction,
                    image_error,
                    ephemeral=True,
                )
                return

        if raw_image_url and not image_val:
            await _safe_send(
                interaction,
                "Invalid image URL. Please use a direct http/https image link.",
                ephemeral=True,
            )
            return
            
        await db.update_reaction_role_message(
            self.editor_view.message_id,
            title=title_val if title_val else "",
            description=desc_val if desc_val else None,
            image_url=image_val
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

    async def on_submit(self, interaction: commands.Context):
        raw_emoji = str(self.p_emoji).strip()
        emoji_str = normalize_emoji(raw_emoji)
        
        # Support raw discord emoji strings and global custom emoji search
        if raw_emoji.startswith('<') and raw_emoji.endswith('>'):
            emoji_str = raw_emoji
        else:
            search_name = raw_emoji.strip(":")
            # Search across all emojis the bot knows about
            custom_emoji = discord.utils.get(interaction.client.emojis, name=search_name)
            if custom_emoji:
                emoji_str = str(custom_emoji)
                
        if not emoji_str:
            await _safe_send(interaction, "Invalid emoji.", ephemeral=True)
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
    async def callback(self, interaction: commands.Context, select: discord.ui.RoleSelect):
        role = select.values[0]
        # Verify role position
        if role.position >= interaction.guild.me.top_role.position:
            await _safe_send(interaction, "That role is too high for me to assign.", ephemeral=True)
            return
            
        await interaction.response.send_modal(SlotEditorModal(self.editor_view, role))


class DashboardEditorView(discord.ui.View):
    def __init__(self, cog: "ReactionRolesCog", interaction: commands.Context, message_id: int):
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

    async def _build_preview_embed(self) -> discord.Embed:
        desc = self.panel.get('description') or ""
        if self.entries and self.panel.get('include_overview', False):
            desc += "\n\n**Roles:**\n"
            for e in self.entries:
                desc += f"{e['emoji']} -> <@&{e['role_id']}>\n"
                
        embed = discord.Embed(
            title=(self.panel.get('title') or None),
            description=(desc or None),
            color=await get_guild_color(self.panel['guild_id'])
        )
        if self.panel.get('image_url'):
            try:
                embed.set_image(url=normalize_image_url(self.panel['image_url']) or self.panel['image_url'])
            except Exception:
                pass
        embed.set_footer(text="👁️ Preview of your Role Message")
        return embed

    async def apply_update(self, **kwargs):
        await db.update_reaction_role_message(self.message_id, **kwargs)

    async def refresh(self, interaction: commands.Context):
        await self.fetch_state()
        try:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        except discord.InteractionResponded:
            await interaction.message.edit(embed=self._build_embed(), view=self)
            
        # Update ephemeral preview message if it exists
        if hasattr(self, 'preview_message') and self.preview_message:
            view = DynamicRoleView(self.panel, self.entries, interaction.guild)
            preview_embed = await self._build_preview_embed()
            preview_embed.set_footer(text=None)
            try:
                await self.preview_message.edit(embed=preview_embed, view=view)
            except Exception:
                pass
                
        # LIVE UPDATE IF PUBLISHED!
        if self.message_id > 0:
            guild = interaction.guild
            if guild:
                channel = guild.get_channel(self.panel['channel_id'])
                if channel:
                    try:
                        msg = await channel.fetch_message(self.message_id)
                        live_view = DynamicRoleView(self.panel, self.entries, guild)
                        live_embed, live_attachments = await self.cog._build_panel_embed_and_attachments(self.panel, self.entries)
                        await msg.edit(embed=live_embed, view=live_view, attachments=live_attachments)
                    except Exception:
                        pass

    # 1. Row 1
    @discord.ui.button(label="Adjust Text/Image", style=discord.ButtonStyle.primary, row=0)
    async def btn_adjust_text(self, interaction: commands.Context, btn: discord.ui.Button):
        await interaction.response.send_modal(TextEditorModal(self))

    @discord.ui.button(label="Add Slot", style=discord.ButtonStyle.primary, row=0)
    async def btn_add_slot(self, interaction: commands.Context, btn: discord.ui.Button):
        await _safe_send(interaction, "Select a role to add...", view=AddSlotRoleSelectView(self), ephemeral=True)

    @discord.ui.button(label="Remove Slot", style=discord.ButtonStyle.danger, row=0)
    async def btn_remove_slot(self, interaction: commands.Context, btn: discord.ui.Button):
        if not self.entries:
            await _safe_send(interaction, "No slots to remove.", ephemeral=True)
            return
            
        class RemoveSelectView(discord.ui.View):
            def __init__(self, editor: DashboardEditorView):
                super().__init__(timeout=900)
                options = []
                for e in editor.entries:
                    # SAFE UI: No 'emoji=' field used in SelectOption to avoid API crashes
                    role_id = e['role_id']
                    e_emoji = e['emoji']
                    options.append(discord.SelectOption(
                        label=f"{e_emoji} Slot: {role_id}", 
                        value=e_emoji,
                        description=f"Remove this mapping"
                    ))
                self.sel = discord.ui.Select(placeholder="Select slot to drop...", options=options)
                self.sel.callback = self.callback
                self.add_item(self.sel)
                self.editor = editor
                
            async def callback(self, inter: commands.Context):
                await db.remove_reaction_role_entry(self.editor.message_id, self.sel.values[0])
                await self.editor.refresh(inter)
                
        await _safe_send(interaction, "Select the mapping to drop.", view=RemoveSelectView(self), ephemeral=True)

    # 2. Row 2 (Toggles)
    @discord.ui.button(label="Toggle Role Removal", style=discord.ButtonStyle.secondary, row=1)
    async def btn_role_rem(self, interaction: commands.Context, btn: discord.ui.Button):
        current = self.panel.get('role_removal', True)
        await self.apply_update(role_removal=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Toggle Multi-Slot", style=discord.ButtonStyle.secondary, row=1)
    async def btn_multi(self, interaction: commands.Context, btn: discord.ui.Button):
        current = self.panel.get('multiple_slots', True)
        await self.apply_update(multiple_slots=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Switch Component Type", style=discord.ButtonStyle.secondary, row=1)
    async def btn_comp(self, interaction: commands.Context, btn: discord.ui.Button):
        current = self.panel.get('component_type', 'Buttons')
        new_val = 'Select' if current == 'Buttons' else 'Buttons'
        await self.apply_update(component_type=new_val)
        await self.refresh(interaction)

    @discord.ui.button(label="Toggle Role Counters", style=discord.ButtonStyle.secondary, row=1)
    async def btn_counters(self, interaction: commands.Context, btn: discord.ui.Button):
        current = self.panel.get('show_counters', False)
        await self.apply_update(show_counters=not current)
        await self.refresh(interaction)

    # 3. Row 3 
    @discord.ui.button(label="Toggle Slot Overview", style=discord.ButtonStyle.secondary, row=2)
    async def btn_overview(self, interaction: commands.Context, btn: discord.ui.Button):
        current = self.panel.get('include_overview', False)
        await self.apply_update(include_overview=not current)
        await self.refresh(interaction)

    @discord.ui.button(label="Require Role...", style=discord.ButtonStyle.secondary, row=2)
    async def btn_req_role(self, interaction: commands.Context, btn: discord.ui.Button):
        class ReqRoleSelectView(discord.ui.View):
            def __init__(self, editor: DashboardEditorView):
                super().__init__(timeout=300)
                self.editor = editor
            @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select required Role (or none to drop)")
            async def call(self, inter: commands.Context, sel: discord.ui.RoleSelect):
                await db.update_reaction_role_message(self.editor.message_id, required_role_id=sel.values[0].id)
                await self.editor.refresh(inter)
            @discord.ui.button(label="Clear Requirement", style=discord.ButtonStyle.danger)
            async def call2(self, inter: commands.Context, b: discord.ui.Button):
                await db.update_reaction_role_message(self.editor.message_id, required_role_id=None)
                await self.editor.refresh(inter)
        await _safe_send(interaction, "Set requirement:", view=ReqRoleSelectView(self), ephemeral=True)

    @discord.ui.button(label="Submit/Publish >>", style=discord.ButtonStyle.success, row=2)
    async def btn_publish(self, interaction: commands.Context, btn: discord.ui.Button):
        await self.cog.publish_panel(self.message_id, interaction)
        self.stop()

    @discord.ui.button(label="Delete/Discard Panel", style=discord.ButtonStyle.danger, row=3, custom_id="btn_delete_panel")
    async def btn_delete(self, interaction: commands.Context, btn: discord.ui.Button):
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
    async def btn_create(self, interaction: commands.Context, btn: discord.ui.Button):
        # We need a channel target.
        class ChSelectView(discord.ui.View):
            def __init__(self, cog: "ReactionRolesCog"):
                super().__init__()
                self.cog = cog
            @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text])
            async def cb(self, inter: commands.Context, sel: discord.ui.ChannelSelect):
                import time
                draft_id = -int(time.time() * 1000)
                
                raw_ch = sel.values[0]
                ch = inter.guild.get_channel(raw_ch.id)
                if not ch:
                    await _safe_send(inter, "Could not resolve that channel.", ephemeral=True)
                    return
                    
                await db.create_reaction_role_message(inter.guild_id, ch.id, draft_id, "Reaction Roles", "Use the buttons below to assign yourself roles.", getattr(inter, 'user', getattr(inter, 'author', None)).id)
                
                editor = DashboardEditorView(self.cog, inter, draft_id)
                await editor.fetch_state()
                await inter.response.edit_message(content=None, embed=editor._build_embed(), view=editor)
                
                # Send the realtime preview
                view = DynamicRoleView(editor.panel, editor.entries, inter.guild)
                preview_embed = await editor._build_preview_embed()
                preview_embed.set_footer(text=None)
                editor.preview_message = await inter.followup.send(content="**Live Preview:**", embed=preview_embed, view=view, ephemeral=True)
                
        await _safe_send(interaction, "Where should the panel be posted?", view=ChSelectView(self.cog), ephemeral=True)

    @discord.ui.button(label="Edit Role Messages", style=discord.ButtonStyle.secondary)
    async def btn_edit(self, interaction: commands.Context, btn: discord.ui.Button):
        panels = await db.get_reaction_role_messages(interaction.guild.id)
        if not panels:
            await _safe_send(interaction, "No panels configured. Create one first.", ephemeral=True)
            return
            
        class EditSelView(discord.ui.View):
            def __init__(self, cog, panels, guild):
                super().__init__()
                opts = []
                for p in panels[:25]:
                    ch = guild.get_channel(p['channel_id'])
                    ch_name = f"#{ch.name}" if ch else "deleted-channel"
                    opts.append(discord.SelectOption(
                        label=f"{p['title']} in {ch_name}"[:100], 
                        value=str(p['message_id'])
                    ))
                self.sel = discord.ui.Select(options=opts)
                self.sel.callback = self.cb
                self.add_item(self.sel)
                self.cog = cog

            async def cb(self, inter: commands.Context):
                editor = DashboardEditorView(self.cog, inter, int(self.sel.values[0]))
                await editor.fetch_state()
                await inter.response.edit_message(content=None, embed=editor._build_embed(), view=editor)
                
                # Send the realtime preview
                view = DynamicRoleView(editor.panel, editor.entries, inter.guild)
                preview_embed = await editor._build_preview_embed()
                preview_embed.set_footer(text=None)
                editor.preview_message = await inter.followup.send(content="**Live Preview:**", embed=preview_embed, view=view, ephemeral=True)
                
        await _safe_send(interaction, "Select a panel to edit:", view=EditSelView(self.cog, panels, interaction.guild), ephemeral=True)


# ==========================================
# COG IMPLEMENTATION
# ==========================================

class ReactionRolesCog(commands.Cog):
    @commands.hybrid_group(name="reactionroles", description="Lawliet-style reaction roles manager")
    async def reactionroles_group(self, ctx: commands.Context):
        pass

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_panel_embed_and_attachments(self, panel: dict, entries: list):
        desc = panel.get('description') or ""
        if entries and panel.get('include_overview', False):
            desc += "\n\n**Roles:**\n"
            for e in entries:
                desc += f"{e['emoji']} -> <@&{e['role_id']}>\n"

        embed = discord.Embed(
            title=(panel.get('title') or None),
            description=(desc or None),
            color=await get_guild_color(panel['guild_id'])
        )

        attachments = []
        image_url = panel.get('image_url')
        if image_url:
            normalized_url = normalize_image_url(image_url) or image_url
            if is_discord_hosted_image(normalized_url):
                embed.set_image(url=normalized_url)
            else:
                hosted_file, image_error = await download_image_for_discord(normalized_url)
                if hosted_file is not None:
                    attachments.append(hosted_file)
                    embed.set_image(url=f"attachment://{hosted_file.filename}")
                else:
                    logger.warning("Failed to rehost reaction role image for panel %s: %s", panel.get('message_id'), image_error)

        return embed, attachments

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

    async def publish_panel(self, message_id: int, interaction: commands.Context):
        logger.info(f"Publishing/Updating reaction role panel {message_id}")
        
        try:
            await getattr(interaction, "response", interaction).defer(ephemeral=True)
        except Exception:
            pass

        try:
            panel = await db.get_reaction_role_message(message_id)
            if not panel:
                if not interaction.response.is_done():
                    await _safe_send(interaction, "Error: Panel not found.", ephemeral=True)
                return

            guild = interaction.guild
            if not guild: return
            channel = guild.get_channel(panel['channel_id'])
            if not channel: return

            entries = await db.get_reaction_role_entries(message_id)
            embed, embed_attachments = await self._build_panel_embed_and_attachments(panel, entries)
            
            panel_to_use = dict(panel)
            if message_id < 0:
                # Claim real ID first
                real_msg = await channel.send("Publishing panel...")
                panel_to_use['message_id'] = real_msg.id
                
                # Update DB
                async with db._pool.acquire() as conn:
                    await conn.execute("UPDATE reaction_role_messages SET message_id=$1 WHERE message_id=$2", real_msg.id, message_id)
                    await conn.execute("UPDATE reaction_role_entries SET message_id=$1 WHERE message_id=$2", real_msg.id, message_id)

            if message_id < 0:
                target_msg = real_msg
            else:
                target_msg = await channel.fetch_message(message_id)
                
            # ATTACH UI components
            view = DynamicRoleView(panel_to_use, entries, guild)
            await target_msg.edit(content=None, embed=embed, view=view, attachments=embed_attachments)
            try:
                await target_msg.clear_reactions()
            except discord.Forbidden:
                pass
            
            action_str = "published" if message_id < 0 else "updated"
            await _safe_send(interaction, f"✅ Reaction panel successfully {action_str} in {channel.mention}!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error publishing panel: {e}", exc_info=True)
            if not getattr(interaction, "response", interaction).is_done():
                try:
                    await _safe_send(interaction, f"An unexpected error occurred: `{e}`", ephemeral=True)
                except Exception:
                    pass
    @reactionroles_group.command(name="dashboard", description="Open the main Reaction Roles setup dashboard")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def rp_dashboard(self, interaction: commands.Context):
        emb = discord.Embed(
            title="☑️ Reaction Roles",
            description="Create role messages that members can use to obtain or revoke roles. Interactive and fast component system based on modern Discord UI features.",
            color=0x5865F2
        )
        await _safe_send(interaction, embed=emb, view=MainDashboardHome(self), ephemeral=True)

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
                self.bot.add_view(DynamicRoleView(p, entries, guild), message_id=p['message_id'])


    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        try:
            await db.delete_reaction_role_message(payload.message_id)
        except Exception:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRolesCog(bot))
