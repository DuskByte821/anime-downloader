"""Tests for 4-section watchlists and dual anime/donghua files."""

from pathlib import Path

import pytest

from config import WATCHLIST_FILES
from models import Anime
from watchlist import (
    VALID_STATUSES, load_watchlist, save_watchlist,
    change_status, format_anime_line,
)


# ----------------------------------------------------------------------
# Four-section parsing
# ----------------------------------------------------------------------

def test_all_four_sections_parsed(tmp_path):
    f = tmp_path / "anime.txt"
    f.write_text(
        "watching\n"
        "A::downloaded 10::watched 5\n"
        "\n"
        "ended\n"
        "B::downloaded 20::watched 20\n"
        "\n"
        "dropped\n"
        "C::downloaded 5::watched 1\n"
        "\n"
        "completed\n"
        "D::downloaded 30::watched 30\n"
    )
    result = load_watchlist(f)
    by_name = {a.name: a for a in result}
    assert by_name["A"].status == "watching"
    assert by_name["B"].status == "ended"
    assert by_name["C"].status == "dropped"
    assert by_name["D"].status == "completed"


def test_writer_emits_all_four_sections_even_when_empty(tmp_path):
    f = tmp_path / "anime.txt"
    save_watchlist([], f)
    text = f.read_text()
    for status in VALID_STATUSES:
        assert status in text


def test_writer_preserves_section_order(tmp_path):
    f = tmp_path / "anime.txt"
    save_watchlist([
        Anime(name="A", status="completed", downloaded=1, watched=1),
        Anime(name="B", status="watching", downloaded=1, watched=1),
    ], f)
    text = f.read_text()
    idx = {s: text.index(s) for s in VALID_STATUSES}
    assert idx["watching"] < idx["ended"] < idx["dropped"] < idx["completed"]


def test_round_trip_with_all_statuses(tmp_path):
    f = tmp_path / "anime.txt"
    original = [
        Anime(name="W", status="watching", downloaded=10, watched=8),
        Anime(name="E", status="ended", downloaded=20, watched=20),
        Anime(name="D", status="dropped", downloaded=5, watched=1),
        Anime(name="C", status="completed", downloaded=30, watched=30),
    ]
    save_watchlist(original, f)
    reloaded = {a.name: a for a in load_watchlist(f)}
    assert reloaded["W"].status == "watching"
    assert reloaded["W"].downloaded == 10
    assert reloaded["W"].watched == 8
    assert reloaded["E"].status == "ended"
    assert reloaded["D"].status == "dropped"
    assert reloaded["C"].status == "completed"


def test_entries_without_season_still_work(tmp_path):
    f = tmp_path / "anime.txt"
    f.write_text(
        "watching\n"
        "The Supreme Body Refining Master::downloaded 13::watched 0\n"
    )
    [a] = load_watchlist(f)
    assert a.name == "The Supreme Body Refining Master"
    assert a.season is None
    assert a.downloaded == 13


# ----------------------------------------------------------------------
# Status transitions
# ----------------------------------------------------------------------

def test_change_status_moves_entry():
    a = Anime(name="X", status="watching", downloaded=5, watched=3)
    lst = [a]
    assert change_status(lst, a, "ended") is True
    assert a.status == "ended"
    # Preserved fields
    assert a.downloaded == 5
    assert a.watched == 3
    # No duplicates
    assert len(lst) == 1


def test_change_status_returns_false_if_same():
    a = Anime(name="X", status="watching")
    assert change_status([a], a, "watching") is False


def test_change_status_returns_false_for_unknown():
    a = Anime(name="X", status="watching")
    assert change_status([a], a, "bogus") is False


def test_change_status_all_transitions():
    for src in VALID_STATUSES:
        for dst in VALID_STATUSES:
            a = Anime(name="X", status=src)
            lst = [a]
            change_status(lst, a, dst)
            assert a.status == dst
            assert len(lst) == 1


# ----------------------------------------------------------------------
# Dual files
# ----------------------------------------------------------------------

def test_anime_and_donghua_files_are_separate(tmp_path, monkeypatch):
    anime_f = tmp_path / "anime.txt"
    donghua_f = tmp_path / "donghua.txt"
    monkeypatch.setitem(WATCHLIST_FILES, "anime", anime_f)
    monkeypatch.setitem(WATCHLIST_FILES, "donghua", donghua_f)

    save_watchlist([Anime(name="AnimeShow", status="watching")], anime_f)
    save_watchlist([Anime(name="DonghuaShow", status="watching")], donghua_f)

    assert [a.name for a in load_watchlist(anime_f)] == ["AnimeShow"]
    assert [a.name for a in load_watchlist(donghua_f)] == ["DonghuaShow"]


def test_saving_donghua_does_not_touch_anime(tmp_path):
    anime_f = tmp_path / "anime.txt"
    donghua_f = tmp_path / "donghua.txt"

    save_watchlist([Anime(name="A", status="watching")], anime_f)
    original = anime_f.read_text()

    save_watchlist([Anime(name="D", status="watching")], donghua_f)

    assert anime_f.read_text() == original