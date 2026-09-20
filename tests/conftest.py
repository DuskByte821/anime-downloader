"""Shared pytest fixtures for the anime-downloader test suite."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from models import Anime


# ----------------------------------------------------------------------
# Temp paths
# ----------------------------------------------------------------------

@pytest.fixture
def tmp_watchlist(tmp_path: Path) -> Path:
    return tmp_path / "anime.txt"


@pytest.fixture
def tmp_links(tmp_path: Path) -> Path:
    return tmp_path / "links.txt"


# ----------------------------------------------------------------------
# Sample Anime objects
# ----------------------------------------------------------------------

@pytest.fixture
def sample_anime() -> Anime:
    return Anime(name="Perfect World", season="season 1", downloaded=284, watched=270)


@pytest.fixture
def sample_watching() -> list[Anime]:
    return [
        Anime(name="Perfect World", season="season 1", downloaded=284, watched=270),
        Anime(name="Renegade Immortal", season="season 1", downloaded=158, watched=156),
        Anime(name="Swallowed Star", season="season 4", downloaded=156, watched=150),
    ]


@pytest.fixture
def sample_completed() -> list[Anime]:
    return [
        Anime(name="Jade Dynasty", season="season 3", downloaded=26, watched=26,
              status="completed"),
        Anime(name="Dragon Raja", season="season 2", downloaded=24, watched=24,
              status="completed"),
    ]


# ----------------------------------------------------------------------
# HTTP mocking helper
# ----------------------------------------------------------------------

class MockResponse:
    """Minimal mock of requests.Response."""

    def __init__(self, text: str = "", status_code: int = 200, url: str = ""):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code} for {self.url}")

    def json(self):
        return {}


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Provide a controllable mock of requests.get.

    Usage:
        def test_x(mock_requests):
            mock_requests.set_url("https://...", text="<html>...</html>")
            ...
    """
    responses = {}

    def fake_get(url, *args, **kwargs):
        if url in responses:
            return responses[url]
        # default: 404
        return MockResponse(text="", status_code=404, url=url)

    monkeypatch.setattr("requests.get", fake_get)

    class Controller:
        def set_url(self, url: str, text: str = "", status_code: int = 200):
            responses[url] = MockResponse(text=text, status_code=status_code, url=url)

        def set_url_404(self, url: str):
            responses[url] = MockResponse(text="", status_code=404, url=url)

    return Controller()


# ----------------------------------------------------------------------
# Fixture HTML loader
# ----------------------------------------------------------------------

@pytest.fixture
def load_fixture():
    """Load an HTML fixture from tests/fixtures/."""
    base = Path(__file__).parent / "fixtures"

    def _load(relative_path: str) -> str:
        return (base / relative_path).read_text(encoding="utf-8")

    return _load