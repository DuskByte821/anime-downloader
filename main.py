"""Anime Downloader – Full TUI with Page Links Manager and all enhancements."""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Pattern

from rich.console import Console
from rich.table import Table, box
from rich.columns import Columns
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from link_cache import scan_links_dir, get_cached_url
from link_manager import LinkManager
from config import (
    DOWNLOAD_DIR, LOGS_DIR, DEBUG, VERSION,
    QUALITY_OPTIONS, DEFAULT_QUALITY, PREVIEW_MAX_SIZE_BYTES, ABBREVIATIONS,
    WATCHLIST_FILES, ANIME_WATCHLIST_FILE, DONGHUA_WATCHLIST_FILE, DEFAULT_CONTENT_TYPE,
)
from downloader import set_quality, CURRENT_QUALITY
from episode import get_missing_episodes
from failed_downloads import add_failed, load_failed, remove_success
from scraper import LuciferDonghuaScraper, CartoonsAreaScraper
from updater import update_watchlist
from watchlist import (    load_watchlist, save_watchlist, normalize_name,
    change_status, VALID_STATUSES,
)
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




# -----------------------------------------------------------
# Content-Type Functions
# -----------------------------------------------------------
#
#
def choose_content_type(prompt_label: str = "Select content type") -> Optional[str]:
    current = get_default_content_type()
    console.print(f"\n[bold cyan]{prompt_label}[/bold cyan]")
    console.print(f"1. Anime{'  [dim](default)[/dim]' if current == 'anime' else ''}")
    console.print(f"2. Donghua{'  [dim](default)[/dim]' if current == 'donghua' else ''}")
    console.print(f"Enter. Use default ({current})")
    console.print("0. Back")
    choice = Prompt.ask(
        "Enter number",
        choices=["0", "1", "2", ""],
        default="",
    )
    if choice == "0":
        return None
    if choice == "":
        return current
    return "anime" if choice == "1" else "donghua"

def _content_type_for_path(file_path: Path) -> Optional[str]:
    """Map a watchlist file path back to its content type, or None."""
    fp = Path(file_path)
    for ct, p in WATCHLIST_FILES.items():
        if Path(p) == fp:
            return ct
    return None


def watchlist_menu():
    while True:
        ctype = choose_content_type("Watchlist")
        if ctype is None:
            return

        file_path = WATCHLIST_FILES[ctype]

        console.print(f"\n[bold cyan]{ctype.title()} – select status[/bold cyan]")
        console.print("1. Watching")
        console.print("2. Ended")
        console.print("3. Dropped")
        console.print("4. Completed")
        console.print("5. All")
        console.print("0. Back")
        choice = Prompt.ask("Enter number", choices=["0", "1", "2", "3", "4", "5"], default="5")
        if choice == "0":
            continue

        status_map = {"1": "watching", "2": "ended", "3": "dropped", "4": "completed"}
        status_filter = status_map.get(choice)  # None -> "all"

        view_watchlist(file_path, status_filter)


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
# Episode Matching Functions

def _episode_pattern(episode: int) -> Pattern[str]:
    """
    Match 'ep<episode>' (or 'e<episode>', 'episode <episode>') with a
    digit boundary on the right so 'ep21' does not match 'ep211'.
    """
    # Matches: ep21, e21, episode 21, episode-21, episode_21
    # Not matched: ep211, ep210, e219
    return re.compile(
        rf"(?:ep|e|episode[\s_-]?)(?P<n>{episode})(?!\d)",
        re.IGNORECASE,
    )


