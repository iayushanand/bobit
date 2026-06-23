import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import Colors
import time


class AFK(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    @commands.command(name="afk")
    async def afk(self, ctx: commands.Context, *, reason: str = "No reason provided"):
        existing = await self.bot.db.afk.find_one({"_id": ctx.author.id})
        if existing:
            embed = discord.Embed(
                description="❌ You are already AFK!",
                color=Colors.RED
            )
            await ctx.send(embed=embed)
            return

        original_name = ctx.author.display_name
        afk_time = int(time.time())

        await self.bot.db.afk.insert_one({
            "_id": ctx.author.id,
            "reason": reason,
            "original_name": original_name,
            "afk_at": afk_time
        })

        try:
            await ctx.author.edit(nick=f"[AFK] {original_name}"[:32])
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            description=f"{ctx.author.mention}, I've set your AFK: **{reason}**",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        for user in message.mentions:
            data = await self.bot.db.afk.find_one({"_id": user.id})
            if data:
                embed = discord.Embed(
                    description=f"{user.mention} is AFK: **{data['reason']}** (<t:{data['afk_at']}:R>)",
                    color=discord.Color.blurple()
                )
                await message.reply(embed=embed, mention_author=False)

        data = await self.bot.db.afk.find_one({"_id": message.author.id})
        if data:
            if time.time() - data["afk_at"] < 60:
                return

            await self.bot.db.afk.delete_one({"_id": message.author.id})

            try:
                await message.author.edit(nick=data["original_name"] if data["original_name"] != message.author.name else None)
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                description=f"Welcome back! I've removed your AFK.",
                color=discord.Color.blue()
            )
            await message.reply(embed=embed, mention_author=False, delete_after=5)


async def setup(bot: BoBit):
    await bot.add_cog(AFK(bot))
