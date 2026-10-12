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

"""Which build of a component is running, as far as it can be known.

A support report needs two names: the tool's and the library's, because
they are installed separately and only one of them is usually the bug.
So the question is asked per *distribution*, by name, the way
:func:`vinsynlib.cli` finds a version -- and this module is where the
answer lives, so the CLI and a help screen cannot drift apart.

The answer is tiered, and the tier is the point:

- a **checkout** can prove a commit, so it says the sha, and the tag that
  points at it when one does;
- a **release** cannot. A wheel is built from an sdist with no ``.git``
  in it, so no sha is knowable there -- and it does not need one: the
  family tags releases ``v<version>``, so ``0.4.1`` *is* the exact
  identity and resolves to one commit in the repository.

So a build with no commit is not a failure, and it must not be dressed
up as one. Nothing here runs ``git``, reads the network, or guesses: a
value that cannot be proved stays ``None``.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import distribution as _distribution
from importlib.metadata import version as _dist_version
from pathlib import Path
from urllib.parse import unquote, urlparse

__all__ = ["Build", "build_of", "version_of"]

#: A loose object lives at ``objects/xx/yyyy…``: two characters of
#: directory and at least one of file, so a sha shorter than this names
#: nothing that could be read.
_LOOSE_OBJECT_MINIMUM = 3


@dataclass(frozen=True, slots=True)
class Build:
    """One component's build, in the strongest terms that could be proved.

    ``version`` is the installed distribution's, or ``None`` for a
    checkout that was never installed -- a normal way to run these
    tools, and not an error. ``commit`` and ``tag`` are ``None`` exactly
    when they could not be known.
    """

    version: str | None
    commit: str | None = None
    tag: str | None = None


def version_of(distribution: str) -> str | None:
    """The installed version of ``distribution``, or ``None``.

    By name rather than by importing something: every tool in this
    family installs a distribution named exactly what the command is
    called, and a console script can be run from a virtualenv in which
    the package is not importable yet. ``PackageNotFoundError`` is not an
    error here -- a checkout that was never installed is a normal way to
    run these.
    """
    try:
        return _dist_version(distribution)
    except PackageNotFoundError:
        return None


def build_of(distribution: str, origin: str | None = None) -> Build:
    """Which build of ``distribution`` is running, as far as it can be known.

    ``origin`` is an optional path *inside* the component -- typically
    its ``__file__`` -- and is the last lead, for a checkout that was
    never installed and so has no distribution metadata at all.
    """
    version = version_of(distribution)
    commit, git_dir = _commit_for(distribution, origin)
    tag = _tag_of(git_dir, commit) if git_dir is not None else None
    return Build(version=version, commit=commit, tag=tag)


# --- where the checkout is ---------------------------------------------


def _commit_for(
    distribution: str, origin: str | None
) -> tuple[str | None, Path | None]:
    """``(commit, git dir)`` for a distribution, or ``(None, None)``.

    Three leads, strongest first: a VCS install names its commit in its
    metadata (PEP 610); a local install names the checkout's path; a
    caller can name a file inside it. The family runs the second way,
    which is why the first is not the only one implemented.
    """
    try:
        dist = _distribution(distribution)
    except PackageNotFoundError:
        dist = None
    if dist is not None:
        document = dist.read_text("direct_url.json")
        if document:
            metadata = json.loads(document)
            commit = metadata.get("vcs_info", {}).get("commit_id")
            if commit:
                return commit, None
            url = metadata.get("url")
            if url and url.startswith("file:"):
                found = _commit_in(Path(unquote(urlparse(url).path)))
                if found:
                    return found
    if origin is not None:
        found = _commit_in(Path(origin).resolve().parent)
        if found:
            return found
    return None, None


def _commit_in(start: Path) -> tuple[str, Path] | None:
    """The commit ``start`` is on, and the repository holding it."""
    git_dir = _git_dir(start)
    if git_dir is None:
        return None
    commit = _commit_of(git_dir)
    if commit is None:
        return None
    return commit, git_dir


def _git_dir(start: Path) -> Path | None:
    """The repository ``start`` sits in, searching upwards.

    A ``.git`` that is a *file* is a worktree: it points at the real
    repository, which is where the refs are, so it is followed rather
    than mistaken for a corrupt checkout.
    """
    for candidate in (start, *start.parents):
        dot = candidate / ".git"
        if dot.is_dir():
            return dot
        if dot.is_file():
            pointer = dot.read_text(encoding="utf-8", errors="replace")
            if pointer.startswith("gitdir:"):
                return Path(pointer.removeprefix("gitdir:").strip())
    return None


# --- reading a commit out of one ---------------------------------------


def _commit_of(git_dir: Path) -> str | None:
    """The commit ``HEAD`` names: a symbolic ref, or a detached sha."""
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    target = head.read_text(encoding="utf-8", errors="replace").strip()
    if not target:
        return None
    if target.startswith("ref: "):
        return _resolve_ref(git_dir, target.removeprefix("ref: ").strip())
    return target


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """The sha ``ref`` names, from a loose ref or from ``packed-refs``."""
    refs = _refs_dir(git_dir)
    loose = refs / ref
    if loose.is_file():
        value = loose.read_text(encoding="utf-8", errors="replace").strip()
        return value or None
    packed = refs / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("^") or " " not in line:
                continue
            sha, name = line.split(" ", 1)
            if name.strip() == ref:
                return sha
    return None


def _refs_dir(git_dir: Path) -> Path:
    """Where the refs live: this directory, or the common one it names.

    A linked worktree keeps its own ``HEAD`` where it sits and its refs
    in the repository, named by a ``commondir`` file. Stopping at the
    worktree would find an empty ``refs`` and call a tag unproved when
    it is one file away.
    """
    pointer = git_dir / "commondir"
    if pointer.is_file():
        target = pointer.read_text(encoding="utf-8", errors="replace")
        if target.strip():
            return (git_dir / target.strip()).resolve()
    return git_dir


def _tag_of(git_dir: Path, commit: str | None) -> str | None:
    """A tag pointing at ``commit`` exactly, if one can be proved.

    A lightweight tag *is* the ref; an annotated one is a tag object
    whose ``object`` line is the commit. A tag whose object sits in a
    packfile is not claimed: proving that needs a packfile reader, and
    an unproved tag is worse than a missing one.
    """
    if commit is None:
        return None
    for sha, name in _tag_refs(git_dir):
        if sha == commit:
            return name
        if _annotated_target(git_dir, sha) == commit:
            return name
    return None


def _tag_refs(git_dir: Path) -> list[tuple[str, str]]:
    """Every tag ref, as ``(sha, name)``, loose and packed."""
    found: list[tuple[str, str]] = []
    refs = _refs_dir(git_dir)
    tags = refs / "refs" / "tags"
    if tags.is_dir():
        for path in sorted(tags.rglob("*")):
            if path.is_file():
                value = path.read_text(
                    encoding="utf-8", errors="replace"
                ).strip()
                if value:
                    found.append((value, path.relative_to(refs).as_posix()))
    packed = refs / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith(("#", "^")) or " " not in line:
                continue
            sha, name = line.split(" ", 1)
            if name.strip().startswith("refs/tags/"):
                found.append((sha, name.strip()))
    return found


def _annotated_target(git_dir: Path, sha: str) -> str | None:
    """The commit a loose tag object points at, or ``None``.

    ``None`` for a sha that is not a loose object at all -- which is
    what a packfile, or any other kind of object, looks like from here.
    """
    obj = _refs_dir(git_dir) / "objects" / sha[:2] / sha[2:]
    if not obj.is_file() or len(sha) < _LOOSE_OBJECT_MINIMUM:
        return None
    try:
        raw = zlib.decompress(obj.read_bytes())
    except zlib.error:
        return None
    # A loose object is ``<type> <size>\0<content>``: the header is not a
    # line, so the content starts after the NUL.
    _, _, content = raw.partition(b"\x00")
    for line in content.split(b"\n"):
        if line.startswith(b"object "):
            return line.removeprefix(b"object ").decode("ascii", "replace")
    return None
