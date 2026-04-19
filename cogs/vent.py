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
                "You can also attach an image by pasting a link!"
            ),
            color=Colors.GREEN
        )
        embed.set_footer(text="All messages are 100% anonymous")

        await interaction.channel.send(embed=embed, view=VentButton()) 
        await interaction.response.send_message("✅ Vent panel created!", ephemeral=True)

    @commands.command(name="ventban", description="Ban someone from venting")
    @commands.has_permissions(administrator=True)
    async def ventban(self, ctx: commands.Context, *, reason=None):
        msg_id = ctx.message.reference.message_id
        data = await self.bot.db.vent.find_one({"message_id": msg_id})
        user = ctx.guild.get_member(data["user_id"])
        content = data["content"]
        image_url = data["image_url"]

        await self.bot.db.ventban.insert_one({"user_id": user.id, "message_id": msg_id, "content": content, "image_url": image_url, "reason": reason})
        embed_1 = discord.Embed(
            description = "✅ User was banned from venting.",
            color = Colors.GREEN
        )
        await ctx.reply(embed = embed_1)
        try:
            embed_2 = embed_1 = discord.Embed(
                description = "🔨 You have been banned from venting.",
                color = Colors.RED
            )
            await user.send(embed = embed_2)
        except: pass # type: ignore


async def setup(bot: BoBit):
    await bot.add_cog(Vent(bot))
