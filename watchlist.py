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

    # Look through the remaining parts to find season and episode
    for part in parts[1:]:
        lower = part.lower()
        if "season" in lower:
            # Extract season number, e.g., "season 7" -> 7, but we keep the whole string
            season = part  # keep as "season 7"
        elif "episode" in lower:
            # Extract episode number from "episode 07[59]" -> 7
            episode = extract_number(part)
        else:
            # If part is just a number, treat as episode
            if part.isdigit():
                episode = int(part)
            # If part has numbers but no keyword, treat as episode (e.g., "[59]" won't happen as separate part)
            # but we already handled above.

    # If no episode found and there is a number in the last part that is not season, assume episode
    # For example: "against the gods::season 1" -> no episode, fine.
    # If there is a part that is pure number, it would have been caught above.

    return name, season, episode


# ----------------------------------------------------------------------
# Main watchlist I/O
# ----------------------------------------------------------------------

def load_watchlist(file_path: Path = WATCHLIST_FILE) -> List[Anime]:
    """
    Parse anime.txt and return a list of Anime objects.

    Format:
        watching
        Name::season X::episode Y
        Name::episode Y
        Name::season X   (no episode → episode=0)

        completed
        Name::season X::episode Y
        ...
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
            if line.lower() in ("watching", "completed"):
                current_status = line.lower()
                continue

            # Parse the line
            name, season, episode = parse_entry(line)

            # Create Anime object
            anime = Anime(
                name=name,
                season=season,
                episode=episode,
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
