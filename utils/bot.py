import discord
from discord.ext import commands
import os
import traceback
from dotenv import load_dotenv
from utils.database import Database
from utils.logger import Logger

load_dotenv()


class BoBit(commands.Bot):
    def __init__(self, command_prefix):
        super().__init__(
            command_prefix,
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
        await self.load_extension("jishaku")
        os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
        os.environ['JISHAKU_RETAIN'] = 'True'
        self.log.info("Loaded → Jishaku")

        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                await self.load_extension(f"cogs.{file[:-3]}")
                self.log.info(f"Loaded → {file[:-3].title()}")

    async def on_ready(self):
        self.log.success(f"Logged in as : {self.user.name}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        error_msg = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        self.log.error(f"Command: {ctx.command} | User: {ctx.author} | Error:\n{error_msg}")
        traceback.print_exception(type(error), error, error.__traceback__)

    async def on_error(self, event: str, *args, **kwargs):
        error_msg = traceback.format_exc()
        self.log.error(f"Event: {event} | Error:\n{error_msg}")
        traceback.print_exc()

    async def close(self):
        await self.db.close()
        await super().close()

    def runbot(self):
        self.run(self.TOKEN)
