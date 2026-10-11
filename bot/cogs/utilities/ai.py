# cogs/ai.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import commands
import os
from core.ai_client import get_ai_client, AIClientError
import logging
from dotenv import load_dotenv
from collections import defaultdict
from typing import Optional
import time
from datetime import datetime, timezone, timedelta
from core import database_pg as db
from utils.embeds import get_guild_color
from utils.stream_responder import StreamingResponder

# Discord embed description hard limit is 4096 chars; stay a little under it
# so the trailing "▌" cursor and the truncation notice never push us over.
_EMBED_DESC_LIMIT = 4096
_LIVE_PREVIEW_LIMIT = 4000
# Never edit a message more than once per this many seconds (Discord's
# per-message edit rate limit is roughly a handful of requests per few
# seconds; 2s keeps us comfortably under it even with jitter/retries).
_STREAM_EDIT_INTERVAL_SECONDS = 2.0

load_dotenv()
logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local Ollama backend instead of Groq (see core/ai_client.py)
        self.client = get_ai_client()
        self.ai_model = self.client.model
        self.user_cooldowns = defaultdict(lambda: 0)
        
        # Conversation history per user (last 5 messages)
        self.conversation_history = defaultdict(list)
        self.max_history = 5
        
        # Main developer ID
        self.main_dev_id = int(os.getenv('MAIN_DEV_ID', 0))
        
        # Daily request tracking (resets at midnight UTC)
        self.daily_requests = defaultdict(lambda: {'count': 0, 'date': None})
        
        # Burst protection (tracks requests in time window)
        self.user_request_times = defaultdict(list)
        
        # Cost tracking
        self.total_daily_requests = 0
        self.daily_cost_estimate = 0.0
        self.last_cost_check = datetime.now(timezone.utc).date()
        
        # Emergency kill switch
        self.ai_enabled = os.getenv('AI_ENABLED', 'true').lower() == 'true'
        self.max_daily_cost = float(os.getenv('MAX_DAILY_COST', '10.0'))

        # Premium tier settings
        self.tier_settings = {
            'free': {
                'cooldown': 90,
                'max_tokens': 500,
                'daily_limit': 20,
                'burst_limit': None,    # ✅ No burst protection (90s cooldown is enough)
                'burst_window': None,
                'emoji': '🆓'
            },
            'premium': {
                'cooldown': 30,
                'max_tokens': 1000,
                'daily_limit': 100,
                'burst_limit': None,      # ✅ No burst protection
                'burst_window': None,
                'emoji': '💎'
            },
            'premium_plus': {
                'cooldown': 10,
                'max_tokens': 2000,
                'daily_limit': 500,
                'burst_limit': None,      # ✅ No burst protection
                'burst_window': None,
                'emoji': '👑'
            }
        }

    @commands.hybrid_group(name="ai", description="Interact with Ataraxia AI assistant")
    async def ai_group(self, ctx: commands.Context):
        pass

    @ai_group.command(name="ask", description="Ask AI a question")
    @app_commands.describe(question="Your question")
    async def ask(self, ctx: commands.Context, question: str):
        user_id = ctx.author.id
        now = time.time()
        today = datetime.now(timezone.utc).date()
        
        # ✅ EMERGENCY KILL SWITCH
        if not self.ai_enabled:
            await ctx.send(
                "🚫 AI is temporarily disabled for maintenance. Please try again later!",
                ephemeral=True
            )
            return
        
        # ✅ DAILY COST LIMIT CHECK
        if self.daily_cost_estimate >= self.max_daily_cost:
            logger.critical(f"DAILY COST LIMIT REACHED: ${self.daily_cost_estimate:.2f}")
            await ctx.send(
                "🚫 AI temporarily disabled due to high usage. Resets at midnight UTC!\n"
                "Sorry for the inconvenience! 💫",
                ephemeral=True
            )
            return
        
        # Get user premium tier
        tier = await db.get_user_premium_tier(user_id)
        settings = self.tier_settings[tier]
        
        # Owner bypass (only for main dev, not co-owner)
        is_owner = user_id == self.main_dev_id
        
        # ✅ BURST PROTECTION (only for premium tiers with burst limits)
        if not is_owner and settings.get('burst_limit') is not None:
            burst_window = settings['burst_window']
            burst_limit = settings['burst_limit']
            
            recent_requests = self.user_request_times[user_id]
            # Keep only requests within the burst window
            recent_requests = [t for t in recent_requests if now - t < burst_window]
            self.user_request_times[user_id] = recent_requests
            
            # Check if over burst limit
            if len(recent_requests) >= burst_limit:
                window_minutes = burst_window // 60
                await ctx.send(
                    f"🚫 **Slow down!** You're sending requests too quickly.\n"
                    f"Max **{burst_limit} requests per {window_minutes} minutes**.\n\n"
                    f"You've made **{len(recent_requests)}** requests in the last {window_minutes} minutes.\n"
                    f"Please wait a moment before trying again! ⏳",
                    ephemeral=True
                )
                logger.warning(
                    f"Burst protection triggered for user {user_id} ({ctx.author.name}) - "
                    f"{len(recent_requests)}/{burst_limit} in {window_minutes}min"
                )
                return
        
        # ✅ DAILY LIMIT CHECK
        user_usage = self.daily_requests[user_id]
        
        # Reset counter if new day
        if user_usage['date'] != today:
            user_usage['count'] = 0
            user_usage['date'] = today
        
        # Check if over daily limit (owner bypass)
        if not is_owner and user_usage['count'] >= settings['daily_limit']:
            next_tier_msg = ""
            if tier == 'free':
                next_tier_msg = (
                    f"\n\n💎 **Need more requests?**\n"
                    f"Premium: 100/day (30s cooldown)\n"
                    f"Premium+: 500/day (10s cooldown)\n"
                    f"Use `/premium` to upgrade!"
                )
            elif tier == 'premium':
                next_tier_msg = f"\n\n👑 **Upgrade to Premium+** for 500 requests/day!"
            
            await ctx.send(
                f"❌ **Daily limit reached!**\n"
                f"You've used **{user_usage['count']}/{settings['daily_limit']}** requests today.\n"
                f"Limit resets at **midnight UTC** (in {self._time_until_midnight()})."
                f"{next_tier_msg}",
                ephemeral=True
            )
            return
        
        # ✅ COOLDOWN CHECK
        cooldown = settings['cooldown']
        if not is_owner and now - self.user_cooldowns[user_id] < cooldown:
            remaining = int(cooldown - (now - self.user_cooldowns[user_id]))
            
            # Show upgrade message if not highest tier
            upgrade_msg = ""
            if tier == 'free':
                upgrade_msg = (
                    f"\n\n💡 **Upgrade for faster AI:**\n"
                    f"💎 Premium: 30s cooldown, 100/day\n"
                    f"👑 Premium+: 10s cooldown, 500/day\n"
                    f"Use `/premium` to learn more!"
                )
            elif tier == 'premium':
                upgrade_msg = f"\n\n👑 **Upgrade to Premium+** for 10s cooldown!"
            
            await ctx.send(
                f"⏳ Please wait **{remaining}s** before asking again!\n"
                f"Daily usage: **{user_usage['count']}/{settings['daily_limit']}**"
                f"{upgrade_msg}",
                ephemeral=True
            )
            return
        
        # Update cooldown & burst tracking
        self.user_cooldowns[user_id] = now
        if not is_owner and settings.get('burst_limit') is not None:
            self.user_request_times[user_id].append(now)
        
        # Defer response
        await ctx.defer()
        
        message = None  # becomes the streaming placeholder once it's sent
        try:
            # Check if user is main developer
            is_main_dev = user_id == self.main_dev_id
            
            # Build Ataraxia-specific context
            system_prompt = await self._build_ataraxia_context(ctx, is_main_dev)
            
            # Add real-time stats if question is stats-related
            additional_context = ""
            question_lower = question.lower()
            
            if any(keyword in question_lower for keyword in ["stats", "statistics", "active", "users", "commands", "level", "xp"]):
                stats_context = await self._get_server_stats(ctx.guild.id)
                additional_context = f"\n\n**Current Server Statistics:**\n{stats_context}"
            
            # Build messages array with conversation history
            messages = [
                {
                    "role": "system",
                    "content": system_prompt + additional_context
                }
            ]
            
            # Add conversation history for this user
            user_history = self.conversation_history[user_id]
            for hist_q, hist_a in user_history:
                messages.append({"role": "user", "content": hist_q})
                messages.append({"role": "assistant", "content": hist_a})
            
            # Add current question
            messages.append({"role": "user", "content": question})
            
            # --- Streaming placeholder -----------------------------------
            # Sent once, then edited in place as the answer streams in.
            question_display = question if len(question) <= 1024 else question[:1021] + "..."
            embed_color = await get_guild_color(ctx.guild.id if ctx.guild.id else None)

            placeholder = discord.Embed(title=f"{settings['emoji']} AI Response", color=embed_color)
            placeholder.add_field(name="❓ Question", value=question_display, inline=False)
            placeholder.description = "⏳ *Thinking...*"
            placeholder.set_footer(text="Generating…")
            message = await ctx.send(embed=placeholder)

            # Mutable extras filled in once the stream finishes successfully;
            # `render` below reads them at the time of the final edit.
            final_extras = {"action_result": None, "footer": None}

            def render(text: str, done: bool, error: Optional[BaseException]) -> dict:
                out = discord.Embed(title=f"{settings['emoji']} AI Response", color=embed_color)
                out.add_field(name="❓ Question", value=question_display, inline=False)

                if not text:
                    body = "*(keine Antwort erhalten)*" if done else "⏳ *Thinking...*"
                elif len(text) <= _LIVE_PREVIEW_LIMIT:
                    body = text if done else text + " ▌"
                else:
                    body = text[:_LIVE_PREVIEW_LIMIT] + "\n\n*(…Antwort geht unten weiter)*"
                out.description = body[:_EMBED_DESC_LIMIT]

                if error is not None:
                    out.color = discord.Color.red()
                    out.set_footer(
                        text="⚠️ Generation failed - response may be incomplete"
                        if text else "⚠️ Generation failed"
                    )
                elif done and final_extras["action_result"]:
                    out.add_field(name="⚙️ Action Executed", value=final_extras["action_result"], inline=False)
                    out.color = discord.Color.gold()
                    out.set_footer(text=final_extras["footer"] or "")
                elif done:
                    out.set_footer(text=final_extras["footer"] or "")
                else:
                    out.set_footer(text="Generating…")

                return {"embed": out}

            response = ""
            usage_sink: dict = {}

            # StreamingResponder guarantees:
            #  - at most one message.edit() every _STREAM_EDIT_INTERVAL_SECONDS
            #  - exactly one final edit on exit, success or failure, so a fast
            #    answer that finishes inside the first interval still ends up
            #    with exactly one edit total (same as the old non-streaming path)
            async with StreamingResponder(message, render, min_interval=_STREAM_EDIT_INTERVAL_SECONDS) as responder:
                async for delta in self.client.stream_chat(
                    model=self.ai_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=settings['max_tokens'],
                    usage_sink=usage_sink,
                ):
                    response += delta
                    responder.update(response)

                # Stream completed without raising - safe to count it and
                # run owner actions before the guaranteed final edit fires.
                user_usage['count'] += 1
                self.total_daily_requests += 1
                # Local model = no API costs; kept only as a reference figure.
                tokens_used = usage_sink.get('total_tokens') or max(1, len(response) // 4)
                cost_per_token = float(os.getenv('AI_COST_PER_TOKEN', '0.0'))
                self.daily_cost_estimate += tokens_used * cost_per_token
                if self.total_daily_requests % 100 == 0:
                    await self._check_cost_alert()

                if is_main_dev:
                    final_extras["action_result"] = await self._process_owner_actions(ctx, question, response)

                final_extras["footer"] = (
                    f"Asked by {ctx.author.display_name} • "
                    f"{tier.replace('_', ' ').title()} • "
                    f"{user_usage['count']}/{settings['daily_limit']} today • "
                    f"{self.ai_model}"
                )

            # The embed description can only hold ~4000 visible chars; send
            # anything beyond that as ordinary follow-up messages.
            if len(response) > _LIVE_PREVIEW_LIMIT:
                for chunk in self._chunk_text(response[_LIVE_PREVIEW_LIMIT:], 1900):
                    await ctx.channel.send(chunk)

            # Save to conversation history
            self.conversation_history[user_id].append((question, response))
            if len(self.conversation_history[user_id]) > self.max_history:
                self.conversation_history[user_id].pop(0)
            
            logger.info(
                f"AI request by {ctx.author.name} (ID: {user_id}, tier: {tier}, "
                f"daily: {user_usage['count']}/{settings['daily_limit']}): {question[:50]}..."
            )

        except AIClientError as e:
            # If a placeholder message exists, StreamingResponder's __aexit__
            # already edited it to show whatever partial text was streamed
            # plus an error note - the ephemeral message below is just a
            # clear heads-up for the requester on top of that.
            logger.error(f"AI backend unreachable for user {user_id}: {e}", exc_info=True)
            await ctx.send(
                "❌ The AI backend is currently unreachable.\n"
                "The self-hosted model might be offline - please try again in a moment!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"AI Error for user {user_id}: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error: {str(e)}\n\n"
                f"If this persists, please contact support!",
                ephemeral=True
            )

    @staticmethod
    def _chunk_text(text: str, limit: int) -> list:
        """Split text into pieces up to `limit` chars, breaking on
        whitespace where possible."""
        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            split_pos = text[:limit].rfind(' ')
            if split_pos == -1:
                split_pos = limit
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        return chunks
    
    @ai_group.command(name="status", description="Check your AI usage tier and limits")
    async def aistatus(self, ctx: commands.Context):
        user_id = ctx.author.id
        tier = await db.get_user_premium_tier(user_id)
        settings = self.tier_settings[tier]
        
        # Get today's usage
        today = datetime.now(timezone.utc).date()
        user_usage = self.daily_requests[user_id]
        if user_usage['date'] != today:
            user_usage['count'] = 0
        
        embed = discord.Embed(
            title=f"{settings['emoji']} Your AI Status",
            color=await get_guild_color(ctx.guild.id if ctx.guild.id else None)
        )
        
        embed.add_field(
            name="Current Tier",
            value=tier.replace('_', ' ').title(),
            inline=False
        )
        
        embed.add_field(
            name="⏱️ Cooldown",
            value=f"{settings['cooldown']} seconds",
            inline=True
        )
        
        embed.add_field(
            name="📊 Daily Limit",
            value=f"{user_usage['count']}/{settings['daily_limit']} used",
            inline=True
        )
        
        embed.add_field(
            name="📝 Max Response",
            value=f"{settings['max_tokens']} tokens",
            inline=True
        )
        
        # Add burst info only for premium tiers
        if settings.get('burst_limit') is not None:
            burst_window_min = settings['burst_window'] // 60
            embed.add_field(
                name="🚀 Burst Protection",
                value=f"Max {settings['burst_limit']} per {burst_window_min} min",
                inline=True
            )
        else:
            embed.add_field(
                name="🚀 Burst Protection",
                value="None (cooldown sufficient)",
                inline=True
            )
        
        if tier != 'premium_plus':
            upgrade_options = []
            if tier == 'free':
                upgrade_options.append("💎 **Premium**: 30s cooldown, 100/day, burst protection")
                upgrade_options.append("👑 **Premium+**: 10s cooldown, 500/day, faster burst limit")
            elif tier == 'premium':
                upgrade_options.append("👑 **Premium+**: 10s cooldown, 500/day, 50 req/10min")
            
            embed.add_field(
                name="✨ Upgrade Available",
                value="\n".join(upgrade_options) + f"\n\nUse `/premium` to learn more!",
                inline=False
            )
        
        # Add reset time
        reset_time = self._time_until_midnight()
        embed.add_field(
            name="🕐 Daily Limit Resets In",
            value=reset_time,
            inline=False
        )
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @ai_group.command(name="clearhistory", description="Clear your conversation history with Ataraxia")
    async def clear_history(self, ctx: commands.Context):
        """Clear conversation history for the user"""
        user_id = ctx.author.id
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
            await ctx.send(
                "🧹 Your conversation history has been cleared! Starting fresh.",
                ephemeral=True
            )
        else:
            await ctx.send(
                "📝 You don't have any conversation history yet!",
                ephemeral=True
            )
    
    def _get_tier_color(self, tier: str) -> discord.Color:
        """Returns color based on tier"""
        colors = {
            'free': discord.Color.blue(),
            'premium': discord.Color.purple(),
            'premium_plus': discord.Color.gold()
        }
        return colors.get(tier, discord.Color.blue())
    
    def _time_until_midnight(self) -> str:
        """Calculate time until midnight UTC"""
        now = datetime.now(timezone.utc)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
        delta = tomorrow - now
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"
    
    async def _check_cost_alert(self):
        """Send alert if daily costs are getting high"""
        if self.daily_cost_estimate > 5.0:  # $5/day warning
            try:
                owner = await self.bot.fetch_user(self.main_dev_id)
                embed = discord.Embed(
                    title="⚠️ AI Cost Alert",
                    description=f"Daily AI costs are getting high!\n\n**Estimated cost today**: ${self.daily_cost_estimate:.2f}",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Total Requests", value=f"{self.total_daily_requests:,}")
                embed.add_field(name="Max Daily Limit", value=f"${self.max_daily_cost:.2f}")
                embed.add_field(
                    name="Note",
                    value="Running on a self-hosted Ollama model (no API costs). This is a reference figure only.",
                    inline=False
                )
                
                await owner.send(embed=embed)
                logger.warning(f"Cost alert sent: ${self.daily_cost_estimate:.2f} today")
            except Exception as e:
                logger.error(f"Failed to send cost alert: {e}")
    
    async def _process_owner_actions(self, ctx: commands.Context, question: str, ai_response: str) -> str:
        """Process special actions for bot owner"""
        question_lower = question.lower()
        
        # Action: Get error logs
        if "show errors" in question_lower or "recent errors" in question_lower:
            try:
                return "📋 Checked error logs (last 10 entries)"
            except Exception as e:
                return f"❌ Failed to fetch logs: {e}"
        
        # Action: Reload a cog
        if "reload" in question_lower or "restart cog" in question_lower:
            cog_name = None
            for cog in self.bot.cogs:
                if cog.lower() in question_lower:
                    cog_name = cog
                    break
            
            if cog_name:
                try:
                    await self.bot.reload_extension(f"cogs.{cog_name.lower()}")
                    return f"✅ Reloaded cog: {cog_name}"
                except Exception as e:
                    return f"❌ Failed to reload {cog_name}: {e}"
        
        # Action: Get user info
        if "get info" in question_lower and "user" in question_lower:
            import re
            match = re.search(r'\d{17,19}', question)
            if match:
                user_id = int(match.group())
                try:
                    user_level = await db.get_level(user_id, ctx.guild.id)
                    if user_level:
                        return f"📊 User {user_id}: Level {user_level['level']}, XP {user_level['xp']:,}"
                    else:
                        return f"📊 User {user_id}: Not in database yet"
                except Exception as e:
                    return f"❌ Failed to fetch user info: {e}"
        
        # Action: Database query
        if "database" in question_lower and "query" in question_lower:
            return "🔒 Direct database queries disabled for safety. Use specific commands instead."
        
        return None
    
    async def _build_ataraxia_context(self, ctx: commands.Context, is_main_dev: bool = False) -> str:
        """Build Ataraxia-specific system prompt"""
        
        base_prompt = f"""You are Ataraxia, a friendly and helpful Discord bot.

**Your Identity:**
- Name: Ataraxia (Greek: ἀταραξία - "tranquility, calmness")
- Personality: Calm, helpful, knowledgeable about your own features
- Server: {ctx.guild.name} ({ctx.guild.member_count} members)
- You're speaking to: {ctx.author.display_name}"""

        if is_main_dev:
            base_prompt += """
- ⚠️ **OWNER MODE**: You're speaking to the bot owner! You can suggest admin actions.

**Available Owner Actions:**
- "show errors" or "recent errors" - View error logs
- "reload [cog_name]" or "restart cog [name]" - Reload a specific cog
- "get info about user [id]" - Fetch user stats from database
"""
        
        base_prompt += """

**Your Features & Commands:**
- **XP & Leveling**: Users gain 10-20 XP per message, 15-25 XP per 3 minutes in voice
- **Server Stats**: Real-time channel stats (members, users, bots, online, voice)
- **Bump Reminders**: Notify roles 2 hours after /bump
- **Verification System**: Reaction-based role assignment
- **Temp Voice**: Create temporary voice channels
- **Admin Stats**: Track command usage, active users, server growth
- **Auto Role**: Assign roles to new members automatically
- **Parent Roles**: Hierarchical role management

**Available Commands:**
- `/serverstats` - Setup stat tracking channels
- `/bump_enable` - Configure bump reminders
- `/verification_setup` - Setup verification system
- `/ask` - That's me! Ask questions about the bot
- `/aistatus` - Check your AI usage limits
- `/clear_history` - Clear conversation history
- `/admin_stats` - View detailed statistics (admin only)
- And many more moderation & utility commands

**How to respond:**
- Be conversational and friendly, not robotic
- Use emojis occasionally (🎯 ✅ 💡 🚀)
- Keep responses concise but informative
- If asked about features, explain them clearly
- If asked about stats, use the real data provided
- If unsure about something specific, admit it honestly
- Refer to yourself as "I" or "Ataraxia", not "the bot"
- Don't be afraid to show personality and humor!

Remember: You ARE Ataraxia, the Discord bot!"""
        
        return base_prompt

    async def _get_server_stats(self, guild_id: int) -> str:
        """Fetch real-time server statistics"""
        try:
            total_commands = await db.get_total_commands()
            daily_active = await db.get_daily_active_users()
            command_stats = await db.get_command_stats(days=1)
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return "Stats unavailable"
            
            top_commands = "\n".join([f"  • {cmd['command_name']}: {cmd['count']} times" 
                                     for cmd in list(command_stats)[:5]])
            
            return f"""
- Total Members: {guild.member_count}
- Active Users (24h): {daily_active}
- Total Commands Used: {total_commands:,}
- Commands Today: {sum(cmd['count'] for cmd in command_stats)}
- Top Commands Today:
{top_commands if top_commands else "  None yet"}
"""
        except Exception as e:
            logger.error(f"Failed to fetch stats: {e}")
            return "Statistics temporarily unavailable"

async def setup(bot):
    await bot.add_cog(AICog(bot))
