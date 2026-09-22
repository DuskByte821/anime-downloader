"""Global configuration."""

from pathlib import Path

VERSION = "2.2.1"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DOWNLOAD_DIR = BASE_DIR / "downloads"
LINK_CACHE_DIR = DATA_DIR / "links"          

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LINK_CACHE_DIR.mkdir(parents=True, exist_ok=True)  

# --- Watchlist files --------------------------------------------------
ANIME_WATCHLIST_FILE = DATA_DIR / "anime.txt"
DONGHUA_WATCHLIST_FILE = DATA_DIR / "donghua.txt"

WATCHLIST_FILES = {
    "anime": ANIME_WATCHLIST_FILE,
    "donghua": DONGHUA_WATCHLIST_FILE,
}

# Legacy alias (kept for backwards-compatible imports)
WATCHLIST_FILE = ANIME_WATCHLIST_FILE

FAILED_LOG_FILE = LOGS_DIR / "failed_downloads.txt"

HEADERS = {"User-Agent": "Mozilla/5.0 ..."}
TIMEOUT = 15
RETRY_COUNT = 3
RETRY_DELAY = 2

CHUNK_SIZE = 8192
MAX_PARALLEL_DOWNLOADS = 2
PREVIEW_MAX_SIZE_MB = 20
PREVIEW_MAX_SIZE_BYTES = PREVIEW_MAX_SIZE_MB * 1024 * 1024

QUALITY_OPTIONS = {
    "best": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
}
DEFAULT_QUALITY = "720p"

USE_YT_DLP = True
YT_DLP_OPTIONS = [
    "--no-playlist",
    "--no-warnings",
    "--merge-output-format", "mp4",
    "--output", "%(title)s.%(ext)s",
]

LUCIFER_DONGHUA_BASE = "https://luciferdonghua.in"
CARTOONS_AREA_BASE = "https://cartoonsarea.com"

DEBUG = False

# Default content type for menus that don't explicitly ask.
# Change here, or toggle at runtime via the [t] shortcut.
DEFAULT_CONTENT_TYPE = "donghua"   # "anime" or "donghua"

ABBREVIATIONS = {
    "the demon hunter": ["tdh", "demon hunter", "demonhunter"],
    "battle through the heavens": ["btth"],
    "perfect world": ["pw"],
    "renegade immortal": ["ri"],
    "swallowed star": ["ss"],
    "stellar transformation": ["st"],
    "soul land 2": ["sl2", "soulland2"],
    "tomb of fallen gods": ["tofg"],
    "beyond the timescape": ["btt", "timescape"],
    "shrouding the heavens": ["sth"],
    "the great ruler": ["tgr"],
    "the divine emperor of destiny": ["tdeod"],
    "twin martial spirits": ["tms"],
    "endless heaven realm": ["ehr"],
    "sword and fairy 3": ["saf3"],
}
