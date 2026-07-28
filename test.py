from watchlist import load_watchlist
from config import WATCHLIST_FILE

print(WATCHLIST_FILE)
print(WATCHLIST_FILE.exists())

anime_list = load_watchlist()

for anime in anime_list:
    print(anime)

anime = load_watchlist()

print(anime)
print(len(anime))