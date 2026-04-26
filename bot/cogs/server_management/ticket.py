import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import io
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

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

class TicketActiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: commands.Context, button: discord.ui.Button):
        # 1. Permission check
        settings = await db.get_ticket_settings(interaction.guild.id)
        is_staff = interaction.author.guild_permissions.administrator
        
        if settings:
            support_role_id = settings.get('support_role_id')
            closer_role_id = settings.get('closer_role_id')
            
            if not is_staff and support_role_id:
                if any(r.id == support_role_id for r in interaction.author.roles):
                    is_staff = True
            if not is_staff and closer_role_id:
                if any(r.id == closer_role_id for r in interaction.author.roles):
                    is_staff = True
                    
        if not is_staff:
            return await interaction.send("❌ Only support staff or administrators can close tickets.", ephemeral=True)

        await interaction.send("Closing ticket and generating transcript... please wait.", ephemeral=True)
        
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
                        description=f"Ticket created by <@{user_id}> was closed by {interaction.author.mention}.",
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
                await interaction.channel.delete(reason=f"Ticket closed by {interaction.author.name}")
            except discord.Forbidden:
                await interaction.send("❌ I lack permissions to delete this channel. Please delete it manually.", ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to delete ticket channel: {e}")
                await interaction.send(f"❌ Failed to delete channel: {e}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_create_btn")
    async def create_ticket(self, interaction: commands.Context, button: discord.ui.Button):
        settings = await db.get_ticket_settings(interaction.guild.id)
        if not settings or not settings.get('category_id'):
            return await interaction.send("❌ Ticket system is not fully set up. Contact an administrator.", ephemeral=True)
            
        # Check limits
        open_tickets = await db.get_open_tickets(interaction.guild.id, interaction.author.id)
        max_tickets = settings.get('max_tickets_per_user', 1)
        
        if len(open_tickets) >= max_tickets:
            return await interaction.send(f"❌ You already have {len(open_tickets)} open ticket(s). Please close them before opening a new one.", ephemeral=True)

        category = interaction.guild.get_channel(settings['category_id'])
        if not category:
            return await interaction.send("❌ The configured ticket category was not found.", ephemeral=True)

        await interaction.defer(ephemeral=True)
        
        # Permissions setup
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        support_role = interaction.guild.get_role(settings['support_role_id']) if settings.get('support_role_id') else None
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        # We need an ID first to append to the channel name
        # Alternatively we can create channel, then record in DB, then append the ID to channel name
        clean_name = ''.join(c if c.isalnum() else '-' for c in interaction.author.name).lower()
        channel_name = f"ticket-{clean_name}"
        
        try:
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {interaction.author.id}"
            )
        except Exception as e:
            return await interaction.send(f"❌ Failed to create ticket channel: {e}", ephemeral=True)
            
        # DB Record
        ticket_id = await db.create_ticket(interaction.guild.id, ticket_channel.id, interaction.author.id)
        
        # Rename channel to include ID based on user preference -> "ticket-username (#ticket-id)" format
        safe_name = f"ticket-{clean_name}-{ticket_id}"
        await ticket_channel.edit(name=safe_name)

        embed = discord.Embed(
            title=f"Ticket #{ticket_id}",
            description=f"Welcome {interaction.author.mention}!\n\nPlease describe your issue and our support team will be with you shortly.",
            color=await get_guild_color(interaction.guild.id, 'color_ticket')
        )
        
        ping_content = f"{interaction.author.mention}"
        if support_role:
            ping_content += f" {support_role.mention}"
            
        await ticket_channel.send(content=ping_content, embed=embed, view=TicketActiveView())
        
        await interaction.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)


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
    async def ticket_setup(self, interaction: commands.Context, category: discord.CategoryChannel, support_role: discord.Role, closer_role: Optional[discord.Role] = None, max_tickets: int = 1):
        closer_id = closer_role.id if closer_role else None
        await db.set_ticket_settings(interaction.guild.id, category.id, support_role.id, closer_id, max_tickets)
        
        embed = discord.Embed(
            title="✅ Ticket System Set Up",
            color=await get_guild_color(interaction.guild.id, 'color_ticket')
        )
        embed.add_field(name="Category", value=category.mention)
        embed.add_field(name="Support Role", value=support_role.mention)
        if closer_role:
            embed.add_field(name="Closer Role", value=closer_role.mention)
        embed.add_field(name="Max Tickets/User", value=str(max_tickets))
        embed.set_footer(text="To configure logging for tickets, use /log set type:Ticket Logs")
        
        await interaction.send(embed=embed, ephemeral=True)

    @ticket_group.command(name="panel", description="Deploy the ticket creation panel")
    @app_commands.describe(
        channel="Channel to deploy the panel in",
        title="Title of the embed",
        description="Description of the embed"
    )
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: commands.Context, channel: discord.TextChannel, title: str = "Support Tickets", description: str = "Click the button below to open a private ticket."):
        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.send(f"❌ I don't have permission to write in {channel.mention}.", ephemeral=True)
            
        settings = await db.get_ticket_settings(interaction.guild.id)
        if not settings or not settings.get('category_id'):
            return await interaction.send("❌ You must run `/ticket setup` before deploying a panel.", ephemeral=True)

        embed = discord.Embed(
            title=title,
            description=description,
            color=await get_guild_color(interaction.guild.id, 'color_ticket')
        )
        
        msg = await channel.send(embed=embed, view=TicketPanelView())
        await db.add_ticket_panel(msg.id, interaction.guild.id, channel.id, title, description)
        await interaction.send(f"✅ Ticket panel deployed to {channel.mention}", ephemeral=True)

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
