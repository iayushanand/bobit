import asyncio
import discord
from discord.ext import commands

from utils.bot import BoBit
from utils.consts import COUNTING_THREAD_ID, Colors


class Counting(commands.Cog):
    """Counting game for the dedicated thread.

    Rules:
    - Only the thread ``COUNTING_THREAD_ID`` is handled.
    - First word must be the next integer (rest of message is ignored, allows split messages).
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

    async def _increment_user(self, user_id: int) -> None:
        try:
            await self.bot.db.counting.update_one(
                {"_id": f"user:{user_id}"},
                {"$inc": {"count": 1}, "$set": {"user_id": user_id}},
                upsert=True,
            )
        except Exception as exc:
            self.bot.log.warning(f"[Counting] increment_user failed for {user_id}: {exc}")

    async def _get_leaderboard(self, limit: int = 10) -> list[dict]:
        try:
            # user docs have _id starting with "user:"
            cursor = self.bot.db.counting.find({"_id": {"$regex": "^user:"}}).sort("count", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as exc:
            self.bot.log.warning(f"[Counting] get_leaderboard failed: {exc}")
            return []

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
        # allow split messages: only first word needs to be the number, rest is ignored
        token = stripped.split()[0] if stripped else ""
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
            await self._increment_user(message.author.id)
            self.bot.log.info(f"[Counting] {message.author} counted {number} in {COUNTING_THREAD_ID}")

    async def _get_webhook_for_counting(self, channel: discord.abc.GuildChannel | discord.Thread) -> tuple[discord.Webhook | None, discord.Thread | None]:
        thread = None
        target: discord.TextChannel | None = None
        if isinstance(channel, discord.Thread):
            thread = channel
            target = channel.parent  # type: ignore
            if not isinstance(target, discord.TextChannel):
                return None, None
        elif isinstance(channel, discord.TextChannel):
            target = channel
        else:
            return None, None
        try:
            webhooks = await target.webhooks()
            webhook: discord.Webhook | None = None
            for wh in webhooks:
                if wh.token is not None and wh.user and wh.user.id == self.bot.user.id:
                    webhook = wh
                    break
            if webhook is None:
                for wh in webhooks:
                    if wh.token is not None:
                        webhook = wh
                        break
            if webhook is None:
                try:
                    webhook = await target.create_webhook(name="CountingRestore")
                except (discord.Forbidden, discord.HTTPException):
                    return None, None
            return webhook, thread
        except (discord.Forbidden, discord.HTTPException):
            return None, None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # restore latest valid count if it was deleted
        if message.channel.id != COUNTING_THREAD_ID:
            return
        if getattr(message, "webhook_id", None):
            return
        # only restore if deleted message was the latest valid counted message
        try:
            state = await self._get_state()
        except Exception:
            return
        if state.get("last_message_id") != message.id:
            return
        # ignore bot messages
        if getattr(message.author, "bot", False):
            return
        content = (message.content or "").strip()
        # fallback to stored count if content empty (should not happen for valid count)
        if not content:
            content = str(state.get("count", ""))

        webhook, thread = await self._get_webhook_for_counting(message.channel)  # type: ignore
        if webhook is None:
            return
        try:
            avatar_url = message.author.display_avatar.url if getattr(message.author, "display_avatar", None) else None
        except Exception:
            avatar_url = None
        try:
            kwargs: dict = {
                "content": content,
                "username": getattr(message.author, "display_name", str(message.author)),
                "avatar_url": avatar_url,
                "allowed_mentions": discord.AllowedMentions(users=False, roles=False, everyone=False),
            }
            if thread is not None:
                kwargs["thread"] = thread
            await webhook.send(**kwargs)
            self.bot.log.info(f"[Counting] Restored deleted latest {content} from {message.author} via webhook")
        except (discord.Forbidden, discord.HTTPException) as exc:
            self.bot.log.warning(f"[Counting] webhook restore failed: {exc}")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.channel_id != COUNTING_THREAD_ID:
            return
        if payload.cached_message is not None:
            return  # handled by on_message_delete
        try:
            state = await self._get_state()
        except Exception:
            return
        if state.get("last_message_id") != payload.message_id:
            return
        count = state.get("count")
        last_user_id = state.get("last_user_id")
        if count is None or last_user_id is None:
            return
        try:
            user = self.bot.get_user(last_user_id)
            if user is None:
                user = await self.bot.fetch_user(last_user_id)
        except (discord.NotFound, discord.HTTPException):
            return
        try:
            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(payload.channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        webhook, thread = await self._get_webhook_for_counting(channel)
        if webhook is None:
            return
        try:
            avatar_url = user.display_avatar.url if getattr(user, "display_avatar", None) else None
        except Exception:
            avatar_url = None
        try:
            kwargs: dict = {
                "content": str(count),
                "username": getattr(user, "display_name", str(user)),
                "avatar_url": avatar_url,
                "allowed_mentions": discord.AllowedMentions(users=False, roles=False, everyone=False),
            }
            if thread is not None:
                kwargs["thread"] = thread
            await webhook.send(**kwargs)
            self.bot.log.info(f"[Counting] Restored raw-deleted latest {count} from {user} via webhook")
        except (discord.Forbidden, discord.HTTPException) as exc:
            self.bot.log.warning(f"[Counting] raw webhook restore failed: {exc}")

    # -- leaderboard commands --
    @commands.group(name="counting", aliases=["count", "cnt"], invoke_without_command=True)
    async def counting_group(self, ctx: commands.Context):
        state = await self._get_state()
        current = int(state.get("count", 0))
        next_expected = current + 1
        e = discord.Embed(
            title="Counting",
            description=f"Current count: **{current}**\nNext: **{next_expected}**\nThread: <#{COUNTING_THREAD_ID}>",
            color=Colors.BLURPLE,
        )
        await ctx.send(embed=e)

    @counting_group.command(name="leaderboard", aliases=["lb", "top", "rank", "leaders"])
    async def counting_leaderboard(self, ctx: commands.Context, limit: int = 10):
        limit = max(1, min(int(limit), 25))
        top_limit = 10 if limit == 10 else limit
        docs = await self._get_leaderboard(top_limit)
        if not docs:
            await ctx.send(embed=discord.Embed(description="No counts yet. Start counting in the thread!", color=Colors.DARK_EMBED))
            return
        state = await self._get_state()
        current = int(state.get("count", 0))

        lines: list[str] = []
        medals = ["🥇", "🥈", "🥉"]
        top_ids = set()
        for idx, doc in enumerate(docs, start=1):
            user_id = int(doc.get("user_id", 0))
            cnt = int(doc.get("count", 0))
            top_ids.add(user_id)
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"<@{user_id}>"
            if ctx.guild:
                member = ctx.guild.get_member(user_id)
                if member:
                    name = member.display_name
            prefix = medals[idx - 1] if idx <= 3 else f"`{idx}.`"
            if user_id == ctx.author.id:
                name = f"__{name}__"
            lines.append(f"{prefix} **{name}** — {cnt:,}")

        if ctx.author.id not in top_ids:
            try:
                author_doc = await self.bot.db.counting.find_one({"_id": f"user:{ctx.author.id}"})
            except Exception:
                author_doc = None
            author_cnt = int(author_doc.get("count", 0)) if author_doc else 0
            try:
                if author_cnt > 0:
                    rank = await self.bot.db.counting.count_documents({"_id": {"$regex": "^user:"}, "count": {"$gt": author_cnt}}) + 1
                else:
                    total = await self.bot.db.counting.count_documents({"_id": {"$regex": "^user:"}})
                    rank = total + 1 if total else None
            except Exception:
                rank = None
            if rank is not None:
                author_name = ctx.author.display_name
                lines.append("")  # separator
                if author_cnt > 0:
                    lines.append(f"`{rank}.` **__{author_name}__** — {author_cnt:,}  ← you")
                else:
                    lines.append(f"`{rank}.` **__{author_name}__** — 0  ← you (no counts yet)")

        e = discord.Embed(
            title="Counting Leaderboard",
            description="\n".join(lines),
            color=Colors.GOLD,
        )
        e.add_field(name="Current Count", value=f"**{current:,}**", inline=True)
        e.add_field(name="Thread", value=f"<#{COUNTING_THREAD_ID}>", inline=True)
        e.set_footer(text=f"Top {len(docs)} + your position • Next: {current + 1}")
        await ctx.send(embed=e)

    @counting_group.command(name="stats", aliases=["me", "self"])
    async def counting_stats(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        try:
            doc = await self.bot.db.counting.find_one({"_id": f"user:{target.id}"})
        except Exception:
            doc = None
        cnt = int(doc.get("count", 0)) if doc else 0
        state = await self._get_state()
        try:
            rank = await self.bot.db.counting.count_documents({"_id": {"$regex": "^user:"}, "count": {"$gt": cnt}}) + 1 if cnt > 0 else None
        except Exception:
            rank = None
        e = discord.Embed(title=f"{target.display_name} — Counting Stats", color=Colors.BLURPLE)
        e.add_field(name="Counts", value=f"**{cnt:,}**", inline=True)
        if rank is not None:
            e.add_field(name="Rank", value=f"#{rank}", inline=True)
        e.add_field(name="Current", value=f"{int(state.get('count', 0)):,}", inline=True)
        await ctx.send(embed=e)


async def setup(bot: BoBit):
    await bot.add_cog(Counting(bot))
