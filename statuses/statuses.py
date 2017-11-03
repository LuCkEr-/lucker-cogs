import os
import discord
from discord.ext import commands
from discord.utils import find
from __main__ import send_cmd_help
from random import randint
import asyncio

class Statuses:
    """Random things."""

    def __init__(self, bot):
        self.bot = bot

    async def display_status(self):
        while self == self.bot.get_cog('Statuses'):
            try:
                statuses = [
                    '!help',
                    'òwó', 'o~o', '>~<', 'xdddddddd', ';_;', '-_-', '._.', ':/',
                    'in {} Servers'.format(len(self.bot.servers)),
                    'with {} Users'.format(str(len(set(self.bot.get_all_members())))),
                    'with Me, Myself & I', 'in #villains-cave', 'with Planes',
                    'with {}'.format(str(self.bot.get_all_members()[
                                     randint(0, len(set(self.bot.get_all_members()))-1)])),
                    'lucker.xyz', 'slidenshine.net'
                ]
                status = randint(0, len(statuses)-1)
                new_status = statuses[status]
                await self.bot.change_presence(game=discord.Game(name=new_status))
            except:
                pass
            await asyncio.sleep(60)

### ---------------------------- Setup ---------------------------------- ###
def setup(bot):
    n = Statuses(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.display_status())
    bot.add_cog(n)
