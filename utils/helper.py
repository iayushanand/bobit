import discord
import string
import datetime as dt
import re
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
from cbvx import iml
from typing import Tuple
from lrclib import LrcLibAPI

class Spotify:
    __slots__ = ("member", "bot", "embed", "regex", "headers", "counter")

    def __init__(self, *, bot, member) -> None:
        self.member: discord.Member | discord.User = member
        self.bot: commands.Bot = bot
        self.counter = 0

    @staticmethod
    def pil_process(pic: BytesIO, name, artists, time, time_at, track) -> discord.File:
        d = Image.open(pic).resize((300, 300))
        buffer = BytesIO()
        d.save(buffer, "png")
        buffer.seek(0)
        csp = iml.Spotify(buffer.getvalue())
        csp.rate(0.55)
        csp.contrast(20.0)
        csp.shift(0)
        _, fore = csp.pallet()
        fore = (fore.r, fore.g, fore.b)
        result = csp.get_base()
        base = Image.frombytes("RGB", (600, 300), result)

        font0 = ImageFont.truetype("assets/fonts/spotify.ttf", 35)
        font2 = ImageFont.truetype("assets/fonts/spotify.ttf", 18)

        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle(
            ((50, 230), (550, 230)),
            radius=1,
            fill=tuple(map(lambda c: int(c * 0.5), fore)),
        )
        draw.rounded_rectangle(
            ((50, 230 - 1), (int(50 + track * 500), 230 + 1)),
            radius=1,
            fill=fore,
        )
        draw.ellipse(
            (int(50 + track * 500) - 5, 230 - 5, int(50 + track * 500) + 5, 230 + 5),
            fill=fore,
            outline=fore,
        )
        draw.text((50, 245), time_at, fore, font=font2)
        draw.text((500, 245), time, fore, font=font2)
        draw.text((50, 50), name, fore, font=font0)
        draw.text((50, 100), artists, fore, font=font2)

        output = BytesIO()
        base.save(output, "png")
        output.seek(0)
        return discord.File(fp=output, filename="spotify.png")

    async def get_from_local(self, bot, act: discord.Spotify) -> discord.File:
        s = tuple(f"{string.ascii_letters}{string.digits}{string.punctuation} ")
        artists = ", ".join(act.artists)
        artists = "".join([x for x in artists if x in s])
        artists = f"{artists[:36]}..." if len(artists) > 36 else artists
        time = act.duration.seconds
        time_at = (
            dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc) - act.start
        ).total_seconds()
        track = time_at / time
        time = f"{time // 60:02d}:{time % 60:02d}"
        time_at = (
            f"{int((time_at if time_at > 0 else 0) // 60):02d}:"
            f"{int((time_at if time_at > 0 else 0) % 60):02d}"
        )
        pog = act.album_cover_url
        name = "".join([x for x in act.title if x in s])
        name = name[0:21] + "..." if len(name) > 21 else name
        rad = await bot.session.get(pog)
        pic = BytesIO(await rad.read())
        return self.pil_process(pic, name, artists, time, time_at, track)

    async def get_embed(self) -> Tuple[discord.Embed, discord.File, discord.ui.View]:
        activity = discord.utils.find(
            lambda activity: isinstance(activity, discord.Spotify),
            self.member.activities,
        )
        if not activity:
            return False
        url = activity.track_url
        image = await self.get_from_local(self.bot, activity)
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                url=url,
                style=discord.ButtonStyle.green,
                label="\u2007Open in Spotify",
                emoji="<:spotify:983984483755765790>",
            )
        )
        return (image, view)

_lrclib_api = LrcLibAPI(
    user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
)

def get_lyrics(name: str, artist: str) -> str:
    results = _lrclib_api.search_lyrics(track_name=name, artist_name=artist)

    if len(results) != 0:
        lyrics = _lrclib_api.get_lyrics_by_id(results[0].id)
        if lyrics.synced_lyrics:
            return (lyrics.synced_lyrics, 1)
        elif lyrics.plain_lyrics:
            return (lyrics.plain_lyrics, 0)
        return None
    else:
        return None

def parse_timestamp_to_seconds(timestamp):
    minutes, seconds = map(float, timestamp.split(':'))
    return minutes * 60 + seconds

def find_surrounding_lyrics(lyrics, target_seconds):
    pattern = r'\[(\d{2}:\d{2}\.\d{2})\] (.+)'
    matches = re.findall(pattern, lyrics)

    parsed_lyrics = []

    for match in matches:
        timestamp, lyric = match
        time_in_seconds = parse_timestamp_to_seconds(timestamp)
        parsed_lyrics.append((time_in_seconds, lyric))

    closest_index = min(range(len(parsed_lyrics)), key=lambda i: abs(parsed_lyrics[i][0] - target_seconds))

    start_index = max(closest_index - 2, 0)
    end_index = min(closest_index + 3, len(parsed_lyrics))

    surrounding_lyrics = [parsed_lyrics[i][1] for i in range(start_index, end_index)]

    return surrounding_lyrics

def parse_duration(duration_str: str) -> int:
    time_dict = {
        'd': 86400,
        'h': 3600,
        'm': 60,
        's': 1
    }
    
    total_seconds = 0
    matches = re.findall(r"(\d+)\s*([dhms])", duration_str.lower())
    
    for amount, unit in matches:
        total_seconds += int(amount) * time_dict[unit]
        
    return total_seconds