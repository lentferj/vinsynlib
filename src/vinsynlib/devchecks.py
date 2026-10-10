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
import copy
import difflib
import os
import sys
from collections.abc import Iterable, Iterator, Sequence

__all__ = [
    "FAMILY_THIRD_PARTY",
    "check_foreign_imports",
    "config_saves_without_path",
    "foreign_imports",
    "iter_test_sources",
    "release_parts_drift",
    "release_parts_invariants",
]

#: Third-party modules every project in the family legitimately imports.
FAMILY_THIRD_PARTY = frozenset({"textual", "rtmidi", "rich", "vinsynlib"})

#: The name of the private helper every project's ``entry.py`` carries. It is
#: a copy *on purpose* -- a version gate must not import the library it is
#: checking, because a library too old to contain the gate would raise, which
#: is the exact failure the gate exists to prevent.
_PARTS_FUNCTION = "_release_parts"


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


# --- the version gate copies -------------------------------------------------
#
# Every project carries a copy of `_release_parts`. The duplication is
# deliberate and must never be "fixed" by making the gate import the library
# it checks. What it needs is a check that the copies stay identical, and
# that is what this section is.


def _canonical_path() -> str:
    """The library's own ``__init__.py`` -- the copy everything must match."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "__init__.py"
    )


def _parts_function(path: str) -> tuple[ast.FunctionDef | None, str | None]:
    """The top-level ``_release_parts`` in one file, and why there isn't one.

    The two failure cases are separated on purpose. A project adopting this
    check gets the path wrong at least once, and "has no _release_parts to
    check" for a file that does not exist sends the reader looking in the
    wrong place entirely.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        return None, f"{path} could not be read ({exc})"
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, f"{path} is not valid Python ({exc})"
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == _PARTS_FUNCTION:
            return node, None
    return None, f"{path} has no {_PARTS_FUNCTION} to check"


def _normalised(node: ast.FunctionDef) -> ast.FunctionDef:
    """A copy of ``node`` with the two spellings that are not drift erased.

    The library names its first parameter ``version_string`` because its
    public function does; every project names it ``version``. The docstring's
    wording differs for the same reason. Neither is a difference in
    behaviour, so both are erased -- and nothing else is, which is what makes
    the comparison worth running.
    """
    first = node.args.args[0].arg
    clone = copy.deepcopy(node)
    body = clone.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        clone.body = body[1:]
    for arg in clone.args.args:
        if arg.arg == first:
            arg.arg = "first"
    for inner in ast.walk(clone):
        if isinstance(inner, ast.Name) and inner.id == first:
            inner.id = "first"
    return clone


def _guard_on(node: ast.FunctionDef, name: str) -> ast.If | None:
    """The ``if not <name>:`` in one function, if there is one."""
    for inner in ast.walk(node):
        if not isinstance(inner, ast.If):
            continue
        test = inner.test
        if (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Name)
            and test.operand.id == name
        ):
            return inner
    return None


def _refuses(arm: ast.If) -> bool:
    """Whether an ``if`` arm's body is exactly ``return None``."""
    return bool(arm.body) and all(
        isinstance(stmt, ast.Return)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is None
        for stmt in arm.body
    )


