"""Anime Downloader – Full TUI with all enhancements, including sync."""

import argparse
import logging
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table, box
from rich.columns import Columns
from rich.panel import Panel
from rich import print as rprint
from rich.prompt import Prompt, Confirm
from rich.live import Live

from config import (
    DOWNLOAD_DIR, LOGS_DIR, DEBUG, VERSION,
    QUALITY_OPTIONS, DEFAULT_QUALITY,
)
from downloader import set_quality, CURRENT_QUALITY
from episode import get_missing_episodes
from failed_downloads import add_failed, load_failed, remove_success
from scraper import LuciferDonghuaScraper, CartoonsAreaScraper
from updater import update_watchlist
from watchlist import load_watchlist, save_watchlist
from queue_manager import DownloadQueue
from models import Anime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "anime_downloader.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

console = Console()
SCRAPER_PRIMARY = LuciferDonghuaScraper()
SCRAPER_FALLBACK = CartoonsAreaScraper()
QUEUE = DownloadQueue(max_workers=2)


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def get_anime_by_name(name: str):
    watchlist = load_watchlist()
    for a in watchlist:
        if a.name.lower() == name.lower():
            return a
    return None


def get_latest_with_fallback(anime):
    try:
        latest = SCRAPER_PRIMARY.get_latest_episode(anime)
        if latest > 0:
            return latest
    except Exception as e:
        logger.warning(f"Primary scraper failed: {e}")
    try:
        latest = SCRAPER_FALLBACK.get_latest_episode(anime)
        if latest > 0:
            logger.info(f"Fallback scraper used for {anime.name}")
            return latest
    except Exception as e:
        logger.warning(f"Fallback scraper failed: {e}")
    return 0


def get_download_link_with_fallback(anime, episode):
    try:
        return SCRAPER_PRIMARY.get_download_link(anime, episode)
    except:
        try:
            return SCRAPER_FALLBACK.get_download_link(anime, episode)
        except:
            raise RuntimeError("No download link found")


def download_episode_background(anime, episode, watchlist):
    try:
        link = get_download_link_with_fallback(anime, episode)
        if not link:
            logger.error(f"No link for {anime.name} ep {episode}")
            add_failed(anime.name, episode)
            return False
        anime_dir = DOWNLOAD_DIR / anime.name
        if anime.season:
            anime_dir = anime_dir / anime.season
        dest = anime_dir / f"Episode {episode}.mp4"
        QUEUE.add_job(anime, episode, watchlist, dest, link)
        return True
    except Exception as e:
        logger.exception(f"Error queuing {anime.name} ep {episode}: {e}")
        add_failed(anime.name, episode)
        return False


def process_anime_background(anime, watchlist):
    if anime.status == "completed":
        return

    latest = get_latest_with_fallback(anime)
    if latest == 0:
        return

    missing = get_missing_episodes(anime.episode, latest)
    if not missing:
        return

    for ep in missing:
        download_episode_background(anime, ep, watchlist)

    # Auto‑mark completed if all caught up
    if latest == anime.episode + len(missing) or latest == anime.episode:
        if Confirm.ask(f"[yellow]You've caught up to episode {latest} of {anime.name}. Mark as completed?[/yellow]"):
            anime.status = "completed"
            save_watchlist(watchlist)
            console.print(f"[green]✅ {anime.name} marked as completed.[/green]")


def sync_watchlist(anime_name=None):
    """Update watchlist to latest episodes without downloading."""
    watchlist = load_watchlist()
    updated = 0
    for anime in watchlist:
        if anime.status == "completed":
            continue
        if anime_name and anime.name.lower() != anime_name.lower():
            continue
        latest = get_latest_with_fallback(anime)
        if latest > 0 and latest > anime.episode:
            old = anime.episode
            anime.episode = latest
            updated += 1
            console.print(f"[green]✓[/green] {anime.name}: {old} → {latest}")
    if updated:
        save_watchlist(watchlist)
        console.print(f"[bold green]Synced {updated} anime(s) to latest episodes.[/bold green]")
    else:
        console.print("[yellow]All anime are already up to date.[/yellow]")


# ------------------------------------------------------------
# TUI Views with Keyboard Shortcuts
# ------------------------------------------------------------

