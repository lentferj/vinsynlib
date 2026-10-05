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

"""The footer legend, in one widget.

Every one of these programs replaced Textual's ``Footer`` with a legend
that wraps rather than truncates -- a footer that silently drops its last
keys teaches the user those keys do not exist. The widget was then copied
into all nine, along with the text-wrapping helper it calls, which was
itself copied from rxved, which copied it from s3ked.

Three different constructors had grown up along the way: one read a module
global, one took the blocks as an argument, one built them from the
bindings. This one takes them as an argument and can build them if it is
not given any, so all three call sites work and none of them is the
special case.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static

from ..keys import CANONICAL_LEGEND, LEGEND_SEPARATOR, wrap_blocks

__all__ = ["KeyHints", "wrap_blocks"]


class KeyHints(Static):
    """The legend, wrapped to the window rather than truncated."""

    DEFAULT_CSS = (
        "KeyHints { height: auto; background: $panel; padding: 0 1; }"
    )

    def __init__(
        self,
        blocks: Sequence[str] | None = None,
        *,
        separator: str = LEGEND_SEPARATOR,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._blocks = (
            tuple(blocks) if blocks is not None else CANONICAL_LEGEND
        )
        self._separator = separator

    @property
    def blocks(self) -> tuple[str, ...]:
        """The hints, in the order they are shown."""
        return self._blocks

    def on_mount(self) -> None:
        self._render_hints()

    def on_resize(self) -> None:
        self._render_hints()

    def _render_hints(self) -> None:
        # NOT named _render: Widget._render is Textual's own, and shadowing
        # it makes every layout pass ask a None for its height.
        width = max(self.size.width - 2, 20)
        self.update(wrap_blocks(self._blocks, width, self._separator))


def compose(blocks: Sequence[str], **kwargs: Any) -> ComposeResult:
    """A legend inside a ``compose``, for callers that want the widget."""
    yield KeyHints(blocks, **kwargs)
