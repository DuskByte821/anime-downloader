"""Anime Downloader – Full TUI with Page Links Manager and all enhancements."""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table, box
from rich.columns import Columns
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from config import (
    DOWNLOAD_DIR, LOGS_DIR, DEBUG, VERSION,
    QUALITY_OPTIONS, DEFAULT_QUALITY, PREVIEW_MAX_SIZE_BYTES,
)
from downloader import set_quality, CURRENT_QUALITY
from episode import get_missing_episodes
from failed_downloads import add_failed, load_failed, remove_success
from scraper import LuciferDonghuaScraper, CartoonsAreaScraper
from updater import update_watchlist
from watchlist import load_watchlist, save_watchlist
from queue_manager import DownloadQueue

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

def find_existing_file(anime_name: str, episode: int, season: Optional[str] = None) -> Optional[Path]:
    """
    Search the downloads directory for a file matching the anime and episode.
    Returns the file path if found and size > PREVIEW_MAX_SIZE_BYTES, else None.
    If a file is found but is too small (preview), it is deleted.
    """
    anime_slug = anime_name.lower().replace(" ", "_")
    patterns = [
        f"*_{anime_slug}_ep{episode}.mp4",
        f"*{anime_slug}*_ep{episode}.mp4",
        f"*ep{episode}*.mp4",
    ]
    if season:
        season_num = re.search(r'\d+', season)
        if season_num:
            s = season_num.group(0)
            patterns.append(f"*_s{s}_ep{episode}.mp4")
            patterns.append(f"*s{s}*ep{episode}*.mp4")

    # Search in DOWNLOAD_DIR
    for pattern in patterns:
        matches = list(DOWNLOAD_DIR.glob(pattern))
        for f in matches:
            if f.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
                return f
            else:
                # This file is too small – delete it (preview)
                logger.warning(f"Deleting small file (preview) : {f} ({f.stat().st_size} bytes)")
                f.unlink()
                # Continue searching for a valid file
    return None


def download_episode_background(anime, episode, watchlist):
    # Build canonical destination
    if anime.season:
        season_num = re.search(r'\d+', anime.season)
        season_str = f"_s{season_num.group(0)}" if season_num else ""
    else:
        season_str = ""
    canonical_name = f"{anime.name.replace(' ', '_')}{season_str}_ep{episode}.mp4"
    canonical_dest = DOWNLOAD_DIR / canonical_name

    # 1. Check canonical file
    if canonical_dest.exists():
        size = canonical_dest.stat().st_size
        if size > PREVIEW_MAX_SIZE_BYTES:
            logger.info(f"✅ Episode {episode} of {anime.name} already downloaded (canonical).")
            update_watchlist(watchlist, anime, episode)
            return True
        else:
            # small file – delete and treat as failed
            logger.warning(f"Deleting small canonical file (preview): {canonical_dest}")
            canonical_dest.unlink()
            add_failed(anime.name, episode)
            return False

    # 2. Fuzzy search (any file containing anime name and episode)
    existing = find_existing_file(anime.name, episode, anime.season)
    if existing:
        # find_existing_file already deleted any small file and returned a valid one
        logger.info(f"✅ Episode {episode} of {anime.name} already downloaded (found as {existing.name}).")
        update_watchlist(watchlist, anime, episode)
        return True

    # 3. No valid file – queue download
    try:
        link = get_download_link_with_fallback(anime, episode)   # episode page
        # Try to get direct video URL
        direct_url = SCRAPER_PRIMARY.get_direct_video_url(anime, episode)
        if direct_url:
            logger.info(f"Found direct video URL for {anime.name} ep {episode}: {direct_url}")
            link = direct_url
        elif SCRAPER_FALLBACK:
            # Also try fallback scraper
            fallback_url = SCRAPER_FALLBACK.get_direct_video_url(anime, episode) if hasattr(SCRAPER_FALLBACK, 'get_direct_video_url') else None
            if fallback_url:
                logger.info(f"Found direct video URL via fallback: {fallback_url}")
                link = fallback_url
        # If still no direct URL, use the episode page (yt-dlp will handle it)
        if not link:
            logger.error(f"No download link for {anime.name} ep {episode}")
            add_failed(anime.name, episode)
            return False
        QUEUE.add_job(anime, episode, watchlist, canonical_dest, link)
        return True
    except Exception as e:
        logger.exception(f"Error queuing {anime.name} ep {episode}: {e}")
        add_failed(anime.name, episode)
        return False

def get_anime_by_name(name: str):
    watchlist = load_watchlist()
    for a in watchlist:
        if a.name.lower() == name.lower():
            return a
    return None

def mark_completed():
    """Manually mark watching anime as completed."""
    watchlist = load_watchlist()
    watching = [a for a in watchlist if a.status == "watching"]
    if not watching:
        console.print("[yellow]No anime in 'watching' status.[/yellow]")
        return

    console.print("\n[bold cyan]Mark Anime as Completed[/bold cyan]")
    for i, anime in enumerate(watching, 1):
        latest = get_latest_with_fallback(anime)
        console.print(f"{i}. {anime.name} [dim](current: {anime.episode}, latest: {latest})[/dim]")
    console.print("0. Mark all as completed")
    console.print("q. Cancel")

    choice = Prompt.ask("Enter number (or q to cancel)", default="q")
    if choice.lower() == "q":
        return

    if choice == "0":
        for anime in watching:
            anime.status = "completed"
        save_watchlist(watchlist)
        console.print(f"[green]✅ Marked {len(watching)} anime as completed.[/green]")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(watching):
                anime = watching[idx]
                anime.status = "completed"
                save_watchlist(watchlist)
                console.print(f"[green]✅ Marked {anime.name} as completed.[/green]")
            else:
                console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Invalid input.[/red]")


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

