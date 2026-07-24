import discord
import inspect
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from typing import Awaitable, Callable, Optional
from utils.embeds import get_guild_color, set_embed_footer

logger = logging.getLogger(__name__)

class BasicInfoModal(discord.ui.Modal, title='Edit Basic Info'):
    embed_title = discord.ui.TextInput(
        label='Title',
        style=discord.TextStyle.short,
        placeholder='Embed Title',
        required=False,
        max_length=256
    )
    embed_desc = discord.ui.TextInput(
        label='Description',
        style=discord.TextStyle.paragraph,
        placeholder='Embed Description',
        required=False,
        max_length=4000
    )
    embed_color = discord.ui.TextInput(
        label='Hex Color (e.g. #FF0000)',
        style=discord.TextStyle.short,
        placeholder='#FFFFFF',
        required=False,
        max_length=7
    )

    def __init__(self, view: 'EmbedBuilderView'):
        super().__init__()
        self.builder_view = view
        # Pre-fill
        if view.preview_embed.title:
            self.embed_title.default = view.preview_embed.title
        if view.preview_embed.description:
            self.embed_desc.default = view.preview_embed.description
        if view.preview_embed.color:
            self.embed_color.default = f"#{view.preview_embed.color.value:06x}"

    async def on_submit(self, interaction: commands.Context):
        embed = self.builder_view.preview_embed
        embed.title = self.embed_title.value if self.embed_title.value else None
        embed.description = self.embed_desc.value if self.embed_desc.value else None
        if self.embed_color.value:
            try:
                hx = self.embed_color.value.lstrip('#')
                embed.color = discord.Color(int(hx, 16))
            except ValueError:
                pass # invalid color
        else:
            embed.color = None
        
        await self.builder_view.edit_preview(interaction)

class AuthorFooterModal(discord.ui.Modal, title='Edit Author & Footer'):
    author_name = discord.ui.TextInput(
        label='Author Name (° to remove)', required=False, max_length=256
    )
    author_icon = discord.ui.TextInput(
        label='Author Icon URL', required=False
    )
    footer_text = discord.ui.TextInput(
        label='Footer Text (° to remove)', required=False, max_length=2048, style=discord.TextStyle.paragraph
    )
    footer_icon = discord.ui.TextInput(
        label='Footer Icon URL', required=False
    )

    def __init__(self, view: 'EmbedBuilderView'):
        super().__init__()
        self.builder_view = view
        em = view.preview_embed
        if em.author:
            self.author_name.default = em.author.name
            if em.author.icon_url:
                self.author_icon.default = em.author.icon_url
        if em.footer:
            self.footer_text.default = em.footer.text
            if em.footer.icon_url:
                self.footer_icon.default = em.footer.icon_url

    async def on_submit(self, interaction: commands.Context):
        embed = self.builder_view.preview_embed
        
        a_n = self.author_name.value
        if a_n == '°':
            embed.remove_author()
        elif a_n:
            embed.set_author(name=a_n, icon_url=self.author_icon.value if self.author_icon.value else None)
            
        f_t = self.footer_text.value
        if f_t == '°':
            embed.remove_footer()
        elif f_t or self.footer_icon.value:
            set_embed_footer(
                embed,
                text=f_t or None,
                icon_url=self.footer_icon.value or None,
            )
            
        await self.builder_view.edit_preview(interaction)

class ImagesModal(discord.ui.Modal, title='Edit Images'):
    thumbnail_url = discord.ui.TextInput(
        label='Thumbnail URL (° to remove)', required=False
    )
    image_url = discord.ui.TextInput(
        label='Main Image URL (° to remove)', required=False
    )

    def __init__(self, view: 'EmbedBuilderView'):
        super().__init__()
        self.builder_view = view
        em = view.preview_embed
        if em.thumbnail and em.thumbnail.url:
            self.thumbnail_url.default = em.thumbnail.url
        if em.image and em.image.url:
            self.image_url.default = em.image.url

    async def on_submit(self, interaction: commands.Context):
        embed = self.builder_view.preview_embed
        
        t_u = self.thumbnail_url.value
        if t_u == '°':
            embed.set_thumbnail(url=None)
        elif t_u:
            embed.set_thumbnail(url=t_u)
            
        i_u = self.image_url.value
        if i_u == '°':
            embed.set_image(url=None)
        elif i_u:
            embed.set_image(url=i_u)
            
        await self.builder_view.edit_preview(interaction)


