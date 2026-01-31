import discord
from discord.ext import commands, tasks
from utils.bot import BoBit
from utils.consts import Colors
from collections import defaultdict
import time


class AntiSpam(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.message_tracker: dict[int, list[float]] = defaultdict(list)
        self.auto_slowmode_channels: set[int] = set()
        self.original_slowmode: dict[int, int] = {}
        self.cooldown_check.start()

    def cog_unload(self):
        self.cooldown_check.cancel()

    async def cog_load(self):
        async for doc in self.bot.db.auto_slowmode.find():
            channel_id = doc["channel_id"]
            self.auto_slowmode_channels.add(channel_id)
            self.original_slowmode[channel_id] = doc["original_slowmode"]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return

        if channel.slowmode_delay > 0 and channel.id not in self.auto_slowmode_channels:
            return

        current_time = time.time()
        self.message_tracker[channel.id].append(current_time)

        self.message_tracker[channel.id] = [
            t for t in self.message_tracker[channel.id] 
            if current_time - t <= 15
        ]

        if len(self.message_tracker[channel.id]) > 5 and channel.id not in self.auto_slowmode_channels:
            original = channel.slowmode_delay
            self.original_slowmode[channel.id] = original
            
            await channel.edit(slowmode_delay=5, reason="Auto-slowmode: High traffic detected")
            self.auto_slowmode_channels.add(channel.id)
            
            await self.bot.db.auto_slowmode.insert_one({
                "channel_id": channel.id,
                "original_slowmode": original,
                "activated_at": int(time.time())
            })
            
            embed = discord.Embed(
                title="🐌 Auto-Slowmode Activated",
                description="High traffic detected! A **5 second** slowmode has been applied.",
                color=Colors.ORANGE
            )
            await channel.send(embed=embed)
            
            self.bot.log.warning(f"Auto-slowmode enabled in #{channel.name}")

    @tasks.loop(minutes=2)
    async def cooldown_check(self):
        channels_to_remove = []
        current_time = time.time()

        for channel_id in list(self.auto_slowmode_channels):
            self.message_tracker[channel_id] = [
                t for t in self.message_tracker[channel_id]
                if current_time - t <= 15
            ]

            if len(self.message_tracker[channel_id]) <= 5:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    original = self.original_slowmode.get(channel_id, 0)
                    await channel.edit(slowmode_delay=original, reason="Auto-slowmode: Traffic normalized")
                    
                    embed = discord.Embed(
                        title="✅ Auto-Slowmode Removed",
                        description="Traffic has normalized. Slowmode has been restored to normal.",
                        color=Colors.GREEN
                    )
                    await channel.send(embed=embed, delete_after=30)
                    
                    self.bot.log.info(f"Auto-slowmode removed from #{channel.name}")
                
                channels_to_remove.append(channel_id)

        for channel_id in channels_to_remove:
            self.auto_slowmode_channels.discard(channel_id)
            self.original_slowmode.pop(channel_id, None)
            self.message_tracker.pop(channel_id, None)
            await self.bot.db.auto_slowmode.delete_one({"channel_id": channel_id})

    @cooldown_check.before_loop
    async def before_cooldown_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: BoBit):
    await bot.add_cog(AntiSpam(bot))
