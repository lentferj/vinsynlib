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
import tomllib
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


def test_a_file_written_in_the_locale_codec_is_still_readable(
    tmp_path: Any,
) -> None:
    """The upgrade path: a file an older build wrote is not this one's fault.

    The cause was a writer that opened the file in text mode with no
    ``encoding=``, which means the locale codec, and on Windows that is
    cp1252 -- where the writer's own em dash in the header comment lands as
    a byte ``tomllib`` rejects. The whole file was then refused, every
    setting in it silently read back as unset, and -- because refusing to
    overwrite an unparseable file is itself correct -- the cache could not
    heal until somebody deleted it by hand.

    Fixing the writer removed the cause. This test is about the other half:
    somebody who ran the broken build still has the file it wrote, and their
    hand-edited keys have to survive the upgrade. Decoding leniently does
    that, and the next save rewrites the file as UTF-8 for good.
    """
    path = tmp_path / "config.toml"
    # Exactly what the broken build wrote: an em dash in cp1252.
    path.write_bytes(
        "# s3ked local config — gitignored, safe to delete.\n"
        'cache_depth = "full"\n'.encode("cp1252")
    )
    store = config.Settings("s3ked", str(path))

    data, status = store.read()
    assert status == "ok", data
    assert data["cache_depth"] == "full"

    # ...and the next save repairs the encoding, keeping the hand-edited key.
    store.save_channel(7)
    path.read_bytes().decode("utf-8")  # must not raise
    assert store.load_channel() == 7
    assert store.read()[0]["cache_depth"] == "full"


def test_a_file_that_is_not_toml_in_any_encoding_is_still_refused(
    tmp_path: Any, capsys: Any
) -> None:
    """Lenient decoding must not become lenient parsing.

    Decoding cp1252 replaces every byte it cannot map, so it will happily
    produce text from a file that was never TOML. The refusal is the
    important part: an unparseable file must not be read as "no settings"
    and then overwritten, or one bad byte costs the user everything else in
    it.
    """
    path = tmp_path / "config.toml"
    path.write_bytes(b"this is not = = toml\x80\x81\n")
    store = config.Settings("s3ked", str(path))
    before = path.read_bytes()

    store.save_channel(4)
    assert store.load_channel() is None
    assert path.read_bytes() == before
    assert "could not be parsed" in capsys.readouterr().err


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


def test_an_unwritable_path_is_survivable(tmp_path: Any) -> None:
    """Forgetting a preference beats refusing to run.

    The unwritable path is a parent that is a *file*, not a read-only
    directory. `os.chmod` on a directory is a no-op on Windows -- the write
    succeeds there, so the read-only version of this test passed for the
    wrong reason on the author's machine and failed on the Windows runner.
    A file where a directory is expected raises `NotADirectoryError` on
    every platform, so this one exercises the same `except OSError` arm and
    means the same thing everywhere.
    """
    not_a_directory = tmp_path / "afile"
    not_a_directory.write_text("", encoding="utf-8")
    store = config.Settings("x5ded", str(not_a_directory / "config.toml"))

    store.save_channel(7)  # must not raise
    assert store.load_channel() is None


@pytest.mark.skipif(
    os.name != "posix",
    reason="Windows has no POSIX mode bits: os.chmod there only toggles the "
    "read-only flag and a directory stays writable, so this would assert "
    "nothing. The platform-independent case is the test above.",
)
def test_a_read_only_directory_is_survivable(tmp_path: Any) -> None:
    """The same thing against a real read-only directory, where that exists."""
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


def test_unset_removes_key_from_settings(tmp_path: Any) -> None:
    """Settings.update can remove keys by setting their value to None."""
    path = tmp_path / "config.toml"
    # Start with a file that has some settings
    path.write_text("port = 'TEST'\ndevice_id = 42\n", encoding="utf-8")

    # Create settings instance
    store = config.Settings("test", str(path))

    # Unset the port by setting it to None
    store.update(port=None)

    # Read back and verify port is gone but device_id remains
    data, _ = store.read()
    assert "port" not in data
    assert data.get("device_id") == 42


def test_the_default_range_is_the_whole_byte(tmp_path: Any) -> None:
    path = tmp_path / "config.toml"
    path.write_text("device_id = 200\n", encoding="utf-8")
    assert config.Settings("x5ded", str(path)).load_device_id() is None
    path.write_text("device_id = 126\n", encoding="utf-8")
    assert config.Settings("x5ded", str(path)).load_device_id() == 126


# --- one file per directory, nine tools --------------------------------------


