"""Persist rejected search candidates for inspection."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from config import LOGS_DIR

logger = logging.getLogger(__name__)

REJECTED_LOG = LOGS_DIR / "rejected_links.txt"


def log_candidates(
    anime_name: str,
    season: str,
    accepted_url: str,
    candidates: List[Tuple[int, str, str, str]],  # (score, title, url, reason)
) -> None:
    """
    Append a block to rejected_links.txt with all candidates for one anime.

    `reason` is a short string like "ok", "score<70", "non-anime", "long-title".
    The accepted candidate is marked so you can see the context in which
    rejections occurred.
    """
    REJECTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append(f"=== {anime_name} | {season or '—'} | {ts} ===")
    lines.append(f"accepted: {accepted_url or '(none)'}")
    if not candidates:
        lines.append("(no candidates returned by search)")
    else:
        for score, title, url, reason in candidates:
            mark = "ACCEPT" if url == accepted_url else "reject"
            lines.append(f"  [{mark}] score={score:>4}  reason={reason:<12}  {url}")
            lines.append(f"           title: {title}")
    lines.append("")

    try:
        with REJECTED_LOG.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        logger.warning(f"Could not write rejected log: {e}")