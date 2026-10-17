# Anime Downloader

A terminal-based anime and donghua downloader and watchlist manager written in Python.

The project provides a TUI-driven workflow for tracking, downloading, and monitoring anime and Chinese animation (donghua), while keeping their watchlists separated.

## Features

* Terminal User Interface (TUI)
* Anime and Donghua support
* Separate watchlists for Anime and Donghua
* Track downloaded and watched episode counts
* Watchlist status management
* Automatic episode/update monitoring
* Scraper-based episode discovery
* Automatic download handling
* Persistent watchlist storage
* Logging
* Pytest test suite

## Note
IF YOU ARE ON THE PAGE, PLEASE DON'T MIND WHAT IT DOES.
THIS IS A FULLY AI-GENERATED TOOL. 
BUT IF YOU DO USE THIS TOOL PLEASE, GIVE ME SOME SUGGESTION 
TO IMPROVE EXISTING FEATURES AS FIRST PRIORTY, THEN NEW FEATURES.
ANYWAY THANKS ALOT!!!
Also check this out:: https://www.youtube.com/watch?v=dQw4w9WgXcQ

## Supported Content

The downloader currently supports two content types:

* **Anime**
* **Donghua**

Each content type has its own watchlist:

```text
data/
├── anime.txt
└── donghua.txt
```

This keeps Anime and Donghua data isolated and prevents updates to one content type from modifying the other.

## Watchlist

Each watchlist is divided into four states:

```text
watching
ended
dropped
completed
```

### Watching

Series that are currently being followed.

### Ended

Series that have finished and are not expected to receive additional episodes.

### Dropped

Series that the user has stopped following.

### Completed

Series that the user has finished downloading/watching or otherwise considers complete.

The four states are stored inside the corresponding content-type watchlist rather than in separate files.

## Watchlist Format

Entries use the following format:

```text
title::season X::downloaded N::watched M
```

For titles without a season:

```text
title::downloaded N::watched M
```

### Examples

```text
renegade immortal::season 1::downloaded 159::watched 158
```

```text
sword and fairy 3::downloaded 8::watched 4
```

Where:

* `title` — series title
* `season X` — optional season information
* `downloaded N` — number of downloaded episodes
* `watched M` — number of watched episodes

The existing entry format is intentionally kept simple so the watchlist remains human-readable and easy to edit manually.

## Example Watchlist

### `data/anime.txt`

```text
watching
Demon Slayer::season 2::downloaded 0::watched 0
Tsukimichi Moonlit::season 2::downloaded 0::watched 0
Lord of Mysteries::season 1::downloaded 4::watched 4

ended

dropped

completed
classroom of the elite::season 2::downloaded 13::watched 13
Dragon Raja::season 2::downloaded 24::watched 24
```

### `data/donghua.txt`

```text
watching
perfect world::season 1::downloaded 284::watched 270
stellar transformation::season 7::downloaded 11::watched 1
renegade immortal::season 1::downloaded 159::watched 158

ended
Throne of seal::season 1::downloaded 208::watched 208

dropped
soul land 2::season 1::downloaded 151::watched 140

completed
apotheosis::season 3::downloaded 26::watched 26
```

Empty sections are preserved so the watchlist always has the same structure.

## TUI

The application is controlled through a terminal interface.

The main workflow separates Anime and Donghua before accessing their respective watchlists.

### Download

```text
Download
├── Anime
├── Donghua
└── Back
```

### Watchlist

```text
Watchlist
├── Anime
│   ├── Watching
│   ├── Ended
│   ├── Dropped
│   └── Completed
├── Donghua
│   ├── Watching
│   ├── Ended
│   ├── Dropped
│   └── Completed
└── Back
```

The selected content type determines which watchlist file is used.

```text
Anime   → data/anime.txt
Donghua → data/donghua.txt
```

## Supported Formats

The downloader works with episode sources supported by its scraper/downloader pipeline.

### Video formats

The downloaded media is handled through the project's downloader backend and can use common video formats supported by the underlying download tools.

Commonly encountered formats include:

* MP4


The exact available output depends on the source and downloader configuration.

### Watchlist format

The native watchlist format is plain UTF-8 text:

```text
.title::season X::downloaded N::watched M
```

No database is required.

## Scrapers

The project uses site-specific scraper modules to discover episode information.

Current scraper support is focused on the sources implemented in the `scraper/` package.

A scraper is responsible for discovering information such as:

* Latest available episode
* Episode URLs
* Source information
* Site-specific episode metadata

The downloader then handles the actual media download.

New sources can be added through additional scraper implementations without changing the watchlist format.

## Updating Episodes

The updater compares the latest available episode with the number recorded in the watchlist.

For example:

```text
Before:
renegade immortal::season 1::downloaded 158::watched 158

Latest episode:
159

After:
renegade immortal::season 1::downloaded 159::watched 158
```

The watched count is preserved independently from the downloaded count.

This means downloading a new episode does not automatically mark that episode as watched.

## Data Storage

Project data is stored under:

```text
data/
├── anime.txt
├── donghua.txt
├── anime_test.txt
├── links.txt
└── logs/
```

The two primary watchlists are:

```text
data/anime.txt
data/donghua.txt
```

These files are intentionally human-readable and can be backed up or edited manually.

## Project Structure

A simplified project structure:

```text
anime-downloader/
├── data/
│   ├── anime.txt
│   ├── donghua.txt
│   ├── anime_test.txt
│   ├── links.txt
│   └── logs/
├── downloads/
├── scraper/
├── tests/
├── anime.py
├── links.py
├── models.py
├── updater.py
├── watchlist.py
├── main.py
└── README.md
```

The exact structure may change as the project evolves.

## Requirements

* Python 3
* `yt-dlp`
* Python dependencies listed by the project
* A terminal capable of running the TUI

Install the required Python packages using the project's dependency configuration.

## Running

From the project directory:

```bash
python main.py
```

The TUI can then be used to select Anime or Donghua and perform the available operations.

## Testing

The project uses `pytest`.

Run the complete test suite with:

```bash
pytest
```

Tests cover core project behavior such as:

* Watchlist parsing
* Watchlist serialization
* Watchlist status handling
* Anime/Donghua data separation
* Download/update logic
* Persistence

Tests should use temporary test data rather than modifying the real watchlists.

## Data Safety

The watchlists are plain text files, making them easy to back up.

Before making structural changes to the watchlist system, it is recommended to create a backup:

```bash
cp data/anime.txt data/anime.txt.bak
cp data/donghua.txt data/donghua.txt.bak
```

The application should always preserve the selected content type when updating a watchlist.

For example:

```text
Donghua
   ↓
donghua.txt
   ↓
Downloader
   ↓
Updater
   ↓
donghua.txt
```

and:

```text
Anime
   ↓
anime.txt
   ↓
Downloader
   ↓
Updater
   ↓
anime.txt
```

## Current Status

The project is actively developed.

The core downloader, scraper, watchlist, updater, and TUI systems are in place, with ongoing improvements to:

* TUI organization
* Anime/Donghua separation
* Watchlist management
* Source support
* Test coverage
* Downloader reliability

## License

See the project license for usage and redistribution terms.
