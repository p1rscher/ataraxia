import discord
from discord.ext import commands
from discord import app_commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

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
            placeholder="Select a channel to post the welcome message...",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1
        )
        
    async def callback(self, interaction: commands.Context):
        ch = self.values[0]
        await db.update_welcome_message(interaction.guild.id, channel_id=ch.id)
        await self.view_obj.refresh(interaction)


class MainTextModal(discord.ui.Modal, title="Edit Welcome Text"):
    p_content = discord.ui.TextInput(label="Ping / Outside Text", required=False, max_length=2000, placeholder="Welcome {user} to the server!")
    p_title = discord.ui.TextInput(label="Embed Title", required=False, max_length=256)
    p_desc = discord.ui.TextInput(label="Embed Description", style=discord.TextStyle.paragraph, required=False, max_length=4000)

    def __init__(self, view_obj):
        super().__init__()
        self.view_obj = view_obj
        p = view_obj.settings
        self.p_content.default = p.get('message') or ""
        self.p_title.default = p.get('embed_title') or ""
        self.p_desc.default = p.get('embed_description') or ""

    async def on_submit(self, interaction: commands.Context):
        await db.update_welcome_message(
            interaction.guild.id,
            message=str(self.p_content).strip() or None,
            embed_title=str(self.p_title).strip() or None,
            embed_description=str(self.p_desc).strip() or None
        )
        await self.view_obj.refresh(interaction)

class ImagesModal(discord.ui.Modal, title="Edit Welcome Images"):
    p_thumb = discord.ui.TextInput(label="Thumbnail URL", required=False, placeholder="https://... or {user.avatar}")
    p_img = discord.ui.TextInput(label="Large Image URL", required=False, placeholder="https://...")

    def __init__(self, view_obj):
        super().__init__()
        self.view_obj = view_obj
        p = view_obj.settings
        self.p_thumb.default = p.get('embed_thumbnail') or ""
        self.p_img.default = p.get('embed_image') or ""

    async def on_submit(self, interaction: commands.Context):
        await db.update_welcome_message(
            interaction.guild.id,
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
        super().__init__()
        self.view_obj = view_obj
        p = view_obj.settings
        self.p_aname.default = p.get('embed_author_name') or ""
        self.p_aicon.default = p.get('embed_author_icon') or ""
        self.p_ftext.default = p.get('embed_footer_text') or ""
        self.p_ficon.default = p.get('embed_footer_icon') or ""

    async def on_submit(self, interaction: commands.Context):
        await db.update_welcome_message(
            interaction.guild.id,
            embed_author_name=str(self.p_aname).strip() or None,
            embed_author_icon=str(self.p_aicon).strip() or None,
            embed_footer_text=str(self.p_ftext).strip() or None,
            embed_footer_icon=str(self.p_ficon).strip() or None
        )
        await self.view_obj.refresh(interaction)

class WelcomeDashboardView(discord.ui.View):
    def __init__(self, cog, interaction):
        super().__init__(timeout=600)
        self.cog = cog
        self.orig_interaction = interaction
        self.settings = None
        self.preview_message = None

    async def fetch_state(self):
        self.settings = await db.get_or_create_welcome_message(self.orig_interaction.guild.id)

    async def _build_preview(self, interaction: commands.Context, preview_mode=False):
        welcome = self.settings
        member = getattr(interaction, 'user', getattr(interaction, 'author', None))
        guild = interaction.guild
        
        def process_text(txt):
            if not txt: return ""
            if not preview_mode: return txt
            txt = txt.replace("{user}", member.mention)
            txt = txt.replace("{user.name}", str(member))
            txt = txt.replace("{user.avatar}", member.display_avatar.url)
            txt = txt.replace("{server}", guild.name)
            txt = txt.replace("{server.icon}", guild.icon.url if guild.icon else "")
            txt = txt.replace("{member_count}", str(guild.member_count))
            return txt

        content = process_text(welcome.get('message'))
        
        embed = None
        if any(welcome.get(k) for k in ['embed_title', 'embed_description', 'embed_image', 'embed_thumbnail', 'embed_author_name', 'embed_footer_text']):
            embed = discord.Embed(
                title=process_text(welcome.get('embed_title')) or None,
                description=process_text(welcome.get('embed_description')) or None,
                color=await get_guild_color(guild.id, 'color_welcome')
            )
            
            if welcome.get('embed_author_name'):
                icon = process_text(welcome.get('embed_author_icon')) or None
                embed.set_author(name=process_text(welcome.get('embed_author_name')), icon_url=icon)
                
            if welcome.get('embed_thumbnail'):
                embed.set_thumbnail(url=process_text(welcome.get('embed_thumbnail')))
                
            if welcome.get('embed_image'):
                embed.set_image(url=process_text(welcome.get('embed_image')))
                
            if welcome.get('embed_footer_text'):
                icon = process_text(welcome.get('embed_footer_icon')) or None
                embed.set_footer(text=process_text(welcome.get('embed_footer_text')), icon_url=icon)
                
        return content, embed

    async def _build_editor_embed(self) -> discord.Embed:
        emb = discord.Embed(
            title="👋 Welcome Message Dashboard",
            description="Use the buttons below to customize the welcome message layout.",
            color=0x5865F2
        )
        
        ch_id = self.settings.get('channel_id')
        ch_text = f"<#{ch_id}>" if ch_id else "❌ Not Set"
        emb.add_field(name="Target Channel", value=ch_text, inline=False)
        
        vars_info = (
            "`{user}` - Mention the user\n"
            "`{user.name}` - User's name\n"
            "`{user.avatar}` - User's avatar URL\n"
            "`{server}` - Server name\n"
            "`{server.icon}` - Server icon URL\n"
            "`{member_count}` - Total members"
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

    @discord.ui.button(label="Clear Entire Message", style=discord.ButtonStyle.danger, row=2)
    async def btn_clear(self, interaction: commands.Context, btn: discord.ui.Button):
        await db.remove_welcome_message(interaction.guild.id)
        await self.fetch_state()
        await self.refresh(interaction)

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

