import discord
from discord.ext import commands
from utils.ui.ticket import CreateButton, CloseButton, TrashButton


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(CreateButton())
        self.bot.add_view(CloseButton())
        self.bot.add_view(TrashButton())

    @commands.command(name="ticket")
    @commands.has_permissions(administrator=True)
    async def ticket(self, ctx):
        embed = discord.Embed(
            description=(
                "🎫 **Click on the button below to create a ticket**\n"
                "If you need any help regarding punishments, roles, or you just have a "
                "general question, feel free to create a ticket and a staff member will "
                "get to you shortly!\n\n"
                "Opening a ticket without a valid reason will get you warned/blacklisted.\n\n"
                "__**Do not open support tickets for Coding Help. Doing so will get you warned.**__"
            ),
            color=0x8b6ffc
        )
        await ctx.send(embed=embed, view=CreateButton())


async def setup(bot):
    await bot.add_cog(TicketCog(bot))