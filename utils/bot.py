import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from utils.database import Database
from utils.logger import Logger
load_dotenv()

class BoBit(commands.Bot):
    def __init__(self, command_prefix):
        super().__init__(command_prefix,
                         help_command=None,
                         intents=discord.Intents.all(),
                         activity=discord.Activity(type=discord.ActivityType.watching, name="over BIT Discord"),
                         status=discord.Status.dnd

        )
        self.TOKEN = os.getenv("TOKEN")
        self.db = Database(os.getenv("MONGOURI"))
        self.col = self.db.collection
        self.log = Logger("BoBit") 
    

    async def setup_hook(self):
        await self.db.connect()

    async def on_ready(self):
        self.log.success(f"Logged in as : {self.user.name}")

    async def close(self):
        await self.db.close()
        await super().close()

    def runbot(self):
          self.run(self.TOKEN)
