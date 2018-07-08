import asyncio
import collections
import json
import math
import os
import re
import urllib

import aiohttp
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from matplotlib import ticker

import pyoppai
from data.osu.oppai_chunks import oppai
from pippy.beatmap import Beatmap

from .common import *


async def get_leaderboard(mode = 0, country_code = None, limit = 50):
    users_per_page = 50
    pages = round(limit/50 + .5)
    urls = []
    player_id_list = []
    for i in range(pages):
        country = ''
        if country_code is not None and country_code != 'GLOBAL':
            country = 'country={}&'.format(str(country_code).upper())
        url = 'https://osu.ppy.sh/rankings/{}/performance?{}page={}#jump-target'.format(modes2[mode], country, i+1)

        soup = await get_web(url)
        span_tags = list(soup.findAll('span'))

        for tag in span_tags:
            try:
                if tag['data-user-id']:
                    # username tag.text.replace('\n','')
                    player_id_list.append(tag['data-user-id'])
            except:
                pass

    return player_id_list[:limit]

async def get_top_cc(pages = 1):
    """Get country codes for top 50"""
    target_base = 'https://osu.ppy.sh/rankings/osu/performance?country='

    for i in range(pages):
        url = 'https://osu.ppy.sh/rankings/osu/country?page={}#jump-target'.format(i)
        soup = await get_web(url)
        a_tags = list(soup.findAll('a'))

        cc = []
        for tag in a_tags:
            try:
                if target_base in tag['href']:
                    # username tag.text.replace('\n','')
                    cc.append(tag['href'].replace(target_base, '').upper())
            except:
                pass

    print(cc)
    return cc

# returns an osu-related url from google
async def get_google_search(search_terms:str, include_title = False):
    search_limit = 10
    option = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}

    regex = [
            re.compile(",\"ou\":\"([^`]*?)\""),
            re.compile("<h3 class=\"r\"><a href=\"\/url\?url=([^`]*?)&amp;"),
            re.compile("<h3 class=\"r\"><a href=\"([^`]*?)\""),
            re.compile("\/url?url=")
        ]

    url = "https://www.google.com/search?hl=en&q="
    encode = urllib.parse.quote_plus(search_terms, encoding='utf-8',
                                     errors='replace')
    uir = url + encode
    async with aiohttp.request('GET', uir, headers=option) as resp:
        test = str(await resp.content.read())
        query_find = regex[1].findall(test)
        if not query_find:
            query_find = regex[2].findall(test)
            try:
                query_find = query_find[:search_limit]
            except IndexError:
                return []
        elif regex[3].search(query_find[0]):
            query_find = query_find[:search_limit]
        else:
            query_find = query_find[:search_limit]

    final_list = []
    for link in query_find:
        if 'osu.ppy.sh/' in link:
            final_list.append(link)

    return final_list

async def get_web(url, parser = 'html.parser'):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.read()

            return BeautifulSoup(text.decode('utf-8'), parser)

# Gets the beatmap
async def get_beatmap(key, api:str, beatmap_id, session = None, no_cache = False):
    if not no_cache:
        beatmap = await get_beatmap_db(beatmap_id)
        if beatmap:
            return beatmap

    url_params = []
    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("b", beatmap_id))
    url = build_request(url_params, "https://{}/api/get_beatmaps?".format(api))
    beatmap = await fetch(url, session)
    await cache_beatmap(beatmap)
    return beatmap

# Gets the beatmap set
async def get_beatmapset(key, api:str, set_id, session = None):
    url_params = []
    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("s", set_id))
    url = build_request(url_params, "https://{}/api/get_beatmaps?".format(api))
    return await fetch(url, session)

# Grabs the scores
async def get_scores(key, api:str, beatmap_id, user_id, mode, session = None):
    url_params = []
    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("b", beatmap_id))
    url_params.append(parameterize_id("u", user_id))
    url_params.append(parameterize_mode(mode))
    url = build_request(url_params, "https://{}/api/get_scores?".format(api))
    return await fetch(url, session)

async def get_user(key, api:str, user_id, mode, session = None, no_cache = False):
    if not no_cache:
        userinfo = await get_user_db(user_id, mode)
        if userinfo:
            return userinfo

    url_params = []
    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("u", user_id))
    url_params.append(parameterize_mode(mode))
    url = build_request(url_params, "https://{}/api/get_user?".format(api))
    return await fetch(url, session)

