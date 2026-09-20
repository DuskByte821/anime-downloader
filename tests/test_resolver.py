"""Tests for scraper/resolver helpers."""

from unittest.mock import MagicMock

from scraper import resolver


def test_extract_download_link_finds_download_anchor(monkeypatch):
    html = '<html><body><a href="/downloads/ep1.mp4">Download</a></body></html>'

    class FakeResp:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    link = resolver.extract_download_link_from_page("http://x/page")
    assert link == "/downloads/ep1.mp4"


def test_extract_download_link_returns_none_on_no_match(monkeypatch):
    html = "<html><body><p>No links here</p></body></html>"

    class FakeResp:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp())
    link = resolver.extract_download_link_from_page("http://x/page")
    assert link is None