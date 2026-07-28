"""Global configuration for the anime downloader."""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DOWNLOAD_DIR = Path.home() / "Downloads" / "Anime"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Watchlist file
WATCHLIST_FILE = DATA_DIR / "anime.txt"

# Network settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
TIMEOUT = 10
RETRY_COUNT = 3
RETRY_DELAY = 2

# Download settings
CHUNK_SIZE = 8192
MAX_PARALLEL_DOWNLOADS = 1

# Scrapers to try in order (class paths)
SCRAPERS = [
    "scraper.luciferdonghua.LuciferDonghuaScraper",
    "scraper.cartoonsarea.CartoonsAreaScraper",
]

# yt-dlp settings
USE_YT_DLP = True
YT_DLP_OPTIONS = [
    "--no-playlist",
    "--quiet",
    "--no-warnings",
    # "--extract-audio",    # uncomment if you want audio only
    # "--audio-format", "mp3",
]