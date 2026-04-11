import discord
from discord.ext import commands
from discord import app_commands
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

    async def log_to_channel(self, exception_msg: str, context: str, is_fatal: bool = True):
        channel = await self.get_log_channel(is_fatal)
        if not channel:
            return
            
        icon = "⚠️" if is_fatal else "ℹ️"
        severity = "Runtime Error" if is_fatal else "Non-Fatal Warning"
        header = f"**{icon} {severity} in {context}:**\n"
        
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
        
        if isinstance(error, non_fatal_exceptions):
            await self.log_to_channel(str(error), ctx_str, is_fatal=False)
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
        
        await self.log_to_channel(tb_text, ctx_str, is_fatal=True)
        
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
        
        if hasattr(ctx.command, 'on_error'):
            return  # The command has its own error handler

        # Check for non-fatal exceptions prior to expanding
        if isinstance(error, non_fatal_exceptions):
            await self.log_to_channel(str(error), ctx_str, is_fatal=False)
            return

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = ''.join(tb_lines)
        
        await self.log_to_channel(tb_text, ctx_str, is_fatal=True)

    @commands.Cog.listener()
    async def on_error(self, event_method: str, /, *args, **kwargs):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if not exc_type:
            return
            
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = ''.join(tb_lines)
        
        ctx_str = f"Event `{event_method}`"
        try:
            await self.log_to_channel(tb_text, ctx_str, is_fatal=True)
        except Exception:
            # Fallback to standard output if log channel fails heavily during on_error
            traceback.print_exc()

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
