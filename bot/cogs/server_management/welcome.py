import discord
from discord.ext import commands
from discord import app_commands
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
        if view_obj.traffic_event:
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

class WelcomeDashboardView(discord.ui.View):
    def __init__(
        self,
        cog,
        interaction,
        traffic_event: str | None = None,
        trigger_word: str | None = None,
    ):
        super().__init__(timeout=600)
        self.cog = cog
        self.orig_interaction = interaction
        self.traffic_event = traffic_event
        self.trigger_word = trigger_word
        self.settings = None
        self.preview_message = None

        if trigger_word:
            self.btn_channel.label = "Trigger Word"
            self.btn_channel.disabled = True
            self.btn_text.label = "Edit Trigger Text"
            self.btn_images.label = "Edit Trigger Images"
            self.btn_author_footer.label = "Edit Trigger Author & Footer"
            self.btn_fields.label = "Edit Trigger Fields"
            self.btn_clear.label = "Reset Trigger Embed"
        elif traffic_event:
            self.btn_channel.label = "Set Traffic Channel"
            self.btn_text.label = "Edit Traffic Text"
            self.btn_images.label = "Edit Traffic Images"
            self.btn_author_footer.label = "Edit Traffic Author & Footer"
            self.btn_fields.label = "Edit Traffic Fields"
            self.btn_clear.label = "Reset Traffic Embed"

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
        return "Welcome"

    def modal_title(self, action: str) -> str:
        if self.trigger_word or self.traffic_event:
            return f"{self.context_label()} • {action}"
        return f"{action} Welcome"

    async def embed_color(self) -> discord.Color:
        """Return this dashboard's color without borrowing Welcome's color."""
        guild_id = self.orig_interaction.guild.id
        if self.traffic_event:
            return await get_embed_color(
                guild_id,
                f"traffic_{self.traffic_event}",
                "color_primary",
            )
        return await get_embed_color(guild_id, "welcome_message", "color_welcome")

    async def fetch_state(self):
        guild_id = self.orig_interaction.guild.id
        if self.trigger_word:
            record = await db.get_trigger_embed(guild_id, self.trigger_word) or {}
            embed_data = _json_object(record.get('embed_data'))
            self.settings = {
                'channel_id': None,
                'message': record.get('content'),
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
                    'embed_title': 'Triggered Embed',
                    'embed_description': 'Customize this triggered message.',
                    'embed_color': 0x5865F2,
                })
            return

        if not self.traffic_event:
            self.settings = await db.get_or_create_welcome_message(guild_id)
            self.settings['embed_fields'] = normalize_embed_fields(self.settings.get('embed_fields'))
            return

        config = await db.get_traffic_embed_config(guild_id, self.traffic_event) or {}
        channel_id = await db.get_traffic_event_channel_id(guild_id, self.traffic_event)
        if channel_id is None:
            channel_id = await db.get_traffic_log_channel_id(guild_id)

        self.settings = {
            'channel_id': channel_id,
            'message': None,
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
            self.settings['embed_thumbnail'] = '{user.avatar}'
            self.settings['embed_footer_text'] = '{server} • {member_count} members'
            self.settings['embed_footer_icon'] = '{server.icon}'

    async def set_target_channel(self, channel_id: int):
        guild_id = self.orig_interaction.guild.id
        if self.traffic_event:
            await db.set_traffic_event_channel(guild_id, self.traffic_event, channel_id)
        else:
            await db.update_welcome_message(guild_id, channel_id=channel_id)

    async def update_settings(self, **values):
        guild_id = self.orig_interaction.guild.id
        if self.trigger_word:
            self.settings.update(values)
            embed_data = dict(self.settings.get('_embed_data') or {})
            embed_data['title'] = self.settings.get('embed_title') or None
            embed_data['description'] = self.settings.get('embed_description') or None
            embed_data['fields'] = self.settings.get('embed_fields', [])
            embed_data['color'] = self.settings.get('embed_color') or embed_data.get('color')
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

        if not self.traffic_event:
            await db.update_welcome_message(guild_id, **values)
            return

        mapping = {
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
        
        embed = None
        if any(welcome.get(k) for k in ['embed_title', 'embed_description', 'embed_image', 'embed_thumbnail', 'embed_author_name', 'embed_footer_text', 'embed_footer_icon', 'embed_fields']):
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
                    if self.trigger_word and welcome.get('embed_color')
                    else await self.embed_color()
                ),
                timestamp=preview_time if preview_mode and has_time_placeholder(*embed_values) else None,
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
        else:
            dashboard_title = "👋 Welcome Message Dashboard"
            dashboard_description = "Use the buttons below to customize the welcome message layout."

        emb = discord.Embed(
            title=dashboard_title,
            description=dashboard_description,
            color=await self.embed_color()
        )
        
        if self.trigger_word:
            emb.add_field(name="Trigger Word", value=f"`{self.trigger_word}`", inline=False)
        else:
            ch_id = self.settings.get('channel_id')
            ch_text = f"<#{ch_id}>" if ch_id else "❌ Not Set"
            emb.add_field(name="Target Channel", value=ch_text, inline=False)
        
        vars_info = (
            "`{user}` - Mention the user\n"
            "`{user.name}` - User's name\n"
            "`{user.avatar}` - User's avatar URL\n"
            "`{server}` - Server name\n"
            "`{server.icon}` - Server icon URL\n"
            "`{member_count}` - Human members only\n"
            "`{member_count_ext}` - Human members with ordinal suffix (31st, 22nd, 13th)\n"
            "`{time}` - Discord-localized time when the message is sent"
        )
        emb.add_field(name="Available Variables", value=vars_info, inline=False)
        return emb

    async def refresh(self, interaction: commands.Context):
        await self.fetch_state()
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
        await _safe_send(interaction, "Select the welcome channel:", view=view, ephemeral=True)

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

    @discord.ui.button(label="Clear Entire Message", style=discord.ButtonStyle.danger, row=2)
    async def btn_clear(self, interaction: commands.Context, btn: discord.ui.Button):
        if self.trigger_word:
            await db.delete_trigger_embed(interaction.guild.id, self.trigger_word)
        elif self.traffic_event:
            await db.reset_traffic_embed_config(interaction.guild.id, self.traffic_event)
        else:
            await db.remove_welcome_message(interaction.guild.id)
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

