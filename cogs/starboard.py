import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import STARBOARD_CHANNEL_ID, STARBOARD_THRESHOLD, Colors
from datetime import datetime, timezone


class Starboard(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    def star_emoji(self, count: int) -> str:
        if count >= 10:
            return "💫"
        if count >= 6:
            return "🌟"
        return "⭐"

    def build_embed(self, message: discord.Message, star_count: int) -> discord.Embed:
        embed = discord.Embed(
            description=message.content or "",
            color=Colors.STARBOARD,
            timestamp=message.created_at
        )

        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )

        embed.add_field(
            name="Source",
            value=f"[Jump to Message]({message.jump_url})",
            inline=True
        )

        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith("image"):
                embed.set_image(url=attachment.url)

        if message.embeds:
            data = message.embeds[0]
            if data.type == "image" and data.url:
                embed.set_image(url=data.url)

        embed.set_footer(text=f"{self.star_emoji(star_count)} {star_count} | #{message.channel.name}")

        return embed

    async def get_star_count(self, message: discord.Message) -> int:
        count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "⭐":
                async for user in reaction.users():
                    if user.id != message.author.id:
                        count += 1
                break
        return count

    async def handle_starboard(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "⭐":
            return
        if STARBOARD_CHANNEL_ID == 0:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        if payload.channel_id == STARBOARD_CHANNEL_ID:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if message.author.bot:
            return

        star_count = await self.get_star_count(message)
        entry = await self.bot.db.starboard.find_one({"_id": message.id})

        starboard_channel = guild.get_channel(STARBOARD_CHANNEL_ID)
        if not starboard_channel or not isinstance(starboard_channel, discord.TextChannel):
            return

        if star_count >= STARBOARD_THRESHOLD:
            embed = self.build_embed(message, star_count)

            if entry:
                try:
                    starboard_msg = await starboard_channel.fetch_message(entry["starboard_message_id"])
                    await starboard_msg.edit(
                        content=f"{self.star_emoji(star_count)} **{star_count}** | {channel.mention}",
                        embed=embed
                    )
                except discord.NotFound:
                    await self.bot.db.starboard.delete_one({"_id": message.id})
            else:
                starboard_msg = await starboard_channel.send(
                    content=f"{self.star_emoji(star_count)} **{star_count}** | {channel.mention}",
                    embed=embed
                )
                await self.bot.db.starboard.insert_one({
                    "_id": message.id,
                    "starboard_message_id": starboard_msg.id,
                    "channel_id": channel.id,
                    "author_id": message.author.id
                })
                self.bot.log.info(f"Starboard → Message {message.id} posted")

        elif entry:
            try:
                starboard_msg = await starboard_channel.fetch_message(entry["starboard_message_id"])
                await starboard_msg.delete()
            except discord.NotFound:
                pass
            await self.bot.db.starboard.delete_one({"_id": message.id})
            self.bot.log.info(f"Starboard → Message {message.id} removed")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        await self.handle_starboard(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        await self.handle_starboard(payload)


async def setup(bot: BoBit):
    await bot.add_cog(Starboard(bot))
