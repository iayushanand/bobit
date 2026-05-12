import discord
from discord.ext import commands
from io import BytesIO
from utils.bot import BoBit
from utils.consts import WELCOME_CHANNEL_ID
from utils.welcomer import WeclomeBanner


class Listeners(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot
        self.banner = WeclomeBanner()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            avatar_bytes = await member.display_avatar.read()
            avatar = BytesIO(avatar_bytes)
            file = self.banner.make_banner(member.name, avatar)
            await welcome_channel.send(
                content=f"-# Welcome to server {member.mention}",
                file=file
            )


async def setup(bot: BoBit):
    await bot.add_cog(Listeners(bot))
