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

"""The favourites database: what it promises, and what it refuses."""

from __future__ import annotations

import os
import threading
from typing import Any

import pytest

from vinsynlib import favorites


@pytest.fixture
def store(tmp_path: Any) -> Any:
    with favorites.Favorites(
        str(tmp_path / "favorites.db"), app_name="x5ded"
    ) as opened:
        yield opened


def test_an_upsert_preserves_the_original_date(store: Any) -> None:
    first = store.add("A", 1, name="Amber Wash")
    again = store.add("A", 1, name="Amber Wash", rating=3)
    assert again.added == first.added
    assert store.get("A", 1).rating == 3


def test_unfavouriting_keeps_the_annotations(store: Any) -> None:
    """Two presses of `f` used to destroy a rating, tags, a note and a date.

    Silently, on the one store these tools call the user's own. The row is
    kept and an `active` flag cleared instead, so the same keystroke brings
    them all back.
    """
    store.add("A", 1, name="Amber", rating=4, tags="pad", note="slow")
    assert store.remove("A", 1) is True
    assert store.get("A", 1) is None
    assert ("A", 1) not in store

    dormant = store.dormant()
    assert len(dormant) == 1
    assert dormant[0].rating == 4
    assert dormant[0].tags == "pad"
    assert dormant[0].note == "slow"


def test_refavouriting_restores_rather_than_starts_blank(store: Any) -> None:
    store.add("A", 1, name="Amber", rating=5, tags="pad", note="slow")
    store.remove("A", 1)
    store.toggle("A", 1, name="Amber")
    back = store.get("A", 1)
    assert (back.rating, back.tags, back.note) == (5, "pad", "slow")


def test_refavouriting_uses_the_new_name_when_there_was_none(
    store: Any,
) -> None:
    store.add("A", 1, name="Amber", rating=5)
    store.remove("A", 1)
    store.toggle("A", 1, name="Different Name")
    assert store.get("A", 1).name == "Amber"


def test_toggle_reports_the_state_it_leaves_behind(store: Any) -> None:
    assert store.toggle("A", 1, name="x") is True
    assert store.toggle("A", 1, name="x") is False
    assert store.toggle("A", 1, name="x") is True


def test_forgetting_is_the_hard_delete(store: Any) -> None:
    store.add("A", 1, name="Amber", rating=5)
    assert store.forget("A", 1) is True
    assert store.dormant() == []


def test_setting_a_rating_does_not_blank_the_tags(store: Any) -> None:
    """`add` takes every field, so a partial edit must merge."""
    store.add("A", 1, name="Amber", tags="pad", note="slow")
    store.set_rating("A", 1, 5)
    rated = store.get("A", 1)
    assert rated is not None
    assert rated.tags == "pad"
    assert rated.note == "slow"


def test_a_rating_outside_the_scale_is_refused(store: Any) -> None:
    store.add("A", 1)
    with pytest.raises(ValueError, match="outside 0-5"):
        store.set_rating("A", 1, 6)


def test_tags_are_trimmed_and_deduplicated(store: Any) -> None:
    store.set_tags("A", 1, " pad , Pad ,lead ,")
    assert store.get("A", 1).tags == "pad, lead"
    assert store.get("A", 1).tag_list == ["pad", "lead"]


def test_with_tag_matches_whole_tags_only(store: Any) -> None:
    """A LIKE '%tag%' would make "pad" match "padded"."""
    store.set_tags("A", 1, "padded")
    store.set_tags("A", 2, "pad")
    assert [f.number for f in store.with_tag("pad")] == [2]


def test_search_escapes_like_wildcards(store: Any) -> None:
    """A search for "%" matched everything, and looked like a real hit."""
    store.add("A", 1, name="100% wet")
    store.add("A", 2, name="dry")
    assert [f.number for f in store.search("%")] == [1]
    assert [f.number for f in store.search("_")] == []


def test_search_covers_tags_and_notes(store: Any) -> None:
    store.add("A", 1, name="Amber", note="needs the tape delay")
    assert [f.number for f in store.search("tape")] == [1]


def test_ordering_is_validated_against_a_fixed_set(store: Any) -> None:
    """`order` reaches here from the command line, and ORDER BY is the one
    clause a parameter placeholder cannot carry."""
    for order in ("added", "rating", "bank", "name"):
        store.all(order=order)
    with pytest.raises(ValueError, match="unknown order"):
        store.all(order="bank_id; DROP TABLE favorites")


def test_keys_are_one_query_not_one_per_row(store: Any) -> None:
    store.add("A", 1)
    store.add("B", 2)
    assert store.keys() == {"A:001", "B:002"}
    assert store.keys_for_bank("A") == {1}


def test_the_key_formats_to_three_digits(store: Any) -> None:
    assert store.add("A", 7, name="x").key == "A:007"


def test_split_key_accepts_a_pair_or_a_string() -> None:
    assert favorites.split_key(("A", 12)) == ("A", 12)
    assert favorites.split_key("A:012") == ("A", 12)


def test_contains_accepts_either_form(store: Any) -> None:
    store.add("A", 12)
    assert ("A", 12) in store
    assert "A:012" in store
    assert "A:013" not in store


def test_refreshing_names_covers_dormant_rows_too(store: Any) -> None:
    store.add("A", 1, name="old")
    store.add("A", 2, name="old")
    store.remove("A", 2)
    changed = store.refresh_names(lambda _bank, _num: "new")
    assert changed == 2
    assert store.get("A", 1).name == "new"


