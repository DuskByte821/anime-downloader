"""Base scraper interface."""

from abc import ABC, abstractmethod
from models import Anime


class Scraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def get_latest_episode(self, anime: Anime) -> int:
        """
        Fetch the latest available episode number for the given anime.
        Returns 0 if no episodes found.
        """
        pass

    @abstractmethod
    def get_download_link(self, anime: Anime, episode: int) -> str:
        """
        Resolve the direct download URL for a specific episode.
        Raises an exception if link cannot be resolved.
        """
        pass