class AddFieldModal(discord.ui.Modal, title='Add Field'):
    field_name = discord.ui.TextInput(
        label='Field Name', max_length=256
    )
    field_value = discord.ui.TextInput(
        label='Field Value', style=discord.TextStyle.paragraph, max_length=1024
    )
    inline = discord.ui.TextInput(
        label='Inline? (True/False)', default='False', max_length=5
    )

    def __init__(self, view: 'EmbedBuilderView'):
        super().__init__()
        self.builder_view = view

    async def on_submit(self, interaction: commands.Context):
        embed = self.builder_view.preview_embed
        inline_val = self.inline.value.lower() == 'true'
        embed.add_field(name=self.field_name.value, value=self.field_value.value, inline=inline_val)
        await self.builder_view.edit_preview(interaction)


class FieldValueModal(discord.ui.Modal):
    field_name = discord.ui.TextInput(label='Field Name', max_length=256)
    field_value = discord.ui.TextInput(label='Field Value', style=discord.TextStyle.paragraph, max_length=1024)
    inline = discord.ui.TextInput(label='Inline? (True/False)', default='False', max_length=5)

    def __init__(self, field_view: 'EmbedFieldEditorView', index: Optional[int] = None):
        super().__init__(title='Edit Field' if index is not None else 'Add Field')
        self.field_view = field_view
        self.index = index
        if index is not None:
            field = field_view.fields[index]
            self.field_name.default = field.get('name', '')
            self.field_value.default = field.get('value', '')
            self.inline.default = str(bool(field.get('inline', False)))

    async def on_submit(self, interaction: commands.Context):
        field = {
            'name': str(self.field_name).strip(),
            'value': str(self.field_value),
            'inline': str(self.inline).strip().lower() in {'true', 'yes', '1'},
        }
        if not field['name'] or not field['value']:
            await interaction.response.send_message('❌ Field name and value are required.', ephemeral=True)
            return
        if self.index is None:
            self.field_view.fields.append(field)
        else:
            self.field_view.fields[self.index] = field
        await self.field_view.commit(interaction)


