import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import VOICE_LOBBY_CHANNEL_ID, VOICE_CATEGORY_ID, Colors
from utils.ui.voicechannel import VoiceChannelView
import time


class VoiceChannel(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot
        self.channel_counter = 0

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VoiceChannelView())
        count = await self.bot.db.voice_channels.count_documents({})
        self.channel_counter = count
        self.bot.log.info(f"VoiceChannel → Loaded {count} active voice channels")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        if after.channel and after.channel.id == VOICE_LOBBY_CHANNEL_ID:
            await self.create_voice_channel(member, after.channel)
        
        if before.channel and before.channel != after.channel:
            await self.handle_leave(member, before.channel)

    async def create_voice_channel(self, member: discord.Member, lobby: discord.VoiceChannel):
        category = member.guild.get_channel(VOICE_CATEGORY_ID)
        if not category:
            category = lobby.category

        self.channel_counter += 1
        channel_name = f"🔈・│Voice {self.channel_counter}"

        try:
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    connect=True,
                    speak=True
                ),
                member: discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    mute_members=True,
                    move_members=True,
                    manage_channels=True
                ),
                member.guild.me: discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    mute_members=True,
                    move_members=True,
                    manage_channels=True
                )
            }

            voice_channel = await category.create_voice_channel(
                name=channel_name,
                overwrites=overwrites
            )

            await member.move_to(voice_channel)

            await self.bot.db.voice_channels.insert_one({
                "channel_id": voice_channel.id,
                "text_channel_id": voice_channel.id,
                "manager_id": member.id,
                "created_at": int(time.time()),
                "guild_id": member.guild.id
            })

            await self.send_control_panel(voice_channel, member)

        except discord.Forbidden:
            self.bot.log.error(f"VoiceChannel → Failed to create channel for {member}")
        except Exception as e:
            self.bot.log.error(f"VoiceChannel → Error creating channel: {e}")

    async def send_control_panel(self, channel: discord.VoiceChannel, manager: discord.Member):
        embed = discord.Embed(
            title="🎛️ Voice Channel Control Panel",
            description=(
                f"**Welcome to your voice channel!**\n\n"
                f"👑 **Creator:** {manager.mention}\n"
                f"🔊 **Created at:** <t:{int(channel.created_at.timestamp())}:f>\n\n"
                f"Use the buttons below to manage your channel."
            ),
            color=Colors.GREEN
        )
        embed.add_field(
            name="📝 Rename",
            value="Change the channel name",
            inline=True
        )
        embed.add_field(
            name="🔒 Lock",
            value="Prevent new users from joining",
            inline=True
        )
        embed.add_field(
            name="👥 User Limit",
            value="Set max users (0 = unlimited)",
            inline=True
        )
        embed.add_field(
            name="👑 Transfer",
            value="Give ownership to another user",
            inline=True
        )
        embed.add_field(
            name="🗑️ Delete",
            value="Delete the voice channel",
            inline=True
        )
        embed.add_field(
            name="🔇 Mute",
            value="Mute/unmute a user",
            inline=True
        )
        embed.add_field(
            name="👢 Kick",
            value="Kick a user from the channel",
            inline=True
        )
        embed.add_field(
            name="🚫 Ban",
            value="Ban a user from the channel",
            inline=True
        )
        embed.set_footer(text="Only the channel manager can use these controls")

        try:
            await channel.send(embed=embed, view=VoiceChannelView())
        except discord.Forbidden:
            self.bot.log.warning(f"VoiceChannel → Cannot send message in {channel.name}")

    async def handle_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        data = await self.bot.db.voice_channels.find_one({"channel_id": channel.id})
        if not data:
            return

        if len(channel.members) == 0:
            await self.delete_voice_channel(channel)
            return

        if data["manager_id"] == member.id:
            await self.transfer_ownership(channel, data)

    async def transfer_ownership(self, channel: discord.VoiceChannel, data: dict):
        if len(channel.members) == 0:
            await self.delete_voice_channel(channel)
            return

        new_manager = channel.members[0]

        await self.bot.db.voice_channels.update_one(
            {"channel_id": channel.id},
            {"$set": {"manager_id": new_manager.id}}
        )

        try:
            await channel.set_permissions(
                new_manager,
                connect=True,
                speak=True,
                mute_members=True,
                move_members=True,
                manage_channels=True
            )
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="👑 New Channel Manager",
            description=f"{new_manager.mention} is now the manager of this voice channel.",
            color=Colors.GREEN
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    async def delete_voice_channel(self, channel: discord.VoiceChannel):
        try:
            await self.bot.db.voice_channels.delete_one({"channel_id": channel.id})
            await channel.delete()
        except discord.NotFound:
            await self.bot.db.voice_channels.delete_one({"channel_id": channel.id})
        except discord.Forbidden:
            self.bot.log.warning(f"VoiceChannel → Cannot delete {channel.name}")
        except Exception as e:
            self.bot.log.error(f"VoiceChannel → Error deleting channel: {e}")

    @commands.command(name="vccleanup")
    @commands.has_permissions(administrator=True)
    async def vc_cleanup(self, ctx: commands.Context):
        """Clean up orphaned voice channel database entries"""
        cursor = self.bot.db.voice_channels.find({"guild_id": ctx.guild.id})
        cleaned = 0
        
        async for doc in cursor:
            channel = ctx.guild.get_channel(doc["channel_id"])
            if not channel:
                await self.bot.db.voice_channels.delete_one({"channel_id": doc["channel_id"]})
                cleaned += 1
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Removed **{cleaned}** orphaned database entries.",
            color=Colors.GREEN
        )
        await ctx.send(embed=embed)


async def setup(bot: BoBit):
    await bot.add_cog(VoiceChannel(bot))
