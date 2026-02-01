import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import WELCOME_CHANNEL_ID


class Listeners(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            await welcome_channel.send(f"-# Welcome to server {member.mention}")


async def setup(bot: BoBit):
    await bot.add_cog(Listeners(bot))