def _anime_matches_filename(anime_name: str, filename: str) -> bool:
    """
    Fuzzy match: at least one abbreviation for this anime must appear in
    the filename, OR 60% of anime-name tokens must appear.
    """
    def slug(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    file_slug = slug(filename)
    name_key = anime_name.lower().strip()

    # 1. Abbreviation check
    abbrs = ABBREVIATIONS.get(name_key, [])
    for ab in abbrs:
        if ab in file_slug:
            return True

    # 2. Token overlap check
    anime_tokens = [t for t in slug(anime_name).split() if len(t) > 1]
    if not anime_tokens:
        return False
    present = sum(1 for t in anime_tokens if t in file_slug)
    return present / len(anime_tokens) >= 0.6

def find_existing_file(
    anime_name: str,
    episode: int,
    season: Optional[str] = None,
) -> Optional[Path]:
    """
    Search DOWNLOAD_DIR for a file matching the anime and episode.

    A match requires:
      - the anime name to appear in the filename (fuzzy, 60% token overlap)
      - the episode number to match with a digit boundary (ep21 != ep211)

    If a matching file exists but is below PREVIEW_MAX_SIZE_BYTES,
    it is deleted and the search continues (preview file).
    """
    if not DOWNLOAD_DIR.exists():
        return None

    ep_re = _episode_pattern(episode)

    for f in DOWNLOAD_DIR.glob("*.mp4"):
        # 1. Episode match (with digit boundary)
        if not ep_re.search(f.name):
            continue

        # 2. Anime match (fuzzy, but must be non-empty)
        if not _anime_matches_filename(anime_name, f.name):
            continue

        # 3. Size check
        if f.stat().st_size > PREVIEW_MAX_SIZE_BYTES:
            return f
        else:
            logger.warning(f"Deleting small file (preview): {f} ({f.stat().st_size} bytes)")
            f.unlink()

    return None

def download_episode_background(anime, episode, watchlist, file_path: Path):
    # Build canonical destination
    if anime.season:
        season_num = re.search(r'\d+', anime.season)
        season_str = f"_s{season_num.group(0)}" if season_num else ""
    else:
        season_str = ""
    canonical_name = f"{anime.name.replace(' ', '_')}{season_str}_ep{episode}.mp4"
    canonical_dest = DOWNLOAD_DIR / canonical_name

    # 1. Canonical file exists
    if canonical_dest.exists():
        size = canonical_dest.stat().st_size
        if size > PREVIEW_MAX_SIZE_BYTES:
            logger.info(f"✅ Episode {episode} of {anime.name} already downloaded (canonical).")
            update_watchlist(watchlist, anime, episode, file_path=file_path)   # ← FIX
            return True
        else:
            logger.warning(f"Deleting small canonical file (preview): {canonical_dest}")
            canonical_dest.unlink()
            add_failed(anime.name, episode)
            return False

    # 2. Fuzzy existing file
    existing = find_existing_file(anime.name, episode, anime.season)
    if existing:
        logger.info(f"✅ Episode {episode} of {anime.name} already downloaded (found as {existing.name}).")
        update_watchlist(watchlist, anime, episode, file_path=file_path)       # ← FIX
        return True

    # 3. Queue the download
    try:
        ctype = _content_type_for_path(file_path)
        link = get_download_link_with_fallback(anime, episode, content_type=ctype)
        if not link:
            logger.error(f"No link for {anime.name} ep {episode}")
            add_failed(anime.name, episode)
            return False
        QUEUE.add_job(
            anime, episode, watchlist, canonical_dest, link,
            watchlist_file=file_path,
        )
        return True
    except Exception as e:
        logger.exception(f"Error queuing {anime.name} ep {episode}: {e}")
        add_failed(anime.name, episode)
        return False

# ------------------------------------------------------------
# Changes Media Status
# ------------------------------------------------------------
#
def change_status_menu():
    ctype = choose_content_type("Change Status")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]

    watchlist = load_watchlist(file_path)
    if not watchlist:
        console.print(f"[yellow]{file_path.name} is empty.[/yellow]")
        return

    # Select anime
    console.print(f"\n[bold cyan]Select anime[/bold cyan]")
    for i, a in enumerate(watchlist, 1):
        console.print(f"{i}. {a.name} [dim]({a.status})[/dim]")
    console.print("0. Cancel")
    choice = Prompt.ask("Enter number", default="0")
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(watchlist)):
            console.print("[red]Invalid selection.[/red]")
            return
    except ValueError:
        console.print("[red]Invalid input.[/red]")
        return
    anime = watchlist[idx]

    # Select new status
    console.print(f"\n[bold]{anime.name}[/bold] (current: {anime.status})")
    console.print("1. Watching")
    console.print("2. Ended")
    console.print("3. Dropped")
    console.print("4. Completed")
    console.print("0. Cancel")
    s_choice = Prompt.ask("New status", choices=["0", "1", "2", "3", "4"], default="0")
    if s_choice == "0":
        return
    status_map = {"1": "watching", "2": "ended", "3": "dropped", "4": "completed"}
    new_status = status_map[s_choice]

    if change_status(watchlist, anime, new_status):
        save_watchlist(watchlist, file_path)
        console.print(f"[green]✅ {anime.name} → {new_status}[/green]")
    else:
        console.print(f"[dim]No change (already {anime.status}).[/dim]")

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


