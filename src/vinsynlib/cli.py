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

"""Building the same command line nine times.

:func:`add_common_arguments` puts the family's options on a parser, in the
family's order, with the family's help text and the family's older
spellings still accepted. A tool adds only what its hardware needs.

The reason this is a function and not a paragraph in a README is that the
tools had already drifted nine ways and nobody noticed, because there was
nothing to notice *against*. Now there is.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import (
    PackageNotFoundError,
)
from importlib.metadata import (
    version as _dist_version,
)
from typing import Any

from . import spec
from .config import MAX_DEVICE_ID, MAX_MIDI_CHANNEL, MIDI_CHANNELS

__all__ = [
    "add_common_arguments",
    "channel_of",
    "make_parser",
    "validate_common",
]


def make_parser(
    prog: str,
    description: str,
    *,
    epilog: str = "",
    distribution: str | None = None,
    version: str | None = None,
) -> argparse.ArgumentParser:
    """A parser with the family's conventions already applied.

    Every tool's parser was written from scratch with the same three lines
    in it. The conventions: the program is asked to print its own help on a
    pipe rather than a width chosen by guesswork, and a subcommand is
    required rather than defaulting to something surprising.

    ``--version`` reports the project's own version, found from the
    installed distribution named by ``distribution`` -- which defaults to
    ``prog``, and is right for every tool's terminal front end, where the
    command and the distribution share a name. It is NOT right for the pipe
    front end: the distribution is ``eosed`` and the command is ``eoscli``,
    so those callers name it. Guessing it from the caller's module would
    work and would be the kind of clever this family keeps having to
    unpick.

    ``version`` is for a caller that is not installed as a distribution at
    all: a test, or a run straight from a checkout.

    A tool that cannot be found as a distribution gets no ``--version``
    rather than a bare ``--version`` that prints nothing useful: an option
    that answers "which version?" with a shrug is worse than an option that
    is not there.
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog=epilog or None,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    found: str | None
    if version is not None:
        found = version
    else:
        found = _version_of(distribution or prog)
    if found:
        parser.add_argument(
            "--version", action="version", version=f"%(prog)s {found}"
        )
    return parser


def _version_of(distribution: str) -> str | None:
    """The installed version of ``distribution``, or ``None``.

    By name rather than by importing something: every tool in this family
    installs a distribution named exactly what the command is called, and a
    console script can be run from a virtualenv in which the package is not
    importable yet. ``PackageNotFoundError`` is not an error here -- a
    checkout that was never installed is a normal way to run these.
    """
    try:
        return _dist_version(distribution)
    except PackageNotFoundError:
        return None


def add_common_arguments(
    parser: argparse.ArgumentParser,
    *,
    port: bool = True,
    scan: bool = False,
    recv_port: bool = False,
    channel: bool = True,
    device_channel: bool = False,
    device_id: bool = False,
    exclusive_channel: bool = False,
    demo: bool = True,
    timeout: bool = False,
    catalog: bool = False,
    config: bool = True,
    favorites: bool = False,
    yes: bool = False,
    allow_write: bool = False,
) -> argparse.ArgumentParser:
    """Add the shared options, in the family's order, to ``parser``.

    Each keyword says whether this tool has the concept at all. A tool
    without a channel does not get ``--channel``: a flag that is accepted
    and then ignored is worse than no flag, because it teaches the user
    that a flag can lie.

    Returns the parser, so a caller can chain. Options are added in
    :data:`spec.CANONICAL_FLAGS` order rather than in the order the
    keywords are written, so ``--help`` reads the same in every tool.
    """
    wanted = {
        "port": port,
        "scan": scan,
        "recv-port": recv_port,
        "channel": channel,
        "device-channel": device_channel,
        "device-id": device_id,
        "exclusive-channel": exclusive_channel,
        "demo": demo,
        "timeout": timeout,
        "catalog": catalog,
        "config": config,
        "favorites": favorites,
        "yes": yes,
        "allow-write": allow_write,
    }
    for flag in spec.CANONICAL_FLAGS:
        if not wanted.get(flag.name, False):
            continue
        kwargs: dict[str, Any] = {
            "help": flag.help,
            "dest": flag.name.replace("-", "_"),
        }
        if flag.kind == "flag":
            kwargs["action"] = "store_true"
            kwargs["default"] = False
        elif flag.kind == "int":
            kwargs["type"] = int
            if flag.metavar:
                kwargs["metavar"] = flag.metavar
        elif flag.metavar:
            kwargs["metavar"] = flag.metavar
        parser.add_argument(*flag.options(), **kwargs)
    return parser


def validate_common(
    args: argparse.Namespace,
    *,
    channel_names: Sequence[str] = ("channel", "device_channel"),
) -> None:
    """Check the shared options' values, and refuse a bad one by name.

    Called before anything is opened, so a mistyped channel costs a
    message rather than a wrong program change sent to a real instrument.
    """
    for name in channel_names:
        value = getattr(args, name, None)
        if value is None:
            continue
        if not isinstance(value, int) or not 1 <= value <= MIDI_CHANNELS:
            option = name.replace("_", "-")
            raise SystemExit(f"error: --{option} is 1-{MIDI_CHANNELS}")

    device_id = getattr(args, "device_id", None)
    if device_id is not None and (
        not isinstance(device_id, int) or not 0 <= device_id <= MAX_DEVICE_ID
    ):
        raise SystemExit(f"error: --device-id is 0-{MAX_DEVICE_ID}")

    exclusive = getattr(args, "exclusive_channel", None)
    if exclusive is not None and (
        not isinstance(exclusive, int)
        or not 0 <= exclusive <= MAX_MIDI_CHANNEL
    ):
        raise SystemExit(f"error: --exclusive-channel is 0-{MAX_MIDI_CHANNEL}")


def channel_of(
    args: argparse.Namespace, *, default: int | None = None
) -> int | None:
    """The channel to send on: the option if given, else ``default``.

    Kept as a function because two tools disagreed about whether
    ``--channel`` was 0-based or 1-based, and a 1-based option that is
    passed straight to ``0xC0 |`` is off by one channel with no error
    anywhere.
    """
    value = getattr(args, "channel", None)
    if isinstance(value, int):
        return value - 1
    return default
