# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""BrowserApp — AppProtocol implementation for the family browser."""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import Static

__all__ = ["BrowserApp"]


class BrowserApp(App[None]):
    """Pilot app implementing the screen contract."""

    DEFAULT_CSS = """
    #status { height: auto; content-align: center middle; }
    #status.refused { color: $error; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.last_status = ""
        self.last_status_refused = False

    def compose(self) -> ComposeResult:
        yield Static("", id="status")

    def notify_status(self, message: str, *, refused: bool = False) -> None:
        self.last_status = message
        self.last_status_refused = refused
        status = self.query_one("#status", Static)
        status.update(message)
        if refused:
            status.add_class("refused")
        else:
            status.remove_class("refused")
        print(message)

    def notify_progress(self, label: str, done: int, total: int) -> None:
        refused = self.last_status_refused
        self.last_status = label
        status = self.query_one("#status", Static)
        status.update(label)
        if refused:
            status.add_class("refused")
        else:
            status.remove_class("refused")
        print(label)

    def push_screen(  # type: ignore[override]
        self, screen: object, *, wait_for_dismiss: bool = False
    ) -> Any:
        return super().push_screen(  # type: ignore[call-overload]
            screen,
            wait_for_dismiss=wait_for_dismiss,
        )
