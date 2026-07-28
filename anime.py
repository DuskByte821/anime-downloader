"""
Anime Downloader

Main entry point.
"""

from config import DOWNLOAD_DIR
from dataclasses import dataclass


@dataclass(slots=True)
class Anime:
    """
    Represents one anime entry inside anime.txt.
    """

    title: str
    status: str  # "watching" or "completed"
    episode: int
    season: int | None = None
    overall: int | None = None


def main():
    print("=" * 50)
    print(" Anime Downloader")
    print("=" * 50)
    print(f"Download directory : {DOWNLOAD_DIR}")
    print()


if __name__ == "__main__":
    main()
