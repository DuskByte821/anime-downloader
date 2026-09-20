"""Tests for episode progress logic."""

from episode import get_missing_episodes


def test_missing_when_latest_greater():
    assert get_missing_episodes(10, 13) == [11, 12, 13]


def test_missing_when_equal():
    assert get_missing_episodes(10, 10) == []


def test_missing_when_latest_less():
    assert get_missing_episodes(10, 5) == []


def test_missing_from_zero():
    assert get_missing_episodes(0, 3) == [1, 2, 3]


def test_missing_ignores_watched_progress():
    """
    get_missing_episodes is driven by `downloaded`, not `watched`.
    Passing a lower value (which would be `watched`) yields more missing episodes;
    passing a higher value (which is `downloaded`) yields fewer.
    """
    # downloaded=12 -> missing 13
    assert get_missing_episodes(12, 13) == [13]
    # watched=8 -> missing 9..13 (more episodes)
    assert get_missing_episodes(8, 13) == [9, 10, 11, 12, 13]