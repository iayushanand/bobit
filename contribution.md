# **Welcome to BoBit - How To Contribute!** #

First off, thank you for considering contributing to BoBit! Whether it's fixing bugs, adding features, or improving documentation. Every contribution helps make this bot better for the BIT Discord community.


## Why read the guidelines?

Following these guidelines respects the time of maintainers and helps get your changes merged faster.

* Other reasons:
    * To maintain code quality and consistency across the project
    * To write readable code that matches the existing style
    * To make the review and merge process much smoother


## What kind of contributions are we looking for?

BoBit is an open source Discord bot written in Python using `discord.py` with a MongoDB backend. We welcome contributions of all kinds:

* Bug fixes and error handling improvements
* New cogs (commands/features)
* Improvements to existing commands
* Documentation updates and typo fixes
* UI component improvements (views, buttons, modals in `utils/ui/`)
* Performance optimizations


## What kind of contributions are we NOT looking for?

* Pull requests that add content unrelated to the bot's purpose
* Features that duplicate existing functionality without good reason
* Changes that break the existing cog structure or architecture
* Dependencies that are unnecessary or bloated for the scope of the feature


## **Contribution Guidelines**

### Code Style

* Follow [PEP 8](https://peps.python.org/pep-0008/) conventions:
    * Use **4 spaces** for indentation (no tabs)
    * Use `snake_case` for variables and functions. `E.g`: `my_variable = 7`, not `myVariable = 7`
    * Constants and global variables must be `ALL_CAPS`. `E.g`: `LOG_CHANNEL_ID`, `STARBOARD_THRESHOLD`
    * Proper spacing around operators and after commas. `E.g`: `x = 7`, `call(arg1, arg2)`
    * **Type hint parameters** where possible - it helps readability and IDE support

    ```py
    # ✅ Good
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):

    # ❌ Bad
    async def kick(self, ctx, member, reason=None):
    ```

### Adding a New Cog

1. Create your cog file inside the `cogs/` directory (or `cogs/fun/` for fun/misc commands)
2. Every cog **must** follow this structure:

    ```py
    import discord
    from discord.ext import commands
    from utils.bot import BoBit
    from utils.consts import Colors

    class MyCog(commands.Cog):
        def __init__(self, bot: BoBit):
            self.bot = bot

        @commands.command(name="mycommand")
        @commands.has_permissions(...)  # Add appropriate permission checks
        async def my_command(self, ctx, ...):
            # Command logic here

            embed = discord.Embed(
                title="✅ Action Completed",
                color=Colors.GREEN
            )
            embed.add_field(name="Field", value="Value")
            await ctx.send(embed=embed)

    async def setup(bot: BoBit):
        await bot.add_cog(MyCog(bot))
    ```

3. Cogs are **auto-loaded** - the bot walks the `cogs/` directory in `setup_hook()`. Just add your `.py` file and it will be picked up automatically. No manual registration needed.

### Embed Responses

* **Always** use `discord.Embed` for command responses - do not send plain text replies
* Use the color constants from `utils/consts.py`:
    * `Colors.GREEN` - Success actions (kick, ban, purge, etc.)
    * `Colors.RED` - Error messages and invalid input
    * `Colors.YELLOW` - Warnings
* Use emoji prefixes in embed titles for visual clarity. `E.g`: `✅`, `❌`, `⚠️`, `🔨`, `🧹`

### Moderation Logging

* If your command is a moderation action, log it using the `log_action` helper in `cogs/moderation.py`:

    ```py
    await self.log_action(
        action="Action Name",
        moderator=ctx.author,
        target=member,         # discord.Member or None
        reason=reason,
        channel=ctx.channel
    )
    ```

### Database Usage

* The bot uses MongoDB via `pymongo.AsyncMongoClient`
* Access the database through `self.bot.db`
* Existing collections are defined in `utils/database.py`:
    * `self.bot.db.collection` - General data (warns, etc.)
    * `self.bot.db.tickets`, `self.bot.db.starboard`, `self.bot.db.tags`, `self.bot.db.afk`, `self.bot.db.vent`, `self.bot.db.ventban`, `self.bot.db.auto_slowmode`, `self.bot.db.voice_channels`
* **If you need a new collection**, add it as an attribute in the `Database` class in `utils/database.py` and initialize it inside the `connect()` method

### Event Listeners

* All event listeners go inside `cogs/listeners.py` (or the relevant cog if tightly coupled, like `starboard.py`)
* Use the `@commands.Cog.listener()` decorator
* If you need multiple listeners for the same event, pass the event name explicitly and name the function descriptively:

    ```py
    @commands.Cog.listener('on_message')
    async def afk_listener(self, message: discord.Message):
        # AFK check logic
    ```

### Constants

* All channel IDs, role IDs, API URLs, and configuration values go in `utils/consts.py`
* **Never** hardcode IDs or URLs directly in cog files

### UI Components (Views, Buttons, Modals)

* Place reusable views and UI components in `utils/ui/`
* Keep cog-specific views within the cog file if they are not shared

### Environment Variables

* Required environment variables are listed in `.env.example`
* If your feature requires a new API key or secret, add it to `.env.example` with an empty value


## **Setting Up for Development**

1. Clone the repository
    ```bash
    git clone https://github.com/iayushanand/BoBit.git
    cd BoBit
    ```

2. Create a virtual environment and install dependencies
    ```bash
    python -m venv env
    # Windows
    env\Scripts\activate
    # Linux/Mac
    source env/bin/activate

    pip install -r requirements.txt
    ```

3. Copy `.env.example` to `.env` and fill in your values
    ```bash
    cp .env.example .env
    ```
    You will need:
    * `TOKEN` - Your Discord bot token
    * `MONGOURI` - Your MongoDB connection string
    * `NASA_API_KEY` - NASA API key (optional, for NASA cog)

4. Configure channel/role IDs in `utils/consts.py` to match your test server

5. Run the bot
    ```bash
    python main.py
    ```


## **Submitting a Pull Request**

* Give your PR a clear, descriptive title
* Describe **what** you changed and **why** in the PR description
* Make sure your code follows the guidelines above
* Test your changes locally before submitting
* Do not include unrelated changes in the same PR
* Do not make PRs that add irrelevant content
