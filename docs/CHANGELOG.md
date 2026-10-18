## Changelog 2.2.3

### 2026-10-18 — Dailymotion extraction fix

**Problem:** Episodes with Dailymotion available were downloading from Rumble instead, which then failed with HTTP 403.

**Cause:** Dailymotion's modern embed uses `<script src="…/player/X.js" data-video="ID">`, not `<iframe>`. The scraper only looked for iframes, so it never found Dailymotion — Rumble (still iframe-based) was the top candidate.

**Fix (`scraper/luciferdonghua.py`):**
- Added `_extract_dailymotion_scripts()` — builds `https://geo.dailymotion.com/player/X.html?video=ID` from the script tag.
- Added duration extraction from `<meta itemprop="duration" content="P1125S">` — no yt-dlp probe needed.
- `_probe_duration()` now returns `(seconds, status)` where status is `ok` / `no_duration` / `unreachable`.
- `resolve_episode_source()` skips unreachable sources instead of accepting them.
- `SourceCandidate` gained a `duration: Optional[int]` field.

**Tests added:** script extraction, ISO 8601 duration parsing, resolver uses page duration without probing.

---

### Earlier this session

- **Search:** AJAX endpoint (`action=ts_ac_do_search`) with HTML fallback; query-token filter drops unrelated results.
- **Caching:** 7-day TTL on series metadata, 1-day on episode maps, stale-while-error fallback.
- **Pre-flight:** duration check before queueing; previews rejected without downloading.
- **Downloads:** direct `.mp4` URLs go through wget, not yt-dlp (fixes archive.org format-selector failure).
- **TUI:** transparent background (`ansi_color=True`), sliding episode window (8 items), slash commands.
- **Tests:** suite caught up to code changes — was 10 failing, now green after updates.
- **Docs:** `PROJECT_STATE.md`, `ARCHITECTURE.md`, `TUI.md`, `README.md`, `GOALS.md`, `CONVENTIONS.md` written from code.