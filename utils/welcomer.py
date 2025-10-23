from PIL import Image, ImageDraw, ImageFont, ImageChops
import discord
from io import BytesIO


class WeclomeBanner():
    def __init__(self):
        self.font = {
            "header": ImageFont.truetype("assets/fonts/MAKISUPA.ttf", 150),
            "username": ImageFont.truetype("assets/fonts/MAKISUPA.ttf", 80),
        }
    
    def circle(self, pfp, size=(350, 350)):
        pfp = pfp.resize(size).convert("RGBA")

        bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
        mask = Image.new("L", bigsize, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + bigsize, fill=255)
        mask = mask.resize(pfp.size)
        mask = ImageChops.darker(mask, pfp.split()[-1])
        pfp.putalpha(mask)
        return pfp


    def make_banner(self, username, pfp):

        pfp = Image.open(pfp)
        bg = Image.open("assets/images/background.png")        
        pfp = self.circle(pfp)


        bx, by = bg.size


        header = "Welcome to BIT"


        bg.paste(pfp, ((bx//2)-(pfp.size[0]//2), by//4), pfp)


        draw = ImageDraw.Draw(bg)
        draw.text((bx//2, by//9), header, fill="#ffff", anchor="mm", font=self.font["header"])
        draw.text((bx//2, by-by//6), username, fill="#ffff", anchor="mm", font=self.font["username"])


        with BytesIO() as image_binary:
            bg.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp = image_binary, filename="welcome.png")
            return file