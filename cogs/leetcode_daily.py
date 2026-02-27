import discord
from discord.ext import commands, tasks
from utils.consts import LEETCODE_CHANNEL_ID, LEETCODE_DAILY_API, LEETCODE_UPCOMING_API, LEETCODE_ROLE_ID, LEETCODE_ICON, Colors

import aiohttp
import html
import re
import datetime
import time


class LeetCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notified_contests = set()
        self.daily_post.start()
        self.check_contests_loop.start()

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

    async def fetch_upcoming_contests(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(LEETCODE_UPCOMING_API, timeout=10) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    @tasks.loop(hours=1)
    async def check_contests_loop(self):
        channel = self.bot.get_channel(LEETCODE_CHANNEL_ID)
        if not channel:
            return

        data = await self.fetch_upcoming_contests()
        if not data or "contests" not in data:
            return

        current_time = int(time.time())

        for contest in data["contests"]:
            start_time = contest.get("startTime", 0)
            duration = contest.get("duration", 0)
            title = contest.get("title", "Unknown Contest")
            slug = contest.get("titleSlug", "unknown-contest")

            if start_time <= current_time <= start_time + duration:
                if slug not in self.notified_contests:
                    self.notified_contests.add(slug)
                    
                    embed = discord.Embed(
                        title=f"🚀 {title} is now LIVE!",
                        description=f"The contest has started and will run for {duration // 60} minutes.\nGood luck and have fun!",
                        color=Colors.LEETCODE,
                        url=f"https://leetcode.com/contest/{slug}/"
                    )
                    embed.set_author(name="LeetCode Contest", icon_url=LEETCODE_ICON)
                    
                    await channel.send(content=f"<@&{LEETCODE_ROLE_ID}>", embed=embed)

    @tasks.loop(time=datetime.time(hour=8, minute=0))
    async def daily_post(self):
        channel = self.bot.get_channel(LEETCODE_CHANNEL_ID)
        if not channel:
            return

        data = await self.fetch_leetcode_daily()
        if not data:
            return
        
        tags = []
        for i in data.get("topicTags", {}):
            tags.append(i["name"])

        description = ""
        if tags:
            description = "-# **Tags:**" + ", ".join(tags) + "\n\n"
        description += self.leetcode_html_to_discord_md(
            data.get("question", "")
        )

        
        if len(description) > 4096:
            description = description[:4000] + "\n\n*(Truncated)*"
        
        # tags = ", ".join(data.get("topicTags", [])) or "N/A"

        hints = data.get("hints", [])
        if hints:
            hints_value = "\n".join(f"- ||{h}||" for h in hints)
        else:
            hints_value = "No hints provided."

        embed = discord.Embed(
            title=data["questionTitle"],
            description=description,
            color=Colors.LEETCODE
        )

        embed.set_author(
            name="Question of the Day",
            icon_url=LEETCODE_ICON,
            url=data["questionLink"]
        )

        # embed.add_field(
        #     name="Tags",
        #     value=f"-# {', '.join(tags) or "N/A"}",
        #     inline=True
        # )

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

    @check_contests_loop.before_loop
    async def before_check_contests(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeetCode(bot))
