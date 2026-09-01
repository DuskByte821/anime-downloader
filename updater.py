"""Update the watchlist after successful downloads."""

import logging
from pathlib import Path
from typing import List

from models import Anime
from watchlist import save_watchlist, load_watchlist
from config import WATCHLIST_FILE

logger = logging.getLogger(__name__)


def update_watchlist(anime_list: List[Anime], anime: Anime, new_episode: int) -> None:
    """
    Update the watched episode for a specific anime and save the watchlist.
    After saving, reload to verify the update.
    """
    try:
        logger.info(f"🔄 Updating {anime.name}: {anime.episode} → {new_episode}")
        anime.episode = new_episode
        save_watchlist(anime_list)
        logger.info(f"💾 Watchlist saved to {WATCHLIST_FILE.resolve()}")

        # Verify by reloading
        reloaded = load_watchlist()
        for a in reloaded:
            if a.name == anime.name and a.season == anime.season:
                if a.episode == new_episode:
                    logger.info(f"✅ Verified: {anime.name} now at episode {new_episode}")
                else:
                    logger.warning(f"⚠️ Verification failed: {anime.name} shows {a.episode} instead of {new_episode}")
                break
    except Exception as e:
        logger.exception(f"❌ Failed to update watchlist: {e}")
        raise