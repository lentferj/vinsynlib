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

"""What a help screen can honestly say about the build it is running.

The repositories here are **written, not cloned**: a ``.git`` directory is
four small files in git's formats, and a test that needed a real clone
would be testing git. ``build_of`` is exercised against those fixtures and
against the metadata of the installed library.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path

import pytest

from vinsynlib.build import Build, build_of, version_of

#: A commit that is a valid object name and nothing else.
COMMIT = "0" * 40
OTHER = "f" * 40


def _repo(path: Path, head: str = "ref: refs/heads/main") -> Path:
    """A ``.git`` directory in ``path``, with ``HEAD`` naming ``head``."""
    dot = path / ".git"
    (dot / "refs" / "heads").mkdir(parents=True)
    (dot / "objects").mkdir(parents=True)
    (dot / "HEAD").write_text(f"{head}\n", encoding="utf-8")
    return dot


def _ref(dot: Path, ref: str, sha: str) -> None:
    target = dot / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{sha}\n", encoding="utf-8")


def test_the_librarys_own_build_is_named() -> None:
    """vinsynlib is installed in this environment, and it is editable.

    So the version resolves, the commit resolves, and neither is a
    guess -- which is the whole point, so it is asserted of the real
    thing rather than only of fixtures.
    """
    build = build_of("vinsynlib", origin=__file__)
    assert build.version is not None
    assert build.commit is not None
    assert len(build.commit) == 40


def test_a_checkout_that_was_never_installed_is_not_an_error() -> None:
    """``None`` for the version, and the commit from the checkout."""
    build = build_of("a-distribution-nobody-installed")
    assert build == Build(version=None, commit=None, tag=None)


def test_the_head_commit_is_read_from_a_branch(tmp_path: Path) -> None:
    _repo(tmp_path)
    _ref(tmp_path / ".git", "refs/heads/main", COMMIT)
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build == Build(version=None, commit=COMMIT, tag=None)


def test_a_detached_head_is_the_commit(tmp_path: Path) -> None:
    _repo(tmp_path, head=COMMIT)
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.commit == COMMIT


def test_a_packed_ref_is_found_when_the_loose_one_is_gone(
    tmp_path: Path,
) -> None:
    dot = _repo(tmp_path)
    (dot / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled\n{COMMIT} refs/heads/main\n",
        encoding="utf-8",
    )
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.commit == COMMIT


def test_a_worktrees_git_file_points_at_the_repository(tmp_path: Path) -> None:
    """A ``.git`` *file* is a worktree: the refs live elsewhere."""
    real = _repo(tmp_path / "main")
    _ref(real, "refs/heads/main", COMMIT)
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
    build = build_of("nothing-installed", origin=str(linked / "a.py"))
    assert build.commit == COMMIT


def test_a_worktree_finds_the_tags_its_repository_holds(
    tmp_path: Path,
) -> None:
    """A linked worktree keeps its own ``HEAD`` and shares the refs.

    Real layout: the ``.git`` file names a per-worktree directory, which
    holds ``HEAD`` and a ``commondir`` file pointing back at the
    repository that holds ``refs/`` and ``packed-refs``. Stopping at the
    worktree finds an empty ``refs`` and calls a tag that exists
    unproved -- which is what happened the first time, against a real
    ``git worktree`` of this repository.
    """
    real = _repo(tmp_path / "main")
    _ref(real, "refs/heads/main", COMMIT)
    _ref(real, "refs/tags/v0.4.1", COMMIT)
    per_worktree = real / "worktrees" / "linked"
    per_worktree.mkdir(parents=True)
    (per_worktree / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    (per_worktree / "commondir").write_text("../..\n", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {per_worktree}\n", encoding="utf-8")
    build = build_of("nothing-installed", origin=str(linked / "a.py"))
    assert build.commit == COMMIT
    assert build.tag == "refs/tags/v0.4.1"


def test_no_git_anywhere_means_no_commit(tmp_path: Path) -> None:
    """A wheel lands in site-packages, where there is no repository."""
    (tmp_path / "site-packages").mkdir()
    build = build_of(
        "nothing-installed", origin=str(tmp_path / "site-packages" / "a.py")
    )
    assert build.commit is None


def test_a_lightweight_tag_at_the_commit_is_named(tmp_path: Path) -> None:
    dot = _repo(tmp_path)
    _ref(dot, "refs/heads/main", COMMIT)
    _ref(dot, "refs/tags/v0.4.1", COMMIT)
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.tag == "refs/tags/v0.4.1"


def test_an_annotated_tag_is_followed_to_its_commit(tmp_path: Path) -> None:
    """An annotated tag's ref is the tag *object*, not the commit.

    The object is written the way git writes one -- ``tag <len>\\0`` and
    then the content -- because a tidier fake is exactly how the first
    version of this parser passed its test while failing on a real
    repository.
    """
    dot = _repo(tmp_path)
    _ref(dot, "refs/heads/main", COMMIT)
    tag_object = "a" * 40
    _ref(dot, "refs/tags/v9.9.9", tag_object)
    content = b"object " + COMMIT.encode() + b"\ntype commit\ntag v9.9.9\n"
    body = b"tag %d\x00" % len(content) + content
    obj = dot / "objects" / tag_object[:2]
    obj.mkdir(parents=True)
    (obj / tag_object[2:]).write_bytes(zlib.compress(body))
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.tag == "refs/tags/v9.9.9"


def test_a_tag_on_some_other_commit_is_not_claimed(tmp_path: Path) -> None:
    dot = _repo(tmp_path)
    _ref(dot, "refs/heads/main", COMMIT)
    _ref(dot, "refs/tags/v0.4.0", OTHER)
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.tag is None


def test_a_packed_annotated_tag_is_not_claimed(tmp_path: Path) -> None:
    """The honest limit: a packed object is not read, so it is not named."""
    dot = _repo(tmp_path)
    _ref(dot, "refs/heads/main", COMMIT)
    tag_object = "b" * 40
    (dot / "packed-refs").write_text(
        f"{tag_object} refs/tags/v0.4.1\n^{COMMIT}\n", encoding="utf-8"
    )
    build = build_of("nothing-installed", origin=str(tmp_path / "a.py"))
    assert build.commit == COMMIT
    assert build.tag is None


def test_a_vcs_installs_commit_id_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PEP 610: installed from a URL with a revision, so it is named.

    A fixture distribution on ``sys.path``, because that is the only way
    ``importlib.metadata`` can find one in a test.
    """
    infos = tmp_path / "x-0.1.0.dist-info"
    infos.mkdir()
    (infos / "METADATA").write_text("Name: x\nVersion: 0.1.0\n", "utf-8")
    (infos / "direct_url.json").write_text(
        json.dumps({"vcs_info": {"commit_id": COMMIT}}), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    build = build_of("x")
    assert build.version == "0.1.0"
    assert build.commit == COMMIT
    assert build.tag is None, "a VCS install names no repository, so no tag"


def test_a_local_install_names_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The family's own case: ``pip install -e .`` of a local checkout.

    ``direct_url.json`` carries a ``file:`` URL and **no** ``vcs_info``,
    so the commit has to come out of the checkout the URL points at --
    which is the whole reason the second lead exists.
    """
    dot = _repo(tmp_path)
    _ref(dot, "refs/heads/main", COMMIT)
    infos = tmp_path / "x-0.1.0.dist-info"
    infos.mkdir()
    (infos / "METADATA").write_text("Name: x\nVersion: 0.1.0\n", "utf-8")
    (infos / "direct_url.json").write_text(
        json.dumps({"url": tmp_path.as_uri()}), encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    build = build_of("x")
    assert build.version == "0.1.0"
    assert build.commit == COMMIT


def test_version_of_a_distribution_that_is_not_there() -> None:
    assert version_of("a-distribution-nobody-installed") is None


def test_a_release_names_its_version_and_no_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other tier: a wheel knows its version and cannot know a sha.

    A build with no commit is still a complete answer -- the family tags
    releases ``v<version>``, so the version is the identity. What must
    not happen is a fabricated sha standing in for one.
    """
    (tmp_path / "site-packages").mkdir()
    infos = tmp_path / "x-0.1.0.dist-info"
    infos.mkdir()
    (infos / "METADATA").write_text("Name: x\nVersion: 0.1.0\n", "utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    build = build_of("x")
    assert build == Build(version="0.1.0", commit=None, tag=None)
