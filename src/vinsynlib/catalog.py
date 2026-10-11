# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Printed names, plus whatever has been read off the unit.

Two sources, kept apart all the way to the screen:

* **Printed** names, from each project's generated catalog file --
  built from the manufacturer's own documentation, which is why the
  file itself is generated locally and never shipped here.
* **Live** names, read from a unit over MIDI and cached between
  runs by :mod:`vinsynlib.livenames`.

A single mapping cannot keep them distinguishable, and the
distinction is the useful part: after anything has been saved into
a writable bank, the printed list describes what the machine
shipped with, not what is in it now. So :class:`Catalog` keeps the
two apart -- :meth:`Catalog.name` reports the printed name,
:meth:`Catalog.live_name` the one read from hardware, and
:meth:`Catalog.display_name` prefers live when there is one.

Keys are **display** numbers: what the unit shows, not the wire
byte. On many instruments the first patch of a bank is number 1
and program change 0. A catalog keyed on the wire byte would make
every screen do the arithmetic; instead the wire-keyed form
converts at the edge -- :func:`wire_to_display` on the way in,
:func:`display_to_wire` on the way out, and :func:`load` accepting
``"pc"`` rows for files that were generated wire-keyed.

A key is ``bank_id[:kind]:number``. Most banks hold one kind of
thing and the kind defaults to ``""``, so the key reads
``"BANK:001"``; a bank that holds two kinds under one id (patches
*and* performances, say) names the kind and reads
``"BANK:KIND:001"``. Kind matching is always whole-word: a filter
for ``"PATCH"`` never matches ``"PATCHED"``, which is how two
kinds once quietly merged under an abbreviated bank id.

Only the layer moves. The generated JSON, the categories, the
bank table and every manufacturer byte stay in each project;
kinds and names are caller-supplied throughout.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "UNNAMED",
    "Catalog",
    "Entry",
    "display_to_wire",
    "dump",
    "empty",
    "load",
    "make_key",
    "split_key",
    "wire_to_display",
]

#: What a slot is called when nothing knows its name. Not an empty
#: string: an empty cell in a browser reads as a rendering fault,
#: and this reads as a missing catalog, which is what it is.
UNNAMED = "--"


def wire_to_display(wire: int, *, offset: int = 1) -> int:
    """The display number for a wire (zero-based) slot number.

    ``offset`` is how far the two count apart on this instrument:
    program change 0 is display number 1 almost everywhere, hence
    the default. Anything instrument-specific -- a base other than
    one -- is the caller's to pass, not the library's to know.
    """
    return int(wire) + int(offset)


def display_to_wire(display: int, *, offset: int = 1) -> int:
    """The inverse of :func:`wire_to_display`, same ``offset``."""
    return int(display) - int(offset)


def make_key(bank_id: str, number: int, kind: str = "") -> str:
    """The storage key for one slot: ``BANK:NNN`` or ``BANK:KIND:NNN``.

    ``number`` is the display number. ``kind`` defaults to ``""``
    for the common single-kind bank.
    """
    if kind:
        return f"{bank_id}:{kind}:{int(number):03d}"
    return f"{bank_id}:{int(number):03d}"


def split_key(key: str) -> tuple[str, str, int]:
    """``(bank_id, kind, number)`` for a :func:`make_key` key.

    ``kind`` is ``""`` when the key carries none. Raises
    :exc:`ValueError` for anything with other than two or three
    colon-separated parts or a non-numeric number -- a name
    attached to the wrong slot is worse than a missing one, so a
    key that does not parse is never guessed at.
    """
    parts = key.split(":")
    match parts:
        case [bank_id, number_text]:
            return bank_id, "", int(number_text)
        case [bank_id, kind, number_text]:
            return bank_id, kind, int(number_text)
    raise ValueError(f"bad catalog key {key!r}")


