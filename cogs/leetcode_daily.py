import discord
from discord.ext import commands, tasks

import aiohttp
import html
import re
import datetime

LEETCODE_DAILY_API = "https://alfa-leetcode-api.onrender.com/daily"
LEETCODE_ICON = "https://upload.wikimedia.org/wikipedia/commons/8/8e/LeetCode_Logo_1.png"


class LeetCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_post.start()

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

    @tasks.loop(time=datetime.time(hour=8, minute=0))
    async def daily_post(self):
        channel_id = 1447626752670306414
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        data = await self.fetch_leetcode_daily()
        if not data:
            return

        description = self.leetcode_html_to_discord_md(
            data.get("questionDescription", "")
        )

        if len(description) > 4096:
            description = description[:4000] + "\n\n*(Truncated)*"

        tags = ", ".join(data.get("topicTags", [])) or "N/A"

        hints = data.get("hints", [])
        if hints:
            hints_value = "\n".join(f"- ||{h}||" for h in hints)
        else:
            hints_value = "No hints provided."

        embed = discord.Embed(
            title=data["questionTitle"],
            description=description,
            color=0xF89F1B
        )

        embed.set_author(
            name="Question of the Day",
            icon_url=LEETCODE_ICON,
            url=data["questionLink"]
        )

        embed.add_field(
            name="Tags",
            value=f"-# {tags}",
            inline=True
        )

        embed.add_field(
            name="Hints",
            value=hints_value,
            inline=True
        )

        embed.set_footer(
            text=f"Difficulty - {data['difficulty']}"
        )

        await channel.send(embed=embed)

    @daily_post.before_loop
    async def before_daily_post(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeetCode(bot))
