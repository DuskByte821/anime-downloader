# Anime Downloader Roadmap

## Purpose

Maintain a reliable command-line and Textual interface for discovering anime and donghua episodes, reusing cached source links, tracking progress, and downloading only when the user requests it. Preserve the existing file-based workflow and keep anime and donghua state separate.

## Current foundation

The repository contains a CLI entry point in `main.py`, an optional Textual TUI, watchlist files for anime and donghua, scraper/search modules, link-cache and link-management code, a download queue manager, downloader logic, logging, and automated tests. `main.py` exposes options for the interactive menu, TUI, link synchronization, debug logging, content type, and targeting a title. Existing scraper support includes Lucifer Donghua and CartoonsArea modules. Treat these as code paths present in the repository, not as a guarantee that every upstream page or workflow currently succeeds.

The TUI has Home, Search, and Title Details screens. The details screen defines an eight-entry episode window. Its `f` binding calls a no-op favorite action and reports that favorites are not implemented. Do not list favorites as a working feature. Audio-language filtering and external-player playback are not present in the current details-screen implementation; they remain future work unless verified in a later code change.

## Non-negotiable design rules

- Keep anime and donghua watchlists separate (`data/anime.txt` and `data/donghua.txt`).
- Preserve existing watchlist formats, sections, and progress when adding discovery or download features.
- Keep discovery/synchronization separate from downloading. Scanning for links must not start downloads implicitly.
- Prefer usable cached links to repeated scraping, but retain a clear fallback/error path when cache entries are absent or stale.
- Do not discard cached source data merely because a download succeeded.
- Route progress updates to the correct content type and watchlist path.
- Keep scraper-specific parsing in scraper modules and avoid coupling UI widgets directly to website HTML.
- Make tests deterministic and avoid relying on live websites for ordinary unit tests.

## Priorities

### P0 — Correctness and test reliability

- Fix the current test failures before treating the suite as a reliable regression gate.
- Remove accidental live-network dependence from tests; use fixtures and mocked HTTP responses.
- Add regression tests for watchlist type/path selection, progress preservation, duplicate discovery, cache reuse, failed downloads, and malformed upstream responses.
- Ensure logs and errors identify the affected title, episode, and source without silently corrupting local state.

### P1 — Complete and clarify the TUI

- Implement or remove the placeholder favorites action; do not imply that it persists favorites until storage and behavior exist.
- Implement audio-language filtering only after stream metadata exposes a dependable language field.
- Add external-player playback only with an explicit player invocation and clear handling when the player is unavailable.
- Ensure selecting a season loads that season's episodes, selecting an episode loads its streams, and download actions use the selected episode and stream.
- Keep the streams table visible alongside the selectors where practical, and keep contextual key hints synchronized with actual bindings.
- Document slash commands and shortcuts from the bindings that exist in code, not from a design proposal.

### P1 — Scraper and cache resilience

- Add fixture-based coverage for supported scrapers and common upstream changes.
- Make stale, empty, rejected, or malformed cached links distinguishable from valid links.
- Improve diagnostics when a source changes markup or blocks a request.
- Keep source-specific behavior isolated so adding a scraper does not require rewriting watchlist or downloader logic.

### P2 — Download management

- Improve retry and resume behavior only where the downloader backend supports it safely.
- Make queue state, failures, and completion visible and recoverable.
- Review output naming and destination rules for anime and donghua without changing watchlist storage semantics.
- Preserve existing files and progress when a download fails or is interrupted.

### P2 — Usability and maintenance

- Keep the README, architecture, project-state, conventions, and roadmap aligned with verified code.
- Keep configuration centralized and avoid unnecessary hard-coded paths.
- Add focused tests for each bug fix and avoid broad refactors without a concrete benefit.
- Keep user-facing commands and help text consistent with argparse definitions and TUI bindings.

## Out of scope until justified

Do not introduce a database, large plugin framework, automatic downloading on startup, or broad parallel-download machinery just for abstraction's sake. Evaluate new sources and features against reliability, maintenance cost, and the existing modular design.

## Definition of done

A change is ready when its behavior matches the code and documentation, the correct watchlist and cache are preserved, errors are handled without damaging user data, tests cover the relevant success and failure paths, and the focused tests pass. Run the full test suite before describing the repository as green; report failures and environment limitations honestly.