def get_download_link_with_fallback(anime, episode, content_type=None):
    """
    Resolve an episode URL.

    Order:
      1. Persistent per-series link cache (data/links/*.txt)
      2. Existing primary scraper
      3. Existing fallback scraper

    The cache is additive: a miss falls through to the existing behavior.
    """
    # 1. Link cache — content-type aware
    if content_type:
        cached = get_cached_url(anime.name, content_type, episode)
        if cached:
            logger.info(
                f"Using cached link for {anime.name} ep {episode} "
                f"({content_type})"
            )
            return cached

    # 2. Existing scraper behavior, unchanged
    try:
        return SCRAPER_PRIMARY.get_download_link(anime, episode)
    except:
        try:
            return SCRAPER_FALLBACK.get_download_link(anime, episode)
        except:
            raise RuntimeError("No download link found")

def process_anime_background(anime, watchlist, file_path: Path):
    if anime.status == "completed":
        return

    latest = get_latest_with_fallback(anime)
    if latest == 0:
        return

    missing = get_missing_episodes(anime.downloaded, latest)
    if not missing:
        return

    for ep in missing:
        download_episode_background(anime, ep, watchlist, file_path)

# Define sync_links() function somewhere before main()
def sync_links(file_path: Path, content_type: str):
    """Synchronize links for all watchlist entries across all supported sites."""
    console.print("[bold cyan]Syncing links for all watchlist entries...[/bold cyan]")
    watchlist = load_watchlist(file_path)
    if not watchlist:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return

    link_manager = LinkManager()
    sites = [LuciferDonghuaScraper(link_manager)]

    changed = False

    for site_scraper in sites:
        site_name = site_scraper.SITE_NAME
        console.print(f"\n[bold]{site_name}[/bold]")

        for anime in watchlist:
            season_str = anime.season or ""

            # ----------------------------------------------------------
            # 1. Explicit entries: never touch.
            # ----------------------------------------------------------
            if link_manager.is_explicit(anime.name, site_name, season_str):
                console.print(f"  ⊘ {anime.name} → explicit (skipped)")
                continue

            # ----------------------------------------------------------
            # 2. Completed anime: try n+1, else check same URL.
            # ----------------------------------------------------------
            if anime.status == "completed":
                if not link_manager.is_explicit(anime.name, site_name, season_str):
                    link_manager.invalidate(anime.name, site_name, season_str)

                current_season_num = site_scraper._extract_season_number(anime.season) or 1
                target_season_str = f"season {current_season_num + 1}"

                status, url = site_scraper.discover_series_url(
                    anime, force_discover=True, target_season=target_season_str
                )

                if status == "found":
                    console.print(
                        f"  ✓ {anime.name} → found season {current_season_num + 1}"
                    )
                    link_manager.set(anime.name, site_name, target_season_str, "found", url, explicit=True, override_explicit=True,)
                    anime.season = target_season_str
                    anime.status = "watching"
                    anime.downloaded = 0
                    anime.watched = 0
                    changed = True
                    continue

                # No new season page → check same URL for new episodes
                status_base, base_url = site_scraper.discover_series_url(
                    anime, force_discover=True
                )
                if status_base == "found" and base_url:
                    latest = site_scraper.check_same_url_for_new_episodes(anime, base_url)
                    if latest > anime.downloaded:
                        console.print(
                            f"  ↻ {anime.name} → continuous, "
                            f"{latest - anime.downloaded} new episode(s)"
                        )
                        link_manager.set(anime.name, site_name, season_str, "found", base_url)
                        anime.status = "watching"
                        changed = True
                        continue

                # Truly finished
                console.print(
                    f"  ✗ {anime.name} → not_found (no new season, no new episodes)"
                )
                link_manager.set(anime.name, site_name, target_season_str, "not_found", "")

            # ----------------------------------------------------------
            # 3. Watching anime: normal discovery.
            # ----------------------------------------------------------
            else:
                status, url = site_scraper.discover_series_url(anime)
                link_manager.set(anime.name, site_name, season_str, status, url)
                if status == "found":
                    console.print(f"  ✓ {anime.name} → found")
                else:
                    console.print(f"  ✗ {anime.name} → not_found")

    if changed:
        save_watchlist(watchlist)
    console.print("\n[bold green]Link sync complete![/bold green]")


