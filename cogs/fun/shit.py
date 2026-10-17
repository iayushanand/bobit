import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import SHITMEME_IMAGE_PATH
from PIL import Image
from io import BytesIO

class ShitMeme(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot


    @commands.command(name = "shit")
    async def create_shit(self, ctx: commands.Context, member: discord.Member):
        template = Image.open(SHITMEME_IMAGE_PATH)

        avatar_bytes = await member.display_avatar.read()
        avatar = BytesIO(avatar_bytes)

        av = Image.open(avatar)
        av = av.resize((75,75)).convert("RGBA").rotate(45, expand=True)
        template.paste(av, (214,624), av)

        with BytesIO() as image_binary:
            template.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="welcome.png")

        await ctx.send(file = file)


async def setup(bot: BoBit):
    await bot.add_cog(ShitMeme(bot = bot))