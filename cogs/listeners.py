import discord
from discord.ext import commands
from utils.bot import BoBit
from io import BytesIO
from utils.welcomer import WeclomeBanner


class Listeners(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot
    
    @commands.Cog.listener(name = "on_member_join")
    async def member_join(self, member: discord.Member):
        welcome_channel =  member.guild.get_channel(1430077291165388821)
        
        
        """ === For Banner === """

        # pfp = BytesIO(await member.display_avatar.read())
        # username = member.name

        # welcomer = WeclomeBanner().make_banner(username, pfp)

        # await welcome_channel.send(file=welcomer)


        """ === For Simple Message === """
        await welcome_channel.send(f"-# Welcome to server {member.mention}")



async def setup(bot):
    await bot.add_cog(Listeners(bot=bot))
