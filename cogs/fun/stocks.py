import discord
from discord.ext import commands
from utils.bot import BoBit

class Stocks(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.db = bot.db

    


async def setup(bot: BoBit):
    await bot.add_cog(Stocks(bot = bot))