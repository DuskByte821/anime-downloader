"""Download files using requests or yt-dlp."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

from config import CHUNK_SIZE, HEADERS, RETRY_COUNT, RETRY_DELAY, TIMEOUT, USE_YT_DLP, YT_DLP_OPTIONS

logger = logging.getLogger(__name__)


def download_file(url: str, destination: Path, retries: int = RETRY_COUNT) -> bool:
    """
    Download a file from url to destination.
    Uses yt-dlp if available and enabled, otherwise requests.
    """
    if USE_YT_DLP and _yt_dlp_available():
        return _download_with_ytdlp(url, destination, retries)
    else:
        return _download_with_requests(url, destination, retries)


def _yt_dlp_available() -> bool:
    """Check if yt-dlp is installed."""
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _download_with_ytdlp(url: str, destination: Path, retries: int) -> bool:
    """Download using yt-dlp."""
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # yt-dlp output template: use the destination filename without extension
    # yt-dlp will add its own extension, so we force the filename
    output_template = str(destination.with_suffix(""))  # remove extension, yt-dlp will add

    cmd = [
        "yt-dlp",
        url,
        "-o", output_template,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
    ] + YT_DLP_OPTIONS

    for attempt in range(retries):
        try:
            logger.info(f"Downloading with yt-dlp: {url} -> {destination}")
            subprocess.run(cmd, check=True, capture_output=True)
            # yt-dlp may output a file with a different extension; we rename if needed
            # Find the actual downloaded file (most recent in directory)
            downloaded_files = list(dest_dir.glob(f"{destination.stem}.*"))
            if downloaded_files:
                actual_file = downloaded_files[0]
                if actual_file != destination:
                    actual_file.rename(destination)
            logger.info(f"Download completed: {destination}")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"yt-dlp attempt {attempt+1} failed: {e.stderr.decode() if e.stderr else e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All yt-dlp attempts failed for {url}")
                return False
    return False


def _download_with_requests(url: str, destination: Path, retries: int) -> bool:
    """Fallback download using requests."""
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries):
        try:
            logger.info(f"Downloading with requests: {url} -> {destination}")
            resp = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT)
            resp.raise_for_status()

            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0

            with destination.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"Progress: {progress:.1f}%")
            logger.info(f"Download completed: {destination}")
            return True
        except Exception as e:
            logger.warning(f"Requests attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All requests attempts failed for {url}")
                return False
    return False