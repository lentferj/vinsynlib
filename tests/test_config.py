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

"""The settings cache, including the two traps it is written around."""

from __future__ import annotations

import os
from typing import Any

import pytest

from vinsynlib import config


def test_a_missing_file_reads_as_empty_and_not_as_an_error(
    tmp_path: Any,
) -> None:
    store = config.Settings("x5ded", str(tmp_path / "absent.toml"))
    data, status = store.read()
    assert data == {}
    assert status == "ok"


def test_a_round_trip_survives_all_three_keys(tmp_path: Any) -> None:
    path = str(tmp_path / "config.toml")
    store = config.Settings("x5ded", path)
    store.save_channel(5)
    store.save_port("Midi Out: X5")
    store.save_recv_port("Midi In: X5")
    store.save_device_id(0x42)

    assert store.load_channel() == 5
    assert store.load_port() == "Midi Out: X5"
    assert store.load_recv_port() == "Midi In: X5"
    assert store.load_device_id() == 0x42


def test_a_toml_boolean_is_not_a_channel(tmp_path: Any) -> None:
    """`channel = true` used to come back as True, which is channel 2.

    `isinstance(True, int)` is True and `0 <= True <= 15` is true, so the
    value passed every range check and then `0xC0 | True` is `0xC1`. A
    wrong channel is not an error anywhere: the instrument simply plays
    nothing, or something else does.
    """
    path = tmp_path / "config.toml"
    path.write_text("channel = true\n", encoding="utf-8")
    store = config.Settings("x5ded", str(path))
    assert store.load_channel() is None


def test_a_toml_boolean_is_not_a_device_id(tmp_path: Any) -> None:
    """Device 1 is a real device, and the wrong one."""
    path = tmp_path / "config.toml"
    path.write_text("device_id = true\n", encoding="utf-8")
    store = config.Settings("x5ded", str(path))
    assert store.load_device_id() is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1, None), (0, 0), (15, 15), (16, None), (999, None)],
)
def test_the_channel_range_is_enforced_on_read(
    tmp_path: Any, value: Any, expected: Any
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f"channel = {value}\n", encoding="utf-8")
    store = config.Settings("x5ded", str(path))
    assert store.load_channel() == expected


def test_an_empty_port_is_no_port(tmp_path: Any) -> None:
    path = tmp_path / "config.toml"
    path.write_text('port = ""\n', encoding="utf-8")
    store = config.Settings("x5ded", str(path))
    assert store.load_port() is None


def test_a_quote_in_a_port_name_does_not_corrupt_the_file(
    tmp_path: Any,
) -> None:
    """ALSA client names are whatever the device reports.

    Writing one straight between quotes produced a file that was not TOML,
    and `_update` then refuses to overwrite a file it cannot parse -- which
    means the cache never heals: every later run reads nothing and writes
    nothing until somebody deletes it by hand.
    """
    path = str(tmp_path / "config.toml")
    store = config.Settings("x5ded", path)
    nasty = 'Midi Out: "X5" \\ here\ttab'
    store.save_port(nasty)

    assert store.load_port() == nasty
    store.save_channel(3)
    assert store.load_channel() == 3


def test_an_unparseable_file_is_never_overwritten(
    tmp_path: Any, capsys: Any
) -> None:
    path = tmp_path / "config.toml"
    path.write_text("this is not = = toml\n", encoding="utf-8")
    store = config.Settings("kwsed", str(path))
    store.save_channel(4)

    assert store.load_channel() is None
    assert path.read_text(encoding="utf-8") == "this is not = = toml\n"
    err = capsys.readouterr().err
    assert "kwsed" in err
    assert "nothing has been overwritten" in err


def test_the_refusal_is_announced_once(tmp_path: Any, capsys: Any) -> None:
    path = tmp_path / "config.toml"
    path.write_text("= = =\n", encoding="utf-8")
    store = config.Settings("kwsed", str(path))
    store.save_channel(1)
    store.save_channel(2)
    assert capsys.readouterr().err.count("could not be parsed") == 1


