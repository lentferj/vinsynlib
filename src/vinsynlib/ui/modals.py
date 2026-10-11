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

"""Modal screens shared by the browser family.

All screens take data + callbacks in their constructors and return structured
results via ``dismiss``. They never contain manufacturer bytes or wire
formats; wording is supplied by the caller. Status messages go through
:class:`vinsynlib.ui.protocol.AppProtocol.notify_status` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Checkbox, DataTable, Input, Label, Static

from .protocol import AppProtocol

__all__ = [
    "CategoryScreen",
    "ChoiceScreen",
    "PickerScreen",
    "RatingFilter",
    "RatingFilterScreen",
    "ReportScreen",
    "SearchScreen",
]


class ReportScreen(ModalScreen[None]):
    """A read-only report modal. ``escape`` / ``q`` / ``enter`` close it."""

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    def __init__(
        self,
        title: str,
        lines: list[str],
        *,
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._title = title
        self._lines = lines
        self._status_message = status_message

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="report-title")
        yield Static("\n".join(self._lines), id="report-body")

    def on_mount(self) -> None:
        if self._status_message:
            self._notify(self._status_message)

    def action_close(self) -> None:
        self.dismiss(None)

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)


class ChoiceScreen(ModalScreen[int | None]):
    """A modal list where the user picks one index.

    The currently-selected item is marked with ``[x]``. ``enter`` confirms
    with ``priority=True`` because a ``DataTable`` would otherwise consume it.
    ``escape`` cancels and returns ``None``.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm", priority=True),
    ]

    def __init__(
        self,
        title: str,
        choices: list[str],
        current: int = 0,
        *,
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._title = title
        self._choices = choices
        if choices:
            self._current = max(0, min(current, len(choices) - 1))
        else:
            self._current = 0
        self._status_message = status_message
        self._table: DataTable[Any] | None = None
        self._row_keys: list[Any] = []
        self._marker_col: Any = None

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="choice-title")
        table: DataTable[Any] = DataTable(id="choice-table", cursor_type="row")
        self._marker_col = table.add_column("marker", key="marker", width=4)
        table.add_column("choice", key="choice")
        self._row_keys = []
        for i, choice in enumerate(self._choices):
            marker = "[x]" if i == self._current else "[ ]"
            row_key = table.add_row(marker, choice, key=str(i))
            self._row_keys.append(row_key)
        self._table = table
        yield table

    def on_mount(self) -> None:
        if self._table and self._choices:
            self._table.move_cursor(row=self._current)
        if self._status_message:
            self._notify(self._status_message)

    def on_key(self, event: Any) -> None:
        key = event.key if hasattr(event, "key") else ""
        if key == "up" and self._current > 0:
            self._current -= 1
            if self._table:
                self._table.move_cursor(row=self._current)
                self._refresh_marker()
            event.prevent_default()
        elif key == "down" and self._current < len(self._choices) - 1:
            self._current += 1
            if self._table:
                self._table.move_cursor(row=self._current)
                self._refresh_marker()
            event.prevent_default()

    def action_confirm(self) -> None:
        if self._choices:
            self.dismiss(self._current)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _refresh_marker(self) -> None:
        if not self._table or not self._marker_col:
            return
        for i in range(len(self._choices)):
            marker = "[x]" if i == self._current else "[ ]"
            if i < len(self._row_keys):
                self._table.update_cell(
                    self._row_keys[i], self._marker_col, marker
                )

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)


