# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
#
# This file is part of vinsynlib.
#
# Assembled from the port-listing and shutdown handling that every browser
# in the family carried its own copy of:
#   Copyright (C) 2026  emorphed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  ensqsqed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  kwsed contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  nanosyned contributors       - GPL-2.0-or-later
#   Copyright (C) 2026  p2ked contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  rxved contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  s3ked contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  x5ded contributors           - GPL-2.0-or-later
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

"""Finding MIDI ports, and shutting down without leaving one open.

The transport-independent half of what every bridge in the family does.
What a *device* answers is none of this module's business -- that is the
hardware-specific layer, and it stays in the project.

Two things here are shared because getting them wrong is expensive and
invisible:

**Both clients are closed before returning.** rtmidi leaks its backend
handle if they are not, which on ALSA shows up later as ports that cannot
be reopened -- a fault inherited, and fixed, in the sibling projects, and
one nobody can diagnose from the symptom.

**SIGTERM closes the ports too.** Ctrl-C already unwinds: it raises
``KeyboardInterrupt`` and every ``finally`` that closes the bridge runs.
SIGTERM does not -- its default action ends the process where it stands,
leaving the MIDI port open, which on ALSA is then unavailable to the next
program until the session is logged out.
"""

from __future__ import annotations

import signal
import sys
from collections.abc import Callable, Sequence
from typing import Any, NoReturn, TypeVar

__all__ = [
    "DeviceError",
    "DeviceNotFound",
    "DeviceRefused",
    "MidiUnavailable",
    "bidirectional_ports",
    "fail",
    "install_clean_exit",
    "likely_ports",
    "list_ports",
    "open_remembered_or_swept",
    "render_ports",
]


class MidiUnavailable(RuntimeError):
    """python-rtmidi is not installed, or cannot see any backend.

    Raised rather than reported, so the caller decides what a program that
    cannot open a port can still do: several of these tools read dump files
    perfectly well without one, and say so.
    """


class DeviceError(RuntimeError):
    """The unit did not answer, or answered something unusable."""


class DeviceNotFound(DeviceError):
    """No port on this host answered as the instrument being looked for.

    Its own class because the remedy differs from every other
    :class:`DeviceError`: this one is fixed by connecting the thing or
    naming the right port, not by retrying.
    """


class DeviceRefused(DeviceError):
    """The unit answered, and the answer was no.

    Worth distinguishing from silence. A refusal is information -- a busy
    unit, a mode it will not answer in, a device ID it does not serve --
    where a timeout only says nothing arrived.
    """


def _rtmidi() -> Any:
    """The rtmidi module, or a clear complaint that it is not there.

    Imported lazily and never at module scope: an offline command such as
    reading a dump file must work on a machine with no MIDI stack at all,
    which is exactly what ``deptry``'s "no unused import" rule and this
    function between them arrange.
    """
    try:
        import rtmidi
    except ImportError as exc:  # pragma: no cover - depends on the host
        raise MidiUnavailable(
            "python-rtmidi is not installed, so no MIDI port can be opened."
        ) from exc
    return rtmidi


def list_ports() -> tuple[list[str], list[str]]:
    """``(inputs, outputs)`` as rtmidi names them, both clients closed."""
    rtmidi = _rtmidi()
    midi_in, midi_out = rtmidi.MidiIn(), rtmidi.MidiOut()
    try:
        return list(midi_in.get_ports()), list(midi_out.get_ports())
    finally:
        midi_in.delete()
        midi_out.delete()


def bidirectional_ports(
    ports: tuple[list[str], list[str]] | None = None,
) -> list[str]:
    """Ports that exist as both an input and an output.

    A synthesizer that can be asked a question has both. Anything else
    cannot answer, so probing it costs a timeout for nothing.
    """
    ins, outs = list_ports() if ports is None else ports
    return [name for name in ins if name in outs]


def likely_ports(
    hints: Sequence[str],
    ports: tuple[list[str], list[str]] | None = None,
) -> list[str]:
    """Ports whose name suggests the instrument. Only an ordering.

    A name hint cannot decide anything here and is not allowed to. Most of
    these instruments hang off a DIN cable behind whatever interface the
    user happens to have, and on a bench that was a *different
    manufacturer's* synth acting as the interface. No hint would ever have
    matched it. The Identity Reply decides; this only changes the order
    ports are tried in.
    """
    _ins, outs = list_ports() if ports is None else ports
    wanted = tuple(h.lower() for h in hints)
    return [port for port in outs if any(h in port.lower() for h in wanted)]


