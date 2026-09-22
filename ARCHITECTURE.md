# Anime Downloader Architecture

This document describes the current architecture and data flow of the project.

---

# Overview

Anime Downloader supports both **Anime** and **Donghua** as first-class content types.

The project is built around four major responsibilities:

1. Watchlist management
2. Episode/link discovery
3. Persistent episode-link caching
4. Explicit downloading and progress tracking

The watchlist stores **user state and progress**.

The link cache stores **episode source information**.

These two responsibilities must remain separate.

---

# High-Level Architecture

```text
                    ┌─────────────────────┐
                    │        TUI / CLI     │
                    └──────────┬──────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
               Anime                    Donghua
                  │                         │
                  ▼                         ▼
          data/anime.txt            data/donghua.txt
                  │                         │
                  └────────────┬────────────┘
                               ▼
                          watchlist.py
                               │
                               ▼
                             Anime
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
       Link Cache Scanner                   Scrapers
              │                                 │
              ▼                                 ▼
        data/links/                    External websites
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
                    Cached Episode Links
                             │
                             │
                    User explicitly selects
                         Download
                             │
                             ▼
                       downloader.py
                             │
                             ▼
                         updater.py
                             │
                             ▼
                 Same selected watchlist
```

---

# Watchlists

Anime and Donghua use separate watchlist files.

```text
data/
├── anime.txt
├── donghua.txt
└── links/
```

The mapping is strict:

```text
Anime   → data/anime.txt
Donghua → data/donghua.txt
```

The selected content type must remain associated with the selected watchlist throughout the entire workflow.

An Anime download must never update `donghua.txt`.

A Donghua download must never update `anime.txt`.

---

# Watchlist Structure

Each watchlist contains four sections:

```text
watching
ended
dropped
completed
```

Entries retain the existing format:

```text
title::season X::downloaded N::watched M
```

or:

```text
title::downloaded N::watched M
```

The watchlist is responsible for:

* title
* season information
* status
* downloaded episode count
* watched episode count

The watchlist is the authoritative source for user progress.

---

# Statuses

The four statuses are mutually exclusive.

```text
watching
ended
dropped
completed
```

### Watching

The user is currently following the series.

### Ended

The series itself has finished.

### Dropped

The user has stopped following the series.

### Completed

The user considers the series complete.

New entries normally begin in:

```text
watching
```

---

# Link Cache

Episode links are persisted under:

```text
data/links/
```

The purpose of the link cache is to avoid repeatedly scraping the same source every time an episode needs to be downloaded.

Example:

```text
data/
└── links/
    ├── renegade-immortal.txt
    ├── perfect-world.txt
    └── battle-through-the-heavens.txt
```

A link-cache file contains discovered episode/source links.

Example:

```text
# title: Renegade Immortal
# type: donghua
# source: example

1::https://example.com/episode-1
2::https://example.com/episode-2
3::https://example.com/episode-3
```

The exact cache format may evolve, but the separation of responsibilities must remain.

---

# Link Cache vs Watchlist

These files have different purposes.

```text
Watchlist
─────────
User state
Progress
Status
Downloaded count
Watched count
Season information
```

```text
Link Cache
──────────
Episode URLs
Source information
Discovered episodes
Cached download targets
```

The link cache must **not** become the authoritative source for download progress.

For example:

```text
Link cache:
episode 160 exists

Watchlist:
downloaded 159
watched 158
```

Scanning the cache must not change the watchlist to:

```text
downloaded 160
```

Only a successful explicit download may update the downloaded count.

---

# Discovery Workflow

Discovery and downloading are separate operations.

```text
External source / manual links
              │
              ▼
        data/links/*.txt
              │
              ▼
       Link Cache Scanner
              │
              ▼
       Detect content type
              │
        ┌─────┴─────┐
        ▼           ▼
      Anime       Donghua
        │           │
        ▼           ▼
   anime.txt    donghua.txt
```

The scanner may be run when the application is started or through an explicit scan action.

Scanning a link-cache directory must:

* detect new link files
* identify their content type
* add missing titles to the appropriate watchlist
* avoid duplicate entries
* preserve existing progress
* preserve existing status
* avoid downloading anything

---

# Scan Invariant

The most important discovery rule is:

```text
SCAN ≠ DOWNLOAD
```

Scanning is an import/discovery operation only.

For a new title:

