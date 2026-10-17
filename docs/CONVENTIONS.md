# Project Conventions

These rules describe the current codebase and the safeguards contributors should preserve.

## Watchlists and content types

- Keep anime and donghua data isolated. Pass the selected watchlist `file_path` through download, update, and save operations; do not rely on the legacy `WATCHLIST_FILE` alias when the content type is known.
- Watchlists use four status sections in this fixed order: `watching`, `ended`, `dropped`, `completed`. Keep the parser compatible with legacy entry forms and write the canonical `Name::season ...::downloaded N::watched N` format through `watchlist.py`.
- Use `normalize_name()` for case- and whitespace-insensitive name comparisons where appropriate. Preserve a series' season and status when updating progress.
- `update_watchlist()` reloads the selected file before modifying it and does not lower an existing downloaded episode number. Keep successful-download updates tied to the correct file path.

## Scraping and caching

- Route scraper HTTP requests through `scraper/http.py` (`fetch_html()` for HTML GETs and `post_json()` for form POSTs). Do not add direct `requests.get()` or `requests.post()` calls inside scraper modules; the shared helpers provide timeouts, per-host pacing, and consistent failure handling.
- Treat failed requests or failed parsing as failures, not successful cached data. Only write cache entries after obtaining valid data. Respect the separate in-memory HTML cache and TTL-based JSON metadata/episode-map caches in `scraper/cache.py`.
- Keep site-specific parsing and URL rules in the relevant scraper module. Shared normalization, resolution, HTTP, cache, and rejected-link behavior belongs in the shared scraper helpers when it genuinely applies across sources.
- Upstream HTML and endpoints can change. Handle missing fields, empty results, and unavailable pages without assuming every expected element exists; log useful context rather than silently fabricating results.

## Downloads and progress

- Keep download destination naming, quality selection, preview-size checks, retries, and yt-dlp options consistent with `config.py` and `downloader.py` rather than duplicating their constants. Direct-media URLs (.mp4, .mkv, .webm) route through wget (with a requests fallback) and skip yt-dlp entirely — do not route them through yt-dlp; the format selector will fail on plain file URLs.
- Advance downloaded progress only after the download has been verified as a usable episode. Do not treat a small preview or an unsuccessful transfer as a completed episode.
- Keep logging on the configured logger path. Avoid printing asynchronous worker messages directly into an active CLI prompt or TUI; surface user-facing status through the interface layer.

## TUI boundaries

- Keep Textual presentation in `tui/` and use `tui/data.py` / `tui/metadata.py` as the boundary to project data and metadata. Avoid copying scraper or downloader logic into screen classes.
- Do not label placeholder bindings as working features. In particular, the current details screen's `f` action is a notification-only no-op for favorites; document and test behavior that exists in code, not only behavior planned in the design.
- Network and download work should not block interactive rendering. Follow the existing asynchronous/task patterns when adding slow operations, and keep key hints consistent with the action actually bound.
- ansi_color = True and transparent backgrounds — must be preserved.
- Key handling must be in on_key, not by adding arrow-key bindings to BINDINGS (which get shadowed by VerticalScroll's defaults). This was a real bug we hit; worth documenting so it isn't re-introduced.

## Tests and changes

- Add or update deterministic tests for behavior changes. Prefer checked-in fixtures and mocked HTTP/download calls; tests should not depend on a live upstream website or available public DNS.
- When fixing a regression, add a test that reproduces it and run the relevant test module, then the full `pytest tests/ -q` suite.
- Keep test fixtures representative of the HTML or JSON shape the scraper expects, and update them deliberately when the parser contract changes.
- Do not claim a feature or test suite is working solely because a code path exists: verify its observable behavior and record known failures accurately.
