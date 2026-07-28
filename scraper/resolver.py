"""Helper functions to extract download links from episode pages."""

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import HEADERS, TIMEOUT


def extract_download_link_from_page(page_url: str) -> Optional[str]:
    """
    Given an episode page URL, extract the direct download link.
    This is a generic placeholder; concrete scrapers may override.
    """
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for common patterns: <a> with "Download" or "Direct Download"
        # This is highly site-specific; we'll implement a naive search.
        # Example: find any link that contains "download" in text or href.
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"].lower()
            if "download" in text or "download" in href:
                return a["href"]
        return None
    except Exception:
        return None


def resolve_redirects(url: str) -> str:
    """Follow redirects to get final URL."""
    try:
        resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return resp.url
    except Exception:
        return url