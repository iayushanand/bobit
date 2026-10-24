import asyncio
import discord
from discord.ext import commands

from utils.bot import BoBit
from utils.consts import COUNTING_THREAD_ID


class Counting(commands.Cog):
    """Counting game for the dedicated thread.

    Rules:
    - Only the thread ``COUNTING_THREAD_ID`` is handled.
    - Message must be exactly the next integer.
    - Same user cannot count twice in a row.
    - Uses ``bot.db.counting`` to persist ``count`` and ``last_user_id`` across restarts.
    """

    def __init__(self, bot: BoBit):
        self.bot = bot
        self._lock = asyncio.Lock()

    async def _get_state(self) -> dict:
        """Return counting state doc or default. Uses ``bot.db.counting`` as in other cogs (tags/afk/starboard)."""
        try:
            doc = await self.bot.db.counting.find_one({"_id": COUNTING_THREAD_ID})
            if doc:
                return doc
        except Exception as exc:
            self.bot.log.warning(f"[Counting] get_state failed: {exc}")
        return {"_id": COUNTING_THREAD_ID, "count": 0, "last_user_id": None}

    async def _set_state(self, count: int, last_user_id: int, last_message_id: int | None = None) -> None:
        try:
            await self.bot.db.counting.update_one(
                {"_id": COUNTING_THREAD_ID},
                {"$set": {"count": count, "last_user_id": last_user_id, "last_message_id": last_message_id}},
                upsert=True,
            )
        except Exception as exc:
            self.bot.log.error(f"[Counting] set_state failed: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or getattr(message, "webhook_id", None):
            return
        if message.channel.id != COUNTING_THREAD_ID:
            return

        content = (message.content or "").strip()
        if not content:
            return

        stripped = content.strip()
        token = stripped.split()[0] if stripped else ""
        if token != stripped:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return
            try:
                state = await self._get_state()
                expected = int(state.get("count", 0)) + 1
                await message.channel.send(
                    f"{message.author.mention} please only send the next number. Next is **{expected}**.",
                    delete_after=5,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
            return

        if not token.lstrip("-").isdigit():
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return
            try:
                await message.channel.send(
                    f"{message.author.mention} that is not a valid number.",
                    delete_after=5,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
            return

        try:
            number = int(token)
        except ValueError:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
            return

        async with self._lock:
            state = await self._get_state()
            current = int(state.get("count", 0))
            last_user_id = state.get("last_user_id")
            expected = current + 1

            if last_user_id is not None and message.author.id == last_user_id:
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    return
                try:
                    await message.channel.send(
                        f"{message.author.mention} you cannot count twice in a row. Wait for someone else. Next is **{expected}**.",
                        delete_after=5,
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return

            if number != expected:
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    return
                try:
                    await message.channel.send(
                        f"{message.author.mention} wrong number. Next is **{expected}**, not **{number}**.",
                        delete_after=5,
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return

            await self._set_state(number, message.author.id, message.id)
            try:
                await message.add_reaction("✅")
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
            self.bot.log.info(f"[Counting] {message.author} counted {number} in {COUNTING_THREAD_ID}")


async def setup(bot: BoBit):
    await bot.add_cog(Counting(bot))
