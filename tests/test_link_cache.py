"""Tests for link_cache.py — persistence, scanning, content-type separation."""

import downloader
import link_cache
from models import Anime
from watchlist import load_watchlist, save_watchlist


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

def test_parse_valid_file(env, write_cache):
    links, _ = env
    p = write_cache(
        links / "renegade_immortal.txt",
        title="Renegade Immortal", ctype="donghua", source="luciferdonghua",
        episodes={1: "https://e/1", 2: "https://e/2"},
    )
    c = link_cache.parse_link_file(p)
    assert c is not None
    assert c.title == "Renegade Immortal"
    assert c.content_type == "donghua"
    assert c.source == "luciferdonghua"
    assert c.episodes == {1: "https://e/1", 2: "https://e/2"}
    assert c.latest_episode() == 2


def test_parse_title_falls_back_to_filename(env, write_cache):
    links, _ = env
    p = write_cache(
        links / "my_new_show.txt", ctype="anime",
        episodes={1: "https://e/1"},
    )
    c = link_cache.parse_link_file(p)
    assert c is not None
    assert c.title == "My New Show"


def test_parse_missing_type_returns_none(env, write_cache):
    links, _ = env
    p = write_cache(links / "x.txt", title="X", episodes={1: "https://e/1"})
    assert link_cache.parse_link_file(p) is None


def test_parse_unknown_type_returns_none(env, write_cache):
    links, _ = env
    p = write_cache(links / "x.txt", title="X", ctype="movie",
                    episodes={1: "https://e/1"})
    assert link_cache.parse_link_file(p) is None


def test_parse_empty_file_returns_none(env, write_cache):
    links, _ = env
    p = write_cache(links / "empty.txt", raw="")
    assert link_cache.parse_link_file(p) is None


def test_parse_malformed_lines_skipped(env, write_cache):
    links, _ = env
    p = write_cache(
        links / "mixed.txt",
        raw=(
            "# title: Mixed\n"
            "# type: anime\n"
            "\n"
            "1::https://e/1\n"
            "not-a-line\n"
            "abc::https://e/2\n"
            "2::\n"
            "3::https://e/3\n"
        ),
    )
    c = link_cache.parse_link_file(p)
    assert c is not None
    assert c.episodes == {1: "https://e/1", 3: "https://e/3"}


def test_parse_invalid_url_skipped(env, write_cache):
    links, _ = env
    p = write_cache(
        links / "bad.txt",
        raw=(
            "# title: Bad\n"
            "# type: anime\n"
            "1::ftp://nope/1\n"
            "2::https://e/2\n"
        ),
    )
    c = link_cache.parse_link_file(p)
    assert c is not None
    assert c.episodes == {2: "https://e/2"}


# ----------------------------------------------------------------------
# Scanning — new / existing / idempotent
# ----------------------------------------------------------------------

def test_scan_creates_new_entry(env, write_cache):
    links, paths = env
    write_cache(links / "new_series.txt", title="New Series",
                ctype="donghua", episodes={1: "https://e/1"})

    report = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert report.scanned == 1
    assert report.added == [("New Series", "donghua")]
    assert report.already_tracked == []
    assert report.invalid == []

    wl = load_watchlist(paths["donghua"])
    assert len(wl) == 1
    assert wl[0].name == "New Series"
    assert wl[0].status == "watching"
    assert wl[0].season == "season 1"
    assert wl[0].downloaded == 0
    assert wl[0].watched == 0


def test_scan_existing_no_duplicate(env, write_cache):
    links, paths = env
    save_watchlist(
        [Anime(name="New Series", season="season 1",
               downloaded=10, watched=8)],
        paths["donghua"],
    )
    write_cache(links / "new_series.txt", title="New Series",
                ctype="donghua", episodes={1: "https://e/1"})

    report = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert report.added == []
    assert report.already_tracked == [("New Series", "donghua")]

    wl = load_watchlist(paths["donghua"])
    assert len(wl) == 1
    assert wl[0].downloaded == 10
    assert wl[0].watched == 8


def test_scan_idempotent(env, write_cache):
    links, paths = env
    write_cache(links / "a.txt", title="A", ctype="anime",
                episodes={1: "https://e/1"})

    link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)
    r2 = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert r2.added == []
    assert r2.already_tracked == [("A", "anime")]
    assert len(load_watchlist(paths["anime"])) == 1


# ----------------------------------------------------------------------
# Content-type separation
# ----------------------------------------------------------------------

