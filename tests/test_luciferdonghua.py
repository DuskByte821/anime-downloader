"""Tests for the LuciferDonghua scraper (offline, fixture-based)."""

import pytest

from link_manager import LinkManager
from models import Anime
from scraper.luciferdonghua import LuciferDonghuaScraper


BASE = "https://luciferdonghua.in"


@pytest.fixture
def scraper(tmp_path):
    lm = LinkManager(file_path=tmp_path / "links.txt")
    return LuciferDonghuaScraper(link_manager=lm)


# ----------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------

def test_search_returns_all_anime_links(scraper, mock_requests, load_fixture):
    mock_requests.set_url(
        f"{BASE}/?s=Perfect+World",
        text=load_fixture("luciferdonghua/search_perfect_world.html"),
    )
    results = scraper.search_anime("Perfect World")
    urls = [r[1] for r in results]
    assert any("/anime/perfect-world-new/" in u for u in urls)
    assert any("/anime/renegade-immortal-xian-ni/" in u for u in urls)


def test_search_empty(scraper, mock_requests, load_fixture):
    mock_requests.set_url(
        f"{BASE}/?s=Nonexistent",
        text=load_fixture("luciferdonghua/search_empty.html"),
    )
    results = scraper.search_anime("Nonexistent")
    assert results == []


# ----------------------------------------------------------------------
# Canonical series URL selection
# ----------------------------------------------------------------------

def test_discover_series_url_picks_exact_match(scraper, mock_requests, load_fixture):
    mock_requests.set_url(
        f"{BASE}/?s=Perfect+World",
        text=load_fixture("luciferdonghua/search_perfect_world.html"),
    )
    # The scraper will fetch each candidate series page; provide the exact one
    mock_requests.set_url(
        f"{BASE}/anime/perfect-world-new/",
        text=load_fixture("luciferdonghua/series_perfect_world.html"),
    )
    mock_requests.set_url(
        f"{BASE}/anime/renegade-immortal-xian-ni/",
        text="<html></html>",
    )
    mock_requests.set_url(
        f"{BASE}/anime/perfect-world-special/",
        text="<html></html>",
    )

    anime = Anime(name="Perfect World", season="season 1")
    status, url = scraper.discover_series_url(anime)
    assert status == "found"
    assert url == f"{BASE}/anime/perfect-world-new/"


def test_discover_series_url_not_found(scraper, mock_requests, load_fixture):
    mock_requests.set_url(
        f"{BASE}/?s=Does+Not+Exist",
        text=load_fixture("luciferdonghua/search_empty.html"),
    )
    anime = Anime(name="Does Not Exist")
    status, url = scraper.discover_series_url(anime)
    assert status == "not_found"
    assert url == ""


def test_discover_series_url_returns_real_url_not_guessed(
    scraper, mock_requests, load_fixture
):
    """The discovered URL must come from the HTML, not be manufactured."""
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

    anime = Anime(name="Perfect World")
    _, url = scraper.discover_series_url(anime)
    assert url == f"{BASE}/anime/perfect-world-new/"
    # Not a guessed URL
    assert url != f"{BASE}/anime/perfect-world/"


# ----------------------------------------------------------------------
# Season matching
# ----------------------------------------------------------------------

def test_season_aware_match_prefers_season_specific_page(
    scraper, mock_requests, load_fixture
):
    search_html = (
        '<div class="items">'
        '<div class="item"><a href="/anime/the-demon-hunter/">The Demon Hunter</a></div>'
        '<div class="item"><a href="/anime/the-demon-hunter-season-2/">The Demon Hunter Season 2</a></div>'
        '<div class="item"><a href="/anime/the-demon-hunter-season-3/">The Demon Hunter Season 3</a></div>'
        "</div>"
    )
    mock_requests.set_url(f"{BASE}/?s=The+Demon+Hunter", text=search_html)
    mock_requests.set_url(
        f"{BASE}/anime/the-demon-hunter-season-2/",
        text=load_fixture("luciferdonghua/series_demon_hunter_s2.html"),
    )
    mock_requests.set_url(
        f"{BASE}/anime/the-demon-hunter-season-3/", text="<html></html>"
    )
    mock_requests.set_url(
        f"{BASE}/anime/the-demon-hunter/", text="<html></html>"
    )

    anime = Anime(name="The Demon Hunter", season="season 2")
    status, url = scraper.discover_series_url(anime)
    assert status == "found"
    assert url == f"{BASE}/anime/the-demon-hunter-season-2/"


