# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

from __future__ import annotations

from vinsynlib.favorites import rating_cell


def test_rating_zero_is_blank() -> None:
    assert rating_cell(0) == ""


def test_exact_outputs_at_scale_5() -> None:
    assert rating_cell(1) == "★····"
    assert rating_cell(3) == "★★★··"
    assert rating_cell(5) == "★★★★★"


def test_scale_parameter_works() -> None:
    assert rating_cell(2, scale=3) == "★★·"
    assert rating_cell(4, scale=10) == "★★★★······"


def test_star_never_appears() -> None:
    for r in range(6):
        result = rating_cell(r)
        assert "*" not in result


def test_zero_does_not_produce_dots() -> None:
    assert rating_cell(0) == ""
    assert "·" not in rating_cell(0)
