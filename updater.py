"""Update the watchlist after successful downloads."""

import logging
from typing import List

from models import Anime
from watchlist import save_watchlist, load_watchlist
from config import WATCHLIST_FILE

logger = logging.getLogger(__name__)


def update_watchlist(anime_list: List[Anime], anime: Anime, new_episode: int) -> None:
    """
    Update the downloaded episode for a specific anime and save the watchlist.
    Does NOT modify watched progress.
    """
    try:
        logger.info(f"🔄 Updating {anime.name}: downloaded {anime.downloaded} → {new_episode}")
        anime.downloaded = new_episode
        save_watchlist(anime_list)
        logger.info(f"💾 Watchlist saved to {WATCHLIST_FILE.resolve()}")

        # Verify
        reloaded = load_watchlist()
        for a in reloaded:
            if a.name == anime.name and a.season == anime.season:
                if a.downloaded == new_episode:
                    logger.info(f"✅ Verified: {anime.name} downloaded={new_episode}")
                else:
                    logger.warning(
                        f"⚠️ Verification failed: {anime.name} shows downloaded={a.downloaded}"
                    )
                break
    except Exception as e:
        logger.exception(f"❌ Failed to update watchlist: {e}")
        raise