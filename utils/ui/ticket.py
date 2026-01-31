import time
import discord
from discord import ui
from utils.consts import OPEN_TICKET_CATEGORY, CLOSED_TICKET_CATEGORY, TICKET_HANDLER_ROLE_ID, TICKET_LOG_CHANNEL


class ReasonModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Ticket Reason", timeout=None)

        self.add_item(
            discord.ui.TextInput(
                label="Reason",
                placeholder="Enter Reason",
                style=discord.TextStyle.short,
                default="No reason provided",
                required=True,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = self.children[0].value

        await interaction.response.defer(ephemeral=True)
        category: discord.CategoryChannel = discord.utils.get(interaction.guild.categories, id=OPEN_TICKET_CATEGORY)
        for ch in category.text_channels:
            if ch.topic == f"{interaction.user.id} DO NOT CHANGE THE TOPIC OF THIS CHANNEL!":
                await interaction.followup.send("You already have a ticket in {0}".format(ch.mention), ephemeral=True)
                return

        r1: discord.Role = interaction.guild.get_role(TICKET_HANDLER_ROLE_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            r1: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await category.create_text_channel(
            name=str(interaction.user),
            topic=f"{interaction.user.id} DO NOT CHANGE THE TOPIC OF THIS CHANNEL!",
            overwrites=overwrites
        )
        i_msg = await channel.send(
            embed=discord.Embed(
                title="Ticket Created!",
                description="Don't ping a staff member, they will be here soon.",
                color=discord.Color.green()
            ).add_field(name="📖 Reason", value=reason),
            view=CloseButton()
        )
        await i_msg.pin()
        await interaction.followup.send(
            embed=discord.Embed(
                description="Created your ticket in {0}".format(channel.mention),
                color=discord.Color.blurple()
            ),
            ephemeral=True
        )

        log_channel = interaction.guild.get_channel(TICKET_LOG_CHANNEL)
        ticket_id = int(time.time())
        embed = discord.Embed(
            title="Ticket Created",
            color=0xe5ffb8
        ).add_field(
            name="🆔 Ticket ID",
            value=str(ticket_id),
            inline=True
        ).add_field(
            name="📬 Opened By",
            value=f"{interaction.user.mention}",
            inline=True
        ).add_field(
            name="📪 Closed By",
            value=f"Not closed yet",
            inline=True
        ).add_field(
            name="📖 Reason",
            value=f"{reason}",
            inline=True
        ).add_field(
            name="🕑 Opened at",
            value=f"<t:{ticket_id}>",
            inline=True
        ).add_field(
            name="🕑 Closed at",
            value=f"Not closed yet",
            inline=True
        ).set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)

        v = ui.View()
        btn = ui.Button(label="Open", url=i_msg.jump_url)
        v.add_item(btn)

        msg = await log_channel.send(
            content=f"{r1.mention}",
            embed=embed,
            view=v,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

        await interaction.client.db.tickets.insert_one({
            "message_id": msg.id,
            "ticket_id": ticket_id,
            "opened_by": interaction.user.id,
            "closed_by": None,
            "opened_at": ticket_id,
            "closed_at": None,
            "reason": reason
        })


class CreateButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(style=discord.ButtonStyle.blurple, emoji="🎫", custom_id="ticketopen")
    async def ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReasonModal())


class CloseButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close the ticket", style=discord.ButtonStyle.red, custom_id="closeticket", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        await interaction.channel.send("Closing this ticket!", delete_after=10)

        category: discord.CategoryChannel = discord.utils.get(interaction.guild.categories, id=CLOSED_TICKET_CATEGORY)
        r1: discord.Role = interaction.guild.get_role(TICKET_HANDLER_ROLE_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            r1: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        await interaction.channel.edit(category=category, overwrites=overwrites)
        member = interaction.guild.get_member(int(interaction.channel.topic.split(" ")[0]))
        await interaction.channel.send(
            embed=discord.Embed(
                description="Ticket Closed!",
                color=discord.Color.red()
            ),
        )

        data = await interaction.client.db.tickets.find_one(
            {"opened_by": member.id},
            sort=[("opened_at", -1)]
        )

        if not data:
            return

        ticket_id = data["ticket_id"]
        message_id = data["message_id"]
        reason = data["reason"]
        closed_at = int(time.time())

        await interaction.channel.edit(topic=f"{ticket_id} DO NOT CHANGE THE TOPIC")
        await interaction.message.edit(view = TrashButton())
        log_channel = interaction.guild.get_channel(TICKET_LOG_CHANNEL)
        msg = await log_channel.fetch_message(message_id)

        embed = discord.Embed(
            title="Ticket Closed",
            color=0xffb8c4
        ).add_field(
            name="🆔 Ticket ID",
            value=str(ticket_id),
            inline=True
        ).add_field(
            name="📬 Opened By",
            value=f"{member.mention}",
            inline=True
        ).add_field(
            name="📪 Closed By",
            value=f"{interaction.user.mention}",
            inline=True
        ).add_field(
            name="📖 Reason",
            value=f"{reason}",
            inline=True
        ).add_field(
            name="🕑 Opened at",
            value=f"<t:{ticket_id}>",
            inline=True
        ).add_field(
            name="🕑 Closed at",
            value=f"<t:{closed_at}>",
            inline=True
        ).set_author(name=member.name, icon_url=member.avatar.url)

        await msg.edit(content=None, embeds=[embed], view = None)

        await interaction.client.db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"closed_by": interaction.user.id, "closed_at": closed_at}}
        )

        try:
            await member.send(embed=embed)
        except:
            pass


class TrashButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Delete", style=discord.ButtonStyle.red, emoji="🚮", custom_id="trash")
    async def trash(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.channel.send("Deleting the ticket!")
        ticket_id = int(interaction.channel.topic.split(" ")[0])

        await interaction.channel.delete()
        await interaction.client.db.tickets.delete_one({"ticket_id": ticket_id})