"""Global configuration."""

from pathlib import Path

VERSION = "2.0.1"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DOWNLOAD_DIR = Path.home() / "Videos" / "Anime" / "anime-dl"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

WATCHLIST_FILE = DATA_DIR / "anime.txt"
FAILED_LOG_FILE = LOGS_DIR / "failed_downloads.txt"

HEADERS = {"User-Agent": "Mozilla/5.0 ..."}
TIMEOUT = 15
RETRY_COUNT = 3
RETRY_DELAY = 2

CHUNK_SIZE = 8192
MAX_PARALLEL_DOWNLOADS = 2   # for background queue

# Download quality options
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
    "--output", "%(title)s.%(ext)s",
]

# Scraper settings
LUCIFER_DONGHUA_BASE = "https://luciferdonghua.in"
CARTOONS_AREA_BASE = "https://cartoonsarea.com"   # fallback

DEBUG = False