```text
link cache
     │
     ▼
scanner
     │
     ▼
watchlist entry
```

It must stop there.

The user must explicitly choose the Download workflow before any episode is downloaded.

---

# Download Workflow

Downloading begins only after an explicit user action.

```text
User selects Download
          │
          ▼
      Anime/Donghua
          │
          ▼
       Watchlist
          │
          ▼
     Link Cache
          │
          ▼
      Episode URL
          │
          ▼
      Downloader
          │
          ▼
   Successful download
          │
          ▼
       Updater
          │
          ▼
   Same watchlist file
```

The downloader may use cached links when available.

Existing scraper functionality remains available as a fallback or for refreshing the cache.

---

# Scrapers

Scrapers are responsible for discovering episode/source information from supported websites.

They should not own watchlist state.

Conceptually:

```text
scraper
   │
   ▼
episode/source information
   │
   ▼
link cache
```

Scrapers may be used when:

* a link cache does not exist
* the cache needs refreshing
* a new source needs to be discovered

The architecture should avoid scraping the same source unnecessarily when usable cached links already exist.

Adding another source should preferably require adding another scraper rather than rewriting the downloader.

---

# Downloader

`downloader.py` is responsible for downloading episodes.

It should receive an episode/source URL and handle the actual download process.

The downloader should not:

* decide watchlist status
* create duplicate watchlist entries
* silently change watched progress
* choose the wrong Anime/Donghua watchlist

The downloader performs the download.

The updater records the resulting progress.

---

# Updater

`updater.py` updates the selected watchlist after successful operations.

The updater must receive enough context to know which watchlist is being modified.

The invariant is:

```text
Anime download
    → update data/anime.txt

Donghua download
    → update data/donghua.txt
```

The updater must never fall back to a global/default watchlist when the current workflow has already selected a specific content type.

---

# TUI / CLI

The user interface provides access to the major workflows.

Conceptually:

```text
Download
├── Anime
├── Donghua
└── Back
```

```text
Watchlist
├── Anime
│   ├── Watching
│   ├── Ended
│   ├── Dropped
│   └── Completed
│
├── Donghua
│   ├── Watching
│   ├── Ended
│   ├── Dropped
│   └── Completed
│
└── Back
```

A scan/import operation may also be exposed through the interface.

The interface should make the distinction between:

```text
Discover / Scan
```

and:

```text
Download
```

clear to the user.

---

# Separation of Responsibilities

Each component should have a clear responsibility.

```text
watchlist.py
    Watchlist parsing, manipulation, and persistence

models.py
    Domain models such as Anime

scraper/
    External source discovery

data/links/
    Persistent episode-link cache

downloader.py
    Episode downloading

updater.py
    Progress/watchlist updates

TUI / CLI
    User interaction and workflow selection
```

No component should silently take responsibility for unrelated layers.

---

# Data Flow Invariants

The following rules must always hold.

### Content separation

```text
Anime   → anime.txt
Donghua → donghua.txt
```

### Discovery

```text
Scan → Import only
```

### Downloading

```text
Download → Explicit user action
```

### Progress

```text
Successful download → updater → watchlist
```

### Cache persistence

```text
Downloaded episode → cached link remains
```

### Watchlist authority

```text
Watchlist → user state/progress
Link cache → source/episode links
```

---

# Error Isolation

A failure involving one series should not unnecessarily terminate the entire application.

For example:

```text
Series A → success
Series B → download failure
Series C → continue
```

Errors should be logged with enough information to diagnose the failure.

---

# Testing Architecture

Core components should be testable without relying on live websites whenever possible.

Tests should cover:

* watchlist parsing
* all four statuses
* watchlist persistence
* Anime/Donghua file separation
* updater path correctness
* status changes
* backward-compatible entry formats
* link-cache parsing
* new link-file discovery
* repeated scans
* duplicate prevention
* new-title import
* existing-title preservation
* no download during scanning
* no progress mutation during scanning
* cache persistence after downloading
* downloader/updater integration

Tests should use temporary files and fixtures rather than modifying real project data.

---

# Design Principle

The central architectural principle is:

```text
DISCOVER ONCE
CACHE LINKS
REUSE THEM
DOWNLOAD ONLY WHEN ASKED
TRACK PROGRESS SEPARATELY
```

This keeps external source discovery, user state, and downloading independent while allowing them to work together through well-defined boundaries.
