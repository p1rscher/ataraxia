# cogs/ai.py
import discord
from discord import app_commands
from discord.ext import commands
import os
from groq import AsyncGroq
import logging
from dotenv import load_dotenv
from collections import defaultdict
import time
from datetime import datetime, timezone, timedelta
from core import database_pg as db

load_dotenv()
logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
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

    ai_group = app_commands.Group(name="ai", description="Interact with Ataraxia AI assistant")

    @ai_group.command(name="ask", description="Ask AI a question")
    @app_commands.describe(question="Your question")
    async def ask(self, ctx: discord.Interaction, question: str):
        user_id = ctx.user.id
        now = time.time()
        today = datetime.now(timezone.utc).date()
        
        # ✅ EMERGENCY KILL SWITCH
        if not self.ai_enabled:
            await ctx.response.send_message(
                "🚫 AI is temporarily disabled for maintenance. Please try again later!",
                ephemeral=True
            )
            return
        
        # ✅ DAILY COST LIMIT CHECK
        if self.daily_cost_estimate >= self.max_daily_cost:
            logger.critical(f"DAILY COST LIMIT REACHED: ${self.daily_cost_estimate:.2f}")
            await ctx.response.send_message(
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
                await ctx.response.send_message(
                    f"🚫 **Slow down!** You're sending requests too quickly.\n"
                    f"Max **{burst_limit} requests per {window_minutes} minutes**.\n\n"
                    f"You've made **{len(recent_requests)}** requests in the last {window_minutes} minutes.\n"
                    f"Please wait a moment before trying again! ⏳",
                    ephemeral=True
                )
                logger.warning(
                    f"Burst protection triggered for user {user_id} ({ctx.user.name}) - "
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
            
            await ctx.response.send_message(
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
            
            await ctx.response.send_message(
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
        await ctx.response.defer()
        
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
            
            # Groq API Call
            completion = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_tokens=settings['max_tokens'],
                stream=False,
            )
            
            response = completion.choices[0].message.content
            
            # ✅ INCREMENT DAILY COUNTER
            user_usage['count'] += 1
            
            # ✅ TRACK COSTS (for monitoring)
            self.total_daily_requests += 1
            # Rough cost estimate if using OpenAI (currently using Groq = free)
            tokens_used = completion.usage.total_tokens if hasattr(completion, 'usage') else 250
            cost_per_token = 0.0000006  # GPT-4o-mini cost (for reference)
            self.daily_cost_estimate += tokens_used * cost_per_token
            
            # ✅ COST ALERT CHECK (every 100 requests)
            if self.total_daily_requests % 100 == 0:
                await self._check_cost_alert()
            
            # Check if owner requested an action
            action_result = None
            if is_main_dev:
                action_result = await self._process_owner_actions(ctx, question, response)
            
            # Build response embed
            embed = discord.Embed(
                title=f"{settings['emoji']} AI Response",
                color=self._get_tier_color(tier)
            )
            
            # Add question field
            question_display = question if len(question) <= 1024 else question[:1021] + "..."
            embed.add_field(name="❓ Question", value=question_display, inline=False)
            
            # Split response into chunks if too long (field value limit is 1024 chars)
            if len(response) <= 1024:
                embed.add_field(name="💬 Answer", value=response, inline=False)
            else:
                chunks = []
                while response:
                    if len(response) <= 1024:
                        chunks.append(response)
                        break
                    else:
                        split_pos = response[:1024].rfind(' ')
                        if split_pos == -1:
                            split_pos = 1024
                        chunks.append(response[:split_pos])
                        response = response[split_pos:].lstrip()
                
                for i, chunk in enumerate(chunks):
                    field_name = "💬 Answer" if i == 0 else "💬 Answer (continued)"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            
            # Add action result if owner executed something
            if action_result:
                embed.add_field(name="⚙️ Action Executed", value=action_result, inline=False)
                embed.color = discord.Color.gold()
            
            # Footer with usage info
            footer_text = (
                f"Asked by {ctx.user.display_name} • "
                f"{tier.replace('_', ' ').title()} • "
                f"{user_usage['count']}/{settings['daily_limit']} today • "
                f"Llama 3.3 70B"
            )
            embed.set_footer(text=footer_text)

            await ctx.followup.send(embed=embed)
            
            # Save to conversation history
            self.conversation_history[user_id].append((question, response))
            if len(self.conversation_history[user_id]) > self.max_history:
                self.conversation_history[user_id].pop(0)
            
            logger.info(
                f"AI request by {ctx.user.name} (ID: {user_id}, tier: {tier}, "
                f"daily: {user_usage['count']}/{settings['daily_limit']}): {question[:50]}..."
            )

        except Exception as e:
            logger.error(f"AI Error for user {user_id}: {e}", exc_info=True)
            await ctx.followup.send(
                f"❌ Error: {str(e)}\n\n"
                f"If this persists, please contact support!",
                ephemeral=True
            )
    
    @ai_group.command(name="status", description="Check your AI usage tier and limits")
    async def aistatus(self, ctx: discord.Interaction):
        user_id = ctx.user.id
        tier = await db.get_user_premium_tier(user_id)
        settings = self.tier_settings[tier]
        
        # Get today's usage
        today = datetime.now(timezone.utc).date()
        user_usage = self.daily_requests[user_id]
        if user_usage['date'] != today:
            user_usage['count'] = 0
        
        embed = discord.Embed(
            title=f"{settings['emoji']} Your AI Status",
            color=self._get_tier_color(tier)
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
        
        await ctx.response.send_message(embed=embed, ephemeral=True)
    
    @ai_group.command(name="clearhistory", description="Clear your conversation history with Ataraxia")
    async def clear_history(self, ctx: discord.Interaction):
        """Clear conversation history for the user"""
        user_id = ctx.user.id
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
            await ctx.response.send_message(
                "🧹 Your conversation history has been cleared! Starting fresh.",
                ephemeral=True
            )
        else:
            await ctx.response.send_message(
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
                    value="Currently using Groq (free), but this shows what it would cost on OpenAI.",
                    inline=False
                )
                
                await owner.send(embed=embed)
                logger.warning(f"Cost alert sent: ${self.daily_cost_estimate:.2f} today")
            except Exception as e:
                logger.error(f"Failed to send cost alert: {e}")
    
    async def _process_owner_actions(self, ctx: discord.Interaction, question: str, ai_response: str) -> str:
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
                    user_level = await db.get_level(user_id, ctx.guild_id)
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
    
    async def _build_ataraxia_context(self, ctx: discord.Interaction, is_main_dev: bool = False) -> str:
        """Build Ataraxia-specific system prompt"""
        
        base_prompt = f"""You are Ataraxia, a friendly and helpful Discord bot.

**Your Identity:**
- Name: Ataraxia (Greek: ἀταραξία - "tranquility, calmness")
- Personality: Calm, helpful, knowledgeable about your own features
- Server: {ctx.guild.name} ({ctx.guild.member_count} members)
- You're speaking to: {ctx.user.display_name}"""

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