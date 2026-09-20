"""Tests for the link cache manager."""

from pathlib import Path

from link_manager import LinkManager


def _make(tmp_path: Path) -> LinkManager:
    return LinkManager(file_path=tmp_path / "links.txt")


def test_set_and_get_found(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("Perfect World", "luciferdonghua", "season 1", "found", "https://x/anime/pw/")
    entry = lm.get("Perfect World", "luciferdonghua", "season 1")
    assert entry is not None
    status, url, explicit = entry
    assert status == "found"
    assert url == "https://x/anime/pw/"
    assert explicit is False


def test_set_and_get_not_found(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("Nonexistent", "luciferdonghua", "", "not_found", "")
    entry = lm.get("Nonexistent", "luciferdonghua", "")
    assert entry is not None
    assert entry[0] == "not_found"
    assert entry[1] == ""


def test_case_insensitive_lookup(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("Perfect World", "luciferdonghua", "season 1", "found", "https://x/")
    # Lookup with different case + extra whitespace
    entry = lm.get("perfect world", "luciferdonghua", "season 1")
    assert entry is not None
    assert entry[0] == "found"


def test_explicit_flag_is_persisted(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site", "", "found", "https://a/", explicit=True)
    # Re-open
    lm2 = LinkManager(file_path=tmp_path / "links.txt")
    entry = lm2.get("A", "site", "")
    assert entry == ("found", "https://a/", True)


def test_invalidate_skips_explicit(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site", "", "found", "https://a/", explicit=True)
    lm.invalidate("A", "site", "")
    assert lm.get("A", "site", "") is not None  # still there


def test_invalidate_removes_non_explicit(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site", "", "found", "https://a/", explicit=False)
    lm.invalidate("A", "site", "")
    assert lm.get("A", "site", "") is None


def test_get_url_returns_none_for_not_found(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site", "", "not_found", "")
    assert lm.get_url("A", "site", "") is None


def test_get_url_returns_url_for_found(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site", "", "found", "https://a/")
    assert lm.get_url("A", "site", "") == "https://a/"


def test_legacy_format_migration(tmp_path: Path):
    """Old `anime::url` lines should migrate to the new format on load."""
    f = tmp_path / "links.txt"
    f.write_text("Perfect World::https://x/anime/pw/\n")
    lm = LinkManager(file_path=f)
    entry = lm.get("Perfect World", "luciferdonghua", "")
    assert entry is not None
    assert entry[0] == "found"
    assert entry[1] == "https://x/anime/pw/"


def test_multiple_sites_do_not_collide(tmp_path: Path):
    lm = _make(tmp_path)
    lm.set("A", "site1", "", "found", "https://s1/")
    lm.set("A", "site2", "", "not_found", "")
    assert lm.get("A", "site1", "") == ("found", "https://s1/", False)
    assert lm.get("A", "site2", "") == ("not_found", "", False)