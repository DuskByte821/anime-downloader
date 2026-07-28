# CONTRIBUTING.md

# Anime Downloader Development Guide

This document defines the architecture and coding standards for the project.

Every contributor (human or AI) should read this before modifying the codebase.

---

# Project Goal

The objective is to build a fully automated anime downloader.

Running

```bash
python main.py
```

should eventually:

1. Load the watchlist.
2. Check every anime.
3. Detect new episodes.
4. Resolve download links.
5. Download missing episodes.
6. Organize downloaded files.
7. Update the watchlist.
8. Exit gracefully.

No manual interaction should be required.

---

# Architecture

The project follows a layered architecture.

```
main.py
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
scraper/
    │
    ▼
downloader.py
    │
    ▼
updater.py
```

Modules communicate only through well-defined interfaces.

Avoid circular imports.

---

# Module Responsibilities

## main.py

Coordinates the entire application.

Should not contain business logic.

---

## config.py

Contains every configurable value.

Examples

- paths
- headers
- timeout
- retry count
- download directory

Never hardcode these elsewhere.

---

## models.py (future)

Contains project-wide data classes.

Example

```
Anime
Episode
DownloadJob
```

Data classes should not perform scraping or downloading.

---

## watchlist.py

Responsible only for

- loading anime.txt
- saving anime.txt

Should never scrape websites.

Should never download files.

---

## episode.py

Responsible only for episode calculations.

Examples

- compare current/latest
- determine missing episodes
- next episode

No networking.

No filesystem.

---

## scraper/

Responsible only for obtaining information from websites.

Should return structured data.

Should not print.

Should not ask for user input.

Should not save files.

---

## downloader.py

Downloads files.

Nothing else.

---

## updater.py

Updates watchlist after successful downloads.

---

# Design Principles

## Single Responsibility Principle

Every module should have one purpose.

Good

```
episode.py

↓

returns missing episodes
```

Bad

```
episode.py

↓

downloads files

updates watchlist

prints progress
```

---

## Separation of Concerns

Business logic and I/O should remain separate.

Business logic

```
return data
```

I/O

```
print()

input()

open()

requests
```

Avoid mixing them.

---

## Prefer Pure Functions

Good

```python
missing = episode_range(207, 210)
```

Bad

```python
episode_range()

↓

prints

writes files

downloads

returns nothing
```

---

## Small Commits

Each commit should implement one idea.

Examples

Good

```
Parser

Episode logic

Downloader

Updater
```

Bad

```
Parser

Downloader

GUI

Logging

Settings

Bug fixes
```

---

# Code Style

Use

- pathlib
- dataclasses
- type hints
- docstrings

Prefer

```python
Path(...)
```

instead of

```python
os.path.join(...)
```

Prefer

```python
list[str]
```

instead of

```python
List[str]
```

where supported.

---

# Error Handling

Raise meaningful exceptions.

Do not silently ignore failures.

Catch exceptions only when they can be handled.

---

# Adding Features

Before adding code ask

1.

Which module owns this responsibility?

2.

Does this duplicate existing logic?

3.

Can this be implemented without modifying unrelated modules?

If the answer is no, reconsider the design.

---

# AI Contributor Rules

If you are an AI assistant helping with this repository:

- Preserve the existing architecture.
- Avoid unnecessary refactoring.
- Do not rewrite working modules.
- Prefer incremental improvements.
- Keep public APIs stable unless explicitly requested.
- Avoid introducing unnecessary dependencies.
- Match the project's coding style.
- Add type hints when possible.
- Add docstrings to public functions.
- Keep functions focused.
- Prefer composition over large monolithic classes.

If uncertain, preserve existing behavior.

---

# Definition of Success

A new contributor should understand the project within five minutes.

The code should remain modular, readable, and easy to extend.

Future scrapers should be addable without changing the rest of the project.
