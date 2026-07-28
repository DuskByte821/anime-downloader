"""Episode comparison logic."""

from typing import List


def get_missing_episodes(watched: int, latest: int) -> List[int]:
    """
    Return a list of episode numbers that are missing.
    If latest <= watched, returns empty list.
    """
    if latest <= watched:
        return []
    return list(range(watched + 1, latest + 1))


def next_episode_to_download(watched: int, latest: int) -> int:
    """Return the next episode number to download, or None if none."""
    if latest <= watched:
        return None
    return watched + 1