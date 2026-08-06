"""Download with yt‑dlp (progress shown) and requests fallback with rich progress."""

import logging
import subprocess
import time
from pathlib import Path

import requests
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
)

logger = logging.getLogger(__name__)

# Global quality setting (can be changed by user)
CURRENT_QUALITY = DEFAULT_QUALITY


def set_quality(quality: str):
    global CURRENT_QUALITY
    if quality in QUALITY_OPTIONS:
        CURRENT_QUALITY = quality
        logger.info(f"Quality set to {quality}")
    else:
        logger.warning(f"Unknown quality '{quality}', keeping {CURRENT_QUALITY}")


def download_file(url: str, destination: Path, retries: int = RETRY_COUNT) -> bool:
    if USE_YT_DLP and _yt_dlp_available():
        return _download_with_ytdlp(url, destination, retries)
    else:
        return _download_with_requests(url, destination, retries)


def _yt_dlp_available() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _download_with_ytdlp(url: str, destination: Path, retries: int) -> bool:
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(destination.with_suffix(""))
    format_option = QUALITY_OPTIONS.get(CURRENT_QUALITY, QUALITY_OPTIONS[DEFAULT_QUALITY])
    cmd = [
        "yt-dlp",
        url,
        "-o", output_template,
        "-f", format_option,
    ] + YT_DLP_OPTIONS

    logger.info(f"📁 Downloading to: {destination} (quality: {CURRENT_QUALITY})")
    for attempt in range(retries):
        try:
            subprocess.run(cmd, check=True)
            # Find downloaded file(s)
            downloaded = list(dest_dir.glob(f"{destination.stem}.*"))
            if not downloaded:
                logger.error("No file found after yt‑dlp completion.")
                return False
            # Rename to destination
            actual = downloaded[0]
            if actual != destination:
                actual.rename(destination)
            # Clean up any leftover .part files
            _cleanup_partials(dest_dir, destination.stem)
            if destination.exists():
                logger.info(f"✅ Downloaded to {destination}")
                return True
            else:
                logger.error(f"❌ Destination file missing: {destination}")
                return False
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ yt‑dlp attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"❌ All yt‑dlp attempts failed for {url}")
                return False
    return False


def _download_with_requests(url: str, destination: Path, retries: int) -> bool:
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
            _cleanup_partials(dest_dir, destination.stem)
            logger.info(f"✅ Downloaded to {destination}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ requests attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"❌ All requests attempts failed for {url}")
                return False
    return False


def _cleanup_partials(directory: Path, basename: str):
    """Remove any leftover .part or temporary files."""
    for pattern in [f"{basename}*.part", f"{basename}*.ytdl", f"{basename}*.temp"]:
        for f in directory.glob(pattern):
            try:
                f.unlink()
                logger.debug(f"Removed partial file: {f}")
            except Exception:
                pass