@dataclass(frozen=True)
class Entry:
    """One named slot, as printed. ``number`` is the display number."""

    bank_id: str
    number: int
    name: str
    kind: str = ""

    def __post_init__(self) -> None:
        if ":" in self.bank_id:
            raise ValueError(f"bank id {self.bank_id!r} holds ':'")
        if ":" in self.kind:
            raise ValueError(f"kind {self.kind!r} holds ':'")

    @property
    def key(self) -> str:
        """``BANK:NNN`` -- or ``BANK:KIND:NNN`` when kinded."""
        return make_key(self.bank_id, self.number, self.kind)


class Catalog:
    """Printed names, plus whatever has been read from a unit.

    Deliberately not a plain dict: the two name sources have to
    stay distinguishable all the way to the screen, and a single
    mapping cannot do that.
    """

    def __init__(
        self,
        entries: Iterable[Entry] = (),
        *,
        source: str = "",
        generated: str = "",
    ) -> None:
        self._entries: dict[str, Entry] = {}
        for entry in entries:
            self._entries[entry.key] = entry
        self._live: dict[str, str] = {}
        #: Where these names came from, for the UI to cite.
        self.source = source
        self.generated = generated

    # --- printed names --------------------------------------------------

    def entry(self, bank_id: str, number: int, kind: str = "") -> Entry | None:
        """The printed entry for this slot, if the catalog has it."""
        return self._entries.get(make_key(bank_id, number, kind))

    def name(self, bank_id: str, number: int, kind: str = "") -> str | None:
        """The printed name for this slot, if the catalog has it."""
        found = self.entry(bank_id, number, kind)
        return found.name if found is not None else None

    def has(self, bank_id: str, *, kind: str | None = None) -> bool:
        """Whether any slot in this bank is named.

        With ``kind`` given, only slots of exactly that kind count
        -- whole-word, never substring: ``"PATCH"`` does not match
        ``"PATCHED"``.
        """
        for stored in self._entries:
            found_bank, found_kind, _ = split_key(stored)
            if found_bank == bank_id and (kind is None or found_kind == kind):
                return True
        return False

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    # --- names read from the hardware -----------------------------------

    def set_live_name(
        self, bank_id: str, number: int, name: str, kind: str = ""
    ) -> None:
        """Record a name read from the device for this slot."""
        self._live[make_key(bank_id, number, kind)] = name

    def live_name(
        self, bank_id: str, number: int, kind: str = ""
    ) -> str | None:
        """The hardware-read name for this slot, if one was read."""
        return self._live.get(make_key(bank_id, number, kind))

    def is_live(self, bank_id: str, number: int, kind: str = "") -> bool:
        """Whether :meth:`display_name` reports a hardware read here."""
        return make_key(bank_id, number, kind) in self._live

    # --- what the browser shows -----------------------------------------

    def display_name(self, bank_id: str, number: int, kind: str = "") -> str:
        """The best name available, hardware winning over print."""
        return (
            self.live_name(bank_id, number, kind)
            or self.name(bank_id, number, kind)
            or UNNAMED
        )

    def differs(self, bank_id: str, number: int, kind: str = "") -> bool:
        """Whether hardware and print disagree about this slot.

        Both sources must speak: no live read, or no printed name,
        is not a disagreement. What a disagreement *means* -- saved
        work in a writable bank, a wrong printed list in a ROM one,
        or nothing at all against a placeholder list -- is the
        caller's to decide; this only reports that the two differ.
        """
        live = self.live_name(bank_id, number, kind)
        if live is None:
            return False
        printed = self.name(bank_id, number, kind)
        return printed is not None and printed != live

    # --- searching ------------------------------------------------------

    def search(
        self, needle: str, *, kind: str | None = None
    ) -> list[tuple[str, str, int, str]]:
        """``(bank_id, kind, number, name)`` for slots matching ``needle``.

        Case-insensitive substring, over both printed and live
        names, so a slot renamed on the machine is findable under
        its new name without a catalog rebuild. The shown name is
        the display one -- live winning over print. With ``kind``
        given, only slots of exactly that kind match.
        """
        wanted = needle.strip().lower()
        if not wanted:
            return []
        out: list[tuple[str, str, int, str]] = []
        for stored in set(self._entries) | set(self._live):
            found_bank, found_kind, found_number = split_key(stored)
            if kind is not None and found_kind != kind:
                continue
            printed = (
                self._entries[stored].name if stored in self._entries else ""
            )
            live = self._live.get(stored)
            if wanted in printed.lower() or (
                live is not None and wanted in live.lower()
            ):
                out.append(
                    (
                        found_bank,
                        found_kind,
                        found_number,
                        self.display_name(
                            found_bank, found_number, found_kind
                        ),
                    )
                )
        out.sort(key=lambda row: (row[0], row[1], row[2]))
        return out


