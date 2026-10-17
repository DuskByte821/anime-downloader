"""Tests for scraper.search — offline, fixture-based."""

from pathlib import Path

import pytest

from scraper import search as search_mod


FIXTURES = Path(__file__).parent / "fixtures" / "lucifer"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# HTML path
# ----------------------------------------------------------------------

def test_html_extracts_only_result_container():
    html = _fixture("search_sidebar.html")
    pairs = search_mod.search_via_html(html)
    urls = [u for _, u, _ in pairs]
    assert "/anime/perfect-world-new/" in urls
    assert "/anime/renegade-immortal-xian-ni/" in urls


def test_html_excludes_sidebar_and_widgets():
    html = _fixture("search_sidebar.html")
    pairs = search_mod.search_via_html(html)
    urls = [u for _, u, _ in pairs]
    assert "/anime/swallowed-star-season-4-new/" not in urls
    assert "/anime/battle-through-the-heavens-season-5-new/" not in urls


def test_html_prefers_heading_title():
    html = _fixture("search_sidebar.html")
    pairs = {(u): (t) for t, u, _ in search_mod.search_via_html(html)}
    assert pairs["/anime/perfect-world-new/"] == "Perfect World [Wanmei Shijie]"


def test_html_deduplicates_by_url():
    html = """
    <div class="listupd">
      <a href="/anime/x/"><h2>X</h2></a>
      <a href="/anime/x/"><h2>X</h2></a>
    </div>
    """
    pairs = search_mod.search_via_html(html)
    assert len(pairs) == 1


def test_html_empty_returns_empty():
    assert search_mod.search_via_html("") == []
    assert search_mod.search_via_html("<html></html>") == []


def test_html_ignores_non_anime_hrefs():
    html = """
    <div class="listupd">
      <a href="/genres/action/"><h2>Action</h2></a>
      <a href="/anime/real-series/"><h2>Real Series</h2></a>
    </div>
    """
    pairs = search_mod.search_via_html(html)
    assert [u for _, u, _ in pairs] == ["/anime/real-series/"]


def test_html_latest_is_zero():
    html = _fixture("search_sidebar.html")
    pairs = search_mod.search_via_html(html)
    assert all(latest == 0 for _, _, latest in pairs)


# ----------------------------------------------------------------------
# AJAX path
# ----------------------------------------------------------------------

def test_ajax_parses_theme_envelope(monkeypatch):
    def fake_post(url, data):
        return {"anime": [{"all": [
            {
                "post_title": "Perfect World [Wanmei Shijie]",
                "post_link": "https://luciferdonghua.in/anime/perfect-world-new/",
                "post_latest": "288",
                "post_type": "DONGHUA",
            }
        ]}]}
    monkeypatch.setattr(search_mod, "post_json", fake_post)
    pairs = search_mod.search_via_ajax("perfect world")
    assert pairs == [(
        "Perfect World [Wanmei Shijie]",
        "/anime/perfect-world-new/",
        288,
    )]


def test_ajax_latest_non_numeric_returns_zero(monkeypatch):
    def fake_post(url, data):
        return {"anime": [{"all": [
            {
                "post_title": "Perfect World Movie",
                "post_link": "/anime/perfect-world-movie/",
                "post_latest": "PT-02",
                "post_type": "Movie",
            }
        ]}]}
    monkeypatch.setattr(search_mod, "post_json", fake_post)
    pairs = search_mod.search_via_ajax("perfect world")
    assert pairs == [(
        "Perfect World Movie",
        "/anime/perfect-world-movie/",
        0,
    )]


def test_ajax_flattens_results_list(monkeypatch):
    def fake_post(url, data):
        return {"results": [
            {"post_title": "X", "post_link": "/anime/x/", "post_latest": "5"}
        ]}
    monkeypatch.setattr(search_mod, "post_json", fake_post)
    pairs = search_mod.search_via_ajax("x")
    assert pairs == [("X", "/anime/x/", 5)]


def test_ajax_returns_none_on_request_failure(monkeypatch):
    monkeypatch.setattr(search_mod, "post_json", lambda u, d: None)
    assert search_mod.search_via_ajax("anything") is None


def test_ajax_returns_empty_list_for_no_results(monkeypatch):
    monkeypatch.setattr(search_mod, "post_json",
                        lambda u, d: {"anime": [{"all": []}]})
    assert search_mod.search_via_ajax("nothing") == []


def test_ajax_unparseable_envelope_returns_empty(monkeypatch):
    """The theme sometimes returns JSON without the anime key.
    Treat that as 'no results' rather than an error — the HTML
    fallback wouldn't find anything either."""
    monkeypatch.setattr(search_mod, "post_json", lambda u, d: {"foo": "bar"})
    assert search_mod.search_via_ajax("anything") == []


