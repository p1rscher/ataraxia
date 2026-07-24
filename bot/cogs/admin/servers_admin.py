# cogs/admin/servers_admin.py
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class InviteConsentView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, developer: discord.User):
        super().__init__(timeout=86400) # 24 hours
        self.bot = bot
        self.guild = guild
        self.developer = developer

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="invite_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # generate invite
        invite = None
        for channel in self.guild.text_channels:
            if channel.permissions_for(self.guild.me).create_instant_invite:
                try:
                    invite = await channel.create_invite(max_age=3600, max_uses=1, unique=True, reason="Owner approved bot developer join request")
                    break
                except discord.HTTPException:
                    continue
        
        if invite:
            try:
                await self.developer.send(f"✅ The owner of **{self.guild.name}** has approved your request! Here is your temporary invite:\n{invite.url}")
            except discord.Forbidden:
                pass
            await interaction.response.edit_message(content=f"✅ You approved the request. An invite has been sent to the developer.", view=None, embed=None)
        else:
            await interaction.response.edit_message(content="❌ I tried to generate an invite, but I lack the permissions in all text channels.", view=None, embed=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="invite_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.developer.send(f"❌ The owner of **{self.guild.name}** has denied your invite request.")
        except discord.Forbidden:
            pass
        await interaction.response.edit_message(content=f"🛑 You denied the request. No invite was generated.", view=None, embed=None)

class ServersAdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="servers", hidden=True)
    @commands.is_owner()
    async def list_servers(self, ctx: commands.Context):
        """Lists all servers the bot is currently in (Prefix command, owner only)"""
        if not self.bot.guilds:
            await ctx.send("🤖 I am not in any servers.")
            return

        guild_list = []
        for index, guild in enumerate(self.bot.guilds, 1):
            owner_str = f"{guild.owner} ({guild.owner_id})" if guild.owner else f"Unknown Owner ({guild.owner_id})"
            
            if "VERIFIED" in guild.features: status = "Verified"
            elif "PARTNERED" in guild.features: status = "Partnered"
            elif "DISCOVERABLE" in guild.features: status = "Discoverable"
            elif "COMMUNITY" in guild.features: status = "Community"
            else: status = "Private"
            
            is_community = "Yes" if "COMMUNITY" in guild.features else "No"

            guild_list.append(
                f"**{index}. {guild.name}**\n"
                f"• ID: `{guild.id}`\n"
                f"• Status: `{status}`\n"
                f"• Community Enabled: `{is_community}`\n"
                f"• Members: `{guild.member_count}`\n"
                f"• Owner: {owner_str}\n"
            )

        # Break the list into pages of 10 servers each to avoid hitting discord's 4000-character embed limit
        pages = [guild_list[i:i + 10] for i in range(0, len(guild_list), 10)]

        for page_num, page_content in enumerate(pages, 1):
            embed = discord.Embed(
                title=f"🌐 Server List (Page {page_num}/{len(pages)})",
                description="\n".join(page_content),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Total Servers: {len(self.bot.guilds)}")
            await ctx.send(embed=embed)

    @commands.command(name="server_invite", aliases=["sinvite", "jserver"], hidden=True)
    @commands.is_owner()
    async def server_invite(self, ctx: commands.Context, guild_id: int, *, reason: str = "No reason provided."):
        """Requests an invite link for a specific server (Prefix command, owner only)"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send(f"❌ I could not find any server with ID `{guild_id}`.")
            return

        if not guild.owner:
            await ctx.send(f"❌ Could not determine the owner for **{guild.name}**.")
            return

        embed = discord.Embed(
            title="🛠️ Developer Support Request",
            description=f"The bot developer (**{ctx.author}**) is requesting to temporarily join your server.\n\n**Reason:** *{reason}*\n\nDo you grant them permission to join?",
            color=discord.Color.gold()
        )
        embed.set_footer(text="If you did not request support, you can safely deny this.")

        view = InviteConsentView(self.bot, guild, ctx.author)

        try:
            await guild.owner.send(embed=embed, view=view)
            await ctx.send(f"✅ An invite request has been sent to the owner of **{guild.name}** (`{guild.owner}`). You will receive a DM if they approve.")
        except discord.Forbidden:
            await ctx.send(f"❌ I cannot DM the owner of **{guild.name}**. They have direct messages disabled.")

async def setup(bot):
    await bot.add_cog(ServersAdminCog(bot))
