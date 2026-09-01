"""Scraper for LuciferDonghua with link mapping reload."""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, List

import requests
from bs4 import BeautifulSoup

from models import Anime
from .base import Scraper
from config import HEADERS, TIMEOUT, DATA_DIR

logger = logging.getLogger(__name__)


class LuciferDonghuaScraper(Scraper):
    BASE_URL = "https://luciferdonghua.in"
    LINKS_FILE = DATA_DIR / "links.txt"

    def __init__(self):
        self._episode_cache: Dict[str, Dict[int, str]] = {}
        self._url_map: Dict[str, str] = self._load_url_map()

    def reload_links(self):
        """Reload the URL mapping from links.txt."""
        self._url_map = self._load_url_map()
        logger.debug(f"Reloaded {len(self._url_map)} anime mappings")

    # ----------------------------------------------------------------------
    # Mapping from anime name to main page URL
    # ----------------------------------------------------------------------
    def _clean_slug(self, slug: str) -> str:
        slug = re.sub(r"-season-\d+", "", slug)
        slug = re.sub(r"-new", "", slug)
        slug = re.sub(r"-\d{4}", "", slug)
        name = slug.replace("-", " ").title()
        return name

    def _load_url_map(self) -> Dict[str, str]:
        mapping = {}
        if not self.LINKS_FILE.exists():
            return mapping
        with self.LINKS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if not url:
                    continue
                match = re.search(r"/anime/([^/]+)/?$", url)
                if match:
                    slug = match.group(1)
                    clean_name = self._clean_slug(slug)
                    mapping[clean_name.lower()] = url
        return mapping
        
    def save_links(self, mapping: Dict[str, str]):
        """Save a new mapping to links.txt (overwrites)."""
        with self.LINKS_FILE.open("w", encoding="utf-8") as f:
            for url in mapping.values():
                f.write(url + "\n")
        self.reload_links()

    def search_anime(self, query: str) -> List[tuple]:
        """
        Search for anime on LuciferDonghua and return list of (name, url, latest_ep).
        """
        results = []
        try:
            search_url = f"{self.BASE_URL}/search?keyword={query.replace(' ', '+')}"
            resp = requests.get(search_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("div.items div.item"):
                a = item.find("a")
                if not a:
                    continue
                name = a.get_text(strip=True)
                url = a.get("href")
                if not url.startswith("http"):
                    url = self.BASE_URL + url
                # get latest episode (quick fetch)
                latest = 0
                try:
                    resp2 = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    for a2 in soup2.find_all("a", href=True):
                        if "episode-" in a2["href"]:
                            match = re.search(r"episode-(\d+)", a2["href"])
                            if match:
                                ep = int(match.group(1))
                                if ep > latest:
                                    latest = ep
                except:
                    pass
                results.append((name, url, latest))
        except Exception as e:
            logger.exception(f"Search failed: {e}")
        return results

    # ----------------------------------------------------------------------
    # Helper methods
    # ----------------------------------------------------------------------
    def _slugify(self, name: str) -> str:
        """Convert anime name to URL-friendly slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug

    def _extract_season_number(self, season_str: Optional[str]) -> Optional[int]:
        if not season_str:
            return None
        match = re.search(r"(\d+)", season_str)
        return int(match.group(1)) if match else None

    # ----------------------------------------------------------------------
    # Main page URL discovery
    # ----------------------------------------------------------------------
    def _get_main_page_url(self, anime: Anime) -> Optional[str]:
        key = anime.name.lower()
        if key in self._url_map:
            logger.debug(f"Using exact mapping for {anime.name}: {self._url_map[key]}")
            return self._url_map[key]

        # fuzzy match
        for mapped_key, url in self._url_map.items():
            if key in mapped_key or mapped_key in key:
                logger.debug(f"Using fuzzy mapping for {anime.name}: {url}")
                return url

        # 3. Fallback: construct URL using common patterns
        slug = self._slugify(anime.name)
        season_num = self._extract_season_number(anime.season)
        patterns = [
            f"{self.BASE_URL}/anime/{slug}/",
            f"{self.BASE_URL}/{slug}/",
        ]
        if season_num is not None:
            season_slug = f"{slug}-season-{season_num}"
            patterns.insert(0, f"{self.BASE_URL}/anime/{season_slug}/")

        for url in patterns:
            try:
                resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT)
                if resp.status_code == 200:
                    return url
            except Exception:
                continue

        logger.warning(f"Could not find main page for {anime.name}")
        return None

    # ----------------------------------------------------------------------
    # Episode scraping
    # ----------------------------------------------------------------------
    def get_direct_video_url(self, anime: Anime, episode: int) -> Optional[str]:
        """
        Fetch the episode page and extract the direct video URL (e.g., Dailymotion embed).
        Returns the URL or None if not found.
        """
        episode_url = self.get_download_link(anime, episode)  # gets the episode page
        try:
            resp = requests.get(episode_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Look for iframes – common pattern for Dailymotion
            iframe = soup.find("iframe", src=re.compile(r"(dailymotion|youtube|player\.vimeo)"))
            if iframe:
                src = iframe.get("src")
                if src:
                    # Clean up URL (remove query params if needed)
                    return src
            # Also look for video source tags
            video = soup.find("video")
            if video:
                source = video.find("source")
                if source and source.get("src"):
                    return source["src"]
            # Try to find any link ending with .mp4
            for a in soup.find_all("a", href=True):
                if a["href"].endswith(".mp4"):
                    return a["href"]
            return None
        except Exception as e:
            logger.exception(f"Failed to extract direct video URL for {anime.name} ep {episode}: {e}")
            return None

    def _scrape_episode_links(self, page_url: str) -> Dict[int, str]:
        """
        Fetch the main page, extract all episode links.
        Returns dict {episode_number: full_url}
        """
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            episode_map = {}
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "episode-" in href:
                    match = re.search(r"episode-(\d+)", href)
                    if match:
                        ep = int(match.group(1))
                        # Build absolute URL
                        if href.startswith("http"):
                            full_url = href
                        else:
                            full_url = self.BASE_URL + href if href.startswith("/") else self.BASE_URL + "/" + href
                        episode_map[ep] = full_url
            return episode_map
        except Exception as e:
            logger.exception(f"Failed to scrape episode links from {page_url}: {e}")
            return {}

    # ----------------------------------------------------------------------
    # Public API (implements Scraper)
    # ----------------------------------------------------------------------
    def get_latest_episode(self, anime: Anime) -> int:
        """Get latest episode by scraping the main page."""
        page_url = self._get_main_page_url(anime)
        if not page_url:
            return 0

        episode_map = self._scrape_episode_links(page_url)
        if not episode_map:
            logger.warning(f"No episode links found for {anime.name}")
            return 0

        # Cache for later use in get_download_link
        self._episode_cache[anime.name] = episode_map
        latest = max(episode_map.keys())
        logger.info(f"Latest episode for {anime.name}: {latest}")
        return latest

    def get_download_link(self, anime: Anime, episode: int) -> str:
        """Return the episode page URL (from cache or constructed)."""
        # First, try cache
        if anime.name in self._episode_cache and episode in self._episode_cache[anime.name]:
            return self._episode_cache[anime.name][episode]

        # If not cached, construct it from the main page URL
        page_url = self._get_main_page_url(anime)
        if not page_url:
            raise RuntimeError(f"Could not find main page for {anime.name}")

        base_path = page_url.rstrip("/")
        ep_url = f"{base_path}/episode-{episode}/"
        return ep_url
