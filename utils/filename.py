# utils/filename.py
"""Filename matching helpers shared across modules."""

import re
from pathlib import Path
from typing import Optional, Set

from config import DOWNLOAD_DIR, PREVIEW_MAX_SIZE_BYTES, ABBREVIATIONS


def episode_pattern(episode: int) -> re.Pattern:
    """
    Match 'ep<episode>' / 'e<episode>' / 'episode <episode>' with a
    digit boundary on the right, so 'ep21' does not match 'ep211'.
    """
    return re.compile(
        rf"(?:ep|e|episode[\s_-]?)(?P<n>{episode})(?!\d)",
        re.IGNORECASE,
    )

def anime_matches_filename(anime_name: str, filename: str) -> bool:
    """
    Fuzzy match: at least one abbreviation for this anime must appear in
    the filename, OR 60% of anime-name tokens must appear.
    """
    def slug(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    file_slug = slug(filename)
    name_key = anime_name.lower().strip()

    # 1. Abbreviation check
    abbrs = ABBREVIATIONS.get(name_key, [])
    for ab in abbrs:
	    if re.search(rf"\b{re.escape(ab)}\b", file_slug):
	        return True

    # 2. Token overlap check
    anime_tokens = [t for t in slug(anime_name).split() if len(t) > 1]
    if not anime_tokens:
        return False
    present = sum(1 for t in anime_tokens if t in file_slug)
    return present / len(anime_tokens) >= 0.6

def episode_candidates_from_url(url: str, primary: Optional[int] = None) -> Set[int]:
    """
    Extract every episode number present in a URL like:
        ...episode-30-96-...   -> {30, 96}
        ...episode-30-...      -> {30}
    """
    nums: Set[int] = set()
    for m in re.finditer(r"episode-([\d-]+)", url, re.I):
        for n in re.findall(r"\d+", m.group(1)):
            nums.add(int(n))
    if primary is not None:
        nums.add(primary)
    return nums

def find_existing_file(
    anime_name: str, episode: int, season: Optional[str] = None
) -> Optional[Path]:
    """
    Scan DOWNLOAD_DIR for an .mp4 that:
      - contains a standalone 'ep<episode>' token (digit boundary)
      - has ≥60% anime-name token overlap
    Returns the file if size > PREVIEW_MAX_SIZE_BYTES, else None.
    Deletes undersized (preview) matches.
    """
    if not DOWNLOAD_DIR.exists():
        return None
    ep_re = episode_pattern(episode)
    for f in DOWNLOAD_DIR.glob("*.mp4"):
        if not ep_re.search(f.name):
            continue
        if not anime_matches_filename(anime_name, f.name):
            continue
        if f.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
            return f
        f.unlink()
    return None