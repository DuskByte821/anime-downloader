"""Stage 1 — Home."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, Static, Label

from config import VERSION
# from tui.widgets.logo import Logo


class HomeScreen(Screen):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+t", "noop", "TV"),
        ("question_mark", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-root"):
            with Center(id="logo-wrap"):
                yield Static(f"[bold]Anime Downloader[/bold]  [dim]v{VERSION}[/dim]", id="version")

 #               yield Logo(id="logo")
  #              yield Static(f"[dim]v{VERSION}[/dim]", id="version")
                
            with Center():
                with Vertical(id="home-search-wrap"):
                    yield Input(
                        placeholder="Search anime or enter a command...",
                        id="home-search",
                    )

            with Vertical(id="home-history"):
                yield Label("[bold]History / Resume[/bold]", classes="section-title")
                with VerticalScroll():
                    yield Static("[dim]No history yet.[/dim]")

            with Center():
                yield Static(
                    "[dim]Ctrl+T TV   ? Help   q Quit[/dim]",
                    id="home-footer",
                )

    def on_mount(self) -> None:
        self.query_one("#home-search", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        if text.startswith("/"):
            self.app.handle_slash_command(text)
            return
        # Instantiate directly — Textual accepts Screen instances in push_screen.
        from tui.screens.search import SearchScreen
        self.app.push_screen(SearchScreen(text))

    def action_help(self) -> None:
        self.app.push_screen("help")

    def action_noop(self) -> None:
        self.app.notify("TV view is not implemented in v1.", severity="information")