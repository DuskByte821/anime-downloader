"""Search strategies for Lucifer Donghua.

Two entry points, both returning list[(title, url)] of clean candidates:

    search_via_ajax(query)  -> list | None   (None = "ajax failed, try HTML")
    search_via_html(html)   -> list           ([] = "no matches")

Provider-specific logic (episode counts, series scoring) stays in
luciferdonghua.py. This module only knows how to find candidate
series URLs.
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from config import LUCIFER_DONGHUA_BASE
from scraper.http import post_json

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Shared URL filter
# ----------------------------------------------------------------------

# Matches /anime/some-slug/ and /anime/some-slug/anything/ (but not /anime/ itself)
ANIME_HREF_RE = re.compile(r"^/anime/[a-z0-9][a-z0-9-]*/?", re.I)

# Common theme prefixes that get glued onto anchor text
_TITLE_PREFIX_RE = re.compile(
    r"^(DONGHUA|ONA|TV|Movie|Ongoing|Completed|Sub|Dub|HD|4K|\s)+",
    re.I,
)


def _normalize_href(href: str) -> Optional[str]:
    """Return a canonical /anime/... path or None if it's not an anime page."""
    if not href:
        return None
    href = href.strip()
    # Strip absolute host if present
    if href.startswith("http"):
        if LUCIFER_DONGHUA_BASE not in href:
            return None
        href = href[len(LUCIFER_DONGHUA_BASE):]
    # Normalize leading slash
    if not href.startswith("/"):
        href = "/" + href
    if not ANIME_HREF_RE.match(href):
        return None
    return href

def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    t = _TITLE_PREFIX_RE.sub("", t).strip()
    return t

def _matches_query(title: str, query: str) -> bool:
    """
    True if at least one meaningful token from the query appears in the title.
    Prevents 'Wealth and Wonder' appearing for 'perfect world'.
    """
    def tokens(s: str):
        return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2]
    q_tokens = tokens(query)
    if not q_tokens:
        return True
    t_lower = title.lower()
    return any(tok in t_lower for tok in q_tokens)

# ----------------------------------------------------------------------
# HTML search And AJAX search
# ----------------------------------------------------------------------

# Containers that *may* hold search results
_RESULT_CONTAINERS = ("div.listupd", "div.items", "div.postbody", "#content")

# Selectors that we must never descend into — sidebar, widgets, homepage widgets
_EXCLUDED_CONTAINERS = (
    "#sidebar",
    ".widget",
    ".section",
    "div.releases.hothome",
    "div.releases.latesthome",
    "div.lucifer-sched",
    "div.serieslist",
)
# The Ajaxy Live Search plugin uses one of these action names depending on
# its version. We try them in order until one returns JSON.
# The theme's live-search endpoint
AJAX_ACTION = "ts_ac_do_search"
AJAX_QUERY_PARAM = "ts_ac_query"


def _parse_latest_int(raw: str) -> int:
    """
    post_latest can be '161', 'PT-02', 'Ep 5', etc.
    Return the integer if the string is purely numeric after stripping,
    else 0.
    """
    if not raw:
        return 0
    s = str(raw).strip()
    if s.isdigit():
        return int(s)
    # Try to pull a leading number (e.g. "Ep 5" -> 5). Only if the rest
    # is short, otherwise "161 sub" could be mistaken for a real one.
    m = re.match(r"^\s*(\d+)\s*$", s)
    if m:
        return int(m.group(1))
    return 0


def search_via_ajax(query: str) -> Optional[List[Tuple[str, str, int]]]:
    """
    Query the theme's AJAX search endpoint.

    Returns list of (title, url, latest) on success, or None on failure.
    `latest` is 0 when the site's response doesn't provide a numeric
    episode number for that result.
    """
    url = f"{LUCIFER_DONGHUA_BASE}/wp-admin/admin-ajax.php"
    payload = {
        "action": AJAX_ACTION,
        AJAX_QUERY_PARAM: query,
    }
    data = post_json(url, payload)
    if data is None:
        return None

    # Envelope is {"anime": [{"all": [...]}]} but be defensive: walk it.
    items = []
    if isinstance(data, dict):
        anime = data.get("anime")
        if isinstance(anime, list):
            for bucket in anime:
                if isinstance(bucket, dict):
                    all_items = bucket.get("all")
                    if isinstance(all_items, list):
                        items.extend(all_items)
        # Some versions flatten it as {"results": [...]}
        elif "results" in data and isinstance(data["results"], list):
            items = data["results"]
    elif isinstance(data, list):
        items = data

    pairs: List[Tuple[str, str, int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _clean_title(item.get("post_title") or "")
        href = item.get("post_link") or ""
        norm = _normalize_href(href)
        if norm is None or not title:
            continue
        latest = _parse_latest_int(item.get("post_latest") or "")
        pairs.append((title, norm, latest))

    return pairs

def _find_result_containers(soup):
    """Return only the *first* container — subsequent listupd blocks are sidebar noise."""
    for selector in _RESULT_CONTAINERS:
        containers = soup.select(selector)
        if containers:
            return [containers[0]]
    return [soup]

def _is_excluded(tag) -> bool:
    """True if the tag sits inside a sidebar / widget / homepage block."""
    for selector in _EXCLUDED_CONTAINERS:
        if tag.find_parent(*selector.split(",")) is not None:
            return True
    return False

def search_via_html(html: str) -> List[Tuple[str, str, int]]:
    """..."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    containers = _find_result_containers(soup)

    seen_urls: set[str] = set()
    pairs: List[Tuple[str, str, int]] = []

    for container in containers:
        for a in container.find_all("a", href=True):
            href = a["href"]
            norm = _normalize_href(href)
            if norm is None:
                continue
            if norm in seen_urls:
                continue
            if _is_excluded(a):
                continue

            heading = a.find(["h2", "h3", "h4"])
            raw_title = heading.get_text(" ", strip=True) if heading else a.get_text(" ", strip=True)
            title = _clean_title(raw_title)
            if not title:
                slug = norm.rstrip("/").rsplit("/", 1)[-1]
                title = slug.replace("-", " ").title()

            seen_urls.add(norm)
            pairs.append((title, norm, 0))   # latest always 0 from HTML

    return pairs