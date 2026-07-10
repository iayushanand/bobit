import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.ui.faculty import FacultyView, build_department_embed
import json

class Faculty(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        
    @commands.command(name = "faculty", aliases=["fc"])
    async def faculty_info(self, ctx: commands.Context, department: str = None):
        departments = ["civil", "mech", "eee", "ece", "cse", "eie", "iem", "ete", "ise", "ai", "cyb", "ds", "rai", "vlsi", "mba", "mca", "phy", "chem", "math"]
        if department not in departments:
            fail_embed = discord.Embed(
                description = ":x: Please choose a faculty from the following - `{0}`".format(", ".join(departments))
            )
            return await ctx.reply(embed = fail_embed)
        
        with open("assets/data/bit.json", 'r', encoding="utf-8") as f:
            data = json.load(f)
        
        dept = next((d for d in data if d["id"] == department), None)
        if not dept:
            return await ctx.reply(":x: Something went wrong :(")

        embed = build_department_embed(dept)
        view = FacultyView(dept, ctx.author.id)
        await ctx.reply(embed=embed, view=view)


async def setup(bot: BoBit):
    await bot.add_cog(Faculty(bot=bot))