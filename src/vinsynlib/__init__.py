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

"""The shared base of the ROMpler instrument browsers.

Nine sibling programs -- emorphed, ensqsqed, eosed, kwsed, nanosyned,
p2ked, rxved, s3ked and x5ded -- grew nine copies of the same handful of
modules: a settings cache, a favourites database, MIDI port discovery, a
wrapped key legend, an error format and a set of command-line conventions.
Each copy then drifted. This library is the common version of that code,
kept in step across the family rather than copied nine times.

What belongs here is what is *not* the manufacturer's: how a preference is
remembered, where a favourite lives, what an error says, which key means
what. What stays in each project is what the hardware owns: the wire
format, the bank table, the meaning of a byte.

The three documents worth reading first:

``docs/UX-SPEC.md``
    The contract itself -- terminology, command line, keys, exit codes --
    in prose, with the reasoning behind the parts that are not obvious.

:mod:`vinsynlib.spec`
    The same contract as data: every flag, its help text and its older
    spellings; every command; the exit codes.

:mod:`vinsynlib.conformance`
    The checks a project runs against its own front end to stay in step.
"""

from __future__ import annotations

__all__ = [
    "cli",
    "config",
    "conformance",
    "devchecks",
    "favorites",
    "is_compatible_version",
    "keys",
    "midi",
    "spec",
    "terms",
]

__version__ = "0.3.1"


def _release_parts(version_string: str, width: int) -> tuple[int, ...] | None:
    """The leading numeric components of a version, or ``None``.

    A component must begin with a digit; anything after the digits is a
    pre-release or build marker and is ignored, so ``"0.2rc1"`` and
    ``"1.0.0+local"`` compare as ``0.2`` and ``1.0.0``. A component that
    does not begin with a digit at all (``"0.1.x"``, ``"not-a-version"``)
    makes the whole string unusable rather than being guessed at, which is
    the one case a version check must not get wrong.
    """
    parts: list[int] = []
    for piece in version_string.split(".")[:width]:
        digits = ""
        for char in piece:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            return None
        parts.append(int(digits))
    if not parts:
        return None
    return tuple(parts + [0] * (width - len(parts)))


def is_compatible_version(
    version_string: str, minimum: tuple[int, ...]
) -> bool:
    """Return True if version_string meets or exceeds minimum version tuple.

    Handles version strings with fewer than 3 components by treating missing
    components as 0 for comparison purposes, and ignores a pre-release or
    build suffix on a component.

    For example, with minimum=(0, 1, 0):
      - "0.1" -> (0, 1, 0) -> True (equal)
      - "0.1.0" -> (0, 1, 0) -> True (equal)
      - "0.2rc1" -> (0, 2, 0) -> True (greater than)
      - "0.0.9" -> (0, 0, 9) -> False (less than)
      - "1" -> (1, 0, 0) -> True (greater than)
      - "0.1.x"/"not-a-version"/None -> False (not a version)
    """
    if not isinstance(version_string, str):
        return False
    current = _release_parts(version_string, len(minimum))
    return current is not None and current >= minimum
