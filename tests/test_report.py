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

"""ReportScreen mounted in a pilot app, and the shapes it reaches.

The last two tests are the extraction's claim: the frame is one class and
the family's divergences are subclasses. rxved closes on ``enter`` as
well; eosed puts the body in a narrower, id-styled box and builds it
from ``BINDINGS``. If either of those stops being expressible without
editing the library, this is the test that says so.
"""

from __future__ import annotations

from typing import Any, ClassVar, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Label, Static

from vinsynlib.ui.report import ReportScreen


class ReportApp(App[None]):
    """A small app that pushes a report and records the dismissal."""

    def __init__(self, screen: ReportScreen) -> None:
        super().__init__()
        self._screen = screen
        self.closed = False

    def compose(self) -> ComposeResult:
        yield from []

    def on_mount(self) -> None:
        def closed(_: None) -> None:
            self.closed = True

        self.push_screen(self._screen, closed)


async def test_the_title_is_bold_and_the_body_is_the_body() -> None:
    """The frame, and nothing else: the words are the caller's."""
    async with ReportApp(
        ReportScreen("Somewhere", "words")
    ).run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert str(screen.query_one(Label).visual) == "Somewhere"
        assert str(screen.query_one("Static.body", Static).visual) == "words"
        # The one line the frame adds: how to leave.
        hint = list(screen.query(Static))[-1]
        assert "close" in str(hint.visual)


async def test_escape_closes_it() -> None:
    async with ReportApp(ReportScreen("Somewhere", "x")).run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
        assert cast(ReportApp, pilot.app).closed


async def test_q_closes_it() -> None:
    async with ReportApp(ReportScreen("Somewhere", "x")).run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert cast(ReportApp, pilot.app).closed


async def test_a_long_body_scrolls_rather_than_truncating() -> None:
    """The reason a tool writes a screen instead of a notification.

    A plain ``Static`` with ``overflow-y: auto`` does **not** scroll in
    Textual -- which is what the eight copies of this class do, and a
    long body is silently clipped by all of them. The body therefore
    lives in a scroll container, and this is the test that keeps it
    there.
    """
    body = "\n".join(f"line {n}" for n in range(200))
    async with ReportApp(ReportScreen("Somewhere", body)).run_test() as pilot:
        await pilot.pause()
        scroll = pilot.app.screen.query("VerticalScroll").first()
        assert scroll.allow_vertical_scroll
        assert scroll.scroll_offset.y == 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert scroll.scroll_offset.y > 0, "the body scrolled"


class RvReportScreen(ReportScreen):
    """rxved's shape: ``enter`` closes as well. Three lines, no rewrite."""

    BINDINGS: ClassVar[list[Any]] = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("enter", "close", "Close"),
    ]


async def test_an_extra_close_binding_is_a_subclass_not_a_copy() -> None:
    async with ReportApp(RvReportScreen("Somewhere", "x")).run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert cast(ReportApp, pilot.app).closed


class EosedReportScreen(ReportScreen):
    """eosed's shape: ids, narrower, ``q`` hidden, and a body from
    ``BINDINGS``.

    A ``compose`` of its own, which is the honest demonstration: the
    subclass keeps the close keys and the dismissal and replaces what is
    inside the box. ``q`` is re-declared as an explicit
    :class:`~textual.binding.Binding` because the flag is not accepted
    in a tuple -- Textual merges ``BINDINGS`` per key with the most
    derived class winning, so saying it again here *hides* it rather
    than adding a second binding for the same key.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ReportScreen { align: center middle; }
    ReportScreen > Vertical {
        width: 64; height: auto; max-height: 80%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    """

    def __init__(self, blocks: list[str]) -> None:
        super().__init__("eosed keys", "\n".join(blocks))

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[b]eosed keys[/b]", id="help-title"),
            VerticalScroll(
                Static(self.body, id="help-body"), id="help-scroll"
            ),
            Static("[dim]w arms writes, esc closes[/dim]"),
            id="help-box",
        )


async def test_a_different_box_is_a_subclass_not_a_copy() -> None:
    async with ReportApp(EosedReportScreen(["a", "b"])).run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#help-box") is not None
        assert screen.query_one("#help-scroll", VerticalScroll) is not None
        assert str(screen.query_one("#help-body", Static).visual) == "a\nb"
        assert "eosed keys" in str(
            screen.query_one("#help-title", Static).visual
        )
        # The footer is what the app draws from a binding's `show` flag, so
        # this is where "eosed hides its q" is proved rather than asserted.
        shown = [b.key for b in screen._bindings.shown_keys]
        assert "q" not in shown, "eosed advertises no q"
        assert screen._bindings.get_bindings_for_key("q"), "but it is bound"
        await pilot.press("q")
        await pilot.pause()
        assert cast(ReportApp, pilot.app).closed
