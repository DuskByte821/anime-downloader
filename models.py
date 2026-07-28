"""Project-wide data classes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Anime:
    """Represents an anime entry from the watchlist."""
    name: str
    season: Optional[str] = None      # e.g., "season 5" or None
    episode: int = 0                  # last watched episode number
    status: str = "watching"          # "watching" or "completed"

    def __post_init__(self):
        if self.season is not None and self.season.strip() == "":
            self.season = None