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

"""Pilot-app tests for all modal screens."""

from __future__ import annotations

from typing import Any, cast

from textual.app import App, ComposeResult

from vinsynlib.ui.modals import (
    CategoryScreen,
    ChoiceScreen,
    PickerScreen,
    RatingFilter,
    RatingFilterScreen,
    ReportScreen,
    SearchScreen,
)


class ModalApp(App[None]):
    """Host app implementing AppProtocol."""

    def __init__(self) -> None:
        super().__init__()
        self.last_status = ""
        self.last_status_refused = False

    def compose(self) -> ComposeResult:
        yield from []

    def notify_status(self, message: str, *, refused: bool = False) -> None:
        self.last_status = message
        self.last_status_refused = refused

    def notify_progress(self, label: str, done: int, total: int) -> None:
        pass


# --- ReportScreen ------------------------------------------------------------


async def test_report_screen_closes_on_escape() -> None:
    screen = ReportScreen("Title", ["line 1", "line 2"])
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]


async def test_report_screen_closes_on_q() -> None:
    screen = ReportScreen("Title", ["line 1"])
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("q")
        await pilot.pause()

    assert results == [None]


async def test_report_screen_closes_on_enter() -> None:
    screen = ReportScreen("Title", ["line 1"])
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [None]


async def test_report_screen_sends_status() -> None:
    screen = ReportScreen("Title", ["line 1"], status_message="Report shown")
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Report shown"


# --- ChoiceScreen ------------------------------------------------------------


async def test_choice_screen_returns_current_index() -> None:
    screen = ChoiceScreen("Pick", ["a", "b", "c"], current=1)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [1]


async def test_choice_screen_returns_none_on_escape() -> None:
    screen = ChoiceScreen("Pick", ["a", "b"], current=0)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]


async def test_choice_screen_enter_priority_over_datatable() -> None:
    """Enter must have priority=True so DataTable doesn't eat it."""
    screen = ChoiceScreen("Pick", ["a", "b", "c"], current=0)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        # Move down then press enter - should confirm the new selection
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

    assert results == [1]


async def test_choice_screen_sends_status() -> None:
    screen = ChoiceScreen("Pick", ["a", "b"], status_message="Choose one")
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Choose one"


# --- SearchScreen ------------------------------------------------------------


async def test_search_screen_returns_needle_and_fields() -> None:
    screen = SearchScreen(
        "Search", {"names": True, "tags": False, "notes": True}
    )
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("t", "e", "s", "t")
        await pilot.press("enter")
        await pilot.pause()

    assert results == [("test", {"names": True, "tags": False, "notes": True})]


async def test_search_screen_returns_none_on_escape() -> None:
    screen = SearchScreen("Search", {"names": True})
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]


async def test_search_screen_respects_current_needle() -> None:
    screen = SearchScreen("Search", {"names": True}, current_needle="existing")
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()


async def test_search_screen_sends_status() -> None:
    screen = SearchScreen(
        "Search", {"names": True}, status_message="Searching..."
    )
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Searching..."


# --- RatingFilterScreen ------------------------------------------------------


async def test_rating_filter_escape_returns_unchanged() -> None:
    current = RatingFilter(stars=3, at_least=True)
    screen = RatingFilterScreen(current)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [current]


async def test_rating_filter_x_then_enter_clears() -> None:
    current = RatingFilter(stars=4, at_least=False)
    screen = RatingFilterScreen(current)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("x")
        await pilot.press("enter")
        await pilot.pause()

    assert results == [RatingFilter(stars=0, at_least=True)]


async def test_rating_filter_confirm_returns_new_values() -> None:
    current = RatingFilter(stars=0, at_least=True)
    screen = RatingFilterScreen(current)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        # Type "2" in stars input, toggle at_least, press enter
        await pilot.press("2")
        await pilot.press("tab")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, RatingFilter)
    assert result.stars == 2
    assert result.at_least is False


async def test_rating_filter_sends_status() -> None:
    screen = RatingFilterScreen(
        RatingFilter(0, True), status_message="Filter ratings"
    )
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Filter ratings"


# --- CategoryScreen ----------------------------------------------------------


async def test_category_screen_returns_selected_codes() -> None:
    cats = {"a": ("Alpha", 5), "b": ("Beta", 3), "c": ("Gamma", 7)}
    screen = CategoryScreen("Categories", cats, current={"a"})
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("down")  # move to Beta
        await pilot.press("space")  # toggle Beta
        await pilot.press("enter")
        await pilot.pause()

    assert results == [{"a", "b"}]


async def test_category_screen_escape_returns_none() -> None:
    cats = {"a": ("Alpha", 5)}
    screen = CategoryScreen("Categories", cats, current={"a"})
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]


async def test_category_screen_empty_selection_returns_none() -> None:
    cats = {"a": ("Alpha", 5)}
    screen = CategoryScreen("Categories", cats, current=set())
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [None]


async def test_category_screen_sends_status() -> None:
    screen = CategoryScreen(
        "Categories", {"a": ("A", 1)}, status_message="Pick cats"
    )
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Pick cats"


# --- PickerScreen ------------------------------------------------------------


async def test_picker_screen_returns_bank_and_slot() -> None:
    banks = [("u:1", "User 1", 8), ("u:2", "User 2", 8)]
    screen = PickerScreen("Picker", banks, "u:1", 3)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [("u:1", 3)]


async def test_picker_screen_escape_returns_none() -> None:
    banks = [("u:1", "User 1", 8)]
    screen = PickerScreen("Picker", banks, "u:1", 1)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]


async def test_picker_screen_navigate_banks_with_left_right() -> None:
    banks = [("u:1", "User 1", 4), ("u:2", "User 2", 4), ("u:3", "User 3", 4)]
    screen = PickerScreen("Picker", banks, "u:2", 2)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("left")  # go to User 1
        await pilot.press("enter")
        await pilot.pause()

    assert results == [("u:1", 1)]


async def test_picker_screen_slot_selection_updates_current() -> None:
    banks = [("u:1", "User 1", 4)]
    screen = PickerScreen("Picker", banks, "u:1", 1)
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        # Navigate to slot 3 in the slot table
        await pilot.press("tab")  # focus slot table
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

    assert results == [("u:1", 3)]


async def test_picker_screen_kinds_filter() -> None:
    banks = [("u:1", "User 1", 4), ("p:1", "Preset 1", 4)]
    screen = PickerScreen("Picker", banks, "u:1", 1, kinds=("u",))
    results: list[Any] = []

    def collect(result: Any) -> None:
        results.append(result)

    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen, callback=collect)
        await pilot.press("enter")
        await pilot.pause()

    assert results == [("u:1", 1)]


async def test_picker_screen_shared_slot_parse() -> None:
    """Test the internal _slot parser."""
    banks = [("u:1", "User 1", 4)]
    screen = PickerScreen("Picker", banks, "u:1", 1)

    # Test valid parse
    parsed = screen._slot("u:1:003")
    assert parsed == ("u:1", 3)

    # Test invalid parses
    assert screen._slot("invalid") is None
    assert screen._slot("u:") is None
    assert screen._slot(":003") is None
    assert screen._slot("u:abc") is None


async def test_picker_screen_sends_status() -> None:
    banks = [("u:1", "User 1", 4)]
    screen = PickerScreen(
        "Picker", banks, "u:1", 1, status_message="Pick slot"
    )
    async with ModalApp().run_test() as pilot:
        await pilot.app.push_screen(screen)
        await pilot.pause()
        app = cast(ModalApp, pilot.app)
        assert app.last_status == "Pick slot"
