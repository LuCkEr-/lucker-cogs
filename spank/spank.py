import discord
from discord.ext import commands
from random import randint

class Spank:
    """Spank your friends!"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def spank(self, ctx, user: discord.Member):
        """Spank your favorite person!"""

        author = ctx.message.author

        if not user:
            await self.bot.send_cmd_help(ctx)
            return

        emotes = [
            ":grinning:",
            ":grimacing:",
            ":grin:",
            ":joy:",
            ":smiley:",
            ":smile:",
            ":sweat_smile:",
            ":laughing:",
            ":innocent:",
            ":wink:",
            ":blush:",
            ":slight_smile:",
            ":upside_down:",
            ":relaxed:",
            ":yum:",
            ":relieved:",
            ":heart_eyes:",
            ":kissing_heart:",
            ":kissing:",
            ":kissing_smiling_eyes:",
            ":kissing_closed_eyes:",
            ":stuck_out_tongue_winking_eye:",
            ":stuck_out_tongue_closed_eyes:",
            ":stuck_out_tongue:",
            ":money_mouth:",
            ":nerd:",
            ":sunglasses:",
            ":hugging:",
            ":smirk:",
            ":no_mouth:",
            ":neutral_face:",
            ":expressionless:",
            ":unamused:",
            ":rolling_eyes:",
            ":thinking:",
            ":flushed:",
            ":disappointed:",
            ":worried:",
            ":angry:",
            ":rage:",
            ":pensive:",
            ":confused:",
            ":slight_frown:",
            ":frowning2:",
            ":persevere:",
            ":confounded:",
            ":tired_face:",
            ":weary:",
            ":triumph:",
            ":open_mouth:",
            ":scream:",
            ":fearful:",
            ":cold_sweat:",
            ":hushed:",
            ":frowning:",
            ":anguished:",
            ":cry:",
            ":disappointed_relieved:",
            ":sleepy:",
            ":sweat:",
            ":sob:",
            ":dizzy_face:",
            ":astonished:",
            ":zipper_mouth:",
            ":mask:",
            ":thermometer_face:",
            ":head_bandage:",
            ":sleeping:"
            ]
        
        emotes_HF = [
            ":lovelyeyes:",
            ":KotoAngery:",
            ":Hush:",
            ":FbladeYaranaika:",
            ":FbladeEyes2:",
            ":FbladeEyes:",
            ":crash: "
            ]

        if ctx.message.server.id == "372058904818876428":
            for emote in emotes_HF:
                emotes.append(emote)

        #msg = [
        #    "{} is enduring the lash of {}s spanking!".format(user.mention, author.mention),
        #    "{} spanks {}".format(author.mention, user.mention),
        #    "{} gets spanked by {}".format(user.mention, author.mention),
        #    ":hand_splayed: :sweat_drops: {}".format(emotes[randint(0, len(emotes) - 1)])
        #    ]

        #await self.bot.say(msg[randint(0, len(msg) - 1)])
        await self.bot.say(":hand_splayed: :sweat_drops: {}".format(emotes[randint(0, len(emotes) - 1)]))
### ---------------------------- Setup ---------------------------------- ###
def setup(bot):
    bot.add_cog(Spank(bot))