async def get_user_best(key, api:str, user_id, mode, limit, session = None, no_cache = False):
    if not no_cache:
        userbest = await get_user_best_db(user_id, mode, limit)
        if userbest:
            return userbest

    url_params = []
    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("u", user_id))
    url_params.append(parameterize_mode(mode))
    url_params.append(parameterize_limit(limit))
    url = build_request(url_params, "https://{}/api/get_user_best?".format(api))
    return await fetch(url, session)

# Returns the user's ten most recent plays.
async def get_user_recent(key, api:str, user_id, mode, session = None):
    url_params = []

    url_params.append(parameterize_key(key))
    url_params.append(parameterize_id("u", user_id))
    url_params.append(parameterize_mode(mode))
    url = build_request(url_params, "https://{}/api/get_user_recent?".format(api))
    return await fetch(url, session)

async def fetch(url, session):
    global api_counter
    counter = 0
    while (counter < 5):
        try:
            api_counter += 1
            if session == None:
                async with aiohttp.get(url) as resp:
                    return await resp.json()
            else:
                async with session.get(url) as resp:
                    return await resp.json()
        except:
            counter += 1
            await asyncio.sleep(0.06)

    print("Fetch Failed")
    return None

async def get_beatmap_db(beatmap_id):
    beatmap_id_list = db.beatmap_cache.find_one({'type': 'list'})
    if beatmap_id_list:
        beatmap_id_list = beatmap_id_list['ids']

        if beatmap_id in beatmap_id_list:
            index = beatmap_id_list.index(beatmap_id)
            beatmap_cache = db.beatmap_cache.find_one({'type': 'maps'})
            beatmap_cache = beatmap_cache['maps']
            beatmap = beatmap_cache[index]
            print('Using cached info for {}'.format(beatmap['beatmap_id']))
            return [beatmap]

    return None

async def get_user_db(user_id, mode):
    cached_info_userid = db.track.find_one({'osu_id':user_id})
    cached_info_username = db.track.find_one({'username':user_id})
    for cache_type, data in [('ID', cached_info_userid), ('USERNAME', cached_info_username)]:
        if data:
            try:
                print('{} Using cached info for {}'.format(cache_type, user_id))
                return [data['userinfo'][modes[mode]]]
            except:
                print('Cached data for {} does not exist yet!'.format(user_id))

    return None

async def get_user_best_db(user_id, mode, limit):
    try:
        cached_info_userid = db.track.find_one({'osu_id':user_id})
        cached_info_username = db.track.find_one({'username':user_id})
        for cache_type, data in [('ID', cached_info_userid), ('USERNAME', cached_info_username)]:
            if data:
                print('{} Using cached info for {}'.format(cache_type, user_id))
                return data['userinfo'][modes[mode]]['best_plays'][:limit]
    except:
        print('Cached data for {} does not exist yet!'.format(user_id))
        return None

async def cache_beatmap(beatmaps):
    cache_maxlen = 1000

    for beatmap in beatmaps:
        # cache only ranked, approved
        if int(beatmap['approved']) in [1,2,4]:
            beatmap_id_list = db.beatmap_cache.find_one({'type': 'list'})
            if not beatmap_id_list:
                new_list = {'type': 'list', 'ids': []}
                db.beatmap_cache.insert_one(new_list)

            beatmap_id_list = db.beatmap_cache.find_one({'type': 'maps'})
            if not beatmap_id_list:
                new_list = {'type': 'maps', 'maps': []}
                db.beatmap_cache.insert_one(new_list)

            beatmap_id_list = db.beatmap_cache.find_one({'type': 'list'})
            beatmap_id_list = collections.deque(beatmap_id_list['ids'], maxlen = cache_maxlen)

            if beatmap['beatmap_id'] not in beatmap_id_list:
                beatmap_map_list = db.beatmap_cache.find_one({'type': 'maps'})
                beatmap_map_list = collections.deque(beatmap_map_list['maps'], maxlen = cache_maxlen)

                # append new beatmap id
                beatmap_id_list.append(beatmap['beatmap_id'])
                # append new beatmap
                beatmap_map_list.append(beatmap)

                db.beatmap_cache.update_one({"type":'list'}, {'$set':{
                    'ids': list(beatmap_id_list)
                }})

                db.beatmap_cache.update_one({"type":'maps'}, {'$set':{
                    'maps': list(beatmap_map_list)
                }})

                print('Beatmap {} Cached'.format(beatmap['beatmap_id']))

