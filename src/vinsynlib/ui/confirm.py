# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
#
# This file is part of vinsynlib.
#
# vinsynlib is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# vinsynlib is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.

"""A generic yes/no confirmation modal."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

__all__ = ["ConfirmScreen"]


class ConfirmScreen(ModalScreen[bool]):
    """Modal yes/no dialog. `y` confirms; `n` or `escape` cancels."""

    BINDINGS: ClassVar[list[Any]] = [
        ("y", "confirm", "Confirm"),
        ("n", "cancel", "Cancel"),
        ("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }
    ConfirmScreen.danger #confirm-dialog {
        border: solid $error;
    }
    #confirm-prompt {
        content-align: center middle;
        text-align: center;
        height: auto;
        padding: 1;
    }
    #confirm-buttons {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    """

    def __init__(
        self,
        prompt: str,
        *,
        confirm: str = "Yes",
        cancel: str = "No",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self.prompt_text = prompt
        self.confirm_text = confirm
        self.cancel_text = cancel
        self.danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self.prompt_text, id="confirm-prompt")
            with Horizontal(id="confirm-buttons"):
                yield Button(
                    self.confirm_text,
                    id="confirm-yes",
                    variant="primary",
                )
                yield Button(
                    self.cancel_text,
                    id="confirm-no",
                    variant="default",
                )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_mount(self) -> None:
        if self.danger:
            self.add_class("danger")
