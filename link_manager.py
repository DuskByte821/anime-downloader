"""Link cache manager with explicit-link support.

Format:
    anime::site::season::status::url::explicit
Where explicit is 'yes' or 'no'.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import DATA_DIR

logger = logging.getLogger(__name__)


class LinkManager:
    def __init__(self, file_path: Path = DATA_DIR / "links.txt"):
        self.file_path = file_path
        # key -> (status, url, explicit)
        self._cache: Dict[Tuple[str, str, str], Tuple[str, str, bool]] = {}
        self._load()

    # ----------------------------------------------------------------------
    # I/O
    # ----------------------------------------------------------------------

    def _load(self):
        self._cache.clear()
        if not self.file_path.exists():
            return
        with self.file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("::")
                if len(parts) < 4:
                    # Legacy: anime::url
                    if "::" in line and not any(kw in line for kw in ("found", "not_found")):
                        anime, url = parts[0], parts[1]
                        key = (anime, "luciferdonghua", "")
                        self._cache[key] = ("found", url, False)
                        logger.debug(f"Migrated legacy link: {anime} -> {url}")
                    continue
                # New format: anime::site::season::status::url[::explicit]
                anime = parts[0]
                site = parts[1]
                season = parts[2]
                status = parts[3]
                url = parts[4] if len(parts) > 4 else ""
                explicit = False
                if len(parts) > 5:
                    explicit = parts[5].lower() == "yes"
                key = (anime, site, season)
                self._cache[key] = (status, url, explicit)
        logger.debug(f"Loaded {len(self._cache)} link entries")

    def _save(self):
        lines = []
        for (anime, site, season), (status, url, explicit) in sorted(self._cache.items()):
            exp_str = "yes" if explicit else "no"
            lines.append(f"{anime}::{site}::{season}::{status}::{url}::{exp_str}")
        with self.file_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.debug(f"Saved {len(lines)} link entries")

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def get(self, anime: str, site: str, season: str = "") -> Optional[Tuple[str, str, bool]]:
        """Return (status, url, explicit) or None."""
        key = self._normalize_key(anime, site, season)
        return self._cache.get(key)

    def set(self, anime: str, site: str, season: str, status: str, url: str = "", explicit: bool = False):
        """Store a link status/URL and explicit flag."""
        key = self._normalize_key(anime, site, season)
        self._cache[key] = (status, url, explicit)
        self._save()

    def invalidate(self, anime: str, site: str, season: str):
        """Remove an entry from the cache, unless it is marked explicit."""
        key = self._normalize_key(anime, site, season)
        entry = self._cache.get(key)
        if entry and entry[2]:  # explicit
            logger.info(f"Skipping invalidation of explicit link: {anime}::{site}::{season}")
            return
        if key in self._cache:
            del self._cache[key]
            self._save()
            logger.debug(f"Invalidated link for {anime}::{site}::{season}")

    def get_url(self, anime: str, site: str, season: str = "") -> Optional[str]:
        """Return URL if status is 'found', else None."""
        entry = self.get(anime, site, season)
        if entry and entry[0] == "found":
            return entry[1]
        return None

    def is_explicit(self, anime: str, site: str, season: str = "") -> bool:
        """Return True if the link is marked explicit."""
        entry = self.get(anime, site, season)
        return entry is not None and entry[2]

    def set_explicit(self, anime: str, site: str, season: str, explicit: bool = True):
        """Mark or unmark a link as explicit."""
        entry = self.get(anime, site, season)
        if entry is None:
            logger.warning(f"Cannot set explicit flag: no entry for {anime}::{site}::{season}")
            return
        status, url, _ = entry
        self.set(anime, site, season, status, url, explicit)
        logger.info(f"Set explicit={explicit} for {anime}::{site}::{season}")

    def _normalize_key(self, anime: str, site: str, season: str) -> Tuple[str, str, str]:
        anime = " ".join(anime.split())
        site = site.lower().strip()
        season = season.strip()
        return (anime, site, season)