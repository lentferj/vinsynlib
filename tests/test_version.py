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

"""is_compatible_version is shared by every tool in the family's entry
point, so it gets its own test module rather than living inside test_ux
with the rest of the command-line checks.
"""

from __future__ import annotations

import pytest

from vinsynlib import is_compatible_version

#: The contract the family has settled on, exercised by every entry.test.
MINIMUM = (0, 1, 0)


@pytest.mark.parametrize(
    "version, expected",
    [
        # Equal and above.
        ("0.1.0", True),
        ("0.1.1", True),
        ("0.2.0", True),
        ("1.0.0", True),
        ("10.20.30", True),
        # Short forms pad missing components to zero.
        ("0.1", True),
        ("0", False),
        ("1", True),
        # Below the minimum.
        ("0.0.9", False),
        ("0.0.0", False),
        # Non-numeric input is refused rather than mis-parsed.
        ("not-a-version", False),
        ("0.1.x", False),
    ],
)
def test_the_contract_entries_the_family_uses(
    version: str, expected: bool
) -> None:
    assert is_compatible_version(version, MINIMUM) is expected


def test_a_too_new_minimum_is_answered_by_the_version_string() -> None:
    assert is_compatible_version("0.1.0", (1, 0, 0)) is False


def test_a_missing_version_is_not_compatible() -> None:
    """A library that cannot report its version is unusable, not compatible."""
    assert is_compatible_version(None, MINIMUM) is False  # type: ignore[arg-type]
