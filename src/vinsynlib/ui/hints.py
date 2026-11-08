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

Because an uncapped legend can eat half the screen on a narrow terminal,
the widget now truncates at ``MAX_LINES`` lines, keeping the first lines
and ending with an explicit pointer (``MORE``) to the full list. The
pointer keeps the original concern addressed: no key is dropped silently,
the user is told where the rest live. A legend that already fits is left
untouched, pointer and all.

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
    """The legend, wrapped to the window and capped at ``MAX_LINES`` lines.

    A legend that already fits is rendered unchanged. One that would take
    more than ``MAX_LINES`` lines is cut to ``MAX_LINES``, the last of
    which ends with ``MORE`` so the user knows the rest exist.
    """

    # Cap on rendered lines. A class attribute so an app can override it.
    MAX_LINES = 2
    # Pointer appended to the last rendered line when truncating.
    MORE = "… ? for all keys"

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
        text = wrap_blocks(self._blocks, width, self._separator)
        lines = text.split("\n")
        max_lines = max(self.MAX_LINES, 1)
        if len(lines) <= max_lines:
            self.update(text)
            return
        more = self.MORE
        kept = lines[: max_lines - 1]
        # Truncate the next wrapped line so the pointer fits on the last
        # line; trim once more so nothing can overflow the width.
        head = lines[max_lines - 1]
        head = head[: max(width - len(more) - 1, 0)]
        # Cut back to the last complete hint: never show a partial hint.
        # Drop the incomplete tail after the final separator. If there is
        # no separator at all (a single hint wider than the line) there is
        # nothing to cut back to, so keep the width-based slice.
        pos = head.rfind(self._separator)
        if pos != -1:
            head = head[:pos]
        final = (head + " " + more)[:width]
        kept.append(final)
        self.update("\n".join(kept))


# Module-level aliases for callers that import the constants directly rather
# than through ``KeyHints``. ``KeyHints`` remains the source of truth.
MAX_LINES = KeyHints.MAX_LINES
MORE = KeyHints.MORE


def compose(blocks: Sequence[str], **kwargs: Any) -> ComposeResult:
    """A legend inside a ``compose``, for callers that want the widget."""
    yield KeyHints(blocks, **kwargs)
