"""Tests for the download queue lifecycle (mocked download + updater)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from models import Anime
from queue_manager import DownloadQueue, DownloadJob
import queue_manager


def test_process_job_success_updates_downloaded(monkeypatch, tmp_path):
    fake_update = MagicMock()
    monkeypatch.setattr(queue_manager, "update_watchlist", fake_update)
    monkeypatch.setattr(queue_manager, "download_file", lambda *a, **k: True)
    monkeypatch.setattr(queue_manager, "remove_success", lambda *a, **k: None)

    q = DownloadQueue(max_workers=1)
    anime = Anime(name="A", downloaded=5, watched=3)
    watchlist = [anime]

    q.add_job(anime, 6, watchlist, tmp_path / "ep6.mp4", "http://x/6")

    # Give the worker time to process
    import time
    for _ in range(50):
        status = q.get_status()
        if any(s[0] == "completed" for s in status.values()):
            break
        time.sleep(0.05)

    assert fake_update.called
    call_args = fake_update.call_args
    assert call_args[0][1] is anime
    assert call_args[0][2] == 6


def test_process_job_failure_tracks_failed(monkeypatch, tmp_path):
    fake_update = MagicMock()
    fake_add_failed = MagicMock()
    monkeypatch.setattr(queue_manager, "update_watchlist", fake_update)
    monkeypatch.setattr(queue_manager, "download_file", lambda *a, **k: False)
    monkeypatch.setattr(queue_manager, "add_failed", fake_add_failed)

    q = DownloadQueue(max_workers=1)
    anime = Anime(name="A", downloaded=5, watched=3)
    watchlist = [anime]

    q.add_job(anime, 6, watchlist, tmp_path / "ep6.mp4", "http://x/6")

    import time
    for _ in range(50):
        status = q.get_status()
        if any(s[0] == "failed" for s in status.values()):
            break
        time.sleep(0.05)

    assert fake_add_failed.called
    assert not fake_update.called