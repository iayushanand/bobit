import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import SLOT_EMOJI, SLOT_EMOJIS, SLOT_WEIGHTS, SLOT_PAYOUTS, SLOT_DEFAULT_BET, Colors
import random
import asyncio


class SlotMachine(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot

    @commands.command(name="slot")
    async def slot(self, ctx: commands.Context, amount: int = None):

        # pls follow PEP8 and set amount inside the function instead of
        # the function arguments for cleaner, more understandable code ~ ayu
        if amount is None:
            amount = SLOT_DEFAULT_BET

        emojis = SLOT_EMOJIS
        # feel free to tweak these weights.
        weights = SLOT_WEIGHTS
        # currently - 
        # the total weight is 114... so the probability of each symbol on a single reel is:

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
        # ⭐⭐⭐	 0.0232% (≈ 1 in 4,316)
        # 🔔🔔🔔	0.0675% (≈ 1 in 1,481)
        # 🍇🍇🍇	0.5397% (≈ 1 in 185)
        # 🍑🍑🍑	1.4817% (≈ 1 in 67) [six seven 👅]
        # 🍒🍒🍒	6.1480% (≈ 1 in 16)

        payouts = SLOT_PAYOUTS

        # roll the result before the animation
        slot = random.choices(emojis, weights=weights, k=3)

        embed = discord.Embed(
            description=(
                f"# {SLOT_EMOJI} {SLOT_EMOJI} {SLOT_EMOJI}\n\n"
                f"-# Betting **₹{amount:,}**"
            ),
            color=Colors.GOLD,
        )

        msg = await ctx.reply(embed=embed)

        # give the animated emoji some time to spin
        await asyncio.sleep(1.2)

        # reveal reel 1
        embed.description = (
            f"# {slot[0]} {SLOT_EMOJI} {SLOT_EMOJI}\n\n"
            f"-# Betting **₹{amount:,}**"
        )
        await msg.edit(embed=embed)

        await asyncio.sleep(0.6)

        # reveal reel 2
        embed.description = (
            f"# {slot[0]} {slot[1]} {SLOT_EMOJI}\n\n"
            f"-# Betting **₹{amount:,}**"
        )
        await msg.edit(embed=embed)

        await asyncio.sleep(0.6)

        # reveal reel 3
        embed.description = (
            f"# {' '.join(slot)}\n\n"
            f"-# Betting **₹{amount:,}**"
        )
        await msg.edit(embed=embed)

        await asyncio.sleep(0.4)

        # result
        if len(set(slot)) == 1:
            multiplier = payouts[slot[0]]
            winnings = amount * multiplier

            embed.color = Colors.GREEN
            embed.description += (
                "\n\n"
                "**🎉 You Won!**\n"
                f"**Multiplier:** ×{multiplier}\n"
                f"**Payout:** ₹{winnings:,}"
            )
        else:
            embed.color = Colors.RED
            embed.description += (
                "\n\n"
                "**❌ You Lost!**\n"
                "Better luck next spin!"
            )

        await msg.edit(embed=embed)


async def setup(bot: BoBit):
    await bot.add_cog(SlotMachine(bot=bot))