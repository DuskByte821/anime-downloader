"""Update the watchlist after successful downloads."""

import logging
from typing import List

from models import Anime
from watchlist import save_watchlist

logger = logging.getLogger(__name__)


def update_watchlist(anime_list: List[Anime], anime: Anime, new_episode: int) -> None:
    """
    Update the watched episode for a specific anime and save the watchlist.
    """
    try:
        logger.info(f"🔄 Updating {anime.name} from episode {anime.episode} to {new_episode}")
        anime.episode = new_episode
        save_watchlist(anime_list)
        logger.info(f"✅ Watchlist saved successfully for {anime.name}")
    except Exception as e:
        logger.exception(f"❌ Failed to update watchlist for {anime.name}: {e}")
        raise