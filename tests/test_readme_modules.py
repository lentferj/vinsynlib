# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Guard: every real module is named in the README's module tree."""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.join(HERE, os.pardir, "src", "vinsynlib")
README = os.path.join(HERE, os.pardir, "README.md")


def _module_names() -> list[str]:
    """Every non-dunder module in the package, by filename."""
    names: list[str] = []
    for directory in (PACKAGE, os.path.join(PACKAGE, "ui")):
        for name in os.listdir(directory):
            if name.endswith(".py") and name != "__init__.py":
                names.append(name)
    return names


def test_every_module_appears_in_the_readme() -> None:
    with open(README, encoding="utf-8") as handle:
        readme = handle.read()
    missing = [name for name in _module_names() if name not in readme]
    assert not missing, f"modules absent from README.md: {missing}"
