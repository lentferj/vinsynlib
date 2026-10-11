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

"""A modal text prompt, shared by all ten projects."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Label

__all__ = ["PromptScreen"]


class PromptScreen(ModalScreen[str | None]):
    """A single-line modal prompt.

    Returns the input value on ``enter``, ``None`` on ``escape``.
    """

    BINDINGS: ClassVar[list[Any]] = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        prompt: str,
        current: str = "",
        *,
        placeholder: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._prompt_text = prompt
        self._current = current
        self._placeholder = placeholder
        self._input_id = id

    def compose(self) -> ComposeResult:
        yield Label(self._prompt_text)
        yield Input(
            value=self._current,
            placeholder=self._placeholder,
            id=self._input_id,
        )

    def on_mount(self) -> None:
        input_widget = (
            self.query_one(f"#{self._input_id}", Input)
            if self._input_id
            else self.query_one(Input)
        )
        input_widget.focus()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        self.dismiss(message.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
