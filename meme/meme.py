import os
import discord
from discord.ext import commands
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

        self.reddit = praw.Reddit(client_id=settings["client_id"],
                     client_secret=settings["client_secret"],
                     user_agent='Helix by LuCkEr',
                     username='Helix')


    @commands.command(pass_context=True, no_pm=True)
    async def meme(self, ctx, *args : int):
        """Displays a random meme from Reddit!"""

        if not args:
            args = 1
        else:
            args = args[0]

        if args > 10:
            await self.bot.say("Can post a maximum of 10 memes at a time")
            return

        submissions = self.reddit.subreddit("memes").hot(limit=100)
        memes = [x for x in submissions if not x.stickied]

        if not memes:
            await self.bot.say("Could not find anything in memes subreddit :(")
            return

        if len(memes) < args:
            await self.bot.say("There aren't enough memes available at this time :(")
            return

        index = 0
        random = []
        while index < args:
            while True:
                randomInt = randint(0, len(memes) - 1)
                if not randomInt in random:
                    random.append(randomInt)
                    break
            index += 1

        for num in random:
            meme = memes[num]

            em = discord.Embed(title=meme.title, url=meme.shortlink)
            em.set_image(url=meme.url)

            await self.bot.say(embed = em)


### ---------------------------- Setup ---------------------------------- ###
def setup(bot):
    bot.add_cog(Meme(bot))

