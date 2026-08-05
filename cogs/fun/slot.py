import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import SLOT_EMOJI
import random
import asyncio


class SlotMachine(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot

    @commands.command(name = "slot")
    async def slot(self, ctx: commands.Context, amount: int = None):


        # please follow PEP8 and set amount inside the function and not in the function arguments for a cleaner more understandable code ~ ayu
        if not amount:
            amount = 10

        embed = discord.Embed(
            description=f"# {SLOT_EMOJI} {SLOT_EMOJI} {SLOT_EMOJI}\n\n-# Slotting - ₹{amount}",
            color = discord.Color.red()
        )

        msg = await ctx.reply(embed = embed)

        await asyncio.sleep(3)

        emojis = ["💎", "⭐", "🔔", "🍇", "🍑", "🍒"]
        weights = [4, 7, 10, 20, 28, 45] # feel free to play with weights to find the sweet spot of winning and losing 
        # currently - 
        # The total weight is 114... so the probability of each symbol on a single reel is:

        # Emoji	Weight	Chance
        # 💎	4	3.51%
        # ⭐    7   6.14%
        # 🔔	10	8.77%
        # 🍇	20	17.54%
        # 🍑	28	24.56%
        # 🍒	45	39.47%

        # The chance of getting three of the same is:
        # Combination	Chance
        # 💎💎💎	0.0043% (≈ 1 in 23,149)
        # ⭐⭐⭐	0.0232% (≈ 1 in 4,316)
        # 🔔🔔🔔	0.0675% (≈ 1 in 1,481)
        # 🍇🍇🍇	0.5397% (≈ 1 in 185)
        # 🍑🍑🍑	1.4817% (≈ 1 in 67) [six seven 👅]
        # 🍒🍒🍒	6.1480% (≈ 1 in 16)

        _slot = random.choices(emojis, weights, k=3)
        payouts = {
            "🍒": 2,
            "🍑": 3,
            "🍇": 5,
            "🔔": 10,
            "⭐": 25,
            "💎": 100,
        }

        final_embed = discord.Embed(
            description = f"# {' '.join(_slot)}\n\n"
        )

        if len(set(_slot)) == 1:
            multiplier = payouts[_slot[0]]
            final_embed.description += f"**You won!**\n-# Payout: ₹{amount*multiplier}"

        else:
            final_embed.description += f"**You lost!**\n-# Try giving it another try 🤑"

        await msg.edit(embeds=[final_embed])


async def setup(bot: BoBit):
    await bot.add_cog(SlotMachine(bot=bot))