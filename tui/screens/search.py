"""Stage 2 — Search results."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.screen import Screen
from textual.widgets import Static, Input
import asyncio
from textual import work

from tui import data


class SearchScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("up", "cursor_up", ""),
        ("down", "cursor_down", ""),
        ("enter", "open_selected", "Open"),
    ]

    def __init__(self, query: str) -> None:
        super().__init__()
        self._query = query
        self._results: list[dict] = []
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="search-root"):
            yield Static(f"[bold]Search results for[/bold]  [italic]{self._query}[/italic]", id="search-header")
            with VerticalScroll(id="search-results", can_focus=False):
                yield Static("[dim]Searching…[/dim]", id="search-loading")

    def on_mount(self) -> None:
        self.focus()
        self._run_search()

    @work(exclusive=True)
    async def _run_search(self) -> None:
        results = await asyncio.to_thread(data.search, self._query)
        self._results = results
        await self._render_results()

    async def _render_results(self) -> None:
        container = self.query_one("#search-results", VerticalScroll)
        await container.remove_children()
        if not self._results:
            await container.mount(Static("[yellow]No results found.[/yellow]"))
            return
        for i, r in enumerate(self._results):
            css_class = "result-card selected" if i == 0 else "result-card"
            body = (
                f"[bold]{r['title']}[/bold]\n"
                f"[dim]Latest: {r['latest'] or '—'}[/dim]\n"
                f"[magenta](Lucifer Donghua)[/magenta]"
            )
            await container.mount(Static(body, classes=css_class))

    def _highlight(self) -> None:
        cards = self.query(".result-card")
        for i, c in enumerate(cards):
            c.set_class(i == self._cursor, "selected")

    def action_cursor_up(self) -> None:
        if not self._results:
            return
        self._cursor = (self._cursor - 1) % len(self._results)
        self._highlight()

    def action_cursor_down(self) -> None:
        if not self._results:
            return
        self._cursor = (self._cursor + 1) % len(self._results)
        self._highlight()

    def action_open_selected(self) -> None:
        if not self._results:
            return
        r = self._results[self._cursor]
        from tui.screens.details import TitleDetailsScreen
        self.app.push_screen(TitleDetailsScreen(r))

    def action_back(self) -> None:
        self.app.pop_screen()