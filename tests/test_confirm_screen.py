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

"""ConfirmScreen mounted in a pilot app."""

from __future__ import annotations

from typing import cast

from textual.app import App, ComposeResult

from vinsynlib.ui.confirm import ConfirmScreen


class ConfirmApp(App[bool]):
    """Small app that pushes ConfirmScreen and records the result."""

    def __init__(self, danger: bool = False) -> None:
        super().__init__()
        self.result: bool | None = None
        self.danger = danger

    def compose(self) -> ComposeResult:
        yield from []

    def on_mount(self) -> None:
        def callback(result: bool | None) -> None:
            self.result = result

        self.push_screen(
            ConfirmScreen(
                "Confirm?",
                confirm="Yes",
                cancel="No",
                danger=self.danger,
            ),
            callback,
        )


async def test_confirm_y_returns_true() -> None:
    async with ConfirmApp().run_test() as pilot:
        await pilot.press("y")
        await pilot.pause()
        app = cast(ConfirmApp, pilot.app)
        assert app.result is True


async def test_confirm_n_returns_false() -> None:
    async with ConfirmApp().run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()
        app = cast(ConfirmApp, pilot.app)
        assert app.result is False


async def test_confirm_escape_returns_false() -> None:
    async with ConfirmApp().run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
        app = cast(ConfirmApp, pilot.app)
        assert app.result is False


def test_danger_parameter_accepted() -> None:
    """The danger flag must be accepted without error."""
    screen = ConfirmScreen("Delete?", danger=True)
    assert screen.danger is True