def test_ajax_strips_absolute_host(monkeypatch):
    def fake_post(url, data):
        return {"anime": [{"all": [
            {"post_title": "X",
             "post_link": "https://luciferdonghua.in/anime/x/",
             "post_latest": "1"}
        ]}]}
    monkeypatch.setattr(search_mod, "post_json", fake_post)
    pairs = search_mod.search_via_ajax("x")
    assert pairs == [("X", "/anime/x/", 1)]


# ----------------------------------------------------------------------
# Integration: search_anime prefers AJAX, falls back to HTML
# ----------------------------------------------------------------------

def test_search_anime_uses_ajax_first(monkeypatch):
    from scraper.luciferdonghua import LuciferDonghuaScraper

    ajax_called = {"count": 0}
    html_called = {"count": 0}

    def fake_ajax(q):
        ajax_called["count"] += 1
        return [("Anything Result", "/anime/anything-result/", 0)]

    def fake_html(h):
        html_called["count"] += 1
        return []

    monkeypatch.setattr("scraper.search.search_via_ajax", fake_ajax)
    monkeypatch.setattr("scraper.search.search_via_html", fake_html)

    scraper = LuciferDonghuaScraper()
    results = scraper.search_anime("anything")
    assert ajax_called["count"] == 1
    assert html_called["count"] == 0
    assert len(results) == 1
    assert results[0][1] == "https://luciferdonghua.in/anime/anything-result/"


def test_search_anime_falls_back_to_html(monkeypatch):
    from scraper.luciferdonghua import LuciferDonghuaScraper
    import scraper.luciferdonghua as luc

    monkeypatch.setattr("scraper.search.search_via_ajax", lambda q: None)
    monkeypatch.setattr(
        "scraper.search.search_via_html",
        lambda h: [("Anything Result", "/anime/anything-result/", 0)],
    )
    monkeypatch.setattr(luc, "fetch_html", lambda u: "<html></html>")

    scraper = LuciferDonghuaScraper()
    results = scraper.search_anime("anything")
    assert len(results) == 1
    assert results[0][1] == "https://luciferdonghua.in/anime/anything-result/"
    assert results[0][2] == 0


def test_search_anime_returns_empty_when_all_methods_fail(monkeypatch):
    from scraper.luciferdonghua import LuciferDonghuaScraper
    import scraper.luciferdonghua as luc

    monkeypatch.setattr("scraper.search.search_via_ajax", lambda q: None)
    monkeypatch.setattr(luc, "fetch_html", lambda u: None)

    scraper = LuciferDonghuaScraper()
    assert scraper.search_anime("anything") == []


def test_search_anime_keeps_ajax_latest(monkeypatch):
    from scraper.luciferdonghua import LuciferDonghuaScraper

    def fake_ajax(q):
        return [("Perfect World", "/anime/perfect-world-new/", 288)]

    monkeypatch.setattr("scraper.search.search_via_ajax", fake_ajax)
    scraper = LuciferDonghuaScraper()
    results = scraper.search_anime("perfect world")
    assert results == [(
        "Perfect World",
        "https://luciferdonghua.in/anime/perfect-world-new/",
        288,
    )]


def test_search_anime_filters_non_matching_titles(monkeypatch):
    from scraper.luciferdonghua import LuciferDonghuaScraper
    monkeypatch.setattr(
        "scraper.search.search_via_ajax",
        lambda q: [
            ("Perfect World", "/anime/perfect-world-new/", 288),
            ("Wealth and Wonder", "/anime/wealth-and-wonder-2025/", 12),
        ],
    )
    scraper = LuciferDonghuaScraper()
    results = scraper.search_anime("perfect world")
    urls = [u for _, u, _ in results]
    assert "https://luciferdonghua.in/anime/perfect-world-new/" in urls
    assert "https://luciferdonghua.in/anime/wealth-and-wonder-2025/" not in urls


# ----------------------------------------------------------------------
# _matches_query
# ----------------------------------------------------------------------

def test_matches_query_accepts_exact():
    from scraper.search import _matches_query
    assert _matches_query("Perfect World [Wanmei Shijie]", "perfect world")
    assert _matches_query("perfect world", "Perfect World")


def test_matches_query_rejects_unrelated():
    from scraper.search import _matches_query
    assert not _matches_query("Wealth and Wonder", "perfect world")
    assert not _matches_query("Martial Universe Season 5", "perfect world")


def test_matches_query_ignores_short_tokens():
    from scraper.search import _matches_query
    assert _matches_query("Tomb of the Fallen Gods", "Tomb")
    assert _matches_query("Anything", "a")