# ----------------------------------------------------------------------
# Episode extraction
# ----------------------------------------------------------------------

def test_episode_map_from_series_page(scraper, mock_requests, load_fixture):
    series_url = f"{BASE}/anime/perfect-world-new/"
    mock_requests.set_url(
        series_url, text=load_fixture("luciferdonghua/series_perfect_world.html")
    )
    ep_map = scraper._build_episode_map(series_url)
    assert 1 in ep_map
    assert 2 in ep_map
    assert 7 in ep_map
    assert 103 in ep_map
    assert 284 in ep_map


def test_episode_map_uses_real_links(scraper, mock_requests, load_fixture):
    series_url = f"{BASE}/anime/perfect-world-new/"
    mock_requests.set_url(
        series_url, text=load_fixture("luciferdonghua/series_perfect_world.html")
    )
    ep_map = scraper._build_episode_map(series_url)
    # URLs must come from the HTML, not be built by appending "-episode-N"
    assert "perfect-world-wanmei-shijie-episode-103" in ep_map[103]


# ----------------------------------------------------------------------
# Episode selection
# ----------------------------------------------------------------------

def test_get_download_link_selects_correct_episode(
    scraper, mock_requests, load_fixture, tmp_path
):
    # Cache a series URL directly in the link manager
    scraper.link_manager.set(
        "Perfect World", "luciferdonghua", "", "found",
        f"{BASE}/anime/perfect-world-new/",
    )
    mock_requests.set_url(
        f"{BASE}/anime/perfect-world-new/",
        text=load_fixture("luciferdonghua/series_perfect_world.html"),
    )
    anime = Anime(name="Perfect World")
    url = scraper.get_download_link(anime, 103)
    assert "episode-103" in url


# ----------------------------------------------------------------------
# Episode numbering (primary vs bracketed)
# ----------------------------------------------------------------------

def test_parse_episode_string_primary_only():
    p, s = LuciferDonghuaScraper._parse_episode_string("Episode 103 [188]")
    assert p == 103
    assert s == 188


def test_parse_episode_string_zero_padded():
    p, s = LuciferDonghuaScraper._parse_episode_string("Episode 07")
    assert p == 7
    assert s is None


def test_parse_episode_string_with_source():
    p, s = LuciferDonghuaScraper._parse_episode_string("Episode 7 [59]")
    assert p == 7
    assert s == 59


def test_parse_episode_string_bare():
    p, s = LuciferDonghuaScraper._parse_episode_string("Episode 1")
    assert p == 1
    assert s is None


def test_episode_number_from_bracketed_is_primary(scraper, mock_requests, load_fixture):
    """
    Regression test: 'Episode 103 [188]' must map to episode 103,
    not 188.
    """
    series_url = f"{BASE}/anime/perfect-world-new/"
    mock_requests.set_url(
        series_url, text=load_fixture("luciferdonghua/series_perfect_world.html")
    )
    ep_map = scraper._build_episode_map(series_url)
    assert 103 in ep_map
    assert 188 not in ep_map


# ----------------------------------------------------------------------
# Failure: parser error is not NOT_FOUND
# ----------------------------------------------------------------------

def test_search_failure_does_not_raise(scraper, mock_requests):
    """A network error during search should not crash discover_series_url."""
    mock_requests.set_url_404(f"{BASE}/?s=Anything")
    anime = Anime(name="Anything")
    status, url = scraper.discover_series_url(anime)
    assert status == "not_found"
    assert url == ""


# ----------------------------------------------------------------------
# Link manager integration
# ----------------------------------------------------------------------

def test_cached_link_is_reused(scraper, mock_requests):
    cached_url = f"{BASE}/anime/perfect-world-new/"
    scraper.link_manager.set(
        "Perfect World", "luciferdonghua", "", "found", cached_url
    )
    # No mock for search URL is set – if scraper tried to search, it would 404.
    anime = Anime(name="Perfect World")
    url = scraper._get_series_url(anime)
    assert url == cached_url


def test_explicit_cached_link_not_invalidated(scraper, tmp_path):
    scraper.link_manager.set(
        "Perfect World", "luciferdonghua", "", "found",
        f"{BASE}/anime/perfect-world-new/", explicit=True,
    )
    scraper.link_manager.invalidate("Perfect World", "luciferdonghua", "")
    assert (
        scraper.link_manager.get_url("Perfect World", "luciferdonghua", "")
        == f"{BASE}/anime/perfect-world-new/"
    )