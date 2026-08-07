import time
from typing import TYPE_CHECKING

import discord
from discord import ui
from discord.ext import commands, tasks
from more_itertools import sliced
from utils.bot import BoBit

if TYPE_CHECKING:
    from typing_extensions import Self

class Piston(discord.ui.View):
    def __init__(
        self,
        cog: commands.Cog,
        code: str,
        language: str,
        message: discord.Message,
        author: discord.Member,
    ) -> None:
        self.code = code
        self.lang = language
        self.cog = cog
        self.timestamp = int(time.time())
        self.is_compiled = False
        self.output = []
        self.msg = message
        self.author = author
        self.page = 0
        super().__init__()
        self.timer.start()
        self.get_code_out.start()
        self.session = cog.bot.session
        # asyncio.run(get_code_out())

    @tasks.loop(seconds=1, count=30)
    async def timer(self):
        if self.is_compiled:
            self.timer.cancel()
            return
        await self.msg.edit(
            embed=discord.Embed(
                title=f"compiling **[** {int(time.time()) - self.timestamp} **]**"
            )
        )

    @tasks.loop(seconds=1, count=1)
    async def get_code_out(self):
        res = await self.session.post(
            url = "https://emkc.org/api/v1/piston/execute",
            data = {"language": self.lang, "source": self.code}
        )
        self.res = await res.json()
        self.is_compiled = True
        self.timer.cancel()
        if "message" in self.res:
            return await self.msg.edit(
                embed=discord.Embed(
                    title=" ",
                    description="```ansi\n[1;31m{}\n```".format(self.res["message"]),
                )
            )
        lines = self.res["output"].split("\n")
        output = []
        for line in lines:
            if len(line) > 500:
                output.extend(sliced(line, 500))
            elif output:
                if len(output[-1].split("\n")) > 15:
                    output.append(line + "\n")
                else:
                    output[-1] += line + "\n"
            else:
                output.append(line + "\n")
        self.output = output
        self.ran = self.res["ran"]
        self.is_compiled = True
        for child in self.children:
            if child.custom_id == "info":
                if self.ran:
                    child.style = discord.ButtonStyle.green
                    child.label = (
                        f"ran '{self.lang}' code  |  "
                        f"{int(time.time()) - self.timestamp}s"
                    )
                else:
                    child.style = discord.ButtonStyle.red
                    child.label = (
                        f"failed to run '{self.lang}' code  |  "
                        f"{int(time.time()) - self.timestamp}s"
                    )
        await self.msg.edit(
            embed=discord.Embed(
                title=" ", description=f"```{self.lang}\n{output[0]}\n```"
            ),
            view=self,
        )

    @ui.button(label="<", custom_id="prev", disabled=True)
    async def _prev(self, interaction: discord.Interaction, button: discord.Button):
        if self.page == 0:
            button.disabled = True
            return await interaction.response.edit_message(view=self)
        self.page -= 1
        for child in self.children:
            if child.custom_id == "next":
                child.disabled = False
        return await interaction.response.edit_message(
            embed=discord.Embed(
                title=" ",
                description=f"```{self.lang}\n{self.output[self.page]}\n```",
            ),
            view=self,
        )

    @ui.button(
        label="...", custom_id="info", style=discord.ButtonStyle.gray, disabled=True
    )
    async def _info(self, interaction: discord.Interaction, button: discord.Button):
        pass

    @ui.button(label=">", custom_id="next", style=discord.ButtonStyle.green)
    async def _next(self, interaction: discord.Interaction, button: discord.Button):
        if self.page + 1 == len(self.output):
            button.disabled = True
            return await interaction.response.edit_message(view=self)
        self.page += 1
        for child in self.children:
            if child.custom_id == "prev":
                child.disabled = False
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=" ",
                    description=f"```{self.lang}\n{self.output[self.page]}\n```",
                ),
                view=self,
            )
        except IndexError:
            self.page -= 1
        return

    @ui.button(
        label="Delete", custom_id="delete", style=discord.ButtonStyle.danger, row=2
    )
    async def _delete(self, interaction: discord.Interaction, button: discord.Button):
        self.stop()
        await self.msg.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author
