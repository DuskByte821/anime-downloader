"""Track and retry failed downloads."""

from pathlib import Path
from typing import List, Tuple

from config import FAILED_LOG_FILE


def load_failed() -> List[Tuple[str, int]]:
    """Return list of (anime_name, episode) that failed."""
    if not FAILED_LOG_FILE.exists():
        return []
    entries = []
    with FAILED_LOG_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("::")
            if len(parts) >= 2:
                try:
                    ep = int(parts[1])
                    entries.append((parts[0], ep))
                except ValueError:
                    pass
    return entries


def save_failed(entries: List[Tuple[str, int]]) -> None:
    """Save failed entries to log."""
    FAILED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FAILED_LOG_FILE.open("w") as f:
        for name, ep in entries:
            f.write(f"{name}::{ep}\n")


def add_failed(name: str, episode: int) -> None:
    """Append a failed download to the log."""
    entries = load_failed()
    if (name, episode) not in entries:
        entries.append((name, episode))
        save_failed(entries)


def remove_success(name: str, episode: int) -> None:
    """Remove an entry after successful download."""
    entries = load_failed()
    entries = [e for e in entries if not (e[0] == name and e[1] == episode)]
    save_failed(entries)