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
    """
    Update the downloaded episode for one anime and save the watchlist
    back to the file the caller loaded it from.

    `file_path` must be provided by callers operating on a specific
    watchlist (anime.txt vs donghua.txt). If omitted, falls back to the
    legacy anime.txt location.
    """
    if file_path is None:
        file_path = ANIME_WATCHLIST_FILE

    try:
        logger.info(
            f"🔄 Updating {anime.name}: downloaded {anime.downloaded} → {new_episode}"
        )
        anime.downloaded = new_episode
        save_watchlist(anime_list, file_path)
        logger.info(f"💾 Watchlist saved to {file_path.resolve()}")

        # Verify the write
        reloaded = load_watchlist(file_path)
        for a in reloaded:
            if a.name == anime.name and a.season == anime.season:
                if a.downloaded == new_episode:
                    logger.info(f"✅ Verified: {anime.name} downloaded={new_episode}")
                else:
                    logger.warning(
                        f"⚠️ Verification mismatch: {anime.name} "
                        f"has downloaded={a.downloaded}, expected {new_episode}"
                    )
                break
    except Exception as e:
        logger.exception(f"❌ Failed to update watchlist: {e}")
        raise