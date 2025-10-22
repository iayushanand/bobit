import discord
from discord.ext import commands
from utils.bot import BoBit

class Moderation(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
    
    @commands.command(name = "kick")
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = None):
        ...

    @commands.command(name = "purge")
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx: commands.Context, limit: str = "1"):
        limit = int(limit) if limit != "all" else 100
        await ctx.message.delete()
        await ctx.channel.purge(limit = limit)
        await ctx.channel.send(f"✅ Purged {limit} messages.", delete_after=3)


async def setup(bot):
    await bot.add_cog(Moderation(bot=bot))
    