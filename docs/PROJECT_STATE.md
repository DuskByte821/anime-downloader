# Project State

**Repository:** https://github.com/ZainALI-LAB/anime-downloader · **Version:** 2.2.1 (`config.py`) · **Python:** 3.14 in the supplied project environment; no packaging metadata declares a supported version range. Runtime dependencies used by the code are `requests`, `beautifulsoup4`, `rich`, `textual`, and `yt-dlp`; `pytest` is needed for tests. `wget` and `ffprobe` are optional external tools. The repository ZIP does not include a dependency lockfile or requirements manifest, so this list is derived from imports and code paths.

## Architecture

`main.py` provides the Rich-based CLI/menu and dispatches download, link-sync, and TUI modes. The Textual frontend in `tui/` has Home, Search, and Title Details screens; `tui/data.py` bridges screen actions to the existing scraper, watchlist, queue, and downloader logic. The engine is shared: `watchlist.py` and `models.py` manage progress, `scraper/` discovers titles and episode sources, `downloader.py` retrieves media, `queue_manager.py` runs queued jobs, and `updater.py` persists progress. Configuration and runtime paths are centralized in `config.py`.

## Feature inventory — code checked

- **CLI:** `python main.py` opens the interactive menu; `--menu`, `--debug`, `--type anime|donghua`, `--test-anime NAME`, `--sync-links`, and `--tui` are accepted. Anime and donghua use separate watchlist files.
- **Watchlists/progress:** entries are loaded and saved through the watchlist module; downloaded and watched progress are distinct; statuses include watching, ended, dropped, and completed. Download updates carry the originating watchlist path.
- **Scraping/search:** `LuciferDonghuaScraper` supports search, series discovery, episode mapping, and source extraction. Search tries the site's AJAX endpoint and has an HTML fallback. `CartoonsAreaScraper` exists but is a stub, not a functioning fallback.
- **Downloads:** quality presets are best, 1080p, and 720p (default). The downloader can use yt-dlp, and direct-media paths use wget with a requests fallback. Queue status and failed-download tracking exist. Preview/short-file checks and optional ffprobe validation are present in code.
- **Caching/links:** scraper HTTP/session caching, disk metadata/episode caches, link-cache management, and link synchronization exist. Explicitly selected cached series URLs are protected from ordinary link synchronization.
- **TUI:** Home accepts a search query or slash command; Search loads results asynchronously and supports up/down/Enter/Escape; Details displays a season selector, an episode list with an eight-item sliding window, and a streams table. The Details screen has focus regions and a `d` download binding. Slash commands recognized by `app.py` are `/help`, `/watchlist`, `/downloads`, `/settings`, `/scraper`, `/quality`, `/type`, and `/clear`.
- **Tests:** 122 tests collected, 112 passed, 10 failed as of 2026-10-17, pytest 9.0.2, Python 3.14
 
## Incomplete or missing — confirmed in code

The TUI is a partial interface, not feature-equivalent to the CLI. The Home history area is static (“No history yet”); TV view is explicitly a no-op; Home's help action pushes a screen name that is not defined in the supplied screen modules; and the favorite binding calls a no-op. Details currently loads one season from metadata rather than providing working multi-season navigation. The streams table displays rows, but no stream-row activation handler is defined. `/settings`, `/scraper`, `/watchlist`, and `/downloads` show notifications/summaries rather than dedicated interactive screens; `/scraper` does not configure a scraper. Audio-language filtering and external-player playback are not present in the inspected TUI code. Do not describe these as available features. The supplied code also does not expose a `--clear-cache` CLI option.

## Invariants and contributor conventions

Keep `Anime.downloaded` separate from `Anime.watched`; downloads must not silently advance watched progress. Always pass the correct watchlist `file_path` through queue/download/update calls so anime and donghua writes cannot cross. Preserve the updater's non-regression behavior and the `downloaded >= watched` invariant. Scraper HTTP requests should use `scraper/http.py` helpers rather than adding ad hoc fetches. Do not cache failed fetches or failed parses. Add fixture-based tests for scraper changes; tests should not depend on live sites. Preserve the Textual app's `ansi_color = True` and transparent CSS backgrounds, which support the intended translucent-terminal appearance.

## Known upstream quirks

Lucifer Donghua's series page has nested title markup; parsing only the first `h1` is unreliable. Search result titles may be prefixed with “DONGHUA Ongoing Sub”, which the HTML search parser strips. The AJAX search response can omit its expected `anime` key; that path returns an empty result list rather than triggering HTML fallback. Some Dailymotion episode pages lazy-load their iframe and require a `data-src` fallback. These are source-site behaviors handled by scraper code and should be preserved in regression tests.

## Commands

Run the CLI/menu with `python main.py`; launch the Textual UI with `python main.py --tui`; process one title with `python main.py --test-anime "Title"`; synchronize cached links with `python main.py --sync-links`; select a content type with `python main.py --type donghua` (or `anime`); run tests with `pytest tests/ -v`.
