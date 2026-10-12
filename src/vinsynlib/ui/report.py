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

"""A scrollable block of text, as a modal: details, help, a result.

The family's read-only dialog. Nine tools wrote their own copy of it --
eight named ``ReportScreen``, one named it ``HelpScreen`` -- and this is
the one they share.

What the copies agree on is worth having once: a bold title, a body that
scrolls rather than truncates, and two keys that close it. What they
disagree on is worth having *there*: an extra ``enter`` to close, a
footer under the body, a narrower box with ids instead of a class, a
body assembled from ``BINDINGS``. All of those are subclasses -- a
binding added, a ``compose`` overridden, a ``DEFAULT_CSS`` re-declared,
which Textual merges over this one -- so none of them is a reason to
keep typing this class out.

The words are the tool's own and are passed in. The library supplies
the frame.

Which of the two divergences to reach by subclass and which by a
parameter is settled the same way for all of them: subclass, because
each one is a *statement about a widget* -- a box's shape, a key that
exists, a footer under the body -- and a parameter for every one of them
would be a bag of switches the library would have to keep interpreting.
Textual already resolves all three the way a subclass wants: it merges
``BINDINGS`` per key with the most derived class winning, it merges
``DEFAULT_CSS`` down the MRO, and a ``compose`` override replaces the
inside wholesale. So a subclass that hides eosed's ``q`` declares it
again as an explicit ``Binding(..., show=False)`` -- the flag is not
accepted in a tuple -- and the key stays bound while the footer stops
advertising it.

Not :class:`vinsynlib.ui.modals.ReportScreen`, which is the library's
own result modal: a title and a list of lines, no box around them, and
``enter`` closes it too. That one is a screen a tool *composes*; this
one is the frame a tool *fills with its own words*. They share the
name because both answer to it, and they share nothing else -- which is
why they are two classes and not one signature taking both.
"""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

__all__ = ["ReportScreen"]


class ReportScreen(ModalScreen[None]):
    """One block of text, read-only, over whatever is behind it."""

    BINDINGS: ClassVar[list[Any]] = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]

    DEFAULT_CSS = """
    ReportScreen { align: center middle; }
    ReportScreen > Vertical {
        width: 84; height: 80%; border: thick $accent;
        background: $surface; padding: 1 2;
    }
    ReportScreen VerticalScroll { height: 1fr; }
    ReportScreen .body { height: auto; }
    """

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.title_text}[/b]")
            with VerticalScroll():
                yield Static(self.body, classes="body")
            yield Static("[dim]esc / q to close[/dim]")

    def action_close(self) -> None:
        self.dismiss(None)
