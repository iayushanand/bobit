import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.helper import Spotify

class SpotifyShowcase(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    
    @commands.command(aliases=["sp"])
    @commands.cooldown(5, 60.0, type=commands.BucketType.user)
    async def spotify(self, ctx: commands.Context, member: discord.Member = None):
        """
        Shows the spotify status of a member.

        Usage:
        ------
        `{prefix}spotify`: *will show your spotify status*
        `{prefix}spotify [member]`: *will show the spotify status of [member]*
        """
        member = ctx.guild.get_member((member or ctx.author).id)

        spotify = Spotify(bot=self.bot, member=member)
        result = await spotify.get_embed()
        if not result:
            if member == ctx.author:
                return await ctx.reply(
                    "You are currently not listening to spotify!", mention_author=False
                )
            return await ctx.reply(
                f"{member.mention} is not listening to Spotify",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        file, view = result
        await ctx.send(file=file, view=view)

async def setup(bot: BoBit):
    await bot.add_cog(SpotifyShowcase(bot = bot))