# Anime Downloader Roadmap

This file describes the long-term goals of the project.

---

# Primary Goal

Fully automate anime downloading.

The user should only execute:

```
python main.py
```

Everything else should happen automatically.

---

# Expected Workflow

```
Load watchlist

↓

Check every anime

↓

Find latest episode

↓

Compare with watched episode

↓

Resolve download links

↓

Download missing episodes

↓

Update watchlist

↓

Exit
```

---

# Core Principles

## 1. Modular

Each module has one responsibility.

No module should perform multiple unrelated jobs.

---

## 2. Extendable

Adding another website should only require adding another scraper.

Example:

```
scraper/

cartoonsarea.py
animekai.py
animepahe.py
nyaa.py
```

Main program should not require modification.

---

## 3. Configurable

All user-editable values belong in config.py.

Examples

- download directory
- timeout
- headers
- retry count
- parallel downloads

---

## 4. Maintainable

Readable code is preferred over clever code.

Functions should remain short.

Avoid unnecessary nesting.

---

# Future Features

## Downloader

- yt-dlp support
- aria2 support
- resume downloads

---

## Watchlist

- aliases
- multiple seasons
- overall episode count
- tags

---

## Scrapers

- CartoonsArea
- luciferdonghua
---

## Download Management

Create folders automatically.

Example

```
Anime/

Battle Through The Heavens/
    Episode 208.mp4

One Piece/
    Episode 1135.mp4
```

If many new episodes exist

```
Battle Through The Heavens/

New Episodes/

Episode 208.mp4
Episode 209.mp4
Episode 210.mp4
```

---

## Logging

Record

- downloads
- failures
- skipped episodes
- retries

---

## Error Handling

The program should never crash because one anime failed.

Continue processing remaining anime.

---

## Testing

Eventually every module should have unit tests.

Modules should be testable without internet whenever possible.

---

# Coding Guidelines

- Use type hints.
- Write docstrings.
- Avoid duplicated code.
- Prefer pathlib over os.
- Keep business logic independent from I/O.
- Avoid hardcoded paths.
- Raise meaningful exceptions.

---

# Definition of Done

The project is considered complete when running

```
python main.py
```

will:

- read the watchlist
- detect new episodes
- resolve download links
- download them
- organize files
- update the watchlist
- produce useful logs
- exit without user interaction
