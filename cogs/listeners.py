import datetime
import re
import discord
from discord.ext import commands, tasks
from io import BytesIO
from utils.bot import BoBit
from utils.consts import WELCOME_CHANNEL_ID, COUNTDOWN_CHANNEL_ID
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
