"""HTTP GET with per-host rate limiting and session HTML caching."""

import logging
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from config import HEADERS, TIMEOUT
from scraper.cache import html_get, html_set

logger = logging.getLogger(__name__)

# Per-host minimum seconds between requests
MIN_REQUEST_INTERVAL = 0.5

_last_request: dict[str, float] = {}


def _wait_for_host(host: str) -> None:
    last = _last_request.get(host, 0.0)
    elapsed = time.time() - last
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request[host] = time.time()


def fetch_html(url: str, use_cache: bool = True) -> Optional[str]:
    """
    Fetch a URL as text.

    - Uses the in-memory session cache if `use_cache` is True.
    - Applies per-host rate limiting.
    - Returns None on any failure.
    - Never raises.
    """
    if use_cache:
        cached = html_get(url)
        if cached is not None:
            logger.debug(f"[http] cache hit: {url}")
            return cached

    host = urlparse(url).netloc
    _wait_for_host(host)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        logger.warning(f"[http] {status} for {url}")
        return None
    except requests.RequestException as e:
        logger.warning(f"[http] failed {url}: {e}")
        return None

    text = resp.text
    if use_cache:
        html_set(url, text)
    return text