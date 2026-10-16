"""Update the watchlist after successful downloads."""

import logging
from pathlib import Path
from typing import List, Optional

from models import Anime
from watchlist import save_watchlist, load_watchlist
from config import ANIME_WATCHLIST_FILE

logger = logging.getLogger(__name__)


def update_watchlist(
    anime_list: List[Anime],
    anime: Anime,
    new_episode: int,
    file_path: Optional[Path] = None,
) -> None:
    if file_path is None:
        file_path = ANIME_WATCHLIST_FILE

    try:
        # Reload fresh so parallel jobs don't clobber each other
        fresh = load_watchlist(file_path)
        target = None
        for a in fresh:
            if a.name == anime.name and a.season == anime.season:
                target = a
                break
        if target is None:
            logger.warning(
                f"[updater] {anime.name} not found in {file_path.name}; "
                f"writing in-memory object as-is"
            )
            target = anime

        if new_episode <= target.downloaded:
            logger.info(
                f"⏭️  Skipping update for {anime.name}: "
                f"downloaded={target.downloaded} >= new={new_episode}"
            )
            return

        logger.info(f"🔄 Updating {anime.name}: downloaded {target.downloaded} → {new_episode}")
        target.downloaded = new_episode
        # Keep in-memory object consistent with disk
        anime.downloaded = new_episode
        save_watchlist(fresh, file_path)
        logger.info(f"💾 Watchlist saved to {file_path.resolve()}")

        # Verify
        reloaded = load_watchlist(file_path)
        for a in reloaded:
            if a.name == anime.name and a.season == anime.season:
                if a.downloaded == new_episode:
                    logger.info(f"✅ Verified: {anime.name} downloaded={new_episode}")
                else:
                    logger.warning(
                        f"⚠️  Verification mismatch: {anime.name} "
                        f"has downloaded={a.downloaded}, expected {new_episode}"
                    )
                break
    except Exception as e:
        logger.exception(f"❌ Failed to update watchlist: {e}")
        raise