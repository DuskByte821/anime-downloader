"""Tests for the Anime data model."""

from models import Anime


def test_defaults():
    a = Anime(name="Test")
    assert a.name == "Test"
    assert a.season is None
    assert a.downloaded == 0
    assert a.watched == 0
    assert a.status == "watching"


def test_downloaded_and_watched_are_independent():
    a = Anime(name="Test", downloaded=154, watched=151)
    assert a.downloaded == 154
    assert a.watched == 151
    assert a.downloaded != a.watched


def test_downloaded_does_not_affect_watched():
    a = Anime(name="Test", downloaded=10, watched=5)
    a.downloaded = 20
    assert a.watched == 5


def test_status_can_be_completed():
    a = Anime(name="Test", status="completed")
    assert a.status == "completed"


def test_equality_by_value():
    a = Anime(name="Test", downloaded=1, watched=0)
    b = Anime(name="Test", downloaded=1, watched=0)
    assert a == b


def test_distinct_downloaded_breaks_equality():
    a = Anime(name="Test", downloaded=1)
    b = Anime(name="Test", downloaded=2)
    assert a != b