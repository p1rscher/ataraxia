import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import io
from core import database_pg as db
from utils.embeds import (
    get_embed_color,
    has_time_placeholder,
    normalize_embed_fields,
    process_member_text,
    set_embed_footer,
)
from cogs.utilities.embed_builder import EmbedBuilderView
from cogs.server_management.welcome import WelcomeDashboardView

logger = logging.getLogger(__name__)


async def send_interaction_message(interaction: discord.Interaction, *args, **kwargs):
    if interaction.response.is_done():
        return await interaction.followup.send(*args, **kwargs)
    return await interaction.response.send_message(*args, **kwargs)

async def create_transcript_bytes(channel: discord.TextChannel) -> io.BytesIO:
    transcript = f"Transcript for {channel.name}\n"
    transcript += "=" * 50 + "\n\n"
    
    messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
    
    for msg in messages:
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        author = msg.author.name
        content = msg.clean_content
        transcript += f"[{timestamp}] {author}: {content}\n"
        if msg.attachments:
            for att in msg.attachments:
                transcript += f"[{timestamp}] {author}: [Attachment: {att.url}]\n"
                
    file_bytes = io.BytesIO(transcript.encode('utf-8'))
    file_bytes.seek(0)
    return file_bytes


async def build_ticket_open_payload(
    guild: discord.Guild,
    member: discord.Member,
    ticket_channel: discord.TextChannel,
    ticket_id: int,
    support_role: Optional[discord.Role],
) -> tuple[Optional[str], discord.Embed]:
    config = await db.get_ticket_open_message_config(guild.id) or {}
    event_time = discord.utils.utcnow()
    extra_values = {
        "event": "ticket_open",
        "ticket_id": str(ticket_id),
        "support_role": support_role.mention if support_role else "",
        "ticket_channel": ticket_channel.mention,
    }

    def render(value: Optional[str], *, footer: bool = False) -> Optional[str]:
        if not value:
            return None
        return process_member_text(
            value,
            member,
            event_time=event_time,
            time_value="" if footer else None,
            extra_values=extra_values,
        ) or None

    default_title = "Ticket #{ticket_id}"
    default_description = "Welcome {user}!\n\nPlease describe your issue and our support team will be with you shortly."
    raw_fields = normalize_embed_fields(config.get("fields"))

    title = config.get("title") if config else default_title
    description = config.get("description") if config else default_description
    embed_values = [
        title,
        description,
        config.get("author_name"),
        config.get("author_icon"),
        config.get("thumbnail"),
        config.get("image"),
        config.get("footer_text"),
        config.get("footer_icon"),
    ]

    embed = discord.Embed(
        title=render(title),
        description=render(description),
        color=await get_embed_color(guild.id, "ticket_open_message", "color_ticket"),
        timestamp=(
            event_time
            if bool(config.get("timestamp_enabled", False)) or has_time_placeholder(*embed_values)
            else None
        ),
    )

    if config.get("author_name"):
        embed.set_author(
            name=render(config.get("author_name")) or " ",
            icon_url=render(config.get("author_icon")),
        )
    if config.get("thumbnail"):
        embed.set_thumbnail(url=render(config.get("thumbnail")))
    if config.get("image"):
        embed.set_image(url=render(config.get("image")))
    set_embed_footer(
        embed,
        text=render(config.get("footer_text"), footer=True),
        icon_url=render(config.get("footer_icon")),
    )

    for field in raw_fields[:25]:
        if not isinstance(field, dict) or not field.get("name"):
            continue
        embed.add_field(
            name=render(field.get("name")) or "Field",
            value=(render(field.get("value")) or "-")[:1024],
            inline=bool(field.get("inline", False)),
        )

    content = render(config.get("content")) if config else None
    return content, embed

class TicketActiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Permission check
        settings = await db.get_ticket_settings(interaction.guild.id)
        member = interaction.user
        is_staff = member.guild_permissions.administrator
        
        if settings:
            support_role_id = settings.get('support_role_id')
            closer_role_id = settings.get('closer_role_id')
            
            if not is_staff and support_role_id:
                if any(r.id == support_role_id for r in member.roles):
                    is_staff = True
            if not is_staff and closer_role_id:
                if any(r.id == closer_role_id for r in member.roles):
                    is_staff = True
                    
        if not is_staff:
            return await send_interaction_message(interaction, "❌ Only support staff or administrators can close tickets.", ephemeral=True)

        await send_interaction_message(interaction, "Closing ticket and generating transcript... please wait.", ephemeral=True)
        
        # 2. Check if it is a valid ticket
        ticket_data = await db.close_ticket_by_channel(interaction.channel_id)
        if not ticket_data:
            return await interaction.edit_original_response(content="❌ This channel is not marked as an active ticket in the database. You can manually delete it.")

        user_id = ticket_data['user_id']
        ticket_user = interaction.guild.get_member(user_id)
        
        try:
            # Generate Transcript Bytes
            buffer = None
            try:
                buffer = await create_transcript_bytes(interaction.channel)
            except Exception as e:
                logger.error(f"Failed to generate transcript: {e}")
                
            # Log it
            log_channel_id = await db.get_ticket_log_channel_id(interaction.guild.id)
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🎫 Ticket Closed",
                        description=f"Ticket created by <@{user_id}> was closed by {member.mention}.",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Channel Name", value=interaction.channel.name)
                    
                    kwargs = {"embed": embed}
                    if buffer:
                        buffer.seek(0)
                        kwargs["file"] = discord.File(buffer, filename=f"transcript-{interaction.channel.name}.txt")
                    
                    try:
                        await log_channel.send(**kwargs)
                    except Exception as e:
                        logger.error(f"Failed to send ticket log: {e}")

            # Also send transcript to user if possible
            if ticket_user and buffer:
                buffer.seek(0)
                try:
                    await ticket_user.send(
                        content=f"Your ticket in **{interaction.guild.name}** has been closed. Here is your transcript:", 
                        file=discord.File(buffer, filename=f"transcript-{interaction.channel.name}.txt")
                    )
                except discord.Forbidden:
                    pass
                except Exception as e:
                    logger.error(f"Failed to DM transcript: {e}")
        finally:
            # 3. Always try to delete the channel no matter what happened during transcripting/DMs
            try:
                await interaction.channel.delete(reason=f"Ticket closed by {member.name}")
            except discord.Forbidden:
                await send_interaction_message(interaction, "❌ I lack permissions to delete this channel. Please delete it manually.", ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to delete ticket channel: {e}")
                await send_interaction_message(interaction, f"❌ Failed to delete channel: {e}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_create_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await db.get_ticket_settings(interaction.guild.id)
        if not settings or not settings.get('category_id'):
            return await send_interaction_message(interaction, "❌ Ticket system is not fully set up. Contact an administrator.", ephemeral=True)
            
        # Check limits
        member = interaction.user
        open_tickets = await db.get_open_tickets(interaction.guild.id, member.id)
        max_tickets = settings.get('max_tickets_per_user', 1)
        
        if len(open_tickets) >= max_tickets:
            return await send_interaction_message(interaction, f"❌ You already have {len(open_tickets)} open ticket(s). Please close them before opening a new one.", ephemeral=True)

        category = interaction.guild.get_channel(settings['category_id'])
        if not category:
            return await send_interaction_message(interaction, "❌ The configured ticket category was not found.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        # Permissions setup
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        support_role = interaction.guild.get_role(settings['support_role_id']) if settings.get('support_role_id') else None
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        # We need an ID first to append to the channel name
        # Alternatively we can create channel, then record in DB, then append the ID to channel name
        clean_name = ''.join(c if c.isalnum() else '-' for c in member.name).lower()
        channel_name = f"ticket-{clean_name}"
        
        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {member.id}"
            )
        except Exception as e:
            return await send_interaction_message(interaction, f"❌ Failed to create ticket channel: {e}", ephemeral=True)
            
        # DB Record
        ticket_id = await db.create_ticket(interaction.guild.id, ticket_channel.id, member.id)
        
        # Rename channel to include ID based on user preference -> "ticket-username (#ticket-id)" format
        safe_name = f"ticket-{clean_name}-{ticket_id}"
        await ticket_channel.edit(name=safe_name)

        custom_content, embed = await build_ticket_open_payload(
            interaction.guild,
            member,
            ticket_channel,
            ticket_id,
            support_role,
        )
        
        ping_content = f"{member.mention}"
        if support_role:
            ping_content += f" {support_role.mention}"
            
        full_content = ping_content if not custom_content else f"{ping_content}\n{custom_content}"
        await ticket_channel.send(content=full_content, embed=embed, view=TicketActiveView())
        
        await send_interaction_message(interaction, f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketActiveView())

    @commands.hybrid_group(name="ticket", description="Manage the ticket system")
    async def ticket_group(self, ctx: commands.Context):
        pass

    @ticket_group.command(name="setup", description="Setup the ticket system configuration")
    @app_commands.describe(
        category="Category where ticket channels will be created",
        support_role="Role that gets access to and is pinged for new tickets",
        closer_role="Optional: Role that is allowed to close tickets (Admins/Support can always close)",
        max_tickets="Maximum number of open tickets a user can have at once (default: 1)"
    )
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: commands.Context, category: discord.abc.GuildChannel, support_role: discord.Role, closer_role: Optional[discord.Role] = None, max_tickets: int = 1):
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.send(
                "❌ Please select a **category channel** for `category` (not a text/voice channel).",
                ephemeral=True,
            )

        closer_id = closer_role.id if closer_role else None
        await db.set_ticket_settings(interaction.guild.id, category.id, support_role.id, closer_id, max_tickets)
        
        embed = discord.Embed(
            title="✅ Ticket System Set Up",
            color=await get_embed_color(interaction.guild.id, 'ticket_panel', 'color_ticket')
        )
        embed.add_field(name="Category", value=category.mention)
        embed.add_field(name="Support Role", value=support_role.mention)
        if closer_role:
            embed.add_field(name="Closer Role", value=closer_role.mention)
        embed.add_field(name="Max Tickets/User", value=str(max_tickets))
        embed.set_footer(text="To configure logging for tickets, use /log set type:Ticket Logs")
        
        await interaction.send(embed=embed, ephemeral=True)

    @ticket_group.command(name="opendashboard", description="Customize the message sent when a ticket is opened")
    @commands.has_permissions(administrator=True)
    async def ticket_open_dashboard(self, ctx: commands.Context):
        editor = WelcomeDashboardView(self, ctx, ticket_open=True)
        await editor.fetch_state()
        await ctx.send(embed=await editor._build_editor_embed(), view=editor, ephemeral=True)

        content, preview_embed = await editor._build_preview(ctx, preview_mode=True)
        editor.preview_message = await ctx.send(
            content=content or "**Live Preview:**",
            embed=preview_embed,
            ephemeral=True,
        )

    @ticket_group.command(name="openpreview", description="Preview the configured ticket-open message")
    @commands.has_permissions(administrator=True)
    async def ticket_open_preview(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("❌ This command can only be used in a server.", ephemeral=True)

        settings = await db.get_ticket_settings(ctx.guild.id)
        support_role = None
        if settings and settings.get('support_role_id'):
            support_role = ctx.guild.get_role(settings['support_role_id'])

        ticket_channel = ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None
        if not ticket_channel:
            return await ctx.send("❌ This preview requires a regular text channel.", ephemeral=True)

        custom_content, preview_embed = await build_ticket_open_payload(
            ctx.guild,
            ctx.author,
            ticket_channel,
            9999,
            support_role,
        )

        ping_content = f"{ctx.author.mention}"
        if support_role:
            ping_content += f" {support_role.mention}"

        full_content = ping_content if not custom_content else f"{ping_content}\n{custom_content}"
        await ctx.send(
            content=f"**Ticket Open Preview**\n{full_content}",
            embed=preview_embed,
            ephemeral=True,
        )

    @ticket_group.command(name="panel", description="Deploy a fully customizable ticket panel with the Embed Builder")
    @app_commands.describe(channel="Channel to deploy the panel in")
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: commands.Context, channel: discord.TextChannel):
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.send(f"❌ I don't have permission to write in {channel.mention}.", ephemeral=True)

        settings = await db.get_ticket_settings(interaction.guild.id)
        if not settings or not settings.get('category_id'):
            return await interaction.send("❌ You must run `/ticket setup` before deploying a panel.", ephemeral=True)

        initial_embed = discord.Embed(
            title="Support Tickets",
            description="Click the button below to open a private ticket.",
            color=await get_embed_color(interaction.guild.id, 'ticket_panel', 'color_ticket')
        )

        async def save_panel(panel_embed: discord.Embed):
            sent = await channel.send(embed=panel_embed, view=TicketPanelView())
            await db.add_ticket_panel(
                sent.id,
                interaction.guild.id,
                channel.id,
                panel_embed.title or "Support Tickets",
                panel_embed.description or "Click the button below to open a private ticket.",
            )

        view = EmbedBuilderView(
            target_channel=channel,
            initial_embed=initial_embed,
            save_callback=save_panel,
        )
        await interaction.send(
            "🛠️ **Ticket Panel Builder**\n*Preview:*",
            embed=initial_embed,
            view=view,
            ephemeral=True,
        )

    @ticket_group.command(name="paneledit", description="Edit an existing ticket panel message with the Embed Builder")
    @app_commands.describe(
        channel="Channel that contains the panel message",
        message_id="ID of the ticket panel message to edit",
    )
    @commands.has_permissions(administrator=True)
    async def ticket_panel_edit(self, interaction: commands.Context, channel: discord.TextChannel, message_id: str):
        if not channel.permissions_for(interaction.guild.me).read_message_history:
            return await interaction.send(f"❌ I can't read message history in {channel.mention}.", ephemeral=True)

        try:
            message_id_int = int(message_id)
        except ValueError:
            return await interaction.send("❌ Invalid message ID formatting.", ephemeral=True)

        panel_record = await db.get_ticket_panel(message_id_int)
        if not panel_record or panel_record.get('guild_id') != interaction.guild.id:
            return await interaction.send("❌ This message is not a registered ticket panel in this server.", ephemeral=True)

        if panel_record.get('channel_id') != channel.id:
            return await interaction.send("❌ The message ID is not registered for the selected channel.", ephemeral=True)

        try:
            target_msg = await channel.fetch_message(message_id_int)
        except discord.NotFound:
            return await interaction.send("❌ Panel message not found in that channel.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.send("❌ I can't fetch that message in the selected channel.", ephemeral=True)

        if target_msg.author.id != self.bot.user.id:
            return await interaction.send("❌ I can only edit my own panel messages.", ephemeral=True)

        if target_msg.components:
            has_ticket_button = any(
                getattr(component, 'custom_id', None) == 'ticket_create_btn'
                for row in target_msg.components
                for component in row.children
            )
            if not has_ticket_button:
                return await interaction.send("❌ This message does not contain the ticket panel button.", ephemeral=True)

        initial_embed = (
            discord.Embed.from_dict(target_msg.embeds[0].to_dict())
            if target_msg.embeds
            else discord.Embed(
                title=panel_record.get('title') or "Support Tickets",
                description=panel_record.get('description') or "Click the button below to open a private ticket.",
                color=await get_embed_color(interaction.guild.id, 'ticket_panel', 'color_ticket'),
            )
        )

        async def save_panel(panel_embed: discord.Embed):
            await target_msg.edit(embed=panel_embed, view=TicketPanelView())
            await db.update_ticket_panel(
                target_msg.id,
                panel_embed.title or "Support Tickets",
                panel_embed.description or "Click the button below to open a private ticket.",
            )

        view = EmbedBuilderView(
            target_channel=channel,
            initial_embed=initial_embed,
            save_callback=save_panel,
        )
        await interaction.send(
            "🛠️ **Ticket Panel Editor**\n*Preview:*",
            embed=initial_embed,
            view=view,
            ephemeral=True,
        )

    @ticket_group.command(name="panellist", description="List all registered ticket panel messages")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_list(self, interaction: commands.Context):
        panels = await db.get_ticket_panels(interaction.guild.id)
        if not panels:
            await interaction.send("ℹ️ No ticket panels are registered in this server.", ephemeral=True)
            return

        lines = []
        for index, panel in enumerate(panels[:25], start=1):
            channel = interaction.guild.get_channel(panel['channel_id'])
            channel_text = channel.mention if channel else f"<#{panel['channel_id']}>"
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{panel['channel_id']}/{panel['message_id']}"
            lines.append(
                f"{index}. Channel: {channel_text} | Message: `{panel['message_id']}` | [Jump]({jump_url})"
            )

        embed = discord.Embed(
            title="🎫 Ticket Panels",
            description="\n".join(lines),
            color=await get_embed_color(interaction.guild.id, 'ticket_panel', 'color_ticket'),
        )
        embed.set_footer(text="Use /ticket paneledit to edit one specific panel message.")
        await interaction.send(embed=embed, ephemeral=True)

    @ticket_group.command(name="add", description="Add a user to the current ticket")
    @app_commands.describe(user="The user to add")
    async def ticket_add(self, interaction: commands.Context, user: discord.Member):
        settings = await db.get_ticket_settings(interaction.guild.id)
        
        is_support = False
        if settings and settings.get('support_role_id'):
            support_role = interaction.guild.get_role(settings['support_role_id'])
            if support_role in interaction.author.roles:
                is_support = True
                
        if not (interaction.author.guild_permissions.administrator or is_support):
            return await interaction.send("❌ Only support staff or administrators can manage ticket members.", ephemeral=True)

        try:
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True)
            await interaction.send(f"✅ {user.mention} has been added to the ticket.")
        except discord.Forbidden:
            await interaction.send("❌ I do not have permission to manage this channel.", ephemeral=True)

    @ticket_group.command(name="remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="The user to remove")
    async def ticket_remove(self, interaction: commands.Context, user: discord.Member):
        settings = await db.get_ticket_settings(interaction.guild.id)
        is_support = False
        if settings and settings.get('support_role_id'):
            support_role = interaction.guild.get_role(settings['support_role_id'])
            if support_role in interaction.author.roles:
                is_support = True
                
        if not (interaction.author.guild_permissions.administrator or is_support):
            return await interaction.send("❌ Only support staff or administrators can manage ticket members.", ephemeral=True)

        try:
            await interaction.channel.set_permissions(user, overwrite=None)
            await interaction.send(f"✅ {user.mention} has been removed from the ticket.")
        except discord.Forbidden:
            await interaction.send("❌ I do not have permission to manage this channel.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
