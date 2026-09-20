"""Tests for watchlist parsing, saving, and migration."""

from pathlib import Path

from models import Anime
from watchlist import (
    load_watchlist,
    save_watchlist,
    parse_entry,
    format_anime_line,
    normalize_name,
)


# ----------------------------------------------------------------------
# parse_entry
# ----------------------------------------------------------------------

def test_parse_name_only():
    name, season, downloaded, watched = parse_entry("Perfect World")
    assert name == "Perfect World"
    assert season is None
    assert downloaded == 0
    assert watched == 0


def test_parse_season_only():
    name, season, downloaded, watched = parse_entry("Perfect World::season 1")
    assert name == "Perfect World"
    assert season == "season 1"
    assert downloaded == 0
    assert watched == 0


def test_parse_legacy_episode_only():
    name, season, downloaded, watched = parse_entry("Test::episode 25")
    assert name == "Test"
    assert season is None
    assert downloaded == 25
    assert watched == 0


def test_parse_legacy_season_episode():
    name, season, downloaded, watched = parse_entry("Test::season 1::episode 25")
    assert name == "Test"
    assert season == "season 1"
    assert downloaded == 25
    assert watched == 0


def test_parse_new_format_with_season():
    name, season, downloaded, watched = parse_entry(
        "Test::season 1::downloaded 25::watched 20"
    )
    assert name == "Test"
    assert season == "season 1"
    assert downloaded == 25
    assert watched == 20


def test_parse_new_format_without_season():
    name, season, downloaded, watched = parse_entry("Test::downloaded 10::watched 7")
    assert name == "Test"
    assert season is None
    assert downloaded == 10
    assert watched == 7


def test_parse_bracketed_episode_uses_primary():
    _, _, downloaded, _ = parse_entry("The Great Ruler::season 2::episode 07[59]")
    assert downloaded == 7


def test_parse_bracketed_large():
    _, _, downloaded, _ = parse_entry("Twin Martial Spirits::episode 103[188]")
    assert downloaded == 103


# ----------------------------------------------------------------------
# format_anime_line
# ----------------------------------------------------------------------

def test_format_with_season():
    a = Anime(name="Test", season="season 1", downloaded=25, watched=20)
    assert format_anime_line(a) == "Test::season 1::downloaded 25::watched 20"


def test_format_without_season():
    a = Anime(name="Test", season=None, downloaded=10, watched=7)
    assert format_anime_line(a) == "Test::downloaded 10::watched 7"


def test_format_preserves_original_name_case():
    a = Anime(name="SwAlLoWeD sTaR", season=None, downloaded=1, watched=0)
    assert format_anime_line(a).startswith("SwAlLoWeD sTaR::")


# ----------------------------------------------------------------------
# normalize_name
# ----------------------------------------------------------------------

def test_normalize_case():
    assert normalize_name("Swallowed Star") == "swallowed star"
    assert normalize_name("SWALLOWED STAR") == "swallowed star"
    assert normalize_name("SwAlLoWeD sTaR") == "swallowed star"


def test_normalize_whitespace():
    assert normalize_name("  Swallowed   Star  ") == "swallowed star"
    assert normalize_name("Swallowed\tStar") == "swallowed star"


# ----------------------------------------------------------------------
# Round-trip
# ----------------------------------------------------------------------

def test_round_trip_preserves_values(tmp_path: Path):
    f = tmp_path / "anime.txt"
    original = [
        Anime(name="A", season="season 1", downloaded=10, watched=8, status="watching"),
        Anime(name="B", season=None, downloaded=5, watched=5, status="completed"),
    ]
    save_watchlist(original, f)
    reloaded = load_watchlist(f)

    assert len(reloaded) == 2

    a = next(x for x in reloaded if x.name == "A")
    assert a.season == "season 1"
    assert a.downloaded == 10
    assert a.watched == 8
    assert a.status == "watching"

    b = next(x for x in reloaded if x.name == "B")
    assert b.season is None
    assert b.downloaded == 5
    assert b.watched == 5
    assert b.status == "completed"


def test_downloaded_154_watched_151_round_trips(tmp_path: Path):
    f = tmp_path / "anime.txt"
    original = [Anime(name="Test", downloaded=154, watched=151)]
    save_watchlist(original, f)
    [reloaded] = load_watchlist(f)
    assert reloaded.downloaded == 154
    assert reloaded.watched == 151


# ----------------------------------------------------------------------
# Legacy / migration
# ----------------------------------------------------------------------

def test_load_legacy_file_migrates_episode(tmp_path: Path):
    f = tmp_path / "anime.txt"
    f.write_text(
        "watching\n"
        "Old Anime::season 1::episode 25\n"
        "Another::episode 4\n"
        "\n"
        "completed\n"
        "Finished::episode 12\n"
    )
    result = load_watchlist(f)
    assert len(result) == 3

    old = next(x for x in result if x.name == "Old Anime")
    assert old.downloaded == 25
    assert old.watched == 0
    assert old.status == "watching"

    another = next(x for x in result if x.name == "Another")
    assert another.downloaded == 4
    assert another.watched == 0

    finished = next(x for x in result if x.name == "Finished")
    assert finished.downloaded == 12
    assert finished.watched == 0
    assert finished.status == "completed"


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------

def test_watching_and_completed_sections_loaded(tmp_path: Path):
    f = tmp_path / "anime.txt"
    f.write_text(
        "watching\n"
        "A::downloaded 5::watched 3\n"
        "\n"
        "completed\n"
        "B::downloaded 10::watched 10\n"
    )
    result = load_watchlist(f)
    a = next(x for x in result if x.name == "A")
    b = next(x for x in result if x.name == "B")
    assert a.status == "watching"
    assert b.status == "completed"


# ----------------------------------------------------------------------
# Malformed input
# ----------------------------------------------------------------------

def test_empty_lines_ignored(tmp_path: Path):
    f = tmp_path / "anime.txt"
    f.write_text("\n\nwatching\n\nA::downloaded 1::watched 1\n\n\n")
    result = load_watchlist(f)
    assert len(result) == 1


def test_blank_lines_dont_corrupt_other_entries(tmp_path: Path):
    f = tmp_path / "anime.txt"
    f.write_text(
        "watching\n"
        "A::downloaded 1::watched 1\n"
        "\n"
        "B::downloaded 2::watched 1\n"
    )
    result = load_watchlist(f)
    names = sorted(x.name for x in result)
    assert names == ["A", "B"]


def test_load_nonexistent_file_returns_empty(tmp_path: Path):
    f = tmp_path / "does_not_exist.txt"
    assert load_watchlist(f) == []