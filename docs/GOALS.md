# Anime Downloader Roadmap

This file describes the long-term goals and design direction of the project.

---

# Primary Goal

Build a reliable Anime and Donghua downloader that can discover episode sources, persist useful source links, maintain user watchlists, and download episodes when explicitly requested.

The project should minimize unnecessary repeated scraping while keeping the workflow understandable and controllable.

The core principle is:

```text
Discover → Cache → Track → Download on demand
```

---

# Supported Content

Anime and Donghua are both first-class content types.

They must remain separated throughout the application.

```text
Anime
  ↓
data/anime.txt

Donghua
  ↓
data/donghua.txt
```

The project must never accidentally update the wrong content type's watchlist.

---

# Expected Workflow

The intended workflow is no longer automatic downloading on every program start.

Instead:

```text
Load / scan project data
        ↓
Discover new titles and episode links
        ↓
Store links in data/links/
        ↓
Add missing titles to the correct watchlist
        ↓
Wait for explicit user action
        ↓
User chooses Download
        ↓
Use cached episode links
        ↓
Download missing episodes
        ↓
Update the same watchlist
```

Discovery and downloading must remain separate operations.

---

# Persistent Link Cache

A major project goal is to avoid scraping external sources every time an episode is downloaded.

Episode/source links should be persistently stored under:

```text
data/links/
```

The cache should allow the project to:

* discover links once
* reuse them later
* avoid unnecessary repeated scraping
* preserve source information after successful downloads
* support manual link collection/import
* provide a foundation for future source management

The cache is source data, not progress data.

---

# Watchlist

The watchlist remains the authoritative source for user state.

Each content type has its own file:

```text
data/anime.txt
data/donghua.txt
```

Each file contains:

```text
watching
ended
dropped
completed
```

Existing entry formats must remain supported:

```text
title::season X::downloaded N::watched M
```

and:

```text
title::downloaded N::watched M
```

The project should preserve human-readable text files rather than introducing a database for this functionality.

---

# Watchlist Goals

The watchlist system should provide:

* Anime/Donghua separation
* four mutually exclusive statuses
* season support
* downloaded episode tracking
* watched episode tracking
* safe persistence
* duplicate prevention
* backwards compatibility with existing entries
* predictable status movement
* preservation of empty sections

Future watchlist improvements may include:

* aliases
* richer season handling
* overall episode counts
* tags
* additional metadata

These should extend the existing model rather than replace it unnecessarily.

---

# Downloading

Downloading must happen only as the result of an explicit user action.

Scanning for new links must never automatically start downloads.

The downloader should:

* consume cached episode links when available
* support existing scraper fallback behavior
* download only missing episodes
* handle failures without destroying watchlist state
* preserve cached links after successful downloads
* report useful progress and errors

Potential future downloader improvements include:

* yt-dlp integration
* aria2 support
* resume support
* improved retry handling
* parallel downloads

---

# Scrapers

Scrapers should provide external source discovery.

Adding a new website should ideally require adding a scraper rather than rewriting unrelated application logic.

Potential sources include:

```text
scraper/
├── cartoonsarea.py
├── luciferdonghua.py
└── ...
```

Scrapers should be reusable for:

* initial link discovery
* cache refreshes
* recovering missing links
* adding support for new sources

The project should prefer cached information when it is already available and usable.

---

# Discovery

The discovery system should be able to scan:

```text
data/links/
```

and detect new link files.

When a new link cache is found:

```text
link file
   ↓
detect title/type
   ↓
check watchlist
   ↓
add missing entry
```

If the title already exists:

```text
do nothing to its existing progress
```

Repeated scans must be idempotent.

Most importantly:

```text
DISCOVERY MUST NOT DOWNLOAD.
```

---

# Download Management

Downloaded files should eventually be organized consistently.

Example:

```text
Anime/
└── One Piece/
    ├── Episode 1135.mp4
    └── Episode 1136.mp4
```

```text
Donghua/
└── Battle Through The Heavens/
    ├── Episode 208.mp4
    └── Episode 209.mp4
```

Folder organization should remain independent from watchlist storage.

---

# Logging

The application should provide useful logs for:

* discovered episodes
* cached links
* downloads
* skipped episodes
* failures
* retries
* watchlist updates
* scraper failures

Logs should help diagnose problems without requiring the user to inspect internal code.

---

# Error Handling

One failed series should not unnecessarily stop the entire workflow.

For example:

```text
Series A → success
Series B → failure → log error
Series C → continue
```

Failures should be isolated wherever practical.

The project should fail clearly rather than silently corrupting watchlist or cache data.

---

# Modularity

Each module should have one primary responsibility.

The architecture should remain roughly:

```text
TUI / CLI
    ↓
Watchlist
    ↓
Models
    ↓
Discovery / Scrapers
    ↓
Link Cache
    ↓
Downloader
    ↓
Updater
```

Modules should communicate through clear interfaces rather than reaching into unrelated components.

---

# Maintainability

Readable code is preferred over clever code.

Goals:

* short functions
* clear names
* type hints
* useful docstrings
* minimal duplication
* pathlib for filesystem operations
* meaningful exceptions
* limited global state
* no unnecessary abstractions
* no broad rewrites when a focused change is sufficient

Business logic should remain as independent from I/O as practical.

---

# Configurability

User-editable configuration should remain centralized where appropriate.

Examples include:

* download directory
* request timeout
* HTTP headers
* retry count
* parallel download settings
* source configuration

Hardcoded paths should be avoided.

---

# Testing

Testing is a core project goal.

Every important component should eventually have automated tests.

Tests should work without internet access whenever possible.

Important coverage includes:

```text
Watchlist
├── parsing
├── saving
├── statuses
├── seasons
├── progress
└── Anime/Donghua separation

Link Cache
├── parsing
├── discovery
├── new titles
├── duplicate detection
├── repeated scans
└── malformed files

Downloader
├── cached links
├── missing episodes
└── failure handling

Updater
├── progress updates
├── correct watchlist selection
└── state preservation
```

Tests must not modify the real project watchlists.

---

# Data Safety

The project should prioritize safe handling of user data.

Important rules:

* never update the wrong watchlist
* never overwrite unrelated entries
* never reset existing progress during discovery
* never delete cached links after downloading
* never duplicate titles during repeated scans
* never automatically download during link scanning

The system should preserve existing user data whenever possible.

---

# Future Direction

Future improvements should build on the current architecture rather than replacing it unnecessarily.

Potential areas include:

* better source selection
* multiple source links per episode
* cache validation
* automatic cache refresh
* richer metadata
* aliases
* better season management
* download queues
* resume support
* improved TUI controls
* additional Anime/Donghua sources
* stronger integration tests

These features should preserve the fundamental separation between:

```text
User State
     │
     ▼
Watchlist

Source Data
     │
     ▼
Link Cache

Actual Transfer
     │
     ▼
Downloader
```

---

# Definition of Done

The project should be considered mature when it can reliably:

* support Anime and Donghua separately
* maintain both watchlists safely
* discover and import new titles
* persist episode links
* reuse cached links
* avoid unnecessary repeated scraping
* download episodes only after explicit user action
* update the correct watchlist after successful downloads
* preserve cached links after downloads
* organize downloaded files
* provide useful logs
* recover gracefully from individual failures
* run a comprehensive automated test suite

The long-term objective is not simply to automate downloading.

It is to build a reliable system that:

```text
DISCOVERS
    ↓
CACHES
    ↓
TRACKS
    ↓
DOWNLOADS ON DEMAND
    ↓
UPDATES SAFELY
```