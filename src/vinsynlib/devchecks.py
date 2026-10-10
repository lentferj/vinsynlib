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

"""Checks every project in the family should be running, written once.

These are not lints. They are the invariants that let nine separately
developed programs stay one family, and each of them was a bug that
actually happened here:

**A test must not write ``config.toml`` into the checkout.** The path is
relative, on purpose -- it is a disposable per-checkout cache -- and being
gitignored is exactly what makes this worth checking rather than
remembering. One was found next to the source, dated during a test run.

**A project must not import another project in the family.** ``emorphed``
had a function that imported ``nano.config``: ``nanosyned``'s package,
which of course is not installed next to it. It was a copy-paste slip from
the sibling the function was ported from, and it would have raised
``ImportError`` the moment ``--config`` was used.

**A project's public vocabulary must be declared.** A tool that has not
said what its instrument calls a stored sound has not finished being part
of this family, and a default would let it drift unnoticed.
"""

from __future__ import annotations

import ast
import os
import sys
from collections.abc import Iterable, Iterator, Sequence

__all__ = [
    "FAMILY_THIRD_PARTY",
    "check_foreign_imports",
    "config_saves_without_path",
    "foreign_imports",
    "iter_test_sources",
]

#: Third-party modules every project in the family legitimately imports.
FAMILY_THIRD_PARTY = frozenset({"textual", "rtmidi", "rich", "vinsynlib"})


def iter_test_sources(test_dir: str) -> Iterator[tuple[str, ast.Module]]:
    """Every test module in a directory, as ``(filename, parsed)``."""
    for name in sorted(os.listdir(test_dir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        path = os.path.join(test_dir, name)
        with open(path, encoding="utf-8") as handle:
            yield name, ast.parse(handle.read())


#: How many positional arguments each writer takes before ``path``. A table
#: rather than a single number, because the arity is not uniform:
#: ``save_ports`` takes two port names and ``path`` is the third. A call that
#: passes no more than this many positional arguments, and no ``path=``
#: keyword, has no path and writes ``./config.toml`` into the checkout.
#:
#: A project's own writer over the same store is listed under its own name.
#: An unlisted one falls back to :data:`_DEFAULT_WRITER_ARITY`.
_WRITER_ARITY: dict[str, int] = {
    # vinsynlib's own.
    "update": 0,
    "save_channel": 1,
    "save_port": 1,
    "save_recv_port": 1,
    "save_device_id": 1,
    "save_ports": 2,
    # The family's wrappers over the same store.
    "save_last_port": 1,
    "save_last_recv_port": 1,
    "save_exclusive_channel": 1,
    "save_last_ports": 2,
}

#: Assumed for a writer :data:`_WRITER_ARITY` has not been told about. One is
#: the shape these methods share -- the value or values, then the path -- and
#: a project that grows a two-value writer adds its name above. Being wrong
#: in this direction misses a call rather than reporting one that is fine.
_DEFAULT_WRITER_ARITY = 1


def config_saves_without_path(test_dir: str) -> list[str]:
    """Test calls of ``config.save_*`` that do not name a file.

    Returns one ``file:lineno name`` string per offender. A save with no
    path writes ``config.toml`` into whatever directory pytest was started
    from, which is the checkout in practice.

    Deciding whether a call names a path is per-method, not one number:
    ``save_ports(send, recv, path)`` takes two values before it, so a
    "two arguments means it has a path" rule reads
    ``config.save_ports("In", "Out")`` as safe and lets it write into the
    checkout. See :data:`_WRITER_ARITY`.

    Only calls on a name bound to ``config`` are examined, so a test that
    imports the module under another spelling is not covered.
    """
    offenders: list[str] = []
    for name, tree in iter_test_sources(test_dir):
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr.startswith("save_")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "config"
            ):
                continue
            before = _WRITER_ARITY.get(node.func.attr, _DEFAULT_WRITER_ARITY)
            named = len(node.args) > before or any(
                kw.arg == "path" for kw in node.keywords
            )
            if not named:
                offenders.append(f"{name}:{node.lineno} {node.func.attr}")
    return offenders


def own_namespaces(*packages: str) -> frozenset[str]:
    """The top-level names a project owns, given its package names."""
    return frozenset(packages)


def foreign_imports(
    path: str,
    *,
    own: Iterable[str],
    third_party: Iterable[str] = FAMILY_THIRD_PARTY,
) -> list[str]:
    """Top-level imports in one file that belong to nobody here.

    A name is foreign when it is not the standard library, not one of this
    project's own packages, and not in the third-party allow-list. The
    point is to catch a sibling project's package name in a function that
    was ported from it -- an import that works in the project it was copied
    from and raises ``ImportError`` in this one.
    """
    allowed = set(own) | set(third_party)
    stdlib: frozenset[str] = getattr(sys, "stdlib_module_names", frozenset())
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` has no module: a relative import is by
            # definition this project's own.
            if node.level:
                continue
            names = [node.module or ""]
        else:
            continue
        for full in names:
            top = full.split(".")[0]
            if not top or top in allowed or top in stdlib:
                continue
            found.append(f"{os.path.basename(path)}:{node.lineno} {full}")

    return sorted(set(found))


def check_foreign_imports(
    paths: Sequence[str],
    *,
    own: Iterable[str],
    third_party: Iterable[str] = FAMILY_THIRD_PARTY,
) -> list[str]:
    """:func:`foreign_imports` over several files."""
    out: list[str] = []
    for path in paths:
        out.extend(foreign_imports(path, own=own, third_party=third_party))
    return out
