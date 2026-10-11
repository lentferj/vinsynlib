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

"""PromptScreen submit and cancel, driven by a pilot App."""

from __future__ import annotations

from textual.app import App

from vinsynlib.ui.prompt import PromptScreen


class PromptApp(App[None]):
    """Small app to host the modal."""


async def test_submit_returns_the_input_value() -> None:
    screen = PromptScreen(
        "Name?",
        current="hello",
        placeholder="type",
        id="test_input",
    )
    results: list[str | None] = []

    def collect(result: str | None) -> None:
        results.append(result)

    async with PromptApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == ["hello"]


async def test_cancel_returns_none() -> None:
    screen = PromptScreen(
        "Name?",
        current="hello",
        id="test_input",
    )
    results: list[str | None] = []

    def collect(result: str | None) -> None:
        results.append(result)

    async with PromptApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]
