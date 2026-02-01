import discord
from discord import ui
from utils.consts import VENT_CHANNEL_ID, Colors


class VentModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Anonymous Vent", timeout=300)
        self.add_item(
            ui.TextInput(
                label="What's on your mind?",
                placeholder="Let it all out... This is completely anonymous.",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=2000
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        vent_content = self.children[0].value
        vent_channel = interaction.guild.get_channel(VENT_CHANNEL_ID)
        
        if not vent_channel:
            await interaction.response.send_message(
                "❌ Vent channel not found. Please contact an admin.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💭 Anonymous Vent",
            description=vent_content,
            color=Colors.ORANGE
        )

        await vent_channel.send(embed=embed, view=VentButton())
        await interaction.response.send_message(
            "✅ Your vent has been posted anonymously 💙.",
            ephemeral=True
        )


class VentButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Vent Anonymously", style=discord.ButtonStyle.blurple, emoji="💭", custom_id="vent_button")
    async def vent(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(VentModal())