class SearchScreen(ModalScreen[tuple[str, dict[str, bool]] | None]):
    """A modal search form with field checkboxes.

    Returns ``(needle, {field: enabled})`` on confirm, ``None`` on cancel.
    Field checkboxes default to enabled.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm", priority=True),
    ]

    def __init__(
        self,
        title: str,
        fields: dict[str, bool] | None = None,
        *,
        current_needle: str = "",
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._title = title
        self._fields = fields or {"names": True, "tags": True, "notes": True}
        self._current_needle = current_needle
        self._status_message = status_message
        self._needle_input: Input | None = None
        self._checkboxes: dict[str, Checkbox] = {}

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="search-title")
        self._needle_input = Input(
            value=self._current_needle,
            placeholder="search term",
            id="search-needle",
        )
        yield self._needle_input
        with Horizontal(id="search-fields"):
            for field, enabled in self._fields.items():
                cb = Checkbox(
                    field.capitalize(), value=enabled, id=f"search-{field}"
                )
                self._checkboxes[field] = cb
                yield cb

    def on_mount(self) -> None:
        if self._needle_input:
            self._needle_input.focus()
        if self._status_message:
            self._notify(self._status_message)

    def action_confirm(self) -> None:
        if not self._needle_input:
            self.dismiss(None)
            return
        needle = self._needle_input.value.strip()
        fields = {f: cb.value for f, cb in self._checkboxes.items()}
        self.dismiss((needle, fields))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)


@dataclass(frozen=True)
class RatingFilter:
    """Immutable filter for star ratings."""

    stars: int  # 0-5, 0 means "any"
    at_least: bool  # True = >= stars, False = exactly stars


class RatingFilterScreen(ModalScreen[RatingFilter | None]):
    """A modal to edit a :class:`RatingFilter`.

    - ``escape`` returns the *unchanged* incoming filter.
    - ``x`` then ``enter`` clears the filter (returns ``RatingFilter(0,
      True)``).
    - Depends only on ``favorites`` (for the :class:`RatingFilter` type)
      and Textual.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("x", "clear", "Clear"),
        Binding("enter", "confirm", "Confirm", priority=True),
    ]

    def __init__(
        self,
        current: RatingFilter,
        *,
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._current = current
        self._status_message = status_message
        self._pending_clear = False
        self._stars_input: Input | None = None
        self._at_least_checkbox: Checkbox | None = None

    def compose(self) -> ComposeResult:
        yield Label("Rating filter", id="rating-title")
        with Horizontal(id="rating-controls"):
            self._stars_input = Input(
                value=str(self._current.stars)
                if self._current.stars > 0
                else "",
                placeholder="0-5 (empty = any)",
                id="rating-stars",
            )
            yield self._stars_input
            self._at_least_checkbox = Checkbox(
                "at least", value=self._current.at_least, id="rating-at-least"
            )
            yield self._at_least_checkbox
        yield Static(
            "esc: keep unchanged | x then enter: clear filter",
            id="rating-hint",
        )

    def on_mount(self) -> None:
        if self._status_message:
            self._notify(self._status_message)

    def action_clear(self) -> None:
        self._pending_clear = True
        if self._stars_input:
            self._stars_input.value = ""
        if self._at_least_checkbox:
            self._at_least_checkbox.value = True

    def action_confirm(self) -> None:
        if self._pending_clear:
            self.dismiss(RatingFilter(stars=0, at_least=True))
            return
        stars = 0
        if self._stars_input and self._stars_input.value.strip():
            text = self._stars_input.value.strip().lower()
            if text == "x":
                self.dismiss(RatingFilter(stars=0, at_least=True))
                return
            try:
                stars = max(0, min(5, int(text)))
            except ValueError:
                stars = 0
        if self._at_least_checkbox:
            at_least = self._at_least_checkbox.value
        else:
            at_least = True
        self.dismiss(RatingFilter(stars=stars, at_least=at_least))

    def action_cancel(self) -> None:
        self.dismiss(self._current)

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)