# Written by Jams
async def get_pyoppai(map_id:str, accs=[100], mods=0, misses=0, combo=None, completion=None, fc=None, plot = False, imgur = None):
    url = 'https://osu.ppy.sh/osu/{}'.format(map_id)

    # try:
    ctx = pyoppai.new_ctx()
    b = pyoppai.new_beatmap(ctx)

    BUFSIZE = 2000000
    buf = pyoppai.new_buffer(BUFSIZE)

    file_path = 'data/osu/temp/{}.osu'.format(map_id) # some unique filepath
    await download_file(url, file_path) # this is the file name that it downloaded
    pyoppai.parse(file_path, b, buf, BUFSIZE, True, 'data/osu/cache/')
    dctx = pyoppai.new_d_calc_ctx(ctx)
    pyoppai.apply_mods(b, mods)

    stars, aim, speed, _, _, _, _ = pyoppai.d_calc(dctx, b)
    cs, od, ar, hp = pyoppai.stats(b)

    if not combo:
        combo = pyoppai.max_combo(b)

    total_pp_list = []
    aim_pp_list = []
    speed_pp_list = []
    acc_pp_list = []

    for acc in accs:
        accurracy, pp, aim_pp, speed_pp, acc_pp = pyoppai.pp_calc_acc(ctx, aim, speed, b, acc, mods, combo, misses)
        total_pp_list.append(pp)
        aim_pp_list.append(aim_pp)
        speed_pp_list.append(speed_pp)
        acc_pp_list.append(acc_pp)

    if fc:
        _, fc_pp, _, _, _ = pyoppai.pp_calc_acc(ctx, aim, speed, b, fc, mods, pyoppai.max_combo(b), 0)
        total_pp_list.append(fc_pp)

    pyoppai_json = {
        'version': pyoppai.version(b),
        'title': pyoppai.title(b),
        'artist': pyoppai.artist(b),
        'creator': pyoppai.creator(b),
        'combo': combo,
        'misses': misses,
        'max_combo': pyoppai.max_combo(b),
        'mode': pyoppai.mode(b),
        'num_objects': pyoppai.num_objects(b),
        'num_circles': pyoppai.num_circles(b),
        'num_sliders': pyoppai.num_sliders(b),
        'num_spinners': pyoppai.num_spinners(b),
        'stars': stars,
        'aim_stars': aim,
        'speed_stars': speed,
        'pp': total_pp_list, # list
        'aim_pp': aim_pp_list,
        'speed_pp': speed_pp_list,
        'acc_pp': acc_pp_list,
        'acc': accs, # list
        'cs': cs,
        'od': od,
        'ar': ar,
        'hp': hp
        }

    if completion:
        try:
            pyoppai_json['map_completion'] = await _map_completion(file_path, int(completion))
        except:
            pass

    if plot:
        pyoppai_json['graph_url'] = await plot_map_stars(file_path, mods, imgur)
        print(pyoppai_json['graph_url'])

    os.remove(file_path)
    return pyoppai_json
    #except:
        #return None

async def _get_taiko_pp(stars:float, od:float, max_combo:int, accs = [100], misses = 0, mods = []):
    od = float(od)
    stars = float(stars)
    max_combo = int(max_combo)

    strain_value = ((max(1, float(stars)/0.0075) * 5 - 4)**2)/100000
    user_combo = max_combo - misses
    length_bonus = min(1, max_combo/1500) * 0.1 + 1
    strain_value *= length_bonus
    strain_value *= 0.985**misses
    strain_value *= min(user_combo**0.5 / max_combo**0.5, 1)

    # scaling values for some mods
    if "EZ" in mods:
        od /= 2
    if "HR" in mods:
        od *= 1.4
    od = max(min(od, 10), 0)
    max_val = 20
    min_val = 50
    result = min_val + (max_val - min_val) * od / 10
    result = math.floor(result) - 0.5
    if "HT" in mods:
        result /= 0.75
    if "DT" in mods:
        result /= 1.5
    od = round(result * 100) / 100

    pp_values = []
    for acc in accs:
        acc_strainValue = strain_value*(acc/100)

        acc_value = (150/od)**1.1 * ((acc/100)**15) * 22
        acc_value *= min((max_combo/1500)**0.3, 1.15)

        mod_multiplier = 1.10
        if "HD" in mods:
            mod_multiplier *= 1.10
            acc_strainValue *= 1.025
        if "SO" in mods:
            mod_multiplier *= 0.95
        if "NF" in mods:
            mod_multiplier *= 0.90
        if "FL" in mods:
            acc_strainValue *= 1.05 * length_bonus

        total_value = (acc_strainValue**1.1 + acc_value**1.1)**(1.0/1.1) * mod_multiplier
        pp_values.append(round(total_value*100)/100)

    return pp_values

