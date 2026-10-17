import random

from discord.ext import commands
import discord
from discord import app_commands
from utils.consts import (
    Colors,
    BLACKJACK_DEALER_CARD_LINK,
    BLACKJACK_PLAYER_CARD_LINK,
    BLACKJACK_FACE_VALUE,
    BLACKJACK_ACE_MIN,
    BLACKJACK_ACE_MAX,
    BLACKJACK_SUITS,
    BLACKJACK_TIMEOUT,
)

# conf
BJ_FACE = BLACKJACK_FACE_VALUE
BJ_ACE_MIN = BLACKJACK_ACE_MIN
BJ_ACE_MAX = BLACKJACK_ACE_MAX

SUITS = BLACKJACK_SUITS
FACES = ['A', 'J', 'Q', 'K'] + [str(x) for x in range(1, 10)]


def total(hand):
    total = 0  # noqa
    for card in hand:
        if card == " J" or card == " Q" or card == " K":
            total += BJ_FACE
        elif card == " A":
            if total >= 11:
                total += BJ_ACE_MIN
            else:
                total += BJ_ACE_MAX
        else:
            total += int(card)
    return total


def generate(player: list, dealer: list) -> str:
    global SUITS, FACES
    out_cards = player + dealer
    card = random.choice(SUITS) + " " + random.choice(FACES)
    if card in out_cards:
        generate(player, dealer)
    else:
        return card


def clean(x):
    return x.replace('♠', "").replace('♥', "").replace('♦', "").replace('♣', '')


# It's a view that has three buttons, each with a different label and style
class Buttons(discord.ui.View):
    def __init__(self, *, timeout=BLACKJACK_TIMEOUT, hands=None):
        """
        The function __init__() is a constructor that initializes the class Blackjack Game

        :param timeout: The time in seconds that the player has to make a decision, defaults to 90 (optional)
        :param hands: a dictionary of the player's and dealer's hands
        """
        super().__init__(timeout=timeout)
        if hands is None:
            hands = {"player": [], "dealer": []}
        self.hands = hands
        self.action = None
        self.SUITS = BLACKJACK_SUITS
        self.FACES = ['A', 'J', 'Q', 'K'] + [str(x) for x in range(1, 10)]
        self.outcomes = {
            "win": {"message": 'You win! ', "color": Colors.WIN_GREEN},
            "loss": {"message": 'You lose! ', "color": Colors.LOSS_RED},
            "tie": {"message": 'You tied. ', "color": Colors.TIE_YELLOW},
            "other": {"message": "", "color": Colors.TIE_YELLOW}
        }
        self.outcome = None
        self.end = False

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)  # noqa

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.blurple, custom_id="h")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button, ):  # noqa
        card = self.FACES.pop()
        self.hands['player'].append(random.choice(self.SUITS) + " " + card)
        if total(clean(x) for x in self.hands['player']) == 21:  # noqa
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) == 21:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['player']) <= 21 and len(self.hands['player']) == 5:
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) <= 21 and len(self.hands['dealer']) == 5:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['player']) > 21:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) > 21:
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) == total(clean(x) for x in self.hands['player']):
            self.outcome = self.outcomes['tie']
            self.stop()
        else:

            renderEmbed = discord.Embed(title=f"{interaction.user.name}'s blackjack game",
                                        color=Colors.BLACKJACK_DEFAULT if self.outcome is None else self.outcome['color'])
            renderEmbed.add_field(name=f"Bobit (Dealer)",
                                  value="Cards: " + ''.join(
                                      f"[`{str(self.hands['dealer'][0])} `]({BLACKJACK_DEALER_CARD_LINK}) "
                                      f"[` ? `]({BLACKJACK_DEALER_CARD_LINK})")
                                        + "\nTotal: `" + str(total([clean(x) for x in self.hands["dealer"]])) + "`")

            renderEmbed.add_field(name=f"{interaction.user.name} (Player)",
                                  value="Cards: " + ''.join(
                                      f"[`{str(x)}`]({BLACKJACK_PLAYER_CARD_LINK}) " for x in
                                      self.hands["player"]) + "\nTotal: `" + str(
                                      total(
                                          [clean(x) for x in
                                           self.hands["player"]])) + "`")
            await interaction.response.edit_message(embed=renderEmbed, view=self)  # noqa

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple, custom_id="s")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):  # noqa
        self.action = 's'
        while total([clean(x) for x in self.hands["dealer"]]) <= 17:
            card = self.FACES.pop()
            self.hands['dealer'].append(random.choice(self.SUITS) + " " + card)
        if total(clean(x) for x in self.hands['player']) == 21:  # noqa
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) == 21:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['player']) <= 21 and len(self.hands['player']) == 5:
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) <= 21 and len(self.hands['dealer']) == 5:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['player']) > 21:
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) > 21:
            self.outcome = self.outcomes['win']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) == total(clean(x) for x in self.hands['player']):
            self.outcome = self.outcomes['tie']
            self.stop()
        elif total(clean(x) for x in self.hands['dealer']) > total(clean(x) for x in self.hands['player']):
            self.outcome = self.outcomes['loss']
            self.stop()
        elif total(clean(x) for x in self.hands['player']) > total(clean(x) for x in self.hands['dealer']):
            self.outcome = self.outcomes['win']
            self.stop()
        else:
            renderEmbed = discord.Embed(title=f"{interaction.user.name}'s blackjack game",
                                        color=Colors.BLACKJACK_DEFAULT if self.outcome is None else self.outcome['color'])
            renderEmbed.add_field(name=f"Bobit (Dealer)",
                                  value="Cards: " + ''.join(
                                      f"[`{str(self.hands['dealer'][0])}`]({BLACKJACK_DEALER_CARD_LINK}) "
                                      f"[` ? `]({BLACKJACK_DEALER_CARD_LINK})")
                                        + "\nTotal: `" + str(total([clean(x) for x in self.hands["dealer"]])) + "`")

            renderEmbed.add_field(name=f"{interaction.user.name} (Player)",
                                  value="Cards: " + ''.join(
                                      f"[`{str(x)}`]({BLACKJACK_PLAYER_CARD_LINK}) " for x in
                                      self.hands["player"]) + "\nTotal: `" + str(
                                      total(
                                          [clean(x) for x in
                                           self.hands["player"]])) + "`")
            await interaction.response.edit_message(embed=renderEmbed, view=self)  # noqa

    @discord.ui.button(label="Forfeit", style=discord.ButtonStyle.blurple, custom_id="f")
    async def forfeit(self, button: discord.ui.Button, interaction: discord.Interaction):  # noqa
        self.end = True


