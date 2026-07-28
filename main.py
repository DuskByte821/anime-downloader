"""Entry point for the anime downloader."""

import argparse
import importlib
import logging
import sys
from pathlib import Path

from config import DOWNLOAD_DIR, LOGS_DIR, SCRAPERS
from downloader import download_file
from episode import get_missing_episodes
from models import Anime
from updater import update_watchlist
from watchlist import load_watchlist, save_watchlist

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "anime_downloader.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def get_scraper_instances():
    """Dynamically import and instantiate all scraper classes from config."""
    scrapers = []
    for path in SCRAPERS:
        try:
            module_path, class_name = path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            scraper_class = getattr(module, class_name)
            scrapers.append(scraper_class())
        except Exception as e:
            logger.error(f"Failed to load scraper {path}: {e}")
    return scrapers


def test_watchlist_parser():
    """Test watchlist loading and saving."""
    print("=== Testing watchlist parser ===")
    watchlist = load_watchlist()
    print(f"Loaded {len(watchlist)} entries:")
    for anime in watchlist:
        print(f"  {anime.name} | season={anime.season} | ep={anime.episode} | status={anime.status}")
    # Save a copy to test
    save_watchlist(watchlist, Path("data/anime_test.txt"))
    print("Saved test file data/anime_test.txt")
    print("=== End watchlist test ===\n")


def test_scraper(anime_name: str, episode: int = None):
    """Test scrapers for a specific anime."""
    print(f"=== Testing scrapers for '{anime_name}' ===")
    anime = Anime(name=anime_name, status="watching")
    scrapers = get_scraper_instances()
    for scraper in scrapers:
        print(f"Using scraper: {scraper.__class__.__name__}")
        latest = scraper.get_latest_episode(anime)
        print(f"  Latest episode: {latest}")
        if latest > 0 and episode is None:
            episode = latest
        if episode:
            try:
                link = scraper.get_download_link(anime, episode)
                print(f"  Download link for ep {episode}: {link}")
            except Exception as e:
                print(f"  Failed to get download link: {e}")
        print()
    print("=== End scraper test ===\n")


def test_downloader(url: str, dest: str = "test_download.mp4"):
    """Test downloader with a given URL."""
    print(f"=== Testing downloader with URL: {url} ===")
    dest_path = Path(dest)
    success = download_file(url, dest_path)
    print(f"Download {'successful' if success else 'failed'}")
    if success and dest_path.exists():
        print(f"File saved to {dest_path.absolute()}")
    print("=== End downloader test ===\n")


def main():
    parser = argparse.ArgumentParser(description="Anime Downloader")
    parser.add_argument("--test", choices=["watchlist", "scraper", "downloader"], help="Test a specific module")
    parser.add_argument("--anime", help="Anime name for scraper test")
    parser.add_argument("--episode", type=int, help="Episode number for scraper test")
    parser.add_argument("--url", help="URL for downloader test")
    parser.add_argument("--dest", default="test_download.mp4", help="Destination for downloader test")
    args = parser.parse_args()

    if args.test == "watchlist":
        test_watchlist_parser()
        return
    elif args.test == "scraper":
        if not args.anime:
            print("Please provide --anime name for scraper test")
            return
        test_scraper(args.anime, args.episode)
        return
    elif args.test == "downloader":
        if not args.url:
            print("Please provide --url for downloader test")
            return
        test_downloader(args.url, args.dest)
        return

    # Normal full run
    logger.info("Starting Anime Downloader (full run)")

    watchlist = load_watchlist()
    if not watchlist:
        logger.info("No anime in watchlist. Exiting.")
        return

    scrapers = get_scraper_instances()
    if not scrapers:
        logger.error("No scrapers loaded. Exiting.")
        return

    for anime in watchlist:
        if anime.status == "completed":
            logger.info(f"Skipping completed: {anime.name}")
            continue

        logger.info(f"Processing {anime.name}")
        latest = 0
        success_scraper = None

        # Try scrapers in order
        for scraper in scrapers:
            try:
                latest = scraper.get_latest_episode(anime)
                if latest > 0:
                    success_scraper = scraper
                    break
            except Exception as e:
                logger.warning(f"Scraper {scraper.__class__.__name__} failed for {anime.name}: {e}")
                continue

        if latest == 0 or success_scraper is None:
            logger.warning(f"No episodes found for {anime.name} from any scraper")
            continue

        missing = get_missing_episodes(anime.episode, latest)
        if not missing:
            logger.info(f"No new episodes for {anime.name}")
            continue

        logger.info(f"Missing episodes for {anime.name}: {missing}")

        for ep in missing:
            try:
                # Try to get link from the same scraper; if fails, try others
                link = None
                for scraper in [success_scraper] + [s for s in scrapers if s != success_scraper]:
                    try:
                        link = scraper.get_download_link(anime, ep)
                        if link:
                            break
                    except Exception:
                        continue
                if not link:
                    logger.error(f"No download link for {anime.name} ep {ep} from any scraper")
                    continue

                anime_dir = DOWNLOAD_DIR / anime.name
                if anime.season:
                    anime_dir = anime_dir / anime.season
                dest = anime_dir / f"Episode {ep}.mp4"

                success = download_file(link, dest)
                if success:
                    update_watchlist(watchlist, anime, ep)
                else:
                    logger.error(f"Failed to download {anime.name} ep {ep}")
            except Exception as e:
                logger.exception(f"Error processing {anime.name} ep {ep}: {e}")

    logger.info("Anime Downloader finished.")


if __name__ == "__main__":
    main()