async def _get_mania_pp(stars:float, od:float, max_combo:int, score = None, accs = [100], mods = []):
    stars = float(stars)
    od = float(od)
    max_combo = int(max_combo)

    # score multiplier
    scoreMultiplier = 1
    od_multiplier = 1
    if "EZ" in mods:
        scoreMultiplier *= 0.5
        od_multiplier = 0.5
    if "NF" in mods:
        scoreMultiplier *= 0.5
    if "HT" in mods:
        scoreMultiplier *= 0.5

    # mod multiplier
    modMultiplier = 1.10
    if "NF" in mods:
        modMultiplier *= 0.90
    if "SO" in mods:
        modMultiplier *= 0.95
    if "EZ" in mods:
        modMultiplier *= 0.50

    od *= od_multiplier

    # for each acc
    pp_values = []
    for acc in accs:
        # print(max_combo, acc)
        if score is None:
            score = 1000000 * (acc/100)

        score *= scoreMultiplier

        # compute strain
        if scoreMultiplier <= 0:
            strainValue = 0
            return
        score *= (1 / scoreMultiplier)

        # star scaling
        star_scaling_factor = 0.018
        # print(stars, star_scaling_factor)
        starRate = float(stars) * star_scaling_factor
        strainValue = (((5 * max(1, starRate / 0.0825) - 4) ** 3) / 110000) * (1 + 0.1 * min(1, max_combo / 1500))

        # accValue computation
        hitWindow300 = 34 + 3 * min(10, max(0, 10.0 - float(od)))
        if hitWindow300 <= 0:
            accValue = 0
        else:
            accValue = (((150 / hitWindow300) * ((acc/100)**16))**1.8) * 2.5 * (min(1.15, ((max_combo / 1500)**0.3)))

        if score <= 500000:
            strainValue *= ((score / 500000) * 0.1)
        elif score <= 600000:
            strainValue *= (0.1 + (score - 500000) / 100000 * 0.2)
        elif score <= 700000:
            strainValue *= (0.3 + (score - 600000) / 100000 * 0.35)
        elif score <= 800000:
            strainValue *= (0.65 + (score - 700000) / 100000 * 0.20)
        elif score <= 900000:
            strainValue *=  (0.85 + (score - 800000) / 100000 * 0.1)
        else:
            strainValue *=  (0.95 + (score - 900000) / 100000 * 0.05)

        pp_values.append((((strainValue**1.1) + (accValue** 1.1))** (1 / 1.1)) * modMultiplier)

    return pp_values

async def _get_ctb_pp(stars, ar, max_combo, player_combo = None, accs = [100], misses = 0, mods = []):
    # requires accurate stars for particular mod DT/HT/HR/EZ
    # also takes original ar WITHOUT DT

    # modify ar for dt
    ar = float(ar)
    stars = float(stars)
    max_combo = int(float(max_combo))

    if "DT" in mods:
        if ar > 5:
            ms = 200 + (11-ar) * 100
        else:
            ms = 800 + (5-ar) * 80

        if ms < 300:
            ar = 11
        elif ms < 1200:
            ar = round((11-(ms-300)/150)*100)/100
        else:
            ar = round((5-(ms-1200)/120)*100)/100

    # input filters
    if not player_combo:
        player_combo = max_combo
    if ar > 11:
        ar = 11

    final = (((5*(stars)/ 0.0049)-4)**2)/100000;
    if max_combo > 3000:
        lb_constant = math.log10(max_combo / 3000.0)
    else:
        lb_constant = 0
    length_bonus = (0.95 + 0.4 * min(1, max_combo / 3000.0) + lb_constant)
    final *= length_bonus
    final *= (0.97**misses)
    final *= (player_combo/max_combo)**0.8
    # ar bonus
    if ar > 9:
        final *= 1+  0.1 * (ar - 9.0)
    if ar < 8:
        final *= 1+  0.025 * (8.0 - ar)

    pp_values = []
    for acc in accs:
        # acc Penalty
        pre_acc_final = final
        pre_acc_final *=  (acc/100) ** 5.5
        post_acc_final = pre_acc_final
        if "FL" in mods and "HD" in mods:
            final_pp = round(100 * post_acc_final * 1.35 * length_bonus*(1.05 + 0.075 * (10.0 - min(10, ar))))/100 #HDFL
        elif "HD" in mods:
            final_pp = round(100 * post_acc_final * (1.05 + 0.075 * (10.0 - min(10, ar))))/100; # HD
        elif "FL" in mods:
            final_pp = round(100 * post_acc_final * 1.35 * length_bonus)/100  # FL
        else:
            final_pp = round(100 * post_acc_final)/100
        pp_values.append(final_pp)

    return pp_values

