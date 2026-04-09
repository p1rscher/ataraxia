import discord
from discord.ext import commands
from discord import app_commands
from core import database_pg as db

class CustomRoleCog(commands.GroupCog, group_name="customrole"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup the anchor role and allowed roles for Custom Roles")
    @app_commands.default_permissions(administrator=True)
    async def setup_cmd(self, interaction: discord.Interaction, anchor_role: discord.Role):
        # Save anchor role initially; allowed_roles empty for now until they pick
        await db.set_custom_role_setup(interaction.guild_id, anchor_role.id, [])
        
        class AllowedRolesSelect(discord.ui.RoleSelect):
            def __init__(self):
                super().__init__(placeholder="Select allowed roles...", min_values=1, max_values=25)
                
            async def callback(self, inter: discord.Interaction):
                role_ids = [role.id for role in self.values]
                await db.set_custom_role_setup(inter.guild_id, anchor_role.id, role_ids)
                await inter.response.edit_message(content=f"✅ Setup Complete!\nAnchor Role: {anchor_role.mention}\nAllowed Roles have been updated.", view=None)

        view = discord.ui.View()
        view.add_item(AllowedRolesSelect())
        await interaction.response.send_message(
            f"Anchor role set to {anchor_role.mention}.\nNow, select the roles that are ALLOWED to create custom roles:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="toggle", description="Toggle Custom Roles on or off globally")
    @app_commands.default_permissions(administrator=True)
    async def toggle_cmd(self, interaction: discord.Interaction):
        settings = await db.get_custom_role_settings(interaction.guild_id)
        new_state = not settings['enabled']
        await db.toggle_custom_role(interaction.guild_id, new_state)
        await interaction.response.send_message(f"✅ Custom Roles are now **{'Enabled' if new_state else 'Disabled'}**.", ephemeral=True)

    @app_commands.command(name="manage", description="Create or edit your custom role")
    @app_commands.describe(icon="Optional: Custom role icon image (Server Boost Lvl 2 required)")
    async def manage_cmd(self, interaction: discord.Interaction, icon: discord.Attachment = None):
        settings = await db.get_custom_role_settings(interaction.guild_id)
        
        if not settings['enabled']:
            return await interaction.response.send_message("❌ Custom Roles are currently disabled on this server.", ephemeral=True)
            
        allowed = settings['allowed_roles']
        if allowed:
            user_role_ids = [r.id for r in interaction.user.roles]
            if not any(r_id in allowed for r_id in user_role_ids):
                return await interaction.response.send_message("❌ You do not have permission to create a custom role.", ephemeral=True)
        else:
             return await interaction.response.send_message("❌ Administrators have not configured any allowed roles yet.", ephemeral=True)
             
        # Fetch existing role if it exists
        existing_role_id = await db.get_user_custom_role(interaction.user.id, interaction.guild_id)
        existing_role = interaction.guild.get_role(existing_role_id) if existing_role_id else None

        class CustomRoleModal(discord.ui.Modal, title='Manage Custom Role'):
            name_input = discord.ui.TextInput(
                label='Role Name',
                style=discord.TextStyle.short,
                default=existing_role.name if existing_role else None,
                max_length=100,
                required=True
            )
            color_input = discord.ui.TextInput(
                label='Hex Color (e.g. #ff0000)',
                style=discord.TextStyle.short,
                default=str(existing_role.color) if existing_role and str(existing_role.color) != "#000000" else None,
                max_length=7,
                required=True
            )
            
            def __init__(self, attached_icon: discord.Attachment):
                super().__init__()
                self.attached_icon = attached_icon

            async def on_submit(self, inter: discord.Interaction):
                await inter.response.defer(ephemeral=True)
                
                try:
                    color_hex = self.color_input.value.strip().lstrip('#')
                    color_int = int(color_hex, 16)
                    role_color = discord.Color(color_int)
                except ValueError:
                    return await inter.followup.send("❌ Invalid Hex Color provided. Use format `#RRGGBB`.", ephemeral=True)
                
                icon_bytes = None
                if self.attached_icon:
                    try:
                        icon_bytes = await self.attached_icon.read()
                    except:
                        pass
                
                anchor_id = settings['anchor_role_id']
                anchor_role = interaction.guild.get_role(anchor_id) if anchor_id else None
                
                if existing_role:
                    try:
                        await existing_role.edit(name=self.name_input.value, color=role_color, display_icon=icon_bytes)
                        if existing_role not in interaction.user.roles:
                            await interaction.user.add_roles(existing_role)
                        success_msg = f"✅ Updated your custom role {existing_role.mention}!"
                    except discord.HTTPException as e:
                        if icon_bytes:
                            await existing_role.edit(name=self.name_input.value, color=role_color)
                            if existing_role not in interaction.user.roles:
                                await interaction.user.add_roles(existing_role)
                            success_msg = f"✅ Updated your custom role {existing_role.mention}! However, the role icon was ignored because this server does not have enough Boosts."
                        else:
                            return await inter.followup.send(f"❌ Failed to edit role: {e}", ephemeral=True)
                else:
                    try:
                        new_role = await interaction.guild.create_role(name=self.name_input.value, color=role_color, display_icon=icon_bytes)
                        await interaction.user.add_roles(new_role)
                        await db.set_user_custom_role(interaction.user.id, interaction.guild_id, new_role.id)
                        
                        if anchor_role:
                            try:
                                await new_role.edit(position=anchor_role.position + 1)
                            except:
                                pass
                        success_msg = f"✅ Created and assigned your new custom role {new_role.mention}!"
                    except discord.HTTPException as e:
                        if icon_bytes:
                            new_role = await interaction.guild.create_role(name=self.name_input.value, color=role_color)
                            await interaction.user.add_roles(new_role)
                            await db.set_user_custom_role(interaction.user.id, interaction.guild_id, new_role.id)
                            
                            if anchor_role:
                                try:
                                    await new_role.edit(position=anchor_role.position + 1)
                                except:
                                    pass
                            success_msg = f"✅ Created your custom role {new_role.mention}! However, the role icon was ignored because this server does not have enough Boosts."
                        else:
                            return await inter.followup.send(f"❌ Failed to create role: {e}", ephemeral=True)

                await inter.followup.send(success_msg, ephemeral=True)

        await interaction.response.send_modal(CustomRoleModal(icon))

async def setup(bot):
    await bot.add_cog(CustomRoleCog(bot))
