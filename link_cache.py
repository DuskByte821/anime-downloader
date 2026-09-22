"""Persistent local episode-link caches.

Each file under data/links/ is a per-series cache:

    # title: Renegade Immortal
    # type: donghua
    # source: cartoonsarea

    1::https://example.com/episode-1
    2::https://example.com/episode-2

Scan/import is DISCOVERY ONLY. It never downloads, never mutates
downloaded/watched, never deletes cache files. Actual downloads remain
an explicit user action through the existing Download workflow.

This is distinct from link_manager.LinkManager, which caches *series
page* URLs (anime::site::season::status::url::explicit). That module is
untouched; this one handles per-episode caches.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from config import LINK_CACHE_DIR, WATCHLIST_FILES
from models import Anime
from watchlist import load_watchlist, save_watchlist, normalize_name

logger = logging.getLogger(__name__)

VALID_TYPES: Tuple[str, ...] = ("anime", "donghua")

_META_RE = re.compile(r"^#\s*([A-Za-z_]+)\s*:\s*(.*)$")
_EPISODE_RE = re.compile(r"^(\d+)\s*::\s*(.+)$")


# ----------------------------------------------------------------------
# Data containers
# ----------------------------------------------------------------------

@dataclass
class LinkCache:
    path: Path
    title: str
    content_type: str
    source: Optional[str]
    episodes: Dict[int, str] = field(default_factory=dict)

    def url_for(self, episode: int) -> Optional[str]:
        return self.episodes.get(episode)

    def latest_episode(self) -> int:
        return max(self.episodes) if self.episodes else 0


@dataclass
class ScanReport:
    scanned: int = 0
    added: List[Tuple[str, str]] = field(default_factory=list)
    already_tracked: List[Tuple[str, str]] = field(default_factory=list)
    invalid: List[Tuple[Path, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.scanned} link file(s) scanned, "
            f"{len(self.added)} added, "
            f"{len(self.already_tracked)} already tracked, "
            f"{len(self.invalid)} invalid"
        )


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

def parse_link_file(path: Path) -> Optional[LinkCache]:
    """
    Parse a single link-cache file.

    Returns None (never raises) if the file is unreadable, missing the
    required `# type:` header, or has an unknown content type. Malformed
    episode lines and non-http URLs are skipped; valid ones are kept.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read link cache {path}: {e}")
        return None

    meta: Dict[str, str] = {}
    episodes: Dict[int, str] = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = _META_RE.match(line)
            if m:
                meta[m.group(1).lower()] = m.group(2).strip()
            continue
        m = _EPISODE_RE.match(line)
        if not m:
            logger.debug(f"Skipping malformed line in {path.name}: {line!r}")
            continue
        try:
            ep_num = int(m.group(1))
        except ValueError:
            continue
        url = m.group(2).strip()
        if not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            logger.debug(f"Skipping non-http URL in {path.name}: {url!r}")
            continue
        episodes[ep_num] = url

    ctype = meta.get("type", "").lower()
    if ctype not in VALID_TYPES:
        logger.warning(
            f"Link cache {path.name} has missing/invalid type {ctype!r}; skipping"
        )
        return None

    title = meta.get("title") or _title_from_filename(path)
    if not title:
        logger.warning(f"Link cache {path.name} has no title and no usable filename")
        return None

    return LinkCache(
        path=path,
        title=title,
        content_type=ctype,
        source=meta.get("source"),
        episodes=episodes,
    )


def _title_from_filename(path: Path) -> Optional[str]:
    """Fallback: `renegade_immortal.txt` -> `Renegade Immortal`."""
    stem = path.stem
    if not stem:
        return None
    parts = [p for p in re.split(r"[_\-]+", stem) if p]
    if not parts:
        return None
    return " ".join(p.capitalize() for p in parts)


# ----------------------------------------------------------------------
# Directory scan
# ----------------------------------------------------------------------

def iter_link_files(links_dir: Path) -> List[Path]:
    if not links_dir.exists():
        return []
    return sorted(p for p in links_dir.glob("*.txt") if p.is_file())


def scan_links_dir(
    links_dir: Optional[Path] = None,
    watchlist_paths: Optional[Dict[str, Path]] = None,
) -> ScanReport:
    """
    Scan data/links/ and ensure every valid cache has a matching watchlist
    entry, using the existing watchlist/model mechanisms.

    DISCOVERY ONLY:
      - never invokes the downloader or the download queue
      - never mutates downloaded/watched on existing entries
      - never deletes or rewrites cache files
      - idempotent: N scans == 1 scan

    Content-type separation is enforced by routing each cache to the
    watchlist file identified by its `# type:` header.
    """
    links_dir = links_dir or LINK_CACHE_DIR
    watchlist_paths = watchlist_paths or WATCHLIST_FILES

    report = ScanReport()

    # Load each watchlist exactly once; track which ones need saving.
    watchlists: Dict[str, List[Anime]] = {}
    dirty: Dict[str, bool] = {}
    seen_titles: Dict[str, Set[str]] = {}
    for ctype, path in watchlist_paths.items():
        wl = load_watchlist(path)
        watchlists[ctype] = wl
        dirty[ctype] = False
        seen_titles[ctype] = {normalize_name(a.name) for a in wl}

    for path in iter_link_files(links_dir):
        cache = parse_link_file(path)
        if cache is None:
            report.invalid.append((path, "unparseable or invalid metadata"))
            continue

        report.scanned += 1
        key = normalize_name(cache.title)

        if key in seen_titles[cache.content_type]:
            report.already_tracked.append((cache.title, cache.content_type))
            continue

        watchlists[cache.content_type].append(
            Anime(
                name=cache.title,
                season="season 1",
                downloaded=0,
                watched=0,
                status="watching",
            )
        )
        seen_titles[cache.content_type].add(key)
        dirty[cache.content_type] = True
        report.added.append((cache.title, cache.content_type))

    for ctype, is_dirty in dirty.items():
        if is_dirty:
            save_watchlist(watchlists[ctype], watchlist_paths[ctype])
            logger.info(
                f"Link cache scan: saved {watchlist_paths[ctype].name}"
            )

    logger.info(f"Link cache scan: {report.summary()}")
    return report


# ----------------------------------------------------------------------
# Lookup (used by the downloader integration in main.py)
# ----------------------------------------------------------------------

def find_cache_for(
    title: str,
    content_type: str,
    links_dir: Optional[Path] = None,
) -> Optional[LinkCache]:
    """
    Find the cache matching (title, content_type) using the same
    normalization the watchlist uses. Returns None on miss.
    """
    if content_type not in VALID_TYPES:
        return None
    links_dir = links_dir or LINK_CACHE_DIR
    key = normalize_name(title)
    for path in iter_link_files(links_dir):
        cache = parse_link_file(path)
        if cache is None:
            continue
        if cache.content_type != content_type:
            continue
        if normalize_name(cache.title) == key:
            return cache
    return None


def get_cached_url(
    title: str,
    content_type: str,
    episode: int,
    links_dir: Optional[Path] = None,
) -> Optional[str]:
    """Return the cached URL for (title, content_type, episode), else None."""
    cache = find_cache_for(title, content_type, links_dir=links_dir)
    if cache is None:
        return None
    return cache.url_for(episode)