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

"""The checks that keep the family one family.

Each function here answers one question and returns the problems it found
as a list of sentences, so a project's test can be the whole contract in a
dozen lines:

    from vinsynlib import conformance

    def test_the_family_contract():
        problems = (
            conformance.check_flags(build_parser(), required={"port", "demo"})
            + conformance.check_bindings(X5dedApp, channel=True)
            + conformance.check_legend(KEY_HINTS)
        )
        assert not problems, "\\n".join(problems)

Returning sentences rather than asserting is deliberate. A test that says
``--midi-channel is not a name this family uses; use --device-channel`` is
worth more than one that says ``False``.

What is checked, and why only these:

* **Flags.** The name, the help text and the old spelling all come from
  :mod:`vinsynlib.spec`, so a tool cannot quietly reword ``--scan`` or drop
  its alias without a test noticing.
* **Bindings.** The shared keys bind the shared actions. A tool that
  renames ``f`` has to say why, in its own test.
* **The legend.** The shared blocks appear, in the shared order, and the
  tool's own hints sit in the one place the family leaves room for them --
  because a legend is a promise about which keys work, and a promise that
  drifts is worse than no promise.
* **Terms.** The tool declared its vocabulary, and the words it uses for
  the concepts it has are the declared ones.

Not checked, deliberately: the hardware. Which bank byte selects what is
the instrument's business and the family's has no opinion.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from . import keys as keys_module
from . import spec
from .terms import Terminology

__all__ = [
    "check_bindings",
    "check_flags",
    "check_legend",
    "check_terms",
]


def check_flags(
    parser: argparse.ArgumentParser,
    *,
    required: Sequence[str] = (),
    forbidden: Sequence[str] = (),
) -> list[str]:
    """Every required option present, worded the family's way.

    ``required`` names canonical flags from :data:`spec.CANONICAL_FLAGS`.
    A required flag that is missing, or present with different help text,
    or present without its documented older spelling, is a problem.
    """
    problems: list[str] = []
    known = {action.dest: action for action in parser._actions}
    by_name = {f.name: f for f in spec.CANONICAL_FLAGS}

    for name in required:
        flag = by_name.get(name)
        if flag is None:
            problems.append(
                f"{name!r} is not a flag this family uses; have "
                f"{', '.join(sorted(by_name))}"
            )
            continue
        action = known.get(flag.name.replace("-", "_"))
        if action is None:
            problems.append(f"--{name} is missing")
            continue
        if (action.help or "") != flag.help:
            problems.append(
                f"--{name} help text differs from the family's:\n"
                f"    family: {flag.help}\n"
                f"    here:   {action.help}"
            )
        present = set(action.option_strings)
        missing = set(flag.options()) - present
        if missing:
            problems.append(
                f"--{name} no longer accepts "
                f"{', '.join(sorted(missing))}; older command lines use it"
            )

    for name in forbidden:
        if name.replace("-", "_") in known:
            problems.append(f"--{name} should not be offered by this tool")

    return problems


def _bindings_of(app: Any) -> dict[str, str]:
    """``key -> action name`` for one App class."""
    out: dict[str, str] = {}
    for binding in getattr(app, "BINDINGS", []):
        key = getattr(binding, "key", None)
        action = getattr(binding, "action", None)
        if key and isinstance(action, str):
            out[key] = action
    return out


def _shared(
    tier: str,
    *,
    favourites: bool,
    channel: bool,
    select: bool,
) -> list[keys_module.Key]:
    """The shared keys that apply to a tool with these concepts.

    One place decides what "applies" means, so that the key check and the
    action check cannot drift into disagreeing about which keys a tool is
    being asked about.
    """
    table = (
        keys_module.EDITOR_KEYS
        if tier == "editor"
        else keys_module.BROWSER_KEYS
    )
    if tier != "editor" and favourites:
        table = table + keys_module.FAVOURITE_KEYS

    wanted: list[keys_module.Key] = []
    for key in table:
        if key.key == "enter" and not select:
            continue
        if not channel and key.legend in ("[ ] channel", "c set channel"):
            continue
        wanted.append(key)
    return wanted


def check_bindings(
    app: Any,
    *,
    tier: str = "browser",
    favourites: bool = True,
    channel: bool = True,
    select: bool = True,
) -> list[str]:
    """The shared keys bind the shared actions, or say why not.

    The keyword flags mirror :func:`keys.legend`: a tool without a
    favourites store is not asked for ``f``.
    """
    have = _bindings_of(app)
    problems: list[str] = []

    # The key side: is the family's key bound to the family's action?
    shared = _shared(
        tier, favourites=favourites, channel=channel, select=select
    )
    for key in shared:
        action = have.get(key.key)
        if action is None:
            problems.append(
                f"{key.key} is not bound; the family binds it to {key.action}"
            )
        elif action != key.action:
            problems.append(
                f"{key.key} is bound to {action}; the family binds it to "
                f"{key.action}"
            )

    # The action side: where did each family action actually go? A key that
    # has been *renamed* -- f moved to a -- leaves every family key unbound,
    # and checking only the keys would report a list of unbound keys and say
    # nothing about where the action went.
    where: dict[str, list[str]] = {}
    for app_key, action in have.items():
        where.setdefault(action, []).append(app_key)
    for key in shared:
        if key.key in where.get(key.action, []):
            continue
        elsewhere = ", ".join(sorted(where.get(key.action, []))) or "nothing"
        problems.append(
            f"{key.action} is not reachable from {key.key}; it is bound to "
            f"{elsewhere}"
        )
    return problems


def check_legend(
    blocks: Sequence[str],
    *,
    extras: Sequence[str] = (),
    favourites: bool = True,
    channel: bool = True,
    select: bool = True,
) -> list[str]:
    """The shared hints appear, in the shared order, with extras in place."""
    expected = keys_module.legend(
        extras, favourites=favourites, channel=channel, select=select
    )
    problems: list[str] = []
    for hint in expected:
        if hint not in blocks:
            problems.append(f"the legend is missing {hint!r}")
    for hint in blocks:
        if hint not in expected:
            problems.append(
                f"the legend shows {hint!r}, which is not in the family's"
            )
    shared = [
        b for b in blocks if b in keys_module.CANONICAL_LEGEND or b in extras
    ]
    order = [
        b
        for b in keys_module.legend(
            extras, favourites=favourites, channel=channel, select=select
        )
        if b in shared
    ]
    if [b for b in shared if b in order] != order:
        problems.append(
            "the legend's hints are not in the family's order: expected "
            + ", ".join(order)
        )
    return problems


def check_terms(terms: Terminology) -> list[str]:
    """The declared vocabulary is the one the family allows."""
    problems: list[str] = []
    try:
        Terminology(
            app_name=terms.app_name,
            sound=terms.sound,
            container=terms.container,
            device=terms.device,
        )
    except ValueError as exc:
        problems.append(str(exc))
    return problems
