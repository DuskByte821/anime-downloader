"""Scraper for Lucifer Donghua – deterministic discovery with link manager."""

import logging
import re
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from models import Anime
from .base import Scraper
from config import HEADERS, TIMEOUT, LUCIFER_DONGHUA_BASE
from link_manager import LinkManager

logger = logging.getLogger(__name__)


class LuciferDonghuaScraper(Scraper):
    BASE_URL = LUCIFER_DONGHUA_BASE
    SITE_NAME = "luciferdonghua"

    def __init__(self, link_manager: Optional[LinkManager] = None):
        self._episode_cache: Dict[str, Dict[int, str]] = {}
        self.link_manager = link_manager or LinkManager()

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize whitespace and case for comparison."""
        return " ".join(name.casefold().split())

    @staticmethod
    def _extract_season_number(season_str: Optional[str]) -> Optional[int]:
        if not season_str:
            return None
        match = re.search(r"\d+", season_str)
        return int(match.group(0)) if match else None

    @staticmethod
    def _parse_episode_string(text: str) -> Tuple[int, Optional[int]]:
        cleaned = re.sub(r'^episode\s*', '', text, flags=re.I).strip()
        match = re.search(r'\[(\d+)\]', cleaned)
        source = int(match.group(1)) if match else None
        if match:
            cleaned = cleaned[:match.start()].strip()
        nums = re.findall(r'\d+', cleaned)
        if not nums:
            return 0, None
        primary = int(nums[0])
        return primary, source

    # ----------------------------------------------------------------------
    # Search and series discovery
    # ----------------------------------------------------------------------

    def search_anime(self, query: str) -> List[Tuple[str, str, int]]:
        """Search Lucifer Donghua and return all anime-like results."""
        results = []
        try:
            search_url = f"{self.BASE_URL}/?s={query.replace(' ', '+')}"
            logger.debug(f"Searching: {search_url}")
            resp = requests.get(search_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if not href:
                    continue
                if "/anime/" not in href:
                    continue
                if href.rstrip("/") == self.BASE_URL + "/anime":
                    continue
                title = a.get_text(strip=True)
                if not title:
                    title = href.split("/")[-2] if href.endswith("/") else href.split("/")[-1]
                    title = title.replace("-", " ").title()
                if not href.startswith("http"):
                    href = self.BASE_URL + href
                latest = self._fetch_latest_episode_from_series(href)
                results.append((title, href, latest))

            # Remove duplicates
            seen = set()
            unique = []
            for title, url, latest in results:
                if url not in seen:
                    seen.add(url)
                    unique.append((title, url, latest))
            return unique
        except Exception as e:
            logger.exception(f"Search failed for '{query}': {e}")
            return []

    def _fetch_latest_episode_from_series(self, series_url: str) -> int:
        try:
            resp = requests.get(series_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            ep_links = soup.select("ul#episode_page li a")
            if not ep_links:
                ep_links = soup.select("div.anime_video_body ul li a")
            numbers = []
            for a in ep_links:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                match = re.search(r"episode-(\d+)", href, re.I)
                if match:
                    ep_num = int(match.group(1))
                else:
                    ep_num, _ = self._parse_episode_string(text)
                if ep_num:
                    numbers.append(ep_num)
            return max(numbers) if numbers else 0
        except Exception:
            return 0

    def _is_likely_anime_result(self, title: str, url: str) -> bool:
        exclude = [
            r"tag/", r"category/", r"author/", r"page/", r"search",
            r"about", r"contact", r"privacy", r"terms", r"disclaimer",
            r"blog", r"post", r"comment", r"wp-", r"feed"
        ]
        for pattern in exclude:
            if re.search(pattern, url, re.I) or re.search(pattern, title, re.I):
                return False
        word_count = len(title.split())
        if word_count < 2 or word_count > 10:
            return False
        anime_keywords = ["season", "episode", "donghua", "anime", "sub", "dub"]
        if any(kw in title.lower() for kw in anime_keywords):
            return True
        if "/anime/" in url:
            return True
        return False

    def _get_series_url(self, anime: Anime, force_discover: bool = False) -> Optional[str]:
        normalized_name = self._normalize_name(anime.name)
        season_str = anime.season or ""
        season_num = self._extract_season_number(season_str)

        if not force_discover:
            cached = self.link_manager.get_url(anime.name, self.SITE_NAME, season_str)
            if cached:
                logger.debug(f"Using cached link for {anime.name}::{season_str}: {cached}")
                return cached

        results = self.search_anime(anime.name)
        if not results:
            logger.warning(f"No search results for {anime.name}")
            return None

        candidates = []
        for title, url, _ in results:
            norm_title = self._normalize_name(title)
            score = 0
            if norm_title == normalized_name:
                score += 100
            elif normalized_name in norm_title or norm_title in normalized_name:
                score += 50
            else:
                score += 10
            if season_num is not None:
                if f"season {season_num}" in title.lower():
                    score += 30
                elif f"season {season_num}" in url.lower():
                    score += 20
            if len(title.split()) > 8:
                score -= 20
            if not self._is_likely_anime_result(title, url):
                score -= 50
            candidates.append((score, title, url))

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_title, best_url = candidates[0]

        MIN_ACCEPT_SCORE = 50
        if best_score < MIN_ACCEPT_SCORE:
            logger.warning(f"No strong match for {anime.name} (best score {best_score}); recording not_found")
            return None

        logger.info(f"Best match for {anime.name}: {best_title} (score {best_score})")
        return best_url

    # ----------------------------------------------------------------------
    # Episode discovery
    # ----------------------------------------------------------------------

    def _build_episode_map(self, series_url: str) -> Dict[int, str]:
        try:
            resp = requests.get(series_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            ep_map = {}
            ep_links = soup.select("ul#episode_page li a")
            if not ep_links:
                ep_links = soup.select("div.anime_video_body ul li a")
            if not ep_links:
                ep_links = soup.find_all("a", href=re.compile(r"episode-\d+", re.I))
            for a in ep_links:
                href = a.get("href")
                if not href:
                    continue
                if not href.startswith("http"):
                    href = self.BASE_URL + href
                match = re.search(r"episode-(\d+)", href, re.I)
                if match:
                    ep_num = int(match.group(1))
                else:
                    text = a.get_text(strip=True)
                    ep_num, _ = self._parse_episode_string(text)
                    if ep_num == 0:
                        continue
                ep_map[ep_num] = href
            return ep_map
        except Exception as e:
            logger.exception(f"Failed to build episode map from {series_url}: {e}")
            return {}

    # ----------------------------------------------------------------------
    # Public API (implements Scraper)
    # ----------------------------------------------------------------------

    def get_latest_episode(self, anime: Anime) -> int:
        series_url = self._get_series_url(anime)
        if not series_url:
            return 0
        ep_map = self._build_episode_map(series_url)
        if not ep_map:
            return 0
        self._episode_cache[anime.name] = ep_map
        latest = max(ep_map.keys())
        logger.info(f"Latest episode for {anime.name}: {latest}")
        return latest

    def get_download_link(self, anime: Anime, episode: int) -> str:
        # Check cache first
        if anime.name in self._episode_cache and episode in self._episode_cache[anime.name]:
            return self._episode_cache[anime.name][episode]
        # If not cached, get series URL and build map
        series_url = self._get_series_url(anime)
        if not series_url:
            raise RuntimeError(f"Cannot find series page for {anime.name}")
        ep_map = self._build_episode_map(series_url)
        if not ep_map:
            raise RuntimeError(f"No episodes found for {anime.name}")
        self._episode_cache[anime.name] = ep_map
        if episode not in ep_map:
            raise RuntimeError(f"Episode {episode} not found for {anime.name}")
        return ep_map[episode]

    def get_direct_video_url(self, anime: Anime, episode: int) -> Optional[str]:
        episode_url = self.get_download_link(anime, episode)
        try:
            resp = requests.get(episode_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            iframe = soup.find("iframe", src=re.compile(r"(dailymotion|youtube|player\.vimeo)"))
            if iframe and iframe.get("src"):
                return iframe["src"]
            video = soup.find("video")
            if video:
                source = video.find("source")
                if source and source.get("src"):
                    return source["src"]
            for a in soup.find_all("a", href=True):
                if a["href"].endswith(".mp4"):
                    return a["href"]
            return None
        except Exception as e:
            logger.exception(f"Failed to extract direct video URL: {e}")
            return None

    # ----------------------------------------------------------------------
    # Link sync support
    # ----------------------------------------------------------------------

    def discover_series_url(self, anime: Anime) -> Tuple[str, str]:
        """Perform fresh discovery (no cache) and return (status, url)."""
        url = self._get_series_url(anime, force_discover=True)
        if url:
            return "found", url
        else:
            return "not_found", ""