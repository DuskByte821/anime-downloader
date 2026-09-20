"""
End-to-end integration test with mocked network.

Watchlist → link manager → scraper → download → updater → watchlist.
"""

from pathlib import Path

import pytest

from link_manager import LinkManager
from models import Anime
from scraper.luciferdonghua import LuciferDonghuaScraper
import updater
from watchlist import load_watchlist, save_watchlist


BASE = "https://luciferdonghua.in"


@pytest.fixture
def isolated_watchlist(tmp_path, monkeypatch):
    """Redirect WATCHLIST_FILE to a temp file for the test."""
    wl_path = tmp_path / "anime.txt"
    monkeypatch.setattr("config.WATCHLIST_FILE", wl_path)
    return wl_path


def test_full_pipeline(tmp_path, mock_requests, load_fixture, monkeypatch):
    wl_path = tmp_path / "anime.txt"
    links_path = tmp_path / "links.txt"

    # --- 1. Initial watchlist ------------------------------------------
    save_watchlist(
        [Anime(name="Perfect World", season="season 1",
               downloaded=283, watched=280, status="watching")],
        wl_path,
    )

    # --- 2. Set up scraper with temp LinkManager ----------------------
    lm = LinkManager(file_path=links_path)
    scraper = LuciferDonghuaScraper(link_manager=lm)

    # --- 3. Mock all HTTP endpoints -----------------------------------
    mock_requests.set_url(
        f"{BASE}/?s=Perfect+World",
        text=load_fixture("luciferdonghua/search_perfect_world.html"),
    )
    mock_requests.set_url(
        f"{BASE}/anime/perfect-world-new/",
        text=load_fixture("luciferdonghua/series_perfect_world.html"),
    )
    mock_requests.set_url(
        f"{BASE}/anime/renegade-immortal-xian-ni/", text="<html></html>"
    )
    mock_requests.set_url(
        f"{BASE}/anime/perfect-world-special/", text="<html></html>"
    )

    # --- 4. Discovery --------------------------------------------------
    anime = load_watchlist(wl_path)[0]
    status, url = scraper.discover_series_url(anime)
    assert status == "found"
    lm.set(anime.name, "luciferdonghua", anime.season or "", status, url)

    # --- 5. Episode discovery ------------------------------------------
    latest = scraper.get_latest_episode(anime)
    assert latest == 284

    # --- 6. Mock the downloader + updater save -------------------------
    import queue_manager
    def fake_download(url, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * (25 * 1024 * 1024))
        return True
    monkeypatch.setattr(queue_manager, "download_file", fake_download)
    monkeypatch.setattr(queue_manager, "remove_success", lambda *a, **k: None)

    # Patch save/load in updater to use wl_path
    import updater as upd_mod
    monkeypatch.setattr(
        upd_mod, "save_watchlist",
        lambda lst, fp=None: save_watchlist(lst, wl_path),
    )
    monkeypatch.setattr(
        upd_mod, "load_watchlist",
        lambda fp=None: load_watchlist(wl_path),
    )

    # --- 7. Run the update --------------------------------------------
    upd_mod.update_watchlist([anime], anime, 284)

    # --- 8. Reload and verify -----------------------------------------
    reloaded = load_watchlist(wl_path)[0]
    assert reloaded.downloaded == 284
    assert reloaded.watched == 280  # unchanged
    assert reloaded.season == "season 1"
    assert reloaded.status == "watching"