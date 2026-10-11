# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Catalog layer (§3.6): display-numbered keys, live layer, sidecar."""

from __future__ import annotations

import json
import pathlib

import pytest

from vinsynlib import livenames
from vinsynlib.catalog import (
    UNNAMED,
    Catalog,
    Entry,
    display_to_wire,
    dump,
    empty,
    load,
    make_key,
    split_key,
    wire_to_display,
)


def test_key_without_kind_is_bank_and_number() -> None:
    assert Entry("USER", 1, "Init").key == "USER:001"
    assert Entry("USER", 42, "Pad").key == "USER:042"


def test_key_with_kind_carries_it() -> None:
    assert Entry("RAM1", 7, "Str", kind="PERF").key == "RAM1:PERF:007"
    assert Entry("RAM1", 7, "Str").key == "RAM1:007"


def test_key_rejects_colon_in_bank_or_kind() -> None:
    with pytest.raises(ValueError):
        Entry("A:B", 1, "x")
    with pytest.raises(ValueError):
        Entry("A", 1, "x", kind="P:Q")


def test_split_key_round_trip() -> None:
    assert split_key("USER:001") == ("USER", "", 1)
    assert split_key("RAM1:PERF:007") == ("RAM1", "PERF", 7)
    assert split_key(make_key("B", 9, "K")) == ("B", "K", 9)


def test_split_key_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        split_key("NOPE")
    with pytest.raises(ValueError):
        split_key("A:B:C:D")
    with pytest.raises(ValueError):
        split_key("A:xx")


def test_wire_to_display_defaults_to_pc_plus_one() -> None:
    assert wire_to_display(0) == 1
    assert wire_to_display(127) == 128
    assert display_to_wire(1) == 0
    assert display_to_wire(wire_to_display(64)) == 64


def test_wire_display_round_trip_with_offset() -> None:
    assert wire_to_display(0, offset=0) == 0
    assert display_to_wire(5, offset=0) == 5


def test_lookup_len_bool_has() -> None:
    assert len(empty()) == 0
    assert not empty()
    cat = Catalog([Entry("USER", 1, "Init"), Entry("PST", 2, "Pad")])
    assert len(cat) == 2
    assert bool(cat)
    assert cat.entry("USER", 1) is not None
    assert cat.entry("USER", 2) is None
    assert cat.name("PST", 2) == "Pad"
    assert cat.name("PST", 3) is None
    assert cat.has("USER")
    assert not cat.has("NOPE")


def test_kind_defaults_to_empty_string() -> None:
    cat = Catalog([Entry("RAM1", 7, "Str", kind="PERF")])
    assert cat.entry("RAM1", 7) is None
    assert cat.entry("RAM1", 7, "PERF") is not None
    assert cat.has("RAM1")
    assert cat.has("RAM1", kind="PERF")
    assert not cat.has("RAM1", kind="PATCH")


def test_display_name_prefers_live_then_print_then_unnamed() -> None:
    cat = Catalog([Entry("USER", 1, "Init")])
    assert cat.display_name("USER", 1) == "Init"
    assert cat.display_name("USER", 9) == UNNAMED
    cat.set_live_name("USER", 1, "Mine")
    assert cat.display_name("USER", 1) == "Mine"
    assert cat.is_live("USER", 1)
    assert not cat.is_live("USER", 9)
    assert cat.live_name("USER", 9) is None


def test_differs_needs_both_sources_and_a_difference() -> None:
    cat = Catalog([Entry("USER", 1, "Init")])
    assert not cat.differs("USER", 1)
    cat.set_live_name("USER", 1, "Init")
    assert not cat.differs("USER", 1)
    cat.set_live_name("USER", 1, "Mine")
    assert cat.differs("USER", 1)
    cat.set_live_name("USER", 9, "Mine")
    assert not cat.differs("USER", 9)


def test_search_hits_both_layers_case_insensitively() -> None:
    cat = Catalog(
        [
            Entry("USER", 1, "Analogue!"),
            Entry("PST", 2, "Soft Pad"),
        ]
    )
    cat.set_live_name("PST", 2, "My Strings")
    assert cat.search("") == []
    assert cat.search("  ") == []
    assert ("USER", "", 1, "Analogue!") in cat.search("analog")
    hits = cat.search("strings")
    assert hits == [("PST", "", 2, "My Strings")]
    assert cat.search("soft") == [("PST", "", 2, "My Strings")]


