import discord
import random
import asyncio
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import ROULETTE_EMOJI, ROULETTE_RED_NUMBERS, ROULETTE_BLACK_NUMBERS, ROULETTE_GREEN_NUMBERS, ROULETTE_NUMBER_MULTIPLIER, ROULETTE_COLOR_MULTIPLIER, ROULETTE_DEFAULT_BET

class Roulette(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    @commands.command(name = "roulette", aliases=["rou"])
    async def roulette(self, ctx: commands.Context, bet: str = None, amount: int = None):
        roulette_color = {
            "red": ROULETTE_RED_NUMBERS,
            "black": ROULETTE_BLACK_NUMBERS,
            "green": ROULETTE_GREEN_NUMBERS
        }

        if not bet:
            await ctx.reply(f":x: Invalid bet! You can bet on `red, black, green, even, odd` or a number between `0 and 36`")
            return

        if not amount:
            amount = ROULETTE_DEFAULT_BET

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
            description=f"# {ROULETTE_EMOJI}",
            color = discord.Color.random()
        )
        msg = await ctx.reply(embed = embed)
        embed.description = f"🎱 **`{winning_bet}`** {ROULETTE_EMOJI} **`{color.upper()}` 🔢 `{parity.upper()}`**\n\n"
        await asyncio.sleep(5)

        if bet.isdigit():
            if 0<=int(bet)<=36:
                if int(bet) == winning_bet:
                    multiplier = ROULETTE_NUMBER_MULTIPLIER
                    embed.description+=f"**🎊 YOU WON!!!**\n 💰 **₹{(multiplier * amount):,}**!"
                else:
                    embed.description+=f"**You lost!!!**"
                await msg.edit(embeds = [embed])
            else:
                await ctx.reply(":x: Pick a number between 0 and 36")
                return
        elif bet in ["red", "black", "green", "even", "odd"]:
            if bet == color or bet == parity:
                multiplier = ROULETTE_COLOR_MULTIPLIER
                embed.description += f"**🎊 YOU WON!!!**\n 💰 **₹{(multiplier * amount):,}**!"
            else:
                embed.description += "You lost!!!"

            await msg.edit(embed=embed)
                    
        else:
            await ctx.reply(f":x: Invalid bet! You can bet on `red, black, green, even, odd` or a number between `0 and 36`")
            return

            
        

async def setup(bot: BoBit):
    await bot.add_cog(Roulette(bot=bot))