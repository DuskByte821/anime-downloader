"""Tests for downloader behavior (no real network)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import downloader
from downloader import download_file


def test_existing_valid_file_skipped(tmp_path, monkeypatch):
    """If the destination exists and is valid, don't re-download."""
    dest = tmp_path / "ep.mp4"
    dest.write_bytes(b"x" * (25 * 1024 * 1024))  # 25 MB

    fake_ytdlp = MagicMock()
    monkeypatch.setattr(downloader, "_download_with_ytdlp", fake_ytdlp)
    monkeypatch.setattr(downloader, "_yt_dlp_available", lambda: True)

    result = download_file("http://x/", dest, anime_name="A", episode=1)
    assert result is True
    assert not fake_ytdlp.called


def test_small_existing_file_deleted_then_downloaded(tmp_path, monkeypatch):
    """A file smaller than the preview threshold should be deleted."""
    dest = tmp_path / "ep.mp4"
    dest.write_bytes(b"x" * 100)

    called = {}
    def fake_ytdlp(url, dest_, retries, episode):
        called["called"] = True
        return True

    monkeypatch.setattr(downloader, "_download_with_ytdlp", fake_ytdlp)
    monkeypatch.setattr(downloader, "_yt_dlp_available", lambda: True)

    result = download_file("http://x/", dest, anime_name="A", episode=1)
    assert called.get("called") is True


def test_ytdlp_success_creates_file(tmp_path, monkeypatch):
    """If yt-dlp subprocess succeeds and creates the file, download_file returns True."""
    dest = tmp_path / "ep.mp4"

    class FakeProc:
        returncode = 0

    def fake_run(cmd, cwd=None, check=False, **kwargs):
        # Simulate yt-dlp creating the file
        (Path(cwd) / dest.name).write_bytes(b"x" * (25 * 1024 * 1024))
        return FakeProc()

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.setattr(downloader, "_yt_dlp_available", lambda: True)

    # Need YT_DLP_OPTIONS not to interfere
    result = download_file("http://x/", dest, anime_name="A", episode=1)
    assert result is True
    assert dest.exists()


def test_ytdlp_failure_returns_false(tmp_path, monkeypatch):
    dest = tmp_path / "ep.mp4"

    class FakeProc:
        returncode = 1

    def fake_run(cmd, cwd=None, check=False, **kwargs):
        return FakeProc()

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.setattr(downloader, "_yt_dlp_available", lambda: True)
    monkeypatch.setattr(downloader.time, "sleep", lambda *a, **k: None)

    result = download_file("http://x/", dest, anime_name="A", episode=1)
    assert result is False