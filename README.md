# Anime Downloader

A modular Python application for automatically downloading new anime/donghua episodes.

The goal is simple:

1. Read your watchlist.
2. Check whether new episodes exist.
3. Resolve download links.
4. Download missing episodes.
5. Update the watchlist.

---

## Features

- Modular architecture
- Watchlist parser
- Episode comparison
- Multiple scraper support
- Automatic episode downloading
- Automatic watchlist updates
- Configurable download directory

---

## Project Structure

```
anime-downloader/

│
├── main.py                 # Entry point
├── config.py               # Global configuration
│
├── watchlist.py            # Read/write anime.txt
├── episode.py              # Episode comparison logic
├── downloader.py           # Download files
├── updater.py              # Update watchlist
│
├── scraper/
│   ├── __init__.py
│   ├── cartoonsarea.py
│   └── resolver.py
│
├── data/
│   ├── anime.txt
│   └── links.txt
│
└── logs/
```

---

## Philosophy

Every module should have **one responsibility**.

Example:

- watchlist.py
    - Reads and writes anime.txt

- episode.py
    - Determines which episodes are missing

- scraper/
    - Finds episode pages
    - Resolves download links

- downloader.py
    - Downloads files

- updater.py
    - Updates anime.txt

Modules should not perform unrelated tasks.

---

## Current Workflow

```
anime.txt
      │
      ▼
watchlist.py
      │
      ▼
Anime objects
      │
      ▼
episode.py
      │
      ▼
scraper
      │
      ▼
downloader
      │
      ▼
updater
```

---

## Watchlist Format

```
watching

Battle Through The Heavens::season 5::episode 207

completed

Death Note::episode 37
```

---

## Design Rules

- Keep modules independent.
- Avoid global state.
- Avoid duplicated configuration.
- Prefer pure functions.
- Every function should have one responsibility.
- Never mix UI with business logic.
- Keep commits small and focused.

---

## Current Status

Project is currently under active development.

Architecture is mostly complete.

Implementation is ongoing.