def test_a_file_that_belongs_to_another_tool_is_not_read(
    tmp_path: Any,
) -> None:
    """The second tool in a directory must not adopt the first's port.

    Nine of these default to the same relative ``config.toml``. On a bench
    that means probing the wrong instrument -- and for the two whose
    hardware shares a manufacturer, a reply that looks right.
    """
    path = tmp_path / "config.toml"
    path.write_text(
        "# x5ded local config - gitignored, safe to delete.\n"
        'port = "Midi Out: Korg X5D"\n'
        "channel = 4\n",
        encoding="utf-8",
    )
    store = config.Settings("p2ked", str(path))
    assert store.load_port() is None
    assert store.load_channel() is None
    assert store.read() == ({}, "ok")


def test_a_file_that_belongs_to_another_tool_is_not_overwritten(
    tmp_path: Any, capsys: Any
) -> None:
    path = tmp_path / "config.toml"
    before = (
        "# x5ded local config - gitignored, safe to delete.\n"
        'port = "Midi Out: Korg X5D"\n'
    )
    path.write_text(before, encoding="utf-8")
    store = config.Settings("p2ked", str(path))

    store.save_channel(1)

    assert path.read_text(encoding="utf-8") == before
    err = capsys.readouterr().err
    assert "p2ked" in err and "x5ded" in err


def test_a_file_with_tables_is_left_alone(tmp_path: Any, capsys: Any) -> None:
    """A foreign project's ``config.toml`` looks exactly like this.

    The old writer would have rendered ``server`` as Python ``repr`` and
    produced a file that is not TOML, losing the whole foreign document.
    """
    path = tmp_path / "config.toml"
    before = (
        '# a project that is not ours\ntitle = "my site"\n'
        '[server]\nhost = "localhost"\nport = 8080\n'
    )
    path.write_text(before, encoding="utf-8")
    store = config.Settings("p2ked", str(path))

    store.save_ports("Midi Out: P2K", "Midi Out: P2K")

    assert path.read_text(encoding="utf-8") == before
    assert "tables" in capsys.readouterr().err


def test_a_legacy_header_with_our_name_is_still_ours(tmp_path: Any) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "# p2ked local config - gitignored, safe to delete.\nchannel = 3\n",
        encoding="utf-8",
    )
    store = config.Settings("p2ked", str(path))
    assert store.load_channel() == 3
    store.save_port("Midi Out: P2K", str(path))
    assert store.load_port() == "Midi Out: P2K"


def test_an_unrecognised_header_is_not_foreign(tmp_path: Any) -> None:
    """An old build's em dash is not another tool.

    Only a header that names a *different* tool makes a file foreign;
    anything else is the caller's own, so the lenient upgrade path from a
    locale-codec build keeps working.
    """
    path = tmp_path / "config.toml"
    path.write_text(
        "# s3ked local config — gitignored, safe to delete.\nchannel = 6\n",
        encoding="utf-8",
    )
    store = config.Settings("s3ked", str(path))
    assert store.load_channel() == 6


def test_the_write_leaves_no_temporary_behind(tmp_path: Any) -> None:
    path = str(tmp_path / "config.toml")
    store = config.Settings("p2ked", path)
    store.save_channel(2)

    assert not [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]


# --- §3.7: one directory per tool --------------------------------------------


def test_config_dir_uses_xdg_config_home(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_dir("rxved") == str(tmp_path / "xdg" / "rxved")
    assert config.config_dir("p2ked") == str(tmp_path / "xdg" / "p2ked")


def test_config_dir_falls_back_to_home_dot_config(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config.config_dir("rxved") == str(tmp_path / ".config" / "rxved")


def test_config_dir_ignores_a_relative_xdg_config_home(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """XDG requires the variable to hold an absolute path.

    A relative value must fall back rather than create directories
    wherever the process happened to have been started.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config.config_dir("rxved") == str(tmp_path / ".config" / "rxved")


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b"])
def test_config_dir_refuses_names_that_are_not_plain(bad: str) -> None:
    with pytest.raises(ValueError):
        config.config_dir(bad)


def test_default_config_path_is_per_tool(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.default_config_path("rxved") == str(
        tmp_path / "rxved" / "config.toml"
    )


def test_config_help_names_the_per_tool_default(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """The --config wording keeps the family's shape, with this tool's
    own default filled in."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    wording = config.config_help("rxved")
    assert "settings cache" in wording
    assert "safe to delete" in wording
    assert str(tmp_path / "rxved" / "config.toml") in wording
    assert "./config.toml" not in wording


def test_the_migration_note_says_where_and_how() -> None:
    """The file move wants a note louder than a changelog bullet."""
    assert "config.toml" in config.MIGRATION_NOTE
    assert "--config" in config.MIGRATION_NOTE


def test_migration_copies_a_legacy_file_into_the_tool_dir(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    legacy = tmp_path / "config.toml"
    legacy.write_text(
        "# rxved local config - gitignored, safe to delete.\n"
        'port = "Midi Out: XV"\nchannel = 4\n',
        encoding="utf-8",
    )
    moved = config.migrate_legacy_config("rxved", legacy=str(legacy))

    assert moved == config.default_config_path("rxved")
    assert moved is not None
    fresh = config.Settings("rxved", moved)
    assert fresh.load_port() == "Midi Out: XV"
    assert fresh.load_channel() == 4
    # A copy, not a move: the old file stays until its owner, having
    # seen the new one work, deletes it by hand.
    assert legacy.exists()


def test_migration_also_takes_a_headerless_file(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """No family header is not another tool: the lenient upgrade path
    treats it as ours, and so does the migration."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    legacy = tmp_path / "config.toml"
    legacy.write_text("channel = 6\n", encoding="utf-8")
    moved = config.migrate_legacy_config("rxved", legacy=str(legacy))
    assert moved is not None
    assert config.Settings("rxved", moved).load_channel() == 6


def test_migration_leaves_a_foreign_file_alone(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    legacy = tmp_path / "config.toml"
    legacy.write_text(
        "# x5ded local config - gitignored, safe to delete.\n"
        'port = "Midi Out: X5D"\n',
        encoding="utf-8",
    )
    assert config.migrate_legacy_config("p2ked", legacy=str(legacy)) is None
    assert not (tmp_path / "xdg" / "p2ked" / "config.toml").exists()


def test_migration_never_overwrites(tmp_path: Any, monkeypatch: Any) -> None:
    """A target that already exists wins: the legacy file may be stale,
    and a migration that destroys the newer memory is no migration."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    target = tmp_path / "xdg" / "rxved" / "config.toml"
    target.parent.mkdir(parents=True)
    target.write_text("channel = 1\n", encoding="utf-8")
    legacy = tmp_path / "config.toml"
    legacy.write_text("channel = 9\n", encoding="utf-8")

    assert config.migrate_legacy_config("rxved", legacy=str(legacy)) is None
    assert target.read_text(encoding="utf-8") == "channel = 1\n"


def test_migration_with_no_legacy_file_is_nothing_to_do(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    missing = tmp_path / "absent.toml"
    assert config.migrate_legacy_config("rxved", legacy=str(missing)) is None


def test_migration_refuses_an_unparseable_legacy_file(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    legacy = tmp_path / "config.toml"
    legacy.write_text("this is not = = toml\n", encoding="utf-8")
    assert config.migrate_legacy_config("rxved", legacy=str(legacy)) is None
    assert not (tmp_path / "xdg" / "rxved" / "config.toml").exists()


# --- §3.15: the screens' own memory ------------------------------------------


def test_ui_state_round_trips_scalars(tmp_path: Any) -> None:
    path = str(tmp_path / "ui-state.toml")
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_ui_state("browser.bank", "USER", path)
    store.save_ui_state("browser.cursor", 3, path)
    store.save_ui_state("browser.preview", True, path)
    store.save_ui_state("browser.mix", 0.75, path)

    assert store.load_ui_state("browser.bank", path) == "USER"
    assert store.load_ui_state("browser.cursor", path) == 3
    assert store.load_ui_state("browser.preview", path) is True
    assert store.load_ui_state("browser.mix", path) == 0.75


def test_ui_state_absent_is_unset_not_none(tmp_path: Any) -> None:
    """Absent means remember-nothing, and UNSET is how that reads.

    The sentinel exists because None is taken: saving None forgets a
    key, so None can never be what the file says, and "nothing kept"
    needs a value of its own.
    """
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    missing = str(tmp_path / "ui-state.toml")

    assert store.load_ui_state("browser.bank", missing) is config.UNSET
    assert store.load_ui_state("browser.bank", missing) is not None
    data, status = store.read_ui_state(missing)
    assert (data, status) == ({}, "ok")


def test_ui_state_explicit_none_is_the_callers_own_default(
    tmp_path: Any,
) -> None:
    """UNSET-vs-None, the other half: a caller passing default=None gets
    None back, which is its own choice and not the file's."""
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    missing = str(tmp_path / "ui-state.toml")

    assert store.load_ui_state("browser.bank", missing, default=None) is None
    assert store.load_ui_state("browser.bank", missing, default=7) == 7


def test_unset_prints_as_itself_and_counts_as_nothing() -> None:
    assert repr(config.UNSET) == "UNSET"
    assert not config.UNSET


def test_ui_state_none_forgets_the_key(tmp_path: Any) -> None:
    path = str(tmp_path / "ui-state.toml")
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_ui_state("browser.bank", "USER", path)
    assert store.load_ui_state("browser.bank", path) == "USER"

    store.save_ui_state("browser.bank", None, path)

    assert "browser.bank" not in store.read_ui_state(path)[0]
    assert store.load_ui_state("browser.bank", path) is config.UNSET


def test_ui_state_bool_is_not_an_int(tmp_path: Any) -> None:
    """bool subclasses int, so the int reader checks bool first.

    A hand-edited ``flag = true`` read as 1 would restore a cursor on
    the second row -- the same trap load_channel guards one file over.
    """
    path = tmp_path / "ui-state.toml"
    path.write_text("flag = true\ncount = 3\n", encoding="utf-8")
    store = config.Settings("rxved", str(tmp_path / "config.toml"))

    assert store.load_ui_bool("flag", str(path)) is True
    assert store.load_ui_int("flag", str(path)) is None
    assert store.load_ui_int("count", str(path)) == 3
    assert store.load_ui_bool("count", str(path)) is None
    assert store.load_ui_str("count", str(path)) is None


def test_ui_state_namespaced_keys_stay_flat(tmp_path: Any) -> None:
    """A dotted key is written quoted: unquoted, ``a.b`` is a table in
    TOML, and a table trips the refusal on the next write."""
    path = tmp_path / "ui-state.toml"
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_ui_state("browser.cursor", 3, str(path))

    text = path.read_text(encoding="utf-8")
    assert '"browser.cursor"' in text
    assert tomllib.loads(text)["browser.cursor"] == 3
    assert store.load_ui_int("browser.cursor", str(path)) == 3

    # ...and the round trip survives a second save, which is what the
    # unquoted form would break: the nested table would refuse.
    store.save_ui_state("browser.bank", "USER", str(path))
    assert store.load_ui_int("browser.cursor", str(path)) == 3
    assert store.load_ui_str("browser.bank", str(path)) == "USER"


def test_ui_state_can_share_the_settings_file(tmp_path: Any) -> None:
    """One flat mapping: namespaced ui keys beside the port keys."""
    path = str(tmp_path / "config.toml")
    store = config.Settings("rxved", path)
    store.save_port("Midi Out: XV")
    store.save_ui_state("browser.cursor", 2, path)
    assert store.load_port() == "Midi Out: XV"
    assert store.load_ui_int("browser.cursor", path) == 2


def test_ui_state_defaults_to_beside_the_settings_file(
    tmp_path: Any,
) -> None:
    """No path means the ui-state file next to this tool's config, and
    another tool's file still reads as empty."""
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    store.save_ui_state("browser.cursor", 5)

    assert (tmp_path / "ui-state.toml").exists()
    assert store.load_ui_state("browser.cursor") == 5
    other = config.Settings("p2ked", str(tmp_path / "config.toml"))
    assert other.load_ui_state("browser.cursor") is config.UNSET


@pytest.mark.parametrize("bad", [{"bank": "USER"}, ["USER"], ("USER",)])
def test_ui_state_rejects_non_scalars(tmp_path: Any, bad: Any) -> None:
    """A screen's memory is scalars: anything nested is a programming
    error, and must be heard rather than silently stringified."""
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    with pytest.raises(TypeError):
        store.save_ui_state("browser.bank", bad, str(tmp_path / "ui.toml"))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_ui_state_rejects_non_finite_floats(tmp_path: Any, bad: float) -> None:
    """NaN and the infinities have no TOML spelling: writing one would
    leave a file the next read refuses, wedging every later save."""
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    with pytest.raises(ValueError):
        store.save_ui_state("browser.mix", bad, str(tmp_path / "ui.toml"))


def test_ui_state_rejects_an_empty_key(tmp_path: Any) -> None:
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    missing = str(tmp_path / "absent.toml")
    with pytest.raises(ValueError):
        store.save_ui_state("", "USER", missing)
    # The key is checked before the file is: even a missing file hears
    # about a programming error rather than answering UNSET.
    with pytest.raises(ValueError):
        store.load_ui_state("", missing)


def test_ui_state_rejects_a_non_string_key(tmp_path: Any) -> None:
    store = config.Settings("rxved", str(tmp_path / "config.toml"))
    key: Any = 123
    with pytest.raises(TypeError):
        store.save_ui_state(key, "USER", str(tmp_path / "ui.toml"))


def test_an_unreadable_ui_state_file_is_remember_nothing(
    tmp_path: Any, capsys: Any
) -> None:
    """The config discipline carries over: a broken ui-state file reads
    as nothing remembered and is never overwritten by a save."""
    path = tmp_path / "ui-state.toml"
    path.write_text("this is not = = toml\n", encoding="utf-8")
    store = config.Settings("rxved", str(tmp_path / "config.toml"))

    assert store.load_ui_state("browser.bank", str(path)) is config.UNSET
    before = path.read_bytes()
    store.save_ui_state("browser.bank", "USER", str(path))
    assert path.read_bytes() == before
    assert "could not be parsed" in capsys.readouterr().err