def test_search_kind_filter_is_whole_word() -> None:
    cat = Catalog(
        [
            Entry("B", 1, "Same", kind="PATCH"),
            Entry("B", 2, "Same", kind="PATCHED"),
            Entry("B", 3, "Same"),
        ]
    )
    assert [row[2] for row in cat.search("same")] == [3, 1, 2]
    assert [row[2] for row in cat.search("same", kind="PATCH")] == [1]
    assert [row[2] for row in cat.search("same", kind="")] == [3]


def test_load_converts_wire_pc_rows_at_the_edge(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "catalog.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "source": "manual",
                "generated": "today",
                "banks": {
                    "USER": [{"pc": 0, "name": "First"}],
                    "PST": [{"n": 2, "name": "Second"}],
                },
            },
            handle,
        )
    cat = load(path)
    assert cat.name("USER", 1) == "First"
    assert cat.entry("USER", 0) is None
    assert cat.name("PST", 2) == "Second"
    assert cat.source == "manual"


def test_load_missing_is_empty(
    tmp_path: pathlib.Path,
) -> None:
    assert not load(str(tmp_path / "absent.json"))
    assert not load(None)


def test_load_rejects_non_dict_banks(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "catalog.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"banks": ["not", "a", "dict"]}, handle)
    with pytest.raises(ValueError, match="is not a catalog"):
        load(path)


def test_load_skips_bad_rows(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "catalog.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "banks": {
                    "USER": [
                        {"n": 1, "name": "Good"},
                        {"n": 2},
                        {"name": "NoNumber"},
                        "junk",
                    ]
                }
            },
            handle,
        )
    cat = load(path)
    assert len(cat) == 1
    assert cat.name("USER", 1) == "Good"


def test_dump_load_round_trip_keeps_kind(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "out" / "catalog.json")
    cat = Catalog(
        [Entry("B", 1, "A"), Entry("B", 7, "S", kind="PERF")],
        source="s",
        generated="g",
    )
    dump(cat, path)
    back = load(path)
    assert back.name("B", 1) == "A"
    assert back.name("B", 7, "PERF") == "S"
    assert back.source == "s"


def test_live_round_trip_persists_and_reloads(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "live-names.json")
    cat = Catalog([Entry("USER", 1, "Init")])
    cat.set_live_name("USER", 1, "Mine")
    assert cat.live_name("USER", 1) is not None
    livenames.save(path, {"USER:001": "Mine", "B:K:007": "Kinded"})
    assert livenames.load(path) == {"USER:001": "Mine", "B:K:007": "Kinded"}
    fresh = Catalog([Entry("USER", 1, "Init")])
    assert livenames.apply_to(fresh, path) == 2
    assert fresh.live_name("USER", 1) == "Mine"
    assert fresh.live_name("B", 7, "K") == "Kinded"
    assert fresh.display_name("USER", 1) == "Mine"


def test_live_load_missing_or_corrupt_is_empty(
    tmp_path: pathlib.Path,
) -> None:
    assert livenames.load(str(tmp_path / "absent.json")) == {}
    bad = str(tmp_path / "bad.json")
    with open(bad, "w", encoding="utf-8") as handle:
        handle.write("{nope")
    assert livenames.load(bad) == {}
    flat = str(tmp_path / "flat.json")
    with open(flat, "w", encoding="utf-8") as handle:
        json.dump(["not", "a", "dict"], handle)
    assert livenames.load(flat) == {}


def test_live_apply_skips_keys_that_do_not_parse(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "live-names.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"USER:001": "Mine", "junk": "Bad"}, handle)
    fresh = Catalog()
    assert livenames.apply_to(fresh, path) == 1
    assert fresh.live_name("USER", 1) == "Mine"


def test_live_key_matches_catalog_key() -> None:
    assert livenames.key("USER", 1) == Entry("USER", 1, "x").key
    assert livenames.key("B", 7, "K") == Entry("B", 7, "x", "K").key


def test_load_ignores_project_side_extras(
    tmp_path: pathlib.Path,
) -> None:
    path = str(tmp_path / "catalog.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "banks": {
                    "USER": [
                        {
                            "n": 1,
                            "name": "Init",
                            "category": "PNO",
                            "voices": 4,
                        }
                    ]
                }
            },
            handle,
        )
    cat = load(path)
    assert cat.name("USER", 1) == "Init"
