"""Download with yt-dlp, with fuzzy post-download file lookup."""

import logging
import subprocess
import time
import re
from pathlib import Path
from typing import Optional, Set

import requests
from utils.filename import (
    episode_pattern,
    episode_candidates_from_url,
    anime_matches_filename )
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from config import (
    CHUNK_SIZE,
    HEADERS,
    RETRY_COUNT,
    RETRY_DELAY,
    TIMEOUT,
    USE_YT_DLP,
    YT_DLP_OPTIONS,
    QUALITY_OPTIONS,
    DEFAULT_QUALITY,
    PREVIEW_MAX_SIZE_BYTES,
)

logger = logging.getLogger(__name__)

CURRENT_QUALITY = DEFAULT_QUALITY


def set_quality(quality: str):
    global CURRENT_QUALITY
    if quality in QUALITY_OPTIONS:
        CURRENT_QUALITY = quality
        logger.info(f"Quality set to {quality}")


def download_file(
    url: str,
    destination: Path,
    retries: int = RETRY_COUNT,
    anime_name: Optional[str] = None,
    episode: Optional[int] = None,
) -> bool:
    """
    Download the file.
    If the canonical destination is not found after download, search for any .mp4
    in the destination directory containing the episode number.
    """
    # Existing valid canonical file → skip
    if destination.exists() and destination.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
        logger.info(f"✅ File already exists: {destination}")
        return True

    # Existing but too small → delete (preview)
    if destination.exists() and destination.stat().st_size <= PREVIEW_MAX_SIZE_BYTES:
        logger.warning(f"Deleting small existing file (preview): {destination}")
        destination.unlink()

    if USE_YT_DLP and _yt_dlp_available():
        return _download_with_ytdlp(url, destination, retries, anime_name, episode )
    else:
        return _download_with_requests(url, destination, retries, anime_name, episode)


def _yt_dlp_available() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _download_with_ytdlp(
    url: str,
    destination: Path,
    retries: int,
    anime_name: Optional[str] = None,
    episode: Optional[int] = None,
) -> bool:
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(destination.with_suffix(""))
    format_option = QUALITY_OPTIONS.get(CURRENT_QUALITY, QUALITY_OPTIONS[DEFAULT_QUALITY])
    cmd = ["yt-dlp", url, "-o", output_template, "-f", format_option] + YT_DLP_OPTIONS

    logger.info(f"📁 Downloading to: {destination} (quality: {CURRENT_QUALITY})")

    for attempt in range(retries):
        try:
            result = subprocess.run(cmd, cwd=dest_dir, check=False)
            if result.returncode == 0:
                # 1. Canonical destination exists
                if destination.exists():
                    if destination.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
                        logger.info(f"✅ Downloaded to {destination}")
                        _cleanup_partials(dest_dir, destination.stem)
                        return True
                    else:
                        logger.warning(
                            f"Downloaded file too small (preview): {destination}. Deleting."
                        )
                        destination.unlink()
                        return False

                # 2. Fuzzy search by episode number
                candidates = episode_candidates_from_url(url, primary=episode)
                for cand in candidates:
                    pat = episode_pattern(cand)
                    for f in dest_dir.glob("*.mp4"):
                        if not pat.search(f.name):
                            continue
                        if anime_name and not anime_matches_filename(anime_name, f.name):
                            continue
                        if f.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
                            logger.info(
                                f"✅ Found downloaded file: {f.name} "
                                f"(matched episode {cand})"
                            )
                            return True
                        else:
                            logger.warning(f"Deleting undersized file: {f}")
                            f.unlink()
                            return False

                logger.error(
                    f"yt-dlp completed but no file found for episode {episode}"
                )
                return False
            else:
                logger.warning(f"yt‑dlp attempt {attempt+1} failed (code {result.returncode})")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"All yt‑dlp attempts failed for {url}")
                    return False
        except Exception as e:
            logger.warning(f"yt‑dlp attempt {attempt+1} error: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All attempts failed for {url}")
                return False
    return False


def _download_with_requests(
    url: str,
    destination: Path,
    retries: int,
    anime_name: Optional[str] = None,
    episode: Optional[int] = None,
) -> bool:
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries):
        try:
            logger.info(f"⬇️ Downloading with requests: {url}")
            resp = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("Downloading", total=total)
                with destination.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
            if destination.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
                logger.info(f"✅ Downloaded to {destination}")
                _cleanup_partials(dest_dir, destination.stem)
                return True
            else:
                logger.warning(f"Downloaded file too small (preview): {destination}. Deleting.")
                destination.unlink()
                return False
        except Exception as e:
            logger.warning(f"requests attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All requests attempts failed for {url}")
                return False
    return False


def _cleanup_partials(directory: Path, basename: str):
    for pattern in [f"{basename}*.part", f"{basename}*.ytdl", f"{basename}*.temp"]:
        for f in directory.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass

