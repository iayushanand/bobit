import discord
from discord.ext import commands
from discord import app_commands
from utils.bot import BoBit
from utils.consts import Colors
from utils.ui.vent import VentButton


class Vent(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VentButton())

    @app_commands.command(name="ventpanel", description="Set up the anonymous vent panel")
    @app_commands.default_permissions(administrator=True)
    async def ventpanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🫂 Anonymous Venting",
            description=(
                "Need to get something off your chest?\n\n"
                "Click the button below to share your thoughts **completely anonymously**. "
            ),
            color=Colors.GREEN
        )
        embed.set_footer(text="All messages are 100% anonymous")

        await interaction.channel.send(embed=embed, view=VentButton())
        await interaction.response.send_message("✅ Vent panel created!", ephemeral=True)


async def setup(bot: BoBit):
    await bot.add_cog(Vent(bot))
