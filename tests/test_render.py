# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vinsynlib.render import progress, table


def test_empty_rows_returns_empty_param() -> None:
    assert table(["h"], [], empty="") == ""
    assert table(["h"], [], empty="(nothing)") == "(nothing)"
    assert table([], [], empty="x") == "x"


def test_zero_row_no_crash() -> None:
    assert table(["a", "b"], []) == ""
    assert table(["a"], []) == ""


def test_table_exact_output() -> None:
    result = table(["name", "val"], [["a", "1"], ["bb", "22"]])
    lines = result.split("\n")
    assert lines[0] == "name | val"
    assert lines[1] == "---- | ---"
    assert lines[2] == "   a |   1"
    assert lines[3] == "  bb |  22"


def test_empty_headers_graceful() -> None:
    result = table([], [["x"]])
    assert "x" in result


def test_single_row() -> None:
    result = table(["h"], [["only"]])
    assert result.startswith("   h\n----")


def test_width_zero_columns() -> None:
    result = table(["", ""], [["", ""]])
    # Should not crash; produces minimal lines
    assert result is not None


def test_progress_format() -> None:
    assert progress("load", 2, 5) == "\r  load 2/5"
    assert progress("x", 0, 0) == "\r  x 0/0"


def test_no_textual_import() -> None:
    # Module must import without Textual
    import vinsynlib.render

    assert vinsynlib.render.table is not None
