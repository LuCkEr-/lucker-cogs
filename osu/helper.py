import datetime
from difflib import SequenceMatcher


# because you people just won't stop bothering me about it
def fix_mods(mods:str):
    if mods == 'PFSOFLNCHTRXDTSDHRHDEZNF':
        return '? KEY'
    else:
        return mods.replace('DTHRHD', 'HDHRDT').replace('DTHD','HDDT').replace('HRHD', 'HDHR')

def get_gamemode(gamemode:int):
    if gamemode == 1:
        gamemode_text = "Taiko"
    elif gamemode == 2:
        gamemode_text = "Catch the Beat!"
    elif gamemode == 3:
        gamemode_text = "osu! Mania"
    else:
        gamemode_text = "osu! Standard"
    return gamemode_text

def get_gamemode_display(gamemode):
    if gamemode == "osu":
        gamemode_text = "osu! Standard"
    elif gamemode == "ctb":
        gamemode_text = "Catch the Beat!"
    elif gamemode == "mania":
        gamemode_text = "osu! Mania"
    elif gamemode == "taiko":
        gamemode_text = "Taiko"
    return gamemode_text

def get_gamemode_number(gamemode:str):
    if gamemode == "taiko":
        gamemode_text = 1
    elif gamemode == "ctb":
        gamemode_text = 2
    elif gamemode == "mania":
        gamemode_text = 3
    else:
        gamemode_text = 0
    return int(gamemode_text)

