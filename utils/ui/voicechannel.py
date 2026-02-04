import discord
from discord import ui
from utils.consts import Colors


class RenameModal(ui.Modal):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(title="🔊 Rename Voice Channel", timeout=300)
        self.channel = channel
        self.add_item(
            ui.TextInput(
                label="New Channel Name",
                placeholder="Enter a new name for your voice channel...",
                style=discord.TextStyle.short,
                required=True,
                max_length=100,
                default=channel.name[3:]
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.children[0].value
        try:
            await self.channel.edit(name=f"🔈・│{new_name}")
            embed = discord.Embed(
                title="✅ Channel Renamed",
                description=f"Channel renamed to **🔈・│{new_name}**",
                color=Colors.GREEN
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="I don't have permission to rename this channel.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class UserLimitModal(ui.Modal):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(title="👥 Set User Limit", timeout=300)
        self.channel = channel
        self.add_item(
            ui.TextInput(
                label="User Limit (0 = Unlimited)",
                placeholder="Enter a number between 0 and 99...",
                style=discord.TextStyle.short,
                required=True,
                max_length=2,
                default=str(channel.user_limit) if channel.user_limit else "0"
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.children[0].value)
            if limit < 0 or limit > 99:
                raise ValueError("Limit must be between 0 and 99")
            
            await self.channel.edit(user_limit=limit)
            limit_text = f"**{limit} users**" if limit > 0 else "**Unlimited**"
            embed = discord.Embed(
                title="✅ User Limit Updated",
                description=f"User limit set to {limit_text}",
                color=Colors.GREEN
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="Please enter a valid number between 0 and 99.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="I don't have permission to modify this channel.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class UserActionSelect(ui.Select):
    def __init__(self, members: list[discord.Member], action: str, channel: discord.VoiceChannel):
        self.action = action
        self.voice_channel = channel
        
        options = [
            discord.SelectOption(
                label=member.display_name,
                value=str(member.id),
                emoji="👤"
            )
            for member in members[:25]
        ]
        
        action_labels = {
            "mute": "🔇 Select User to Mute",
            "kick": "👢 Select User to Kick",
            "ban": "🚫 Select User to Ban"
        }
        
        super().__init__(
            placeholder=action_labels.get(action, "Select a user..."),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"vc_user_action_{action}"
        )

    async def callback(self, interaction: discord.Interaction):
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        
        if not member:
            embed = discord.Embed(
                title="❌ User Not Found",
                description="This user is no longer in the server.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            if self.action == "mute":
                if member.voice and member.voice.channel == self.voice_channel:
                    await member.edit(mute=not member.voice.mute)
                    status = "muted" if not member.voice.mute else "unmuted"
                    embed = discord.Embed(
                        title=f"🔇 User {status.title()}",
                        description=f"{member.mention} has been {status}.",
                        color=Colors.GREEN
                    )
                else:
                    embed = discord.Embed(
                        title="❌ User Not in Channel",
                        description="This user is not in your voice channel.",
                        color=Colors.RED
                    )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif self.action == "kick":
                if member.voice and member.voice.channel == self.voice_channel:
                    await member.move_to(None)
                    embed = discord.Embed(
                        title="👢 User Kicked",
                        description=f"{member.mention} has been kicked from the voice channel.",
                        color=Colors.GREEN
                    )
                else:
                    embed = discord.Embed(
                        title="❌ User Not in Channel",
                        description="This user is not in your voice channel.",
                        color=Colors.RED
                    )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif self.action == "ban":
                if member.voice and member.voice.channel == self.voice_channel:
                    await member.move_to(None)
                await self.voice_channel.set_permissions(member, connect=False)
                embed = discord.Embed(
                    title="🚫 User Banned",
                    description=f"{member.mention} has been banned from this voice channel.",
                    color=Colors.GREEN
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="I don't have permission to perform this action.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class UserSelectView(ui.View):
    def __init__(self, members: list[discord.Member], action: str, channel: discord.VoiceChannel):
        super().__init__(timeout=60)
        self.add_item(UserActionSelect(members, action, channel))


class TransferOwnershipSelect(ui.Select):
    def __init__(self, members: list[discord.Member], channel_id: int):
        self.channel_id = channel_id
        
        options = [
            discord.SelectOption(
                label=member.display_name,
                value=str(member.id),
                emoji="👑"
            )
            for member in members[:25]
        ]
        
        super().__init__(
            placeholder="👑 Select New Owner",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="vc_transfer_ownership"
        )

    async def callback(self, interaction: discord.Interaction):
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        
        if not member:
            embed = discord.Embed(
                title="❌ User Not Found",
                description="This user is no longer in the server.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.client.db.voice_channels.update_one(
            {"channel_id": self.channel_id},
            {"$set": {"manager_id": member_id}}
        )
        
        embed = discord.Embed(
            title="👑 Ownership Transferred",
            description=f"{member.mention} is now the manager of this voice channel.",
            color=Colors.GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TransferSelectView(ui.View):
    def __init__(self, members: list[discord.Member], channel_id: int):
        super().__init__(timeout=60)
        self.add_item(TransferOwnershipSelect(members, channel_id))


class VoiceChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_manager(self, interaction: discord.Interaction) -> bool:
        data = await interaction.client.db.voice_channels.find_one(
            {"text_channel_id": interaction.channel.id}
        )
        if not data:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        
        if data["manager_id"] != interaction.user.id:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="Only the channel manager can use these controls.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        
        return True

    async def get_voice_channel(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        data = await interaction.client.db.voice_channels.find_one(
            {"text_channel_id": interaction.channel.id}
        )
        if not data:
            return None
        return interaction.guild.get_channel(data["channel_id"])

    @ui.button(label="Rename", style=discord.ButtonStyle.blurple, emoji="📝", custom_id="vc_rename", row=0)
    async def rename(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_modal(RenameModal(channel))

    @ui.button(label="Lock", style=discord.ButtonStyle.gray, emoji="🔒", custom_id="vc_lock", row=0)
    async def lock(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        overwrites = channel.overwrites_for(interaction.guild.default_role)
        is_locked = overwrites.connect is False
        
        overwrites.connect = None if is_locked else False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrites)
        
        status = "unlocked 🔓" if is_locked else "locked 🔒"
        embed = discord.Embed(
            title=f"✅ Channel {status.title()}",
            description=f"Your voice channel is now **{status}**.",
            color=Colors.GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="User Limit", style=discord.ButtonStyle.gray, emoji="👥", custom_id="vc_limit", row=0)
    async def user_limit(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_modal(UserLimitModal(channel))

    @ui.button(label="Transfer", style=discord.ButtonStyle.green, emoji="👑", custom_id="vc_transfer", row=0)
    async def transfer(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        members = [m for m in channel.members if m.id != interaction.user.id]
        if not members:
            embed = discord.Embed(
                title="❌ No Members",
                description="There are no other members in the channel to transfer ownership to.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        data = await interaction.client.db.voice_channels.find_one(
            {"text_channel_id": interaction.channel.id}
        )
        await interaction.response.send_message(
            "Select the new owner:",
            view=TransferSelectView(members, data["channel_id"]),
            ephemeral=True
        )

    @ui.button(label="Delete", style=discord.ButtonStyle.red, emoji="🗑️", custom_id="vc_delete", row=1)
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        data = await interaction.client.db.voice_channels.find_one(
            {"text_channel_id": interaction.channel.id}
        )
        if not data:
            return
        
        channel = interaction.guild.get_channel(data["channel_id"])
        
        await interaction.response.send_message("🗑️ Deleting voice channel...", ephemeral=True)
        
        if channel:
            await channel.delete()
        
        await interaction.client.db.voice_channels.delete_one({"channel_id": data["channel_id"]})

    @ui.button(label="Mute", style=discord.ButtonStyle.gray, emoji="🔇", custom_id="vc_mute", row=1)
    async def mute(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        members = [m for m in channel.members if m.id != interaction.user.id]
        if not members:
            embed = discord.Embed(
                title="❌ No Members",
                description="There are no other members in the channel to mute.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Select a user to mute/unmute:",
            view=UserSelectView(members, "mute", channel),
            ephemeral=True
        )

    @ui.button(label="Kick", style=discord.ButtonStyle.gray, emoji="👢", custom_id="vc_kick", row=1)
    async def kick(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        members = [m for m in channel.members if m.id != interaction.user.id]
        if not members:
            embed = discord.Embed(
                title="❌ No Members",
                description="There are no other members in the channel to kick.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Select a user to kick:",
            view=UserSelectView(members, "kick", channel),
            ephemeral=True
        )

    @ui.button(label="Ban", style=discord.ButtonStyle.red, emoji="🚫", custom_id="vc_ban", row=1)
    async def ban(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_manager(interaction):
            return
        
        channel = await self.get_voice_channel(interaction)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="This voice channel no longer exists.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        members = [m for m in channel.members if m.id != interaction.user.id]
        if not members:
            embed = discord.Embed(
                title="❌ No Members",
                description="There are no other members in the channel to ban.",
                color=Colors.RED
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Select a user to ban from this channel:",
            view=UserSelectView(members, "ban", channel),
            ephemeral=True
        )
