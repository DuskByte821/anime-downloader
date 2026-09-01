"""Download with yt‑dlp – no renaming, rely on fuzzy checks."""

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
    PREVIEW_MAX_SIZE_BYTES,
)

logger = logging.getLogger(__name__)

CURRENT_QUALITY = DEFAULT_QUALITY


def set_quality(quality: str):
    global CURRENT_QUALITY
    if quality in QUALITY_OPTIONS:
        CURRENT_QUALITY = quality
        logger.info(f"Quality set to {quality}")
    else:
        logger.warning(f"Unknown quality '{quality}', keeping {CURRENT_QUALITY}")


def download_file(url: str, destination: Path, retries: int = RETRY_COUNT) -> bool:
    # If the destination already exists, we're done.
    if destination.exists() and destination.stat().st_size > 0:
        logger.info(f"✅ File already exists: {destination}")
        return True

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

    output_template = str(destination.with_suffix(".%(ext)s"))
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
            # Let yt-dlp write to stdout/stderr directly so the user sees progress
            result = subprocess.run(cmd, cwd=dest_dir, check=False)
            if result.returncode == 0:
                # Check if the destination exists and has valid size
                if destination.exists():
                    size = destination.stat().st_size
                    if size > PREVIEW_MAX_SIZE_BYTES:
                        logger.info(f"✅ Downloaded to {destination}")
                        _cleanup_partials(dest_dir, destination.stem)
                        return True
                    else:
                        logger.warning(f"Downloaded file is too small (preview): {destination} ({size} bytes). Deleting.")
                        destination.unlink()
                        return False
                # If destination doesn't exist, maybe yt-dlp saved with a different name due to output template.
                # We can try to find any .mp4 in dest_dir and rename, but we'll keep it simple – fail.
                logger.error(f"yt-dlp completed but {destination} does not exist.")
                return False
            else:
                logger.warning(f"yt‑dlp attempt {attempt+1} failed (code {result.returncode})")
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"All yt‑dlp attempts failed for {url}")
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
            # Check size
            if destination.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
                _cleanup_partials(dest_dir, destination.stem)
                logger.info(f"✅ Downloaded to {destination}")
                return True
            else:
                logger.warning(f"Downloaded file is too small (preview): {destination} ({destination.stat().st_size} bytes). Deleting.")
                destination.unlink()
                return False
        except Exception as e:
            logger.warning(f"⚠️ requests attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"❌ All requests attempts failed for {url}")
                return False
    return False

def _cleanup_partials(directory: Path, basename: str):
    for pattern in [f"{basename}*.part", f"{basename}*.ytdl", f"{basename}*.temp"]:
        for f in directory.glob(pattern):
            try:
                f.unlink()
                logger.debug(f"Removed partial file: {f}")
            except Exception:
                pass