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
                usernames = []
                users = self.bot.get_all_members()
                for user in users:
                    if user.nick is not None:
                        usernames.append(user.nick)
                    else:
                        usernames.append(user.name)
                
                # 26 is the max character lenght
                statuses = [
                    '!help',
                    'òwó', 'OwO', 'o~o', '>~<', 'XD', ';_;', '-_-', '._.', ':/', ':^)',
                    'in {} Servers'.format(len(self.bot.servers)),
                    'with {} Users'.format(
                        str(len(set(self.bot.get_all_members())))),
                    'with Me, Myself & I',
                    'with {}'.format(str(usernames[
                                     randint(0, len(set(usernames)) - 1)])),
                    'Skrrt', 'Mans not hot',
                    'lucker.xyz', 'slidenshine.net',
                    'For I have ascended', 'And I am born anew',
                    'Anime is ruining us', 'Anime was a mistake',
                    'Respecting womens rights', 'I am a nice guy',
                    'Don\'t tread on me',
                    'I can outlive you',
                    'Making creampies w/o cream',
                    'Console masterrace',
                    'Try murdering a cow',
                    'Don\'t let him fool you', 'Read a wikipedia page',
                    'Choking on the blue pill', 'Traps are gay',
                    'GNU/Linux',
                    'Blowing trap dicks', 'Bullying Fblade'
                ]

                status = randint(0, len(statuses) - 1)
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
