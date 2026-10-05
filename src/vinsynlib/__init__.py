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
    "keys",
    "midi",
    "spec",
    "terms",
]

__version__ = "0.1.0"
