import discord
from discord.ext import commands, tasks
from utils.bot import BoBit
from utils.consts import GENERAL_CHAT_ID, DEAD_CHAT_MESSAGES
import random
import time


class DeadChatReviver(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.last_message_time: float = time.time()
        self.already_sent: bool = False
        self.dead_chat_check.start()

    def cog_unload(self):
        self.dead_chat_check.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != GENERAL_CHAT_ID:
            return
        if message.author.bot:
            return
        self.last_message_time = time.time()
        self.already_sent = False

    @tasks.loop(hours=1)
    async def dead_chat_check(self):
        if GENERAL_CHAT_ID == 0:
            return
        if self.already_sent:
            return

        current_time = time.time()
        hours_since_message = (current_time - self.last_message_time) / 3600

        if hours_since_message >= 10:
            channel = self.bot.get_channel(GENERAL_CHAT_ID)
            if channel and isinstance(channel, discord.TextChannel):
                message = random.choice(DEAD_CHAT_MESSAGES)
                await channel.send(message)
                self.already_sent = True
                self.bot.log.info(f"Dead chat message sent in #{channel.name}")

    @dead_chat_check.before_loop
    async def before_dead_chat_check(self):
        await self.bot.wait_until_ready()
        if GENERAL_CHAT_ID == 0:
            return
        channel = self.bot.get_channel(GENERAL_CHAT_ID)
        if channel and isinstance(channel, discord.TextChannel):
            async for msg in channel.history(limit=1):
                self.last_message_time = msg.created_at.timestamp()
                break


async def setup(bot: BoBit):
    await bot.add_cog(DeadChatReviver(bot))