def sync_watchlist(anime_name=None):
    watchlist = load_watchlist()
    updated = 0
    for anime in watchlist:
        if anime.status == "completed":
            continue
        if anime_name and anime.name.lower() != anime_name.lower():
            continue
        latest = get_latest_with_fallback(anime)
        if latest > 0 and latest > anime.downloaded:
            old = anime.downloaded
            anime.downloaded = latest
            updated += 1
            console.print(f"[green]✓[/green] {anime.name}: {old} → {latest}")
    if updated:
        save_watchlist(watchlist)
        console.print(f"[bold green]Synced {updated} anime(s) to latest episodes.[/bold green]")
    else:
        console.print("[yellow]All anime are already up to date.[/yellow]")


# ------------------------------------------------------------
# Page Links Manager
def page_links_menu():
    ctype = choose_content_type("Page Links")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    manage_page_links(file_path)


def manage_page_links(file_path: Path):
    """Interactive page-link manager scoped to one watchlist file."""
    from link_manager import LinkManager
    link_manager = LinkManager()
    scraper = SCRAPER_PRIMARY
    site = scraper.SITE_NAME

    while True:
        watchlist = load_watchlist(file_path)
        if not watchlist:
            console.print(f"[yellow]{file_path.name} is empty.[/yellow]")
            return

        console.print(f"\n[bold cyan]Current Page Links – {file_path.stem.title()}[/bold cyan]")
        table = Table(box=box.ROUNDED)
        table.add_column("Anime", style="white")
        table.add_column("Season", justify="center", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Explicit", justify="center")
        table.add_column("URL", style="blue", overflow="fold")

        for anime in watchlist:
            season_str = anime.season or ""
            entry = link_manager.get(anime.name, site, season_str)
            if entry is None:
                status_disp = "[red]✗[/red]"
                explicit_disp = "—"
                url_disp = "—"
            else:
                status, url, explicit = entry
                status_disp = (
                    "[green]✓ found[/green]" if status == "found"
                    else "[yellow]not_found[/yellow]"
                )
                explicit_disp = "[green]yes[/green]" if explicit else "[dim]no[/dim]"
                url_disp = url or "—"
            table.add_row(anime.name, season_str or "—", status_disp, explicit_disp, url_disp)
        console.print(table)

        console.print("\n[bold]Options:[/bold]")
        console.print("1. Assign / re-discover a link for an anime")
        console.print("2. Toggle 'explicit' on an existing link")
        console.print("3. Remove a link from the cache")
        console.print("4. Exit")
        action = Prompt.ask("Choose", choices=["1", "2", "3", "4"], default="4")
        if action == "4":
            return

        # Select anime
        console.print("\nSelect an anime:")
        for i, anime in enumerate(watchlist, 1):
            console.print(f"{i}. {anime.name} [dim]({anime.season or 'no season'})[/dim]")
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

        season_str = selected_anime.season or ""

        if action == "1":
            console.print(f"\n[bold]{selected_anime.name}[/bold]")
            console.print("1. Re-discover from site (search + score)")
            console.print("2. Enter URL manually")
            sub = Prompt.ask("Choose", choices=["1", "2"], default="1")

            if sub == "1":
                console.print("[dim]Searching...[/dim]")
                status, url = scraper.discover_series_url(selected_anime)
                if status == "found":
                    link_manager.set(selected_anime.name, site, season_str, "found", url)
                    console.print(f"[green]✅ Found:[/green] {url}")
                else:
                    link_manager.set(selected_anime.name, site, season_str, "not_found", "")
                    console.print("[yellow]✗ Not found on site.[/yellow]")
            else:
                url = Prompt.ask("Enter full URL")
                if not url:
                    continue
                if "/anime/" not in url:
                    if not Confirm.ask("[yellow]URL does not look like an anime page. Continue?[/yellow]"):
                        continue
                link_manager.set(
                    selected_anime.name, site, season_str, "found", url,
                    explicit=True, override_explicit=True,
                )
                console.print(f"[green]✅ Assigned (explicit):[/green] {url}")

        elif action == "2":
            entry = link_manager.get(selected_anime.name, site, season_str)
            if entry is None:
                console.print("[red]No cached link.[/red]")
                continue
            status, url, explicit = entry
            link_manager.set(
                selected_anime.name, site, season_str, status, url,
                explicit=not explicit, override_explicit=True,
            )
            console.print(f"[green]Explicit set to {not explicit}.[/green]")

        elif action == "3":
            link_manager.invalidate(selected_anime.name, site, season_str)
            if link_manager.get(selected_anime.name, site, season_str) is not None:
                console.print(
                    "[yellow]Link is explicit and was not removed. "
                    "Toggle explicit off first.[/yellow]"
                )
            else:
                console.print("[green]Removed cache entry.[/green]")
# ------------------------------------------------------------
# TUI Views
# ------------------------------------------------------------
def view_watchlist(file_path: Path, status_filter: Optional[str] = None):
    watchlist = load_watchlist(file_path)
    if not watchlist:
        console.print(f"[yellow]{file_path.name} is empty.[/yellow]")
        return

    # Filter
    if status_filter:
        shown = [a for a in watchlist if a.status == status_filter]
        title = status_filter.title()
    else:
        shown = watchlist
        title = "All"

    shown = sorted(shown, key=lambda a: a.name.lower())

    if not shown:
        console.print(f"[yellow]No entries in status '{status_filter}'.[/yellow]")
        return

    table = Table(
        title=f"{file_path.stem.title()} – {title}",
        title_style="bold cyan",
        header_style="bold cyan",
        box=box.ROUNDED,
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Anime", style="white")
    table.add_column("Status", justify="center", style="green")
    table.add_column("Season", justify="center", style="green")
    table.add_column("Downloaded", justify="right", style="cyan")
    table.add_column("Watched", justify="right", style="magenta")

    for i, a in enumerate(shown, 1):
        season = a.season or "—"
        dl = str(a.downloaded) if a.downloaded > 0 else "—"
        wt = str(a.watched) if a.watched > 0 else "—"
        table.add_row(str(i), a.name, a.status, season, dl, wt)

    console.print(table)

def update_watched_entry():
    ctype = choose_content_type("Update Watched")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    update_watched(file_path)

def update_watched(file_path: Path):
    """Update the watched progress for one or more anime in the given watchlist."""
    watchlist = load_watchlist(file_path)
    watching = [a for a in watchlist if a.status in ("watching", "ended", "dropped")]
    if not watching:
        console.print(f"[yellow]No updateable entries in {file_path.name}.[/yellow]")
        return

    while True:
        console.print(f"\n[bold cyan]Update Watched – {file_path.stem.title()}[/bold cyan]")
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", pad_edge=False)
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Anime", style="white")
        table.add_column("Status", justify="center", style="green")
        table.add_column("Downloaded", justify="right", style="cyan", width=10)
        table.add_column("Watched", justify="right", style="magenta", width=8)

        for i, anime in enumerate(watching, 1):
            dl = str(anime.downloaded) if anime.downloaded > 0 else "—"
            wt = str(anime.watched) if anime.watched > 0 else "—"
            table.add_row(str(i), anime.name, anime.status, dl, wt)
        table.add_row("0", "[italic]Back[/italic]", "", "", "")
        console.print(table)

        choice = Prompt.ask(
            "Select anime to update (0 to exit)",
            choices=[str(i) for i in range(len(watching) + 1)],
            default="0",
        )
        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(watching)):
                console.print("[red]Invalid selection.[/red]")
                continue
            anime = watching[idx]
        except ValueError:
            console.print("[red]Invalid input.[/red]")
            continue

        console.print(f"\n[bold]{anime.name}[/bold]")
        console.print(f"Downloaded: [cyan]{anime.downloaded}[/cyan]")
        console.print(f"Watched:    [magenta]{anime.watched}[/magenta]")
        console.print("\nOptions:")
        console.print("1. Set watched to a specific episode")
        console.print("2. Increment watched by 1")
        console.print("3. Set watched = downloaded (catch up)")
        console.print("0. Cancel")
        action = Prompt.ask("Choose", choices=["1", "2", "3", "0"], default="0")
        if action == "0":
            continue

        new_watched = anime.watched
        if action == "1":
            val = Prompt.ask("Enter episode number", default=str(anime.watched))
            try:
                new_watched = int(val)
            except ValueError:
                console.print("[red]Invalid number.[/red]")
                continue
        elif action == "2":
            new_watched = anime.watched + 1
        elif action == "3":
            new_watched = anime.downloaded

        if new_watched < 0:
            console.print("[red]Watched cannot be negative.[/red]")
            continue
        if new_watched > anime.downloaded:
            if not Confirm.ask(
                f"[yellow]Watched ({new_watched}) exceeds downloaded "
                f"({anime.downloaded}). Continue?[/yellow]"
            ):
                continue

        anime.watched = new_watched
        save_watchlist(watchlist, file_path)
        console.print(f"[green]✅ {anime.name} watched → {new_watched}[/green]")

def view_available(file_path: Path, anime_name: Optional[str] = None):
    watchlist = load_watchlist(file_path)
    if not watchlist:
        console.print(f"[yellow]{file_path.name} is empty.[/yellow]")
        return

    if anime_name:
        anime = get_anime_by_name(anime_name, file_path)   # ← added file_path
        if not anime:
            console.print(f"[red]Anime '{anime_name}' not found in {file_path.name}.[/red]")
            return
        latest = get_latest_with_fallback(anime)
        if latest == 0:
            console.print(f"[yellow]No episodes found for {anime.name}[/yellow]")
        else:
            missing = get_missing_episodes(anime.downloaded, latest)
            console.print(
                f"[cyan]{anime.name}[/cyan]: latest = [green]{latest}[/green], "
                f"missing = {missing if missing else 'None'}"
            )
        return

    table = Table(title="Available Downloads", title_style="bold magenta", header_style="bold cyan", box=box.ROUNDED)
    table.add_column("Anime", style="white", no_wrap=False)
    table.add_column("Latest", justify="center", style="green")
    table.add_column("Missing", justify="center", style="yellow")

    for anime in watchlist:
        if anime.status == "completed":
            continue
        latest = get_latest_with_fallback(anime)
        missing = get_missing_episodes(anime.downloaded, latest) if latest > 0 else []
        table.add_row(
            anime.name,
            str(latest) if latest > 0 else "—",
            ", ".join(map(str, missing)) if missing else "None"
        )
    console.print(table)


# ----------------------------------------------------------------
# Warpers 
# ----------------------------------------------------------------
def page_links_entry():
    ctype = choose_content_type("Page Links")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    manage_page_links(file_path)

def view_available_entry():
    ctype = choose_content_type("View Available")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    name = Prompt.ask("Enter anime name (or press Enter for all)", default="")
    view_available(file_path, name if name else None)

def download_entry():
    ctype = choose_content_type("Download")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    download_submenu(file_path)

def scan_new_links_entry():
    """Discover new series from data/links/ and add them to the watchlist.

    DISCOVERY ONLY — no downloads, no progress mutations.
    """
    console.print("\n[bold cyan]Scanning data/links/...[/bold cyan]\n")
    try:
        report = scan_links_dir()
    except Exception as e:
        logger.exception("Link cache scan failed")
        console.print(f"[red]Scan failed: {e}[/red]")
        return

    for title, ctype in report.already_tracked:
        console.print(
            f"  [green]✓[/green] {title} [dim]({ctype})[/dim] — already in watchlist"
        )
    for title, ctype in report.added:
        console.print(
            f"  [bold green]+[/bold green] {title} [dim]({ctype})[/dim] "
            f"— added to watchlist"
        )
    for path, reason in report.invalid:
        console.print(f"  [yellow]![/yellow] {path.name} — skipped ({reason})")

    console.print()
    console.print(f"[bold]{report.scanned}[/bold] link file(s) scanned")
    console.print(
        f"[bold green]{len(report.added)}[/bold green] new entry added"
    )
    console.print(
        f"[bold]{len(report.already_tracked)}[/bold] already tracked"
    )
    if report.invalid:
        console.print(
            f"[yellow]{len(report.invalid)}[/yellow] invalid file(s) skipped"
        )
    console.print("\n[dim]No downloads performed.[/dim]")

# =======================================================


def download_submenu(file_path: Path):
    """Download flow scoped to a specific watchlist file."""
    watchlist = load_watchlist(file_path)
    watching = [a for a in watchlist if a.status == "watching"]
    if not watching:
        console.print(
            f"[yellow]No anime in 'watching' status in {file_path.name}.[/yellow]"
        )
        return

    console.print(f"\n[bold cyan]Select Anime to Download – {file_path.stem.title()}[/bold cyan]")
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", pad_edge=False)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Anime", style="white")
    table.add_column("Downloaded", justify="right", style="cyan", width=10)
    table.add_column("Watched", justify="right", style="magenta", width=8)

    for i, anime in enumerate(watching, 1):
        dl = str(anime.downloaded) if anime.downloaded > 0 else "—"
        wt = str(anime.watched) if anime.watched > 0 else "—"
        table.add_row(str(i), anime.name, dl, wt)

    table.add_row("0", "[italic]Download all[/italic]", "", "")
    console.print(table)

    choice = Prompt.ask(
        "Enter number",
        choices=[str(i) for i in range(len(watching) + 1)],
        default="0",
    )

    if choice == "0":
        for anime in watching:
            process_anime_background(anime, watchlist, file_path)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(watching):
                process_anime_background(watching[idx], watchlist, file_path)
            else:
                console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Invalid input.[/red]")


