import datetime
import re
import discord
from discord.ext import commands, tasks
from io import BytesIO
from utils.bot import BoBit
from utils.consts import COUNTING_THREAD_ID, WELCOME_CHANNEL_ID, COUNTDOWN_CHANNEL_ID
from utils.welcomer import WeclomeBanner

# instagram -> kkinstagram fixer
INSTAGRAM_RE = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s<>\"]+", re.IGNORECASE)
# characters commonly trailing a URL that should not be part of the link
_TRAILING_PUNCT = ".,!?:;)]\"'"

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def get_new_year_countdown_topic() -> str:
    """Return the channel topic string for the New Year countdown."""
    today = datetime.datetime.now(IST).date()
    if today.month == 1 and today.day == 1:
        return f"🎉 Happy New Year {today.year}! 🎉 Welcome to BIT!"

    next_year = today.year + 1
    new_year_date = datetime.date(next_year, 1, 1)
    days_left = (new_year_date - today).days

    if days_left == 1:
        return f"⏳ 1 day left until {next_year} 🎆"
    return f"⏳ {days_left} days left until {next_year}"


class Listeners(commands.Cog):
    def __init__(self, bot: BoBit):
        super().__init__()
        self.bot = bot
        self.banner = WeclomeBanner()
        self._last_message_id: dict[int, int] = {}
        self.update_year_countdown.start()

    def cog_unload(self):
        self.update_year_countdown.cancel()

    async def _update_countdown_topic(self):
        """Helper to update the countdown channel topic."""
        channel = self.bot.get_channel(COUNTDOWN_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(COUNTDOWN_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                self.bot.log.warning(f"[Countdown] Could not fetch channel {COUNTDOWN_CHANNEL_ID}: {e}")
                return

        if not isinstance(channel, discord.TextChannel):
            self.bot.log.warning(f"[Countdown] Channel {COUNTDOWN_CHANNEL_ID} is not a TextChannel, skipping.")
            return

        new_topic = get_new_year_countdown_topic()
        if channel.topic == new_topic:
            return

        try:
            await channel.edit(topic=new_topic, reason="Daily New Year countdown update")
            self.bot.log.info(f"[Countdown] Updated channel topic to: {new_topic}")
        except discord.Forbidden:
            self.bot.log.error(f"[Countdown] Missing permissions to edit channel {COUNTDOWN_CHANNEL_ID} topic")
        except discord.HTTPException as e:
            self.bot.log.error(f"[Countdown] Failed to update countdown topic: {e}")

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=IST))
    async def update_year_countdown(self):
        await self._update_countdown_topic()

    @update_year_countdown.before_loop
    async def before_update_year_countdown(self):
        await self.bot.wait_until_ready()
        await self._update_countdown_topic()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or getattr(message, "webhook_id", None):
            return
        # track latest message per channel for delete-restore logic
        try:
            self._last_message_id[message.channel.id] = message.id
        except Exception:
            pass
        content = message.content or ""
        if not content:
            return
        lower = content.lower()
        if "kkinstagram.com" in lower:
            return
        if "instagram.com" not in lower:
            return

        matches = list(INSTAGRAM_RE.finditer(content))
        if not matches:
            return

        def _fix_match(m: re.Match) -> str:
            url = m.group(0)
            trailing = ""
            while url and url[-1] in _TRAILING_PUNCT:
                trailing = url[-1] + trailing
                url = url[:-1]
            fixed = re.sub(r"instagram\.com", "kkinstagram.com", url, flags=re.IGNORECASE)
            return fixed + trailing

        fixed_content = INSTAGRAM_RE.sub(_fix_match, content)

        if fixed_content == content:
            return

        if message.guild is None or not isinstance(message.channel, discord.TextChannel):
            try:
                await message.channel.send(
                    content=fixed_content,
                    allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False),
                    reference=message,
                    mention_author=False,
                )
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
            except (discord.Forbidden, discord.HTTPException):
                pass
            return

        try:
            webhook: discord.Webhook | None = None
            try:
                webhooks = await message.channel.webhooks()
                for wh in webhooks:
                    if wh.token is not None and wh.user and wh.user.id == self.bot.user.id:
                        webhook = wh
                        break
                if webhook is None:
                    for wh in webhooks:
                        if wh.token is not None:
                            webhook = wh
                            break
            except (discord.Forbidden, discord.HTTPException):
                webhook = None

            if webhook is None:
                try:
                    webhook = await message.channel.create_webhook(name="InstaFix")
                except (discord.Forbidden, discord.HTTPException):
                    await message.channel.send(
                        content=fixed_content,
                        allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False),
                        reference=message,
                        mention_author=False,
                    )
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                        pass
                    return

            try:
                avatar_url = message.author.display_avatar.url if message.author.display_avatar else None
            except Exception:
                avatar_url = None

            await webhook.send(
                content=fixed_content,
                username=message.author.display_name,
                avatar_url=avatar_url,
                allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False),
            )
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _get_webhook_for_channel(self, channel: discord.abc.GuildChannel | discord.Thread) -> tuple[discord.Webhook | None, discord.Thread | None]:
        """Return (webhook, thread) for webhook send. Handles TextChannel and Thread."""
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
                    webhook = await target.create_webhook(name="Restore")
                except (discord.Forbidden, discord.HTTPException):
                    return None, None
            return webhook, thread
        except (discord.Forbidden, discord.HTTPException):
            return None, None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # ignore bot/webhook and non-guild
        if getattr(message, "webhook_id", None) or getattr(message.author, "bot", False):
            return
        if not message.guild:
            return
        # counting thread is handled by Counting cog to avoid double restore and to keep DB logic
        if message.channel.id == COUNTING_THREAD_ID:
            return
        # only restore if deleted message was the latest in its channel
        is_latest = False
        cached_last = self._last_message_id.get(message.channel.id)
        if cached_last is not None and cached_last == message.id:
            is_latest = True
            # pop so next delete correctly evaluated
            self._last_message_id.pop(message.channel.id, None)
        else:
            try:
                # fallback: if deleted id is greater than current latest, it was latest before delete
                async for latest in message.channel.history(limit=1):
                    if message.id > latest.id:
                        is_latest = True
                    break
                else:
                    # channel now empty -> deleted was the only/latest
                    is_latest = True
            except (discord.Forbidden, discord.HTTPException):
                return
        if not is_latest:
            return
        if not message.content and not message.attachments and not message.embeds:
            return
        # build content to restore
        content = message.content or ""
        # include attachment URLs as fallback if we cannot re-upload
        files: list[discord.File] = []
        if message.attachments:
            for att in message.attachments:
                try:
                    files.append(await att.to_file())
                except (discord.HTTPException, discord.Forbidden):
                    # fallback to url in content
                    content = (content + f"\n{att.url}").strip() if content else att.url

        webhook, thread = await self._get_webhook_for_channel(message.channel)  # type: ignore
        if webhook is None:
            return
        try:
            avatar_url = message.author.display_avatar.url if getattr(message.author, "display_avatar", None) else None
        except Exception:
            avatar_url = None
        try:
            kwargs: dict = {
                "content": content or None,
                "username": getattr(message.author, "display_name", str(message.author)),
                "avatar_url": avatar_url,
                "allowed_mentions": discord.AllowedMentions(users=False, roles=False, everyone=False),
            }
            if files:
                kwargs["files"] = files
            if thread is not None:
                kwargs["thread"] = thread
            await webhook.send(**kwargs)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        # handle uncached deletes where we still know it was latest via cache
        if payload.cached_message is not None:
            return  # already handled by on_message_delete
        channel_id = payload.channel_id
        if channel_id == COUNTING_THREAD_ID:
            return
        cached_last = self._last_message_id.get(channel_id)
        if cached_last is None or cached_last != payload.message_id:
            return
        # we know it was latest but have no content to restore - cannot webhook without content
        # pop cache
        self._last_message_id.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            avatar_bytes = await member.display_avatar.read()
            avatar = BytesIO(avatar_bytes)
            file = self.banner.make_banner(member.name, avatar, member_count=member.guild.member_count)
            await welcome_channel.send(
                content=f"-# Welcome to server {member.mention}",
                file=file
            )


async def setup(bot: BoBit):
    await bot.add_cog(Listeners(bot))
