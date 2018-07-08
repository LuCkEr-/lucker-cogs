# import asyncio
# import collections
# import datetime
# import json
# import logging
# import math
import operator
# import os
import random
# import re
# import time
# import urllib
# from difflib import SequenceMatcher
# from random import randint
# from threading import Thread

# import aiohttp
import discord
# import matplotlib as mpl
# import matplotlib.pyplot as plt
# import numpy as np
import pytesseract
# from bs4 import BeautifulSoup
from cogs.utils import checks
from discord.ext import commands
from discord.utils import find
from imgurpython import ImgurClient
# from matplotlib import ticker
from PIL import Image
# from pymongo import MongoClient

# import pyoppai
from __main__ import send_cmd_help
# from data.osu.oppai_chunks import oppai
# from pippy.beatmap import Beatmap

from .fetching import *
from .helper import *
from .common import *
from .utils.dataIO import fileIO

# mpl.use('Agg') # for non gui

prefix = fileIO("data/red/settings.json", "load")['PREFIXES'][0]
help_msg = [
            "**No linked account (`{}osuset user [username]`) or not using **`{}command [username] [gamemode]`".format(prefix, prefix),
            "**No linked account (`{}osuset user [username]`)**".format(prefix)
            ]
# modes = ["osu", "taiko", "ctb", "mania"]
# modes2 = ["osu", "taiko", "fruits", "mania"]
# client = MongoClient()
# db = client['owo_database_2']
# log = logging.getLogger("red.osu")
# log.setLevel(logging.DEBUG)

