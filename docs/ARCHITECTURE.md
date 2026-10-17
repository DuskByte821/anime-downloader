# Anime Downloader Architecture

This document describes the architecture visible in the current source tree. It distinguishes the legacy Rich/Prompt CLI from the newer Textual TUI; the two interfaces do not expose identical workflows.

## Application entry points

`main.py` is the command-line entry point and owns the legacy interactive menu as well as non-interactive dispatch. With no flags, it opens the legacy menu. `--menu` also selects that menu, `--tui` launches `tui.app.AnimeDownloaderApp`, `--sync-links` synchronizes links for both configured watchlists, and `--test-anime NAME` processes one matching title. `--type anime|donghua` selects the watchlist for the non-interactive download paths. The legacy menu exposes watchlist, download, available-episode, retry, search, log, queue, page-link, scan, quality, status, watched-progress, and default-content-type actions.

The Textual TUI starts at `tui/screens/home.py`, sends ordinary search text to `SearchScreen`, and dispatches slash commands through `tui/app.py`. The visible flow is Home → Search Results → Title Details. Home history/resume and TV are placeholders, and the `help` binding attempts to push a screen named `help` although no help screen is defined in the supplied tree. The details screen shows one season value, an episode selector, and a streams table; it is not a full multi-season browser. Its episode window is eight entries. The `f` binding only displays a “Favourites not implemented in v1” notification. Favourites have no data model or storage — implementing them requires new watchlist fields or a separate file, and a decision about scope. Treat f as unused, not as a nearly-complete feature. The streams table is populated using `yt-dlp -J`; the current UI renders stream information, but its download action queues the selected episode URL rather than selecting the highlighted stream's format URL. Audio-language filtering and external-player playback are not present in the current details-screen code.

## Core modules and responsibilities

- `config.py` defines paths, version, default content type, request/retry settings, download quality options, scraper base URLs, source preferences, and media-detection thresholds. It creates the data, logs, downloads, and link-cache directories at import time.
- `models.py` defines the `Anime` domain model used across watchlists and scrapers.
- `watchlist.py` loads, normalizes, changes, and saves title records and their status/progress. Anime and Donghua are kept in separate files: `data/anime.txt` and `data/donghua.txt`.
- `scraper/` contains the source abstraction and source-specific discovery. `LuciferDonghuaScraper` provides the primary search/episode discovery path used by the TUI. `CartoonsAreaScraper` is also wired into the legacy engine as a fallback/source option. Shared HTTP helpers and a scraper response cache are in `scraper/http.py` and `scraper/cache.py`; parsing and rejected-candidate logging are separated into helper modules.
- Three distinct caches exist and must not be confused:

    link_manager.py → data/links.txt — series URL cache. One row per (title, site, season), storing the canonical series page URL and a status (found/not_found) plus an explicit flag. The explicit flag protects hand-picked URLs from being overwritten by sync.

    link_cache.py → data/links/<slug>.txt — per-series episode URL caches. One file per series, episode_number::episode_url per line, plus optional metadata header. Populated by the legacy [scan] workflow, or written manually.

    scraper/cache.py → data/meta/ — HTTP response cache (in-memory, per session) and disk JSON caches for series metadata (7-day TTL) and episode maps (1-day TTL).

    Do not treat these as one interchangeable store.

- `downloader.py` resolves/downloads media through direct media URLs or `yt-dlp`, applies the configured quality options, checks for preview-sized/short content, and handles download output. `queue_manager.py` tracks queued/active job state. `failed_downloads.py` records failed jobs for retry.
- `updater.py` and `watchlist.py` persist successful download progress and other user state. The interface/engine must pass the selected watchlist path rather than relying on the legacy `WATCHLIST_FILE` alias, which points to the Anime watchlist.
- `tui/data.py` is an adapter between the Textual screens and existing project logic: it searches Lucifer Donghua, obtains metadata/episode maps, inspects stream formats through a `yt-dlp -J` subprocess, looks up or creates watchlist entries, and queues downloads.

## Data and workflow boundaries

The watchlist and link cache are separate sources of truth. A watchlist stores user state: title, season, status, downloaded progress, and watched progress. `data/links/` stores discovered title/episode URLs and is used by the legacy scan/synchronization workflow. Scraper response caching is a separate optimization for fetched pages/responses.

Anime operations must use `data/anime.txt`; Donghua operations must use `data/donghua.txt`. Carry the chosen content type and watchlist path through lookup, download, retry, and update operations. `config.WATCHLIST_FILE` is a backwards-compatibility alias for the Anime file, not a safe generic default.

Discovery, download, and progress updates are distinct actions. The legacy menu runs a quiet link-cache scan at startup; scanning imports missing entries from `data/links/` into the appropriate watchlist and is not itself a download operation. The legacy `sync_links` workflow contacts configured scrapers to discover/update source links for titles already in a watchlist. Download workflows select episode URLs from cached/discovered sources, call the downloader, and update the same selected watchlist after success. The TUI uses its own search → metadata/episode lookup → queue path and does not currently implement every legacy cache-management workflow. The TUI does not implement parallel business logic. tui/data.py instantiates and calls the same LuciferDonghuaScraper, download_file, QUEUE.add_job, and update_watchlist that main.py uses. Any difference in behavior between CLI and TUI is a difference in which engine functions the TUI calls, not in how those functions behave.

## Key invariants for contributors

1. **Preserve content-type isolation.** Never let an Anime operation update the Donghua watchlist or vice versa. Pass the selected file path explicitly through updater/download/retry code.
2. **Keep user progress separate from discovered links.** A newly discovered URL or a cache scan must not increment downloaded or watched progress.
3. **Only successful downloads update downloaded progress.** Failures should be logged/recorded for retry without being counted as completed downloads.
4. **Keep discovery separate from downloading.** Search, scan, cache refresh, and link synchronization must not silently trigger downloads.
5. **Preserve existing watchlist state.** Importing or refreshing links must not duplicate titles or overwrite existing status/progress.
6. **Reuse shared models and helpers.** Scrapers discover source data; watchlist modules own watchlist parsing/persistence; downloader modules own media retrieval; interfaces select and display workflows rather than duplicating engine logic.
7. **Keep external network work failure-tolerant.** A source or title failure should be logged and isolated where possible rather than aborting unrelated work.
8. **Keep tests independent of live sites and real user data.** Prefer fixtures and temporary paths; tests should not require working external DNS or mutate repository watchlists.

## External dependencies and upstream behavior

The project relies on website HTML/API structures that can change independently of this repository. Lucifer Donghua search uses site-specific requests/parsing, and episode pages can expose multiple mirrors or embeds. CartoonsArea has its own page layout and resolver assumptions. These sources may rate-limit, change markup, remove episodes, or fail transiently; cache data can therefore become stale.

The downloader relies on the external `yt-dlp` executable for supported extraction and metadata/format inspection, and on `wget` for URLs treated as direct media by the downloader. The TUI's stream-inspection adapter invokes `yt-dlp -J` with a timeout and returns an empty stream list if the command fails. Format metadata is not guaranteed to include file sizes or all codecs. External player launching is not wired into the current TUI details flow.

## Testing

The test suite covers watchlist/model behavior, cache and link-manager logic, downloader/updater integration, queue handling, resolvers, and Lucifer Donghua parsing/search. Source fixtures are under `tests/fixtures/`. Keep unit tests deterministic and mocked where practical; a test that reaches a live site is vulnerable to DNS, rate limiting, and upstream markup changes.
