
import discord
import math
import string
import textwrap
import re

import datetime as dt
import numpy as np

from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
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



def create_quote_buffer(avatar, quote, display_name, username):
    WIDTH = 1600
    HEIGHT = 900

    IMAGE_WIDTH = int(WIDTH * 0.48)

    template = Image.new("RGBA", (WIDTH, HEIGHT), "black")

    FONT = "assets/fonts/InterBlack.ttf"

    quote_font = ImageFont.truetype(FONT, 64)
    info_font = ImageFont.truetype(FONT, 34)


    avatar = (
        avatar.convert("L")
            .convert("RGBA")
    )

    avatar = ImageEnhance.Contrast(avatar).enhance(0.9)
    avatar = ImageEnhance.Brightness(avatar).enhance(0.8)

    avatar = ImageOps.fit(
        avatar,
        (IMAGE_WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.0, 0.5),
    )

    overlay = Image.new(
        "RGBA",
        avatar.size,
        (0, 0, 0, 70),
    )

    avatar = Image.alpha_composite(avatar, overlay)


    mask = Image.new("L", (IMAGE_WIDTH, HEIGHT))
    pixels = mask.load()

    fade_start = IMAGE_WIDTH * 0.15
    fade_end = IMAGE_WIDTH * 0.98
    curve_strength = IMAGE_WIDTH * 0.08

    for y in range(HEIGHT):
        arc = math.sin(math.pi * y / (HEIGHT - 1))
        offset = curve_strength * arc

        start = fade_start + offset
        end = fade_end + offset

        for x in range(IMAGE_WIDTH):
            if x <= start:
                alpha = 255
            elif x >= end:
                alpha = 0
            else:
                t = (x - start) / (end - start)
                t = t ** 1.8
                alpha = int(255 * (1 - t))

            pixels[x, y] = alpha

    avatar.putalpha(mask)
    template.alpha_composite(avatar)

    draw = ImageDraw.Draw(template)


    wrapped = textwrap.fill(quote, width=28)

    bbox = draw.multiline_textbbox(
        (0, 0),
        wrapped,
        font=quote_font,
        spacing=10,
        align="center",
    )

    qw = bbox[2] - bbox[0]
    qh = bbox[3] - bbox[1]

    center_x = int(WIDTH * 0.73)
    quote_y = HEIGHT // 2 - qh // 2 - 30

    draw.multiline_text(
        (center_x - qw // 2, quote_y),
        wrapped,
        font=quote_font,
        fill="white",
        align="center",
        spacing=10,
    )


    author = f"- {display_name}"

    bbox = draw.textbbox((0, 0), author, font=info_font)
    aw = bbox[2] - bbox[0]
    ah = bbox[3] - bbox[1]

    author_y = quote_y + qh + 26

    draw.text(
        (center_x - aw // 2, author_y),
        author,
        font=info_font,
        fill="white",
    )


    user = f"@{username}"

    bbox = draw.textbbox((0, 0), user, font=info_font)
    uw = bbox[2] - bbox[0]

    draw.text(
        (center_x - uw // 2, author_y + ah + 8),
        user,
        font=info_font,
        fill=(140, 140, 140),
    )


    with BytesIO() as image_binary:
        template.save(image_binary, "PNG")
        image_binary.seek(0)

        return discord.File(
            fp=image_binary,
            filename="quote.png",
        )