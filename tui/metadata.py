"""TUI-facing metadata accessor. Delegates to the scraper, which
handles caching and rate-limiting."""

from scraper.luciferdonghua import LuciferDonghuaScraper


def fetch_series_metadata(series_url: str) -> dict:
    return LuciferDonghuaScraper().get_series_metadata(series_url)