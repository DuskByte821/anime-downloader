"""Read and write the watchlist file (anime.txt) with flexible parsing."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from models import Anime
from config import WATCHLIST_FILE


# ----------------------------------------------------------------------
# Helper extraction functions
# ----------------------------------------------------------------------

def extract_number(text: str) -> int:
    """Extract the first integer from a string, return 0 if none."""
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else 0


def parse_entry(line: str) -> Tuple[str, Optional[str], int]:
    """
    Parse a watchlist line like:
        "Name::season X::episode Y"
        "Name::episode Y"
        "Name::season X"   (no episode)
        "Name"             (no season, no episode)

    Returns (name, season, episode).
    """
    parts = [p.strip() for p in line.split("::")]
    name = parts[0]

    season = None
    episode = 0
    downloaded = 0
    watched = 0
    for part in parts[1:]:
        lower = part.lower()
        if "season" in lower:
            season = part
        elif "downloaded" in lower:
            downloaded = extract_number(part)
        elif "watched" in lower:
            watched = extract_number(part)
        elif "episode" in lower:
            downloaded = extract_number(part)   # legacy
        elif part.isdigit():
            downloaded = int(part)              # fallback for plain number
    return name, season, downloaded, watched

# ----------------------------------------------------------------------
# Main watchlist I/O
# ----------------------------------------------------------------------
def load_watchlist(file_path: Path = WATCHLIST_FILE) -> List[Anime]:
    if not file_path.exists():
        return []
    anime_list = []
    current_status = "watching"
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("watching", "completed"):
                current_status = line.lower()
                continue
            name, season, downloaded, watched = parse_entry(line)
            anime = Anime(
                name=name,
                season=season,
                downloaded=downloaded,
                watched=watched,
                status=current_status
            )
            anime_list.append(anime)
    return anime_list

def save_watchlist(anime_list: List[Anime], file_path: Path = WATCHLIST_FILE) -> None:
    """
    Save the list of Anime objects to anime.txt in a clean, consistent format.
    Groups by status: watching first, then completed.
    """
    watching = [a for a in anime_list if a.status == "watching"]
    completed = [a for a in anime_list if a.status == "completed"]

    lines = []
    if watching:
        lines.append("watching")
        for a in watching:
            lines.append(format_anime_line(a))
        lines.append("")  # blank line separator

    if completed:
        lines.append("completed")
        for a in completed:
            lines.append(format_anime_line(a))
        lines.append("")

    file_path.write_text("\n".join(lines), encoding="utf-8")


def format_anime_line(anime: Anime) -> str:
    """
    Format a single Anime object into a watchlist line.
    Always includes episode for watching entries; for completed, includes only if >0.
    """
    parts = [anime.name]
    if anime.season:
        parts.append(anime.season)
    # Include episode if it's >0 or if status is watching (we want to keep it)
    if anime.episode > 0 or anime.status == "watching":
        parts.append(f"episode {anime.episode}")
    # If episode is 0 and status is completed, we omit it entirely (as in "against the gods::season 1")
    return "::".join(parts)
