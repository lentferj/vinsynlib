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

"""The keys every tool in the family uses, in the order they are shown.

The legend at the bottom of every one of these programs was, until this
module existed, nine hand-written tuples that had drifted apart: one tool
called a key "Multi mode", another called the same key "Channels", a third
had no such key at all, and two of them had learned to build their legend
from their bindings while the rest had not.

Three tiers, and the tiers are the whole design:

**Shared.** The keys in :data:`BROWSER_KEYS` mean the same thing in every
tool that has them. A user who learns ``f`` in one browser has learned it
in all of them. They are in the order the legend shows them, so the legend
reads the same everywhere too.

**Editor.** The keys in :data:`EDITOR_KEYS` are for the two tools that edit
a sampler rather than browse one, where the shared browser keys would be
wrong: there is no favourite to toggle in a tool with no favourites
database. The two agree with each other.

**The tool's own.** Anything else a tool binds is its own business, on one
condition: it must not take a key another meaning already holds *within the
same tool*. ``i`` is "Device" in a browser and "Integrity" in an editor,
and that is not a conflict, because no tool is both. ``s`` is "Scan bank"
in rxved and "SCSI" in s3ked, and that is fine too. A browser that wanted
``s`` for "Save" would not be.

Two keys are the reason this file exists:

``m`` meant "Multi mode" in kwsed, "Channels" in p2ked, "Multi-mode setup"
in rxved, "Master" in s3ked and "Master" in eosed. In a browser it now
means **channels** -- and kwsed's Multisets *are* channel assignments, so
the change is a clarification rather than a loss. In an editor it means the
**master menu**, where the destructive operations live.

``r`` meant "Read names" in seven tools and "Refresh" in two. Both are
honest, so the shared concept is **re-read from the device** and the
legend says which of the two this tool is doing.

Movement is not in the tables: ``↑↓`` is Textual's own table navigation and
every tool's legend already opens with the same two words for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "BROWSER_KEYS",
    "CANONICAL_LEGEND",
    "EDITOR_KEYS",
    "FAVOURITE_KEYS",
    "LEGEND_SEPARATOR",
    "Key",
    "key_for",
    "legend",
    "legend_from_bindings",
    "wrap_blocks",
]

#: What the legend puts between two hints.
LEGEND_SEPARATOR = " · "


@dataclass(frozen=True)
class Key:
    """One key, what it does, and how the legend spells it.

    ``key`` is a Textual binding name -- ``"slash"``, ``"question_mark"``,
    ``"left_square_bracket"`` -- because that is what ``BINDINGS`` needs.
    ``press`` is what the user types, for the legend and for help text,
    because ``"/"`` and ``"slash"`` are the same key and only one of them
    looks like it to somebody reading.
    """

    key: str
    action: str
    legend: str
    press: str


def _k(key: str, action: str, legend: str, press: str = "") -> Key:
    return Key(key, action, legend, press or key)


#: Shared browser keys, in legend order. ``[ ] channel`` covers two keys,
#: so the pair appears once in the legend and twice in this table.
BROWSER_KEYS: tuple[Key, ...] = (
    _k("tab", "switch_pane", "tab pane"),
    _k("enter", "select_slot", "⏎ select on the unit", "enter"),
    _k("r", "read_names", "r read names"),
    _k("slash", "search", "/ search", "/"),
    _k("left_square_bracket", "channel_down", "[ ] channel", "["),
    _k("right_square_bracket", "channel_up", "[ ] channel", "]"),
    _k("c", "pick_channel", "c set channel"),
    _k("f", "toggle_favorite", "f favourite"),
    _k("i", "device_info", "i device"),
    _k("question_mark", "help", "? help", "?"),
    _k("q", "quit", "q quit"),
)

#: A tool with a favourites store has these as well. Kept apart because a
#: tool may have the store without an annotations screen, and the legend
#: must not then promise one.
FAVOURITE_KEYS: tuple[Key, ...] = (
    _k("F", "cycle_favorites", "F favourites view"),
    _k("t", "edit_tags", "t tags"),
    _k("n", "edit_note", "n note"),
)

#: Shared editor keys, in legend order.
EDITOR_KEYS: tuple[Key, ...] = (
    _k("r", "refresh", "r refresh"),
    _k("w", "toggle_write", "w write gate"),
    _k("z", "undo", "z undo"),
    _k("Z", "undo_all", "Z undo all"),
    _k("h", "history", "h history"),
    _k("m", "master", "m master menu"),
    _k("question_mark", "help", "? help", "?"),
    _k("q", "quit", "q quit"),
)

#: The shared browser legend, in the order every tool shows it. The first
#: block is written into every legend by hand: it is movement, which belongs
#: to Textual's table rather than to a binding.
CANONICAL_LEGEND: tuple[str, ...] = (
    "↑↓ move",
    "tab pane",
    "⏎ select on the unit",
    "r read names",
    "/ search",
    "[ ] channel",
    "c set channel",
    "f favourite",
    "F favourites view",
    "t tags",
    "n note",
    "i device",
    "? help",
    "q quit",
)

#: The blocks a tool without a favourites store drops rather than advertise.
FAVOURITE_BLOCKS: frozenset[str] = frozenset(
    {"f favourite", "F favourites view", "t tags", "n note"}
)

#: The blocks a tool that does not send on a MIDI channel drops.
CHANNEL_BLOCKS: frozenset[str] = frozenset(
    {"[ ] channel", "c set channel", "⏎ select on the unit"}
)


def key_for(action: str, *, tier: str = "browser") -> Key | None:
    """The shared key bound to an action, if this tier has one.

    ``tier`` is ``"browser"`` or ``"editor"``. A ``None`` return is normal
    for an action the tier does not have -- the point is that a tool
    without favourites does not pretend to have them.
    """
    table = EDITOR_KEYS if tier == "editor" else BROWSER_KEYS + FAVOURITE_KEYS
    for key in table:
        if key.action == action:
            return key
    return None


def legend(
    extras: Sequence[str] = (),
    *,
    favourites: bool = True,
    channel: bool = True,
    select: bool = True,
) -> tuple[str, ...]:
    """The legend blocks: the shared ones, plus this tool's own.

    ``extras`` go in the one place the shared legend leaves room for them
    -- after ``n note`` and before ``i device`` -- so that a reader's eye
    lands on them in the same place in all nine programs.

    The three keyword flags drop shared blocks a tool has no concept for.
    A tool that does not send on a channel must not show ``[ ] channel``,
    and one with no favourites store must not show ``f favourite``: a
    legend is a promise about which keys work.
    """
    drop: set[str] = set()
    if not favourites:
        drop |= FAVOURITE_BLOCKS
    if not channel:
        drop |= CHANNEL_BLOCKS
    if not select:
        drop.add("⏎ select on the unit")
    blocks = [b for b in CANONICAL_LEGEND if b not in drop]
    anchor = "i device" if "i device" in blocks else "? help"
    index = blocks.index(anchor) if anchor in blocks else len(blocks)
    return tuple(blocks[:index] + list(extras) + blocks[index:])


def wrap_blocks(
    blocks: Sequence[str], width: int, sep: str = LEGEND_SEPARATOR
) -> str:
    """Pack hints into lines no wider than ``width``.

    Breaks happen only *between* blocks, so a hint is never split
    mid-label; a block wider than ``width`` takes its own line rather than
    being cut. The point is that the legend wraps instead of truncating --
    a footer that silently drops its last keys teaches the user those keys
    do not exist.

    Ported from rxved, which ports it from s3ked. The width is clamped
    rather than trusted: a width of zero or less would make every candidate
    "too wide" and never break, so the legend came out as one very long
    line -- the degenerate version of exactly the truncation this function
    exists to avoid.
    """
    width = max(width, 1)
    lines: list[str] = []
    current = ""
    for block in blocks:
        candidate = block if not current else current + sep + block
        if len(candidate) > width and current:
            lines.append(current)
            current = block
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def legend_from_bindings(
    bindings: Sequence[object],
    *,
    press_names: dict[str, str] | None = None,
) -> list[str]:
    """Build legend blocks from a class's ``BINDINGS``.

    Two of the family already do this and were right to: a legend written
    by hand is a second list to keep in step, and it drifts. The ones that
    still hand-write theirs are converted by this.
    """
    blocks: list[str] = []
    names = press_names or {}
    for binding in bindings:
        key = getattr(binding, "key", None)
        description = getattr(binding, "description", None)
        show = getattr(binding, "show", True)
        if not key or not description or not show:
            continue
        blocks.append(f"{names.get(key, key)} {description}")
    return blocks
