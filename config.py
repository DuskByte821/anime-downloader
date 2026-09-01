"""Global configuration – all paths are absolute."""

from pathlib import Path

VERSION = "2.1.0"

# Base directory: location of this config file
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
# Download to project's downloads/ directory
DOWNLOAD_DIR = BASE_DIR / "downloads"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

WATCHLIST_FILE = DATA_DIR / "anime.txt"
FAILED_LOG_FILE = LOGS_DIR / "failed_downloads.txt"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
TIMEOUT = 15
RETRY_COUNT = 3
RETRY_DELAY = 2

CHUNK_SIZE = 8192
MAX_PARALLEL_DOWNLOADS = 2

# Maximum size (in MB) for a preview file; anything smaller is deleted
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
    "--merge-output-format", "mp4",   # ensures output is always .mp4
    "--output", "%(title)s.%(ext)s", # yt-dlp will name as it likes; we'll rely on fuzzy matching
]

LUCIFER_DONGHUA_BASE = "https://luciferdonghua.in"
CARTOONS_AREA_BASE = "https://cartoonsarea.com"

DEBUG = False