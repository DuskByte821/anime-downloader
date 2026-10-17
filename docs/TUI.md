# TUI Guide and Current Behavior

The Textual interface is launched with `python main.py --tui`. It is a separate front end over the existing scraper, watchlist, queue, and downloader modules; it is not a separate download engine. This document describes the behavior visible in the current source code, including incomplete controls.

## Screens

### 1. Home

The home screen shows the application name and version, a search input, a placeholder History / Resume section, and footer hints. The history section currently displays static “No history yet” text; it is not populated from persisted history. The search input is focused when the screen opens.

Enter a search phrase to open the Search screen. Enter a slash command to dispatch it through the app. `q` quits. `Ctrl+T` displays a notification that the TV view is not implemented. "?" currently raises an error because it pushes a screen named "help" that isn't registered. Use /help for a slash-command summary.

### 2. Search results

The Search screen runs the search in a background worker and displays each result's title, latest episode value, and a hard-coded “Lucifer Donghua” source label. The current TUI search adapter calls `LuciferDonghuaScraper`; the screen does not currently offer a scraper selector or combine results from multiple sources.

- `Up` / `Down`: move the highlighted result, wrapping at the ends.
- `Enter`: open the highlighted result's details.
- `Esc`: return to the previous screen.

If no results are returned, the screen displays “No results found.”

### 3. Title details

The details screen loads series metadata and an episode-to-URL map through the existing Lucifer Donghua scraper. The header shows the title and any available status, type, and release metadata. The season column currently renders one season number from metadata (or defaults to Season 1); it is not a multi-season selector. The seasons region has focus but no key handlers — pressing Up/Down there does nothing meaningful. Only the episode and streams regions respond to arrows. The episode column displays a sliding window of up to eight episodes, defined by `EPISODE_WINDOW_SIZE = 8`. The streams table remains visible beside the selectors.

- `Tab` / `Shift+Tab` or `Left` / `Right`: change the focused region (season, episode, streams).
- `Up` / `Down` while the episode region is focused: move between episodes and request stream data for the selected episode.
- `Up` / `Down` while the streams region is focused: move the table cursor.
- `i`: open the information modal, showing the description when available.
- `d`: queue a download for the selected episode through the existing queue manager.
- `Esc`: return to search results.
- `f`: show “Favourites not implemented in v1.” No favorite is saved.

The footer displays contextual hints, but some hints describe behavior that is not wired up yet. In particular, there is no implemented Enter action for choosing a season or episode. Pressing `d` while the streams region is focused still queues the selected episode; it does not download the currently highlighted stream/format. d always queues the selected episode using the default source-resolution path, regardless of which stream row is highlighted. Stream row selection is display-only in the current code. The stream table is populated from `yt-dlp -J` format metadata, but the displayed source and release columns are currently hard-coded placeholders. The code does not currently implement audio-language filtering or playback in an external player such as mpv.

## Slash commands

Commands are entered in the Home search input and begin with `/`:

- `/help` or `/?`: show the slash-command summary notification.
- `/watchlist`: show the entry count and status counts for the currently selected default content type.
- `/downloads`: show counts of queued, downloading, and failed jobs in the in-memory queue; this is not a persistent download-history screen.
- `/settings`: display the current quality and default content type.
- `/scraper`: display the configured primary/fallback scraper names as a notification; it does not change scraper selection.
- `/quality`: display the current quality and available options.
- `/quality <option>`: change quality if the value matches a configured option.
- `/type anime` or `/type donghua`: change the TUI's default content type for watchlist and download actions during the current app session.
- `/clear`: clear app notifications.

Unknown commands produce an error notification. Settings and content-type changes are in-memory for the current TUI session unless the underlying engine separately persists a setting.

## Download behavior and boundaries

The TUI reuses `tui/data.py` to search, fetch metadata and episode URLs, inspect formats with `yt-dlp`, find or add a watchlist entry, and enqueue downloads. When a title is not found in the selected watchlist, the TUI adds it before queueing the selected episode. The download action passes the selected content type and watchlist file to the queue manager.

The streams view is informational in the current code: selecting a stream does not select a specific format for download. The TUI also does not currently provide a working favorites feature, a TV view, populated watch/resume history, audio-language filtering, or external-player playback. The `?` help binding points to an undefined screen name. Treat these as known gaps rather than supported features.

## Contributor notes

Keep UI presentation and key handling in `tui/`, and route scraper, watchlist, and queue operations through the existing data/engine layer rather than duplicating business logic in screen classes. Keep network and `yt-dlp` work off the UI thread using Textual workers or thread offloading. Preserve the selected content type and corresponding watchlist path when queueing a download. Update this document whenever bindings or actual screen behavior change; footer labels alone are not proof that an action works.
Preserve ansi_color = True on the App and the transparent CSS backgrounds — these implement the intended translucent-terminal look.