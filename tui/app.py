"""Textual application root."""

from textual.app import App, ComposeResult

from config import DEFAULT_CONTENT_TYPE
from tui.screens.home import HomeScreen
from tui.screens.search import SearchScreen
from tui.screens.details import TitleDetailsScreen


class AnimeDownloaderApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Anime Downloader"
    ansi_color = True

    def __init__(self) -> None:
        super().__init__()
        self.default_content_type = DEFAULT_CONTENT_TYPE

    def on_mount(self) -> None:
        from tui.screens.home import HomeScreen
        self.push_screen(HomeScreen())

    def handle_slash_command(self, text: str) -> None:
        """Dispatch a slash-command typed into the search bar."""
        cmd = text.strip().lstrip("/").lower()
        # Split on whitespace in case someone types "/watchlist renegade"
        parts = cmd.split(maxsplit=1)
        verb = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if verb in ("help", "?"):
            self._show_help()
        elif verb == "watchlist":
            self._show_watchlist()
        elif verb == "downloads":
            self._show_downloads()
        elif verb == "settings":
            self._show_settings()
        elif verb == "scraper":
            self._show_scraper()
        elif verb == "quality":
            self._show_quality(arg)
        elif verb == "type":
            self._set_default_type(arg)
        elif verb == "clear":
            self.clear_notifications()
        else:
            self.notify(f"Unknown command: /{verb}", severity="error")

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _show_help(self) -> None:
        self.notify(
            "Commands: /watchlist  /downloads  /settings  /scraper  "
            "/quality  /type  /clear  /help",
            title="Slash commands",
            timeout=8,
        )

    def _show_watchlist(self) -> None:
        from watchlist import load_watchlist
        from config import WATCHLIST_FILES
        fp = WATCHLIST_FILES[self.default_content_type]
        entries = load_watchlist(fp)
        if not entries:
            self.notify(f"{fp.name} is empty.", severity="information")
            return
        counts = {}
        for a in entries:
            counts[a.status] = counts.get(a.status, 0) + 1
        summary = "  ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        self.notify(f"{fp.name} — {len(entries)} entries ({summary})", timeout=6)

    def _show_downloads(self) -> None:
        from queue_manager import QUEUE
        status = QUEUE.get_status()
        if not status:
            self.notify("No active jobs.", severity="information")
            return
        active = sum(1 for s in status.values() if s[0] == "downloading")
        queued = sum(1 for s in status.values() if s[0] == "queued")
        failed = sum(1 for s in status.values() if s[0] == "failed")
        self.notify(
            f"Queue: {active} downloading, {queued} queued, {failed} failed",
            timeout=6,
        )

    def _show_settings(self) -> None:
        from downloader import CURRENT_QUALITY
        self.notify(
            f"Quality: {CURRENT_QUALITY}  |  Content type: {self.default_content_type}",
            title="Settings",
            timeout=6,
        )

    def _show_scraper(self) -> None:
        self.notify(
            "Scraper: luciferdonghua (primary)  |  cartoonsarea (fallback)",
            title="Scraper",
            timeout=6,
        )

    def _show_quality(self, arg: str) -> None:
        from downloader import set_quality, CURRENT_QUALITY
        from config import QUALITY_OPTIONS
        if not arg:
            self.notify(
                f"Current: {CURRENT_QUALITY}. Options: {', '.join(QUALITY_OPTIONS.keys())}",
                timeout=6,
            )
            return
        if arg in QUALITY_OPTIONS:
            set_quality(arg)
            self.notify(f"Quality set to {arg}")
        else:
            self.notify(f"Unknown quality: {arg}", severity="error")

    def _set_default_type(self, arg: str) -> None:
        if arg in ("anime", "donghua"):
            self.default_content_type = arg
            self.notify(f"Default content type → {arg}")
        else:
            self.notify(f"Usage: /type anime|donghua", severity="warning")