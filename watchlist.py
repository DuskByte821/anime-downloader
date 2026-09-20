"""Read and write watchlist files (anime.txt / donghua.txt).

Both files share the same format with four fixed status sections:

    watching
    ended
    dropped
    completed
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from models import Anime
from config import ANIME_WATCHLIST_FILE

# Fixed order – must be preserved by the writer.
VALID_STATUSES = ("watching", "ended", "dropped", "completed")


# ----------------------------------------------------------------------
# Name normalization
# ----------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Case- and whitespace-insensitive comparison key."""
    return " ".join(name.casefold().split())


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def extract_number(text: str) -> int:
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else 0


def parse_entry(line: str) -> Tuple[str, Optional[str], int, int]:
    """
    Parse a watchlist entry line.

    Supported forms:
        Name::season X::downloaded Y::watched Z
        Name::downloaded Y::watched Z
        Name::season X::episode Y          (legacy -> downloaded=Y, watched=0)
        Name::episode Y                    (legacy -> downloaded=Y, watched=0)
        Name::season X
        Name

    Returns (name, season, downloaded, watched).
    """
    parts = [p.strip() for p in line.split("::")]
    name = parts[0]

    season = None
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
            downloaded = extract_number(part)
        elif part.isdigit():
            downloaded = int(part)

    return name, season, downloaded, watched


# ----------------------------------------------------------------------
# Load / save
# ----------------------------------------------------------------------

def load_watchlist(file_path: Path = ANIME_WATCHLIST_FILE) -> List[Anime]:
    """
    Parse a watchlist file. Recognizes all four status section headers.
    Unknown/blank lines are ignored.
    """
    if not file_path.exists():
        return []

    anime_list: List[Anime] = []
    current_status = "watching"

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if lower in VALID_STATUSES:
                current_status = lower
                continue

            name, season, downloaded, watched = parse_entry(line)
            anime_list.append(Anime(
                name=name,
                season=season,
                downloaded=downloaded,
                watched=watched,
                status=current_status,
            ))

    return anime_list


def save_watchlist(
    anime_list: List[Anime],
    file_path: Path = ANIME_WATCHLIST_FILE,
) -> None:
    """
    Write a watchlist file with all four sections in fixed order.
    Sections are always emitted, even when empty.
    """
    by_status = {s: [] for s in VALID_STATUSES}
    for a in anime_list:
        s = a.status if a.status in by_status else "watching"
        by_status[s].append(a)

    lines: List[str] = []
    for status in VALID_STATUSES:
        lines.append(status)
        for a in by_status[status]:
            lines.append(format_anime_line(a))
        lines.append("")   # separator between sections

    # Drop trailing blank line for a tidy file
    while lines and lines[-1] == "":
        lines.pop()

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_anime_line(anime: Anime) -> str:
    """Serialize an Anime object into the canonical entry format."""
    parts = [anime.name]
    if anime.season:
        parts.append(anime.season)
    parts.append(f"downloaded {anime.downloaded}")
    parts.append(f"watched {anime.watched}")
    return "::".join(parts)


# ----------------------------------------------------------------------
# Status transitions
# ----------------------------------------------------------------------

def change_status(anime_list: List[Anime], anime: Anime, new_status: str) -> bool:
    """
    Move an anime to a new status section, in-place.
    Returns True if a change was made, False otherwise.
    Preserves name, season, downloaded, watched.
    Never creates duplicates (anime object stays unique in the list).
    """
    if new_status not in VALID_STATUSES:
        return False
    if anime not in anime_list:
        return False
    if anime.status == new_status:
        return False
    anime.status = new_status
    return True