def empty() -> Catalog:
    """A catalog that knows no names. What you get with no data file."""
    return Catalog()


def _parse_row(bank_id: str, row: Any) -> Entry:
    """One generated-file row as an :class:`Entry`.

    Raises :exc:`KeyError`, :exc:`TypeError` or :exc:`ValueError`
    for anything unreadable; the caller counts and skips those.
    """
    if not isinstance(row, dict):
        raise TypeError("row is not a dict")
    name = row["name"]
    if not isinstance(name, str):
        raise TypeError("name is not a string")
    row_kind = row.get("kind", "")
    if not isinstance(row_kind, str):
        raise TypeError("kind is not a string")
    if "n" in row:
        number = int(row["n"])
    elif "pc" in row:
        number = wire_to_display(int(row["pc"]))
    else:
        raise KeyError("row has neither 'n' nor 'pc'")
    return Entry(bank_id=bank_id, number=number, name=name, kind=row_kind)


def load(path: str | None = None) -> Catalog:
    """Read a generated catalog file, or return an empty one.

    A missing file is not an error: a browser is useful without
    names -- banks and numbers are computed, not looked up -- and
    the file is deliberately not shipped. A file that exists but
    is not a catalog raises, because silently browsing unnamed
    slots would be a poor way to find out the extractor broke.

    One bad row costs one row, not the file: each row is parsed on
    its own and the unreadable ones are counted to stderr. Rows
    carry the display number in ``"n"``; rows carrying a wire
    number in ``"pc"`` convert at the edge. ``"kind"`` defaults to
    ``""``. Anything else a row carries -- categories, voices --
    stays project-side and is ignored here.
    """
    if path is None or not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as handle:
        payload: Any = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a catalog")
    entries: list[Entry] = []
    skipped = 0
    banks: Any = payload.get("banks", {})
    if not isinstance(banks, dict):
        raise ValueError(f"{path} is not a catalog")
    for bank_id, rows in banks.items():
        if not isinstance(rows, list):
            skipped += 1
            continue
        for row in rows:
            try:
                entries.append(_parse_row(bank_id, row))
            except (KeyError, TypeError, ValueError):
                skipped += 1
    if skipped:
        print(
            f"warning: {path} has {skipped} unreadable row(s), "
            "skipped; regenerate it with tools/extract_catalog.py",
            file=sys.stderr,
        )
    source = payload.get("source", "")
    generated = payload.get("generated", "")
    return Catalog(
        entries,
        source=source if isinstance(source, str) else "",
        generated=generated if isinstance(generated, str) else "",
    )


def dump(
    catalog: Catalog,
    path: str,
    *,
    source: str = "",
    generated: str = "",
    note: str = "",
) -> None:
    """Write a catalog back out in the format :func:`load` reads."""
    by_bank: dict[str, list[dict[str, Any]]] = {}
    for entry in catalog._entries.values():
        row: dict[str, Any] = {"n": entry.number, "name": entry.name}
        if entry.kind:
            row["kind"] = entry.kind
        by_bank.setdefault(entry.bank_id, []).append(row)
    for rows in by_bank.values():
        rows.sort(key=lambda row: int(row["n"]))
    payload: dict[str, Any] = {
        "source": source or catalog.source,
        "generated": generated or catalog.generated,
    }
    if note:
        payload["note"] = note
    payload["banks"] = by_bank
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
