import discord
import asyncio
import random

from discord.ext import commands
from utils.bot import BoBit

class HorseRace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="race", aliases=["hr"])
    async def horse_race(self, ctx: commands.Context, horse: str = None):
        horses = ["Thunder", "Shadow", "Blaze", "Storm", "Star"]

        if not horse or horse.lower() not in [h.lower() for h in horses]:
            await ctx.reply(
                f'Please choose one of the following horses: `{", ".join(horses)}`'
            )
            return

        horse = next(h for h in horses if h.lower() == horse.lower())

        track_size = 20

        horse_pos = {h: track_size for h in horses}

        embed = discord.Embed(
            title="Racing your Horses!!! 🎠",
            description=f"Your bet: `{horse}`\n\n",
            color=discord.Color.random()
        )

        for _horse in horses:
            pos = horse_pos[_horse]

            embed.description += (
                "🚧"
                + "⠀" * pos
                + "🏇 "
                + "⠀" * (track_size - pos)
                + _horse
                + "\n"
            )

        msg = await ctx.send(embed=embed)

        winner = None
        await asyncio.sleep(1)

        while winner is None:

            embed.description = f"Your bet: `{horse}`\n\n"

            for _horse in horses:
                run = random.randint(0, 5)

                horse_pos[_horse] -= run
                horse_pos[_horse] = max(0, horse_pos[_horse])

                if horse_pos[_horse] == 0 and winner is None:
                    winner = _horse

                pos = horse_pos[_horse]

                embed.description += (
                    "🚧"
                    + "⠀" * pos
                    + "🏇 "
                    + "⠀" * (track_size - pos)
                    + _horse
                    + "\n"
                )

            await msg.edit(embed=embed)

            if winner is None:
                await asyncio.sleep(1)

        embed.description += f"\n**Winner: {winner}**"

        if winner.lower() == horse.lower():
            embed.description += "\nYou won! 🏆"
        else:
            embed.description += "\nYou lost! 😢"

        await msg.edit(embed=embed)

        




async def setup(bot: BoBit):
    await bot.add_cog(HorseRace(bot = bot))
    