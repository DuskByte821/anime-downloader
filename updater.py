"""Update the watchlist after successful downloads."""

import logging
from typing import List

from models import Anime
from watchlist import save_watchlist

logger = logging.getLogger(__name__)


def update_watchlist(anime_list: List[Anime], anime: Anime, new_episode: int) -> None:
    """
    Update the watched episode for a specific anime and save the watchlist.
    Assumes the anime object is already in the list (by reference).
    """
    # Update the episode number in the list (the object is mutable)
    anime.episode = new_episode
    save_watchlist(anime_list)
    logger.info(f"Updated {anime.name} to episode {new_episode}")