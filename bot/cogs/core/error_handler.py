import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands
import traceback
import sys
import os
import io

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Save the original tree error handler to restore on unload
        self._original_tree_error = bot.tree.on_error
        bot.tree.on_error = self.on_app_command_error

    async def cog_unload(self):
        # Restore the original when unloading
        self.bot.tree.on_error = self._original_tree_error

    async def get_log_channel(self, is_fatal: bool = True):
        env_var = "ERROR_LOG_CHANNEL_ID" if is_fatal else "NON_FATAL_LOG_CHANNEL_ID"
        channel_id_str = os.getenv(env_var)
        if not channel_id_str:
            return None
        try:
            channel_id = int(channel_id_str)
            return self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        except ValueError:
            return None

    def _extract_guild_and_user(self, *args, **kwargs):
        guild = None
        user = None
        
        def check_obj(obj):
            nonlocal guild, user
            if not obj:
                return
            
            # Check interaction
            if isinstance(obj, discord.Interaction):
                if not guild:
                    guild = obj.guild
                if not user:
                    user = obj.user
                return
                    
            # Check Context
            if isinstance(obj, commands.Context):
                if not guild:
                    guild = obj.guild
                if not user:
                    user = obj.author
                return

            # Check direct types
            if isinstance(obj, discord.Guild) and not guild:
                guild = obj
            if isinstance(obj, (discord.User, discord.Member)) and not user:
                user = obj
            
            # Check properties/attributes
            if not guild and hasattr(obj, 'guild'):
                guild = getattr(obj, 'guild', None)
            if not user and hasattr(obj, 'author'):
                user = getattr(obj, 'author', None)
            if not user and hasattr(obj, 'user'):
                user = getattr(obj, 'user', None)

            # Check guild_id / user_id
            if not guild:
                g_id = getattr(obj, 'guild_id', None)
                if g_id:
                    guild = self.bot.get_guild(g_id)
            if not user:
                u_id = getattr(obj, 'user_id', None) or getattr(obj, 'author_id', None)
                if u_id:
                    user = self.bot.get_user(u_id) or self.bot.get_member(u_id)

        for arg in args:
            check_obj(arg)
        for val in kwargs.values():
            check_obj(val)
            
        return guild, user

    async def log_to_channel(self, exception_msg: str, context: str, is_fatal: bool = True, guild: discord.Guild = None, user: discord.User = None):
        channel = await self.get_log_channel(is_fatal)
        if not channel:
            return
            
        icon = "⚠️" if is_fatal else "ℹ️"
        severity = "Runtime Error" if is_fatal else "Non-Fatal Warning"
        
        guild_name = guild.name if guild else "N/A"
        guild_id = str(guild.id) if guild else "N/A"
        username = user.name if user else "N/A"
        
        header = (
            f"**{icon} {severity} in {context}:**\n"
            f"**Server Name:** {guild_name}\n"
            f"**Server ID:** {guild_id}\n"
            f"**Username:** {username}\n"
        )
        
        if len(header) + len(exception_msg) + 10 > 2000:
            file = discord.File(io.BytesIO(exception_msg.encode('utf-8')), filename="traceback.py")
            try:
                await channel.send(f"{header}(See attached file)", file=file)
            except discord.HTTPException:
                pass
        else:
            try:
                await channel.send(f"{header}```py\n{exception_msg}\n```")
            except discord.HTTPException:
                pass

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Non-fatal exceptions
        non_fatal_exceptions = (
            app_commands.CommandNotFound,
            app_commands.MissingPermissions,
            app_commands.BotMissingPermissions,
            app_commands.CheckFailure,
            app_commands.CommandOnCooldown,
        )
        
        ctx_str = f"Slash Command `/{interaction.command.name if interaction.command else 'Unknown'}`"
        guild = interaction.guild
        user = interaction.user
        
        if isinstance(error, non_fatal_exceptions):
            await self.log_to_channel(str(error), ctx_str, is_fatal=False, guild=guild, user=user)
            msg = str(error)
            # Try to inform the user nicely about timeouts/permissions without throwing a stack trace
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(msg, ephemeral=True)
                except:
                    pass
            elif not interaction.is_expired():
                 try:
                     await interaction.followup.send(msg, ephemeral=True)
                 except:
                     pass
            return

        # If it's a CommandInvokeError, the true error is in `error.original`
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        # Format traceback
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = ''.join(tb_lines)
        
        await self.log_to_channel(tb_text, ctx_str, is_fatal=True, guild=guild, user=user)
        
        # User feedback
        msg = "An unexpected internal error occurred. Administrators have been notified."
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(msg, ephemeral=True)
            except:
                pass
        elif not interaction.is_expired():
             try:
                 await interaction.followup.send(msg, ephemeral=True)
             except:
                 pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Non-fatal prefix command failures
        non_fatal_exceptions = (
            commands.CommandNotFound,
            commands.MissingPermissions,
            commands.BotMissingPermissions,
            commands.CheckFailure,
            commands.CommandOnCooldown,
            commands.UserInputError,
        )
        
        ctx_str = f"Prefix Command `{ctx.command.qualified_name if ctx.command else 'Unknown'}`"
        guild = ctx.guild
        user = ctx.author
        
        if hasattr(ctx.command, 'on_error'):
            return  # The command has its own error handler

        # Provide help for missing arguments or bad syntax
        if isinstance(error, commands.MissingRequiredArgument):
            signature = ctx.command.signature if ctx.command else ""
            await ctx.send(f"❌ You are missing a required argument: `{error.param.name}`.\n**Correct usage:** `{ctx.prefix}{ctx.command.qualified_name} {signature}`", ephemeral=True)
            return
            
        if isinstance(error, commands.BadArgument):
            signature = ctx.command.signature if ctx.command else ""
            await ctx.send(f"❌ Invalid argument provided. Please check your spelling or formatting.\n**Correct usage:** `{ctx.prefix}{ctx.command.qualified_name} {signature}`", ephemeral=True)
            return

        # Check for non-fatal exceptions prior to expanding
        if isinstance(error, non_fatal_exceptions):
            await self.log_to_channel(str(error), ctx_str, is_fatal=False, guild=guild, user=user)
            
            # Send permission/cooldown errors to user
            if getattr(error, 'original', error) is not error:
                msg = str(error)
            else:
                msg = f"❌ {str(error)}"
            try:
                await ctx.send(msg, ephemeral=True)
            except:
                pass
            return

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = ''.join(tb_lines)
        
        await self.log_to_channel(tb_text, ctx_str, is_fatal=True, guild=guild, user=user)

    @commands.Cog.listener()
    async def on_error(self, event_method: str, /, *args, **kwargs):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if not exc_type:
            return
            
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = ''.join(tb_lines)
        
        ctx_str = f"Event `{event_method}`"
        guild, user = self._extract_guild_and_user(*args, **kwargs)
        try:
            await self.log_to_channel(tb_text, ctx_str, is_fatal=True, guild=guild, user=user)
        except Exception:
            # Fallback to standard output if log channel fails heavily during on_error
            traceback.print_exc()

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
