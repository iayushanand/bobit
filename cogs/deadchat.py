import discord
from discord.ext import commands, tasks
from utils.bot import BoBit
from utils.consts import GENERAL_CHAT_ID
import random
import time

DEAD_CHAT_MESSAGES = [
    "Welcome to the wake. Please leave your flowers and 'F's in the chat. Services for the conversation will begin shortly.",
    "I didn't realize I'd accidentally joined a cemetery. Who's the groundskeeper here?",
    "Does anyone have a defibrillator? I'm trying to find a heartbeat in this channel.",
    "I'm currently checking the walls for structural integrity since this place has been abandoned for so long.",
    "Anyone want to help me scrub the graffiti off these dead messages? This place is looking rough.",
    "Is this a Discord server or a ghost town simulation?",
    "Just checking in to see if the spiders have finished taking over the general chat yet.",
    "I love how we all collectively decided to go into witness protection at the exact same time.",
    "If a message drops in a dead chat and nobody is around to read it, does it actually make a notification?",
    "This chat is so dead I'm starting to hear my own thoughts. It's scary in here. Help.",
    "I'm not saying the chat is dead, but I just saw a 'Going Out of Business' sign on the server icon.",
    "I've spent the last three hours carbon-dating the last message. It belongs in a museum.",
    "Archaeologists are going to find this chat in 2000 years and wonder what happened to the civilization that lived here.",
    "The silence in here is so loud it's actually starting to break the sound barrier.",
    "I'm conducting a social experiment to see how long a group of humans can go without moving. So far, you guys are winning.",
    "Day 4: Rations are low. The 'General Chat' is a wasteland. I've forgotten the sound of a notification. If anyone finds this... tell my mom I love her.",
    "Just checking for signs of life. Blink once for 'I'm busy,' twice for 'I've been kidnapped by a rival server.'",
    "I feel like the last guy left on earth in a movie, wandering around an empty mall shouting 'HELLO??'",
    "*Throws a flare into the channel...* Anyone? No? Just the echoes of my own loneliness? Cool.",
    "I didn't know we were all playing a server-wide game of The Quiet Game. Who's winning?",
    "This chat has the same energy as an empty Victorian hallway at 3:00 AM.",
    "I've seen more activity in a 'Terms and Conditions' agreement than I've seen in here today.",
    "Are we all just staring at the screen waiting for someone else to be the 'main character' and talk first?",
    "This chat is currently in a medically induced coma.",
    "The cobwebs on my screen are getting out of hand.",
    "I'm 90% sure I just saw a ghost walk through this sub-channel.",
    "Is this a Discord server or a witness protection program?",
    "Checking the chat's 'Do Not Resuscitate' order...",
    "Since nobody is talking, I'm assuming I'm now the acting CEO of this server. My first decree: Someone say something funny or you're all fired."
]


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