def calculate_acc(beatmap, gamemode:int):
    if gamemode == 0:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *=300
        user_score = float(beatmap['count300']) * 300.0
        user_score += float(beatmap['count100']) * 100.0
        user_score += float(beatmap['count50']) * 50.0
    elif gamemode == 1:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *= 300
        user_score = float(beatmap['count300']) * 1.0
        user_score += float(beatmap['count100']) * 0.5
        user_score *= 300
    elif gamemode == 2:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score += float(beatmap['countkatu'])
        user_score = float(beatmap['count300'])
        user_score += float(beatmap['count100'])
        user_score  += float(beatmap['count50'])
    elif gamemode == 3:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['countgeki'])
        total_unscale_score += float(beatmap['countkatu'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *=300
        user_score = float(beatmap['count300']) * 300.0
        user_score += float(beatmap['countgeki']) * 300.0
        user_score += float(beatmap['countkatu']) * 200.0
        user_score += float(beatmap['count100']) * 100.0
        user_score += float(beatmap['count50']) * 50.0

    return (float(user_score)/float(total_unscale_score)) * 100.0

def no_choke_acc(beatmap, gamemode:int):
    if gamemode == 0:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *=300
        user_score = float(beatmap['count300']) * 300.0
        user_score += (float(beatmap['count100']) + float(beatmap['countmiss'])) * 100.0
        user_score += float(beatmap['count50']) * 50.0
    elif gamemode == 1:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *= 300
        user_score = float(beatmap['count300']) * 1.0
        user_score += (float(beatmap['count100']) + float(beatmap['countmiss'])) * 0.5
        user_score *= 300
    elif gamemode == 2:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score += float(beatmap['countkatu'])
        user_score = float(beatmap['count300'])
        user_score += (float(beatmap['count100']) + float(beatmap['countmiss']))
        user_score  += float(beatmap['count50'])
    elif gamemode == 3:
        total_unscale_score = float(beatmap['count300'])
        total_unscale_score += float(beatmap['countgeki'])
        total_unscale_score += float(beatmap['countkatu'])
        total_unscale_score += float(beatmap['count100'])
        total_unscale_score += float(beatmap['count50'])
        total_unscale_score += float(beatmap['countmiss'])
        total_unscale_score *=300
        user_score = float(beatmap['count300']) * 300.0
        user_score += float(beatmap['countgeki']) * 300.0
        user_score += float(beatmap['countkatu']) * 200.0
        user_score += (float(beatmap['count100']) + float(beatmap['countmiss'])) * 100.0
        user_score += float(beatmap['count50']) * 50.0

    return (float(user_score)/float(total_unscale_score)) * 100.0

# gives a list of the ranked mods given a peppy number lol
def num_to_mod(number):
    """This is the way pyttanko does it.
    Just as an actual bitwise instead of list.
    Deal with it."""
    number = int(number)
    mod_list = []

    if number & 1<<0:   mod_list.append('NF')
    if number & 1<<1:   mod_list.append('EZ')
    if number & 1<<3:   mod_list.append('HD')
    if number & 1<<4:   mod_list.append('HR')
    if number & 1<<5:   mod_list.append('SD')
    if number & 1<<9:   mod_list.append('NC')
    elif number & 1<<6: mod_list.append('DT')
    if number & 1<<7:   mod_list.append('RX')
    if number & 1<<8:   mod_list.append('HT')
    if number & 1<<10:  mod_list.append('FL')
    if number & 1<<12:  mod_list.append('SO')
    if number & 1<<14:  mod_list.append('PF')
    if number & 1<<15:  mod_list.append('4 KEY')
    if number & 1<<16:  mod_list.append('5 KEY')
    if number & 1<<17:  mod_list.append('6 KEY')
    if number & 1<<18:  mod_list.append('7 KEY')
    if number & 1<<19:  mod_list.append('8 KEY')
    if number & 1<<20:  mod_list.append('FI')
    if number & 1<<24:  mod_list.append('9 KEY')
    if number & 1<<25:  mod_list.append('10 KEY')
    if number & 1<<26:  mod_list.append('1 KEY')
    if number & 1<<27:  mod_list.append('3 KEY')
    if number & 1<<28:  mod_list.append('2 KEY')

    return mod_list


def mod_to_num(mods:str):
    """It works."""
    mods = mods.upper()
    total = 0

    if 'NF' in mods:    total += 1<<0
    if 'EZ' in mods:    total += 1<<1
    if 'HD' in mods:    total += 1<<3
    if 'HR' in mods:    total += 1<<4
    if 'SD' in mods:    total += 1<<5
    if 'DT' in mods:    total += 1<<6
    if 'RX' in mods:    total += 1<<7
    if 'HT' in mods:    total += 1<<8
    if 'NC' in mods:    total += 1<<9
    if 'FL' in mods:    total += 1<<10
    if 'SO' in mods:    total += 1<<12
    if 'PF' in mods:    total += 1<<14
    if '4 KEY' in mods: total += 1<<15
    if '5 KEY' in mods: total += 1<<16
    if '6 KEY' in mods: total += 1<<17
    if '7 KEY' in mods: total += 1<<18
    if '8 KEY' in mods: total += 1<<19
    if 'FI' in mods:    total += 1<<20
    if '9 KEY' in mods: total += 1<<24
    if '10 KEY'in mods: total += 1<<25
    if '1 KEY' in mods: total += 1<<26
    if '3 KEY' in mods: total += 1<<27
    if '2 KEY' in mods: total += 1<<28

    return int(total)

def get_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def compare_val(map_stat, omap, param, dec_places:int = 1, single = False):
    if not omap:
        if dec_places == 0:
            return "{}".format(int(float(map_stat))), int(float(map_stat))
        return "{}".format(round(float(map_stat), dec_places)), round(float(map_stat), dec_places)
    elif omap and not map_stat:
        if dec_places == 0:
            return "{}".format(int(float(omap[param]))), int(float(omap[param]))
        return "{}".format(round(float(omap[param]), dec_places)), round(float(omap[param]), dec_places)
    else:
        map_stat = float(map_stat)
        op_stat = float(omap[param])
        if int(round(op_stat, dec_places)) != 0 and abs(round(map_stat, dec_places) - round(op_stat, dec_places)) > 0.05:
            if single:
                if dec_places == 0:
                    return "{}".format(int(float(op_stat))), int(float(op_stat))
                return "{}".format(round(op_stat, dec_places)), round(op_stat, dec_places)
            else:
                if dec_places == 0:
                    return "{}({})".format(int(float(map_stat)), int(float(op_stat))), int(float(op_stat))
                return "{}({})".format(round(map_stat, dec_places),
                    round(op_stat, dec_places)), round(op_stat, dec_places)
        else:
            if dec_places == 0:
                return "{}".format(int(float(map_stat))), int(float(map_stat))
            return "{}".format(round(map_stat, dec_places)), round(map_stat, dec_places)

def determine_pp_range(pp, range_of_pp = 30):
    nearest_range = int(range_of_pp * round(float(pp)/range_of_pp))

    upper_bound = 0
    lower_bound = 0
    if (nearest_range - pp) > 0:
        lower_bound = nearest_range - range_of_pp
        upper_bound = nearest_range - 1
    else:
        lower_bound = nearest_range
        upper_bound = nearest_range + range_of_pp - 1

    return "{}_{}".format(lower_bound, upper_bound)

def calc_time(total_sec, bpm, factor:float=1):
    m1, s1 = divmod(round(float(total_sec)/factor), 60)
    bpm1 = round(factor*float(bpm), 1)
    return (m1,s1,bpm1)

def time_ago(time1, time2):
    time_diff = time1 - time2
    timeago = datetime.datetime(1,1,1) + time_diff
    time_limit = 0
    time_ago = ""
    if timeago.year-1 != 0:
        time_ago += "{} Year{} ".format(timeago.year-1, determine_plural(timeago.year-1))
        time_limit = time_limit + 1
    if timeago.month-1 !=0:
        time_ago += "{} Month{} ".format(timeago.month-1, determine_plural(timeago.month-1))
        time_limit = time_limit + 1
    if timeago.day-1 !=0 and not time_limit == 2:
        time_ago += "{} Day{} ".format(timeago.day-1, determine_plural(timeago.day-1))
        time_limit = time_limit + 1
    if timeago.hour != 0 and not time_limit == 2:
        time_ago += "{} Hour{} ".format(timeago.hour, determine_plural(timeago.hour))
        time_limit = time_limit + 1
    if timeago.minute != 0 and not time_limit == 2:
        time_ago += "{} Minute{} ".format(timeago.minute, determine_plural(timeago.minute))
        time_limit = time_limit + 1
    if not time_limit == 2:
        time_ago += "{} Second{} ".format(timeago.second, determine_plural(timeago.second))
    return time_ago

# really stevy? yes, really.
def determine_plural(number):
    if int(number) != 1:
        return 's'
    else:
        return ''
