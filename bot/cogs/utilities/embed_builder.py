import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

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
        
        await interaction.response.edit_message(embed=embed, view=self.builder_view)

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
        elif f_t:
            embed.set_footer(text=f_t, icon_url=self.footer_icon.value if self.footer_icon.value else None)
            
        await interaction.response.edit_message(embed=embed, view=self.builder_view)

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
            
        await interaction.response.edit_message(embed=embed, view=self.builder_view)


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
        await interaction.response.edit_message(embed=embed, view=self.builder_view)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, target_channel: discord.TextChannel | discord.Thread, 
                 target_message: Optional[discord.Message] = None,
                 initial_embed: Optional[discord.Embed] = None):
        super().__init__(timeout=900)  # 15 minutes timeout
        self.target_channel = target_channel
        self.target_message = target_message
        self.preview_embed = initial_embed or discord.Embed(title="New Embed")
        
        # Adjust send button label depending on create/edit
        if target_message:
            self.send_button.label = "💾 Save Edits"
            self.send_button.style = discord.ButtonStyle.green

    @discord.ui.button(label="📝 Basic Info", style=discord.ButtonStyle.secondary, row=0)
    async def btn_basic(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(BasicInfoModal(self))

    @discord.ui.button(label="👤 Author & Footer", style=discord.ButtonStyle.secondary, row=0)
    async def btn_author(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(AuthorFooterModal(self))

    @discord.ui.button(label="🖼️ Images", style=discord.ButtonStyle.secondary, row=0)
    async def btn_images(self, interaction: commands.Context, button: discord.ui.Button):
        await interaction.response.send_modal(ImagesModal(self))

    @discord.ui.button(label="➕ Add Field", style=discord.ButtonStyle.primary, row=1)
    async def btn_add_field(self, interaction: commands.Context, button: discord.ui.Button):
        if len(self.preview_embed.fields) >= 25:
            await interaction.send("Embeds can have a maximum of 25 fields.", ephemeral=True)
            return
        await interaction.response.send_modal(AddFieldModal(self))

    @discord.ui.button(label="🗑️ Clear Fields", style=discord.ButtonStyle.danger, row=1)
    async def btn_clear_fields(self, interaction: commands.Context, button: discord.ui.Button):
        self.preview_embed.clear_fields()
        await interaction.response.edit_message(embed=self.preview_embed, view=self)

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

            if self.target_message:
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
            color=discord.Color.blurple()
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
            initial_embed = discord.Embed(title="New Embed")
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
