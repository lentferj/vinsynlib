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

"""The command line every tool in the family presents, as data.

A tool's ``--help`` is its front door, and nine separately written front
doors had drifted into nine different shapes: some documented their flags
and some did not, one tool called the channel it sends on ``--channel`` and
another called the unit's own base channel ``--midi-channel`` *in the same
program*, ``--scan`` existed in two tools out of nine, and one tool's
``config`` subcommand meant "which ROMs are fitted" while the ``--config``
flag next to it meant "the settings file".

This module is the contract. :data:`CANONICAL_FLAGS` is what a flag is
called and what its help says, :data:`SUBCOMMANDS` is what a command is
called and which older names still work, and the exit codes are the three
every tool has always used, named.

A tool adds what its hardware needs and nothing else. Where this family
previously had a flag that meant nothing but "I did not know what to call
it", the flag is now either named here or gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CANONICAL_FLAGS",
    "EXIT_ERROR",
    "EXIT_OK",
    "EXIT_USAGE",
    "SUBCOMMANDS",
    "Flag",
    "Subcommand",
    "flag_help",
    "flag_names",
    "subcommand_names",
]

#: It worked.
EXIT_OK = 0

#: It did not work: no unit answered, it refused, the file was unreadable,
#: the answer was declined. Always printed as ``error: <what>`` on stderr.
EXIT_ERROR = 1

#: The command line itself was wrong. argparse's own code, and the only
#: one this family ever used for anything else.
EXIT_USAGE = 2


@dataclass(frozen=True)
class Flag:
    """One option, as the family presents it."""

    #: The canonical spelling, without dashes: ``"port"``.
    name: str
    help: str
    #: Older spellings that still work, without dashes. Kept so that a
    #: command line written against last year's tool keeps working.
    aliases: tuple[str, ...] = ()
    #: ``"str"``, ``"int"`` or ``"flag"`` -- ``"flag"`` takes no value.
    kind: str = "str"
    #: What argparse should print after the option.
    metavar: str = ""
    #: Only for editors: the option that arms a destructive path.
    editor_only: bool = False

    @property
    def option(self) -> str:
        """The canonical spelling, with dashes."""
        return f"--{self.name}"

    def options(self) -> tuple[str, ...]:
        """Every spelling argparse should accept, canonical first."""
        return (self.option, *(f"--{a}" for a in self.aliases))


def _f(  # noqa: PLR0913
    name: str,
    kind: str,
    help: str,
    *,
    aliases: tuple[str, ...] = (),
    metavar: str = "",
    editor_only: bool = False,
) -> Flag:
    return Flag(name, help, aliases, kind, metavar, editor_only)


#: Every option the family knows, in the order ``--help`` shows them.
CANONICAL_FLAGS: tuple[Flag, ...] = (
    _f(
        "port",
        "str",
        "MIDI port name (default: the one remembered in config.toml)",
        metavar="PORT",
    ),
    _f(
        "scan",
        "flag",
        "probe every MIDI port again, instead of trusting the remembered "
        "one, and update config.toml",
    ),
    _f(
        "recv-port",
        "str",
        "MIDI input port, if it differs from --port",
        metavar="PORT",
    ),
    _f(
        "channel",
        "int",
        "channel to send on, 1-16 (default: remembered, or 1)",
        metavar="N",
    ),
    _f(
        "device-channel",
        "int",
        "the unit's own base channel, 1-16, where the hardware has one",
        aliases=("midi-channel",),
        metavar="N",
    ),
    _f(
        "device-id",
        "int",
        "the unit's SysEx device ID, where the hardware has one",
        metavar="N",
    ),
    _f(
        "exclusive-channel",
        "int",
        "the unit's SysEx exclusive channel, where the hardware has one",
        metavar="N",
    ),
    _f("demo", "flag", "the built-in demo device; opens no MIDI ports"),
    _f(
        "timeout",
        "int",
        "seconds to wait for a reply",
        metavar="SECONDS",
    ),
    _f(
        "catalog",
        "str",
        "generated name catalog (default: beside the package)",
        metavar="PATH",
    ),
    _f(
        "config",
        "str",
        "settings cache (default: ./config.toml; safe to delete)",
        metavar="PATH",
    ),
    _f(
        "favorites",
        "str",
        "favourites database (default: the per-platform data directory)",
        metavar="PATH",
    ),
    _f(
        "yes",
        "flag",
        "do not ask before something that changes the unit",
    ),
    _f(
        "allow-write",
        "flag",
        "start with the write gate armed (default: locked)",
        editor_only=True,
    ),
)


@dataclass(frozen=True)
class Subcommand:
    """One command: the canonical name, and what it used to be called."""

    name: str
    help: str
    aliases: tuple[str, ...] = ()
    #: ``"browser"``, ``"editor"`` or ``"both"``. Documentation, so that
    #: the family can be read at a glance; nothing enforces it.
    tier: str = "browser"
    #: What the command needs: ``"nothing"``, ``"names"`` (a catalog) or
    #: ``"device"``.
    needs: str = "device"
    #: True when it changes the unit, and so must not run unconfirmed.
    writes: bool = False
    #: The argparse group this command belongs to, if any.
    group: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def _s(  # noqa: PLR0913
    name: str,
    help: str,
    *,
    aliases: tuple[str, ...] = (),
    tier: str = "browser",
    needs: str = "device",
    writes: bool = False,
    group: str = "",
) -> Subcommand:
    return Subcommand(name, help, aliases, tier, needs, writes, group)


#: The commands the family knows. A tool uses the ones its hardware has,
#: and adds its own beside them; where a tool's existing name differs from
#: the canonical one it keeps its name as an alias, so nothing that worked
#: last month stops working tonight.
SUBCOMMANDS: tuple[Subcommand, ...] = (
    _s("ports", "MIDI ports on this host", needs="nothing"),
    _s("status", "ask the unit who it is"),
    _s(
        "banks",
        "the bank table (no unit needed)",
        aliases=("groups", "regions", "roms"),
        needs="nothing",
    ),
    _s("list", "one bank's slots (no unit needed)", needs="nothing"),
    _s(
        "find",
        "search names (no unit needed)",
        aliases=("search",),
        needs="nothing",
    ),
    _s(
        "fav",
        "the favourites database",
        aliases=("favorites",),
        needs="nothing",
    ),
    _s("tags", "tags in use, with counts", needs="nothing"),
    _s("names", "read a bank's names off the unit (silent)"),
    _s("current", "what the unit is playing (silent)"),
    _s(
        "select",
        "select a slot ON THE UNIT",
        aliases=("reach",),
    ),
    _s(
        "read",
        "read a dump file (no hardware)",
        aliases=("syx",),
        needs="nothing",
    ),
    _s("dump", "dump a bank or preset off the unit (silent)"),
    _s("send", "WRITE a dump into the unit", writes=True),
    _s(
        "hardware",
        "what the unit reports about itself (no unit needed)",
        aliases=("config", "inquire"),
        needs="nothing",
    ),
    _s("channels", "every MIDI channel, and what it selects"),
    _s("multi", "multi-mode setup, and why a channel is silent"),
    _s("mixes", "the unit's mix slots (silent)"),
    _s(
        "resolve",
        "what does this MSB/LSB/PC select? (no unit needed)",
        needs="nothing",
    ),
    _s(
        "params",
        "the parameter table (no unit needed)",
        tier="editor",
        needs="nothing",
    ),
    _s("programs", "resident program names", tier="editor"),
    _s("samples", "resident sample names", tier="editor"),
    _s("audit", "what plays silence, and why", tier="editor"),
    _s("header", "one whole header, decoded", tier="editor"),
    _s("get", "read one parameter", tier="editor"),
    _s("set", "WRITE one parameter", tier="editor", writes=True),
    _s("memory", "memory totals and free space", tier="editor"),
    _s("catalog", "the unit's names, read over MIDI", tier="editor"),
)

#: Commands that touch the unit without writing to it. Every tool declares
#: its own; this is the union, for the family documentation.
SILENT_SUFFIX = " (silent)"


def flag_names(*, tier: str = "browser") -> tuple[str, ...]:
    """The canonical option names, for one tier."""
    return tuple(
        f.name for f in CANONICAL_FLAGS if tier != "editor" or f.editor_only
    )


def flag_help(name: str) -> str:
    """The help text for one option, by canonical name.

    Raises :class:`KeyError` for a name the family does not have, which is
    the point: a tool that wants a tenth flag adds it here, in the open,
    rather than inventing one in its own ``build_parser``.
    """
    for flag in CANONICAL_FLAGS:
        if flag.name == name or name in flag.aliases:
            return flag.help
    raise KeyError(
        f"no flag {name!r} in the family; have "
        f"{', '.join(sorted(flag_names()))}"
    )


def subcommand_names(*, tier: str = "both") -> tuple[str, ...]:
    """The canonical command names, for one tier."""
    return tuple(s.name for s in SUBCOMMANDS if tier in ("both", s.tier))


def aliases_for(name: str) -> tuple[str, ...]:
    """The older spellings of one command."""
    for sub in SUBCOMMANDS:
        if sub.name == name:
            return sub.aliases
    raise KeyError(f"no subcommand {name!r} in the family")
