import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiohttp
import html
import re
import datetime

LEETCODE_DAILY_API = "https://alfa-leetcode-api.onrender.com/daily"


class LeetCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_post.start()  # uncomment if you want auto-posting

    def leetcode_html_to_discord_md(self, text: str) -> str:
        text = html.unescape(text)

        replacements = {
            "<strong>": "**",
            "</strong>": "**",
            "<code>": "`",
            "</code>": "`",
            "<pre>": "```",
            "</pre>": "```",
            "<p>": "",
            "</p>": "\n",
            "<ul>": "",
            "</ul>": "",
            "<li>": "- ",
            "</li>": "\n",
            "&nbsp;": "",
        }

        for k, v in replacements.items():
            text = text.replace(k, v)

        text = re.sub(r"<sup>2</sup>", "²", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    async def fetch_leetcode_daily(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(LEETCODE_DAILY_API, timeout=10) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    # @app_commands.command(
    #     name="leetcode-daily",
    #     description="Get today's LeetCode Question of the Day"
    # )
    # async def leetcode_daily(self, interaction: discord.Interaction):
    #     await interaction.response.defer()

    #     data = await self.fetch_leetcode_daily()
    #     if not data:
    #         await interaction.followup.send(
    #             "❌ Could not fetch today's LeetCode Daily."
    #         )
    #         return

    #     description = self.leetcode_html_to_discord_md(
    #         data.get("questionDescription", "")
    #     )

    #     if len(description) > 4096:
    #         description = description[:4000] + "\n\n*(Truncated)*"

    #     embed = discord.Embed(
    #         title=f"📘 {data['questionTitle']}",
    #         url=data["questionLink"],
    #         description=description,
    #         color=0xF89F1B
    #     )

    #     embed.add_field(
    #         name="Difficulty",
    #         value=data["difficulty"],
    #         inline=True
    #     )

    #     embed.add_field(
    #         name="Tags",
    #         value=", ".join(data.get("topicTags", [])) or "N/A",
    #         inline=True
    #     )

    #     embed.set_footer(text="LeetCode Question of the Day")

    #     await interaction.followup.send(embed=embed)

    @tasks.loop(time=datetime.time(hour=8, minute=0))
    async def daily_post(self):
        channel_id = 1234567890
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        data = await self.fetch_leetcode_daily()
        if not data:
            return

        embed = discord.Embed(
            title=f"📘 LeetCode Daily: {data['questionTitle']}",
            url=data["questionLink"],
            color=0xF89F1B
        )

        await channel.send(embed=embed)

    @daily_post.before_loop
    async def before_daily_post(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeetCode(bot))
