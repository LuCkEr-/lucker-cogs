import os
import discord
from discord.ext import commands
from __main__ import send_cmd_help
from random import randint
import asyncio
import praw
from .utils.dataIO import dataIO
from requests import Session
import json

class Meme:
    """Random things."""

    def __init__(self, bot):
        self.bot = bot

        settings = dataIO.load_json("data/meme/settings.json")
        #self.settings = defaultdict(dict, settings)

        self.reddit = praw.Reddit(client_id=settings["client_id"],
                     client_secret=settings["client_secret"],
                     user_agent='Helix by LuCkEr',
                     username='Helix')


    @commands.command(pass_context=True, no_pm=True)
    async def meme(self):
        """Displays a random meme from Reddit!"""

        memes = self.reddit.subreddit('memes').hot(limit=100)
        await self.bot.say(memes[randint(0, 100)].url)

### ---------------------------- Setup ---------------------------------- ###
def setup(bot):
    bot.add_cog(Meme(bot))
