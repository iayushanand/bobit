import discord
from discord.ext import commands
from utils.bot import BoBit
from utils.consts import LOG_CHANNEL_ID, Colors
from datetime import datetime, timezone


class EventLogger(commands.Cog):
    def __init__(self, bot: BoBit):
        self.bot = bot

    def get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        return guild.get_channel(LOG_CHANNEL_ID)

    async def send_log(
        self,
        guild: discord.Guild,
        embed: discord.Embed
    ):
        channel = self.get_log_channel(guild)
        if channel:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )

        content = message.content or "*[No text content]*"
        if len(content) > 1024:
            content = content[:1021] + "..."

        embed.add_field(name="Author", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=content, inline=False)

        if message.attachments:
            attachment_list = "\n".join([a.filename for a in message.attachments])
            embed.add_field(name="Attachments", value=attachment_list, inline=False)

        embed.set_footer(text=f"Message ID: {message.id}")

        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=Colors.ORANGE,
            timestamp=datetime.now(timezone.utc)
        )

        before_content = before.content or "*[Empty]*"
        after_content = after.content or "*[Empty]*"

        if len(before_content) > 1024:
            before_content = before_content[:1021] + "..."
        if len(after_content) > 1024:
            after_content = after_content[:1021] + "..."

        embed.add_field(name="Author", value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before_content, inline=False)
        embed.add_field(name="After", value=after_content, inline=False)
        embed.add_field(name="Jump to Message", value=f"[Click Here]({after.jump_url})", inline=False)

        embed.set_footer(text=f"Message ID: {after.id}")

        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="📥 Member Joined",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )

        account_age = datetime.now(timezone.utc) - member.created_at
        days = account_age.days

        if days < 7:
            age_warning = f"⚠️ **{days} days old** (Possible alt)"
        else:
            age_warning = f"{days} days old"

        embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=True)
        embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
        embed.add_field(
            name="Account Created",
            value=f"{discord.utils.format_dt(member.created_at, 'F')}\n{age_warning}",
            inline=False
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="📤 Member Left",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )

        roles = [r.mention for r in member.roles if r != member.guild.default_role]
        roles_str = ", ".join(roles) if roles else "None"

        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Roles", value=roles_str[:1024], inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)

        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="🔨 Member Banned",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                if entry.target.id == user.id:
                    embed.add_field(name="Banned By", value=entry.user.mention, inline=True)
                    embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=False)
                    break
        except discord.Forbidden:
            embed.add_field(name="Audit Log", value="*Unable to access audit logs*", inline=False)

        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="🔓 Member Unbanned",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=5):
                if entry.target.id == user.id:
                    embed.add_field(name="Unbanned By", value=entry.user.mention, inline=True)
                    embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=False)
                    break
        except discord.Forbidden:
            embed.add_field(name="Audit Log", value="*Unable to access audit logs*", inline=False)

        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="🔊 Joined Voice Channel",
                color=Colors.GREEN,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=True)
            embed.add_field(name="Channel", value=after.channel.mention, inline=True)

        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="🔇 Left Voice Channel",
                color=Colors.RED,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=True)
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)

        else:
            embed = discord.Embed(
                title="🔀 Moved Voice Channel",
                color=Colors.ORANGE,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=True)
            embed.add_field(name="From", value=before.channel.mention, inline=True)
            embed.add_field(name="To", value=after.channel.mention, inline=True)

        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        if not messages or not messages[0].guild:
            return

        guild = messages[0].guild
        channel = messages[0].channel

        embed = discord.Embed(
            title="🗑️ Bulk Messages Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Count", value=f"{len(messages)} messages", inline=True)

        authors = set(m.author for m in messages if m.author)
        if authors:
            author_list = ", ".join([str(a) for a in list(authors)[:5]])
            if len(authors) > 5:
                author_list += f" (+{len(authors) - 5} more)"
            embed.add_field(name="Authors", value=author_list, inline=False)

        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Nickname Changed",
                color=Colors.ORANGE,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
            embed.add_field(name="Before", value=before.nick or "*None*", inline=True)
            embed.add_field(name="After", value=after.nick or "*None*", inline=True)
            embed.set_thumbnail(url=after.display_avatar.url)
            await self.send_log(after.guild, embed)

        before_roles = set(before.roles)
        after_roles = set(after.roles)

        added = after_roles - before_roles
        removed = before_roles - after_roles

        if added or removed:
            embed = discord.Embed(
                title="🎭 Roles Updated",
                color=Colors.ORANGE,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)

            if added:
                embed.add_field(name="Added", value=", ".join(r.mention for r in added), inline=False)
            if removed:
                embed.add_field(name="Removed", value=", ".join(r.mention for r in removed), inline=False)

            embed.set_thumbnail(url=after.display_avatar.url)
            await self.send_log(after.guild, embed)

        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until and after.timed_out_until > datetime.now(timezone.utc):
                embed = discord.Embed(
                    title="⏳ Member Timed Out",
                    color=Colors.ORANGE,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
                embed.add_field(name="Until", value=discord.utils.format_dt(after.timed_out_until, "F"), inline=True)

                try:
                    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=5):
                        if entry.target.id == after.id:
                            embed.add_field(name="Moderator", value=entry.user.mention, inline=True)
                            embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=False)
                            break
                except discord.Forbidden:
                    pass

                embed.set_thumbnail(url=after.display_avatar.url)
                await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="📁 Channel Created",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=f"{channel.mention} (`{channel.name}`)", inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title(), inline=True)

        if channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)

        try:
            async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=5):
                if entry.target.id == channel.id:
                    embed.add_field(name="Created By", value=entry.user.mention, inline=True)
                    break
        except discord.Forbidden:
            pass

        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=f"`{channel.name}`", inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title(), inline=True)

        try:
            async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=5):
                if entry.target.id == channel.id:
                    embed.add_field(name="Deleted By", value=entry.user.mention, inline=True)
                    break
        except discord.Forbidden:
            pass

        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(
            title="🎨 Role Created",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Role", value=f"{role.mention} (`{role.name}`)", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=5):
                if entry.target.id == role.id:
                    embed.add_field(name="Created By", value=entry.user.mention, inline=True)
                    break
        except discord.Forbidden:
            pass

        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(
            title="🗑️ Role Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Role", value=f"`{role.name}`", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=5):
                if entry.target.id == role.id:
                    embed.add_field(name="Deleted By", value=entry.user.mention, inline=True)
                    break
        except discord.Forbidden:
            pass

        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
        if before.permissions != after.permissions:
            changes.append("**Permissions:** Modified")

        if not changes:
            return

        embed = discord.Embed(
            title="🔧 Role Updated",
            color=Colors.ORANGE,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Role", value=after.mention, inline=True)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)

        await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        embed = discord.Embed(
            title="🔗 Invite Created",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)
        embed.add_field(name="Created By", value=invite.inviter.mention if invite.inviter else "Unknown", inline=True)

        if invite.max_uses:
            embed.add_field(name="Max Uses", value=str(invite.max_uses), inline=True)
        if invite.max_age:
            embed.add_field(name="Expires In", value=f"{invite.max_age // 3600}h", inline=True)

        await self.send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        embed = discord.Embed(
            title="🔗 Invite Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)

        await self.send_log(invite.guild, embed)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Created",
            color=Colors.GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Thread", value=thread.mention, inline=True)
        embed.add_field(name="Parent", value=thread.parent.mention if thread.parent else "Unknown", inline=True)
        embed.add_field(name="Owner", value=f"<@{thread.owner_id}>", inline=True)

        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Deleted",
            color=Colors.RED,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Thread", value=f"`{thread.name}`", inline=True)
        embed.add_field(name="Parent", value=thread.parent.mention if thread.parent else "Unknown", inline=True)

        await self.send_log(thread.guild, embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: tuple[discord.Emoji],
        after: tuple[discord.Emoji]
    ):
        before_set = set(before)
        after_set = set(after)

        added = after_set - before_set
        removed = before_set - after_set

        if added:
            embed = discord.Embed(
                title="😀 Emoji Added",
                color=Colors.GREEN,
                timestamp=datetime.now(timezone.utc)
            )
            for emoji in added:
                embed.add_field(name="Emoji", value=f"{emoji} (`:{emoji.name}:`)", inline=True)
            await self.send_log(guild, embed)

        if removed:
            embed = discord.Embed(
                title="😢 Emoji Removed",
                color=Colors.RED,
                timestamp=datetime.now(timezone.utc)
            )
            for emoji in removed:
                embed.add_field(name="Emoji", value=f"`:{emoji.name}:`", inline=True)
            await self.send_log(guild, embed)


async def setup(bot: BoBit):
    await bot.add_cog(EventLogger(bot))
