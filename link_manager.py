"""Link cache manager with explicit-link support.

Format:
    anime::site::season::status::url::explicit
Where explicit is 'yes' or 'no'.

Anime names are matched case-insensitively and whitespace-normalized,
but the original display name is preserved in the file.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import DATA_DIR

logger = logging.getLogger(__name__)


class LinkManager:
    def __init__(self, file_path: Path = DATA_DIR / "links.txt"):
        self.file_path = file_path
        # key -> (status, url, explicit, display_name)
        self._cache: Dict[Tuple[str, str, str], Tuple[str, str, bool, str]] = {}
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
                        key = self._normalize_key(anime, "luciferdonghua", "")
                        self._cache[key] = ("found", url, False, anime)
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
                key = self._normalize_key(anime, site, season)
                self._cache[key] = (status, url, explicit, anime)
        logger.debug(f"Loaded {len(self._cache)} link entries")

    def _save(self):
        lines = []
        for (anime_key, site, season), (status, url, explicit, display) in sorted(self._cache.items()):
            exp_str = "yes" if explicit else "no"
            lines.append(f"{display}::{site}::{season}::{status}::{url}::{exp_str}")
        with self.file_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.debug(f"Saved {len(lines)} link entries")

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def get(self, anime: str, site: str, season: str = "") -> Optional[Tuple[str, str, bool]]:
        """Return (status, url, explicit) or None."""
        key = self._normalize_key(anime, site, season)
        entry = self._cache.get(key)
        if entry is None:
            return None
        status, url, explicit, _display = entry
        return (status, url, explicit)

    def set(
        self,
        anime: str,
        site: str,
        season: str,
        status: str,
        url: str = "",
        explicit: bool = False,
        override_explicit: bool = False,
    ):
        """
        Store a link status/URL.

        If the existing entry is explicit and `override_explicit` is False,
        the update is skipped and a warning is logged. This prevents
        accidental overwrites by --sync-links or future callers.
        """
        key = self._normalize_key(anime, site, season)
        existing = self._cache.get(key)
        if existing and existing[2] and not override_explicit:
            logger.warning(
                f"Refusing to overwrite explicit link for {anime}::{site}::{season}"
            )
            return

        display = " ".join(anime.split())
        self._cache[key] = (status, url, explicit, display)
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
        key = self._normalize_key(anime, site, season)
        entry = self._cache.get(key)
        if entry is None:
            logger.warning(f"Cannot set explicit flag: no entry for {anime}::{site}::{season}")
            return
        status, url, _old_explicit, display = entry
        self._cache[key] = (status, url, explicit, display)
        self._save()
        logger.info(f"Set explicit={explicit} for {anime}::{site}::{season}")

    def _normalize_key(self, anime: str, site: str, season: str) -> Tuple[str, str, str]:
        """Normalize key components for consistent lookup (case-insensitive)."""
        anime_key = " ".join(anime.casefold().split())
        site_key = site.lower().strip()
        season_key = season.strip()
        return (anime_key, site_key, season_key)

    # ----------------------------------------------------------------------
    # Bulk operations for debugging / sync
    # ----------------------------------------------------------------------

    def get_all_entries(self) -> List[Dict[str, str]]:
        entries = []
        for (anime_key, site, season), (status, url, explicit, display) in self._cache.items():
            entries.append({
                "anime": display,
                "site": site,
                "season": season,
                "status": status,
                "url": url,
                "explicit": "yes" if explicit else "no",
            })
        return entries