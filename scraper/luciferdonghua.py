"""Scraper for Lucifer Donghua – deterministic discovery with link manager."""
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import (
    Dict,
    List, 
    Optional, 
    Tuple,
)
import requests
from bs4 import BeautifulSoup
from models import Anime
from .base import Scraper
from link_manager import LinkManager
from scraper.rejected_log import log_candidates
from config import (
    LUCIFER_DONGHUA_BASE,
    MAX_MIRRORS, SOURCE_PRIORITY, DIRECT_MEDIA_EXTENSIONS,
    YTDLP_METADATA_TIMEOUT, MIN_EPISODE_DURATION_SECONDS,
)
from scraper.http import fetch_html

logger = logging.getLogger(__name__)

@dataclass
class SourceCandidate:
    kind: str            # "iframe" | "direct_media"
    url: str
    provider: str        # "dailymotion", "rumble", "other", "archive", "direct"

    # -----------------------------------------------------------------------
    #  Modular Functions
    # -----------------------------------------------------------------------
def _strip_meta(title: str) -> str:
    """Remove bracketed alt-titles and parenthesized years for comparison."""
    t = re.sub(r"\[[^\]]*\]", "", title)
    t = re.sub(r"\(\s*\d{4}\s*\)", "", t)
    return t.strip()