# asynchronously download the file
async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            with open(filename, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return await response.release()

# Returns url to uploaded stars graph
async def plot_map_stars(beatmap, mods, imgur):
    #try:
    star_list, speed_list, aim_list, time_list = [], [], [], []
    #results = oppai(beatmap, mods=mods)
    print('beatmap: {}'.format(beatmap))
    results = oppai(beatmap)
    print('results: {}'.format(json.dumps(results, indent=4, sort_keys=True)))
    for chunk in results:
        print('chunk[time]: {}'.format(chunk['time']))
        time_list.append(chunk['time'])
        star_list.append(chunk['stars'])
        aim_list.append(chunk['aim_stars'])
        speed_list.append(chunk['speed_stars'])
    plt.figure(figsize=(10, 5))
    plt.style.use('ggplot')
    plt.plot(time_list, star_list, color='blue', label='Stars', linewidth=3.0)
    plt.plot(time_list, aim_list, color='red', label='Aim Stars', linewidth=3.0)
    plt.plot(time_list, speed_list, color='green', label='Speed Stars', linewidth=3.0)
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(plot_time_format))
    plt.ylabel('Stars')
    plt.legend(loc='best')
    plt.tight_layout()
    filepath = "{}.png".format(beatmap)
    plt.savefig(filepath)
    plt.close()
    print(imgur.credits['ClientRemaining'])
    if int(imgur.credits['ClientRemaining']) < 50:
        return 'http://i.imgur.com/iOA0QMA.png'

    pfile = imgur.upload_from_path(filepath)
    os.remove(filepath)
    return pfile['link']
    #except:
        #return 'http://i.imgur.com/iOA0QMA.png'

def plot_time_format(time, pos=None):
    s, mili = divmod(time, 1000)
    m, s = divmod(s, 60)
    return "%d:%02d" % (m, s)

async def _map_completion(btmap, totalhits=0):
    btmap = open(btmap, 'r').read()
    btmap = Beatmap(btmap)
    good = btmap.parse()
    if not good:
        raise ValueError("Beatmap verify failed. "
                         "Either beatmap is not for osu! standart, or it's malformed")
        return
    hitobj = []
    if totalhits == 0:
        totalhits = len(btmap.hit_objects)
    numobj = totalhits - 1
    num = len(btmap.hit_objects)
    for objects in btmap.hit_objects:
        hitobj.append(objects.time)
    timing = int(hitobj[num - 1]) - int(hitobj[0])
    point = int(hitobj[numobj]) - int(hitobj[0])
    map_completion = (point / timing) * 100
    return map_completion

# Returns the full API request URL using the provided base URL and parameters.
def build_request(url_params, url):
    for param in url_params:
        url += str(param)
        if (param != ""):
            url += "&"
    return url[:-1]

def parameterize_event_days(event_days):
    if (event_days == ""):
        event_days = "event_days=1"
    elif (int(event_days) >= 1 and int(event_days) <= 31):
        event_days = "event_days=" + str(event_days)
    else:
        print("Invalid Event Days")
    return event_days

def parameterize_id(t, id):
    if (t != "b" and t != "s" and t != "u" and t != "mp"):
        print("Invalid Type")
    if (len(str(id)) != 0):
        return t + "=" + str(id)
    else:
        return ""

def parameterize_key(key):
    if (len(key) == 40):
        return "k=" + key
    else:
        print("Invalid Key")

def parameterize_limit(limit):
    ## Default case: 10 scores
    if (limit == ""):
        limit = "limit=10"
    elif (int(limit) >= 1 and int(limit) <= 100):
        limit = "limit=" + str(limit)
    else:
        print("Invalid Limit")
    return limit

def parameterize_mode(mode):
    ## Default case: 0 (osu!)
    if (mode == ""):
        mode = "m=0"
    elif (int(mode) >= 0 and int(mode) <= 3):
        mode = "m=" + str(mode)
    else:
        print("Invalid Mode")
    return mode