def test_scan_donghua_does_not_touch_anime(env, write_cache):
    links, paths = env
    write_cache(links / "d.txt", title="Donghua Show", ctype="donghua",
                episodes={1: "https://e/1"})

    link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert len(load_watchlist(paths["donghua"])) == 1
    assert not paths["anime"].exists() or load_watchlist(paths["anime"]) == []


def test_scan_anime_does_not_touch_donghua(env, write_cache):
    links, paths = env
    write_cache(links / "a.txt", title="Anime Show", ctype="anime",
                episodes={1: "https://e/1"})

    link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert len(load_watchlist(paths["anime"])) == 1
    assert not paths["donghua"].exists() or load_watchlist(paths["donghua"]) == []


# ----------------------------------------------------------------------
# No side effects
# ----------------------------------------------------------------------

def test_scan_preserves_cache_file(env, write_cache):
    links, paths = env
    p = write_cache(links / "a.txt", title="A", ctype="anime",
                    episodes={1: "https://e/1"})
    before = p.read_text(encoding="utf-8")

    link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    assert p.exists()
    assert p.read_text(encoding="utf-8") == before


def test_scan_does_not_mutate_progress(env, write_cache):
    links, paths = env
    save_watchlist(
        [Anime(name="A", season="season 1", downloaded=159, watched=158)],
        paths["donghua"],
    )
    write_cache(
        links / "a.txt", title="A", ctype="donghua",
        episodes={i: f"https://e/{i}" for i in range(1, 161)},
    )

    link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)

    wl = load_watchlist(paths["donghua"])
    assert len(wl) == 1
    assert wl[0].downloaded == 159
    assert wl[0].watched == 158


def test_scan_never_invokes_downloader(env, write_cache, monkeypatch):
    """Scan must never call download_file or the download queue."""
    links, paths = env
    write_cache(links / "a.txt", title="A", ctype="donghua",
                episodes={1: "https://e/1"})

    def boom(*a, **kw):
        raise AssertionError("downloader invoked during scan!")

    monkeypatch.setattr(downloader, "download_file", boom)

    # Also guard the queue: accessing main.QUEUE is a proxy for a
    # download-side import path that the scanner must not touch.
    import main as main_module
    monkeypatch.setattr(main_module, "download_episode_background", boom)

    report = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)
    assert report.added == [("A", "donghua")]


# ----------------------------------------------------------------------
# New file discovery between scans
# ----------------------------------------------------------------------

def test_scan_detects_new_file_after_first_scan(env, write_cache):
    links, paths = env
    write_cache(links / "a.txt", title="A", ctype="anime",
                episodes={1: "https://e/1"})

    r1 = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)
    assert r1.added == [("A", "anime")]

    write_cache(links / "b.txt", title="B", ctype="anime",
                episodes={1: "https://e/1"})

    r2 = link_cache.scan_links_dir(links_dir=links, watchlist_paths=paths)
    assert r2.added == [("B", "anime")]
    assert r2.already_tracked == [("A", "anime")]

    names = {a.name for a in load_watchlist(paths["anime"])}
    assert names == {"A", "B"}


# ----------------------------------------------------------------------
# Lookup (used by main.get_download_link_with_fallback)
# ----------------------------------------------------------------------

def test_find_cache_for_is_case_insensitive(env, write_cache):
    links, _ = env
    write_cache(links / "ren.txt", title="Renegade Immortal",
                ctype="donghua", episodes={1: "https://e/1"})

    assert link_cache.find_cache_for(
        "renegade immortal", "donghua", links_dir=links
    ) is not None
    assert link_cache.find_cache_for(
        "RENEGADE IMMORTAL", "donghua", links_dir=links
    ) is not None


def test_find_cache_for_rejects_wrong_content_type(env, write_cache):
    links, _ = env
    write_cache(links / "ren.txt", title="Renegade Immortal",
                ctype="donghua", episodes={1: "https://e/1"})

    assert link_cache.find_cache_for(
        "Renegade Immortal", "anime", links_dir=links
    ) is None


def test_get_cached_url_hit_and_miss(env, write_cache):
    links, _ = env
    write_cache(links / "ren.txt", title="Renegade Immortal",
                ctype="donghua",
                episodes={1: "https://e/1", 2: "https://e/2"})

    assert link_cache.get_cached_url(
        "Renegade Immortal", "donghua", 2, links_dir=links
    ) == "https://e/2"
    assert link_cache.get_cached_url(
        "Renegade Immortal", "donghua", 99, links_dir=links
    ) is None