import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import LOG_CHANNEL_ID, Colors
from datetime import datetime
import time


class Moderation(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    async def log_action(
        self,
        *,
        action: str,
        moderator: discord.Member,
        target: discord.Member | None,
        reason: str,
        channel: discord.TextChannel
    ):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(
            title="📋 Moderation Log",
            color=Colors.RED,
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(
            name="Target",
            value=target.mention if target else "N/A",
            inline=True
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)

        await log_channel.send(embed=embed)

    @commands.command(name="kick")
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        await member.kick(reason=reason)

        embed = discord.Embed(
            title="✅ Member Kicked",
            color=Colors.GREEN
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason or "None")

        await ctx.send(embed=embed)
        await self.log_action(
            action="Kick",
            moderator=ctx.author,
            target=member,
            reason=reason,
            channel=ctx.channel
        )

    @commands.command(name="ban")
    async def ban(self, ctx, member: discord.Member, *, reason: str = None):
        await member.ban(reason=reason)

        embed = discord.Embed(
            title="🔨 Member Banned",
            color=Colors.GREEN
        )
        embed.add_field(name="User", value=f"{member} (`{member.id}`)")
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason or "None")

        await ctx.send(embed=embed)
        await self.log_action(
            action="Ban",
            moderator=ctx.author,
            target=member,
            reason=reason,
            channel=ctx.channel
        )

    @commands.command(name="timeout")
    async def timeout(
        self,
        ctx,
        member: discord.Member,
        minutes: int,
        *,
        reason: str = None
    ):
        until = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await member.edit(timeout=until, reason=reason)

        embed = discord.Embed(
            title="⏳ Member Timed Out",
            color=Colors.GREEN
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minutes")
        embed.add_field(name="Reason", value=reason or "None")

        await ctx.send(embed=embed)
        await self.log_action(
            action=f"Timeout ({minutes}m)",
            moderator=ctx.author,
            target=member,
            reason=reason,
            channel=ctx.channel
        )

    @commands.command(name="slowmode",aliases=["sm"])
    async def slowmode(self, ctx, seconds: int = 0):
        await ctx.channel.edit(slowmode_delay=seconds)

        embed = discord.Embed(
            title="🐌 Slowmode Updated",
            color=Colors.GREEN
        )
        embed.add_field(name="Channel", value=ctx.channel.mention)
        embed.add_field(name="Delay", value=f"{seconds} seconds")

        await ctx.send(embed=embed)
        await self.log_action(
            action="Set Slowmode",
            moderator=ctx.author,
            target=None,
            reason=f"{seconds}s slowmode",
            channel=ctx.channel
        )

    @commands.command(name="warn")
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        warn_data = {
            "reason": reason,
            "moderator_id": ctx.author.id,
            "timestamp": int(time.time())
        }

        await self.bot.db.collection.update_one(
            {"_id": member.id},
            {"$push": {"warns": warn_data}},
            upsert=True
        )

        embed = discord.Embed(
            title="⚠️ User Warned",
            color=Colors.YELLOW
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Reason", value=reason)

        await ctx.send(embed=embed)
        await self.log_action(
            action="Warn",
            moderator=ctx.author,
            target=member,
            reason=reason,
            channel=ctx.channel
        )

    @commands.command(name="warns")
    async def warns(self, ctx, member: discord.Member):
        doc = await self.bot.db.collection.find_one({"_id": member.id})
        warns = doc["warns"] if doc else []

        embed = discord.Embed(
            title=f"⚠️ Warnings for {member}",
            color=Colors.YELLOW
        )

        if not warns:
            embed.description = "No warnings."
        else:
            for i, warn in enumerate(warns, 1):
                embed.add_field(
                    name=f"Warning #{i}",
                    value=(
                        f"**Reason:** {warn['reason']}\n"
                        f"**Moderator:** <@{warn['moderator_id']}>"
                    ),
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(name="warnremove")
    async def warnremove(self, ctx, member: discord.Member, index: int):
        doc = await self.bot.db.collection.find_one({"_id": member.id})
        if not doc:
            return

        warns = doc["warns"]
        warns.pop(index - 1)

        await self.bot.db.collection.update_one(
            {"_id": member.id},
            {"$set": {"warns": warns}}
        )

        embed = discord.Embed(
            title="🗑️ Warning Removed",
            color=Colors.GREEN
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Removed Index", value=index)

        await ctx.send(embed=embed)

    @commands.command(name="warnclear")
    async def warnclear(self, ctx, member: discord.Member):
        await self.bot.db.collection.delete_one({"_id": member.id})

        embed = discord.Embed(
            title="✅ Warnings Cleared",
            color=Colors.GREEN
        )
        embed.add_field(name="User", value=member.mention)

        await ctx.send(embed=embed)


async def setup(bot: BoBit):
    await bot.add_cog(Moderation(bot))