def test_the_warning_names_the_application_that_is_unhappy(
    tmp_path: Any, capsys: Any
) -> None:
    """Six of these open in one session; the message has to say which."""
    path = tmp_path / "config.toml"
    path.write_text("= = =\n", encoding="utf-8")
    config.Settings("nanosyned", str(path)).save_channel(1)
    assert "nanosyned:" in capsys.readouterr().err


def test_the_header_says_which_tool_it_belongs_to(tmp_path: Any) -> None:
    path = tmp_path / "config.toml"
    config.Settings("s3ked", str(path)).save_channel(1)
    head = path.read_text(encoding="utf-8").splitlines()[0]
    assert head.startswith("# s3ked local config")


def test_a_read_only_directory_is_survivable(tmp_path: Any) -> None:
    """Forgetting a preference beats refusing to run."""
    directory = tmp_path / "ro"
    directory.mkdir()
    os.chmod(directory, 0o500)
    try:
        store = config.Settings("x5ded", str(directory / "config.toml"))
        store.save_channel(7)
        assert store.load_channel() is None
    finally:
        os.chmod(directory, 0o700)


def test_an_explicit_path_overrides_the_default(tmp_path: Any) -> None:
    store = config.Settings("x5ded", str(tmp_path / "default.toml"))
    other = str(tmp_path / "other.toml")
    store.save_channel(9, other)
    assert store.load_channel(other) == 9
    assert store.load_channel() is None


def test_bind_names_the_application() -> None:
    store = config.bind("rxved")
    assert store.app_name == "rxved"
    assert store.default_path == config.DEFAULT_PATH


def test_a_project_shim_needs_only_a_name() -> None:
    """What each of the nine projects' config.py is now.

    The binding, not a copy: `load_channel` here is the very same bound
    method object the library hands out, so a fix in one is a fix in all.
    """
    from vinsynlib.config import Settings

    shim = Settings("x5ded")
    assert shim.app_name == "x5ded"
    assert shim.default_path == "config.toml"
    # Two shims, one implementation: the method each project binds is the
    # same function object, so a fix here lands in all nine.
    other = Settings("rxved")
    assert type(other).load_channel is type(shim).load_channel


# --- the port pair, and the device-ID ranges ---------------------------------


def test_the_pair_round_trips(tmp_path: Any) -> None:
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_ports("Midi Out: XV", "Midi In: XV")
    assert store.load_ports() == ("Midi Out: XV", "Midi In: XV")


def test_half_a_pair_is_no_pair(tmp_path: Any) -> None:
    """Three tools open one port and read the other from the same name, and
    treat an output-only memory as nothing remembered rather than half."""
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_port("Midi Out: XV")
    assert store.load_ports() is None


def test_saving_the_pair_keeps_the_channel(tmp_path: Any) -> None:
    store = config.Settings("eosed", str(tmp_path / "config.toml"))
    store.save_channel(3)
    store.save_ports("out", "in")
    assert store.load_channel() == 3
    assert store.load_ports() == ("out", "in")


def test_a_roland_device_id_is_refused_outside_its_panel_range(
    tmp_path: Any,
) -> None:
    """17-32 on the panel is 0x10-0x1F on the wire. They overlap, and a value
    from the wrong one is answered with silence -- so returning 5 would hand
    back something the user cannot confirm on the hardware."""
    path = tmp_path / "config.toml"
    path.write_text("device_id = 5\n", encoding="utf-8")
    store = config.Settings("rxved", str(path))

    assert store.load_device_id(minimum=17, maximum=32) is None
    assert store.load_device_id() == 5


@pytest.mark.parametrize("value", [17, 20, 32])
def test_a_roland_device_id_in_range_is_returned(
    tmp_path: Any, value: int
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f"device_id = {value}\n", encoding="utf-8")
    store = config.Settings("rxved", str(path))
    assert store.load_device_id(minimum=17, maximum=32) == value


def test_the_default_range_is_the_whole_byte(tmp_path: Any) -> None:
    path = tmp_path / "config.toml"
    path.write_text("device_id = 200\n", encoding="utf-8")
    assert config.Settings("x5ded", str(path)).load_device_id() is None
    path.write_text("device_id = 126\n", encoding="utf-8")
    assert config.Settings("x5ded", str(path)).load_device_id() == 126