class Blackjack(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        # It's a class that has a bunch of variables that are used in the class.
        self.bot = bot
        self.SUITS = BLACKJACK_SUITS
        self.FACES = ['A', 'J', 'Q', 'K'] + [str(x) for x in range(1, 10)]
        self.outcomes = {
            "win": {"message": 'You win! ', "color": Colors.WIN_GREEN},
            "loss": {"message": 'You lose! ', "color": Colors.LOSS_RED},
            "tie": {"message": 'You tied. ', "color": Colors.TIE_YELLOW},
            "other": {"message": "", "color": Colors.TIE_YELLOW}
        }

    @app_commands.command(description="Play blackjack")
    async def blackjack(self, interaction: discord.Interaction):
        hands = {
            "player": [],
            "dealer": []
        }
        for i in range(2):
            hands["player"].append(random.choice(self.SUITS) + " " + random.choice(self.FACES))
            hands["dealer"].append(random.choice(self.SUITS) + " " + random.choice(self.FACES))

        # making sure game doesn't start with 21 total already
        if total(clean(x) for x in hands['dealer']) > 20 or total(
                clean(x) for x in hands['player']) > 20:
            hands["player"].append(random.choice(self.SUITS) + " " + random.choice(self.FACES))
            hands["dealer"].append(random.choice(self.SUITS) + " " + random.choice(self.FACES))

        if total(clean(x) for x in hands['dealer']) > 20 or total(  # statistic improbabilty 〜(￣▽￣〜)
                clean(x) for x in hands['player']) > 20:
            hands["player"] = [' ♣ 6 ', '♣ 7']
            hands["dealer"] = [' ♣ 4', ' ♣ 9']

        renderEmbed = discord.Embed(title=f"{interaction.user.name}'s blackjack game",
                                    colour=Colors.BLACKJACK_DEFAULT)
        renderEmbed.add_field(name=f"Bobit (Dealer)",
                              value="Cards: " + ''.join(
                                  f"[`{str(hands['dealer'][0])} `]({BLACKJACK_DEALER_CARD_LINK}) "
                                  f"[` ? `]({BLACKJACK_DEALER_CARD_LINK})")
                                    + "\nTotal: `" + str(total([clean(x) for x in hands["dealer"]])) + "`")

        renderEmbed.add_field(name=f"{interaction.user.name} (Player)",
                              value="Cards: " + ''.join(
                                  f"[`{str(x)}`]({BLACKJACK_PLAYER_CARD_LINK}) " for x in
                                  hands["player"]) + "\nTotal: `" + str(
                                  total(
                                      [clean(x) for x in
                                       hands["player"]])) + "`")
        view = Buttons(hands=hands)
        await interaction.response.send_message(embed=renderEmbed, view=view)
        view.message = await interaction.original_response()

        await view.wait()
        if view.outcome is None:
            pass
            # timeout
        elif view.end:
            # game actually ended
            for child in view.children:
                child.disabled = True

            await view.message.edit(view=view)
        elif view.outcome is not None:
            outcome = view.outcome
            hands = view.hands
            # the game has ended
            PlayerScore = total([clean(x) for x in hands["player"]])
            DealerScore = total([clean(x) for x in hands["dealer"]])

            # Checking the player's score and add a detailed message to the outcome dictionary.
            if PlayerScore == 21:
                outcome['message'] = outcome['message'] + "You got to 21."
            elif DealerScore == 21:
                outcome['message'] = outcome['message'] + "The dealer got to 21 before you."
            elif PlayerScore <= 21 and len(hands['player']) == 5:
                outcome['message'] = outcome['message'] + "You took 5 cards without going over 21."
            elif DealerScore <= 21 and len(hands['dealer']) == 5:
                outcome['message'] = outcome['message'] + "The dealer took 5 cards without going over 21."
            elif PlayerScore > 21:
                outcome['message'] = outcome['message'] + "You went over 21 and busted."
            elif DealerScore > 21:
                outcome['message'] = outcome['message'] + "The dealer went over 21 and busted."
            elif view.action == "s" and PlayerScore > DealerScore:
                outcome['message'] = outcome[
                                         'message'] + f"You stood with a higer score (`{PlayerScore}`) than the dealer (`{DealerScore}`)"
            elif view.action == "s" and DealerScore > PlayerScore:
                outcome['message'] = outcome[
                                         'message'] + f"You stood with a lower score (`{PlayerScore}`) than the dealer (`{DealerScore}`)"
            elif view.action == "s" and PlayerScore == DealerScore:
                outcome['message'] = outcome['message'] + f"You got the same score as the dealer"

            finalEmbed = discord.Embed(title=f"{interaction.user.name}'s blackjack game", color=outcome['color'])
            finalEmbed.add_field(name=outcome['message'], value='** **', inline=False)
            finalEmbed.add_field(name=f"Bobit (Dealer)",
                                 value="Cards: " + ''.join(
                                     f"[`{str(x)}`]({BLACKJACK_DEALER_CARD_LINK}) " for x in
                                     hands["dealer"])
                                       + "\nTotal: `" + str(total([clean(x) for x in hands["dealer"]])) + "`")

            finalEmbed.add_field(name=f"{interaction.user.name} (Player)",
                                 value="Cards: " + ''.join(
                                     f"[`{str(x)}`]({BLACKJACK_PLAYER_CARD_LINK}) " for x in
                                     hands["player"]) + "\nTotal: `" + str(
                                     total(
                                         [clean(x) for x in
                                          hands["player"]])) + "`")
            for child in view.children: child.disabled = True  # noqa
            await interaction.edit_original_response(embed=finalEmbed, view=view)


async def setup(bot):
    await bot.add_cog(Blackjack(bot))