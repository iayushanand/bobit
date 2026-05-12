from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter, ImageEnhance
import discord
from io import BytesIO


class WeclomeBanner():
    def __init__(self):
        self.font = {
            "header": ImageFont.truetype("assets/fonts/MAKISUPA.ttf", 72),
            "username": ImageFont.truetype("assets/fonts/MAKISUPA.ttf", 52),
            "subtitle": ImageFont.truetype("assets/fonts/MAKISUPA.ttf", 30),
        }

    def circle(self, pfp, size=(220, 220)):
        pfp = pfp.resize(size, Image.LANCZOS).convert("RGBA")
        bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
        mask = Image.new("L", bigsize, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + bigsize, fill=255)
        mask = mask.resize(pfp.size, Image.LANCZOS)
        mask = ImageChops.darker(mask, pfp.split()[-1])
        pfp.putalpha(mask)
        return pfp

    def draw_glow_ring(self, draw, center, radius, color, ring_width=4, glow_layers=12):
        cx, cy = center
        for i in range(glow_layers, 0, -1):
            alpha = int(40 * (1 - i / glow_layers))
            r = radius + ring_width + i * 2
            draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                outline=(*color, alpha), width=2
            )
        draw.ellipse(
            (cx - radius - ring_width, cy - radius - ring_width,
             cx + radius + ring_width, cy + radius + ring_width),
            outline=(*color, 220), width=ring_width
        )

    def draw_decorative_dots(self, draw, width, height):
        dot_color = (255, 255, 255, 30)
        positions = [
            (60, 80), (80, 60), (100, 90), (70, 110),
            (width - 60, 80), (width - 80, 60), (width - 100, 90), (width - 70, 110),
            (60, height - 80), (80, height - 60), (100, height - 90),
            (width - 60, height - 80), (width - 80, height - 60), (width - 100, height - 90),
        ]
        for x, y in positions:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=dot_color)

    def draw_line_accents(self, draw, width, height):
        line_color = (255, 255, 255, 40)
        draw.line([(40, height // 2 - 60), (40, height // 2 + 60)], fill=line_color, width=2)
        draw.line([(46, height // 2 - 40), (46, height // 2 + 40)], fill=line_color, width=1)
        draw.line([(width - 40, height // 2 - 60), (width - 40, height // 2 + 60)], fill=line_color, width=2)
        draw.line([(width - 46, height // 2 - 40), (width - 46, height // 2 + 40)], fill=line_color, width=1)

    def make_banner(self, username, pfp, member_count=None):
        pfp = Image.open(pfp)
        bg = Image.open("assets/images/background.png")
        bx, by = bg.size

        bg = bg.convert("RGBA")
        bg = ImageEnhance.Brightness(bg).enhance(0.35)

        overlay = Image.new("RGBA", (bx, by), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        for y in range(by):
            dist = abs(y - by // 2) / (by // 2)
            overlay_draw.line([(0, y), (bx, y)], fill=(10, 10, 30, int(60 + 120 * dist)))

        for x in range(bx):
            dist = abs(x - bx // 2) / (bx // 2)
            if dist > 0.6:
                overlay_draw.line([(x, 0), (x, by)], fill=(5, 5, 20, int(80 * ((dist - 0.6) / 0.4))))

        bg = Image.alpha_composite(bg, overlay)

        accent_color = (88, 101, 242)
        bar_height = 6
        for i in range(bar_height):
            alpha = int(200 * (1 - i / bar_height))
            overlay_draw.line(
                [(bx // 4, by - 20 - i), (3 * bx // 4, by - 20 - i)],
                fill=(*accent_color, alpha), width=1
            )
        for i in range(15):
            alpha = int(30 * (1 - i / 15))
            overlay_draw.line(
                [(bx // 4 + 20, by - 20 + i), (3 * bx // 4 - 20, by - 20 + i)],
                fill=(*accent_color, alpha), width=1
            )
        bg = Image.alpha_composite(bg, overlay)

        avatar_size = 200
        pfp_circle = self.circle(pfp, size=(avatar_size, avatar_size))
        avatar_x = bx // 2 - avatar_size // 2
        avatar_y = by // 2 - avatar_size // 2 - 50

        ring_layer = Image.new("RGBA", (bx, by), (0, 0, 0, 0))
        ring_draw = ImageDraw.Draw(ring_layer)
        center = (bx // 2, by // 2 - 50)
        self.draw_glow_ring(ring_draw, center, avatar_size // 2, color=accent_color, ring_width=4, glow_layers=16)
        bg = Image.alpha_composite(bg, ring_layer)

        bg.paste(pfp_circle, (avatar_x, avatar_y), pfp_circle)

        decor_layer = Image.new("RGBA", (bx, by), (0, 0, 0, 0))
        decor_draw = ImageDraw.Draw(decor_layer)
        self.draw_decorative_dots(decor_draw, bx, by)
        self.draw_line_accents(decor_draw, bx, by)

        sep_y = by // 2 - avatar_size // 2 - 80
        line_len = 160
        for i in range(line_len):
            decor_draw.point((bx // 2 - 200 - line_len + i, sep_y), fill=(255, 255, 255, int(50 * (i / line_len))))
            decor_draw.point((bx // 2 + 200 + i, sep_y), fill=(255, 255, 255, int(50 * (1 - i / line_len))))

        bg = Image.alpha_composite(bg, decor_layer)

        text_layer = Image.new("RGBA", (bx, by), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        text_draw.text(
            (bx // 2, sep_y), "W E L C O M E   T O",
            fill=(255, 255, 255, 200), anchor="mm", font=self.font["subtitle"]
        )

        header_text = "BIT DISCORD"
        for offset in range(6, 0, -1):
            text_draw.text(
                (bx // 2, by // 2 + avatar_size // 2 + 20), header_text,
                fill=(*accent_color, int(20 * (1 - offset / 6))), anchor="mm", font=self.font["header"]
            )
        text_draw.text(
            (bx // 2, by // 2 + avatar_size // 2 + 20), header_text,
            fill=(255, 255, 255, 255), anchor="mm", font=self.font["header"]
        )

        display_name = username if len(username) <= 24 else username[:21] + "..."
        text_draw.text(
            (bx // 2, by // 2 + avatar_size // 2 + 80), display_name,
            fill=(200, 200, 220, 200), anchor="mm", font=self.font["username"]
        )

        if member_count:
            text_draw.text(
                (bx // 2, by - 50), f"Member #{member_count}",
                fill=(150, 150, 180, 150), anchor="mm", font=self.font["subtitle"]
            )

        bg = Image.alpha_composite(bg, text_layer)
        final = bg.convert("RGB")

        with BytesIO() as image_binary:
            final.save(image_binary, "PNG", quality=95)
            image_binary.seek(0)
            return discord.File(fp=image_binary, filename="welcome.png")