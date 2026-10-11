# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Backup envelope: stdlib-only JSON, never touches MIDI."""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from vinsynlib.backup import FORMAT, list_backups, load, save


def test_round_trip(tmp_path: pathlib.Path) -> None:
    target = str(tmp_path / "backups")
    path = save(
        target,
        kind="patch",
        slot="01",
        name="Amber",
        device_id="roland-xv",
        source="manual",
        blocks={"sysex": b"\xf0\x01\xf7"},
    )
    loaded = load(path)
    assert loaded.kind == "patch"
    assert loaded.slot == "01"
    assert loaded.name == "Amber"
    assert loaded.device_id == "roland-xv"
    assert loaded.source == "manual"
    assert loaded.blocks == {"sysex": b"\xf0\x01\xf7"}
    assert loaded.error is None


def test_save_never_overwrites(tmp_path: pathlib.Path) -> None:
    target = str(tmp_path / "backups")
    path1 = save(
        target,
        kind="k",
        slot="s",
        name="n",
        device_id="d",
        source="src",
        blocks={},
    )
    path2 = save(
        target,
        kind="k",
        slot="s",
        name="n",
        device_id="d",
        source="src",
        blocks={},
    )
    assert path1 != path2
    assert os.path.isfile(path1)
    assert os.path.isfile(path2)


def test_load_refuses_wrong_version(tmp_path: pathlib.Path) -> None:
    bad_path = str(tmp_path / "bad.json")
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump({"format": 99, "kind": "x", "slot": ""}, f)
    with pytest.raises(ValueError, match="wrong version"):
        load(bad_path)


def test_load_refuses_wrong_kind(tmp_path: pathlib.Path) -> None:
    bad_path = str(tmp_path / "bad_kind.json")
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump({"format": FORMAT, "kind": ""}, f)
    with pytest.raises(ValueError, match="wrong kind"):
        load(bad_path)


def test_list_backups_includes_corrupt_with_error(
    tmp_path: pathlib.Path,
) -> None:
    target = str(tmp_path / "backups")
    _ = save(
        target,
        kind="good",
        slot="1",
        name="Good",
        device_id="d",
        source="s",
        blocks={},
    )
    corrupt_path = str(tmp_path / "backups" / "corrupt.json")
    with open(corrupt_path, "w", encoding="utf-8") as f:
        f.write("not json")
    backups = list_backups(target)
    kinds = {b.kind for b in backups}
    assert "good" in kinds
    corrupt_entries = [b for b in backups if b.error is not None]
    assert len(corrupt_entries) >= 1
    assert any("Expecting" in (b.error or "") for b in corrupt_entries)
