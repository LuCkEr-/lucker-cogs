import asyncio

from .osu import Osu
from .tracking import Tracking


def check_folders():
    if not os.path.exists("data/osu"):
        print("Creating data/osu folder...")
        os.makedirs("data/osu")
    if not os.path.exists("data/osu/cache"):
        print("Creating data/osu/cache folder...")
        os.makedirs("data/osu/cache")
    if not os.path.exists("data/osu/temp"):
        print("Creating data/osu/temp folder...")
        os.makedirs("data/osu/temp")

def check_files():
    api_keys = {"osu_api_key" : "", 'imgur_auth_info' : "", "puush_api_key": ""}
    api_file = "data/osu/apikey.json"

    if not fileIO(api_file, "check"):
        print("Adding data/osu/apikey.json...")
        fileIO(api_file, "save", api_keys)
    else:  # consistency check
        current = fileIO(api_file, "load")
        if current.keys() != api_keys.keys():
            for key in current.keys():
                if key not in api_keys.keys():
                    current[key] = api_keys[key]
                    print("Adding " + str(key) +
                          " field to osu apikey.json")
            fileIO(api_file, "save", current)

    # creates file for server to use
    settings_file = "data/osu/osu_settings.json"
    if not fileIO(settings_file, "check"):
        print("Adding data/osu/osu_settings.json...")
        fileIO(settings_file, "save", {
            "type": {
                "default": "osu.ppy.sh",
                "ripple":"ripple.moe"
                },
            "num_track" : 50,
            "num_best_plays": 5,
            })

def setup(bot):
    check_folders()
    check_files()

    global api_counter
    api_counter = 0

    osu = Osu(bot)
    tracking = Tracking(bot)

    loop = asyncio.get_event_loop()
    loop.create_task(tracking.play_tracker())
    bot.add_listener(osu.find_link, "on_message")
    bot.add_cog(osu)
    bot.add_cog(tracking)