def _empty_metadata() -> dict:
    return {
        "title": None, "alt_titles": [], "description": "",
        "status": None, "network": None, "studio": None,
        "released": None, "duration": None, "season": None,
        "country": None, "type": None, "episodes": None,
        "fansub": None, "genres": [],
    }

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
        from scraper.search import (
            search_via_ajax, search_via_html, _matches_query,
        )

        pairs = search_via_ajax(query)
        method = "ajax"
        if pairs is None:
            search_url = f"{self.BASE_URL}/?s={query.replace(' ', '+')}"
            text = fetch_html(search_url)
            if text is None:
                logger.warning(f"[search] query={query!r} all methods failed")
                return []
            pairs = search_via_html(text)
            method = "html"

        logger.debug(
            f"[search] query={query!r} method={method} results={len(pairs)}"
        )

        results: List[Tuple[str, str, int]] = []
        filtered = 0
        for title, href, latest in pairs:
            if not _matches_query(title, query):
                filtered += 1
                logger.debug(
                    f"[search] candidate filtered: title={title!r} reason='no-query-token'"
                )
                continue
            if not href.startswith("http"):
                href = self.BASE_URL + href
            results.append((title, href, latest))

        if filtered:
            logger.debug(f"[search] filtered {filtered} irrelevant candidate(s)")

        return results
                    
    def _fetch_latest_episode_from_series(self, series_url: str) -> int:
        try:
            text = fetch_html(series_url)
            if text is None:
                return 0
            soup = BeautifulSoup(text, "html.parser")
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
            log_candidates(anime.name, anime.season or "", "", [])
            return None

        base_name = self._normalize_name(_strip_meta(anime.name))
        season_num = self._extract_season_number(anime.season)

        scored = []  # (score, title, url, reason)
        for title, url, _ in results:
            display_title = title
            title_for_cmp = _strip_meta(title)
            norm_title = self._normalize_name(title_for_cmp)

            score = 0
            reason_parts = []

            # Name match
            if norm_title == base_name:
                score += 100
                reason_parts.append("exact-name")
            elif base_name in norm_title or norm_title in base_name:
                score += 50
                reason_parts.append("substring")
            else:
                score += 10
                reason_parts.append("weak-name")

            # Season handling
            m = re.search(r"season\s*(\d+)", title_for_cmp, re.I)
            season_in_title = int(m.group(1)) if m else None
            m = re.search(r"season-(\d+)", url, re.I)
            season_in_url = int(m.group(1)) if m else None
            site_season = season_in_title if season_in_title is not None else season_in_url

            if season_num is None or season_num == 1:
                if site_season is not None and site_season == season_num:
                    score += 20
                    reason_parts.append("season-match")
            else:
                if site_season == season_num:
                    score += 60
                    reason_parts.append("season-match")
                elif site_season is None:
                    score -= 20
                    reason_parts.append("season-missing")
                else:
                    score -= 40
                    reason_parts.append(f"season-mismatch({site_season})")

            # Heuristics
            if len(title_for_cmp.split()) > 8:
                score -= 20
                reason_parts.append("long-title")
            if not self._is_likely_anime_result(title_for_cmp, url):
                score -= 50
                reason_parts.append("non-anime")

            scored.append((score, display_title, url, "+".join(reason_parts)))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_title, best_url, best_reason = scored[0]

        MIN_ACCEPT_SCORE = 70
        if best_score < MIN_ACCEPT_SCORE:
            logger.warning(
                f"No strong match for {anime.name} (best score {best_score}); recording not_found"
            )
            log_candidates(anime.name, anime.season or "", "", scored)
            return None

        logger.info(f"Best match for {anime.name}: {best_title} (score {best_score})")
        log_candidates(anime.name, anime.season or "", best_url, scored)
        return best_url
    # ----------------------------------------------------------------------
    # Episode discovery
    # ----------------------------------------------------------------------

    def _build_episode_map(self, series_url: str) -> Dict[int, str]:
        """
        Return {episode_number: episode_url}.

        Uses a disk cache with a 1-day TTL. On fetch failure with a stale
        cache present, returns the stale cache and logs a warning. On
        fetch failure with no cache, returns {}.
        """
        from scraper.cache import read_episode_map, write_episode_map
        from scraper.http import fetch_html

        cached, fresh = read_episode_map(series_url)
        if cached is not None and fresh:
            logger.debug(f"[epmap] fresh cache hit for {series_url}")
            return {int(k): v for k, v in cached.items()}

        if cached is not None:
            logger.info(f"[epmap] stale cache for {series_url}; refreshing")

        text = fetch_html(series_url)
        if text is None:
            if cached is not None:
                logger.warning(
                    f"[epmap] fetch failed; using stale cache for {series_url}"
                )
                return {int(k): v for k, v in cached.items()}
            return {}

        soup = BeautifulSoup(text, "html.parser")
        ep_map: Dict[int, str] = {}

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
                ep_text = a.get_text(strip=True)
                ep_num, _ = self._parse_episode_string(ep_text)
                if ep_num == 0:
                    continue
            ep_map[ep_num] = href

        if ep_map:
            write_episode_map(series_url, ep_map)
        else:
            logger.warning(f"[epmap] parsed empty for {series_url}, not caching")

        return ep_map
    
    # ----------------------------------------------------------------------
    # MetaData
    # ----------------------------------------------------------------------
    def get_series_metadata(self, series_url: str) -> dict:
        """
        Return series metadata, using disk cache when possible.

        On cache miss: fetch and write.
        On fresh cache: return as-is.
        On stale cache: attempt fetch; on failure, return stale.
        On fetch failure with no cache: return empty structure.
        """
        from scraper.cache import read_series_meta, write_series_meta

        cached, fresh = read_series_meta(series_url)
        if cached is not None and fresh:
            logger.debug(f"[meta] fresh cache hit for {series_url}")
            return cached

        if cached is not None:
            logger.info(f"[meta] stale cache for {series_url}; refreshing")

        text = fetch_html(series_url, use_cache=True)
        if text is None:
            if cached is not None:
                logger.warning(f"[meta] fetch failed; using stale cache for {series_url}")
                return cached
            logger.warning(f"[meta] fetch failed and no cache for {series_url}")
            return _empty_metadata()

        from scraper.metadata_parser import parse_series_metadata
        parsed = parse_series_metadata(text)

        # Only write on successful parse (parsed has a title or description)
        if parsed.get("title") or parsed.get("description"):
            write_series_meta(series_url, parsed)
        else:
            logger.warning(f"[meta] parsed empty for {series_url}, not caching")

        return parsed

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
        """
        Return the direct iframe/video URL from the episode page.
        Used so yt-dlp doesn't have to parse the page itself (avoids
        the generic extractor's broken src parsing on this theme).
        """
        episode_url = self.get_download_link(anime, episode)
        try:
            text = fetch_html(episode_url)
            if text is None:
                return None
            soup = BeautifulSoup(text, "html.parser")
            def _clean(src: str) -> Optional[str]:
                if not src:
                    return None
                src = src.strip()
                # Reject anything with embedded whitespace, quotes, or `>` —
                # those are symptoms of mis-parsed attributes.
                if not src.startswith("http"):
                    return None
                if any(ch in src for ch in (" ", '"', "'", ">", "<")):
                    return None
                return src

            # 1. Standard iframe with src=
            iframe = soup.find(
                "iframe",
                src=re.compile(r"(dailymotion|youtube|player\.vimeo)", re.I),
            )
            if iframe:
                cleaned = _clean(iframe.get("src", ""))
                if cleaned:
                    return cleaned

            # 2. Lazy-loaded iframes sometimes use data-src=
            iframe = soup.find(
                "iframe",
                attrs={"data-src": re.compile(r"dailymotion", re.I)},
            )
            if iframe:
                cleaned = _clean(iframe.get("data-src", ""))
                if cleaned:
                    return cleaned

            # 3. <video><source src=...>
            video = soup.find("video")
            if video:
                source = video.find("source")
                if source:
                    cleaned = _clean(source.get("src", ""))
                    if cleaned:
                        return cleaned

            # 4. .mp4 link
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.endswith(".mp4"):
                    cleaned = _clean(href)
                    if cleaned:
                        return cleaned

            return None
        except Exception as e:
            logger.exception(f"Failed to extract direct video URL for {anime.name} ep {episode}: {e}")
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

    # ----------------------------------------------------------------------
    # Extraction helpers
    # ----------------------------------------------------------------------

    def _classify_iframe(self, url: str) -> Optional[str]:
        """Return the provider name if the URL is a known iframe host."""
        lower = url.lower()
        for token in SOURCE_PRIORITY:
            if token in lower:
                return token.split(".")[0]     # "dailymotion", "rumble", etc.
        return None


    def _extract_iframe_sources(self, soup) -> List[SourceCandidate]:
        """Return all iframe-based sources on the page."""
        out: List[SourceCandidate] = []
        for iframe in soup.find_all("iframe"):
            src = (iframe.get("src") or iframe.get("data-src") or "").strip()
            if not src or not src.startswith("http"):
                continue
            # Reject the garbage strings we saw earlier (with embedded whitespace/quotes)
            if any(ch in src for ch in (" ", '"', "'", ">", "<")):
                continue
            provider = self._classify_iframe(src) or "other"
            out.append(SourceCandidate(kind="iframe", url=src, provider=provider))
        return out


    def _extract_direct_media(self, soup) -> List[SourceCandidate]:
        """Return all direct .mp4/.mkv/etc. URLs on the page."""
        out: List[SourceCandidate] = []

        # <video><source src=...>
        for video in soup.find_all("video"):
            for source in video.find_all("source"):
                src = (source.get("src") or "").strip()
                if src.startswith("http") and src.lower().endswith(DIRECT_MEDIA_EXTENSIONS):
                    provider = "archive" if "archive.org" in src.lower() else "direct"
                    out.append(SourceCandidate(kind="direct_media", url=src, provider=provider))

        # <a href="...mp4">
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and href.lower().endswith(DIRECT_MEDIA_EXTENSIONS):
                provider = "archive" if "archive.org" in href.lower() else "direct"
                out.append(SourceCandidate(kind="direct_media", url=href, provider=provider))

        return out


    def _rank_sources(self, candidates: List[SourceCandidate]) -> List[SourceCandidate]:
        """
        Rank candidates: dailymotion > rumble > other iframe > direct (non-archive)
        > archive.org. Deduplicate by URL.
        """
        def score(c: SourceCandidate) -> int:
            if c.provider == "dailymotion":
                return 0
            if c.provider == "rumble":
                return 1
            if c.kind == "iframe" and c.provider != "archive":
                return 2
            if c.kind == "direct_media" and c.provider != "archive":
                return 3
            if c.provider == "archive":
                return 4
            return 5

        seen = set()
        unique = []
        for c in sorted(candidates, key=score):
            if c.url in seen:
                continue
            seen.add(c.url)
            unique.append(c)
        return unique


    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def _fetch_episode_soup(self, episode_url: str):
        """Fetch an episode page and return its soup, or None on failure."""
        try:
            text = fetch_html(episode_url)
            if text is None:
                logger.warning(f"[resolve] fetch failed for {episode_url}")
                return None
            return BeautifulSoup(text, "html.parser")
        except Exception as e:
            logger.warning(f"[resolve] failed to fetch {episode_url}: {e}")
            return None


    def get_playable_sources(self, anime: Anime, episode: int) -> List[SourceCandidate]:
        """
        Collect candidate sources from the episode page and its mirrors
        (/v/1 .. /v/MAX_MIRRORS). Ranked best-first.
        """
        base_url = self.get_download_link(anime, episode)
        if not base_url:
            return []

        all_candidates: List[SourceCandidate] = []

        # Base page
        soup = self._fetch_episode_soup(base_url)
        if soup:
            all_candidates.extend(self._extract_iframe_sources(soup))
            all_candidates.extend(self._extract_direct_media(soup))

        # Mirrors: append /v/N/ to the base URL (strip trailing slash first)
        base = base_url.rstrip("/")
        for n in range(1, MAX_MIRRORS + 1):
            mirror_url = f"{base}/v/{n}"
            soup = self._fetch_episode_soup(mirror_url)
            if not soup:
                continue
            found = (
                self._extract_iframe_sources(soup)
                + self._extract_direct_media(soup)
            )
            if found:
                logger.debug(f"[resolve] {anime.name} ep {episode} mirror /v/{n}: {len(found)} source(s)")
                all_candidates.extend(found)

        ranked = self._rank_sources(all_candidates)
        logger.info(
            f"[resolve] {anime.name} ep {episode}: {len(all_candidates)} candidate(s) "
            f"from {1 + MAX_MIRRORS} page(s); top = "
            f"{ranked[0].provider if ranked else 'none'}"
        )
        return ranked


    def resolve_episode_source(self, anime: Anime, episode: int):
        """
        Pre-flight: return (ok, kind, url, duration, reason).

        - ok=True  -> a playable source was found and passes duration filter
        - ok=False -> reason explains why (no_source / preview_only / fetch_failed)
        """
        candidates = self.get_playable_sources(anime, episode)
        if not candidates:
            return (False, "", "", None, "no_source")

        for cand in candidates:
            # For iframe sources, probe duration via yt-dlp -J.
            if cand.kind == "iframe":
                duration = self._probe_duration(cand.url)
                if duration is None:
                    # Can't determine duration — accept but log
                    logger.info(
                        f"[resolve] {anime.name} ep {episode}: "
                        f"{cand.provider} duration unknown, accepting"
                    )
                    return (True, cand.kind, cand.url, None, "ok_unknown_duration")
                if duration < MIN_EPISODE_DURATION_SECONDS:
                    logger.info(
                        f"[resolve] {anime.name} ep {episode}: "
                        f"{cand.provider} duration={duration}s < "
                        f"{MIN_EPISODE_DURATION_SECONDS}s → preview, trying next"
                    )
                    continue
                return (True, cand.kind, cand.url, duration, "ok")

            # Direct media: no metadata endpoint; accept and rely on post-download size check.
            if cand.kind == "direct_media":
                logger.info(
                    f"[resolve] {anime.name} ep {episode}: "
                    f"direct media from {cand.provider}, accepting (size check after download)"
                )
                return (True, cand.kind, cand.url, None, "ok_direct")

        # Every candidate was a preview or unusable
        return (False, "", "", None, "preview_only")


    def _probe_duration(self, url: str) -> Optional[int]:
        """
        Run `yt-dlp -J --skip-download <url>` and return duration in seconds.
        Returns None on failure or if the field is missing.
        """
        import json
        import subprocess
        from config import YTDLP_METADATA_TIMEOUT

        try:
            proc = subprocess.run(
                ["yt-dlp", "-J", "--skip-download", "--no-warnings", url],
                capture_output=True, text=True, timeout=YTDLP_METADATA_TIMEOUT, check=True,
            )
            info = json.loads(proc.stdout)
            d = info.get("duration")
            return int(d) if d else None
        except Exception as e:
            logger.debug(f"[resolve] duration probe failed for {url}: {e}")
            return None
