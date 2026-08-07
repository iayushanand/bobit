import re
import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.ui.piston import Piston

class Compiler(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.regex = {
            "codeblock": re.compile(r"(\w*)\s*(?:```)(\w*)?([\s\S]*)(?:```$)")
        }

    @commands.command()
    async def run(self, ctx, *, codeblock: str):
        msg = await ctx.reply("...")
        matches = self.regex["codeblock"].findall(codeblock)
        lang = matches[0][0] or matches[0][1]
        if not matches:
            return await msg.edit(
                embed=self.bot.embed(title="```ansi\nInvalid codeblock\n```")
            )
        if not lang:
            return await msg.edit(
                embed=self.bot.embed(title="```ansi\nno language specified\n```")
            )
        code = matches[0][2]
        await msg.edit(
            view=Piston(
                self,
                code,
                lang,
                msg,
                ctx.author,
            ),
        )


async def setup(bot: BoBit):
    await bot.add_cog(Compiler(bot=bot))