import discord
import random
import asyncio
from discord.ext import commands
from utils.bot import BoBit

class Roulette(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    @commands.command(name = "roulette", aliases=["rou"])
    async def roulette(self, ctx: commands.Context, bet: str = None, amount: int = None):
        roulette_color = {
            "red": [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36],
            "black": [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35],
            "green": [0]
        }

        if not bet:
            await ctx.reply(f":x: Invalid bet! You can bet on `red, black, green, even, odd` or a number between `0 and 36`")
            return

        if not amount:
            amount = 100

        winning_bet = random.randint(0,36)
        color = None
        parity = None
        if winning_bet in roulette_color["red"]:
            color = "red"
        elif winning_bet in roulette_color["black"]:
            color = "black"
        else:
            color = "green"
        if winning_bet % 2 == 0:
            parity = "even"
        else:
            parity = "odd"
        embed = discord.Embed(
            title = "Roulette",
            description="# <a:roulette:1535732657957109760>",
            color = discord.Color.random()
        )
        msg = await ctx.reply(embed = embed)
        embed.description = f"🎱 **`{winning_bet}`** <a:roulette:1535732657957109760> **`{color.upper()}` 🔢 `{parity.upper()}`**\n\n"
        await asyncio.sleep(5)

        if bet.isdigit():
            if 0<=int(bet)<=36:
                if int(bet) == winning_bet:
                    multiplier = 5
                    embed.description+=f"**🎊 YOU WON!!!**\n 💰 **₹{(multiplier * amount):,}**!"
                else:
                    embed.description+=f"**You lost!!!**"
                await msg.edit(embeds = [embed])
            else:
                await ctx.reply(":x: Pick a number between 0 and 36")
                return
        elif bet in ["red", "black", "green", "even", "odd"]:
            if bet == color or bet == parity:
                multiplier = 2
                embed.description += f"**🎊 YOU WON!!!**\n 💰 **₹{(multiplier * amount):,}**!"
            else:
                embed.description += "You lost!!!"

            await msg.edit(embed=embed)
                    
        else:
            await ctx.reply(f":x: Invalid bet! You can bet on `red, black, green, even, odd` or a number between `0 and 36`")
            return

            
        

async def setup(bot: BoBit):
    await bot.add_cog(Roulette(bot=bot))