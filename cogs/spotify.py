import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.helper import Spotify, get_lyrics, find_surrounding_lyrics
import time

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
    

    @commands.command(name = "lyric", aliases = ["lyrics", "ly"])
    async def lyric(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        
        spotify_activity = None
        for activity in member.activities:
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break

        if not spotify_activity:
            await ctx.send(f"{member.display_name} is not listening to Spotify.")
            return
    
        else:
            duration = time.time()-spotify_activity.start.timestamp()
            song_title = spotify_activity.title
            song_artist = spotify_activity.artist
            lyr = get_lyrics(song_title, song_artist)
            if not lyr:
                return await ctx.send(f"Lyrics not found for song - {song_title} - {song_artist}")
            if lyr[1] == 1:
                lyr = "\n".join(find_surrounding_lyrics(lyr[0], int(duration)))
            else:
                lyr = "\n".join(lyr[0].splitlines()[0:5])

            embed = discord.Embed(description = lyr, title = f"{song_title} - {song_artist}", color = spotify_activity.color)
            embed.set_author(name = ctx.author, icon_url = ctx.author.avatar.url)
            embed.set_thumbnail(url = spotify_activity.album_cover_url)

            await ctx.send(embed = embed)

async def setup(bot: BoBit):
    await bot.add_cog(SpotifyShowcase(bot = bot))