# The device type this function hands back. Spelled out rather than imported
# from `typing_extensions` for the same reason the rest of this file spells
# things out: one dependency less.
_Device = TypeVar("_Device")


def open_remembered_or_swept(
    *,
    probe: Callable[[str, str], _Device],
    sweep: Callable[[Callable[[str], None] | None], _Device],
    remembered: tuple[str, str] | None = None,
    scan: bool = False,
    remember: Callable[[Any], None] | None = None,
    on_try: Callable[[str], None] | None = None,
) -> _Device:
    """Open the remembered port if it still answers, else sweep for one.

    **This is the policy behind ``--scan``, and it is the whole reason that
    flag exists.** The normal path is *one* Identity Request, to the port
    remembered in ``config.toml``. That is not only an optimisation. A sweep
    sends an Identity Request to *every* bidirectional port on the machine,
    which on a studio box with thirty of them takes seconds, prints thirty
    lines, and pings every piece of hardware on the chain once per launch --
    and once the answer is known there is nothing left to learn by asking
    again. So: use the remembered port, sweep when there is none, sweep on
    request.

    **A remembered port that does not answer is not a licence to sweep.**
    The guess is gone, but sweeping anyway would make a launch silently
    take the slow path for a reason the user did not ask about, and would
    then quietly overwrite the file it was told to trust. Naming ``--scan``
    says what happened and what to do about it. It is the wrong fix for
    "the unit moved to another port", which is what USB re-enumeration
    causes: ALSA renumbers clients out from under a saved name.

    Ported from rxved's ``XvBridge.connect``, which was itself written the
    hard way -- its first version swept on every launch while its docstring
    claimed otherwise. The policy is worth having once, in one place, with
    tests, rather than in each project as a slightly different paragraph.

    ``probe`` raises :class:`DeviceError` (or ``OSError``) when the named
    port does not answer. ``sweep`` is expected to raise
    :class:`DeviceNotFound` if nothing answers at all. ``remember`` is
    called with the opened device afterwards, if given, and is where a
    project writes the pair it just learned.
    """
    if remembered is not None and not scan:
        send_port, recv_port = remembered
        try:
            device = probe(send_port, recv_port)
        except (DeviceError, OSError):
            # The remembered port is gone. Fall through to the sweep, and
            # say so: a silent sweep here would look like the fast path
            # having worked.
            if on_try is not None:
                on_try(f"{send_port} (remembered, did not answer)")
        else:
            return device

    device = sweep(on_try)
    if remember is not None:
        remember(device)
    return device


def render_ports(
    ins: Sequence[str],
    outs: Sequence[str],
    *,
    likely: Sequence[str] = (),
    likely_label: str = "",
    note: str = "",
) -> str:
    """The ``ports`` listing every tool prints, in one shape.

    Inputs, then outputs, two spaces of indent, and a bracketed mark on
    any port that can answer (:data:`bidirectional_ports`) or whose name
    suggests the instrument. A tool with no useful hint passes none and
    the mark simply does not appear -- the listing never claims a
    judgement it cannot make.
    """
    both = set(ins) & set(outs)
    hints = set(likely)
    lines: list[str] = []
    for label, names in (("inputs", ins), ("outputs", outs)):
        lines.append(f"{label}:")
        if not names:
            lines.append("  (none)")
            continue
        for name in names:
            marks = []
            if name in both:
                marks.append("bidirectional")
            if likely_label and name in hints:
                marks.append(likely_label)
            suffix = f"   [{', '.join(marks)}]" if marks else ""
            lines.append(f"  {name}{suffix}")
    if note:
        lines.append("")
        lines.append(note)
    return "\n".join(lines)


def install_clean_exit(on_exit: Callable[[], None] | None = None) -> None:
    """Close ports on SIGINT/SIGTERM rather than leaving them open.

    The optional ``on_exit`` is called first, for a caller that has
    something the ``finally`` blocks cannot reach.
    """

    def handler(signum: int, _frame: Any) -> None:  # pragma: no cover
        if on_exit is not None:
            try:
                on_exit()
            except Exception:
                pass
        sys.exit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):  # pragma: no cover - not main thread
            pass


def fail(message: str) -> NoReturn:
    """Stop with the family's one error format.

    ``error: <what happened>`` on stderr and exit code 1, everywhere, so
    that a message can be recognised without knowing which of the nine
    programs produced it. argparse uses exit code 2 for a usage mistake and
    prints in its own format; that is its business, not this function's.
    """
    raise SystemExit(f"error: {message}")
