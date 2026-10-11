# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Names read off the unit, kept between runs.

A writable bank is the user's own work, and its printed list is
guaranteed to be wrong about it -- the catalog says what the
factory shipped, and a bank that has been saved into says
something else entirely. So for writable banks the hardware is
the only authority, and reading it is the only way to be right.

The problem is what happens next: those names live in
``Catalog._live``, which is a plain dict in a process that exits.
Every restart falls back to the printed list, so the browser
confidently shows the factory bank for a machine full of the
user's own patches, and re-reading fixes the screen for exactly
as long as the session lasts. Names that are expensive to get
and true today should not evaporate overnight.

So they are written here, in a per-project sidecar file, and
read back at startup -- which means the browser shows the right
names *immediately*, before anything has talked to the unit, and
the hardware read that follows only confirms them.

Deliberately not in the catalog file. That file is generated
from the manufacturer's own documentation, the
printed-versus-live distinction is the whole point of having two
name sources, and a cache of one instrument's current contents
does not belong in a document describing what the manual says.
Overwriting one with the other would destroy the disagreement
the marker exists to show. Each project keeps its own file --
and its own categories -- beside its own catalog.

Format is ``{"USER:001": "..."}``, flat and keyed the same way
:class:`vinsynlib.catalog.Catalog` keys its live layer. A
missing file is normal and means nothing has been read yet; a
corrupt one is worth a warning rather than an exception, because
names are a convenience and refusing to open the browser over
one would be the wrong trade.
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING

from vinsynlib.catalog import make_key, split_key

if TYPE_CHECKING:
    from vinsynlib.catalog import Catalog

__all__ = ["FILE_NAME", "apply_to", "key", "load", "save"]

#: The filename, beside the project's own catalog file.
FILE_NAME = "live-names.json"


def key(bank_id: str, number: int, kind: str = "") -> str:
    """The storage key for one slot. Same shape ``Catalog`` uses."""
    return make_key(bank_id, number, kind)


def load(path: str) -> dict[str, str]:
    """Previously-read names, keyed ``"BANK:NNN"``. Empty if none."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        # Not worth refusing to start over. The alternative is a
        # browser that will not open because a cache it can rebuild
        # -- the unit is right there -- is malformed.
        print(
            f"vinsynlib: ignoring {path}: {exc}. It is a cache of "
            "names read from the unit; delete it and read them again.",
            file=sys.stderr,
        )
        return {}
    if not isinstance(raw, dict):
        return {}
    # Keep only what the rest of the program can use: a str key and
    # a str value. Anything else came from a hand-edit or a future
    # version.
    return {
        stored: name
        for stored, name in raw.items()
        if isinstance(stored, str) and isinstance(name, str)
    }


def apply_to(catalog: Catalog, path: str) -> int:
    """Lay the stored names over ``catalog``. Returns how many applied.

    Needed before anything draws, and the parsing is the part worth
    sharing: a key that does not parse is skipped rather than
    guessed at, because a name attached to the wrong slot is worse
    than a missing one -- it is a plausible wrong answer.
    """
    applied = 0
    for stored, name in load(path).items():
        try:
            bank_id, kind, number = split_key(stored)
        except ValueError:
            continue
        catalog.set_live_name(bank_id, number, name, kind)
        applied += 1
    return applied


def save(path: str, names: dict[str, str]) -> None:
    """Write the live layer out. Best effort -- a cache is not required.

    Read-modify-write rather than replace, so a file that also
    holds something else keeps it. Losing the whole file because
    one bank could not be read would be a poor way to lose one
    bank's names.
    """
    merged = load(path)
    merged.update(names)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # Write-then-rename: a crash or a full disk mid-write leaves
        # the previous file intact rather than a half-written one,
        # which json would then refuse to parse.
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(
                merged,
                handle,
                indent=1,
                sort_keys=True,
                ensure_ascii=False,
            )
            handle.write("\n")
        os.replace(temp, path)
    except OSError:
        # Same reasoning as above: the names are still on screen,
        # they just will not survive a restart.
        pass
