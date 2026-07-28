"""Scraper for luciferdonghua.com (or luciferdonghua.in)."""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from models import Anime
from .base import Scraper
from config import HEADERS, TIMEOUT

logger = logging.getLogger(__name__)


class LuciferDonghuaScraper(Scraper):
    """Scraper for LuciferDonghua (luciferdonghua.com)."""

    BASE_URL = "https://luciferdonghua.com"  # change if needed

    def get_latest_episode(self, anime: Anime) -> int:
        """
        Search for the anime and return the latest episode number.
        """
        try:
            # Construct search URL
            # Typical pattern: https://luciferdonghua.com/search?q=name
            search_keyword = anime.name.replace(" ", "+")
            search_url = f"{self.BASE_URL}/search?q={search_keyword}"

            resp = requests.get(search_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Find first result link
            result = soup.select_one("div.result-item a")  # adjust selector
            if not result:
                logger.warning(f"No search result for {anime.name}")
                return 0

            anime_url = result.get("href")
            if not anime_url:
                return 0
            if not anime_url.startswith("http"):
                anime_url = self.BASE_URL + anime_url

            # Get episode list
            resp2 = requests.get(anime_url, headers=HEADERS, timeout=TIMEOUT)
            resp2.raise_for_status()
            soup2 = BeautifulSoup(resp2.text, "html.parser")

            # Extract episode numbers from links (e.g., /episode/1, /episode/2, ...)
            ep_links = soup2.select("a[href*='/episode/']")
            if not ep_links:
                # Try to find links with "episode" in text
                ep_links = soup2.find_all("a", href=re.compile(r"/episode/"))
            if not ep_links:
                return 0

            numbers = []
            for a in ep_links:
                href = a.get("href")
                match = re.search(r"/episode/(\d+)", href)
                if match:
                    numbers.append(int(match.group(1)))
                else:
                    # Try text
                    text = a.get_text(strip=True)
                    match = re.search(r"(\d+)", text)
                    if match:
                        numbers.append(int(match.group(1)))
            if not numbers:
                return 0
            return max(numbers)

        except Exception as e:
            logger.exception(f"Error fetching latest episode for {anime.name}: {e}")
            return 0

    def get_download_link(self, anime: Anime, episode: int) -> str:
        """
        Get the direct download link for a specific episode.
        """
        try:
            # Build episode URL
            anime_slug = anime.name.lower().replace(" ", "-")
            anime_slug = re.sub(r"[^a-z0-9-]", "", anime_slug)
            episode_url = f"{self.BASE_URL}/{anime_slug}/episode/{episode}"

            resp = requests.get(episode_url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for download links
            # Often there's a "Download" button or direct link
            download_link = None
            # Find all <a> tags with href ending in .mp4, .mkv, etc.
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.endswith((".mp4", ".mkv", ".avi", ".webm")):
                    download_link = href
                    break
                # Or check text for "Download"
                if "download" in a.get_text(strip=True).lower():
                    download_link = href
                    break

            if not download_link:
                # Sometimes the link is in a <source> or <video> tag
                video = soup.find("video")
                if video and video.get("src"):
                    download_link = video["src"]

            if download_link:
                if not download_link.startswith("http"):
                    download_link = self.BASE_URL + download_link
                return download_link

            raise RuntimeError(f"No download link found for {anime.name} episode {episode}")

        except Exception as e:
            logger.exception(f"Error getting download link for {anime.name} ep {episode}: {e}")
            raise