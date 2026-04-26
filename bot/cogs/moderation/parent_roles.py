# cogs/parent_roles.py
import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import logging
from core import database_pg as db
from utils.embeds import get_guild_color

logger = logging.getLogger(__name__)

# Invisible character for truncation (Discord shows as empty space)
INVISIBLE_CHAR = "ㅤ"
MAX_ROLE_NAME_LENGTH = 100  # Discord's max role name length


def create_truncated_name(name: str) -> str:
    """
    Create a truncated role name that spans the full width in Discord.
    Base padding: 8 invisible chars per side
    For every 4 characters in name: reduce padding by 1 per side (rounded up)
    
    Examples:
    - "Age" (3 chars) → ceil(3/4) = 1 → 8-1 = 7 padding each side
    - "Test" (4 chars) → ceil(4/4) = 1 → 8-1 = 7 padding each side
    - "Pronouns" (8 chars) → ceil(8/4) = 2 → 8-2 = 6 padding each side
    - "Very Long Name" (14 chars) → ceil(14/4) = 4 → 8-4 = 4 padding each side
    """
    
    # Base padding
    base_padding = 8
    
    # Calculate reduction: for every 4 chars in name, reduce by 1 (rounded up)
    name_length = len(name)
    reduction = name_length // 4 + (1 if name_length % 4 != 0 else 0) # alternative to math.ceil
    
    # Calculate final padding (minimum 0)
    padding = max(0, base_padding - reduction)
    
    return f"{INVISIBLE_CHAR * padding} - {name} - {INVISIBLE_CHAR * padding}"


class ParentRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="parentrole", description="Manage parent role system")
    async def parentrole_group(self, ctx: commands.Context):
        pass

    @parentrole_group.command(name="create", description="Create a parent role with truncated name")
    @app_commands.describe(
        name="The display name for the parent role (will be auto-truncated)",
        color="Hex color code (e.g., #ff0000) or leave empty for default"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def parent_role_create(
        self, 
        ctx: commands.Context, 
        name: str,
        color: str = None
    ):
        """Create a parent role with automatic truncation"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        # Create truncated name to fill the full width (100 chars)
        truncated_name = create_truncated_name(name)
        
        # Parse color
        role_color = discord.Color.default()
        if color:
            try:
                # Remove # if present
                color = color.lstrip('#')
                role_color = discord.Color(int(color, 16))
            except ValueError:
                await ctx.send("❌ Invalid color format! Use hex format like #ff0000", ephemeral=True)
                return
        
        try:
            # Create the role
            role = await ctx.guild.create_role(
                name=truncated_name,
                color=role_color,
                hoist=True,  # Display separately in member list
                mentionable=False,
                reason=f"Parent role created by {ctx.author}"
            )
            
            # Add to database
            await db.add_parent_role(ctx.guild.id, role.id)
            
            await ctx.send(
                f"✅ Created parent role: {role.mention}\n"
                f"Use `/parentrole addchild` to add child roles to it.",
                ephemeral=True
            )
            logger.info(f"Created parent role '{name}' (ID: {role.id}) in guild {ctx.guild.id}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to create roles!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Error creating role: {e}", ephemeral=True)
            logger.error(f"Error creating parent role in guild {ctx.guild.id}: {e}")

    @parentrole_group.command(name="addchild", description="Add a child role to a parent role")
    @app_commands.describe(
        parent_role="The parent role (category)",
        child_role="The child role that triggers the parent"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def parent_role_add_child(
        self, 
        ctx: commands.Context, 
        parent_role: discord.Role,
        child_role: discord.Role
    ):
        """Add a child role to a parent role"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.add_child_to_parent(ctx.guild.id, parent_role.id, child_role.id)
        
        await ctx.send(
            f"✅ Added {child_role.mention} as child of {parent_role.mention}\n"
            f"Members with {child_role.mention} will automatically get {parent_role.mention}",
            ephemeral=True
        )
        logger.info(f"Added child role {child_role.name} to parent {parent_role.name} in guild {ctx.guild.id}")

    @parentrole_group.command(name="removechild", description="Remove a child role from a parent role")
    @app_commands.describe(
        parent_role="The parent role (category)",
        child_role="The child role to remove"
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def parent_role_remove_child(
        self, 
        ctx: commands.Context, 
        parent_role: discord.Role,
        child_role: discord.Role
    ):
        """Remove a child role from a parent role"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        await db.remove_child_from_parent(ctx.guild.id, parent_role.id, child_role.id)
        
        await ctx.send(
            f"✅ Removed {child_role.mention} from parent {parent_role.mention}",
            ephemeral=True
        )
        logger.info(f"Removed child role {child_role.name} from parent {parent_role.name} in guild {ctx.guild.id}")

    @parentrole_group.command(name="delete", description="Delete a parent role configuration")
    @app_commands.describe(parent_role="The parent role to delete")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def parent_role_delete(self, ctx: commands.Context, parent_role: discord.Role):
        """Delete a parent role and its configuration"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ You need administrator permissions!", ephemeral=True)
            return
        
        # Remove from database
        await db.remove_parent_role(ctx.guild.id, parent_role.id)
        
        # Optionally delete the role itself
        try:
            await parent_role.delete(reason=f"Parent role deleted by {ctx.author}")
            await ctx.send(
                f"✅ Deleted parent role and its configuration",
                ephemeral=True
            )
            logger.info(f"Deleted parent role {parent_role.name} (ID: {parent_role.id}) from guild {ctx.guild.id}")
        except discord.Forbidden:
            await ctx.send(
                f"✅ Removed configuration but couldn't delete the role (missing permissions)",
                ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"❌ Error: {e}", ephemeral=True)

    @parentrole_group.command(name="list", description="List all parent roles and their children")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def parent_role_list(self, ctx: commands.Context):
        """List all parent role configurations"""
        parent_configs = await db.get_all_parent_roles(ctx.guild.id)
        
        if not parent_configs:
            await ctx.send(
                "❌ No parent roles configured for this server.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="👪 Parent Role Configuration",
            color=await get_guild_color(ctx.guild.id)
        )
        
        for config in parent_configs:
            parent_role = ctx.guild.get_role(config['parent_role_id'])
            if not parent_role:
                continue
            
            child_ids = config['child_role_ids'] if config['child_role_ids'] else []
            
            if not child_ids:
                child_list = "*No child roles*"
            else:
                child_roles = [ctx.guild.get_role(cid) for cid in child_ids]
                child_list = "\n".join([f"• {role.mention}" for role in child_roles if role])
            
            embed.add_field(
                name=f"{parent_role.name}",
                value=child_list,
                inline=False
            )
        
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ParentRolesCog(bot))
