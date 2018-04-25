import discord
from discord.ext import commands
from random import randint

class Spank:
    """Spank your friends!"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx, user: discord.Member):
        """Spank someone"""

        author = ctx.message.author

        if not user:
            await self.bot.send_cmd_help(ctx)
            return

        msg = [
            "{} is enduring the lash of {}s spanking!".format(author.mention, user.mention),
            "{} spanks {}".format(author.mention, user.mention),
            "{} gets spanked by {}".format(user.mention, author.mention)
            ]

        await self.bot.say(msg[randint(0, len(msg) - 1)])
### ---------------------------- Setup ---------------------------------- ###
def setup(bot):
    bot.add_cog(Spank(bot))
