"""Bridges between the TUI and the existing downloader engine."""

import logging
import subprocess
import json
from pathlib import Path
from typing import List, Optional

from config import DOWNLOAD_DIR, WATCHLIST_FILES
from models import Anime
from queue_manager import QUEUE
from scraper.luciferdonghua import LuciferDonghuaScraper
from watchlist import load_watchlist, save_watchlist

logger = logging.getLogger(__name__)

_scraper = LuciferDonghuaScraper()


# ----------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------

def search(query: str) -> List[dict]:
    """
    Search Lucifer for `query`. Returns list of dicts:
        {"title": str, "url": str, "latest": int}
    """
    results = _scraper.search_anime(query)
    return [{"title": t, "url": u, "latest": l} for t, u, l in results]


# ----------------------------------------------------------------------
# Series metadata (delegates to tui.metadata)
# ----------------------------------------------------------------------

def series_metadata(series_url: str) -> dict:
    from tui.metadata import fetch_series_metadata
    return fetch_series_metadata(series_url)


# ----------------------------------------------------------------------
# Episodes
# ----------------------------------------------------------------------

def series_episodes(series_url: str) -> dict[int, str]:
    """Return {episode_number: episode_url}."""
    return _scraper._build_episode_map(series_url)


# ----------------------------------------------------------------------
# Streams (via yt-dlp -J)
# ----------------------------------------------------------------------

def fetch_streams(episode_url: str) -> List[dict]:
    """
    Run `yt-dlp -J <episode_url>` and return a list of format dicts:
        {"res": "1080p", "size": "543 MB", "codec": "HEVC", "url": str}
    Empty list if yt-dlp fails.
    """
    try:
        proc = subprocess.run(
            ["yt-dlp", "-J", "--no-warnings", episode_url],
            capture_output=True, text=True, timeout=60, check=True,
        )
        info = json.loads(proc.stdout)
    except Exception as e:
        logger.warning(f"yt-dlp -J failed for {episode_url}: {e}")
        return []

    rows = []
    for f in info.get("formats", []):
        height = f.get("height")
        if not height:
            continue
        res = f"{height}p"
        size_bytes = f.get("filesize") or f.get("filesize_approx")
        if size_bytes:
            size_mb = size_bytes / (1024 * 1024)
            size = f"{size_mb:.0f} MB"
        else:
            size = "—"
        codec = (f.get("vcodec") or "").split(".")[0].upper() or "—"
        rows.append({
            "res": res,
            "size": size,
            "codec": codec,
            "url": f.get("url", ""),
        })
    # dedupe by resolution, keep largest
    best = {}
    for r in rows:
        key = r["res"]
        if key not in best or r["size"] > best[key]["size"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: int(r["res"].rstrip("p")), reverse=True)


# ----------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------

def queue_download(
    anime: Anime,
    episode: int,
    episode_url: str,
    content_type: str,
) -> int:
    """
    Enqueue a download using the existing queue manager.
    Returns the job id.
    """
    file_path = WATCHLIST_FILES[content_type]
    watchlist = load_watchlist(file_path)

    if anime.season:
        m = __import__("re").search(r"\d+", anime.season)
        season_str = f"_s{m.group(0)}" if m else ""
    else:
        season_str = ""
    canonical = f"{anime.name.replace(' ', '_')}{season_str}_ep{episode}.mp4"
    dest = DOWNLOAD_DIR / canonical

    return QUEUE.add_job(
        anime, episode, watchlist, dest, episode_url,
        watchlist_file=file_path,
    )


# ----------------------------------------------------------------------
# Watchlist helpers for the TUI
# ----------------------------------------------------------------------

def find_in_watchlist(name: str, content_type: str) -> Optional[Anime]:
    from watchlist import normalize_name
    watchlist = load_watchlist(WATCHLIST_FILES[content_type])
    key = normalize_name(name)
    for a in watchlist:
        if normalize_name(a.name) == key:
            return a
    return None


def add_to_watchlist(name: str, season: Optional[str], content_type: str) -> Anime:
    file_path = WATCHLIST_FILES[content_type]
    watchlist = load_watchlist(file_path)
    from watchlist import normalize_name
    key = normalize_name(name)
    for a in watchlist:
        if normalize_name(a.name) == key:
            return a
    anime = Anime(name=name, season=season, downloaded=0, watched=0, status="watching")
    watchlist.append(anime)
    save_watchlist(watchlist, file_path)
    return anime