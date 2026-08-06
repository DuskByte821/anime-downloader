"""Scraper package."""

from .base import Scraper
from .luciferdonghua import LuciferDonghuaScraper
from .cartoonsarea import CartoonsAreaScraper

__all__ = ["Scraper", "LuciferDonghuaScraper", "CartoonsAreaScraper"]