class Osu:
    """Cog to give osu! stats for all gamemodes."""
    def __init__(self, bot):
        self.bot = bot
        self.api_keys = fileIO("data/osu/apikey.json", "load")
        if 'imgur_auth_info' in self.api_keys.keys():
            client_id = self.api_keys['imgur_auth_info']['client_id']
            client_secret = self.api_keys['imgur_auth_info']['client_secret']
            self.imgur = ImgurClient(client_id, client_secret)
        else:
            self.imgur = None
        self.osu_settings = fileIO("data/osu/osu_settings.json", "load")
        self.num_max_prof = 8
        self.max_map_disp = 3
        self.sleep_time = 0.06

    # ---------------------------- Settings ------------------------------------
    @commands.group(pass_context=True)
    async def osuset(self, ctx):
        """Where you can define some settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @osuset.command(pass_context=True, no_pm=True)
    @checks.is_owner()
    async def tracktop(self, ctx, top_num:int):
        """ Set # of top plays being tracked """
        msg = ""
        if top_num < 1 or top_num > 100:
            msg = "**Please enter a valid number. (1 - 100)**"
        else:
            self.osu_settings["num_track"] = top_num
            msg = "**Maximum tracking set to {} plays.**".format(top_num)
            fileIO("data/osu/osu_settings.json", "save", self.osu_settings)
        await self.bot.say(msg)

    @osuset.command(pass_context=True, no_pm=True, name = 'ccbmp')
    @checks.is_owner()
    async def clear_cache(self):
        db.beatmap_cache.update_one({"type":'list'}, {'$set':{
            'ids': list([])
        }})

        db.beatmap_cache.update_one({"type":'maps'}, {'$set':{
            'maps': list([])
        }})

    @osuset.command(pass_context=True, no_pm=True, name = 'reccount')
    @checks.is_owner()
    async def reccount(self):
        counter = 0
        for pp_maps in db.suggest_osu.find({}, no_cursor_timeout = True):
            counter += len(pp_maps['beatmaps'])

        await self.bot.say('There are currently `{}` maps in the osu! standard recommendation database.'.format(counter))

    @osuset.command(pass_context=True, no_pm=True)
    @checks.is_owner()
    async def displaytop(self, ctx, top_num:int):
        """ Set # of best plays being displayed in top command """
        msg = ""
        if top_num < 1 or top_num > 10:
            msg = "**Please enter a valid number. (1 - 10)**"
        else:
            self.osu_settings["num_best_plays"] = top_num
            msg = "**Now Displaying Top {} Plays.**".format(top_num)
            fileIO("data/osu/osu_settings.json", "save", self.osu_settings)
        await self.bot.say(msg)

    @osuset.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def tracking(self, ctx, toggle=None):
        """ For disabling tracking on server (enable/disable) """
        server = ctx.message.server

        server_settings = db.osu_settings.find_one({'server_id':server.id})
        if not server_settings:
            db.osu_settings.insert_one({'server_id':server.id})
            server_settings = db.osu_settings.find_one({'server_id':server.id})

        if 'tracking' not in server_settings:
            db.osu_settings.update_one({'server_id':server.id}, {'$set': {
                'tracking': True}})
        server_settings = db.osu_settings.find_one({'server_id':server.id})

        status = ""
        if not toggle:
            track = server_settings['tracking']
            if not track:
                track = True
                status = "Enabled"
            else:
                track = False
                status = "Disabled"
        elif toggle.lower() == "enable":
            track = True
            status = "Enabled"
        elif toggle.lower() == "disable":
            track = False
            status = "Disabled"
        db.osu_settings.update_one({'server_id':server.id}, {'$set': {'tracking': track}})
        await self.bot.say("**Player Tracking {} on {}.**".format(server.name, status))

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def overview(self, ctx):
        """ Get an overview of your settings """
        server = ctx.message.server
        user = ctx.message.author

        em = discord.Embed(description='', colour=user.colour)
        em.set_author(name="Current Settings for {}".format(server.name), icon_url = server.icon_url)

        # determine api to use
        server_settings = db.osu_settings.find_one({'server_id':server.id})
        passive_settings = db.options.find_one({'server_id':server.id})

        if server_settings:
            if "api" not in server_settings:
                api = "Official osu! API"
            elif server_settings["api"] == self.osu_settings["type"]["default"]:
                api = "Official osu! API"
            elif server_settings["api"] == self.osu_settings["type"]["ripple"]:
                api = "Ripple API"
        else:
            api = "Official osu! API"

        # determine
        if not server_settings or "tracking" not in server_settings or server_settings["tracking"] == True:
            tracking = "Enabled"
        else:
            tracking = "Disabled"

        info = "**__General Settings__**\n"
        info += "**Default API:** {}\n".format(api)
        info += "**Top Plays (Global):** {}\n".format(self.osu_settings['num_best_plays'])
        info += "**Tracking:** {}\n".format(tracking)

        if tracking == "Enabled":
            info += "**Tracking Max (Global):** {}\n".format(self.osu_settings['num_track'])
        info += "**Tracking Total (Global):** {} players\n".format(str(db.track.count()))
        cycle_time = self.bot.get_cog('Tracking').cycle_time
        info += "**Tracking Cycle Time:** {:.3f} min\n".format(float(cycle_time))

        if not passive_settings:
            passive_settings = {
                "graph_beatmap": True,
                "graph_screenshot": False,
                "beatmap": True,
                "screenshot": True
            }

        info += "**\n__Passive Options__**\n"
        info += "**Beatmap Url Detection:** {}\n".format(self._is_enabled(passive_settings['beatmap']))
        info += "**Beatmap Graph:** {}\n".format(self._is_enabled(passive_settings['graph_beatmap']))
        info += "**Screenshot Detection:** {}\n".format(self._is_enabled(passive_settings['screenshot']))
        info += "**Screenshot Graph:** {}".format(self._is_enabled(passive_settings['graph_screenshot']))

        em.description = info
        await self.bot.say(embed = em)

    def _is_enabled(self, option):
        if option:
            return 'Enabled'
        else:
            return 'Disabled'

    @osuset.command(pass_context=True, no_pm=True)
    @checks.is_owner()
    async def api(self, ctx, *, choice):
        """'official' or 'ripple'"""
        server = ctx.message.server
        server_settings = db.osu_settings.find_one({'server_id':server.id})
        if not server_settings or 'api' not in server_settings:
            db.osu_settings.insert_one({'server_id':server.id, 'api':self.osu_settings["type"]["default"]})

        if not choice.lower() == "official" and not choice.lower() == "ripple":
            await self.bot.say("The two choices are `official` and `ripple`")
            return
        elif choice.lower() == "official":
            db.osu_settings.update_one({'server_id':server.id}, {'$set':{"api": self.osu_settings["type"]["default"]}})
        elif choice.lower() == "ripple":
            db.osu_settings.update_one({'server_id':server.id}, {'$set':{"api": self.osu_settings["type"]["ripple"]}})
        await self.bot.say("**Switched to `{}` server as default on `{}`.**".format(choice, server.name))

    @osuset.command(pass_context=True, no_pm=True)
    async def default(self, ctx, mode:str):
        """ Set your default gamemode """
        user = ctx.message.author
        server = ctx.message.server

        try:
            if mode.lower() in modes:
                gamemode = modes.index(mode.lower())
            elif int(mode) >= 0 and int(mode) <= 3:
                gamemode = int(mode)
            else:
                await self.bot.say("**Please enter a valid gamemode.**")
                return
        except:
            await self.bot.say("**Please enter a valid gamemode.**")
            return

        user_set = db.user_settings.find_one({'user_id':user.id})
        if user_set:
            db.user_settings.update_one({'user_id':user.id},
                {'$set':{"default_gamemode": int(gamemode)}})
            await self.bot.say("**`{}`'s default gamemode has been set to `{}`.** :white_check_mark:".format(user.name, modes[gamemode]))
        else:
            await self.bot.say(help_msg[1])

    @osuset.group(name="key", pass_context=True)
    @checks.is_owner()
    async def setkey(self, ctx):
        """Sets your osu and puush api key"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @setkey.command(name="imgur", pass_context=True)
    @checks.is_owner()
    async def setimgur(self, ctx):
        await self.bot.whisper("Type your imgur client ID. You can reply here.")
        client_id = await self.bot.wait_for_message(timeout=30, author=ctx.message.author)
        if client_id is None:
            return
        await self.bot.whisper("Type your client secret.")
        client_secret = await self.bot.wait_for_message(timeout=30, author=ctx.message.author)
        if client_secret is None:
            return
        self.api_keys['imgur_auth_info'] = {}
        self.api_keys['imgur_auth_info']['client_id'] = client_id.content
        self.api_keys['imgur_auth_info']['client_secret'] = client_secret.content
        fileIO("data/osu/apikey.json", "save", self.api_keys)
        self.imgur = ImgurClient(client_id.content, client_secret.content)
        await self.bot.whisper("Imgur API details added. :white_check_mark:")

    @setkey.command(name="osu", pass_context=True)
    @checks.is_owner()
    async def setosu(self, ctx):
        await self.bot.whisper("Type your osu! api key. You can reply here.")
        key = await self.bot.wait_for_message(timeout=30, author=ctx.message.author)
        if key is None:
            return
        else:
            self.api_keys["osu_api_key"] = key.content
            fileIO("data/osu/apikey.json", "save", self.api_keys)
            await self.bot.whisper("osu! API Key details added. :white_check_mark:")

    @commands.command(pass_context=True, no_pm=True)
    async def osu(self, ctx, *username):
        """osu usernames [-ripple|-official]"""
        await self._process_user_info(ctx, username, 0)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def osutop(self, ctx, *username):
        """osutop username [-ripple|-official]"""
        await self._process_user_top(ctx, username, 0)

    @commands.command(pass_context=True, no_pm=True)
    async def taiko(self, ctx, *username):
        """taiko usernames [-ripple|-official]"""
        await self._process_user_info(ctx, username, 1)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def taikotop(self, ctx, *username):
        """taikotop username [-ripple|-official]"""
        await self._process_user_top(ctx, username, 1)

    @commands.command(pass_context=True, no_pm=True)
    async def ctb(self, ctx, *username):
        """ctb usernames [-ripple|-official]"""
        await self._process_user_info(ctx, username, 2)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def ctbtop(self, ctx, *username):
        """ctbtop username [-ripple|-official]"""
        await self._process_user_top(ctx, username, 2)

    @commands.command(pass_context=True, no_pm=True)
    async def mania(self, ctx, *username):
        """mania usernames [-ripple|-official]"""
        await self._process_user_info(ctx, username, 3)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True)
    async def maniatop(self, ctx, *username):
        """maniatop username [-ripple|-official]"""
        await self._process_user_top(ctx, username, 3)

    @commands.command(pass_context=True, no_pm=True)
    async def recent(self, ctx, *username):
        """recent username [gamemode] [-ripple|-official]"""
        await self._process_user_recent(ctx, username)

    @commands.command(pass_context=True)
    async def scores(self, ctx, map_link, *username):
        """scores map_link [-t] [username]"""
        if not 'https://osu.ppy.sh/b/' in map_link:
            await self.bot.say("There needs to be a proper beatmap link")
            return
        else:
            map_link = map_link.replace('https://osu.ppy.sh/b/', '')
        await self._process_map_score(ctx, map_link, username)

    @commands.command(pass_context = True, name = 'osuleaderboard', aliases = ['ol','osul'])
    async def osuleaderboard(self, ctx, *option):
        """Uses linked database and cached data to generate leaderboard"""
        return
        try:
            mode = modes[mode] # mode
            members = ctx.message.server.members
            userlist = []
            for member in members:
                userinfo = await self._process_username(ctx, member, disp_error = False)
                if not userinfo:
                    continue

                osu_id = userinfo['osu_id']

                # find userinfo
                player = db.osutrack.find_one({'osu_id': osu_id})
                if not player:
                    player = db.user_settings.find({'osu_user_id': osu_id})
                    try:
                        player_info = player['userinfo'][mode]
                        player_info['discord_username'] = userinfo['discord_username']
                    except:
                        pass # has not done >osu command
                else:
                    player_info = player['userinfo'][mode]

                userlist.append(player_info)

            sorted(userlist, key=operator.itemgetter('pp_rank'), reverse=True)
            sorted_list = userlist

            title = "Osu! Leaderboard for {}\n".format(server.name)
            board_type = 'PP'
            footer_text = ""
            icon_url = server.icon_url

            # multiple page support
            page = 1
            per_page = 15
            pages = math.ceil(len(sorted_list)/per_page)
            for option in options:
                if str(option).isdigit():
                    if page >= 1 and int(option) <= pages:
                        page = int(str(option))
                    else:
                        await self.bot.say("**Please enter a valid page number! (1 - {})**".format(str(pages)))
                        return
                    break

            msg = ""
            msg += "**Rank              Name (Page {}/{})**\n".format(page, pages)
            rank = 1 + per_page*(page-1)
            start_index = per_page*page - per_page
            end_index = per_page*page

            default_label = "   "
            special_labels = ["♔", "♕", "♖", "♗", "♘", "♙"]

            for single_user in sorted_list[start_index:end_index]:
                if rank-1 < len(special_labels):
                    label = special_labels[rank-1]
                else:
                    label = default_label

                msg += u'`{:<2}{:<2}{:<2}   # {:<22}'.format(rank, label, u"➤", self._truncate_text(single_user[0],20))
                msg += u'{:>5}{:<2}{:<2}{:<5}`\n'.format(" ", " ", " ", "Total {}: ".format(board_type) + str(single_user[1]))
                rank += 1
            msg +="----------------------------------------------------\n"
            msg += "`{}`".format(footer_text)

            em = discord.Embed(description='', colour=user.colour)
            em.set_author(name=title, icon_url = icon_url)
            em.description = msg

            await self.bot.say(embed = em)
        except:
            pass

    @checks.admin_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def options(self, ctx):
        """Set some server options"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @options.command(pass_context=True, no_pm=True)
    async def beatmapgraph(self, ctx):
        """Toggle beatmap graph"""
        key_name = "graph_beatmap"
        server = ctx.message.server
        option = self._handle_option(key_name, server.id)

        msg = ""
        if option:
            msg = "**Beatmap graph enabled.**"
        else:
            msg = "**Beatmap graph disabled.**"

        await self.bot.say(msg)

    @options.command(pass_context=True, no_pm=True)
    async def ssgraph(self, ctx):
        """Toggle screenshot beatmap graph"""
        key_name = "graph_screenshot"
        server = ctx.message.server
        option = self._handle_option(key_name, server.id)

        msg = ""
        if option:
            msg = "**Screenshot beatmap graph enabled.**"
        else:
            msg = "**Screenshot beatmap graph disabled.**"

        await self.bot.say(msg)

    @options.command(pass_context=True, no_pm=True)
    async def beatmap(self, ctx):
        """Toggle beatmap url detection"""
        key_name = "beatmap"
        server = ctx.message.server
        option = self._handle_option(key_name, server.id)

        msg = ""
        if option:
            msg = "**Beatmap url detection enabled.**"
        else:
            msg = "**Beatmap url detection disabled.**"

        await self.bot.say(msg)

    @options.command(pass_context=True, no_pm=True)
    async def screenshot(self, ctx):
        """Toggle screenshot detection"""
        key_name = "screenshot"
        server = ctx.message.server
        option = self._handle_option(key_name, server.id)

        msg = ""
        if option:
            msg = "**Screenshot detection enabled.**"
        else:
            msg = "**Screenshot detection disabled.**"

        await self.bot.say(msg)

    def _handle_option(self, key_name, server_id):
        server_options = db.options.find_one({"server_id":server_id})
        if server_options is None:
            server_options = {
                "server_id": server_id,
                "graph_beatmap": True,
                "graph_screenshot": False,
                "beatmap": True,
                "screenshot": True
            }
            server_options[key_name] = not server_options[key_name]
            db.options.insert_one(server_options)
        else:
            server_options[key_name] = not server_options[key_name]
            db.options.update_one({"server_id":server_id}, {
                '$set':{key_name: server_options[key_name]
                }})

        return server_options[key_name]

    @osuset.command(pass_context=True, no_pm=True)
    async def user(self, ctx, *, username):
        """Sets user information given an osu! username"""
        user = ctx.message.author
        channel = ctx.message.channel
        server = user.server
        key = self.api_keys["osu_api_key"]

        if not self._check_user_exists(user):
            try:
                osu_user = list(await get_user(key, self.osu_settings["type"]["default"], username, 1))
                newuser = {
                    "discord_username": user.name,
                    "osu_username": username,
                    "osu_user_id": osu_user[0]["user_id"],
                    "default_gamemode": 0,
                    "ripple_username": "",
                    "ripple_user_id": "",
                    "user_id": user.id
                }
                db.user_settings.insert_one(newuser)
                await self.bot.say("{}, your account has been linked to osu! username `{}`".format(user.mention, osu_user[0]["username"]))
            except:
                await self.bot.say("`{}` doesn't exist in the osu! database.".format(username))
        else:
            try:
                osu_user = list(await get_user(key, self.osu_settings["type"]["default"], username, 1))
                db.user_settings.update_one({'user_id': user.id}, {'$set':{'osu_username':username,
                    "osu_user_id":osu_user[0]["user_id"]
                    }})

                stevy_info = db.user_settings.find_one({'user_id':user.id})
                await self.bot.say("{}, your osu! username has been edited to `{}`".format(user.mention, osu_user[0]["username"]))
            except:
                await self.bot.say("`{}` doesn't exist in the osu! database.".format(username))

    @osuset.command(name = "skin", pass_context=True, no_pm=True)
    async def setskin(self, ctx, link:str):
        """Link your skin."""
        user = ctx.message.author
        user_set = db.user_settings.find_one({'user_id':user.id})
        if user_set != None:

            """ # Later
            if link == '-find':
                url = self._find_skin(user_set['osu_user_id'])
            elif self._is_valid_skin(link):
                url = link
            else:
                return"""

            db.user_settings.update_one({'user_id':user.id},
                {'$set':{"skin": link}})
            await self.bot.say("**`{}`'s skin has been set to `{}`.**".format(user.name, link))
        else:
            await self.bot.say(help_msg[1])

    @commands.command(pass_context=True, no_pm=True)
    async def skin(self, ctx, user:discord.Member = None):
        """skin username"""
        if user == None:
            user = ctx.message.author

        userinfo = db.user_settings.find_one({'user_id':user.id})

        if userinfo != None:
            if 'skin' in userinfo:
                await self.bot.say("**`{}`'s Skin: <{}>.**".format(user.name, userinfo['skin']))
            else:
                await self.bot.say("**`{}` has not set a skin.**".format(user.name))
        else:
            await self.bot.say("**`{}` does not have an account linked.**".format(user.name))

    # Gets json information to proccess the small version of the image
    async def _process_user_info(self, ctx, usernames, gamemode:int):
        key = self.api_keys["osu_api_key"]
        channel = ctx.message.channel
        user = ctx.message.author
        server = user.server

        # checks for detailed flag
        if '-d' in usernames:
            detailed = True
            usernames = list(usernames)
            del usernames[usernames.index('-d')]
            usernames = tuple(usernames)
        else:
            detailed = False

        if not usernames:
            usernames = [None]
        # get rid of duplicates initially
        usernames = list(set(usernames))

        # determine api to use
        usernames, api = self._determine_api(server, usernames)

        # gives the final input for osu username
        final_usernames = []
        for username in usernames:
            test_username = await self._process_username(ctx, username)
            if test_username != None:
                final_usernames.append(test_username)

        # get rid of duplicates initially
        final_usernames = list(set(final_usernames))

        # testing if username is osu username
        all_user_info = []
        sequence = []

        count_valid = 0
        for i in range(len(final_usernames)):
            #try:
            userinfo = list(await get_user(key, api, final_usernames[i], gamemode, no_cache = True)) # get user info from osu api
            # self._update_linked_user(userinfo)
            if userinfo != None and len(userinfo) > 0 and userinfo[0]['pp_raw'] != None:
                all_user_info.append(userinfo[0])
                sequence.append((count_valid, int(userinfo[0]["pp_rank"])))
                count_valid = count_valid + 1
            else:
                await self.bot.say("**`{}` has not played enough.**".format(final_usernames[i]))
            #except:
                #await self.bot.say("Error. Please try again later.")
                #return

        sequence = sorted(sequence, key=operator.itemgetter(1))

        all_players = []
        for i, pp in sequence:
            if detailed:
                all_players.append(await self._det_user_info(api, server, user, all_user_info[i], gamemode))
            else:
                all_players.append(await self._get_user_info(api, server, user, all_user_info[i], gamemode))
        disp_num = min(self.num_max_prof, len(all_players))
        if disp_num < len(all_players):
            await self.bot.say("Found {} users, but displaying top {}.".format(len(all_players), disp_num))

        for player in all_players[0:disp_num]:
            await self.bot.say(embed=player)

    def _update_linked_user(self, userinfo):
        pass

    # takes iterable of inputs and determines api, also based on defaults
    def _determine_api(self, server, inputs):

        if not inputs or ('-ripple' not in inputs and '-official' not in inputs): # in case not specified
            server_settings = db.osu_settings.find_one({'server_id':server.id})
            if server_settings and "api" in server_settings:
                if server_settings["api"] == self.osu_settings["type"]["default"]:
                    api = self.osu_settings["type"]["default"]
                elif server_settings["api"] == self.osu_settings["type"]["ripple"]:
                    api = self.osu_settings["type"]["ripple"]
            else:
                api = self.osu_settings["type"]["default"]
        if '-ripple' in inputs:
            inputs = list(inputs)
            inputs.remove('-ripple')
            api = self.osu_settings["type"]["ripple"]
        if '-official' in inputs:
            inputs = list(inputs)
            inputs.remove('-official')
            api = self.osu_settings["type"]["default"]

        if not inputs:
            inputs = [None]

        return inputs, api

    # Gets the user's most recent score
    async def _process_user_recent(self, ctx, inputs):
        key = self.api_keys["osu_api_key"]
        channel = ctx.message.channel
        user = ctx.message.author
        server = user.server

        # forced handle gamemode
        gamemode = -1
        inputs = list(inputs)
        for mode in modes:
            if len(inputs) >= 2 and mode in inputs:
                gamemode = get_gamemode_number(mode)
                inputs.remove(mode)
            elif len(inputs) == 1 and mode == inputs[0]:
                gamemode = get_gamemode_number(mode)
                inputs.remove(mode)

        recent_best = False
        if '-b' in inputs:
            recent_best = True
            inputs.remove('-b')

        inputs = tuple(inputs)

        # handle api and username (1)
        username, api = self._determine_api(server, list(inputs))
        username = username[0]

        # gives the final input for osu username
        test_username = await self._process_username(ctx, username)
        if test_username:
            username = test_username
        else:
            return

        # determines which recent gamemode to display based on user
        if gamemode == -1:
            target_id = self._get_discord_id(username, api)
            if target_id != -1:
                user_setting = db.user_settings.find_one({'user_id':target_id})
                gamemode = user_setting['default_gamemode']
            elif target_id == -1 and self._check_user_exists(user):
                user_setting = db.user_settings.find_one({'user_id':user.id})
                gamemode = user_setting['default_gamemode']
            else:
                gamemode = 0

        try:
            userinfo = list(await get_user(key, api, username, gamemode))
            await asyncio.sleep(self.sleep_time)
            if recent_best:
                userbest = list(await get_user_best(key, api, username, gamemode, 100))
                web = False
            else:
                userrecent = list(await get_user_recent(key, api, username, gamemode))
        except:
            await self.bot.say("Error. Please try again later.")
            return
        await asyncio.sleep(self.sleep_time)

        if not userinfo:
            await self.bot.say("**`{}` was not found or no recent plays in `{}`.**".format(username, get_gamemode(gamemode)))
            return

        try:
            userinfo = userinfo[0]
            if recent_best:
                # save keep index
                for i, score in enumerate(userbest):
                    userbest[i]['index'] = i
                userbest = sorted(userbest, key=operator.itemgetter('date'), reverse=True)
                userbest = [userbest[0]]

                # get best plays map information and scores, assume length is self.osu_settings['num_best_plays']
                best_beatmaps = []
                best_acc = []
                beatmap = list(await get_beatmap(key, api, beatmap_id=userbest[0]['beatmap_id']))[0]
                best_beatmaps = [beatmap]
                best_acc = [calculate_acc(userbest[0], gamemode)]
                score_num = userbest[0]['index']

                msg, embed = await self._get_user_top(
                    ctx, api, userinfo, userbest, best_beatmaps, best_acc, gamemode, score_num = score_num, web = web)
            else:
                userrecent = userrecent[0]
                msg, embed = await self._get_recent(ctx, api, userinfo, userrecent, gamemode)
        except:
            await self.bot.say("**`{}` was not found or no recent plays in `{}`.**".format(username, get_gamemode(gamemode)))
            return

        await self.bot.say(msg, embed=embed)

    def _get_discord_id(self, username:str, api:str):
        #if api == self.osu_settings["type"]["ripple"]:
            #name_type = "ripple_username"
        #else:
            #name_type = "osu_username"
        # currently assumes same name
        name_type = "osu_username"
        user = db.user_settings.find_one({name_type:username})
        if user:
            return user['user_id']
        return -1

    # Gets information to proccess the top play version of the image
    async def _process_user_top(self, ctx, username, gamemode: int):
        key = self.api_keys["osu_api_key"]
        channel = ctx.message.channel
        user = ctx.message.author
        server = user.server

        # Written by Jams
        score_num = None
        show_recent = False
        greater_than = None
        if '-p' in username:
            if '-r' in username or '-g' in username:
                await self.bot.say("**You cannot use -r, -g, or -p at the same time**")
                return
            marker_loc = username.index('-p')
            if len(username) - 1 == marker_loc:
                await self.bot.say("**Please provide a score number!**")
                return

            username = tuple(username)
            score_num = username[marker_loc + 1]
            if not score_num.isdigit():
                await self.bot.say("**Please use only whole numbers for number of top plays!**")
                return
            else:
                score_num = int(score_num)

            if score_num <= 0 or score_num > 100:
                await self.bot.say("**Please enter a valid top play number! (1-100)**")
                return

            username = list(username)
            del username[marker_loc + 1]
            del username[marker_loc]
        elif '-r' in username:
            if '-g' in username:
                await self.bot.say("**You cannot use -r, -g, or -p at the same time**")
                return
            username = list(username)
            del username[username.index('-r')]
            show_recent = True
        elif '-g' in username:
            username = list(username)
            marker_loc = username.index('-g')
            greater_than = username[marker_loc + 1]
            if not greater_than.replace('.', '').isdigit():
                await self.bot.say("**Please use only numbers for amount of PP!**")
                return
            else:
                greater_than = float(greater_than)
            del username[marker_loc + 1]
            del username[marker_loc]

        # if you're not getting the score number, then only use the first one
        if not username:
            usernames = [None]
        elif not score_num and username:
            usernames = [username[0]]
        else:
            usernames = list(username)

        # determine api to use
        usernames, api = self._determine_api(server, usernames)

        embed_list = [] # final list to display
        for username in usernames:

            # gives the final input for osu username
            username = await self._process_username(ctx, username)

            # get info, get from website if api is official
            userinfo = list(await get_user(key, api, username, gamemode))
            #if api == self.osu_settings["type"]["default"]: # returns the same format
                #userbest, best_beatmaps, best_acc = await self._get_user_best_web(ctx, userinfo[0], gamemode, num_plays = 100)
                #is_web = True
            #else:
            userbest = list(await get_user_best(key, api, username, gamemode, 100))
            best_beatmaps, best_acc = None, None
            is_web = False

            if not userinfo or not userbest:
                await self.bot.say("**`{}` was not found or not enough plays.**".format(username))
                return

            # save keep index
            for i, score in enumerate(userbest):
                userbest[i]['index'] = i

            # handle options and process userbest
            if show_recent:
                userbest = sorted(userbest, key=operator.itemgetter('date'), reverse=True)
                userbest = userbest[:self.osu_settings['num_best_plays']]
            elif greater_than:
                # count how many are above.
                counter = 0
                for score in userbest:
                    if float(score['pp']) >= greater_than:
                        counter += 1
                await self.bot.say("**`{}` has {} plays worth more than {}PP**".format(username, str(counter), greater_than))
                return
            elif score_num:
                # grab only that one.
                index = score_num - 1
                userbest = [userbest[index]]
            else:
                userbest = userbest[:self.osu_settings['num_best_plays']]

            # process best_beatmaps and best_acc arrays, assume in order
            if not best_beatmaps and not best_acc:
                # get best plays map information and scores, assume length is self.osu_settings['num_best_plays']
                best_beatmaps = []
                best_acc = []
                for i in range(len(userbest)):
                    beatmap = list(await get_beatmap(key, api, beatmap_id=userbest[i]['beatmap_id']))[0]
                    best_beatmaps.append(beatmap)
                    best_acc.append(calculate_acc(userbest[i], gamemode))
                    await asyncio.sleep(self.sleep_time)
            else:
                temp_best_maps = []
                temp_best_acc = []
                if score_num:
                    index = score_num - 1
                    best_beatmaps, best_acc = [best_beatmaps[index]], [best_acc[index]]
                else:
                    for play in userbest:
                        temp_best_maps.append(best_beatmaps[int(play['index'])])
                        temp_best_acc.append(best_acc[int(play['index'])])
                    best_beatmaps = temp_best_maps
                    best_acc = temp_best_acc

            # get top
            msg, embed = await self._get_user_top(
                ctx, api, userinfo[0], userbest, best_beatmaps, best_acc, gamemode, score_num = score_num, recent = show_recent, web = is_web)
            embed_list.append((msg, embed))

        # print out all the necessary embeds
        for msg, embed in embed_list:
            await self.bot.say(msg, embed = embed)

    # Gives a user profile image with some information
    async def _get_user_top(self, ctx, api, user, userbest, best_beatmaps, best_acc, gamemode, score_num = None, recent = False, web = False):
        server_user = ctx.message.author
        server = ctx.message.server
        key = self.api_keys["osu_api_key"]

        if api == self.osu_settings["type"]["default"]:
            profile_url ='https://a.ppy.sh/{}'.format(user['user_id'])
        elif api == self.osu_settings["type"]["ripple"]:
            profile_url = 'http://a.ripple.moe/{}.png'.format(user['user_id'])

        flag_url = 'https://osu.ppy.sh/images/flags/{}.png'.format(user['country'])
        gamemode_text = get_gamemode(gamemode)

        msg = ''
        desc = ''

        # takes in the processed userbest
        for i in range(len(userbest)):
            mods = num_to_mod(userbest[i]['enabled_mods'])
            oppai_info = await get_pyoppai(best_beatmaps[i]['beatmap_id'], accs = [float(best_acc[i])], mods = int(userbest[i]['enabled_mods']))

            # missing information
            best_beatmaps[i]['max_combo'] = oppai_info['max_combo']

            if not mods:
                mods = []
                mods.append('No Mod')
            beatmap_url = 'https://osu.ppy.sh/b/{}'.format(best_beatmaps[i]['beatmap_id'])

            info = ''
            if not score_num:
                number = '{}. '.format(str(int(userbest[i]['index']) + 1))
            else:
                number = ''

            star_str, _ = compare_val(best_beatmaps[i]['difficultyrating'], oppai_info, param = 'stars', dec_places = 2, single = True)
            info += '**{}[{} [{}]]({}) +{}** [{}★]\n'.format(
                number, best_beatmaps[i]['title'],
                best_beatmaps[i]['version'], beatmap_url,
                fix_mods(''.join(mods)), star_str)

            # choke text
            choke_text = ''
            if (oppai_info != None and userbest[i]['countmiss'] != None and best_beatmaps[i]['max_combo']!= None) and (int(userbest[i]['countmiss'])>=1 or (int(userbest[i]['maxcombo']) <= 0.95*int(best_beatmaps[i]['max_combo']) and 'S' in userbest[i]['rank'])):
                choke_text += ' _({:.2f}pp for FC)_'.format(oppai_info['pp'][0])
            info += '▸ **{} Rank** ▸ **{:.2f}pp**{} ▸ {:.2f}%\n'.format(userbest[i]['rank'], float(userbest[i]['pp']), choke_text, float(best_acc[i]))
            info += '▸ {} ▸ x{}/{} ▸ [{}/{}/{}/{}]\n'.format(
                userbest[i]['score'],
                userbest[i]['maxcombo'], best_beatmaps[i]['max_combo'],
                userbest[i]['count300'],userbest[i]['count100'],userbest[i]['count50'],userbest[i]['countmiss']
                )

            if web:
                timeago = time_ago(datetime.datetime.utcnow() + datetime.timedelta(hours=8), datetime.datetime.strptime(userbest[i]['date'], '%Y-%m-%dT%H:%M:%S+00:00'))
            else:
                timeago = time_ago(datetime.datetime.utcnow() + datetime.timedelta(hours=8), datetime.datetime.strptime(userbest[i]['date'], '%Y-%m-%d %H:%M:%S'))
            info += '▸ Score Set {}Ago\n'.format(timeago)
            desc += info

        em = discord.Embed(description=desc, colour=server_user.colour)
        if recent:
            title = "Most Recent {} Top Play for {}".format(gamemode_text, user['username'])
        elif score_num:
            title = "Top {} {} Play for {}".format(str(score_num), gamemode_text, user['username'])
        else:
            title = "Top {} {} Plays for {}".format(self.osu_settings['num_best_plays'], gamemode_text, user['username'])

        em.set_author(name = title, url="https://osu.ppy.sh/u/{}".format(user['user_id']), icon_url=flag_url)
        em.set_footer(text = "On osu! {} Server".format(self._get_api_name(api)))
        em.set_thumbnail(url=profile_url)

        return (msg, em)

    # Written by Jams
    async def _process_map_score(self, ctx, map_id, inputs):
        key = self.api_keys["osu_api_key"]
        channel = ctx.message.channel
        user = ctx.message.author
        server = user.server

        # determine api to use
        _, api = self._determine_api(server, list(inputs))

        # do this now to allow getting the gamemode from the map itself if not specified
        beatmap = list(await get_beatmap(key, api, beatmap_id=map_id))[0]

        if '-g' in inputs:
            marker_loc = inputs.index('-g')
            gamemode = inputs[marker_loc + 1]
            if gamemode.isdigit() and (int(gamemode) >= 0 and int(gamemode) <= 3):
                inputs = list(inputs)
                del inputs[marker_loc + 1]
                del inputs[marker_loc]
                inputs = tuple(inputs)
                gamemode = int(gamemode)
            else:
                await self.bot.say("**Please input a valid gamemode number.**")
                return
        else:
            gamemode = int(beatmap['mode'])

        username, _ = self._determine_api(server, list(inputs))
        username = username[0]
        # gives the final input for osu username
        username = await self._process_username(ctx, username)

        # for getting user scores
        userinfo = list(await get_user(key, api, username, gamemode))
        userscores = list(await get_scores(
            key, api, map_id, userinfo[0]['user_id'], gamemode))
        if userinfo and userscores:
            msg, top_plays = await self._get_user_scores(ctx, api, map_id, userinfo[0], userscores, gamemode, beatmap)
            await self.bot.say(msg, embed=top_plays)
        else:
            await self.bot.say("**`{}` was not found or no scores on the map.**".format(username))

    ## processes username. probably the worst chunck of code in this project so far. will fix/clean later
    async def _process_username(self, ctx, username, disp_error = True, check_api = True):
        channel = ctx.message.channel
        user = ctx.message.author
        server = user.server
        key = self.api_keys["osu_api_key"]

        # if nothing is given, must rely on if there's account
        if not username:
            if self._check_user_exists(user):
                find_user = db.user_settings.find_one({"user_id":user.id})
                username = find_user["osu_username"]
            else:
                if disp_error:
                    await self.bot.say("It doesn't seem that you have an account linked. Do `{}osuset user [username]`.".format(prefix))
                return None # bad practice, but too lazy to make it nice
        # if it's a discord user, first check to see if they are in database and choose that username
        # then see if the discord username is a osu username, then try the string itself
        elif find(lambda m: m.name == username, channel.server.members) is not None:
            target = find(lambda m: m.name == username, channel.server.members)
            try:
                find_user = db.user_settings.find_one({"user_id":target.id})
                username = find_user["osu_username"]
            except:
                if check_api and await get_user(key, self.osu_settings["type"]["default"], username, 0):
                    username = str(target)
                else:
                    await self.bot.say(help_msg[1])
                    return None
        # @ implies its a discord user (if not, it will just say user not found in the next section)
        # if not found, then oh well.
        elif "@" in username:
            user_id = re.findall("\d+", username)
            if user_id:
                user_id = user_id[0]
                find_user = db.user_settings.find_one({"user_id":user_id})
                if find_user:
                    username = find_user["osu_username"]
                else:
                    await self.bot.say(help_msg[1])
                    return None
            else:
                await self.bot.say(help_msg[1])
                return None
        else:
            username = str(username)
        return username

    # Checks if user exists
    def _check_user_exists(self, user):
        find_user = db.user_settings.find_one({"user_id":user.id})
        if not find_user:
            return False
        return True

    def _get_api_name(self, url:str):
        if url == self.osu_settings["type"]["ripple"]:
            return "Ripple"
        else:
            return "Official"

    # Gives a small user profile
    async def _get_user_info(self, api:str, server, server_user, user, gamemode: int):
        if api == self.osu_settings["type"]["default"]:
            profile_url ='https://a.ppy.sh/{}'.format(user['user_id'])
            pp_country_rank = " ({}#{})".format(user['country'], user['pp_country_rank'])
        elif api == self.osu_settings["type"]["ripple"]:
            profile_url = 'http://a.ripple.moe/{}.png'.format(user['user_id'])
            pp_country_rank = ""

        flag_url = 'https://osu.ppy.sh/images/flags/{}.png'.format(user['country'])

        gamemode_text = get_gamemode(gamemode)

        #try:
        user_url = 'https://{}/u/{}'.format(api, user['user_id'])
        em = discord.Embed(description='', colour=server_user.colour)
        em.set_author(name="{} Profile for {}".format(gamemode_text, user['username']), icon_url = flag_url, url = user_url)
        em.set_thumbnail(url=profile_url)
        level_int = int(float(user['level']))
        level_percent = float(user['level']) - level_int

        info = ""
        info += "**▸ {} Rank:** #{} {}\n".format(self._get_api_name(api), user['pp_rank'], pp_country_rank)
        info += "**▸ Level:** {} ({:.2f}%)\n".format(level_int, level_percent*100)
        info += "**▸ Total PP:** {}\n".format(user['pp_raw'])
        info += "**▸ Hit Accuracy:** {}%\n".format(user['accuracy'][0:5])
        info += "**▸ Playcount:** {}".format(user['playcount'])
        em.description = info

        if api == self.osu_settings["type"]["default"]:
            time_url = "https://osu.ppy.sh/u/{}".format(user['user_id'])
            print('time_url: {}'.format(time_url))
            soup = await get_web(time_url)
            timestamps = []
            for tag in soup.findAll(attrs={'class': 'timeago'}):
                timestamps.append(datetime.datetime.strptime(tag.contents[0].strip().replace(" UTC", ""), '%Y-%m-%d %H:%M:%S'))
                print('tag: {}'.format(tag.contents[0].strip().replace(" UTC", "")))
                print('datetime: {}'.format(datetime.datetime.strptime(tag.contents[0].strip().replace(" UTC", ""), '%Y-%m-%d %H:%M:%S')))
            print('timestamps: {}'.format(timestamps))
            if user['username'] == 'peppy':
                timeago = time_ago(datetime.datetime.now(), timestamps[0])
            else:
                timeago = time_ago(datetime.datetime.now(), timestamps[1])
            print('datetime_now: {}'.format(datetime.datetime.now()))
            print('timeago: {}'.format(timeago))
            timeago = "Last Logged in {} ago".format(timeago)
            em.set_footer(text=timeago)
        else:
            em.set_footer(text = "On osu! {} Server".format(self._get_api_name(api)))

        return em
        #except:
            #return None

    # Gives a detailed user profile
    async def _det_user_info(self, api:str, server, server_user, user, gamemode: int):
        key = self.api_keys["osu_api_key"]
        if api == self.osu_settings["type"]["default"]:
            profile_url ='https://a.ppy.sh/{}'.format(user['user_id'])
            pp_country_rank = " ({}#{})".format(user['country'], user['pp_country_rank'])
        elif api == self.osu_settings["type"]["ripple"]:
            profile_url = 'http://a.ripple.moe/{}.png'.format(user['user_id'])
            pp_country_rank = ""

        flag_url = 'https://osu.ppy.sh/images/flags/{}.png'.format(user['country'])

        gamemode_text = get_gamemode(gamemode)

        #try:
        user_url = 'https://{}/u/{}'.format(api, user['user_id'])
        em = discord.Embed(description='', colour=server_user.colour)
        em.set_author(name="{} Profile for {}".format(gamemode_text, user['username']), icon_url = flag_url, url = user_url)
        em.set_thumbnail(url=profile_url)
        topscores = list(await get_user_best(key, api, user['username'], gamemode, 100))
        modstats = await self._process_mod_stats(topscores, user)
        level_int = int(float(user['level']))
        level_percent = float(user['level']) - level_int
        totalhits = int(user['count50']) + int(user['count100']) + int(user['count300'])
        if totalhits == 0:
            totalhits = 1
        totalranks = int(user['count_rank_ss']) + int(user['count_rank_s']) + int(user['count_rank_a'])
        if totalranks == 0:
            totalranks = 1

        info = ""
        info += "**▸ {} Rank:** #{} {}\n".format(self._get_api_name(api), user['pp_rank'], pp_country_rank)
        info += "**▸ Level:** {} ({:.2f}%)\n".format(level_int, level_percent*100)
        info += "**▸ Total PP:** {:,} ({:,.2f} Per Play)\n".format(float(user['pp_raw']), float(user['pp_raw']) / int(user['playcount']))
        info += "**▸ Hit Accuracy:** {}%\n".format(user['accuracy'][0:5])
        info += "**▸ Playcount:** {:,}\n".format(int(user['playcount']))
        info += "**▸ Total Hits:** {:,} ({:,.2f} Per Play)\n".format(
            totalhits, totalhits / int(user['playcount']))
        info += "**▸ Ranked Score:** {:,} ({:,.2f} Per Play)\n".format(
            int(user['ranked_score']), int(user['ranked_score']) / int(user['playcount']))
        info += "**▸ Total Score: ** {:,} ({:,.2f} Per Play)\n".format(
            int(user['total_score']), int(user['total_score']) / int(user['playcount']))
        info += "**▸ 300:** {:,} *({:.2f}%)* **○ 100:** {:,} *({:.2f}%)* **○ 50:** {:,} *({:.2f}%)*\n".format(
            int(user['count300']), (int(user['count300']) / totalhits) * 100,
            int(user['count100']), (int(user['count100']) / totalhits) * 100,
            int(user['count50']), (int(user['count50']) / totalhits) * 100)
        info += "**▸ SS:** {:,} *({:.2f}%)* **○ S:** {:,} *({:.2f}%)* **○ A:** {:,} *({:.2f}%)*\n".format(
            int(user['count_rank_ss']), (int(user['count_rank_ss']) / totalranks) * 100,
            int(user['count_rank_s']), (int(user['count_rank_s']) / totalranks) * 100,
            int(user['count_rank_a']), (int(user['count_rank_a']) / totalranks) * 100)

        if api == self.osu_settings["type"]["default"]:
            time_url = "https://osu.ppy.sh/u/{}".format(user['user_id'])
            soup = await get_web(time_url)
            timestamps = []
            for tag in soup.findAll(attrs={'class': 'timeago'}):
                timestamps.append(datetime.datetime.strptime(tag.contents[0].strip().replace(" UTC", ""), '%Y-%m-%d %H:%M:%S'))
            if user['username'] == 'peppy':
                logged = time_ago(datetime.datetime.now(), timestamps[0])
                info += "**▸ Joined Osu! in the beginning.**\n"
                info += "**▸ Last Logged in {}**".format(logged)
            else:
                joined = time_ago(datetime.datetime.now(), timestamps[0])
                logged = time_ago(datetime.datetime.now(), timestamps[1])
                info += "**▸ Joined Osu! {}**\n".format(joined)
                info += "**▸ Last Logged in {}**".format(logged)
        em.description = info
        em.add_field(name='Favourite Mods:', value='{}'.format(modstats[0]))
        em.add_field(name='PP Sources:', value='{}'.format(modstats[1]))
        em.add_field(name='PP Range:', value='{:,} - {:,} = {:,}'.format(
            float(topscores[0]['pp']), float(topscores[len(topscores) - 1]['pp']),
            round(float(topscores[0]['pp']) - float(topscores[len(topscores) - 1]['pp']), 2)))
        if self._get_api_name(api) == "Official":
            em.set_footer(text = "On osu! {} Server".format(self._get_api_name(api)))
        else:
            em.set_footer(text = "On osu! {} Server (Servers other than Official are glitched with -d)".format(self._get_api_name(api)))
        return em
        #except:
            #return None

    # Written by Jams
    async def _process_mod_stats(self, scores, user):
        moddic = {"weighted": {}, "unweighted": {}}
        totals = {"weighted":0, "unweighted":0}
        for i, score in enumerate(scores):
            mod = fix_mods(''.join(num_to_mod(score['enabled_mods'])))
            if mod == '':
                mod = "No Mod"
            weight = float(score['pp']) * (0.95 ** i)
            unweighted = float(score['pp'])
            if not mod in moddic['weighted']:
                moddic['weighted'][mod] = weight
                moddic['unweighted'][mod] = unweighted
                totals['weighted'] += weight
                totals['unweighted'] += unweighted
            else:
                moddic['weighted'][mod] += weight
                moddic['unweighted'][mod] += unweighted
                totals['weighted'] += weight
                totals['unweighted'] += unweighted
        mods_weighted = sorted(list(moddic['weighted'].items()), key=operator.itemgetter(1), reverse=True)
        mods_unweighted = sorted(list(moddic['unweighted'].items()), key=operator.itemgetter(1), reverse=True)
        favourites = ''
        for mod in mods_unweighted:
            favourites += "**{}**: {:.2f}% ".format(mod[0], (moddic['unweighted'][mod[0]] / totals['unweighted']) * 100)
        sources = ''
        for mod in mods_weighted:
            sources += "**{}**: {:.2f}PP ".format(mod[0], mod[1])
        return [favourites, sources]

    async def _get_recent(self, ctx, api, user, userrecent, gamemode:int):
        server_user = ctx.message.author
        server = ctx.message.server
        key = self.api_keys["osu_api_key"]

        if api == self.osu_settings["type"]["default"]:
            profile_url ='https://a.ppy.sh/{}'.format(user['user_id'])
        elif api == self.osu_settings["type"]["ripple"]:
            profile_url = 'http://a.ripple.moe/{}.png'.format(user['user_id'])

        flag_url = 'https://osu.ppy.sh/images/flags/{}.png'.format(user['country'])

        # get best plays map information and scores
        beatmap = list(await get_beatmap(key, api, beatmap_id=userrecent['beatmap_id']))[0]
        if not userrecent:
            return ("**No recent score for `{}` in user's default gamemode (`{}`)**".format(user['username'], get_gamemode(gamemode)), None)
        acc = calculate_acc(userrecent, gamemode)
        fc_acc = no_choke_acc(userrecent, gamemode)
        mods = num_to_mod(userrecent['enabled_mods'])

        # determine mods
        if not mods:
            mods = []
            mods.append('No Mod')
        else:
            oppai_mods = "+{}".format("".join(mods))

        beatmap_url = 'https://osu.ppy.sh/b/{}'.format(beatmap['beatmap_id'])

        msg = "**Most Recent {} Play for {}:**".format(get_gamemode(gamemode), user['username'])
        info = ""

        # calculate potential pp
        pot_pp = ''
        if userrecent['rank'] == 'F':
            totalhits = (int(userrecent['count50']) + int(userrecent['count100']) + int(userrecent['count300']) + int(userrecent['countmiss']))
            oppai_output = await get_pyoppai(userrecent['beatmap_id'], accs=[float(acc)], mods = int(userrecent['enabled_mods']), completion=totalhits)
            if oppai_output != None:
                pot_pp = '**No PP** ({:.2f}PP for {:.2f}% FC)'.format(oppai_output['pp'][0], fc_acc)
        else:
            oppai_output = await get_pyoppai(userrecent['beatmap_id'], combo=int(userrecent['maxcombo']), accs=[float(acc)], fc=fc_acc, mods = int(userrecent['enabled_mods']), misses=int(userrecent['countmiss']))
            if oppai_output != None:
                if oppai_output['pp'][0] != oppai_output['pp'][1]:
                    pot_pp = '**{:.2f}PP** ({:.2f}PP for {:.2f}% FC)'.format(oppai_output['pp'][0], oppai_output['pp'][1], fc_acc)
                else:
                    pot_pp = '**{:.2f}PP**'.format(oppai_output['pp'][0])

        info += "▸ **{} Rank** ▸ {} ▸ {}%\n".format(userrecent['rank'], pot_pp, round(acc,2))
        info += "▸ {} ▸ x{}/{} ▸ [{}/{}/{}/{}]\n".format(
            userrecent['score'],
            userrecent['maxcombo'], beatmap['max_combo'],
            userrecent['count300'], userrecent['count100'], userrecent['count50'], userrecent['countmiss'])
        if userrecent['rank'] == 'F':
            try:
                info += "▸ **Map Completion:** {:.2f}%".format(oppai_output['map_completion'])
            except:
                pass

        # get stars
        star_str, _ = compare_val(beatmap['difficultyrating'], oppai_output, 'stars', dec_places = 2, single = True)

        # grab beatmap image
        soup = await get_web(beatmap_url)
        #print("beatmap_url: {}".format(beatmap_url))
        map_image = json.loads(soup.find('script', {'id': 'json-beatmapset'}).get_text())
        #print("map_image: {}".format(len(map_image)))
        if map_image['covers']['list@2x']:
            map_image_url = map_image['covers']['list@2x']
        else:
            map_image_url = "https://share.lucker.xyz/img/unknown.png"
        #print("map_image_url: {}".format(map_image_url))

        em = discord.Embed(description=info, colour=server_user.colour)
        em.set_author(name="{} [{}] +{} [{}★]".format(beatmap['title'], beatmap['version'],
            fix_mods(''.join(mods)),star_str), url = beatmap_url, icon_url = profile_url)
        em.set_thumbnail(url=map_image_url)
        timeago = time_ago(datetime.datetime.utcnow() + datetime.timedelta(hours=8), datetime.datetime.strptime(userrecent['date'], '%Y-%m-%d %H:%M:%S'))
        em.set_footer(text = "{}Ago On osu! {} Server".format(timeago, self._get_api_name(api)))
        return (msg, em)

    # to take load off of the api/faster osutop
    async def _get_user_best_web(self, ctx, user, gamemode:int, num_plays = None):
        if not num_plays:
            num_plays = self.osu_settings['num_best_plays']

        user_id = user['user_id']
        url = "https://osu.ppy.sh/u/{}".format(user['user_id'])
        mode = modes[gamemode]
        if gamemode == 2:
            mode = "fruits"

        url = 'https://osu.ppy.sh/users/{}'.format(user_id)
        soup = await get_web(url, parser = "lxml")
        script = soup.find('script',{"id": "json-user"})
        user = json.loads(script.get_text())

        top_plays = user['allScoresBest'][mode]
        play_list = []
        map_list = []
        acc_list = []

        for play in top_plays[:num_plays]:
            play_info = {}
            map_info = {}

            map_info['title'] = play['beatmapset']['title']
            map_info['beatmap_id'] = play['beatmap']['id']
            map_info['difficultyrating'] = play['beatmap']['difficulty_rating']
            map_info['version'] = play['beatmap']['version']
            map_info['max_combo'] = None # website doesn't give this information :C
            map_list.append(map_info)

            play_info['beatmap_id'] = play['beatmap']['id']
            play_info['score'] = play['score']
            play_info['pp'] = play['pp']
            play_info['rank'] = play['rank']
            play_info['date'] = play['created_at']
            play_info['enabled_mods'] = mod_to_num(''.join(play['mods']))
            play_info['maxcombo'] = play['max_combo']
            play_info['count300'] = play['statistics']['count_300']
            play_info['count100'] = play['statistics']['count_100']
            play_info['count50'] = play['statistics']['count_50']
            play_info['countgeki'] = play['statistics']['count_geki']
            play_info['countkatu'] = play['statistics']['count_katu']
            play_info['countmiss'] = play['statistics']['count_miss']
            play_list.append(play_info)

            acc_list.append(float(play['accuracy']*100))

        return play_list, map_list, acc_list

    # written by Jams
    async def _get_user_scores(self, ctx, api, map_id, user, userscore, gamemode:int, beatmap):
        server_user = ctx.message.author
        server = ctx.message.server
        key = self.api_keys["osu_api_key"]

        if api == self.osu_settings["type"]["default"]:
            profile_url ='https://a.ppy.sh/{}'.format(user['user_id'])
        elif api == self.osu_settings["type"]["ripple"]:
            profile_url = 'http://a.ripple.moe/{}.png'.format(user['user_id'])

        flag_url = 'https://osu.ppy.sh/images/flags/{}.png'.format(user['country'])
        gamemode_text = get_gamemode(gamemode)

        # sort the scores based on pp
        userscore = sorted(userscore, key=operator.itemgetter('pp'), reverse=True)

        # get best plays map information and scores
        best_beatmaps = []
        best_acc = []
        pp_sort = []
        for i in range(len(userscore)):
            score = userscore[i]
            best_beatmaps.append(beatmap)
            best_acc.append(calculate_acc(score,gamemode))

        all_plays = []
        desc = ''
        mapname = '{} [{}]'.format(
            best_beatmaps[i]['title'],
            best_beatmaps[i]['version'])

        for i in range(len(userscore)):
            mods = num_to_mod(userscore[i]['enabled_mods'])
            oppai_info = await get_pyoppai(best_beatmaps[i]['beatmap_id'], accs = [float(best_acc[i])], mods = int(userscore[i]['enabled_mods']))

            if not mods:
                mods = []
                mods.append('No Mod')
            beatmap_url = 'https://osu.ppy.sh/b/{}'.format(best_beatmaps[i]['beatmap_id'])

            info = ''
            star_str, _ = compare_val(best_beatmaps[i]['difficultyrating'], oppai_info, param = 'stars', dec_places = 2, single = True)
            info += '**{}. {} Score** [{}★]\n'.format(
                i+1, fix_mods(''.join(mods)), star_str)
            # choke text
            choke_text = ''
            if (oppai_info != None and userscore[i]['countmiss'] != None and best_beatmaps[i]['max_combo']!= None) and (int(userscore[i]['countmiss'])>=1 or (int(userscore[i]['maxcombo']) <= 0.95*int(best_beatmaps[i]['max_combo']) and 'S' in userscore[i]['rank'])):
                choke_text += ' _({:.2f}pp for FC)_'.format(oppai_info['pp'][0])
            info += '▸ **{} Rank** ▸ **{:.2f}pp**{} ▸ {:.2f}%\n'.format(userscore[i]['rank'], float(userscore[i]['pp']), choke_text, float(best_acc[i]))
            info += '▸ {} ▸ x{}/{} ▸ [{}/{}/{}/{}]\n'.format(
                userscore[i]['score'],
                userscore[i]['maxcombo'], best_beatmaps[i]['max_combo'],
                userscore[i]['count300'],userscore[i]['count100'],userscore[i]['count50'],userscore[i]['countmiss']
                )

            timeago = time_ago(datetime.datetime.utcnow() + datetime.timedelta(hours=8), datetime.datetime.strptime(userscore[i]['date'], '%Y-%m-%d %H:%M:%S'))
            info += '▸ Score Set {}Ago\n'.format(timeago)

            desc += info
        em = discord.Embed(description=desc, colour=server_user.colour)
        title = "Top {} Plays for {} on {}".format(gamemode_text, user['username'], mapname)
        em.set_author(name = title, url="https://osu.ppy.sh/b/{}".format(map_id), icon_url=flag_url)
        em.set_footer(text = "On osu! {} Server".format(self._get_api_name(api)))
        em.set_thumbnail(url=profile_url)

        return ("", em)

    #--------------------- Suggestion Database Creation/Methods ------------------------
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.command(pass_context=True, no_pm=True, aliases = ['r','rec'])
    async def recommend(self, ctx, *options):
        """>recommend [mods] [target pp]"""
        key = self.api_keys["osu_api_key"]
        # gives the final input for osu username
        username = ctx.message.author.name
        username = await self._process_username(ctx, username)

        if not username:
            return
        if len(options) > 2:
            await self.bot.say('**Incorrect usage: `>recommend [mods] [target pp]`**')
            return

        mods = None
        target_pp = None
        for option in options:
            if option.isnumeric():
                target_pp = float(option)
            else:
                if str(option).lower() == 'nomod':
                    mods = ''
                elif str(option).lower() == 'any':
                    mods = 'ANY'
                else:
                    mods = str(option)

        #print('Target pp: ', str(target_pp), 'Mods: ', mods)

        top_num = 10 # use top 12 plays
        gamemode = 0
        try:
            userbest = list(await get_user_best(
                key, self.osu_settings["type"]["default"], username, gamemode, top_num))
        except:
            await self.bot.say('Error. Please try again later.')
            return

        # get statistics for these plays <- should be its own function
        # since used multiple times (-d)
        top_beatmap_ids = []
        moddic = {}
        totals = 0
        sum_pp = 0
        for i in range(len(userbest)):
            score = userbest[i]
            top_beatmap_ids.append(score['beatmap_id'])
            mod_text = fix_mods(''.join(num_to_mod(score['enabled_mods'])))

            unweighted = float(score['pp'])
            sum_pp += float(score['pp'])
            if not mod_text in moddic.keys():
                moddic[mod_text] = unweighted
                totals += unweighted
            else:
                moddic[mod_text] += unweighted
                totals += unweighted

        if target_pp is None:
            if len(userbest) != 0:
                average_pp = sum_pp/len(userbest)
                average_pp += random.randint(0, int(average_pp/5))
            else:
                await self.bot.say('**Not enough plays.**')
                return
        else:
            average_pp = target_pp

        mods_unweighted = sorted(list(moddic.items()), key=operator.itemgetter(1), reverse=True)
        mods_unweighted = mods_unweighted[:3]

        # give recommendation
        pp_range = determine_pp_range(average_pp)
        full_pp_list = db.suggest_osu.find_one({'pp_range':pp_range})
        if not full_pp_list:
            await self.bot.say('**No suggestions at the moment.**')
            return

        # handle what mod to look for
        if mods != 'ANY':
            if mods is None: # based on player's mods
                # I could make this weighted, but whatever
                mods = random.choice([best_mod for best_mod, _ in mods_unweighted])
            elif mods is not None:
                mods = mods.replace('+','').upper()
            user_mods = set(num_to_mod(mod_to_num(mods))) # mods is now a set

        suggest_list = []
        for beatmap_id, mod_combo_list in full_pp_list['beatmaps']:
            map_mods = set(num_to_mod(mod_to_num(
                ''.join(mod_combo_list).replace('SD', '').replace('PF', ''))))

            # won't check anything else if mods = ANY
            if mods == 'ANY' or (user_mods == map_mods and beatmap_id not in top_beatmap_ids):
                # print('Mods detected. {} {}'.format(str(mod), str(mods)))
                suggest_list.append((beatmap_id, ''.join(list(map_mods))))

        if suggest_list:
            beatmap_id, mods = random.choice(suggest_list)
            #beatmap_url = 'https://osu.ppy.sh/b/{}'.format(beatmap_id)
            beatmap_url = 'https://osu.ppy.sh/beatmapsets/{}'.format(beatmap_id)
            beatmap = await get_beatmap(key, self.osu_settings["type"]["default"], beatmap_id)
            await self.disp_beatmap(ctx.message, beatmap, beatmap_url, mods=mods, username = ctx.message.author.name)
        else:
            await self.bot.say('**No suggestions at the moment.**')
            return

    # this code is very similar to the play tracker
    async def suggestion_play_parser(self, player):
        # ensures that data is recieved
        got_data = False
        get_data_counter = 1
        top_plays = None
        mode = 0
        if 'osu_id' in player:
            osu_id = player['osu_id']
        else:
            osu_id = player['userinfo']['osu']['user_id']

        key = self.api_keys["osu_api_key"]
        while(not got_data and get_data_counter <= 10):
            try:
                top_plays = await get_user_best(
                    key, self.osu_settings["type"]["default"], osu_id,
                    mode, self.osu_settings["num_track"])
                got_data = True
            except:
                get_data_counter += 1

        if top_plays is None:
            return

        # if still no data
        if top_plays == None:
            print("Data fetched failed for {}".format(player['username']))
            return

        for play in top_plays:
            await self._append_suggestion_database(play)

    async def _append_suggestion_database(self, play):
        # calculate the pp for the beatmap
        accs = [100] # based on 100% acc
        mods_list = num_to_mod(play['enabled_mods']) # list
        oppai_output = await get_pyoppai(play['beatmap_id'], accs=accs, mods = int(play['enabled_mods']))
        if not oppai_output:
            return

        pp_100 = float(oppai_output['pp'][0])
        pp_range = determine_pp_range(pp_100)
        # create structure...
        section = db.suggest_osu.find_one({'pp_range':pp_range})
        if not section:
            """
            new_play = self._new_database_entry(play, oppai_output, mods_list)

            new_range = {'pp_range':pp_range, 'beatmaps': [new_play]}
            db.suggest_std.insert_one(new_range)
            """
            new_range = {'pp_range':pp_range, 'beatmaps': [(play['beatmap_id'], mods_list)]}
            db.suggest_osu.insert_one(new_range)
        else:
            for temp_beatmap, temp_mods in section['beatmaps']:
                if temp_beatmap == play['beatmap_id'] and temp_mods == mods_list:
                    return
            """
            new_play = self._new_database_entry(play, oppai_output, mods_list)
            section['beatmaps'].append(new_play)
            db.suggest_std.update_one({'pp_range':pp_range}, {'$set':{"beatmaps":section['beatmaps']}})
            """
            section['beatmaps'].append((play['beatmap_id'], mods_list))
            db.suggest_osu.update_one({'pp_range':pp_range}, {'$set':{"beatmaps":section['beatmaps']}})
        print("New {}, beatmap_id: {} mods: {}".format(pp_range, play['beatmap_id'], str(mods_list)))

    def _new_database_entry(self, play, oppai_output, mods_list):
            new_play = {}
            new_play['beatmap_id'] = play['beatmap_id']
            new_play['mods_list'] = mods_list
            bpm = play['bpm']
            if 'DT' in mods:
                bpm *= 1.5
            elif 'HT' in mods:
                bpm /= 1.5
            new_play['bpm'] = bpm
            new_play['ar'] = oppai_output['ar']
            new_play['od'] = oppai_ouput['od']

    # ---------------------------- Detect Links ------------------------------
    # called by listener
    async def find_link(self, message):
        # await self.bot.send_message(message.channel, 'URL DETECTED')
        server = message.server

        #try:
        if message.author.id == self.bot.user.id:
            return
        if message.content.startswith(prefix):
            return

        # ------------------------ get attachments ------------------------
        all_urls = []
        # get all attachments
        in_attachments = False
        for att in message.attachments:
            if 'screenshot' in str(att).lower():
                all_urls.append((str(att['proxy_url']), ''))
                in_attachments = True

        # process from a url in msg
        original_message = message.content

        # this is just me being extremely lazy and not wanting to deal with regex, will fix later
        for domain in ['osu', 'ripple', 'puu']:
            get_urls = re.findall("(https:\/\/{}[^\s]+)([ ]\+[A-Za-z][^\s]+)?".format(domain), original_message)
            for url in get_urls:
                all_urls.append(url)
            get_urls = re.findall("(http:\/\/{}[^\s]+)([ ]\+[A-Za-z][^\s]+)?".format(domain), original_message)
            for url in get_urls:
                all_urls.append(url)

        # get rid of duplicates
        all_urls = list(set(all_urls))

        if len(all_urls) > 3:
            all_urls = all_urls[0:3]
            await self.bot.send_message(message.channel, "Too many things, processing first 3.")

        ## -------------------- user url detection ---------------------

        if 'https://osu.ppy.sh/u/' in original_message:
            await self.process_user_url(all_urls, message)

        ## -------------------- beatmap detection ---------------------
        try:
            server_options = db.options.find_one({"server_id":server.id})
        except:
            return

        if server_options is None or server_options["beatmap"]:
            # try:
            beatmap_url_triggers = [
                'https://osu.ppy.sh/s/',
                'https://osu.ppy.sh/b/',
                'http://osu.ppy.sh/ss/',
                'https://osu.ppy.sh/ss/',
                'http://ripple.moe/ss/',
                'https://ripple.moe/ss/',
                'https://puu.sh',
                '.jpg', '.png'
                ]

            if any([link in original_message for link in beatmap_url_triggers]) or in_attachments:
                # print('LINK DETECTED!')
                await self.process_beatmap(all_urls, message, server_options)
            #except:
                #pass

    # processes user input for user profile link
    async def process_user_url(self, all_urls, message):
        key = self.api_keys["osu_api_key"]
        server_user = message.author
        try:
            server = message.author.server
        except:
            await self.bot.send_message('Cannot execute here.')
            return

        for url, suffix in all_urls:
            try:
                if url.find('https://osu.ppy.sh/u/') != -1:
                    user_id = url.replace('https://osu.ppy.sh/u/','')
                    user_info = await get_user(
                        key, self.osu_settings["type"]["default"], user_id, 0)
                    find_user = db.user_settings.find_one({"user_id":user_id})
                    if find_user:
                        gamemode = int(find_user["default_gamemode"])
                    else:
                        gamemode = 0
                    em = await self._get_user_info(
                        self.osu_settings["type"]["default"],
                        server, server_user, user_info[0], gamemode)
                    await self.bot.send_message(message.channel, embed = em)
            except:
                pass

    # processes user input for the beatmap
    async def process_beatmap(self, all_urls, message, server_options = None):
        key = self.api_keys["osu_api_key"]
        # print(all_urls)
        for url, mods in all_urls:
            screenshot_links = [
                'http://osu.ppy.sh/ss/',
                'https://osu.ppy.sh/ss/',
                'http://ripple.moe/ss/',
                'https://ripple.moe/ss/',
                'https://puu.sh',
                '.jpg', '.png'
                ]

            is_screenshot = any([url.find(link) != -1 for link in screenshot_links]) # checked twice..?
            #try:
            if url.find('https://osu.ppy.sh/s/') != -1:
                beatmap_id = url.replace('https://osu.ppy.sh/s/','')
                beatmap_info = await get_beatmapset(key, self.osu_settings["type"]["default"], beatmap_id)
                extra_info = None
                display_if = (server_options and server_options['graph_beatmap']) or (server_options is None)
                include_graph = display_if and len(beatmap_info) == 1
            elif url.find('https://osu.ppy.sh/b/') != -1:
                beatmap_id = url.replace('https://osu.ppy.sh/b/','')
                # find mods
                beatmap_info = await get_beatmap(key, self.osu_settings["type"]["default"], beatmap_id)
                extra_info = None
                include_graph = True
                if server_options and not server_options['graph_beatmap']:
                    include_graph = False
            elif is_screenshot:
                # (beatmap_info, beatmap_id, mods, pp, mode)
                print('Screenshot Detected!')
                if server_options is None or server_options["screenshot"]:
                    beatmap_info, beatmap_id, mods, map_url, extra_info = await self._get_screenshot_map(
                        url, unique_id = str(message.author.id))
                    url = map_url
                    include_graph = False # default is true
                    if server_options and server_options['graph_screenshot']:
                        include_graph = True
                else:
                    beatmap_info = None
            else: # catch all case
                beatmap_info = None

            if beatmap_info:
                #print(include_graph)
                await self.disp_beatmap(message, beatmap_info, url, mods, extra_info = extra_info, graph = include_graph)
            #except:
                #pass

    async def _get_screenshot_map(self, url, unique_id):
        key = self.api_keys["osu_api_key"]

        if not unique_id:
            unique_id = '0'

        # print(url)

        filepath = 'data/osu/temp/ss_{}.png'.format(unique_id)
        none_response = (None, None, None, None, None)

        # print("GETTING IMAGE")
        # determine if valid image
        try:
            async with aiohttp.get(url) as r:
                image = await r.content.read()
            with open(filepath,'wb') as f:
                f.write(image)
                f.close()
            original_image = Image.open(filepath)
        except:
            return none_response

        # print("IMAGE RETRIEVED")

        # get certain measurements for screenshot
        height = original_image.size[1]
        width = original_image.size[0]
        title_bar_height = height*0.124 # approximate ratio
        title_bar_width = width*0.66 # approximate ratio
        info_image = original_image.crop((0, 0, title_bar_width, title_bar_height))
        # info_image.save('ss_test.png')
        # deallocate memory?
        os.remove(filepath)
        info = pytesseract.image_to_string(info_image).split('\n')

        # process info
        map_name = None
        map_author = None # not as important
        player_name = None
        # print(info)
        for text in info:
            if len(text) != 0:
                if ('-' in text or "—" in text) and not map_name:
                    map_name = text

                played_by_present = get_similarity('Played by', text) > (len('Played by')/len(text))*(0.9)
                if played_by_present and not player_name and "by" in text:
                    player_name = text[text.find('by')+3:]
                    player_name = player_name[0:player_name.find(' on ')]
                    player_name = player_name.replace('|<', 'k').replace('l<', 'k')

                beatmap_author_present = get_similarity('Beatmap by', text) > (len('Beatmap by')/len(text))*(0.9)
                if beatmap_author_present and "by" in text:
                    map_author = text[text.find('by')+3:]

        # -------- last resorts for map names --------
        if len(info) > 0 and not map_name:
            map_name = info[0] # try setting the map name to the first thing

        # if there's no difficulty information, then try the whole top
        if '[' not in map_name or ']' not in map_name:
            title_image = original_image.crop((0, 0, width, title_bar_height/3 + 2))
            map_name = pytesseract.image_to_string(title_image)

        # print
        print(player_name, map_name, map_author)

        # deallocated memory?
        original_image = None
        info = None

        # if it couldn't get the name, not point in continuing
        if map_name is None or len(map_name) < 5:
            return none_response

        # first try top scores, then try recent plays
        for mode in modes2:
            for attr in ['best', 'recent']:
                # get from site
                try:
                    url = 'https://osu.ppy.sh/users/{}/{}'.format(player_name, mode)
                    soup = await get_web(url, parser = "lxml")
                    script = soup.find('script',{"id": "json-scores"})
                    user = json.loads(script.get_text())
                    success = True

                    beatmap_info = None
                    mods = ''
                except:
                    continue

                if attr == "best":
                    list_type = "Top"
                else:
                    list_type = "Recent"

                #try:
                plays = user[attr]
                for play in plays:
                    # using api to be consistent
                    if 'title' in play['beatmapset']:
                        compiled_name = "{} - {} [{}]".format(
                            play['beatmapset']['artist'],
                            play['beatmapset']['title'],
                            play['beatmap']['version'])
                        similarity = get_similarity(compiled_name, map_name)
                        # print(similarity)
                        if compiled_name in map_name or similarity >= 0.85: # high threshhold
                            # no pp if not top
                            if attr == "best":
                                pp = play["pp"]
                            else:
                                pp = None

                            extra_info = {
                                "rank": play["rank"],
                                "pp": pp,
                                "created_at": play['created_at'],
                                "accuracy": play['accuracy'],
                                "username": player_name.capitalize(),
                                "statistics": play['statistics'],
                                "type": list_type
                                }
                            mods = fix_mods(''.join(play['mods']))
                            beatmap_id = play['beatmap']['id']
                            #url = 'https://osu.ppy.sh/b/{}'.format(beatmap_id)
                            url = 'https://osu.ppy.sh/beatmapsets/{}'.format(beatmap_id)
                            beatmap_info = await get_beatmap(key, self.osu_settings["type"]["default"], beatmap_id)
                            return (beatmap_info, beatmap_id, mods, url, extra_info)

        # if that fails, try searching google? use only map name
        #try:
        author_query = ""
        if map_author:
            author_query = "(mapped by {})".format(map_author)

        search_query = "{} {} - Osu!".format(map_name, author_query).replace('|<', 'k')
        print(search_query)
        google_results = await get_google_search(search_query)
        # print(google_results)
        g_result_upper_threshold = 0.99
        overall_map_list = []
        max_similarity = 0
        map_sims = []
        for result in google_results:
            if 'https://osu.ppy.sh/s/' in result:
                url = ''
                beatmapset_id = result.replace('https://osu.ppy.sh/s/','')
                beatmap_info = await get_beatmapset(key, self.osu_settings["type"]["default"], beatmapset_id)
                # grab the correct map
                max_similarity = 0
                map_sims = []
                for bm in beatmap_info:
                    title = '{} - {} [{}]'.format(bm['artist'], bm['title'], bm['version'])
                    max_similarity = max(max_similarity, get_similarity(title, map_name))
                    map_sims.append(max_similarity)

                map_index = map_sims.index(max_similarity)
                # print(map_sims, map_index)
                bm_info = beatmap_info[map_index]
                beatmap_id = beatmap_info[map_index]["beatmap_id"]
                url = 'https://osu.ppy.sh/b/{}'.format(beatmap_id)

                return_tup = ([bm_info], beatmap_id, '', url, None)
                if max_similarity >= g_result_upper_threshold:
                    return return_tup
                else:
                    overall_map_list.append((max_similarity, return_tup))

            elif 'https://osu.ppy.sh/b/' in result:
                url = result
                beatmap_id = result.replace('https://osu.ppy.sh/b/','')
                beatmap_info = await get_beatmap(key, self.osu_settings["type"]["default"], beatmap_id)
                beatmap_info = beatmap_info[0]
                title = '{} - {} [{}]'.format(beatmap_info['artist'], beatmap_info['title'], beatmap_info['version'])
                max_similarity = max(max_similarity, get_similarity(title, map_name))
                map_sims.append(max_similarity)

                return_tup = ([beatmap_info], beatmap_id, '', url, None)
                if max_similarity >= g_result_upper_threshold: # threshhold
                    return return_tup
                else:
                    overall_map_list.append((max_similarity, return_tup))

        # get if none of them are extremely accurate, pick the most accurate
        # print(overall_map_list)
        if overall_map_list:
            sorted(overall_map_list, key=operator.itemgetter(0), reverse = True)
            return overall_map_list[0][1]

        return none_response

    # displays the beatmap properly
    async def disp_beatmap(self, message, beatmap, beatmap_url:str, mods='', extra_info = None, graph = False, username = None):
        # create embed
        em = discord.Embed()

        # process time
        num_disp = min(len(beatmap), self.max_map_disp)
        if (len(beatmap) > self.max_map_disp):
            msg = "Found {} maps, but only displaying {}.\n".format(len(beatmap), self.max_map_disp)
        else:
            msg = "Found {} map(s).\n".format(len(beatmap))

        # sort by difficulty first
        map_order = []
        for i in range(len(beatmap)):
            map_order.append((i,float(beatmap[i]['difficultyrating'])))
        map_order = sorted(map_order, key=operator.itemgetter(1), reverse=True)
        map_order = map_order[0:num_disp]

        beatmap_msg = ""
        oppai_version = ""
        accs = [95, 99, 100]

        mods = fix_mods(mods.upper())
        mod_num = mod_to_num(mods)

        # deal with extra info
        if extra_info and extra_info['pp'] == None:
            statistics = extra_info['statistics']
            totalhits = int(statistics['count_50']) + int(statistics['count_100']) + int(statistics['count_300']) + int(statistics['count_miss'])
            user_oppai_info = await get_pyoppai(
                beatmap[0]['beatmap_id'], accs = [float(extra_info['accuracy']*100)], mods = mod_num, completion = totalhits)
            extra_info['pp'] = user_oppai_info['pp'][0]

        # safe protect
        if self.imgur.credits['ClientRemaining'] is not None and int(self.imgur.credits['ClientRemaining']) >= 60:
            imgur_object = self.imgur
        else:
            imgur_object = None

        oppai_info = await get_pyoppai(beatmap[0]['beatmap_id'], accs = accs, mods = mod_num, plot = graph, imgur = imgur_object)

        m0, s0 = divmod(int(beatmap[0]['total_length']), 60)
        if oppai_info != None:
            # oppai_version = oppai_info['oppai_version']
            if 'DT' in mods or 'HT' in mods or 'NC' in mods:
                if 'DT' in mods or 'NC' in mods:
                    m1, s1, bpm_mod = calc_time(beatmap[0]['total_length'], beatmap[0]['bpm'], 1.5)
                elif 'HT' in mods:
                    m1, s1, bpm_mod = calc_time(beatmap[0]['total_length'], beatmap[0]['bpm'], (2/3))
                desc = '**Length:** {}:{}({}:{})  **BPM:** {:.1f}({}) '.format(
                    m0, str(s0).zfill(2),
                    m1, str(s1).zfill(2),
                    float(beatmap[0]['bpm']), bpm_mod)
            else:
                desc = '**Length:** {}:{} **BPM:** {}  '.format(m0,
                    str(s0).zfill(2), beatmap[0]['bpm'])
        else:
            desc = '**Length:** {}:{} **BPM:** {}  '.format(m0,
                str(s0).zfill(2), beatmap[0]['bpm'])

        # Handle mods
        desc += "**Mods:** "
        if mods != '':
            desc += mods
        else:
            desc += '-'
        desc += '\n'

        for i, diff in map_order:
            if i == 0:
                temp_oppai_info = oppai_info
            elif oppai_info == None:
                temp_oppai_info == None
            else:
                temp_oppai_info = await get_pyoppai(beatmap[i]['beatmap_id'], accs = accs, mods = mod_num)

            # updated values, if it has the oppai value, it will give it
            stars, stars_val = compare_val(beatmap[i]['difficultyrating'], temp_oppai_info, param = 'stars', dec_places = 2)
            ar, ar_val = compare_val(beatmap[i]['diff_approach'], temp_oppai_info, param = 'ar')
            od, od_val = compare_val(beatmap[i]['diff_overall'], temp_oppai_info, param = 'od')
            hp, hp_val = compare_val(beatmap[i]['diff_drain'], temp_oppai_info, param = 'hp')
            cs, cs_val = compare_val(beatmap[i]['diff_size'], temp_oppai_info, param = 'cs')
            max_combo, max_combo_val = compare_val(beatmap[i]['max_combo'], temp_oppai_info, param = 'max_combo', dec_places = 0)

            # calculate pp for other gamemodes if necessary
            gamemode = int(beatmap[i]['mode'])
            # print(gamemode)

            if gamemode == 1: # taiko
                temp_oppai_info['pp'] = await _get_taiko_pp(
                    stars_val, od_val, max_combo_val, accs = accs, mods = mods)
            elif gamemode == 2: # ctb
                temp_oppai_info['pp'] = await _get_ctb_pp(
                    stars, beatmap[i]['diff_approach'], max_combo_val, accs = accs, mods = mods)
            """elif gamemode == 3: # mania
                # print(temp_oppai_info)
                # print(beatmap[i])
                temp_oppai_info['pp'] = await _get_mania_pp(
                    beatmap[i]['difficultyrating'], od_val, temp_oppai_info['max_combo'], score = None, accs = accs, mods = mods)"""

            beatmap_info = ""
            beatmap_info += "**▸Difficulty:** {}★ **▸Max Combo:** x{}\n".format(
                stars, max_combo)
            beatmap_info += "**▸AR:** {} **▸OD:** {} **▸HP:** {} **▸CS:** {}\n".format(
                ar, od, hp, cs)

            # calculate pp values
            if temp_oppai_info != None:
                beatmap_info += '**▸PP:** '
                for j in range(len(accs[0:3])):
                    beatmap_info += '○ **{}%**–{:.2f} '.format(accs[j], temp_oppai_info['pp'][j])

            show_mode = ''
            if gamemode != 0:
                show_mode = ' [{}]'.format(modes[gamemode])

            em.add_field(name = "__{}__{}\n".format(beatmap[i]['version'], show_mode), value = beatmap_info, inline = False)

        # download links
        dl_links = self._get_dl_links(beatmap[i]['beatmapset_id'], beatmap[i]['beatmap_id'])
        desc += '**Download:** [map]({})([no vid]({}))  [osu!direct]({})  [bloodcat]({})\n'.format(
            dl_links[0],dl_links[1],dl_links[2],dl_links[3])
        desc += '-------------------\n'

        # if it's a screenshot and score is detected
        if extra_info:
            official = ""
            if extra_info['type'] == "Recent":
                official = " _(Not official)_"

            pp = "-"
            if extra_info['pp']:
                pp = "{:.2f}".format(float(extra_info['pp']))

            desc += "**{} play for [{}]({})\n▸ {} rank  ▸ {}pp{}  ▸ {:.2f}%**\n".format(
                extra_info['type'],
                extra_info['username'], 'https://osu.ppy.sh/users/{}'.format(extra_info['username'].replace(' ', '\\_').replace("_", "\\_")),
                extra_info['rank'], pp, official, float(extra_info['accuracy']*100))
            timeago = time_ago(
                datetime.datetime.utcnow(),
                datetime.datetime.strptime(extra_info['created_at'], '%Y-%m-%dT%H:%M:%S+00:00')) # 2016-11-04T04:20:35+00:00
            desc += 'Played {}Ago\n'.format(timeago) # timestamp
            desc += '-------------------'

        # determine color of embed based on status
        colour, colour_text = self._determine_status_color(int(beatmap[i]['approved']))

        # create return em
        em.colour = colour
        em.description = desc
        em.set_author(name="{} – {} by {}".format(beatmap[0]['artist'], beatmap[0]['title'], beatmap[0]['creator']), url=beatmap_url)
        soup = await get_web(beatmap_url)
        #print("beatmap_url: {}".format(beatmap_url))
        map_image = json.loads(soup.find('script', {'id': 'json-beatmapset'}).get_text())
        #print("map_image: {}".format(len(map_image)))
        if map_image['covers']['list@2x']:
            map_image_url = map_image['covers']['list@2x']
        else:
            map_image_url = "https://share.lucker.xyz/img/unknown.png"
        #print("map_image_url: {}".format(map_image_url))
        em.set_thumbnail(url=map_image_url)
        if oppai_info and 'graph_url' in oppai_info:
            em.set_image(url=oppai_info['graph_url'])

        # await self.bot.send_message(message.channel, map_image_url)
        for_user = ''
        if username is not None:
            for_user = 'Request for {} | '.format(username)

        em.set_footer(text = '{} | {}Powered by Oppai v0.9.5'.format(colour_text, for_user))

        await self.bot.send_message(message.channel, msg, embed = em)

    def _get_dl_links(self, beatmapset_id, beatmap_id):
        vid = 'https://osu.ppy.sh/d/{}'.format(beatmapset_id)
        novid = 'https://osu.ppy.sh/d/{}n'.format(beatmapset_id)
        direct = 'osu://b/{}'.format(beatmap_id)
        bloodcat = 'https://bloodcat.com/osu/s/{}'.format(beatmapset_id)

        ret = [vid, novid, direct, bloodcat]
        return ret

    def _determine_status_color(self, status):
        colour = 0xFFFFFF
        text = 'Unknown'

        if status == -2: # graveyard, red
            colour = 0xc10d0d
            text = 'Graveyard'
        elif status == -1: # WIP, purple
            colour = 0x713c93
            text = 'Work in Progress'
        elif status == 0: # pending, blue
            colour = 0x1466cc
            text = 'Pending'
        elif status == 1: # ranked, bright green
            colour = 0x02cc37
            text = 'Ranked'
        elif status == 2: # approved, dark green
            colour = 0x0f8c4a
            text = 'Approved'
        elif status == 3: # qualified, turqoise
            colour = 0x00cebd
            text = 'Qualified'
        elif status == 4: # loved, pink
            colour = 0xea04e6
            text = 'Loved'

        return (colour, text)
