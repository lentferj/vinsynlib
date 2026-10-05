# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
#
# This file is part of vinsynlib.
#
# Assembled from the settings-cache handling that every browser in the
# family carried its own copy of:
#   Copyright (C) 2026  emorphed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  ensqsqed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  eosed contributors           - GPL-2.0-or-later
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

"""The local settings cache: which port answered, and which channel.

**Disposable on purpose.** Unlike the favourites database, nothing here is
the user's own work -- it is a note of what was true last time, so that
starting the program again does not mean setting the same things again.
Deleting it costs one re-entry of each. That is why it lives in the working
directory rather than the data directory, why every failure to write it is
swallowed, and why it is gitignored.

Only :class:`OSError` is swallowed, mind: a read-only directory or a full
disk, where forgetting a preference beats refusing to run. Anything else is
a bug and should be heard. rxved's first attempt at remembering a channel
caught everything, and so never noticed that it was raising ``NameError``
on every single call and writing nothing at all.

One :class:`Settings` per application. The application name is only used in
the one warning message, but it is required, because that message has to
say which of the family is refusing to save -- otherwise a user with six of
these open has no way to tell which one is unhappy.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

# Every project in the family requires 3.11 or later, and this library
# only ever imports under a newer interpreter than that, so the fallback
# below is unreachable in practice and is not tested. It is here because
# two of the copies it replaces had it and a reader would wonder where it
# went.
tomllib: Any
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None

__all__ = [
    "DEFAULT_PATH",
    "Settings",
    "bind",
]

#: Where the cache lives unless told otherwise. Relative on purpose: it is a
#: per-checkout note, gitignored, and one checkout per checkout.
DEFAULT_PATH = "config.toml"

#: MIDI has sixteen channels, zero-based on the wire and one-based on every
#: command line in this family. Both numbers are named because confusing
#: them costs a channel with no error anywhere.
MIDI_CHANNELS = 16
MAX_MIDI_CHANNEL = MIDI_CHANNELS - 1

#: A SysEx device ID is a byte. 127 is broadcast in some protocols and a
#: real device in others, which is why reading one back is range-checked
#: against a number rather than trusted.
MAX_DEVICE_ID = 127

#: DEL. The one control character with no TOML escape of its own.
DEL = 0x7F

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}


@dataclass
class Settings:
    """One application's settings cache.

    Construct once per process with the application's name, then call the
    methods. Every method takes an optional ``path`` so a test can hand in
    a temporary file; the default is this application's :data:`DEFAULT_PATH`.
    """

    app_name: str
    default_path: str = DEFAULT_PATH
    #: Whether the "cannot save" warning has already been printed. Module
    #: level in the per-project copies this replaces, which is to say it was
    #: shared by every ``Settings`` in the process; per instance is closer
    #: to the intent and behaves the same for a single application.
    _warned: bool = field(default=False, init=False, repr=False)

    # --- reading -------------------------------------------------------------

    def read(self, path: str | None = None) -> tuple[dict[str, Any], str]:
        """The file's keys, and ``"ok"`` or ``"unreadable"``.

        A file that does not exist reads as empty and is not an error: the
        first run of a program has no settings yet, and that is the normal
        case rather than a fault to report.
        """
        target = path or self.default_path
        if not os.path.exists(target) or tomllib is None:
            return {}, "ok"
        try:
            with open(target, "rb") as handle:
                return tomllib.load(handle), "ok"
        except (OSError, ValueError):
            return {}, "unreadable"

    # --- writing -------------------------------------------------------------

    def update(self, path: str | None = None, **changes: Any) -> None:
        """Merge ``changes`` into the file, rewriting what is there.

        Refuses to write over a file it cannot parse, and says so once. That
        refusal is also why the escaping below matters: a port name is an
        arbitrary string -- ALSA client names are whatever the device
        reports -- so a quote in one produces a file that is not TOML, and a
        cache that never heals, because every later run reads nothing and
        writes nothing until somebody deletes it by hand.
        """
        target = path or self.default_path
        data, status = self.read(target)
        if status == "unreadable":
            if not self._warned:
                self._warned = True
                print(
                    f"{self.app_name}: {target} could not be parsed, so "
                    f"settings are not being saved. Fix or delete it; "
                    f"nothing has been overwritten.",
                    file=sys.stderr,
                )
            return
        data.update(changes)
        lines = [
            f"# {self.app_name} local config - gitignored, safe to delete."
        ]
        for key, value in data.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, str):
                lines.append(f"{key} = {self._toml_string(value)}")
            else:
                lines.append(f"{key} = {value}")
        try:
            # encoding= is not optional: without it Python uses the locale
            # codec, and TOML is UTF-8 by spec. Both ends must say so.
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        except OSError:
            pass

    @staticmethod
    def _toml_string(value: str) -> str:
        """One TOML basic string, escaped.

        TOML basic strings interpret the usual backslash escapes as well,
        so a literal tab or newline is written as an escape rather than
        embedded, and a control character that has no escape becomes a
        ``\\uXXXX``.
        """
        out = ['"']
        for char in value:
            if char in _ESCAPES:
                out.append(_ESCAPES[char])
            elif ord(char) < 0x20 or ord(char) == DEL:
                out.append(f"\\u{ord(char):04X}")
            else:
                out.append(char)
        out.append('"')
        return "".join(out)

    # --- channel -------------------------------------------------------------

    def load_channel(self, path: str | None = None) -> int | None:
        """The channel last sent on, zero-based, or None.

        The bool check is not decoration. ``isinstance(True, int)`` is True
        and ``0 <= True <= 15`` is true, so a hand-edited ``channel = true``
        used to come back as ``True`` and pass every range check downstream
        -- and then ``0xC0 | True`` is ``0xC1``, which is MIDI **channel
        2**. A wrong channel is not an error anywhere: the instrument
        simply plays nothing, or something else does.
        """
        value = self.read(path)[0].get("channel")
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if 0 <= value <= MAX_MIDI_CHANNEL else None

    def save_channel(self, channel: int, path: str | None = None) -> None:
        self.update(path, channel=int(channel))

    # --- ports ---------------------------------------------------------------

    def load_port(self, path: str | None = None) -> str | None:
        """The port name last used for output."""
        value = self.read(path)[0].get("port")
        return value if isinstance(value, str) and value else None

    def save_port(self, port: str, path: str | None = None) -> None:
        self.update(path, port=str(port))

    def load_recv_port(self, path: str | None = None) -> str | None:
        """The input port last opened, when it differed from the output one.

        A separate key rather than a second port: most of these instruments
        take their input from the same USB port they output to, and a
        second key that is empty most of the time is the cheapest way to
        remember the case where it is not.
        """
        value = self.read(path)[0].get("recv_port")
        return value if isinstance(value, str) and value else None

    def save_recv_port(self, port: str, path: str | None = None) -> None:
        self.update(path, recv_port=str(port))

    def load_ports(self, path: str | None = None) -> tuple[str, str] | None:
        """Both remembered ports as a pair, or None.

        Only when *both* are known. A half-remembered pair is not a pair:
        three of the tools in this family open one port and read the other
        from the same name, and treat an output-only or input-only memory
        as nothing remembered at all rather than as half of what they need.
        """
        data = self.read(path)[0]
        send = data.get("port")
        recv = data.get("recv_port")
        if isinstance(send, str) and send and isinstance(recv, str) and recv:
            return send, recv
        return None

    def save_ports(
        self, send_port: str, recv_port: str, path: str | None = None
    ) -> None:
        """Remember both ports at once, in one write to the file.

        One write rather than two because the file is rewritten whole every
        time: writing ``port`` and then ``recv_port`` separately reads and
        rewrites between them, and a failure in between leaves the first
        saved and the second lost.
        """
        self.update(path, port=str(send_port), recv_port=str(recv_port))

    # --- device id -----------------------------------------------------------

    def load_device_id(
        self,
        path: str | None = None,
        *,
        minimum: int = 0,
        maximum: int = MAX_DEVICE_ID,
    ) -> int | None:
        """The device ID last used, or None.

        ``isinstance(True, int)`` is True, so a hand-edited
        ``device_id = true`` would come back as device 1 -- a real device,
        and the wrong one. A wrong device ID is answered with silence by
        these instruments, which is the failure mode that hides behind
        every other.

        ``minimum``/``maximum`` because a device ID is not one range
        everywhere. It is a byte for most of these instruments, 0-127, and
        on a Roland XV-2020 the synth *displays* it as the panel number
        17-32, which is the wire byte 0x10-0x1F plus one. That tool
        therefore checks its own range, and it is right to: a value of 5
        there is not a device ID that happens to be unused, it is a value
        its own front panel cannot show, so returning it would hand back
        something the user cannot confirm on the hardware.
        """
        value = self.read(path)[0].get("device_id")
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if minimum <= value <= maximum else None

    def save_device_id(self, device_id: int, path: str | None = None) -> None:
        self.update(path, device_id=int(device_id))


def bind(app_name: str, default_path: str = DEFAULT_PATH) -> Settings:
    """A :class:`Settings` for one application.

    The shape every project used to hand-roll: one settings object, named
    after the tool, with the tool's name in its one warning message.
    """
    return Settings(app_name=app_name, default_path=default_path)
