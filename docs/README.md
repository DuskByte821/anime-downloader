# Anime Downloader

Anime Downloader is a Python terminal application for maintaining separate anime and donghua watchlists, searching supported scraper sources, and downloading episodes. The repository contains both a Rich-based interactive CLI and a Textual TUI; these interfaces are not feature-identical. Current configuration declares version **2.2.1**. The code uses `requests`, `beautifulsoup4`, `rich`, and `textual`; tests use `pytest`. `yt-dlp` is an external executable used for media downloads and metadata checks when available. The repository does not include a dependency lockfile or requirements file, so install these dependencies in your environment and verify compatibility there.

## Requirements and setup

Use a supported Python 3 environment. From the repository root, install the Python packages `requests`, `beautifulsoup4`, `rich`, `textual`, and `pytest` (the last is needed only for tests), and make `yt-dlp` available on `PATH` for the full download workflow. The application creates its `data/`, `logs/`, and `downloads/` directories from configuration when imported. Network access is required for live source searches and downloads.

## Running the application

Run `python main.py` to open the default interactive CLI menu. Run `python main.py --tui` to launch the Textual interface. The CLI also accepts `--menu` to force its interactive menu, `--type anime` or `--type donghua` to select the watchlist for non-interactive processing, `--test-anime "TITLE"` to process one title from that watchlist, `--sync-links` to synchronize cached links across both watchlists, and `--debug` to enable debug logging. With no `--tui`, `--sync-links`, or `--test-anime` option, `main.py` opens the CLI menu; do not assume a bare invocation starts a batch download.

The TUI currently has Home, Search, and Title Details screens. Home accepts a search query or slash command. The command handler recognizes `/help`, `/watchlist`, `/downloads`, `/settings`, `/scraper`, `/quality`, `/type`, and `/clear`. In Title Details, Tab/Shift+Tab (or left/right) changes the focus region, up/down navigates episodes or stream rows depending on focus, `d` invokes the download action, `i` opens information, and Escape returns. The episode window constant is eight. Favorites (`f`) and the Home TV shortcut are placeholders, not working features. Audio-language filtering and external-player playback are not available in the current TUI code. The help binding points to a help screen name that is not registered in the current screen implementation, so that path should be treated as incomplete.

## Watchlists and data

Anime and donghua are stored separately in `data/anime.txt` and `data/donghua.txt`. Each file uses status sections (`watching`, `ended`, `dropped`, and `completed`) and human-readable entries containing the title, optional season, downloaded count, and watched count. Keep the two content types separate and preserve the status-section structure when editing files manually. Configuration also places logs in `logs/`, downloads in `downloads/`, and link-cache data under `data/links/`.

## Sources and limitations

Scraper modules live in `scraper/`. The current code identifies Lucifer Donghua as the primary source and CartoonsArea as a fallback, but actual coverage depends on the individual scraper and the upstream site's current HTML, endpoints, and media providers. Upstream changes, rate limiting, DNS/network failures, and media-host behavior can break discovery or downloads. `yt-dlp` availability affects the media pipeline; direct media URLs may follow a separate path. Do not assume every result or every source is currently supported.

## Tests

Run the test suite from the repository root with `pytest tests/ -q`. Some search and integration behavior may depend on network calls unless properly mocked; a test run's pass/fail count should be recorded with the date and Python/pytest versions rather than treated as a permanent guarantee.

## Project documentation

See `docs/PROJECT_STATE.md` for the current verified state, `docs/ARCHITECTURE.md` for module responsibilities and data flow, `docs/CONVENTIONS.md` for invariants, `docs/CONTRIBUTING.md` for contribution guidance, and `docs/GOALS.md` for planned work. Prefer improvements to existing behavior and tests before adding new features.