def process_anime_background(anime, watchlist):
             # If completed, check if new episodes exist
    if anime.status == "completed":
        latest = get_latest_with_fallback(anime)
        if latest > anime.episode:
            if Confirm.ask(f"[yellow]New episodes found for completed '{anime.name}'. Move back to watching and download?[/yellow]"):
                anime.status = "watching"
                save_watchlist(watchlist)
                console.print("[green]✅ Moved back to watching.[/green]")
            else:
                return
        else:
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
#    if latest == anime.episode + len(missing) or latest == anime.episode:
#        if Confirm.ask(f"[yellow]You've caught up to episode {latest} of {anime.name}. Mark as completed?[/yellow]"):
#            anime.status = "completed"
#            save_watchlist(watchlist)
#            console.print(f"[green]✅ {anime.name} marked as completed.[/green]")


def sync_watchlist(anime_name=None):
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
# Page Links Manager
def manage_page_links():
    """Interactive page link manager with loop."""
    scraper = SCRAPER_PRIMARY
    while True:
        watchlist = load_watchlist()
        if not watchlist:
            console.print("[yellow]Watchlist is empty. Add some anime first.[/yellow]")
            return

        mappings = scraper._url_map.copy()

        # Display current links
        console.print("\n[bold cyan]Current Page Links[/bold cyan]")
        table = Table(title="Mapped URLs", box=box.ROUNDED)
        table.add_column("Anime", style="white")
        table.add_column("URL", style="blue")
        table.add_column("Status", justify="center")

        for anime in watchlist:
            matched_url = None
            for key, url in mappings.items():
                if key == anime.name.lower() or anime.name.lower() in key or key in anime.name.lower():
                    matched_url = url
                    break
            status = "✓" if matched_url else "✗"
            table.add_row(anime.name, matched_url or "—", f"[{'green' if matched_url else 'red'}]{status}[/{'green' if matched_url else 'red'}]")
        console.print(table)

        console.print("\n[bold]Options:[/bold]")
        console.print("1. Assign/update a page link")
        console.print("2. Exit link manager")
        action = Prompt.ask("Choose", choices=["1", "2"])

        if action == "2":
            break

        # Select anime
        console.print("\nSelect anime to assign/update its page link:")
        for i, anime in enumerate(watchlist, 1):
            console.print(f"{i}. {anime.name}")
        console.print("0. Cancel")
        choice = Prompt.ask("Enter number", default="0")

        if choice == "0":
            continue

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(watchlist)):
                console.print("[red]Invalid selection.[/red]")
                continue
            selected_anime = watchlist[idx]
        except ValueError:
            console.print("[red]Invalid input.[/red]")
            continue

        # Search or manual
        console.print(f"\n[bold]Anime: {selected_anime.name}[/bold]")
        console.print("1. Search online for page URL")
        console.print("2. Enter URL manually")
        subchoice = Prompt.ask("Choose", choices=["1", "2"])

        selected_url = None
        if subchoice == "1":
            query = Prompt.ask("Enter search keyword (press Enter to use anime name)", default=selected_anime.name)
            results = scraper.search_anime(query)
            if not results:
                console.print("[yellow]No results found.[/yellow]")
                continue
            console.print("\n[bold]Search Results:[/bold]")
            for i, (name, url, latest) in enumerate(results, 1):
                console.print(f"{i}. {name} [dim](latest: {latest})[/dim]")
                console.print(f"   {url}")
            url_choice = Prompt.ask("Select result number (or 0 to cancel)", default="0")
            if url_choice == "0":
                continue
            try:
                url_idx = int(url_choice) - 1
                if not (0 <= url_idx < len(results)):
                    console.print("[red]Invalid selection.[/red]")
                    continue
                selected_url = results[url_idx][1]
            except ValueError:
                console.print("[red]Invalid input.[/red]")
                continue
        else:
            selected_url = Prompt.ask("Enter full URL of the anime's main page")

        if not selected_url:
            console.print("[red]No URL provided.[/red]")
            continue

        if Confirm.ask(f"Assign [cyan]{selected_url}[/cyan] to [yellow]{selected_anime.name}[/yellow]?"):
            new_mappings = {k: v for k, v in mappings.items() if k != selected_anime.name.lower()}
            new_mappings[selected_anime.name.lower()] = selected_url
            scraper.save_links(new_mappings)
            console.print("[green]✅ Page link assigned successfully![/green]")
            # Continue loop
        else:
            console.print("[dim]Cancelled.[/dim]")


# ------------------------------------------------------------
# TUI Views
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
# Main TUI
# ------------------------------------------------------------

def tui():
    console.print(Panel.fit(f" Anime Downloader v{VERSION} ", style="bold magenta"))
    console.print("[dim]Shortcuts: \\[w]atchlist \\[d]ownload \\[v]iew available \\[r]etry failed \\[s]earch \\[l]ogs \\[q]ueue status \\[p]age links \\[m]ark completed \\[quality] \\[t]est \\[e]xit[/dim]\n")

    while True:
        status = QUEUE.get_status()
        if status:
            active = sum(1 for s in status.values() if s[0] == "downloading")
            queued = sum(1 for s in status.values() if s[0] == "queued")
            console.print(f"[dim]Queue: {active} downloading, {queued} queued[/dim]")

        choice = Prompt.ask(
            "[bold cyan]Command[/bold cyan]",
            choices=["w", "d", "v", "r", "s", "l", "q", "p", "quality", "m", "t", "e"],
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
        elif choice == "p":
            manage_page_links()
        elif choice == "quality":
            set_download_quality()
        elif choice == "t":
            test_modules()
        elif choice == "m":
            mark_completed()
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