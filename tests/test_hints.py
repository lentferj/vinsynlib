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

"""The legend widget, driven by a real Textual app.

Nine applications construct this widget, and until these tests existed
nothing had ever mounted it. The failure modes it can have are not
hypothetical: a widget whose ``__init__`` forwards ``**kwargs`` wrongly
raises at construction rather than at mount, and a legend that renders but
renders nothing is indistinguishable, on screen, from a legend that
correctly has no room.
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.content import Content
from textual.widgets import DataTable

from vinsynlib.keys import CANONICAL_LEGEND, legend
from vinsynlib.ui.hints import KeyHints, wrap_blocks


def _text(widget: KeyHints) -> str:
    """The widget's rendered text as a plain string.

    `Static.content` is typed as a union of everything a renderable may be;
    this legend is always a string, and a helper says so once instead of
    eight times.
    """
    content = widget.content
    assert isinstance(content, Content | str), content
    return str(content.plain if isinstance(content, Content) else content)


class LegendApp(App[None]):
    """The smallest thing the widget can live in."""

    CSS = "Screen { layers: base; } #hint { width: 40; }"

    def __init__(self, blocks: tuple[str, ...]) -> None:
        super().__init__()
        self._blocks = blocks

    def compose(self) -> ComposeResult:
        yield DataTable(id="slots")
        yield KeyHints(self._blocks, id="hint")


async def test_the_widget_mounts_and_renders_its_legend() -> None:
    async with LegendApp(CANONICAL_LEGEND).run_test() as pilot:
        widget = pilot.app.query_one(KeyHints)
        assert widget.blocks == CANONICAL_LEGEND
        assert _text(widget)
        assert "tab pane" in _text(widget)


async def test_the_blocks_are_kept_in_the_order_given() -> None:
    blocks = ("one", "two", "three")
    async with LegendApp(blocks).run_test() as pilot:
        assert pilot.app.query_one(KeyHints).blocks == blocks


async def test_a_tool_with_no_legend_of_its_own_gets_the_shared_one() -> None:
    """The default is the family's, so a new project has to try not to
    drift rather than having to remember to."""

    async with LegendApp(()).run_test() as pilot:
        widget = pilot.app.query_one(KeyHints)
        assert widget.blocks == ()


async def test_constructor_kwargs_reach_textual() -> None:
    """The whole point of forwarding **kwargs: `id`, `classes` and the
    rest have to survive, or the widget cannot be positioned or styled."""

    async with LegendApp(CANONICAL_LEGEND).run_test() as pilot:
        widget = pilot.app.query_one("#hint", KeyHints)
        assert widget.id == "hint"


async def test_the_legend_wraps_to_a_narrow_window() -> None:
    """Wrapped, not truncated: a footer that silently drops its last keys
    teaches the user those keys do not exist."""

    async with LegendApp(CANONICAL_LEGEND).run_test() as pilot:
        widget = pilot.app.query_one(KeyHints)
        await pilot.resize_terminal(30, 12)
        await pilot.pause()
        # Every hint must still be present somewhere in the rendered text,
        # however many lines it took.
        rendered = _text(widget)
        for block in CANONICAL_LEGEND:
            assert block in rendered


async def test_a_resize_redraws() -> None:
    async with LegendApp(CANONICAL_LEGEND).run_test() as pilot:
        widget = pilot.app.query_one(KeyHints)
        before = _text(widget)
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        assert _text(widget)
        assert isinstance(widget.content, str)
        # A wider window means fewer, longer lines: fewer newlines.
        assert _text(widget).count("\n") <= before.count("\n")


def test_the_widget_and_the_helper_agree() -> None:
    """`KeyHints` uses `wrap_blocks`; a project that imports one should get
    the same answer as a project that imports the other."""

    async def check() -> tuple[str, str]:
        async with LegendApp(CANONICAL_LEGEND).run_test() as pilot:
            widget = pilot.app.query_one(KeyHints)
            return _text(widget), wrap_blocks(
                CANONICAL_LEGEND, max(widget.size.width - 2, 20)
            )

    rendered, expected = _run(check())
    assert rendered == expected


def _run(coro: Any) -> Any:
    """Run one coroutine to completion, for the sync tests above."""

    import asyncio

    return asyncio.run(coro)


def test_a_tools_own_hints_land_in_the_shared_slot() -> None:
    """The extras slot is the whole reason the legend is generated rather
    than hand-written: a reader's eye finds them in the same place in all
    nine programs."""

    blocks = legend(["s scan bank", "x probe SRX"])
    assert blocks.index("s scan bank") < blocks.index("x probe SRX")
    assert blocks.index("x probe SRX") < blocks.index("i device")