class CategoryScreen(ModalScreen[set[str] | None]):
    """A modal to pick categories.

    The ``categories`` parameter is a mapping ``{code: (label, count)}``.
    The caller decides the codes and labels; this screen does not import
    ``cat.CATEGORY_NAMES``.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("space", "toggle_item", "Toggle"),
    ]

    def __init__(
        self,
        title: str,
        categories: dict[str, tuple[str, int]],
        current: set[str] | None = None,
        *,
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._title = title
        self._categories = categories
        self._current = current or set()
        self._status_message = status_message
        self._table: DataTable[Any] | None = None
        self._row_keys: list[Any] = []
        self._marker_col: Any = None
        self._sorted_codes: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="category-title")
        table: DataTable[Any] = DataTable(
            id="category-table", cursor_type="row"
        )
        self._marker_col = table.add_column("marker", key="marker", width=4)
        table.add_column("category", key="category")
        table.add_column("count", key="count", width=6)
        self._sorted_codes = sorted(self._categories.keys())
        self._row_keys = []
        for code in self._sorted_codes:
            label, count = self._categories[code]
            marker = "[x]" if code in self._current else "[ ]"
            row_key = table.add_row(marker, label, str(count), key=code)
            self._row_keys.append(row_key)
        self._table = table
        yield table

    def on_mount(self) -> None:
        if self._status_message:
            self._notify(self._status_message)

    def action_toggle_item(self) -> None:
        if not self._table or not self._marker_col:
            return
        row_idx = self._table.cursor_row
        if 0 <= row_idx < len(self._sorted_codes):
            code = self._sorted_codes[row_idx]
            if code in self._current:
                self._current.remove(code)
            else:
                self._current.add(code)
            marker = "[x]" if code in self._current else "[ ]"
            if row_idx < len(self._row_keys):
                self._table.update_cell(
                    self._row_keys[row_idx], self._marker_col, marker
                )

    def action_confirm(self) -> None:
        self.dismiss(self._current if self._current else None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)


class PickerScreen(ModalScreen[tuple[str, int] | None]):
    """Two-level picker: bank table over slot table.

    - Left table shows banks with ``<-`` marker on the current bank.
    - Right table shows slots for the selected bank.
    - Shared ``_slot`` method parses ``BANK:NNN`` row keys.
    - ``kinds`` parameter filters which bank kinds are shown.
    - Returns ``(bank_id, slot_number)`` on confirm, ``None`` on cancel.
    """

    BINDINGS: ClassVar[list[Any]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("left", "prev_bank", "Previous bank"),
        Binding("right", "next_bank", "Next bank"),
    ]

    def __init__(
        self,
        title: str,
        banks: list[tuple[str, str, int]],  # (bank_id, label, slot_count)
        current_bank: str,
        current_slot: int,
        *,
        kinds: tuple[str, ...] = (),
        status_message: str = "",
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self._title = title
        self._all_banks = banks
        self._kinds = kinds
        self._current_bank = current_bank
        self._current_slot = current_slot
        self._status_message = status_message
        self._bank_table: DataTable[Any] | None = None
        self._slot_table: DataTable[Any] | None = None
        self._filtered_banks: list[tuple[str, str, int]] = []
        self._bank_row_keys: list[Any] = []
        self._slot_row_keys: list[Any] = []
        self._mounting = False

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="picker-title")
        with Horizontal(id="picker-tables"):
            bank_table: DataTable[Any] = DataTable(
                id="picker-banks", cursor_type="row"
            )
            bank_table.add_column("bank", key="bank")
            bank_table.add_column("slots", key="slots", width=6)
            self._bank_table = bank_table
            yield bank_table

            slot_table: DataTable[Any] = DataTable(
                id="picker-slots", cursor_type="row"
            )
            slot_table.add_column("slot", key="slot")
            slot_table.add_column("name", key="name")
            self._slot_table = slot_table
            yield slot_table

    def on_mount(self) -> None:
        want_slot = self._current_slot
        self._mounting = True
        try:
            self._filter_banks()
            self._populate_bank_table()
            self._populate_slot_table()
            if self._bank_table and self._filtered_banks:
                for i, (bid, _, _) in enumerate(self._filtered_banks):
                    if bid == self._current_bank:
                        self._bank_table.move_cursor(row=i)
                        break
        finally:
            self._mounting = False
        self._current_slot = want_slot
        if self._slot_table:
            idx = max(0, min(want_slot - 1, len(self._slot_row_keys) - 1))
            if self._slot_row_keys:
                self._slot_table.move_cursor(row=idx)
        if self._status_message:
            self._notify(self._status_message)

    def _filter_banks(self) -> None:
        if not self._kinds:
            self._filtered_banks = self._all_banks
            return
        self._filtered_banks = [
            (bid, label, count)
            for bid, label, count in self._all_banks
            if any(bid.startswith(f"{kind}:") for kind in self._kinds)
        ]

    def _populate_bank_table(self) -> None:
        if not self._bank_table:
            return
        self._bank_table.clear()
        self._bank_row_keys = []
        for bid, label, count in self._filtered_banks:
            marker = "<- " if bid == self._current_bank else ""
            row_key = self._bank_table.add_row(f"{marker}{label}", str(count))
            self._bank_row_keys.append(row_key)

    def _populate_slot_table(self) -> None:
        if not self._slot_table:
            return
        self._slot_table.clear()
        self._slot_row_keys = []
        for bid, _, count in self._filtered_banks:
            if bid == self._current_bank:
                for n in range(1, count + 1):
                    marker = ">" if n == self._current_slot else " "
                    row_key = self._slot_table.add_row(
                        f"{marker}{n:03d}", "", key=f"{bid}:{n:03d}"
                    )
                    self._slot_row_keys.append(row_key)
                break

    def _slot(self, row_key: str) -> tuple[str, int] | None:
        """Parse a ``BANK:NNN`` row key into (bank_id, slot_number).

        Bank IDs can contain colons (e.g., "u:1"), so we split from the right.
        """
        if ":" not in row_key:
            return None
        bank_id, number = row_key.rsplit(":", 1)
        if not bank_id or not number.isdigit():
            return None
        return bank_id, int(number)

    def on_data_table_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        if self._mounting:
            return
        table = event.data_table
        if table.id == "picker-banks":
            row_idx = table.cursor_row
            if 0 <= row_idx < len(self._filtered_banks):
                bid, _, _ = self._filtered_banks[row_idx]
                if bid == self._current_bank:
                    return
                self._current_bank = bid
                self._current_slot = 1
                self._populate_bank_table()
                self._populate_slot_table()
        elif table.id == "picker-slots":
            row_idx = table.cursor_row
            if 0 <= row_idx < len(self._slot_row_keys):
                row_key_obj = self._slot_row_keys[row_idx]
                row_key = str(row_key_obj.value)
                parsed = self._slot(row_key)
                if parsed:
                    self._current_bank, self._current_slot = parsed

    def action_prev_bank(self) -> None:
        if not self._bank_table or not self._filtered_banks:
            return
        idx = self._bank_table.cursor_row
        if idx > 0:
            self._bank_table.move_cursor(row=idx - 1)
            bid, _, _ = self._filtered_banks[idx - 1]
            self._current_bank = bid
            self._current_slot = 1
            self._populate_bank_table()
            self._populate_slot_table()

    def action_next_bank(self) -> None:
        if not self._bank_table or not self._filtered_banks:
            return
        idx = self._bank_table.cursor_row
        if idx < len(self._filtered_banks) - 1:
            self._bank_table.move_cursor(row=idx + 1)
            bid, _, _ = self._filtered_banks[idx + 1]
            self._current_bank = bid
            self._current_slot = 1
            self._populate_bank_table()
            self._populate_slot_table()

    def action_confirm(self) -> None:
        self.dismiss((self._current_bank, self._current_slot))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _notify(self, message: str) -> None:
        app = self.app
        if isinstance(app, AppProtocol):
            app.notify_status(message)
