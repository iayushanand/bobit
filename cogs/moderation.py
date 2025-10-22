import discord
from discord.ext import commands
from utils.bot import BoBit

class Moderation(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
    
    @commands.command(name = "kick")
    async def kick(self, ctx: commands.Context):
        ...


async def setup(bot):
    await bot.add_cog(Moderation(bot=bot))
    