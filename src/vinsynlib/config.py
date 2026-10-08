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

import contextlib
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

#: The end of the first line written by :meth:`Settings.update`, after the
#: application's name. One string, because two things now read it: the writer
#: that puts it there, and the reader that refuses to treat another
#: application's file as its own. The prefix is deliberately loose -- a build
#: before this one wrote an em dash where this writes a hyphen, and a file
#: that old still has to read as ours rather than as a stranger's.
_HEADER = " local config - gitignored, safe to delete."


def _owner(first_line: str | None) -> str | None:
    """The application named in a settings file's first line, or ``None``.

    ``None`` means "not a family header": a hand-written file, an old build's
    em dash, or no comment at all. Only a file that names *another* tool is
    treated as foreign, so an unrecognised header stays the caller's own and
    the lenient upgrade path keeps working.
    """
    if first_line is None:
        return None
    line = first_line.strip()
    if not line.startswith("#"):
        return None
    body = line[1:].strip()
    if not body.endswith(_HEADER):
        return None
    name = body[: -len(_HEADER)].strip()
    return name or None


@dataclass
class Settings:
    """One application's settings cache.

    Construct once per process with the application's name, then call the
    methods. Every method takes an optional ``path`` so a test can hand in
    a temporary file; the default is this application's :data:`DEFAULT_PATH`.
    """

    app_name: str
    default_path: str = DEFAULT_PATH
    #: Which refusals have already been announced, so a launch prints each
    #: at most once. Module level in the per-project copies this replaces,
    #: which is to say it was shared by every ``Settings`` in the process;
    #: per instance is closer to the intent and behaves the same for a
    #: single application. A set rather than a bool because there are now
    #: three reasons to refuse to write, and one must not silence another.
    _warned: set[str] = field(default_factory=set, init=False, repr=False)

    # --- reading -------------------------------------------------------------

    def read(self, path: str | None = None) -> tuple[dict[str, Any], str]:
        """The file's keys, and ``"ok"`` or ``"unreadable"``.

        A file that does not exist reads as empty and is not an error: the
        first run of a program has no settings yet, and that is the normal
        case rather than a fault to report.

        A file that exists but cannot be parsed reports ``"unreadable"``,
        which :meth:`update` turns into a refusal rather than a blind
        overwrite. Collapsing the two cases is what made a whole class of
        bug invisible, so they are kept apart.

        **Decoded leniently, then parsed as TOML.** Three of the copies this
        replaces decoded the bytes themselves and fell back to cp1252 for
        anything that was not valid UTF-8, and dropping that on the way into
        the library was a regression rather than a simplification. The cause
        was real: a writer that opened the file in text mode with no
        ``encoding=`` used the locale codec, which on Windows is cp1252, and
        the em dash in the writer's own header comment then landed as a byte
        ``tomllib`` rejects. The whole file was refused, every setting in it
        silently read back as unset, and -- because refusing to overwrite an
        unparseable file is itself correct -- the settings cache could not
        heal until somebody deleted it by hand.

        Fixing the writer removed that one cause. It did not remove the
        upgrade path: somebody who ran the broken build still has the file
        it wrote. Decoding leniently lets their hand-edited keys survive, and
        the next save rewrites the file as UTF-8, so it stays readable from
        then on.

        **A file that belongs to another tool reads as empty.** Nine of
        these tools default to the same relative ``config.toml`` in whatever
        directory they are launched from. When two of them meet in one
        directory, the second must not read the first's remembered port: on
        a bench that means probing the wrong instrument, and for the two
        tools whose hardware shares a manufacturer it means a reply that
        looks right. The file's own header says whose it is; see
        :func:`_owner`.
        """
        target = path or self.default_path
        data, status, first_line = self._read_document(target)
        if status != "ok":
            return data, status
        owner = _owner(first_line)
        if owner is not None and owner != self.app_name:
            return {}, "ok"
        return data, "ok"

    def _read_document(
        self, target: str
    ) -> tuple[dict[str, Any], str, str | None]:
        """The parsed file, its status, and its first line.

        The unfiltered form of :meth:`read`: :meth:`update` needs the header
        and any foreign content to decide whether writing is safe, while
        callers of :meth:`read` only ever want this application's keys.
        """
        if not os.path.exists(target) or tomllib is None:
            return {}, "ok", None
        try:
            with open(target, "rb") as handle:
                raw = handle.read()
        except OSError:
            return {}, "unreadable", None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Not valid UTF-8, so it was almost certainly written by a build
            # using the locale codec. Decoded leniently so a user's
            # hand-edited keys survive the upgrade; the next save repairs the
            # encoding for good.
            text = raw.decode("cp1252", errors="replace")
        try:
            data = tomllib.loads(text)
        except ValueError:
            return {}, "unreadable", None
        first_line = text.split("\n", 1)[0]
        return data, "ok", first_line

    # --- writing -------------------------------------------------------------

    def update(self, path: str | None = None, **changes: Any) -> None:
        """Merge ``changes`` into the file, rewriting what is there.

        Refuses, and says so once, in three cases, because in all three the
        alternative is destroying something this tool did not write:

        * the file cannot be parsed -- the refusal that is also why the
          escaping below matters (a port name is an arbitrary string, and a
          quote in one would otherwise produce a file that never heals);
        * the file's header names a **different** tool in the family -- two
          of these in one directory would otherwise overwrite each other's
          remembered port on every launch, for ever;
        * the file holds tables or lists -- this tool writes only scalars,
          so anything nested belongs to somebody else (a foreign project's
          ``config.toml`` looks exactly like this) and the old writer turned
          it into Python ``repr`` and destroyed the file.

        The write itself is atomic: a temporary file beside the target, then
        ``os.replace``. The old writer truncated the target and refilled it,
        so a reader running at the same time could see half a file. Only
        :class:`OSError` is swallowed, as everywhere here.

        To unset a key, set its value to ``None``.
        """
        target = path or self.default_path
        data, status, first_line = self._read_document(target)
        if status == "unreadable":
            self._warn_once(
                "unreadable",
                f"{self.app_name}: {target} could not be parsed, so "
                f"settings are not being saved. Fix or delete it; "
                f"nothing has been overwritten.",
            )
            return
        owner = _owner(first_line)
        if owner is not None and owner != self.app_name:
            self._warn_once(
                "foreign",
                f"{self.app_name}: {target} is {owner}'s settings file, so "
                f"{self.app_name} is leaving it alone. Use --config to name "
                f"a path of its own.",
            )
            return
        if any(isinstance(value, (dict, list)) for value in data.values()):
            self._warn_once(
                "complex",
                f"{self.app_name}: {target} holds tables or lists, which "
                f"{self.app_name} does not write, so it is leaving it alone. "
                f"Use --config to name a path of its own.",
            )
            return
        for key, value in changes.items():
            if value is None:
                data.pop(key, None)  # Remove key if present
            else:
                data[key] = value
        lines = [f"# {self.app_name}{_HEADER}"]
        for key, value in data.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, str):
                lines.append(f"{key} = {self._toml_string(value)}")
            else:
                lines.append(f"{key} = {value}")
        self._write_atomic(target, "\n".join(lines) + "\n")

    def _warn_once(self, reason: str, message: str) -> None:
        """Print ``message`` once per reason, per instance."""
        if reason in self._warned:
            return
        self._warned.add(reason)
        print(message, file=sys.stderr)

    @staticmethod
    def _write_atomic(target: str, text: str) -> None:
        """Write ``text`` to ``target`` through a temporary beside it.

        ``encoding=`` is not optional: without it Python uses the locale
        codec, and TOML is UTF-8 by spec. Both ends must say so.
        """
        tmp = f"{target}.{os.getpid()}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, target)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp)

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
