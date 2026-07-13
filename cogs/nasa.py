import discord
from discord.ext import commands, tasks
from utils.bot import BoBit
from utils.consts import NASA_POD
from dotenv import load_dotenv
import os

load_dotenv()

class Nasa(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.api_key = os.getenv("NASA_API_KEY")

    @commands.Cog.listener(name = "on_ready")
    async def on_ready(self):
        self.pod.start()
        self.iss_loop.start()
    
    @commands.command(name = "pod")
    async def pod(self, ctx: commands.Context):
        fetch_url = NASA_POD+f"?api_key={self.api_key}"

        response = await self.bot.session.get(fetch_url)
        data = await response.json()
        await ctx.send(data)

        embed = discord.Embed(
            title = data["title"],
            description = data["explanation"],
            color = discord.Color.dark_blue(),
            url=data["url"]
        ).set_image(
            url = data["url"]
        ).set_footer(
            text=data["date"]
        )

        await ctx.reply(embed = embed)

    
    @commands.command(name = "iss")
    async def iss(self, ctx: commands.Context):
        async with self.bot.session.get(
                "https://api.wheretheiss.at/v1/satellites/25544"
            ) as response:
                json = await response.json()
        lat = json["latitude"]
        lon = json["longitude"]
        zoom = "3"

        url = f"https://static-maps.yandex.ru/1.x/?z={zoom}&lang=en_US&ll={lon},{lat}&size=450,450&l=sat,trf,skl&pt={lon},{lat},vkbkm"
        em = (
            discord.Embed(
                description="Current Location of the ISS",
                color=discord.Color.random(),
                timestamp=ctx.message.created_at,
            )
            .add_field(name="Latitude", value=json["latitude"], inline=False)
            .add_field(name="Longitude", value=json["longitude"], inline=False)
            .add_field(
                name="Altitude", value=str(json["altitude"]) + " km", inline=False
            )
            .add_field(
                name="Velocity", value=str(json["velocity"]) + " km/h", inline=False
            )
            .add_field(name="Visibility", value=json["visibility"], inline=False)
            .set_thumbnail(
                url="https://www.nasa.gov/sites/default/files/thumbnails/image/nasa-logo-web-rgb.png"
            )
            .set_image(
                url="http://www.nasa.gov/sites/default/files/thumbnails/image/final_configuration_of_iss.jpg"
            )
            .set_image(url=url)
        )
        await ctx.send(embed=em)
    

    @tasks.loop(minutes=5)
    async def iss_loop(self):
        channel = self.bot.get_channel(1525828633485119528)
        message = await channel.fetch_message(1525830057732608041)
        async with self.bot.session.get(
                "https://api.wheretheiss.at/v1/satellites/25544"
            ) as response:
                json = await response.json()
        lat = json["latitude"]
        lon = json["longitude"]
        zoom = "3"

        url = f"https://static-maps.yandex.ru/1.x/?z={zoom}&lang=en_US&ll={lon},{lat}&size=450,450&l=sat,trf,skl&pt={lon},{lat},vkbkm"
        em = (
            discord.Embed(
                description="Current Location of the ISS",
                color=discord.Color.random(),
                timestamp=discord.utils.datetime.datetime.now(),
            )
            .add_field(name="Latitude", value=json["latitude"], inline=False)
            .add_field(name="Longitude", value=json["longitude"], inline=False)
            .add_field(
                name="Altitude", value=str(json["altitude"]) + " km", inline=False
            )
            .add_field(
                name="Velocity", value=str(json["velocity"]) + " km/h", inline=False
            )
            .add_field(name="Visibility", value=json["visibility"], inline=False)
            .set_thumbnail(
                url="https://www.nasa.gov/sites/default/files/thumbnails/image/nasa-logo-web-rgb.png"
            )
            .set_image(
                url="http://www.nasa.gov/sites/default/files/thumbnails/image/final_configuration_of_iss.jpg"
            )
            .set_image(url=url)
        )
        await message.edit(embed=em)


    @tasks.loop(hours=24)
    async def pod(self):
        thread = self.bot.get_channel(1525802023163789393)
        fetch_url = NASA_POD+f"?api_key={self.api_key}"

        response = await self.bot.session.get(fetch_url)
        data = await response.json()

        embed = discord.Embed(
            title = data["title"],
            description = data["explanation"],
            color = discord.Color.dark_blue(),
            url=data["url"]
        ).set_image(
            url = data["url"]
        ).set_footer(
            text=data["date"]
        )

        await thread.send(embed = embed)

async def setup(bot: BoBit):
    await bot.add_cog(Nasa(bot))