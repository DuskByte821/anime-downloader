"""Stage 3 — Title details."""

import subprocess
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, DataTable
from textual import work
import asyncio

from tui import data
from tui.widgets.info_modal import InfoModal
from tui.widgets.logo import Logo  # not used but keeps import surface consistent

EPISODE_WINDOW_SIZE = 8

class TitleDetailsScreen(Screen):
    FOCUS_REGIONS = ["seasons", "episodes", "streams"]

    def __init__(self, result: dict) -> None:
        super().__init__()
        self._result = result
        self._meta: dict = {}
        self._episodes: dict[int, str] = {}
        self._selected_season: Optional[int] = None
        self._selected_episode: Optional[int] = None
        self._focus_index = 0
    
    BINDINGS = [
        ("escape", "back", "Back"),
        ("tab", "focus_next_region", "Next"),
        ("shift+tab", "focus_prev_region", "Prev"),
        ("i", "show_info", "Info"),
        ("d", "download", "Download"),
        ("f", "noop_fav", "Fav"),
        # Note: no up/down/left/right here — handled by on_key
    ]

    async def on_key(self, event) -> None:
        region = self.FOCUS_REGIONS[self._focus_index]

        if event.key == "up":
            if region == "episodes":
                await self._shift_episode(-1)
                event.stop()
            elif region == "streams":
                table = self.query_one("#streams-table", DataTable)
                if table.cursor_row > 0:
                    table.move_cursor(row=table.cursor_row - 1)
                event.stop()

        elif event.key == "down":
            if region == "episodes":
                await self._shift_episode(1)
                event.stop()
            elif region == "streams":
                table = self.query_one("#streams-table", DataTable)
                if table.cursor_row < table.row_count - 1:
                    table.move_cursor(row=table.cursor_row + 1)
                event.stop()

        elif event.key == "left":
            self.action_focus_prev_region()
            event.stop()

        elif event.key == "right":
            self.action_focus_next_region()
            event.stop()

    async def _shift_episode(self, delta: int) -> None:
        if not self._episodes or self._selected_episode is None:
            return
        eps_sorted = sorted(self._episodes.keys())
        if self._selected_episode not in eps_sorted:
            return
        idx = eps_sorted.index(self._selected_episode)
        new_idx = max(0, min(len(eps_sorted) - 1, idx + delta))
        if new_idx == idx:
            return
        self._selected_episode = eps_sorted[new_idx]
        await self._refresh_episode_highlight()
        self._load_streams(self._episodes[self._selected_episode])
        
    # --------------------------------------------------------------
    # Layout
    # --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="details-root"):
            yield Static("", id="details-header")
            with Horizontal(id="details-body"):
                with Vertical(id="seasons-col", classes="selector-col"):
                    yield Static("[bold]Season[/bold]", classes="col-title")
                    yield VerticalScroll(id="seasons-list", can_focus=False)
                with Vertical(id="episodes-col", classes="selector-col"):
                    yield Static("[bold]Episode[/bold]", classes="col-title")
                    yield VerticalScroll(id="episodes-list", can_focus=False)
                with Vertical(id="streams-col", classes="selector-col grow"):
                    yield Static("[bold]Streams[/bold]", classes="col-title")
                    yield DataTable(id="streams-table")
            with Horizontal(id="details-footer"):
                yield Static("", id="footer-hints")

    def on_mount(self) -> None:
        self.focus()
        table = self.query_one("#streams-table", DataTable)
        table.add_columns("RES", "Size", "Media", "Source", "Release")
        self._load_metadata()

    @work(exclusive=True)
    async def _load_metadata(self) -> None:
        url = self._result["url"]
        meta = await asyncio.to_thread(data.series_metadata, url)
        eps = await asyncio.to_thread(data.series_episodes, url)
        self._meta = meta
        self._episodes = eps

        # Header
        title = meta.get("title") or self._result["title"]
        parts = []
        if meta.get("status"):     parts.append(meta["status"])
        if meta.get("type"):       parts.append(meta["type"])
        if meta.get("released"):   parts.append(meta["released"])
        line = " · ".join(parts) if parts else "(Lucifer Donghua)"
        self.query_one("#details-header", Static).update(
            f"[bold]{title}[/bold]\n[dim]{line}[/dim]"
        )

        # Seasons
        seasons_col = self.query_one("#seasons-list", VerticalScroll)
        await seasons_col.remove_children()
        season_no = meta.get("season") or 1
        self._selected_season = season_no
        await seasons_col.mount(
            Static(f"[green]Season {season_no}[/green]", classes="selector-item selected")
        )

        # Episodes
        await self._render_episodes()
        self._update_footer()
        self._focus_region(0)

    async def _gather(self, url: str):
        meta = await self.app.run_in_thread(data.series_metadata, url)
        eps = await self.app.run_in_thread(data.series_episodes, url)
        return meta, eps

    async def _render_episodes(self) -> None:
        """Render a window of episodes around the current selection."""
        col = self.query_one("#episodes-list", VerticalScroll)
        # Use run_worker-free sync refresh: we don't need async for this
        if not self._episodes:
            return

        eps_sorted = sorted(self._episodes.keys())
        if self._selected_episode is None:
            self._selected_episode = eps_sorted[0]

        start, end = self._episode_window(eps_sorted, self._selected_episode)

        # Rebuild children synchronously
        for child in list(col.children):
            child.remove()

        for ep in eps_sorted[start:end]:
            cls = "selector-item selected" if ep == self._selected_episode else "selector-item"
            col.mount(Static(f"Episode {ep}", classes=cls))


    def _episode_window(self, eps_sorted, selected):
        """
        Return (start, end) for a window of EPISODE_WINDOW_SIZE entries
        that includes the selected episode. Slides by one at the edges.
        """
        total = len(eps_sorted)
        if total <= EPISODE_WINDOW_SIZE:
            return 0, total

        sel_idx = eps_sorted.index(selected)
        half = EPISODE_WINDOW_SIZE // 2
        start = sel_idx - half
        if start < 0:
            start = 0
        end = start + EPISODE_WINDOW_SIZE
        if end > total:
            end = total
            start = end - EPISODE_WINDOW_SIZE
        return start, end

    async def _refresh_episode_highlight(self) -> None:
        """Highlight the selected episode, sliding the window if needed."""
        if not self._episodes or self._selected_episode is None:
            return
        eps_sorted = sorted(self._episodes.keys())

        col = self.query_one("#episodes-list", VerticalScroll)
        current_labels = [
            child.renderable.plain if hasattr(child, "renderable") else ""
            for child in col.children
        ]
        selected_label = f"Episode {self._selected_episode}"

        if selected_label in current_labels:
            # Just flip the highlight
            for child in col.children:
                label = child.renderable.plain if hasattr(child, "renderable") else ""
                child.set_class(label == selected_label, "selected")
            return

        # Slide the window
        start, end = self._episode_window(eps_sorted, self._selected_episode)
        await col.remove_children()
        for ep in eps_sorted[start:end]:
            cls = "selector-item selected" if ep == self._selected_episode else "selector-item"
            await col.mount(Static(f"Episode {ep}", classes=cls))

    @work(exclusive=True)
    async def _load_streams(self, episode_url: str) -> None:
        table = self.query_one("#streams-table", DataTable)
        table.clear()
        rows = await asyncio.to_thread(data.fetch_streams, episode_url)
        if not rows:
            table.add_row("—", "—", "—", "—", "—")
            return
        for r in rows:
            table.add_row(r["res"], r["size"], r["codec"], "Dailymotion", "—")

    # --------------------------------------------------------------
    # Focus / footer
    # --------------------------------------------------------------

    def _focus_region(self, idx: int) -> None:
        self._focus_index = idx % len(self.FOCUS_REGIONS)
        for i, name in enumerate(self.FOCUS_REGIONS):
            col = self.query_one(f"#{name}-col")
            col.set_class(i == self._focus_index, "focused")
        self._update_footer()

    def _update_footer(self) -> None:
        region = self.FOCUS_REGIONS[self._focus_index]
        self.query_one("#footer-hints", Static).update(
        f"[dim]focus: {region}  |  selected episode: {self._selected_episode}[/dim]"
        )

        parts = []
        if region == "seasons":
            parts.append("←/→: region")
            parts.append("Enter: select season")
        elif region == "episodes":
            parts.append("↑/↓: episode")
            parts.append("Enter: select episode")
            parts.append("d: download episode")
        elif region == "streams":
            parts.append("↑/↓: stream")
            parts.append("d: download stream")
        parts.append("Tab/←/→: change region")
        parts.append("i: Info")
        parts.append("Esc: Back")
        self.query_one("#footer-hints", Static).update("  ".join(parts))
        
    def action_focus_next_region(self) -> None:
        self._focus_region(self._focus_index + 1)

    def action_focus_prev_region(self) -> None:
        self._focus_region(self._focus_index - 1)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_show_info(self) -> None:
        self.app.push_screen(
            InfoModal(
                title=self._meta.get("title") or self._result["title"],
                description=self._meta.get("description", ""),
            )
        )

    def action_noop_fav(self) -> None:
        self.app.notify("Favourites not implemented in v1.", severity="information")

    def action_download(self) -> None:
        region = self.FOCUS_REGIONS[self._focus_index]
        if region == "seasons":
            self.app.notify("Select an episode to download.", severity="warning")
            return
        if self._selected_episode is None:
            self.app.notify("No episode selected.", severity="warning")
            return
        episode_url = self._episodes.get(self._selected_episode)
        if not episode_url:
            self.app.notify("No URL for that episode.", severity="error")
            return

        content_type = self.app.default_content_type
        anime = data.find_in_watchlist(self._meta.get("title") or self._result["title"], content_type)
        if anime is None:
            anime = data.add_to_watchlist(
                name=self._meta.get("title") or self._result["title"],
                season=f"season {self._meta.get('season')}" if self._meta.get("season") else None,
                content_type=content_type,
            )

        job_id = data.queue_download(anime, self._selected_episode, episode_url, content_type)
        self.app.notify(f"Queued ep {self._selected_episode} as job #{job_id}")