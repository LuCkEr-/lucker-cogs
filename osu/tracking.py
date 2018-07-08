import logging
import operator
from random import randint

import discord
import numpy as np
from cogs.utils import checks
from discord.ext import commands
from discord.utils import find

from __main__ import send_cmd_help

from .common import *
from .fetching import *
from .helper import *
from .utils.dataIO import fileIO

log = logging.getLogger("red.osu.tracker")
log.setLevel(logging.DEBUG)

class Tracking:
    def __init__(self, bot):
        self.bot = bot
        self.osu_settings = fileIO("data/osu/osu_settings.json", "load")
        self.api_keys = fileIO("data/osu/apikey.json", "load")
        self.max_requests = 1100 # per minute, for tracking only
        self.total_requests = 0
        self.server_send_fail = []
        self.cycle_time = 0
        self.sleep_time = 0.01 # initial
        self.track_server_limit = 150
        global api_counter
        self.latency = collections.deque(maxlen = 300)
        if os.path.exists('data/osu/temp/latency.txt'):
            with open('data/osu/temp/latency.txt', "r") as f:
                for line in f:
                    self.latency.append(int(line.strip()))

    @commands.group(pass_context=True)
    async def osutrack(self, ctx):
        """Set some tracking options"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    # @commands.cooldown(1, 300, commands.BucketType.user)
    @osutrack.command(name = "latency", pass_context=True, no_pm=True)
    async def graph_latency(self, ctx):
        """Check tracking latency for past 300 plays"""
        channel = ctx.message.channel

        plt.figure(figsize=(10, 5))
        plt.style.use('ggplot')
        self.latency = collections.deque([i for i in self.latency if i < 1200], maxlen = 300)
        x = np.array(self.latency)/60 # for minutes
        plt.hist(x, bins=18, color='c')
        plt.axvline(x.mean(), color='b', linestyle='dashed', linewidth=2)
        plt.xlabel('min')
        plt.ylabel('# Plays')
        plt.tight_layout()
        filepath = 'data/osu/temp/latency.png'
        plt.savefig(filepath)
        plt.close()
        await self.bot.send_file(channel, filepath, content='**Tracking Latency for Previous 300 Plays**')
        # self.save_latency()

    async def save_latency(self):
        # save the data somewhere
        filepath = 'data/osu/temp/latency.txt'
        with open(filepath, "w") as f:
            for l in self.latency:
                f.write(str(l) +"\n")

    @osutrack.command(pass_context=True, no_pm=True)
    async def list(self, ctx):
        """Check which players are currently tracked"""
        server = ctx.message.server
        channel = ctx.message.channel
        user = ctx.message.author
        max_users = 30

        em = discord.Embed(colour=user.colour)
        em.set_author(name="osu! Players Currently Tracked in {}".format(server.name), icon_url = server.icon_url)
        channel_users = {}

        target_channel = None
        for track_user in db.track.find({}):
            if "servers" in track_user and server.id in track_user["servers"]:
                target_channel = find(lambda m: m.id == track_user['servers'][server.id]["channel"], server.channels)
                if target_channel.name not in channel_users:
                    channel_users[target_channel.name] = []


                if "options" in track_user['servers'][server.id]:
                    options = track_user['servers'][server.id]["options"]
                else:
                    options = None
                channel_users[target_channel.name].append((track_user['username'], options))

        if target_channel:
            display_num = min(max_users, len(channel_users[target_channel.name]))
        else:
            display_num = 0

        if target_channel:
            channel_users[target_channel.name] = sorted(channel_users[target_channel.name], key=operator.itemgetter(0))
            for channel_name in channel_users.keys():
                display_list = []
                for username, options in channel_users[channel_name][0:display_num]:
                    if options is not None:
                        display_list.append("{} [m:`{}` t:`{}`]".format(username, "|".join(map(str, options['gamemodes'])), str(options['plays'])))
                    else:
                        display_list.append("{} [m:`0` t:`50`]".format(username))

                msg_users = ", ".join(display_list)
                if display_num < len(channel_users[channel_name]):
                    msg_users += "..."
                em.add_field(name = "__#{} ({})__".format(channel_name, len(channel_users[channel_name])), value = msg_users)
        else:
            em.description = "None."
        await self.bot.say(embed = em)

    @commands.cooldown(1, 10, commands.BucketType.user)
    @osutrack.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def add(self, ctx, *usernames:str):
        """Adds a player to track for top scores.\n"""
        """-m (gamemodes) -t (top # plays)"""
        """osutrack add username1 username2 -m 03 -t 30"""
        server = ctx.message.server
        channel = ctx.message.channel

        key = self.api_keys["osu_api_key"]
        msg = ""
        count_add = 0
        count_update = 0

        if usernames == ():
            await self.bot.say("**Please enter a user (+ Parameters)! e.g. `Stevy -m 02 -t 20`**")
            return

        # gets options for tracking
        options, usernames = await self._get_options(usernames)
        if options == None:
            return

        for username in usernames:
            track_num = self._get_server_track_num(server)
            if track_num >= self.track_server_limit:
                await self.bot.say('**You are at or past the user tracking limit: `{}` Tracked.**'.format(str(track_num)))
                msg = "**Added `{}` users to tracking on `#{}`. {}**".format(count_add, channel.name,self._display_options(options))
                break

            #try:
            userinfo = list(await get_user(key, self.osu_settings["type"]["default"], username, 0))

            if not userinfo or len(userinfo) == 0:
                msg += "`{}` does not exist in the osu! database.\n".format(username)
            else:
                userinfo = userinfo[0]
                username = userinfo['username']
                osu_id = userinfo["user_id"]
                track_user = db.track.find_one({"osu_id":osu_id})
                track_user_username = db.track.find_one({"username":username})

                if not track_user:
                    # backwards compatibility
                    if track_user_username and not track_user:
                        print("Existing Create ID")
                        db.track.update_one({"username":username}, {'$set':{"osu_id":osu_id}})
                    else:
                        new_json = {}
                        new_json['username'] = username
                        new_json['osu_id'] = osu_id
                        new_json["servers"] = {}
                        new_json["servers"][server.id] = {}
                        new_json["servers"][server.id]["channel"] = channel.id
                        new_json["servers"][server.id]["options"] = options
                        # add current userinfo
                        new_json["userinfo"] = {}
                        for mode in modes:
                            new_json["userinfo"][mode] = list(await get_user(key, self.osu_settings["type"]["default"], osu_id, get_gamemode_number(mode), no_cache = True))[0]
                            self.total_requests += 1

                        # add last tracked time
                        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        new_json["last_check"] = current_time
                        db.track.insert_one(new_json)
                    count_add += 1
                    msg += "**`{}` added. Will now track on `#{}`. {}**\n".format(username, channel.name, self._display_options(options))
                else:
                    count_add += 1
                    if "servers" in track_user and server.id in track_user["servers"].keys():
                        track_user["servers"][server.id]["channel"] = channel.id
                        track_user["servers"][server.id]["options"] = options
                        db.track.update_one({"osu_id":osu_id}, {'$set':{
                            "servers.{}.channel".format(server.id):channel.id,
                            "servers.{}.options".format(server.id):options,
                            }})

                        msg += "**Updated tracking `{}` on `#{}`. {}**\n".format(username, channel.name, self._display_options(options))
                    else:
                        db.track.update_one({"osu_id":osu_id}, {'$set':{
                            "servers.{}.channel".format(server.id):channel.id,
                            "servers.{}.options".format(server.id):options,
                            }})
                        msg += "**`{}` now tracking on `#{}`. {}**\n".format(username, channel.name, self._display_options(options))
            #except:
                #pass
            await asyncio.sleep(self.sleep_time)

        if len(msg) > 500:
            await self.bot.say("**Added `{}` users to tracking on `#{}`. {}**".format(count_add, channel.name,self._display_options(options)))
        else:
            await self.bot.say(msg)

    def _get_server_track_num(self, server):
        """Reads database to see how many people are tracked on this server"""
        counter = 0
        target_channel = None
        for track_user in db.track.find({}):
            if "servers" in track_user and server.id in track_user["servers"]:
                counter += 1
        return counter

    def _display_options(self, options):
        msg = ""
        gamemodes_str = []
        for mode in options['gamemodes']:
            gamemodes_str.append(str(mode))

        msg += "(Modes: `{}`, Plays: `{}`)".format('|'.join(gamemodes_str), str(options['plays']))
        return msg

    @osutrack.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def clear(self, ctx):
        """Clear all tracked users from server."""
        server = ctx.message.server
        user = ctx.message.author

        await self.bot.say('**You are about to clear users tracked on this server. Confirm by typing `yes`.**')
        answer = await self.bot.wait_for_message(timeout=15, author=user)
        if answer is None:
            await self.bot.say('**Clear canceled.**')
        elif "yes" not in answer.content.lower():
            await self.bot.say('**No action taken.**')
        else:
            for username in db.track.find({}):
                servers = username['servers']
                if server.id in servers.keys():
                    del servers[server.id]
                    db.track.update_one({'username':username['username']}, {'$set': {'servers':servers}})
            await self.bot.say('**Users tracked on `{}` cleared.**'.format(server.name))

    # this needs serious refactoring.. why do i even use a tuple?
    async def _get_options(self, usernames:tuple):
        # option parser, these are default
        options = {"gamemodes": [0], "plays": 50}
        if '-m' in usernames:
            marker_loc = usernames.index('-m')
            # check if nothing after
            if len(usernames) - 1 == marker_loc:
                await self.bot.say("**Please provide a mode!**")
                return (None, usernames)

            modes = usernames[marker_loc + 1]
            if not modes.isdigit():
                await self.bot.say("**Please use only whole numbers for number of top plays!**")
                return (None, usernames)

            modes = list(modes)
            valid_modes = [0,1,2,3]
            final_modes = []
            # parse modes into strings
            for mode in modes:
                if int(mode) in valid_modes:
                    final_modes.append(int(mode))

            if not final_modes:
                await self.bot.say("**Please enter valid modes! e.g. `0123`**")
                return (None, usernames)

            final_modes = set(final_modes)
            options["gamemodes"] = sorted(list(final_modes))
            usernames = list(usernames)
            del usernames[marker_loc + 1]
            del usernames[marker_loc]
            usernames = tuple(usernames)

        if '-t' in usernames:
            marker_loc = usernames.index('-t')
            # check if nothing after
            if len(usernames) - 1 == marker_loc:
                await self.bot.say("**Please provide a number for top plays!**")
                return (None, usernames)

            top_num = usernames[marker_loc + 1]
            if top_num.isdigit():
                top_num = int(top_num)
            else:
                await self.bot.say("**Please provide an integer for top plays!**")
                return (None, usernames)

            if top_num > self.osu_settings['num_track'] or top_num < 1:
                await self.bot.say("**Please provide a valid number of plays! (1-{})**".format(self.osu_settings['num_track']))
                return (None, usernames)

            options["plays"] = top_num
            usernames = list(usernames)
            del usernames[marker_loc + 1]
            del usernames[marker_loc]
            usernames = tuple(usernames)

        if '-c' in usernames:
            if len(options["gamemodes"]) != 1:
                await self.bot.say("**You must specify a single gamemode for country tracking.**")
                return (None, usernames)

            marker_loc = usernames.index('-c')
            # check if nothing after
            if len(usernames) - 1 == marker_loc:
                await self.bot.say("**Please provide a 2-char country code or `global`**")
                return (None, usernames)

            country_code = str(usernames[marker_loc + 1]).upper()
            if len(country_code) != 2 and country_code != 'GLOBAL':
                await self.bot.say("**Please provide a 2-char country code or `global`**")
                return (None, usernames)

            usernames = list(usernames)
            del usernames[marker_loc + 1]
            del usernames[marker_loc]
            usernames = tuple(usernames)

            # default values
            if country_code == 'GLOBAL':
                num_top_players = 50
            else:
                num_top_players = 25

            if '-p' in usernames:
                marker_loc = usernames.index('-p')
                # check if nothing after
                if len(usernames) - 1 == marker_loc:
                    await self.bot.say("**Please provide a number for # of top players!**")
                    return (None, usernames)

                num_top_players = usernames[marker_loc + 1]
                if num_top_players.isdigit():
                    num_top_players = int(num_top_players)
                else:
                    await self.bot.say("**Please provide an integer for # of top players!**")
                    return (None, usernames)

                if (num_top_players > 50 and country_code != 'GLOBAL') or (num_top_players > 100 and country_code == 'GLOBAL') :
                    await self.bot.say("**Please provide a valid number of top players! Global Max: `100`, Country Max: `50`**")
                    return (None, usernames)

                usernames = list(usernames)
                del usernames[marker_loc + 1]
                del usernames[marker_loc]
                usernames = tuple(usernames)

            # append the appropriate user ids
            leaderboard_userids = await get_leaderboard(mode = options["gamemodes"][0], country_code = country_code, limit = num_top_players)
            # new usernames
            if not usernames:
                usernames = []
            else:
                usernames = list(usernames)

            # print(leaderboard_userids, len(leaderboard_userids), country_code, num_top_players, usernames)
            usernames = tuple(leaderboard_userids)
            await self.bot.say("Disclaimer: This is a static list!. Please give owo a moment...")

        return (options, usernames)

    @osutrack.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def remove(self, ctx, *usernames:str):
        """Removes a player to track for top scores."""
        server = ctx.message.server
        channel = ctx.message.channel
        msg = ""
        count_remove = 0

        if usernames == ():
            await self.bot.say("Please enter a user")
            return

        for username in usernames:
            user_find = db.track.find_one({"username":username})
            if user_find and "servers" in user_find and server.id in user_find["servers"]:
                if channel.id == user_find["servers"][server.id]["channel"]:
                    db.track.update_one({"username":username}, {"$unset":{"servers.{}".format(server.id):"channel"}})
                    msg+="**No longer tracking `{}` in `#{}`.**\n".format(username, channel.name)
                    count_remove += 1
                else:
                    msg+="**`{}` is not currently being tracked in `#{}`.**\n".format(username, channel.name)
            else:
                msg+="**`{}` is not currently being tracked.**\n".format(username)

        if len(msg) > 500:
            await self.bot.say("**Removed `{}` users from tracking on `#{}`.**".format(count_remove, channel.name))
        else:
            await self.bot.say(msg)

    @osutrack.command(pass_context=True, no_pm=True)
    @checks.is_owner()
    async def untrack(self, ctx, *usernames:str):
        """Removes a user from the database."""
        server = ctx.message.server
        channel = ctx.message.channel
        msg = ""
        count_remove = 0

        if answer is None:
            await self.bot.say('**Clear canceled.**')
        elif "yes" not in answer.content.lower():
            await self.bot.say('**No action taken.**')
        else:
            for username in db.track.find({}):
                servers = username['servers']
                if server.id in servers.keys():
                    del servers[server.id]
                    db.track.update_one({'username':username['username']}, {'$set': {'servers':servers}})
            await self.bot.say('**Users tracked on `{}` cleared.**'.format(server.name))

    # ------- play tracker ----------
    async def play_tracker(self):
        # tries to load x new people each time the bot boots up
        global api_counter
        # await self.remove_duplicates()
        # await self.create_suggestion_database()
        cycle = 0
        self.total_requests = await self._count_total_requests()

        while self == self.bot.get_cog('Tracking'):
            api_counter = 0
            total_tracking = db.track.count() # counts total number of players
            requests_per_user = self.total_requests/total_tracking # without recent (hardcoded)
            max_cycles_per_min = self.max_requests/requests_per_user
            self.cycle_time = total_tracking/max_cycles_per_min # minutes
            self.sleep_time = (self.cycle_time * 60) / total_tracking # in seconds
            print("Time Started. Projected Cycle Time: {} Rate: {}".format(str(self.cycle_time), str(self.max_requests)))

            current_time = datetime.datetime.now()
            loop = asyncio.get_event_loop()
            should_cache = False
            for player in db.track.find({}, no_cursor_timeout=True):

                if cycle % 10 == 0:
                    should_cache = True
                    cycle = 0

                loop.create_task(self.player_tracker(player, cache = should_cache))
                await asyncio.sleep(self.sleep_time)

            loop_time = datetime.datetime.now()
            elapsed_time = loop_time - current_time
            rate = api_counter/(elapsed_time.total_seconds()/60)
            print("Time Ended. Cycle Time: {} Rate: {} Requests: {}".format(str(elapsed_time), str(rate), str(api_counter)))

            if self.cycle_time*60 < 60:
                await asyncio.sleep(60 - self.cycle_time*60)
            else:
                pass
            cycle += 1

    async def remove_single_duplicate(self, username:str):
        player_find_count = db.track.find({"username":username}).count()
        if player_find_count == 2:
            db.track.delete_one({"username":username})
            print("Deleted One Instance of {}".format(username))
        elif player_find_count > 2:
            db.track.delete_many({"username":username})
            print("Deleted All Instances of {}".format(username))

    async def remove_duplicates(self):
        for player in db.track.find({}, no_cursor_timeout=True):
            player_find_count = db.track.find({"username":player['username']}).count()
            if player_find_count == 2:
                db.track.delete_one({"username":player['username']})
                print("Deleted One Instance of {}".format(player['username']))
            elif player_find_count > 2:
                db.track.delete_many({"username":player['username']})
                print("Deleted All Instances of {}".format(player['username']))

    async def _count_total_requests(self):
        total_requests = 0

        for player in db.track.find({}, no_cursor_timeout=True):
            max_gamemodes = 0
            for mode in modes:
                all_servers = player['servers'].keys()
                for server_id in all_servers:
                    try:
                        num_gamemodes = len(player['servers'][server_id]['options']['gamemodes'])
                    except:
                        num_gamemodes = 1 # precaution

                    max_gamemodes = max(num_gamemodes, max_gamemodes)
            total_requests += max_gamemodes

        print("There are currently a total of {} requests".format(total_requests))
        return total_requests

    async def _remove_bad_servers(self):
        if self.server_send_fail != [] and len(self.server_send_fail) <= 15: # arbitrary threshold in case discord api fails
            for player in db.track.find({}, no_cursor_timeout=True):
                all_servers = player['servers'].keys()
                for failed_server_id in self.server_send_fail:
                    if failed_server_id in all_servers:
                        del player['servers'][failed_server_id]
                        db.track.update_one({"username":player['username']}, {'$set':{"servers":player['servers']}})
                        find_test = db.track.find_one({"username":player['username']})
                        if failed_server_id in find_test['servers'].keys():
                            log.info("FAILED to delete Server {} from {}".format(failed_server_id, player['username']))
                        else:
                            log.info("Deleted Server {} from {}".format(failed_server_id, player['username']))
            self.server_send_fail = []

    # used to track top plays of specified users (someone please make this better c:)
    # Previous failed attempts include exponential blocking, using a single client session (unreliable),
    # threading/request to update info and then displaying separately, aiohttp to update and then displaying separately
    async def player_tracker(self, player, cache = False):
        key = self.api_keys["osu_api_key"]

        # purge, not implemented
        purge = True

        # get id, either should be the same, but one is backup
        if 'osu_id' in player:
            osu_id = player['osu_id']
        else:
            osu_id = player['userinfo']['osu']['user_id']

        # create last check just in case it doesn't exist
        if 'last_check' not in player:
            print("Creating Last Check for {}".format(player['username']))
            player['last_check'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.track.update_one({"username":player['username']}, {'$set':{"last_check":player['last_check']}})

        # ensures that data is recieved
        got_data = False
        get_data_counter = 1
        new_data = None

        new_data, required_modes = await self._fetch_new(osu_id, player["servers"]) # contains data for player

        # if still no data
        if new_data == None:
            print("Data fetched failed for {}".format(player['username']))
            return

        current_time = datetime.datetime.now()

        for mode in required_modes:

            gamemode_number = get_gamemode_number(mode)
            score_gamemode = get_gamemode_display(mode)
            try:
                best_plays = new_data["best"][mode] # single mode
                recent_play = new_data["recent"][mode] # not used yet

                # print(best_plays)
                best_timestamps = []
                for best_play in best_plays:
                    best_timestamps.append(best_play['date'])
            except:
                continue

            top_play_num_tracker = [] # used for pruning
            for i in range(len(best_timestamps)): # max 100
                last_top = player["last_check"]
                last_top_datetime = datetime.datetime.strptime(last_top, '%Y-%m-%d %H:%M:%S')
                best_datetime = datetime.datetime.strptime(best_timestamps[i], '%Y-%m-%d %H:%M:%S')

                if best_datetime > last_top_datetime: # and (current_time.timetuple().tm_yday - best_datetime.timetuple().tm_yday) <= 1: # could just use string...
                    purge = False # if there was a best, then continue
                    top_play_num = i+1
                    play = best_plays[i]
                    play_map = await get_beatmap(key, self.osu_settings["type"]["default"], play['beatmap_id'])
                    new_user_info = list(await get_user(key, self.osu_settings["type"]["default"], osu_id, gamemode_number, no_cache = True))

                    # ----- put into suggestion database -----
                    if gamemode_number == 0:
                        await self._append_suggestion_database(play)

                    if new_user_info != None and len(new_user_info) > 0 and new_user_info[0]['pp_raw'] != None:
                        new_user_info = new_user_info[0]
                    else:
                        print(player["username"] + "({})".format(osu_id) + " has not played enough.")
                        return

                    # send appropriate message to channel
                    if mode in player["userinfo"]:
                        old_user_info = player["userinfo"][mode]
                        em = await self._create_top_play(top_play_num, play, play_map, old_user_info, new_user_info, score_gamemode)
                    else:
                        old_user_info = None
                        em = await self._create_top_play(top_play_num, play, play_map, old_user_info, new_user_info, score_gamemode)

                    # display it to the player with info
                    all_servers = player['servers'].keys()
                    for server_id in all_servers:
                        try:
                            server = find(lambda m: m.id == server_id, self.bot.servers)
                            server_settings = db.osu_settings.find_one({"server_id": server_id})
                            if server and (not server_settings or "tracking" not in server_settings or server_settings["tracking"] == True):
                                server_player_info = player['servers'][server_id]
                                if 'options' in server_player_info:
                                    plays_option = server_player_info['options']['plays']
                                    gamemodes_option = server_player_info['options']['gamemodes']
                                if 'options' not in server_player_info or i <= plays_option and  gamemode_number in gamemodes_option:
                                    channel = find(lambda m: m.id == player['servers'][server_id]["channel"], server.channels)
                                    await self.bot.send_message(channel, embed = em)
                        except:
                            log.info("Failed to send to server {}".format(server_id))
                            if server_id not in self.server_send_fail:
                                self.server_send_fail.append(server_id)

                    # calculate latency
                    besttime = datetime.datetime.strptime(best_timestamps[i], '%Y-%m-%d %H:%M:%S')
                    oldlastcheck = datetime.datetime.strptime(last_top, '%Y-%m-%d %H:%M:%S')
                    delta = besttime.minute - oldlastcheck.minute

                    log.info("Created top {} {} play for {}({}) | {} {}".format(top_play_num, mode, new_user_info['username'], osu_id, str(besttime), str(oldlastcheck)))

                    # update userinfo for next use
                    player["last_check"] = best_timestamps[i]
                    player['userinfo'][mode] = new_user_info # already non-list

                    # save timestamp for most recent top score... should just go by id..
                    # update username
                    if player['username'] != new_user_info['username']:
                        print("Username updated from {} to {}".format(player['username'], new_user_info['username']))
                        db.track.update_one({"username":player['username']}, {'$set':{"username":new_user_info['username']}})
                        player['username'] = new_user_info['username']

                    # update top plays
                    player['userinfo'][mode] = new_user_info
                    player['userinfo'][mode]['best_plays'] = new_data['best'][mode]
                    db.track.update_one({"username":player['username']}, {'$set':{"userinfo":player['userinfo']}})
                    # db.track.update_one({"username":player['username']}, {'$set':{"userinfo.{}".format(mode):new_user_info}})
                    db.track.update_one({"username":player['username']}, {'$set':{"last_check":best_timestamps[i]}})

            # caching... everything, every 10 cycles... maybe better?
            try:
                if cache and new_data:
                    player['userinfo'][mode]['best_plays'] = new_data['best'][mode]
                    db.track.update_one({"username":player['username']}, {'$set':{"userinfo":player['userinfo']}})
                    # print("{} {} Cached".format(player['username'], mode))
            except:
                pass

            # remove duplicates if necessary
            await self.remove_single_duplicate(player['username'])

    async def _fetch_new(self, osu_id, player_servers):
        key = self.api_keys["osu_api_key"]
        new_data = {"best":{}, "recent":{}}

        required_modes = await self._get_required_modes(player_servers)
        # print(required_modes)

        for mode in required_modes:
            try:
                new_data["best"][mode] = await get_user_best(
                    key, self.osu_settings["type"]["default"], osu_id,
                    get_gamemode_number(mode), self.osu_settings["num_track"], no_cache = True)
                """new_data["recent"][mode] = await get_user_recent(
                    key, self.osu_settings["type"]["default"], osu_id,
                    get_gamemode_number(mode))""" # get recent, ahahahah yeah right.
                new_data["recent"][mode] = {}
            except:
                pass
        return new_data, required_modes


    async def _get_required_modes(self, player_servers):
        required_modes = []
        for server_id in player_servers.keys():
            server_player_info = player_servers[server_id]
            if 'options' in server_player_info:
                required_modes.extend(server_player_info['options']['gamemodes'])
            else: # if no option exists
                required_modes.extend([0])

        required_modes = list(set(required_modes))
        required_modes_txt = []
        for mode_num in required_modes:
            required_modes_txt.append(modes[mode_num])
        return required_modes_txt

    async def _create_top_play(self, top_play_num, play, beatmap, old_user_info, new_user_info, gamemode):
        beatmap_url = 'https://osu.ppy.sh/b/{}'.format(play['beatmap_id'])
        user_url = 'https://{}/u/{}'.format(self.osu_settings["type"]["default"], new_user_info['user_id'])
        profile_url = 'https://a.ppy.sh/{}'.format(new_user_info['user_id'])
        beatmap = beatmap[0]

        # get infomation
        m0, s0 = divmod(int(beatmap['total_length']), 60)
        mods = num_to_mod(play['enabled_mods'])
        em = discord.Embed(description='', colour=0xffa500)
        acc = calculate_acc(play, int(beatmap['mode']))

        # determine mods
        if not mods:
            mods = []
            mods.append('No Mod')
            oppai_output = None
        else:
            oppai_mods = "+{}".format("".join(mods))
            oppai_output = await get_pyoppai(beatmap['beatmap_id'], accs=[int(acc)], mods = int(play['enabled_mods']))

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
        em.set_thumbnail(url=map_image_url)
        em.set_author(name="New #{} for {} in {}".format(top_play_num, new_user_info['username'], gamemode), icon_url = profile_url, url = user_url)

        info = ""
        map_title = "{} [{}]".format(beatmap['title'], beatmap['version'])
        map_rank = None
        map_rank = await self.get_map_rank(new_user_info['user_id'], map_title)
        # print(map_rank) # just for debugging
        map_rank_str = ''
        if map_rank:
            map_rank_str = '▸ #{}'.format(str(map_rank))

        info += "▸ [**__{}__**]({}) {}                            \n".format(map_title, beatmap_url, map_rank_str)
        # calculate bpm and time... MUST clean up.
        if oppai_output and ('DT' in str(mods).upper() or 'HT' in str(mods).upper()):
            if 'DT' in str(mods):
                m1,s1,bpm1 = calc_time(beatmap['total_length'], beatmap['bpm'], 1.5)
            elif 'HT' in str(mods):
                m1,s1,bpm1 = calc_time(beatmap['total_length'], beatmap['bpm'], 2/3)

            star_str, _ = compare_val(beatmap['difficultyrating'], oppai_output, 'stars', dec_places = 2)
            info += "▸ **{}★** ▸ {}:{}({}:{}) ▸ {}({})bpm\n".format(
                star_str,
                m0, str(s0).zfill(2),
                m1, str(s1).zfill(2),
                beatmap['bpm'], bpm1)
        elif 'DT' in str(mods).upper() or 'HT' in str(mods).upper():
            if 'DT' in str(mods):
                m1,s1,bpm1 = calc_time(beatmap['total_length'], beatmap['bpm'], 1.5)
            elif 'HT' in str(mods):
                m1,s1,bpm1 = calc_time(beatmap['total_length'], beatmap['bpm'], 2/3)

            star_str, _ = compare_val(beatmap['difficultyrating'], oppai_output, 'stars', dec_places = 2)
            info += "▸ **{}★** ▸ {}:{}({}:{}) ▸ {}({})bpm\n".format(
                star_str,
                m0, str(s0).zfill(2),
                m1, str(s1).zfill(2),
                beatmap['bpm'], bpm1)
        else:
            stars_str, _ = compare_val(beatmap['difficultyrating'], oppai_output, 'stars', dec_places = 2)
            info += "▸ **{}★** ▸ {}:{} ▸ {}bpm\n".format(
                stars_str, m0, str(s0).zfill(2), beatmap['bpm'])
        try:
            if old_user_info != None:
                dpp = float(new_user_info['pp_raw']) - float(old_user_info['pp_raw'])
                if dpp == 0:
                    pp_gain = ""
                else:
                    pp_gain = "({:+.2f})".format(dpp)
                info += "▸ +{} ▸ **{:.2f}%** ▸ **{}** Rank ▸ **{:.2f} {}pp**\n".format(fix_mods(''.join(mods)),
                    float(acc), play['rank'], float(play['pp']), pp_gain)
                info += "▸ {} ▸ x{}/{} ▸ [{}/{}/{}/{}]\n".format(
                    play['score'], play['maxcombo'], beatmap['max_combo'],
                    play['count300'],play['count100'],play['count50'],play['countmiss'])
                info += "▸ #{} → #{} ({}#{} → #{})".format(
                    old_user_info['pp_rank'], new_user_info['pp_rank'],
                    new_user_info['country'],
                    old_user_info['pp_country_rank'], new_user_info['pp_country_rank'])
            else: # if first time playing
                info += "▸ +{} ▸ **{:.2f}%** ▸ **{}** Rank ▸ **{:.2f}pp**\n".format(
                    fix_mods(''.join(mods)), float(acc), play['rank'], float(play['pp']))
                info += "▸ {} ▸ x{}/{} ▸ [{}/{}/{}/{}]\n".format(
                    play['score'], play['maxcombo'], beatmap['max_combo'],
                    play['count300'],play['count100'],play['count50'],play['countmiss'])
                info += "▸ #{} ({}#{})".format(
                    new_user_info['pp_rank'],
                    new_user_info['country'],
                    new_user_info['pp_country_rank'])
        except:
            info += "Error"
        em.description = info

        time_ago_datetime = datetime.datetime.utcnow() + datetime.timedelta(hours=8) - datetime.datetime.strptime(play['date'], '%Y-%m-%d %H:%M:%S')
        self.latency.append(int(time_ago_datetime.total_seconds())) # keep track of how long it took
        await self.save_latency()

        timeago = time_ago(
            datetime.datetime.utcnow() + datetime.timedelta(hours=8),
            datetime.datetime.strptime(play['date'], '%Y-%m-%d %H:%M:%S'))
        em.set_footer(text = "{}Ago On osu! Official Server".format(timeago))
        return em

    # gets user map rank if less than 1000
    async def get_map_rank(self, osu_userid, title):
        try:
            ret = None
            url = 'https://osu.ppy.sh/users/{}'.format(osu_userid)
            soup = await get_web(url, parser = "lxml")
            find = soup.find('script',{"id": "json-user"})
            user = json.loads(find.get_text())

            for recent_play in user['recentActivities']:
                if title in recent_play['beatmap']['title']:
                    ret = int(recent_play['rank'])
                    break
            return ret
        except:
            return None

    # one_time, very beta (meirl)
    async def create_suggestion_database(self):
        self.total_requests = await self._count_total_requests()
        print("Appending Suggestion Database.")
        total_tracking = db.track.count() # around 1700 for owo
        requests_per_user = self.total_requests/total_tracking # without recent (hardcoded)
        max_cycles_per_min = self.max_requests/requests_per_user
        self.cycle_time = total_tracking/max_cycles_per_min # minutes
        self.sleep_time = (self.cycle_time * 60) / total_tracking # in seconds
        print('Sleep per user: ', self.sleep_time)

        current_time = datetime.datetime.now()
        loop = asyncio.get_event_loop()
        counter = 0
        bound_size = 0 # EDIT THIS VALUE
        start_index = randint(0, total_tracking - bound_size - 1)
        end_index = start_index + bound_size
        # force_list = ['124493', '4787150', '2558286', '1419095', '2614511', '2831793', '2003326','227717'] # EDIT THESE LISTS
        # force_list = ['1205412', '941094', '64501'] # ez/fl players
        # force_list = ['147515'] # random
        force_list = [] # empty
        for player in db.track.find({}, no_cursor_timeout=True):
            if 'osu_id' in player:
                osu_id = player['osu_id']
            else:
                osu_id = player['userinfo']['osu']['user_id']
            if (counter > start_index and counter <= end_index) or osu_id in force_list:
                loop.create_task(self.suggestion_play_parser(player))
                # await asyncio.sleep(self.sleep_time)
            counter += 1

        loop_time = datetime.datetime.now()
        elapsed_time = loop_time - current_time
        print("Time ended: " + str(elapsed_time))
        print("Suggestion Database Creation ENDED!!!. Took: {}".format(str(elapsed_time)))

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

    async def update_leaderboard():
        current_user_ids = [user['id'] for user in user_list]
        new_list = await get_leaderboard(mode = gamemode, country_code = country_code)
        sym_diff = set(current_user_ids).symmetric_difference(set(new_list))

        # replace only what's necessary
        for ids in sym_diff:
            # remove indices !!!!!!!!!!!!11
            pass
