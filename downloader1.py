"""Download using yt-dlp (preferred) or requests."""

import logging
import subprocess
import time
from pathlib import Path

import requests

from config import (
    CHUNK_SIZE,
    HEADERS,
    RETRY_COUNT,
    RETRY_DELAY,
    TIMEOUT,
    USE_YT_DLP,
    YT_DLP_OPTIONS,
)

logger = logging.getLogger(__name__)


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
        logger.warning("yt-dlp not found, falling back to requests")
        return False


def _download_with_ytdlp(url: str, destination: Path, retries: int) -> bool:
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build output template: use destination stem, let yt-dlp add extension
    output_template = str(dest_dir / f"{destination.stem}.%(ext)s")

    cmd = [
        "yt-dlp",
        url,
        "-o", output_template,
        "--no-playlist",
        "--progress",
        "--newline",
        "--no-warnings",
    ]
    # Add any additional options from config (excluding those we already set)
    for opt in YT_DLP_OPTIONS:
        if opt not in ["--no-playlist", "--progress", "--newline", "--no-warnings"]:
            cmd.append(opt)

    for attempt in range(retries):
        try:
            logger.info(f"Downloading with yt-dlp: {url}")
            # Run yt-dlp; its output will go to stdout/stderr, showing progress
            result = subprocess.run(cmd, check=False, capture_output=False)  # capture_output=False to show progress
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd)

            # Find the downloaded file(s) matching the stem
            downloaded_files = list(dest_dir.glob(f"{destination.stem}.*"))
            if not downloaded_files:
                logger.error(f"No file found for {destination.stem}.* after download")
                return False

            # Rename the first found file to the desired destination
            actual_file = downloaded_files[0]
            if actual_file != destination:
                actual_file.rename(destination)
            logger.info(f"Downloaded to {destination}")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"yt-dlp attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All yt-dlp attempts failed for {url}")
                return False
    return False


def _download_with_requests(url: str, destination: Path, retries: int) -> bool:
    dest_dir = destination.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(retries):
        try:
            logger.info(f"Downloading with requests: {url}")
            resp = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with destination.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            progress = (downloaded / total) * 100
                            logger.info(f"Progress: {progress:.1f}%")
            logger.info(f"Downloaded to {destination}")
            return True
        except Exception as e:
            logger.warning(f"Requests attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All requests attempts failed for {url}")
                return False
    return False