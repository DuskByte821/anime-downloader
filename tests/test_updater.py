"""Tests for the updater – downloaded advances, watched does not."""

from unittest.mock import MagicMock

from models import Anime
import updater


def test_downloaded_advances_watched_unchanged(monkeypatch):
    save_calls = []

    def fake_save(anime_list, file_path=None):
        save_calls.append(list(anime_list))

    monkeypatch.setattr(updater, "save_watchlist", fake_save)
    # reload verification returns the updated anime
    fake_reloaded = [Anime(name="A", downloaded=11, watched=8)]
    monkeypatch.setattr(updater, "load_watchlist", lambda file_path=None: fake_reloaded)

    anime = Anime(name="A", downloaded=10, watched=8)
    watchlist = [anime]
    updater.update_watchlist(watchlist, anime, 11)

    assert anime.downloaded == 11
    assert anime.watched == 8
    assert len(save_calls) == 1


def test_update_does_not_lower_downloaded(monkeypatch):
    """Duplicate / lower update is not prevented, but must not change watched."""
    monkeypatch.setattr(updater, "save_watchlist", lambda *a, **k: None)
    monkeypatch.setattr(
        updater, "load_watchlist",
        lambda file_path=None: [Anime(name="A", downloaded=10, watched=8)],
    )
    anime = Anime(name="A", downloaded=10, watched=8)
    updater.update_watchlist([anime], anime, 10)
    assert anime.downloaded == 10
    assert anime.watched == 8


def test_update_watched_never_touched(monkeypatch):
    monkeypatch.setattr(updater, "save_watchlist", lambda *a, **k: None)
    monkeypatch.setattr(
        updater, "load_watchlist",
        lambda file_path=None: [Anime(name="A", downloaded=100, watched=50)],
    )
    anime = Anime(name="A", downloaded=50, watched=50)
    updater.update_watchlist([anime], anime, 100)
    assert anime.downloaded == 100
    assert anime.watched == 50  # not advanced to 100