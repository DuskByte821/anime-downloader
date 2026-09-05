"""Project-wide data classes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Anime:
    """Represents an anime entry from the watchlist."""
    name: str
    season: str | None = None
    downloaded: int = 0
    watched: int = 0
    status: str = "watching"



    def __post_init__(self):
        if self.season is not None and self.season.strip() == "":
            self.season = None