# -------------------------------------------------------------
# Retry Failed Functions
# -------------------------------------------------------------
#
def retry_failed(file_path: Path):
    failed = load_failed()
    if not failed:
        console.print("[green]No failed downloads recorded.[/green]")
        return
    console.print(f"[yellow]Found {len(failed)} failed download(s). Retrying...[/yellow]")
    watchlist = load_watchlist(file_path)
    for name, ep in failed:
        anime = get_anime_by_name(name, file_path)
        if not anime:
            console.print(f"[red]Anime '{name}' not in {file_path.name}; removing from failed log.[/red]")
            remove_success(name, ep)
            continue
        console.print(f"[cyan]Queuing {name} episode {ep}[/cyan]")
        download_episode_background(anime, ep, watchlist, file_path)

def retry_failed_entry():
    ctype = choose_content_type("Retry Failed")
    if ctype is None:
        return
    file_path = WATCHLIST_FILES[ctype]
    retry_failed(file_path)

# ====================================================================

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


# -----------------------------------------------------------
# Run-Time Toggle
# ------------------------------------------------------------
# Runtime state
_runtime_content_type = None  # None → use config default


def get_default_content_type() -> str:
    """Return the active default content type (config or runtime override)."""
    return _runtime_content_type or DEFAULT_CONTENT_TYPE