def view_watchlist():
    watchlist = load_watchlist()
    if not watchlist:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return

    watching = sorted([a for a in watchlist if a.status == "watching"], key=lambda a: a.name.lower())
    completed = sorted([a for a in watchlist if a.status == "completed"], key=lambda a: a.name.lower())

    def build_table(items, title, color):
        table = Table(title=title, title_style=f"bold {color}", header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Anime", style="white", no_wrap=False)
        table.add_column("Season", justify="center", style="green")
        table.add_column("Episode", justify="center", style="yellow")
        for a in items:
            if a.season:
                season_match = re.search(r'\d+', a.season)
                season = f"S{season_match.group(0)}" if season_match else a.season
            else:
                season = "—"
            episode = f"E{a.episode}" if a.episode > 0 else "—"
            table.add_row(a.name, season, episode)
        return table

    left = Panel(build_table(watching, "Watching", "green"), title="Watching", border_style="green")
    right = Panel(build_table(completed, "Completed", "blue"), title="Completed", border_style="blue")
    console.print(Columns([left, right], equal=True, expand=True))


def view_available(anime_name=None):
    watchlist = load_watchlist()
    if not watchlist:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return

    if anime_name:
        anime = get_anime_by_name(anime_name)
        if not anime:
            console.print(f"[red]Anime '{anime_name}' not found.[/red]")
            return
        latest = get_latest_with_fallback(anime)
        if latest == 0:
            console.print(f"[yellow]No episodes found for {anime.name}[/yellow]")
        else:
            missing = get_missing_episodes(anime.episode, latest)
            console.print(f"[cyan]{anime.name}[/cyan]: latest = [green]{latest}[/green], missing = {missing if missing else 'None'}")
        return

    table = Table(title="Available Downloads", title_style="bold magenta", header_style="bold cyan", box=box.ROUNDED)
    table.add_column("Anime", style="white", no_wrap=False)
    table.add_column("Latest", justify="center", style="green")
    table.add_column("Missing", justify="center", style="yellow")

    for anime in watchlist:
        if anime.status == "completed":
            continue
        latest = get_latest_with_fallback(anime)
        missing = get_missing_episodes(anime.episode, latest) if latest > 0 else []
        table.add_row(
            anime.name,
            str(latest) if latest > 0 else "—",
            ", ".join(map(str, missing)) if missing else "None"
        )
    console.print(table)


def download_submenu():
    watchlist = load_watchlist()
    watching = [a for a in watchlist if a.status == "watching"]
    if not watching:
        console.print("[yellow]No anime in 'watching' status.[/yellow]")
        return

    console.print("\n[bold cyan]Select Anime to Download[/bold cyan]")
    for i, anime in enumerate(watching, 1):
        console.print(f"{i}. {anime.name} [dim](current ep: {anime.episode})[/dim]")
    console.print("0. Download all")
    choice = Prompt.ask("Enter number", choices=[str(i) for i in range(len(watching)+1)], default="0")

    if choice == "0":
        for anime in watching:
            process_anime_background(anime, watchlist)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(watching):
                process_anime_background(watching[idx], watchlist)
            else:
                console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Invalid input.[/red]")


def retry_failed():
    failed = load_failed()
    if not failed:
        console.print("[green]No failed downloads recorded.[/green]")
        return
    console.print(f"[yellow]Found {len(failed)} failed download(s). Retrying...[/yellow]")
    watchlist = load_watchlist()
    for name, ep in failed:
        anime = get_anime_by_name(name)
        if not anime:
            console.print(f"[red]Anime '{name}' no longer in watchlist; removing from failed log.[/red]")
            remove_success(name, ep)
            continue
        console.print(f"[cyan]Queuing {name} episode {ep}[/cyan]")
        download_episode_background(anime, ep, watchlist)


def view_logs():
    log_file = LOGS_DIR / "anime_downloader.log"
    if not log_file.exists():
        console.print("[yellow]No log file found.[/yellow]")
        return
    with log_file.open("r") as f:
        lines = f.readlines()
    last_lines = lines[-20:] if len(lines) > 20 else lines
    console.print("\n[bold cyan]Last 20 log entries:[/bold cyan]")
    for line in last_lines:
        console.print(line.strip())


def search_anime():
    query = Prompt.ask("[bold cyan]Enter anime name to search[/bold cyan]")
    if not query:
        return
    console.print(f"\n[bold]Searching for '{query}'...[/bold]")
    results = SCRAPER_PRIMARY.search_anime(query)
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    table = Table(title="Search Results", box=box.ROUNDED)
    table.add_column("Name", style="white")
    table.add_column("Latest Episode", justify="center", style="green")
    table.add_column("URL", style="blue")
    for name, url, latest in results:
        table.add_row(name, str(latest) if latest else "—", url)
    console.print(table)


def show_queue_status():
    status = QUEUE.get_status()
    if not status:
        console.print("[dim]No active jobs.[/dim]")
        return
    table = Table(title="Download Queue", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Anime", style="white")
    table.add_column("Episode", justify="center")
    table.add_column("Status", justify="center")
    for jid, (stat, name, ep) in status.items():
        color = "green" if stat == "completed" else "yellow" if stat == "downloading" else "red" if stat == "failed" else "white"
        table.add_row(str(jid), name, str(ep), f"[{color}]{stat}[/{color}]")
    console.print(table)


def set_download_quality():
    console.print("\n[bold cyan]Select download quality[/bold cyan]")
    for i, q in enumerate(QUALITY_OPTIONS.keys(), 1):
        current = " (current)" if q == CURRENT_QUALITY else ""
        console.print(f"{i}. {q}{current}")
    choice = Prompt.ask("Enter number", choices=[str(i) for i in range(1, len(QUALITY_OPTIONS)+1)])
    idx = int(choice) - 1
    quality = list(QUALITY_OPTIONS.keys())[idx]
    set_quality(quality)
    console.print(f"[green]Quality set to {quality}[/green]")


def test_modules():
    console.print("\n[bold cyan]Testing Modules[/bold cyan]")
    watchlist = load_watchlist()
    console.print(f"Watchlist loaded: {len(watchlist)} entries")
    if watchlist:
        test_anime = watchlist[0]
        console.print(f"Testing scraper for [cyan]{test_anime.name}[/cyan] ...")
        latest = get_latest_with_fallback(test_anime)
        console.print(f"Latest episode: [green]{latest}[/green]")
        if latest > 0:
            try:
                link = get_download_link_with_fallback(test_anime, latest)
                console.print(f"Download link for ep {latest}: [blue]{link}[/blue]")
            except:
                console.print("[red]Could not get download link.[/red]")
    else:
        console.print("[yellow]No anime to test scraper.[/yellow]")
    try:
        import subprocess
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        console.print("[green]yt-dlp is available.[/green]")
    except:
        console.print("[yellow]yt-dlp not found (fallback to requests).[/yellow]")
    console.print("[green]Testing complete.[/green]")


# ------------------------------------------------------------
# Main TUI with Keyboard Shortcuts
# ------------------------------------------------------------

def tui():
    console.print(Panel.fit(f" Anime Downloader v{VERSION} ", style="bold magenta"))
    # Escaped brackets to display literally
    console.print("[dim]Shortcuts: \\[w]atchlist \\[d]ownload \\[v]iew available \\[r]etry failed [/dim]")
    console.print("             [dim]\\[s]earch \\[l]ogs \\[q]ueue status \\[quality] \\[t]est \\[e]xit[/dim]\n")



    while True:
        # Show queue status line
        status = QUEUE.get_status()
        if status:
            active = sum(1 for s in status.values() if s[0] == "downloading")
            queued = sum(1 for s in status.values() if s[0] == "queued")
            console.print(f"[dim]Queue: {active} downloading, {queued} queued[/dim]")

        choice = Prompt.ask(
            "[bold cyan]Command[/bold cyan]",
            choices=["w", "d", "v", "r", "s", "l", "q", "quality", "t", "e"],
            default="w"
        )

        if choice == "w":
            view_watchlist()
        elif choice == "d":
            download_submenu()
        elif choice == "v":
            name = Prompt.ask("Enter anime name (or press Enter for all)", default="")
            view_available(name if name else None)
        elif choice == "r":
            retry_failed()
        elif choice == "s":
            search_anime()
        elif choice == "l":
            view_logs()
        elif choice == "q":
            show_queue_status()
        elif choice == "quality":
            set_download_quality()
        elif choice == "t":
            test_modules()
        elif choice == "e":
            console.print("[bold green]Goodbye![/bold green]")
            break


# ------------------------------------------------------------
# CLI entry
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Anime Downloader")
    parser.add_argument("--test-anime", type=str, help="Process only this anime name")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--menu", action="store_true", help="Force interactive menu")
    parser.add_argument("--sync", action="store_true", help="Update watchlist to latest episodes (no download)")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    if args.sync:
        sync_watchlist(args.test_anime)
        return

    if args.menu or (not args.test_anime and not args.menu):
        tui()
        return

    if args.test_anime:
        watchlist = load_watchlist()
        anime = get_anime_by_name(args.test_anime)
        if anime:
            process_anime_background(anime, watchlist)
        else:
            logger.error(f"Anime '{args.test_anime}' not found.")
    else:
        watchlist = load_watchlist()
        for anime in watchlist:
            process_anime_background(anime, watchlist)


if __name__ == "__main__":
    main()