def test_an_unknown_name_source_changes_nothing(store: Any) -> None:
    store.add("A", 1, name="old")
    assert store.refresh_names(lambda _b, _n: None) == 0
    assert store.get("A", 1).name == "old"


def test_the_store_is_usable_from_a_worker_thread(store: Any) -> None:
    """SQLite refuses cross-thread use by default, and a Textual worker
    that so much as asks for len() raises out of the worker."""
    store.add("A", 1)
    seen: list[int] = []
    worker = threading.Thread(target=lambda: seen.append(len(store)))
    worker.start()
    worker.join()
    assert seen == [1]


def test_the_directory_is_created_if_it_is_not_there(tmp_path: Any) -> None:
    path = tmp_path / "new" / "deeper" / "favorites.db"
    with favorites.Favorites(str(path)) as opened:
        assert len(opened) == 0
    assert os.path.exists(path)


def test_a_database_from_a_newer_build_is_refused(tmp_path: Any) -> None:
    path = str(tmp_path / "favorites.db")
    with favorites.Favorites(path) as opened:
        opened._db.execute(
            f"PRAGMA user_version = {favorites.SCHEMA_VERSION + 1}"
        )
        opened._db.commit()
    with pytest.raises(RuntimeError, match="newer"):
        favorites.Favorites(path, app_name="x5ded")


def test_a_v1_database_gains_the_active_column(tmp_path: Any) -> None:
    """The upgrade every project in the family needs to survive."""
    import sqlite3

    path = tmp_path / "favorites.db"
    db = sqlite3.connect(path)
    db.execute(
        """
        CREATE TABLE favorites (
            bank_id TEXT    NOT NULL,
            number  INTEGER NOT NULL,
            name    TEXT    NOT NULL DEFAULT '',
            rating  INTEGER NOT NULL DEFAULT 0,
            tags    TEXT    NOT NULL DEFAULT '',
            note    TEXT    NOT NULL DEFAULT '',
            added   REAL    NOT NULL DEFAULT 0,
            PRIMARY KEY (bank_id, number)
        );
        """
    )
    db.execute(
        "INSERT INTO favorites VALUES ('A', 1, 'Old', 5, 'pad', 'n', 1)"
    )
    db.execute("PRAGMA user_version = 1")
    db.commit()
    db.close()

    with favorites.Favorites(str(path)) as opened:
        assert len(opened) == 1
        kept = opened.get("A", 1)
        assert kept is not None
        assert kept.rating == 5
        opened.remove("A", 1)
        dormant = opened.dormant()
        assert len(dormant) == 1
        assert dormant[0].rating == 5


# --- where the file lives ----------------------------------------------------


def _home(monkeypatch: Any, path: str) -> None:
    """Point ``~`` at ``path`` on every platform.

    Patching HOME is not enough. ``os.path.expanduser`` reads HOME on POSIX
    and USERPROFILE on Windows, so on a Windows runner the library resolved
    the *real* home directory while these tests compared against a temporary
    one -- three failures that no amount of running them here would show.

    Patching ``expanduser`` itself tests the branch under test rather than
    the host's convention for saying where home is, which is the thing that
    differs.
    """
    monkeypatch.setattr(os.path, "expanduser", lambda _path="~": path)


def test_xdg_data_home_is_honoured_when_absolute(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert favorites.data_dir("rxved") == str(tmp_path / "rxved")


def test_a_relative_xdg_data_home_is_ignored(
    monkeypatch: Any, tmp_path: Any
) -> None:
    """XDG says a relative XDG_DATA_HOME must be ignored, so a stray value
    falls back rather than creating a directory wherever the process was
    started."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
    _home(monkeypatch, str(tmp_path))
    assert favorites.data_dir("rxved") == str(
        tmp_path / ".local" / "share" / "rxved"
    )


def test_windows_prefers_local_app_data(
    monkeypatch: Any, tmp_path: Any
) -> None:
    """Roaming copies files wholesale at logon and logoff, and a SQLite
    database caught mid-write by that copy is a known way to corrupt one."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert favorites.data_dir("p2ked") == str(tmp_path / "Local" / "p2ked")


def test_windows_without_local_app_data_uses_roaming(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert favorites.data_dir("p2ked") == str(tmp_path / "Roaming" / "p2ked")


def test_windows_with_neither_falls_back_to_xdg(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert favorites.data_dir("p2ked") == str(tmp_path / "p2ked")


def test_macos_uses_application_support(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    _home(monkeypatch, str(tmp_path))
    assert favorites.data_dir("ensqsqed") == str(
        tmp_path / "Library" / "Application Support" / "ensqsqed"
    )


def test_macos_with_no_home_falls_back_to_xdg(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    # A "~" that did not expand: not an absolute path, so the macOS branch
    # has nowhere to put anything and falls through to XDG.
    _home(monkeypatch, "~")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert favorites.data_dir("ensqsqed") == str(tmp_path / "ensqsqed")


def test_the_default_path_is_the_database_in_the_data_directory() -> None:
    assert favorites.default_path("kwsed").endswith(
        os.path.join("kwsed", "favorites.db")
    )


def test_bound_names_the_application_it_binds() -> None:
    bound = favorites.bind("s3ked")
    assert bound.app_name == "s3ked"
    assert bound.default_path().endswith(os.path.join("s3ked", "favorites.db"))
    with bound.store(":memory:") as opened:
        assert opened.path == ":memory:"
