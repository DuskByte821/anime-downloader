"""Session-level and disk-level caching for scraper fetches.

Three goals:
  1. Avoid re-fetching the same URL twice in one process.
  2. Persist series metadata across runs, with a TTL.
  3. Never cache failures — a fetch that fails must be retried next run.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from config import DATA_DIR

logger = logging.getLogger(__name__)

META_DIR = DATA_DIR / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

# TTLs in seconds
SERIES_META_TTL = 7 * 24 * 3600       # 7 days
EPISODE_MAP_TTL = 24 * 3600           # 1 day

# In-memory session cache for HTML
_html_cache: dict[str, str] = {}


# ----------------------------------------------------------------------
# In-memory HTML cache (per process)
# ----------------------------------------------------------------------

def html_get(url: str) -> Optional[str]:
    """Return cached HTML for this session, or None."""
    return _html_cache.get(url)


def html_set(url: str, text: str) -> None:
    """Store HTML for this session. Only call on successful fetches."""
    _html_cache[url] = text


def html_clear() -> None:
    _html_cache.clear()


# ----------------------------------------------------------------------
# Disk cache helpers (JSON)
# ----------------------------------------------------------------------

def _slug_from_url(url: str) -> str:
    """Extract the last path segment from a URL, sanitized."""
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if "/" in path else path
    # Sanitize: keep alnum, dash, underscore
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)


def _meta_path(url: str, suffix: str = ".json") -> Path:
    return META_DIR / f"{_slug_from_url(url)}{suffix}"


def read_json_cache(url: str, suffix: str, ttl: int) -> tuple[Optional[Any], bool]:
    """
    Read a JSON cache entry.
    Returns (data, is_fresh).
      - (None, False) if no file
      - (data, True)  if file exists and is fresh
      - (data, False) if file exists but is stale
    """
    path = _meta_path(url, suffix)
    if not path.exists():
        return (None, False)
    try:
        age = time.time() - path.stat().st_mtime
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return (data, age < ttl)
    except Exception as e:
        logger.debug(f"[cache] failed to read {path.name}: {e}")
        return (None, False)


def write_json_cache(url: str, suffix: str, data: Any) -> None:
    """Persist a JSON cache entry. Never call on failure."""
    path = _meta_path(url, suffix)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"[cache] wrote {path.name}")
    except Exception as e:
        logger.warning(f"[cache] failed to write {path.name}: {e}")


def invalidate(url: str, suffix: str = ".json") -> None:
    """Delete a cache entry (used on schema changes or explicit refresh)."""
    path = _meta_path(url, suffix)
    if path.exists():
        path.unlink()
        logger.info(f"[cache] invalidated {path.name}")


# ----------------------------------------------------------------------
# Convenience wrappers for the two things we actually cache
# ----------------------------------------------------------------------

def read_series_meta(url: str) -> tuple[Optional[dict], bool]:
    return read_json_cache(url, ".json", SERIES_META_TTL)


def write_series_meta(url: str, data: dict) -> None:
    write_json_cache(url, ".json", data)


def read_episode_map(url: str) -> tuple[Optional[dict], bool]:
    """Episode maps are stored with int keys — JSON converts them to str.
    Callers must convert back."""
    return read_json_cache(url, ".episodes.json", EPISODE_MAP_TTL)


def write_episode_map(url: str, ep_map: dict[int, str]) -> None:
    # Convert int keys to str for JSON
    serializable = {str(k): v for k, v in ep_map.items()}
    write_json_cache(url, ".episodes.json", serializable)