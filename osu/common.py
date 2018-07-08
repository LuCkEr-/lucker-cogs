from pymongo import MongoClient

modes = ["osu", "taiko", "ctb", "mania"]
modes2 = ["osu", "taiko", "fruits", "mania"]

client = MongoClient()
db = client['owo_database_2']