class EmbedFieldEditorView(discord.ui.View):
    """Reusable field editor for every configurable embed in the bot."""

    def __init__(self, fields: list[dict], on_change: Callable[[list[dict]], Awaitable[None]]):
        super().__init__(timeout=900)
        self.fields = [dict(field) for field in fields if isinstance(field, dict)]
        self.on_change = on_change
        self.selected_index: Optional[int] = None
        self.field_select = discord.ui.Select(
            placeholder='Select a field to edit or remove...',
            min_values=1,
            max_values=1,
            options=self._options(),
            disabled=not self.fields,
            row=0,
        )
        self.field_select.callback = self._select_field
        self.add_item(self.field_select)

    def _options(self):
        if not self.fields:
            return [discord.SelectOption(label='No fields configured', value='none')]
        return [
            discord.SelectOption(
                label=f"{index + 1}. {field.get('name', 'Unnamed')}"[:100],
                value=str(index),
                description=str(field.get('value', ''))[:100],
            )
            for index, field in enumerate(self.fields[:25])
        ]

    def _summary(self) -> discord.Embed:
        embed = discord.Embed(title='🧩 Embed Fields', description='Manage the fields of this embed.')
        if not self.fields:
            embed.description = 'No fields configured yet.'
        for index, field in enumerate(self.fields[:25], start=1):
            embed.add_field(
                name=f"{field.get('name', 'Unnamed')}",
                value=f"{field.get('value', '-')[:1024]}\nInline: {'Yes' if field.get('inline') else 'No'}",
                inline=False,
            )
        return embed

    async def _select_field(self, interaction: commands.Context):
        value = self.field_select.values[0]
        if value == 'none':
            await interaction.response.defer()
            return
        self.selected_index = int(value)
        await interaction.response.edit_message(
            content=f"Selected field **{self.selected_index + 1}**.",
            embed=self._summary(),
            view=self,
        )

    async def commit(self, interaction: commands.Context):
        if len(self.fields) > 25:
            self.fields = self.fields[:25]
        await self.on_change(self.fields)
        self.field_select.options = self._options()
        self.field_select.disabled = not self.fields
        self.selected_index = None
        await interaction.response.edit_message(content=None, embed=self._summary(), view=self)

    @discord.ui.button(label='➕ Add Field', style=discord.ButtonStyle.success, row=1)
    async def add_field(self, interaction: commands.Context, button: discord.ui.Button):
        if len(self.fields) >= 25:
            await interaction.response.send_message('❌ An embed can contain at most 25 fields.', ephemeral=True)
            return
        await interaction.response.send_modal(FieldValueModal(self))

    @discord.ui.button(label='✏️ Edit Selected', style=discord.ButtonStyle.primary, row=1)
    async def edit_field(self, interaction: commands.Context, button: discord.ui.Button):
        if self.selected_index is None or self.selected_index >= len(self.fields):
            await interaction.response.send_message('❌ Select a field first.', ephemeral=True)
            return
        await interaction.response.send_modal(FieldValueModal(self, self.selected_index))

    @discord.ui.button(label='🗑️ Remove Selected', style=discord.ButtonStyle.danger, row=1)
    async def remove_field(self, interaction: commands.Context, button: discord.ui.Button):
        if self.selected_index is None or self.selected_index >= len(self.fields):
            await interaction.response.send_message('❌ Select a field first.', ephemeral=True)
            return
        self.fields.pop(self.selected_index)
        await self.commit(interaction)

    @discord.ui.button(label='🧹 Clear All', style=discord.ButtonStyle.secondary, row=2)
    async def clear_fields(self, interaction: commands.Context, button: discord.ui.Button):
        self.fields.clear()
        await self.commit(interaction)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, target_channel: discord.TextChannel | discord.Thread, 
                 target_message: Optional[discord.Message] = None,
                 initial_embed: Optional[discord.Embed] = None,
                 save_callback: Optional[Callable[[discord.Embed], Awaitable[None]]] = None,
                 preview_renderer: Optional[Callable[[discord.Embed], Awaitable[discord.Embed] | discord.Embed]] = None):
        super().__init__(timeout=900)  # 15 minutes timeout
        self.target_channel = target_channel
        self.target_message = target_message
        self.save_callback = save_callback
        self.preview_renderer = preview_renderer
        self.preview_embed = initial_embed or discord.Embed(title="New Embed")
        
        # Adjust send button label depending on create/edit
        if target_message:
            self.send_button.label = "💾 Save Edits"
            self.send_button.style = discord.ButtonStyle.green
        elif save_callback:
            self.send_button.label = "💾 Save Configuration"
            self.send_button.style = discord.ButtonStyle.green
        if self.preview_embed.timestamp:
            self.btn_timestamp.label = "🕒 Remove Timestamp"

    async def get_preview_embed(self) -> discord.Embed:
        """Return a rendered copy while keeping placeholders in the editable embed."""
        preview = discord.Embed.from_dict(self.preview_embed.to_dict())
        if self.preview_renderer:
            rendered = self.preview_renderer(preview)
            if inspect.isawaitable(rendered):
                rendered = await rendered
            preview = rendered
        return preview

    async def edit_preview(self, interaction: commands.Context):
        await interaction.response.edit_message(embed=await self.get_preview_embed(), view=self)

    async def _replace_fields(self, fields: list[dict]):
        self.preview_embed.clear_fields()
        for field in fields[:25]:
            self.preview_embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=bool(field.get('inline', False)),
            )

    @discord.ui.button(label="📝 Basic Info", style=discord.ButtonStyle.secondary, row=0)
    async def btn_basic(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(BasicInfoModal(self))

    @discord.ui.button(label="👤 Author & Footer", style=discord.ButtonStyle.secondary, row=0)
    async def btn_author(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(AuthorFooterModal(self))

    @discord.ui.button(label="🖼️ Images", style=discord.ButtonStyle.secondary, row=0)
    async def btn_images(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(ImagesModal(self))

    @discord.ui.button(label="🧩 Edit Fields", style=discord.ButtonStyle.primary, row=1)
    async def btn_add_field(self, interaction: commands.Context, button: discord.ui.Button):
        fields = self.preview_embed.to_dict().get('fields', [])
        async def on_change(updated_fields: list[dict]):
            await self._replace_fields(updated_fields)
        field_view = EmbedFieldEditorView(fields, on_change)
        await interaction.response.send_message(
            embed=field_view._summary(),
            view=field_view,
            ephemeral=True,
        )

    @discord.ui.button(label="🗑️ Clear Fields", style=discord.ButtonStyle.danger, row=1)
    async def btn_clear_fields(self, interaction: commands.Context, button: discord.ui.Button):
        self.preview_embed.clear_fields()
        await self.edit_preview(interaction)

    @discord.ui.button(label="🕒 Toggle Timestamp", style=discord.ButtonStyle.secondary, row=2)
    async def btn_timestamp(self, interaction: commands.Context, button: discord.ui.Button):
        if self.preview_embed.timestamp:
            self.preview_embed.timestamp = None
            button.label = "🕒 Add Timestamp"
        else:
            self.preview_embed.timestamp = discord.utils.utcnow()
            button.label = "🕒 Remove Timestamp"
        await self.edit_preview(interaction)

    @discord.ui.button(label="✅ Send", style=discord.ButtonStyle.success, row=2)
    async def send_button(self, interaction: commands.Context, button: discord.ui.Button):
        try:
            # Check for totally empty embeds which Discord rejects
            if not any([
                self.preview_embed.title, self.preview_embed.description,
                self.preview_embed.fields, self.preview_embed.image,
                self.preview_embed.thumbnail, self.preview_embed.author,
                self.preview_embed.footer
            ]):
                return await interaction.send("❌ This embed is totally empty, please add a title or description.", ephemeral=True)

            if self.save_callback:
                await self.save_callback(self.preview_embed)
                await interaction.response.edit_message(
                    content="✅ Embed configuration saved successfully!",
                    embed=await self.get_preview_embed(),
                    view=None,
                )
            elif self.target_message:
                await self.target_message.edit(embed=self.preview_embed)
                await interaction.response.edit_message(content="✅ Embed updated successfully!", embed=self.preview_embed, view=None)
            else:
                await self.target_channel.send(embed=self.preview_embed)
                await interaction.response.edit_message(content=f"✅ Embed sent to {self.target_channel.mention}!", embed=self.preview_embed, view=None)
            self.stop()
        except discord.Forbidden:
            await interaction.send("❌ I do not have permissions to send/edit messages in that channel.", ephemeral=True)
        except Exception as e:
            await interaction.send(f"❌ Failed: {e}", ephemeral=True)


class EmbedBuilderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="embed", description="Create and manage embeds")
    async def embed_group(self, ctx: commands.Context):
        pass

    @embed_group.command(name="create", description="Create a new embed via an interactive builder")
    @app_commands.describe(channel="The channel to send the embed to")
    @commands.has_permissions(administrator=True)
    async def embed_create(self, interaction: commands.Context, channel: discord.TextChannel):
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.send(f"❌ I don't have permission to write in {channel.mention}.", ephemeral=True)
            
        initial_embed = discord.Embed(
            title="Your New Embed",
            description="Use the buttons below to build your embed.",
            color=await get_guild_color(interaction.guild.id)
        )
        view = EmbedBuilderView(target_channel=channel, initial_embed=initial_embed)
        await interaction.send(
            "🛠️ **Embed Builder**\n*Preview:*", 
            embed=initial_embed, 
            view=view, 
            ephemeral=True
        )

    @embed_group.command(name="edit", description="Edit an existing bot embed via the builder")
    @app_commands.describe(
        channel="The channel where the message is",
        message_id="The ID of the bot message to edit"
    )
    @commands.has_permissions(administrator=True)
    async def embed_edit(self, interaction: commands.Context, channel: discord.TextChannel, message_id: str):
        try:
            message_id_int = int(message_id)
        except ValueError:
            return await interaction.send("❌ Invalid message ID formatting.", ephemeral=True)
            
        try:
            target_msg = await channel.fetch_message(message_id_int)
        except discord.NotFound:
            return await interaction.send("❌ Message not found in that channel.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.send("❌ I cannot read message history in that channel.", ephemeral=True)
            
        if target_msg.author.id != self.bot.user.id:
            return await interaction.send("❌ I can only edit my own messages.", ephemeral=True)
            
        if not target_msg.embeds:
            initial_embed = discord.Embed(
                title="New Embed",
                color=await get_guild_color(interaction.guild.id)
            )
        else:
            initial_embed = target_msg.embeds[0]
            
        view = EmbedBuilderView(target_channel=channel, target_message=target_msg, initial_embed=initial_embed)
        await interaction.send(
            "🛠️ **Embed Editor**\n*Preview:*", 
            embed=initial_embed, 
            view=view, 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedBuilderCog(bot))