def release_parts_invariants(path: str) -> list[str]:
    """The four things any project's ``_release_parts`` must keep true.

    Checked against the copy in **one file**, and deliberately not against
    the library's own: if both sides of a comparison are wrong the
    comparison passes, so the library has to be held to these separately or
    the whole guard can be disarmed by editing the canonical and propagating
    the edit.

    Each invariant is here because breaking it produces a specific bad
    outcome rather than a general one:

    * a component with no leading digit **refused** rather than skipped --
      a ``break`` there reports a version it could not read as *compatible*,
      which is the guess the docstring exists to forbid, and it fails open;
    * the split bounded by ``width`` -- a hardcoded ``[:3]`` silently
      truncated any comparison wider than three components;
    * a **tuple** returned -- a list raises ``TypeError`` against a MINIMUM
      and stops every tool that uses it;
    * two parameters -- ``width`` is the width of the comparison and has to
      come from the caller.
    """
    function, missing = _parts_function(path)
    if function is None:
        return [missing]  # type: ignore[list-item]
    problems: list[str] = []

    names = [arg.arg for arg in function.args.args]
    if len(names) != 2 or names[1] != "width":
        problems.append(
            f"{path}: {_PARTS_FUNCTION} takes {names}; it needs two "
            "parameters with width last"
        )

    bounded = any(
        isinstance(node.slice, ast.Slice)
        and isinstance(node.slice.upper, ast.Name)
        and node.slice.upper.id == "width"
        for node in ast.walk(function)
        if isinstance(node, ast.Subscript)
    )
    if not bounded:
        problems.append(
            f"{path}: {_PARTS_FUNCTION} does not bound its split by `width`; "
            "a literal there truncated any comparison wider than three "
            "components, which was a bug once already"
        )

    # The dangerous break is the one in the guard's arm, not any break: the
    # inner loop breaks on the first non-digit by design, and that is what
    # makes "0.2rc1" read as 0.2. What must never happen is the outer loop
    # *skipping* a component it could not parse, which fails open.
    arm = _guard_on(function, "digits")
    if arm is not None:
        for node in ast.walk(arm):
            if isinstance(node, (ast.Break, ast.Continue)):
                problems.append(
                    f"{path}: {_PARTS_FUNCTION} uses "
                    f"{type(node).__name__.lower()} inside the "
                    "`if not digits` arm at line "
                    f"{node.lineno}, so a component it cannot parse would be "
                    "skipped instead of refused -- the gate then reports a "
                    "version it never read as compatible"
                )
        if not _refuses(arm):
            problems.append(
                f"{path}: {_PARTS_FUNCTION} does not `return None` when a "
                "component has no leading digit, so an unreadable version is "
                "guessed at instead of refused"
            )

    if not any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "tuple"
        for node in ast.walk(function)
    ):
        problems.append(
            f"{path}: {_PARTS_FUNCTION} does not return a tuple(), which is "
            "what makes it comparable against a MINIMUM"
        )
    return problems


def _library_version() -> str:
    """The version of the library file this module compares against.

    Read from the source rather than from ``importlib.metadata`` so that the
    version named in a message is the one belonging to the file the message
    is about.
    """
    try:
        with open(_canonical_path(), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError):  # pragma: no cover - our own file
        return "unknown"
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
        ):
            continue
        return str(node.value.value)
    return "unknown"  # pragma: no cover - our own file


def release_parts_drift(entry_path: str) -> list[str]:
    """Whether one project's ``_release_parts`` still matches the library's.

    Every project carries its own copy, so that a version gate never imports
    the library it is checking -- a library too old to contain the gate would
    raise, which is the failure the gate exists to prevent. That duplication
    is deliberate and must not be "fixed" by sharing it.

    What it needs is a check that the copies stay identical, and the reason
    is the shape of the failure when they do not: a drift lands in *one*
    tool, so the symptom is "s3ked is broken with this vinsynlib and the
    other nine work" -- a support ticket about one program, rather than a red
    build anyone can see.

    The comparison is against the **installed** library, because that is what
    the project's gate actually runs against. A virtualenv that has not been
    synced therefore reports drift that is only staleness, so the message
    names the version it compared against and the file it came from.

    A failing message carries a diff, not just a verdict: the point is to say
    *what* drifted, and a diff does that better than an enumeration would.
    """
    theirs, missing = _parts_function(entry_path)
    if theirs is None:
        return [missing]  # type: ignore[list-item]
    canonical = _canonical_path()
    ours, missing = _parts_function(canonical)
    if ours is None:  # pragma: no cover - the library's own file
        return [missing]  # type: ignore[list-item]

    problems = release_parts_invariants(entry_path)
    if ast.dump(_normalised(ours), include_attributes=False) == ast.dump(
        _normalised(theirs), include_attributes=False
    ):
        return problems

    problems.append(
        f"{entry_path}'s {_PARTS_FUNCTION} differs from the one in vinsynlib "
        f"{_library_version()} ({canonical}). A project's copy must stay "
        "identical to the library's; update this one, or the library's first "
        "and then this one."
    )
    problems.extend(
        "    " + line
        for line in difflib.unified_diff(
            ast.unparse(_normalised(ours)).splitlines(),
            ast.unparse(_normalised(theirs)).splitlines(),
            "library",
            "project",
            lineterm="",
        )
    )
    return problems