def set_default_content_type(ctype: str) -> None:
    """Persist the runtime default for the rest of the session."""
    global _runtime_content_type
    if ctype in ("anime", "donghua"):
        _runtime_content_type = ctype
        console.print(f"[green]Default content type → {ctype}[/green]")


def switch_default_menu():
    """Interactive: switch the global default content type."""
    current = get_default_content_type()
    console.print(f"\n[bold cyan]Default content type[/bold cyan] (currently: {current})")
    console.print("1. Anime")
    console.print("2. Donghua")
    console.print("0. Cancel")
    choice = Prompt.ask("Choose", choices=["0", "1", "2"], default="0")
    if choice == "1":
        set_default_content_type("anime")
    elif choice == "2":
        set_default_content_type("donghua")




# ------------------------------------------------------------
# Main TUI
# ------------------------------------------------------------

def tui():
    console.print(Panel.fit(f" Anime Downloader v{VERSION} ", style="bold magenta"))

    # Quiet startup scan: discover new link caches without user action.
    # Never downloads; only adds missing watchlist entries.
    try:
        startup_report = scan_links_dir()
        if startup_report.added:
            console.print(
                f"[green]Link cache: {len(startup_report.added)} new entry(ies) "
                f"added — run [bold]scan[/bold] for details[/green]"
            )
    except Exception:
        logger.exception("Startup link-cache scan failed")

    console.print(
        "[dim]Shortcuts: \\[w]atchlist \\[d]ownload \\[v]iew available \n"
        "\\[r]etry failed \\[s]earch \\[l]ogs \\[q]ueue status \\[p]age links\n "
        "\\[scan] links \\[c]hange status \\[u]pdate watched \\[D]efault type "
        "\\[quality] \\[t]est \\[e]xit[/dim]\n"
    )

    while True:
        status = QUEUE.get_status()
        if status:
            active = sum(1 for s in status.values() if s[0] == "downloading")
            queued = sum(1 for s in status.values() if s[0] == "queued")
            console.print(f"[dim]Queue: {active} downloading, {queued} queued[/dim]")

        choice = Prompt.ask(
            "[bold cyan]Command[/bold cyan]",
            choices=["w", "d", "v", "r", "s", "l", "q", "p", "scan", "quality", "c", "u", "D", "t", "e"],
            default="w"
        )

        if choice == "w":
            watchlist_menu()
        elif choice == "d":
            download_entry()
        elif choice == "v":
            # name = Prompt.ask("Enter anime name (or press Enter for all)", default="")
            view_available_entry(name if name else None)
        elif choice == "r":
            retry_failed_entry()
        elif choice == "s":
            search_anime()
        elif choice == "l":
            view_logs()
        elif choice == "q":
            show_queue_status()
        elif choice == "p":
            page_links_entry()
        elif choice == "quality":
            set_download_quality()
        elif choice == "t":
            test_modules()
        elif choice == "c":
            change_status_menu()
        elif choice == "u":
            update_watched_entry()
        elif choice == "D":
            switch_default_menu()
        elif choice == "scan":
            scan_new_links_entry()
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
    parser.add_argument("--sync-links", action="store_true", help="Sync links for all watchlists")
    parser.add_argument("--type", choices=["anime", "donghua"], default=None,
                        help="Which watchlist to operate on (default: config)")
    args = parser.parse_args()

    # 1. Debug flag (independent of dispatch)
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    # 2. Dispatch – first matching branch wins
    if args.sync_links:
        for ctype, fp in WATCHLIST_FILES.items():
            sync_links(fp, ctype)
        return

    if args.menu or (not args.test_anime and not args.sync_links):
        tui()
        return

    # 3. Non-interactive download paths
    ctype = args.type or get_default_content_type()
    file_path = WATCHLIST_FILES[ctype]

    if args.test_anime:
        watchlist = load_watchlist(file_path)
        anime = get_anime_by_name(args.test_anime, file_path)
        if anime:
            process_anime_background(anime, watchlist, file_path)
        else:
            logger.error(f"Anime '{args.test_anime}' not found in {file_path.name}.")
        return

    # 4. No specific flag → download all in the chosen content type
    watchlist = load_watchlist(file_path)
    for anime in watchlist:
        process_anime_background(anime, watchlist, file_path)

if __name__ == "__main__":
    main()