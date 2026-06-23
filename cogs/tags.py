import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import Colors
import time

class Tags(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    @commands.group(name="tag", invoke_without_command=True)
    async def tag_group(self, ctx: commands.Context, *, name: str):
        tag = await self.bot.db.tags.find_one({"_id": name.lower()})
        
        if not tag:
            embed = discord.Embed(
                description=f"❌ Tag `{name}` not found. Use `.tag create {name} <content>` to make it.",
                color=Colors.RED
            )
            await ctx.send(embed=embed)
            return
            
        await self.bot.db.tags.update_one({"_id": name.lower()}, {"$inc": {"uses": 1}})
        await ctx.send(tag["content"])

    @tag_group.command(name="create", aliases=["add", "make"])
    async def tag_create(self, ctx: commands.Context, name: str, *, content: str):
        name = name.lower()
        if len(name) > 32:
            return await ctx.send("❌ Tag name must be 32 characters or less.")
            
        existing = await self.bot.db.tags.find_one({"_id": name})
        if existing:
            return await ctx.send("❌ That tag already exists!")
            
        await self.bot.db.tags.insert_one({
            "_id": name,
            "content": content,
            "author_id": ctx.author.id,
            "created_at": int(time.time()),
            "uses": 0
        })
        
        embed = discord.Embed(
            description=f"✅ Successfully created tag `{name}`",
            color=Colors.GREEN
        )
        await ctx.send(embed=embed)

    @tag_group.command(name="edit")
    async def tag_edit(self, ctx: commands.Context, name: str, *, new_content: str):
        name = name.lower()
        tag = await self.bot.db.tags.find_one({"_id": name})
        
        if not tag:
            return await ctx.send(f"❌ Tag `{name}` not found!")
            
        if tag["author_id"] != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ You don't own this tag!")
            
        await self.bot.db.tags.update_one(
            {"_id": name},
            {"$set": {"content": new_content}}
        )
        
        embed = discord.Embed(
            description=f"✅ Successfully edited tag `{name}`",
            color=Colors.GREEN
        )
        await ctx.send(embed=embed)

    @tag_group.command(name="delete", aliases=["remove"])
    async def tag_delete(self, ctx: commands.Context, name: str):
        name = name.lower()
        tag = await self.bot.db.tags.find_one({"_id": name})
        
        if not tag:
            return await ctx.send(f"❌ Tag `{name}` not found!")
            
        if tag["author_id"] != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ You don't own this tag!")
            
        await self.bot.db.tags.delete_one({"_id": name})
        
        embed = discord.Embed(
            description=f"✅ Successfully deleted tag `{name}`",
            color=Colors.GREEN
        )
        await ctx.send(embed=embed)

    @tag_group.command(name="info")
    async def tag_info(self, ctx: commands.Context, name: str):
        name = name.lower()
        tag = await self.bot.db.tags.find_one({"_id": name})
        
        if not tag:
            return await ctx.send(f"❌ Tag `{name}` not found!")
            
        owner = self.bot.get_user(tag["author_id"])
        owner_name = owner.mention if owner else f"Unknown ID ({tag['author_id']})"
        
        embed = discord.Embed(title=f"Tag: {name}", color=Colors.BLURPLE)
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Uses", value=tag.get("uses", 0), inline=True)
        embed.add_field(name="Created At", value=f"<t:{tag['created_at']}:R>", inline=False)
        
        await ctx.send(embed=embed)

    @tag_group.command(name="list")
    async def tag_list(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        cursor = self.bot.db.tags.find({"author_id": member.id}).sort("uses", -1)
        tags = await cursor.to_list(length=20)
        
        if not tags:
            return await ctx.send(f"❌ {member.display_name} has no tags!")
            
        tag_list = "\n".join([f"• `{t['_id']}` (Uses: {t.get('uses', 0)})" for t in tags])
        
        embed = discord.Embed(
            title=f"Tags for {member.display_name} (Top 20)",
            description=tag_list,
            color=Colors.BLURPLE
        )
        await ctx.send(embed=embed)

    @tag_group.command(name="all")
    async def tag_all(self, ctx: commands.Context):
        cursor = self.bot.db.tags.find({}).sort("uses", -1)
        tags = await cursor.to_list(length=None)
        
        if not tags:
            return await ctx.send("❌ No tags have been created yet!")
            
        tag_list = ", ".join([f"`{t['_id']}`" for t in tags])
        
        embed = discord.Embed(
            title="All Available Tags",
            description=tag_list[:4000],
            color=Colors.BLURPLE
        )
        await ctx.send(embed=embed)

async def setup(bot: BoBit):
    await bot.add_cog(Tags(bot))
