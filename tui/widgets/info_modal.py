"""Full-description modal."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class InfoModal(ModalScreen):
    BINDINGS = [("escape,q", "dismiss", "Close")]

    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        self._title = title
        self._description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="info-modal"):
            yield Static(f"[bold]{self._title}[/bold]", id="info-modal-title")
            with VerticalScroll(id="info-modal-body"):
                yield Static(self._description or "(no description available)")
            yield Button("Close (Esc)", id="info-modal-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()