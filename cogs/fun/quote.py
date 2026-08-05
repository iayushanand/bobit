import discord

from discord.ext import commands
from io import BytesIO
from utils.bot import BoBit
from PIL import Image
from utils.helper import create_quote_buffer

class Quote(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot


    @commands.command(name = "quote")
    async def quote(self, ctx: commands.Context):
        reference = ctx.message.reference
        if not reference:
            return await ctx.reply(":x: Please reply to a message that you want to quote.")

        reply_message = await ctx.channel.fetch_message(reference.message_id)

        author = reply_message.author
        content = reply_message.content

        avatar_asset = author.display_avatar  # falls back to default avatar if needed
        avatar_bytes = await avatar_asset.read()

        av = Image.open(BytesIO(avatar_bytes)).convert("RGBA")

        file = create_quote_buffer(
            avatar = av,
            quote = content,
            display_name = author.global_name,
            username = author.name
        )

        await ctx.send(file = file)

async def setup(bot: BoBit):
    await bot.add_cog(Quote(bot=bot))
        