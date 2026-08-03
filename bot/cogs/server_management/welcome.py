import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from core import database_pg as db
from cogs.utilities.embed_builder import EmbedFieldEditorView
from utils.embeds import (
    get_embed_color,
    has_time_placeholder,
    normalize_embed_fields,
    process_member_text,
    set_embed_footer,
)

logger = logging.getLogger(__name__)


def _json_object(value) -> dict:
    """Normalize JSONB values returned as dicts or JSON strings."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


async def _safe_send(interaction, content=None, **kwargs):
    """Safely sends a message whether we have an Interaction or a Context."""
    try:
        if isinstance(interaction, commands.Context):
            return await interaction.send(content, **kwargs)
        else:
            if interaction.response.is_done():
                return await interaction.followup.send(content, **kwargs)
            else:
                await interaction.response.send_message(content, **kwargs)
                return await interaction.original_response()
    except Exception as e:
        logger.error(f"Failed safe send: {e}")
        return None


class WelcomeChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, view_obj):
        self.view_obj = view_obj
        super().__init__(
            placeholder=(
                "Select a channel for this traffic event..."
                if view_obj.traffic_event
                else "Select a channel for level-up notifications..."
                if view_obj.level_up
                else "Select a channel to post the welcome message..."
            ),
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1
        )
        
    async def callback(self, interaction: commands.Context):
        ch = self.values[0]
        await self.view_obj.set_target_channel(ch.id)
        await self.view_obj.refresh(interaction)


class MainTextModal(discord.ui.Modal, title="Edit Welcome Text"):
    p_content = discord.ui.TextInput(label="Ping / Outside Text", required=False, max_length=2000, placeholder="Welcome {user} to the server!")
    p_title = discord.ui.TextInput(label="Embed Title", required=False, max_length=256)
    p_desc = discord.ui.TextInput(label="Embed Description", style=discord.TextStyle.paragraph, required=False, max_length=4000)

    def __init__(self, view_obj):
        super().__init__(title=view_obj.modal_title("Edit Text"))
        self.view_obj = view_obj
        p = view_obj.settings
        if view_obj.traffic_event or view_obj.level_up or view_obj.ticket_open:
            self.p_content.label = "Optional Message Text"
            self.p_content.placeholder = "Optional text outside the embed"
            self.p_title.label = "Embed Title"
            self.p_desc.label = "Embed Description"
        self.p_content.default = p.get('message') or ""
        self.p_title.default = p.get('embed_title') or ""
        self.p_desc.default = p.get('embed_description') or ""

    async def on_submit(self, interaction: commands.Context):
        await self.view_obj.update_settings(
            message=str(self.p_content).strip() or None,
            embed_title=str(self.p_title).strip() or None,
            embed_description=str(self.p_desc).strip() or None,
        )
        await self.view_obj.refresh(interaction)

class ImagesModal(discord.ui.Modal, title="Edit Welcome Images"):
    p_thumb = discord.ui.TextInput(label="Thumbnail URL", required=False, placeholder="https://... or {user.avatar}")
    p_img = discord.ui.TextInput(label="Large Image URL", required=False, placeholder="https://...")

    def __init__(self, view_obj):
        super().__init__(title=view_obj.modal_title("Edit Images"))
        self.view_obj = view_obj
        p = view_obj.settings
        self.p_thumb.default = p.get('embed_thumbnail') or ""
        self.p_img.default = p.get('embed_image') or ""

    async def on_submit(self, interaction: commands.Context):
        await self.view_obj.update_settings(
            embed_thumbnail=str(self.p_thumb).strip() or None,
            embed_image=str(self.p_img).strip() or None
        )
        await self.view_obj.refresh(interaction)

class AuthorFooterModal(discord.ui.Modal, title="Author & Footer"):
    p_aname = discord.ui.TextInput(label="Author Name", required=False, max_length=256)
    p_aicon = discord.ui.TextInput(label="Author Icon URL", required=False, placeholder="https://... or {user.avatar}")
    p_ftext = discord.ui.TextInput(label="Footer Text", required=False, max_length=2048)
    p_ficon = discord.ui.TextInput(label="Footer Icon URL", required=False, placeholder="https://... or {server.icon}")

    def __init__(self, view_obj):
        super().__init__(title=view_obj.modal_title("Edit Author & Footer"))
        self.view_obj = view_obj
        p = view_obj.settings
        self.p_aname.default = p.get('embed_author_name') or ""
        self.p_aicon.default = p.get('embed_author_icon') or ""
        self.p_ftext.default = p.get('embed_footer_text') or ""
        self.p_ficon.default = p.get('embed_footer_icon') or ""

    async def on_submit(self, interaction: commands.Context):
        await self.view_obj.update_settings(
            embed_author_name=str(self.p_aname).strip() or None,
            embed_author_icon=str(self.p_aicon).strip() or None,
            embed_footer_text=str(self.p_ftext).strip() or None,
            embed_footer_icon=str(self.p_ficon).strip() or None
        )
        await self.view_obj.refresh(interaction)


class TriggerColorModal(discord.ui.Modal, title="Trigger Embed Color"):
    p_color = discord.ui.TextInput(
        label="Embed Color (empty = reset)",
        required=False,
        max_length=16,
        placeholder="#RRGGBB, 0xRRGGBB, 5793266, or leave empty",
    )

    def __init__(self, view_obj, current_color: int | None = None):
        super().__init__(title=view_obj.modal_title("Set Color"))
        self.view_obj = view_obj
        current = current_color
        if current is None and view_obj.trigger_word:
            current = view_obj.settings.get('embed_color')
        self.p_color.default = f"#{int(current):06X}" if isinstance(current, int) else ""

    @staticmethod
    def _parse_color(raw: str) -> int | None:
        value = (raw or "").strip()
        if not value:
            return None

        if value.startswith("#"):
            value = value[1:]
        elif value.lower().startswith("0x"):
            value = value[2:]

        if all(ch in "0123456789abcdefABCDEF" for ch in value) and len(value) in {3, 6}:
            if len(value) == 3:
                value = "".join(ch * 2 for ch in value)
            return int(value, 16)

        if value.isdigit():
            parsed = int(value)
            if 0 <= parsed <= 0xFFFFFF:
                return parsed
        return -1

    async def on_submit(self, interaction: commands.Context):
        parsed = self._parse_color(str(self.p_color))
        if parsed == -1:
            await interaction.response.send_message(
                "❌ Invalid color. Use `#RRGGBB`, `0xRRGGBB`, short hex like `#ABC`, or a decimal between 0 and 16777215.",
                ephemeral=True,
            )
            return

        await self.view_obj.apply_color_value(parsed)
        await self.view_obj.refresh(interaction)

class WelcomeDashboardView(discord.ui.View):
    def __init__(
        self,
        cog,
        interaction,
        traffic_event: str | None = None,
        trigger_word: str | None = None,
        level_up: bool = False,
        ticket_open: bool = False,
    ):
        super().__init__(timeout=600)
        self.cog = cog
        self.orig_interaction = interaction
        self.traffic_event = traffic_event
        self.trigger_word = trigger_word
        self.level_up = level_up
        self.ticket_open = ticket_open
        self.settings = None
        self.preview_message = None

        if trigger_word:
            self.btn_channel.label = "Trigger Word"
            self.btn_channel.disabled = True
            self.btn_text.label = "Edit Trigger Text"
            self.btn_images.label = "Edit Trigger Images"
            self.btn_author_footer.label = "Edit Trigger Author & Footer"
            self.btn_fields.label = "Edit Trigger Fields"
            self.btn_color.label = "Set Trigger Color"
            self.btn_color.disabled = False
            self.btn_clear.label = "Reset Trigger Embed"
        elif traffic_event:
            self.btn_channel.label = "Set Traffic Channel"
            self.btn_text.label = "Edit Traffic Text"
            self.btn_images.label = "Edit Traffic Images"
            self.btn_author_footer.label = "Edit Traffic Author & Footer"
            self.btn_fields.label = "Edit Traffic Fields"
            self.btn_color.label = "Set Traffic Color"
            self.btn_color.disabled = False
            self.btn_clear.label = "Reset Traffic Embed"
        elif level_up:
            self.btn_channel.label = "Set Level-Up Channel"
            self.btn_text.label = "Edit Level-Up Text"
            self.btn_images.label = "Edit Level-Up Images"
            self.btn_author_footer.label = "Edit Level-Up Author & Footer"
            self.btn_fields.label = "Edit Level-Up Fields"
            self.btn_color.label = "Set Level-Up Color"
            self.btn_color.disabled = False
            self.btn_clear.label = "Reset Level-Up Embed"
        elif ticket_open:
            self.btn_channel.label = "Ticket Open Message"
            self.btn_channel.disabled = True
            self.btn_text.label = "Edit Ticket Open Text"
            self.btn_images.label = "Edit Ticket Open Images"
            self.btn_author_footer.label = "Edit Ticket Open Author & Footer"
            self.btn_fields.label = "Edit Ticket Open Fields"
            self.btn_color.label = "Set Ticket Open Color"
            self.btn_color.disabled = False
            self.btn_clear.label = "Reset Ticket Open Message"
        else:
            self.btn_color.label = "Set Welcome Color"
            self.btn_color.disabled = False

    def _embed_enabled(self) -> bool:
        return bool(self.settings.get('embed_enabled', True)) if self.settings else True

    def _update_embed_toggle_button(self):
        enabled = self._embed_enabled()
        self.btn_toggle_embed.label = "✅ Embed Enabled" if enabled else "⛔ Embed Disabled"
        self.btn_toggle_embed.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary

    def traffic_label(self) -> str:
        return {
            'join': 'Member Join',
            'leave': 'Member Leave',
            'boost': 'Server Boost',
        }.get(self.traffic_event, 'Traffic')

    def context_label(self) -> str:
        if self.trigger_word:
            return f"Trigger `{self.trigger_word}`"
        if self.traffic_event:
            return self.traffic_label()
        if self.level_up:
            return "Level-Up"
        if self.ticket_open:
            return "Ticket Open"
        return "Welcome"

    def modal_title(self, action: str) -> str:
        if self.trigger_word or self.traffic_event or self.level_up:
            return f"{self.context_label()} • {action}"
        return f"{action} Welcome"

    def color_embed_key(self) -> str | None:
        if self.trigger_word:
            return None
        if self.traffic_event:
            return f"traffic_{self.traffic_event}"
        if self.level_up:
            return "level_up_notification"
        if self.ticket_open:
            return "ticket_open_message"
        return "welcome_message"

    async def apply_color_value(self, parsed: int | None):
        guild_id = self.orig_interaction.guild.id
        if self.trigger_word:
            # Empty input restores trigger default color.
            color_value = 0x5865F2 if parsed is None else parsed
            await self.update_settings(embed_color=color_value)
            return

        embed_key = self.color_embed_key()
        if not embed_key:
            return
        if parsed is None:
            await db.reset_embed_color(guild_id, embed_key)
        else:
            await db.set_embed_color(guild_id, embed_key, int(parsed))

    async def current_embed_color_value(self) -> int:
        """Return the effective color value currently used by this dashboard."""
        if self.trigger_word:
            configured = self.settings.get('embed_color') if self.settings else None
            if isinstance(configured, int):
                return configured
            # Trigger embeds keep their own built-in default unless explicitly changed.
            return 0x5865F2

        resolved = await self.embed_color()
        return int(resolved.value)

    async def embed_color(self) -> discord.Color:
        """Return this dashboard's color without borrowing Welcome's color."""
        guild_id = self.orig_interaction.guild.id
        if self.traffic_event:
            return await get_embed_color(
                guild_id,
                f"traffic_{self.traffic_event}",
                "color_primary",
            )
        if self.level_up:
            return await get_embed_color(guild_id, "level_up_notification", "color_level_up")
        if self.ticket_open:
            return await get_embed_color(guild_id, "ticket_open_message", "color_ticket")
        return await get_embed_color(guild_id, "welcome_message", "color_welcome")

    async def fetch_state(self):
        guild_id = self.orig_interaction.guild.id
        if self.trigger_word:
            record = await db.get_trigger_embed(guild_id, self.trigger_word) or {}
            embed_data = _json_object(record.get('embed_data'))
            self.settings = {
                'channel_id': None,
                'message': record.get('content'),
                'embed_enabled': bool(embed_data.get('enabled', True)),
                'embed_title': embed_data.get('title'),
                'embed_description': embed_data.get('description'),
                'embed_thumbnail': (embed_data.get('thumbnail') or {}).get('url'),
                'embed_image': (embed_data.get('image') or {}).get('url'),
                'embed_author_name': (embed_data.get('author') or {}).get('name'),
                'embed_author_icon': (embed_data.get('author') or {}).get('icon_url'),
                'embed_footer_text': (embed_data.get('footer') or {}).get('text'),
                'embed_footer_icon': (embed_data.get('footer') or {}).get('icon_url'),
                'embed_fields': normalize_embed_fields(embed_data.get('fields')),
                'embed_color': embed_data.get('color'),
                'embed_timestamp': embed_data.get('timestamp'),
                '_embed_data': embed_data,
            }
            if not embed_data:
                self.settings.update({
                    'embed_enabled': True,
                    'embed_title': 'Triggered Embed',
                    'embed_description': 'Customize this triggered message.',
                    'embed_color': 0x5865F2,
                })
            return

        if self.level_up:
            config = await db.get_level_up_embed_config(guild_id) or {}
            self.settings = {
                'channel_id': await db.get_level_log_channel_id(guild_id),
                'message': config.get('message'),
                'embed_enabled': bool(config.get('embed_enabled', True)),
                'embed_title': config.get('title'),
                'embed_description': config.get('description'),
                'embed_thumbnail': config.get('thumbnail'),
                'embed_image': config.get('image'),
                'embed_author_name': config.get('author_name'),
                'embed_author_icon': config.get('author_icon'),
                'embed_footer_text': config.get('footer_text'),
                'embed_footer_icon': config.get('footer_icon'),
                'embed_fields': normalize_embed_fields(config.get('fields')),
                'embed_timestamp': bool(config.get('timestamp_enabled', False)),
            }

            if not config:
                self.settings.update({
                    'embed_enabled': True,
                    'embed_title': '🎉 Level Up!',
                    'embed_description': '{user} has reached **Level {level}**!',
                    'embed_thumbnail': '{user.avatar}',
                    'embed_fields': [
                        {'name': 'Current XP', 'value': '{current_xp}', 'inline': True},
                        {'name': 'Next Level', 'value': '{next_level_xp} XP', 'inline': True},
                    ],
                    'embed_timestamp': False,
                })
            return

        if self.ticket_open:
            config = await db.get_ticket_open_message_config(guild_id) or {}
            self.settings = {
                'channel_id': None,
                'message': config.get('content'),
                'embed_enabled': bool(config.get('embed_enabled', True)),
                'embed_title': config.get('title'),
                'embed_description': config.get('description'),
                'embed_thumbnail': config.get('thumbnail'),
                'embed_image': config.get('image'),
                'embed_author_name': config.get('author_name'),
                'embed_author_icon': config.get('author_icon'),
                'embed_footer_text': config.get('footer_text'),
                'embed_footer_icon': config.get('footer_icon'),
                'embed_fields': normalize_embed_fields(config.get('fields')),
                'embed_timestamp': bool(config.get('timestamp_enabled', False)),
            }

            if not config:
                self.settings.update({
                    'embed_enabled': True,
                    'embed_title': 'Ticket #{ticket_id}',
                    'embed_description': 'Welcome {user}!\n\nPlease describe your issue and our support team will be with you shortly.',
                    'embed_timestamp': False,
                })
            return

        if not self.traffic_event:
            self.settings = await db.get_or_create_welcome_message(guild_id)
            self.settings['embed_enabled'] = bool(self.settings.get('embed_enabled', True))
            self.settings['embed_fields'] = normalize_embed_fields(self.settings.get('embed_fields'))
            return

        config = await db.get_traffic_embed_config(guild_id, self.traffic_event) or {}
        channel_id = await db.get_traffic_event_channel_id(guild_id, self.traffic_event)
        if channel_id is None:
            channel_id = await db.get_traffic_log_channel_id(guild_id)

        self.settings = {
            'channel_id': channel_id,
            'message': config.get('content'),
            'embed_enabled': bool(config.get('embed_enabled', True)),
            'embed_title': config.get('title'),
            'embed_description': config.get('description'),
            'embed_thumbnail': config.get('thumbnail'),
            'embed_image': config.get('image'),
            'embed_author_name': config.get('author_name'),
            'embed_author_icon': config.get('author_icon'),
            'embed_footer_text': config.get('footer_text'),
            'embed_footer_icon': config.get('footer_icon'),
            'embed_fields': normalize_embed_fields(config.get('fields')),
        }

        if not config:
            if self.traffic_event == 'join':
                self.settings['embed_title'] = '{user.name} joined the server'
            elif self.traffic_event == 'leave':
                self.settings['embed_title'] = '{user.name} left the server'
            else:
                self.settings['embed_title'] = '{user.name} boosted the server'
            self.settings['embed_enabled'] = True
            self.settings['embed_thumbnail'] = '{user.avatar}'
            self.settings['embed_footer_text'] = '{server} • {member_count} members'
            self.settings['embed_footer_icon'] = '{server.icon}'

    async def set_target_channel(self, channel_id: int):
        guild_id = self.orig_interaction.guild.id
        if self.traffic_event:
            await db.set_traffic_event_channel(guild_id, self.traffic_event, channel_id)
        elif self.level_up:
            await db.set_level_log_channel(guild_id, channel_id)
        elif self.ticket_open:
            return
        else:
            await db.update_welcome_message(guild_id, channel_id=channel_id)

    async def update_settings(self, **values):
        guild_id = self.orig_interaction.guild.id
        if self.trigger_word:
            self.settings.update(values)
            embed_data = dict(self.settings.get('_embed_data') or {})
            embed_data['enabled'] = bool(self.settings.get('embed_enabled', True))
            embed_data['title'] = self.settings.get('embed_title') or None
            embed_data['description'] = self.settings.get('embed_description') or None
            embed_data['fields'] = self.settings.get('embed_fields', [])
            if self.settings.get('embed_color') is not None:
                embed_data['color'] = int(self.settings['embed_color'])
            else:
                embed_data.pop('color', None)
            if self.settings.get('embed_thumbnail'):
                embed_data['thumbnail'] = {'url': self.settings['embed_thumbnail']}
            else:
                embed_data.pop('thumbnail', None)
            if self.settings.get('embed_image'):
                embed_data['image'] = {'url': self.settings['embed_image']}
            else:
                embed_data.pop('image', None)
            if self.settings.get('embed_author_name'):
                embed_data['author'] = {
                    'name': self.settings['embed_author_name'],
                    'icon_url': self.settings.get('embed_author_icon'),
                }
            else:
                embed_data.pop('author', None)
            if self.settings.get('embed_footer_text'):
                embed_data['footer'] = {
                    'text': self.settings['embed_footer_text'],
                    'icon_url': self.settings.get('embed_footer_icon'),
                }
            else:
                embed_data.pop('footer', None)
            await db.update_trigger_embed(
                guild_id,
                self.trigger_word,
                content=self.settings.get('message'),
                embed_data=embed_data,
            )
            self.settings['_embed_data'] = embed_data
            return

        if self.level_up:
            mapping = {
                'message': 'message',
                'embed_title': 'title',
                'embed_description': 'description',
                'embed_thumbnail': 'thumbnail',
                'embed_image': 'image',
                'embed_author_name': 'author_name',
                'embed_author_icon': 'author_icon',
                'embed_footer_text': 'footer_text',
                'embed_footer_icon': 'footer_icon',
                'embed_fields': 'fields',
                'embed_timestamp': 'timestamp_enabled',
                'embed_enabled': 'embed_enabled',
            }
            level_values = {
                mapping[key]: value
                for key, value in values.items()
                if key in mapping
            }
            if level_values:
                await db.set_level_up_embed_config(guild_id, **level_values)
            return

        if self.ticket_open:
            mapping = {
                'message': 'content',
                'embed_title': 'title',
                'embed_description': 'description',
                'embed_thumbnail': 'thumbnail',
                'embed_image': 'image',
                'embed_author_name': 'author_name',
                'embed_author_icon': 'author_icon',
                'embed_footer_text': 'footer_text',
                'embed_footer_icon': 'footer_icon',
                'embed_fields': 'fields',
                'embed_timestamp': 'timestamp_enabled',
                'embed_enabled': 'embed_enabled',
            }
            open_values = {
                mapping[key]: value
                for key, value in values.items()
                if key in mapping
            }
            if open_values:
                await db.set_ticket_open_message_config(guild_id, **open_values)
            return

        if not self.traffic_event:
            await db.update_welcome_message(guild_id, **values)
            return

        mapping = {
            'message': 'content',
            'embed_enabled': 'embed_enabled',
            'embed_title': 'title',
            'embed_description': 'description',
            'embed_thumbnail': 'thumbnail',
            'embed_image': 'image',
            'embed_author_name': 'author_name',
            'embed_author_icon': 'author_icon',
            'embed_footer_text': 'footer_text',
            'embed_footer_icon': 'footer_icon',
            'embed_fields': 'fields',
        }
        traffic_values = {
            mapping[key]: value
            for key, value in values.items()
            if key in mapping
        }
        if traffic_values:
            await db.set_traffic_embed_config(
                guild_id,
                self.traffic_event,
                **traffic_values,
            )

    async def _build_preview(self, interaction: commands.Context, preview_mode=False):
        welcome = self.settings
        member = getattr(interaction, 'user', getattr(interaction, 'author', None))
        guild = interaction.guild

        extra_values = {}
        if self.trigger_word:
            extra_values = {'trigger': self.trigger_word, 'event': 'trigger'}
        elif self.level_up:
            preview_level = 12
            next_required = 7286
            extra_values = {
                'event': 'level_up',
                'level': str(preview_level),
                'levels_gained': '1',
                'current_xp': f"{next_required - 15:,}",
                'next_level_xp': f"{next_required:,}",
                'role_unlocked': '@Level Role',
            }
        elif self.ticket_open:
            extra_values = {
                'event': 'ticket_open',
                'ticket_id': '1234',
                'support_role': '@Support',
                'ticket_channel': '#ticket-sample-1234',
            }
        elif self.traffic_event:
            extra_values = {
                'account_created': f"<t:{int(member.created_at.timestamp())}:f>",
                'joined_at': (
                    f"<t:{int(member.joined_at.timestamp())}:f>"
                    if member.joined_at else "Unknown"
                ),
                'event': self.traffic_event,
            }
        
        def process_text(txt):
            if not txt or not preview_mode:
                return txt or ""
            return process_member_text(txt, member, extra_values=extra_values)

        preview_time = discord.utils.utcnow()

        def process_embed_text(txt):
            if not txt or not preview_mode:
                return txt or ""
            return process_member_text(txt, member, event_time=preview_time, extra_values=extra_values)

        def process_footer_text(txt):
            if not txt or not preview_mode:
                return txt or ""
            return process_member_text(txt, member, event_time=preview_time, time_value="", extra_values=extra_values)

        content = process_text(welcome.get('message'))
        embed_enabled = bool(welcome.get('embed_enabled', True))
        
        embed = None
        if embed_enabled and any(welcome.get(k) for k in ['embed_title', 'embed_description', 'embed_image', 'embed_thumbnail', 'embed_author_name', 'embed_footer_text', 'embed_footer_icon', 'embed_fields']):
            embed_values = [
                welcome.get('embed_title'),
                welcome.get('embed_description'),
                welcome.get('embed_author_name'),
                welcome.get('embed_author_icon'),
                welcome.get('embed_thumbnail'),
                welcome.get('embed_image'),
                welcome.get('embed_footer_text'),
                welcome.get('embed_footer_icon'),
            ]
            embed = discord.Embed(
                title=process_embed_text(welcome.get('embed_title')) or None,
                description=process_embed_text(welcome.get('embed_description')) or None,
                color=(
                    discord.Color(welcome['embed_color'])
                    if self.trigger_word and welcome.get('embed_color') is not None
                    else await self.embed_color()
                ),
                timestamp=(
                    preview_time
                    if preview_mode and (
                        has_time_placeholder(*embed_values)
                        or bool(welcome.get('embed_timestamp'))
                    )
                    else None
                ),
            )
            
            if welcome.get('embed_author_name'):
                icon = process_embed_text(welcome.get('embed_author_icon')) or None
                embed.set_author(name=process_embed_text(welcome.get('embed_author_name')), icon_url=icon)
                
            if welcome.get('embed_thumbnail'):
                embed.set_thumbnail(url=process_embed_text(welcome.get('embed_thumbnail')))
                
            if welcome.get('embed_image'):
                embed.set_image(url=process_embed_text(welcome.get('embed_image')))
                
            set_embed_footer(
                embed,
                text=process_footer_text(welcome.get('embed_footer_text')),
                icon_url=process_embed_text(welcome.get('embed_footer_icon')),
            )

            for field in welcome.get('embed_fields', [])[:25]:
                if not isinstance(field, dict) or not field.get('name'):
                    continue
                embed.add_field(
                    name=process_embed_text(field['name']) or 'Field',
                    value=(process_embed_text(field.get('value')) or '-')[:1024],
                    inline=bool(field.get('inline', False)),
                )
                
        return content, embed

    async def _build_editor_embed(self) -> discord.Embed:
        self._update_embed_toggle_button()
        if self.trigger_word:
            dashboard_title = f"📝 Trigger Embed Dashboard"
            dashboard_description = f"Customize the message and embed sent when {self.trigger_word} is used."
        elif self.traffic_event:
            event_labels = {
                'join': 'Member Join',
                'leave': 'Member Leave',
                'boost': 'Server Boost',
            }
            dashboard_title = f"📋 {event_labels.get(self.traffic_event, self.traffic_event.title())} Embed Dashboard"
            dashboard_description = "Use the buttons below to customize this traffic embed layout."
        elif self.level_up:
            dashboard_title = "🏆 Level-Up Embed Dashboard"
            dashboard_description = "Use the buttons below to customize level-up notifications."
        elif self.ticket_open:
            dashboard_title = "🎫 Ticket Open Message Dashboard"
            dashboard_description = "Customize the message sent when a new ticket channel is created."
        else:
            dashboard_title = "👋 Welcome Message Dashboard"
            dashboard_description = "Use the buttons below to customize the welcome message layout."

        emb = discord.Embed(
            title=dashboard_title,
            description=dashboard_description,
            color=discord.Color(await self.current_embed_color_value())
        )
        
        if self.trigger_word:
            emb.add_field(name="Trigger Word", value=f"`{self.trigger_word}`", inline=False)
        elif self.ticket_open:
            emb.add_field(name="Target", value="Sent into every newly created ticket channel", inline=False)
        else:
            ch_id = self.settings.get('channel_id')
            ch_text = f"<#{ch_id}>" if ch_id else "❌ Not Set"
            emb.add_field(name="Target Channel", value=ch_text, inline=False)

        color_value = await self.current_embed_color_value()
        color_hex = f"#{color_value:06X}"
        color_info = f"{color_hex} ({color_value})"
        if self.trigger_word:
            if isinstance(self.settings.get('embed_color') if self.settings else None, int):
                color_info += "\nMode: Custom per-trigger"
            else:
                color_info += "\nMode: Trigger default"
        else:
            embed_key = self.color_embed_key()
            if embed_key:
                override = await db.get_embed_color_override(self.orig_interaction.guild.id, embed_key)
                if override is None:
                    color_info += "\nMode: Fallback color"
                else:
                    color_info += "\nMode: Custom override"
        emb.add_field(name="Current Embed Color", value=color_info, inline=False)
        emb.add_field(name="Embed State", value=("Enabled" if self._embed_enabled() else "Disabled (content-only mode)"), inline=False)
        
        vars_info = (
            "`{user}` - Mention the user\n"
            "`{user.name}` - User's name\n"
            "`{user.avatar}` - User's avatar URL\n"
            "`{server}` - Server name\n"
            "`{server.icon}` - Server icon URL\n"
            "`{server.avatar}` - Alias of server icon URL\n"
            "`{member_count}` - Human members only\n"
            "`{member_count_ext}` - Human members with ordinal suffix (31st, 22nd, 13th)\n"
            "`{time}` - Discord-localized time when the message is sent"
        )
        if self.level_up:
            vars_info += (
                "\n`{level}` - New level number\n"
                "`{levels_gained}` - Number of levels gained at once\n"
                "`{current_xp}` - Current total XP\n"
                "`{next_level_xp}` - XP required for the next level\n"
                "`{role_unlocked}` - Mention of the unlocked role (if any)"
            )
        if self.ticket_open:
            vars_info += (
                "\n`{ticket_id}` - Numeric ticket ID\n"
                "`{support_role}` - Mention of configured support role\n"
                "`{ticket_channel}` - Mention of the newly created ticket channel"
            )
        emb.add_field(name="Available Variables", value=vars_info, inline=False)
        return emb

    async def refresh(self, interaction: commands.Context):
        await self.fetch_state()
        self._update_embed_toggle_button()
        try:
            await interaction.response.edit_message(embed=await self._build_editor_embed(), view=self)
        except discord.InteractionResponded:
            await interaction.message.edit(embed=await self._build_editor_embed(), view=self)
            
        if self.preview_message:
            content, preview_embed = await self._build_preview(interaction, preview_mode=True)
            try:
                await self.preview_message.edit(content=content or "**Live Preview:**", embed=preview_embed)
            except Exception:
                pass

    @discord.ui.button(label="Set Target Channel", style=discord.ButtonStyle.primary, row=0)
    async def btn_channel(self, interaction: commands.Context, btn: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(WelcomeChannelSelect(self))
        prompt = "Select the welcome channel:"
        if self.traffic_event:
            prompt = "Select the traffic channel:"
        elif self.level_up:
            prompt = "Select the level-up channel:"
        elif self.ticket_open:
            prompt = "Ticket open messages are sent in newly created ticket channels."
        await _safe_send(interaction, prompt, view=view, ephemeral=True)

    @discord.ui.button(label="Edit Main Text", style=discord.ButtonStyle.secondary, row=1)
    async def btn_text(self, interaction: commands.Context, btn: discord.ui.Button):
        await interaction.response.send_modal(MainTextModal(self))

    @discord.ui.button(label="Edit Images", style=discord.ButtonStyle.secondary, row=1)
    async def btn_images(self, interaction: commands.Context, btn: discord.ui.Button):
        await interaction.response.send_modal(ImagesModal(self))

    @discord.ui.button(label="Edit Author & Footer", style=discord.ButtonStyle.secondary, row=1)
    async def btn_author_footer(self, interaction: commands.Context, btn: discord.ui.Button):
        await interaction.response.send_modal(AuthorFooterModal(self))

    @discord.ui.button(label="🧩 Edit Fields", style=discord.ButtonStyle.secondary, row=2)
    async def btn_fields(self, interaction: commands.Context, btn: discord.ui.Button):
        async def on_change(fields: list[dict]):
            await self.update_settings(embed_fields=fields)
            self.settings['embed_fields'] = fields
            await self.refresh_preview_message(interaction)

        field_view = EmbedFieldEditorView(self.settings.get('embed_fields', []), on_change)
        await interaction.response.send_message(
            embed=field_view._summary(),
            view=field_view,
            ephemeral=True,
        )

    @discord.ui.button(label="Set Color", style=discord.ButtonStyle.secondary, row=0)
    async def btn_color(self, interaction: commands.Context, btn: discord.ui.Button):
        current_color = await self.current_embed_color_value()
        await interaction.response.send_modal(TriggerColorModal(self, current_color=current_color))

    @discord.ui.button(label="✅ Embed Enabled", style=discord.ButtonStyle.success, row=2)
    async def btn_toggle_embed(self, interaction: commands.Context, btn: discord.ui.Button):
        enabled = not self._embed_enabled()
        await self.update_settings(embed_enabled=enabled)
        self.settings['embed_enabled'] = enabled
        self._update_embed_toggle_button()
        await self.refresh(interaction)

    @discord.ui.button(label="Clear Entire Message", style=discord.ButtonStyle.danger, row=2)
    async def btn_clear(self, interaction: commands.Context, btn: discord.ui.Button):
        if self.trigger_word:
            await db.delete_trigger_embed(interaction.guild.id, self.trigger_word)
        elif self.traffic_event:
            await db.reset_traffic_embed_config(interaction.guild.id, self.traffic_event)
            await db.reset_embed_color(interaction.guild.id, f"traffic_{self.traffic_event}")
        elif self.level_up:
            await db.reset_level_up_embed_config(interaction.guild.id)
            await db.reset_embed_color(interaction.guild.id, "level_up_notification")
        elif self.ticket_open:
            await db.reset_ticket_open_message_config(interaction.guild.id)
            await db.reset_embed_color(interaction.guild.id, "ticket_open_message")
        else:
            await db.remove_welcome_message(interaction.guild.id)
            await db.reset_embed_color(interaction.guild.id, "welcome_message")
        await self.fetch_state()
        await self.refresh(interaction)

    async def refresh_preview_message(self, interaction: commands.Context):
        if not self.preview_message:
            return
        content, preview_embed = await self._build_preview(interaction, preview_mode=True)
        await self.preview_message.edit(
            content=content or "**Live Preview:**",
            embed=preview_embed,
        )

class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="welcome",
        description="Configure the welcome message for new members"
    )
    async def welcome_group(self, ctx: commands.Context):
        pass

    @welcome_group.command(name="dashboard", description="Open the Welcome Message Editor Dashboard")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcome_dashboard(self, ctx: commands.Context):
        editor = WelcomeDashboardView(self, ctx)
        await editor.fetch_state()
        await ctx.send(embed=await editor._build_editor_embed(), view=editor, ephemeral=True)
        
        content, preview_embed = await editor._build_preview(ctx, preview_mode=True)
        editor.preview_message = await ctx.send(content=content or "**Live Preview:**", embed=preview_embed, ephemeral=True)

    @welcome_group.command(name="disable", description="Disable the welcome message")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcome_disable(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return

        settings = await db.get_welcome_message(ctx.guild.id)
        if not settings:
            await ctx.send("ℹ️ No welcome message is currently configured.", ephemeral=True)
            return

        await db.remove_welcome_message(ctx.guild.id)
        await ctx.send("✅ Welcome message has been disabled.", ephemeral=True)
        logger.info(f"Welcome message disabled for guild {ctx.guild.id}")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))

