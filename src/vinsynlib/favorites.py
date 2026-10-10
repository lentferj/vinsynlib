# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
#
# This file is part of vinsynlib.
#
# Assembled from the favourites databases that every browser in the family
# carried its own copy of:
#   Copyright (C) 2026  emorphed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  ensqsqed contributors        - GPL-2.0-or-later
#   Copyright (C) 2026  kwsed contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  nanosyned contributors       - GPL-2.0-or-later
#   Copyright (C) 2026  p2ked contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  rxved contributors           - GPL-2.0-or-later
#   Copyright (C) 2026  x5ded contributors           - GPL-2.0-or-later
#
# The seven copies were byte-identical apart from the prose and the
# example bank names in it, which is why this is one file.
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

"""The local favourites database.

The one piece of state in these tools that is genuinely the **user's**
rather than the device's or the manufacturer's, which is why it gets a
real database rather than another key in ``config.toml``. Three things
follow from that:

**It is keyed on the slot, not on the name.** A row records the bank and
the displayed number, never the name -- so a favourite survives a rename,
and a favourite of a slot means the slot, permanently. The name is stored
too, but only as a label to show when the catalog is missing; it is never
the identity. The displayed number is what the unit shows, not the wire
byte: on many instruments the first patch of a bank is number 1 and
program change 0.

**The bank id is the catalog's, not a wire number.** Wire numbering is the
instrument's business and can differ from the order a person sees the
banks in; a favourites file outlives any particular reading of it.

**It is SQLite, and that is not over-engineering for a list of
favourites.** A JSON file rewritten on every toggle loses the whole file to
a crash or a full disk mid-write, and the natural next features --
ratings, tags, notes, "when did I last use this" -- are all things a flat
file grows badly. SQLite gives atomic writes for free. The schema is
versioned from the first commit so the second version does not have to
guess what the first one wrote.

**It lives outside the project directory by default**, in the per-platform
application-*data* directory -- see :func:`data_dir` for where that is on
each and why. Unlike ``config.toml``, which is a disposable cache of which
MIDI port answered last and lives in the working directory, favourites are
the user's own work: the one thing here worth backing up, and the one
thing that must not be lost to a ``git clean`` in a checkout.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "APP_NAME",
    "DB_NAME",
    "SCHEMA_VERSION",
    "Bound",
    "Favorite",
    "Favorites",
    "bind",
    "data_dir",
    "default_path",
    "split_key",
]

#: Bumped whenever the schema changes; :meth:`Favorites._migrate` reads it.
SCHEMA_VERSION = 2

#: The database's filename, in whichever per-platform data root applies.
DB_NAME = "favorites.db"

#: Used when no application name is given. A library cannot know the name
#: of the program using it; each project passes its own.
APP_NAME = "vinsynlib"


def data_dir(app_name: str = APP_NAME) -> str:
    """The per-platform directory for an application's **data**.

    Data, not configuration: the distinction is real on every platform and
    matters here, because favourites are the user's own work -- the one
    thing in these tools worth backing up -- while ``config.toml`` is a
    cache of which MIDI port answered last and is disposable.

    * **Windows** -- ``%LOCALAPPDATA%\\<app>`` (typically
      ``C:\\Users\\<user>\\AppData\\Local\\<app>``).

      Local rather than Roaming deliberately. ``%APPDATA%`` roams, and a
      roaming profile copies files wholesale at logon and logoff; a SQLite
      database caught mid-write by that copy, or opened on two machines at
      once against one synced file, is a known way to corrupt one. SQLite's
      own documentation warns against network filesystems for the same
      reason. Roaming would be the right answer for a small settings file
      and is the wrong one for a database.

      When ``%LOCALAPPDATA%`` is absent -- a stripped service account --
      ``%APPDATA%`` is used anyway, and that is a decision rather than an
      oversight: the profile that would corrupt the database is the profile
      that *sets* ``%LOCALAPPDATA%``, so an account without it is not on a
      roaming one either. The alternative is the XDG layout, which on
      Windows is a path no other tool on the machine knows how to find.
      A wrong-looking but familiar directory beats a right one nobody can
      find, and both beat refusing to start.

    * **macOS** -- ``~/Library/Application Support/<app>``, which is where
      Apple's File System Programming Guide puts application data that is
      not a cache and not a user document.

    * **Linux, BSD, everything else** -- the XDG Base Directory
      Specification: ``$XDG_DATA_HOME/<app>``, falling back to
      ``~/.local/share/<app>``. Note that XDG requires ``XDG_DATA_HOME`` to
      be an **absolute** path and says a relative one must be ignored, so a
      stray relative value falls back rather than creating a directory
      wherever the process happens to have been started.

    Every branch falls back to the XDG layout if the platform's own
    environment variable is missing, which is what happens on a stripped
    Windows service account or a macOS process with no HOME. A wrong-looking
    but writable path beats raising on startup, since the alternative is a
    browser that will not open because it cannot decide where to put a file
    the user may never use.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return os.path.join(base, app_name)
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        # Absolute, not merely different from "~": a process with HOME set
        # to a relative value -- a stripped service account, a container
        # with a placeholder -- expands to that relative path rather than
        # to a tilde, and the branch below would then return a path
        # relative to the working directory, which is never where the
        # user's data is.
        if os.path.isabs(home):
            return os.path.join(
                home, "Library", "Application Support", app_name
            )

    base = os.environ.get("XDG_DATA_HOME")
    # XDG: "If $XDG_DATA_HOME is either not set or empty, a default equal to
    # $HOME/.local/share should be used." and paths in it must be absolute.
    if not base or not os.path.isabs(base):
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, app_name)


def default_path(app_name: str = APP_NAME, db_name: str = DB_NAME) -> str:
    """Where an application's favourites database lives, per platform.

    Overridable everywhere it is used -- ``--favorites`` on both front
    ends -- so a user who wants it beside a project, on a stick, or in a
    synced folder can say so.
    """
    return os.path.join(data_dir(app_name), db_name)


class _Result:
    """The rows of one statement, already fetched.

    :class:`_LockedConnection` hands this back instead of a live cursor,
    because a cursor iterated *after* the lock is released is exactly the
    interleaving the lock exists to prevent. Everything is read inside the
    lock; what comes out is an ordinary list.
    """

    __slots__ = ("rowcount", "rows")

    def __init__(self, rows: list[Any], rowcount: int) -> None:
        self.rows = rows
        self.rowcount = rowcount

    def fetchone(self) -> Any | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Any]:
        return self.rows

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


class _LockedConnection:
    """A SQLite connection usable from more than one thread.

    SQLite refuses cross-thread use of a connection by default, and that
    default is a silent mine in a Textual application: the store is opened
    on the main thread, and any background worker that so much as asks for
    ``len()`` raises ``ProgrammingError`` *out of the worker*, which takes
    the whole application down. That is not hypothetical -- it is what
    pressing `i` did, the first time anybody pressed it, because the
    device-info worker built its report on the wrong thread.

    The structural fix was to move that work back to the main thread. This
    is the belt to that's braces: one lock, held across each statement and
    its fetch, so the next worker to reach for the database finds it safe
    rather than fatal. SQLite is content with a connection shared between
    threads as long as the calls do not overlap, and serialising operations
    this small costs nothing at this size.
    """

    def __init__(self, path: str) -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> _Result:
        with self._lock:
            cursor = self._db.execute(sql, parameters)
            rows = cursor.fetchall()
            return _Result(rows, cursor.rowcount)

    def executescript(self, sql: str) -> None:
        with self._lock:
            self._db.executescript(sql)

    def commit(self) -> None:
        with self._lock:
            self._db.commit()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        """Run a block of statements as one transaction.

        The lock is held for the block, which is what makes it safe to call
        from a worker: the next thread to reach for the database finds the
        whole batch done rather than half of it. Re-entrant, so a statement
        inside the block takes the lock again without deadlocking -- but a
        caller that commits inside the block (``add`` does) ends the
        transaction early, so those should not be using this.
        """
        with self._lock:
            try:
                yield
            except BaseException:
                self._db.rollback()
                raise
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()


@dataclass(frozen=True)
class Favorite:
    """One favourited slot."""

    bank_id: str
    number: int
    #: The name at the time of favouriting, as a label of last resort. Not
    #: the identity: see the module docstring.
    name: str = ""
    rating: int = 0
    tags: str = ""
    note: str = ""
    added: float = 0.0

    @property
    def key(self) -> str:
        """``BANK:NNN`` -- the display form of this slot's identity."""
        return f"{self.bank_id}:{self.number:03d}"

    @property
    def tag_list(self) -> list[str]:
        """The tags, split and stripped."""
        return _split_tags(self.tags)


class Favorites:
    """A SQLite-backed set of favourited slots.

    Usable as a context manager. Safe to construct against a path whose
    directory does not exist yet -- it is created.

    ``app_name`` only decides where :meth:`path` defaults to, and what that
    decision is called in the error message for a database written by a
    newer schema.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        app_name: str = APP_NAME,
        db_name: str = DB_NAME,
    ) -> None:
        self.app_name = app_name
        self.path = path or default_path(app_name, db_name)
        if self.path != ":memory:":
            os.makedirs(
                os.path.dirname(os.path.abspath(self.path)), exist_ok=True
            )
        # Shared across threads on purpose; see _LockedConnection.
        self._db = _LockedConnection(self.path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    # --- schema -------------------------------------------------------------

    def _migrate(self) -> None:
        """Create or upgrade the schema.

        ``user_version`` rather than a table of our own: it is a single
        integer in the database header, costs no row, and cannot itself be
        the thing that is missing when we go looking for the version.
        """
        row = self._db.execute("PRAGMA user_version").fetchone()
        current = int(row[0]) if row is not None else 0
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"{self.path} was written by a newer {self.app_name} "
                f"(schema {current}, this build understands "
                f"{SCHEMA_VERSION}). Refusing to touch it rather than risk "
                f"dropping columns it has and this does not."
            )
        if current < 1:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    bank_id TEXT    NOT NULL,
                    number  INTEGER NOT NULL,
                    name    TEXT    NOT NULL DEFAULT '',
                    rating  INTEGER NOT NULL DEFAULT 0,
                    tags    TEXT    NOT NULL DEFAULT '',
                    note    TEXT    NOT NULL DEFAULT '',
                    added   REAL    NOT NULL DEFAULT 0,
                    active  INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (bank_id, number)
                );
                CREATE INDEX IF NOT EXISTS favorites_rating
                    ON favorites (rating DESC);
                """
            )
        if current < 2:
            # Un-favouriting stopped deleting the row. It clears this flag
            # instead, so a rating, tags, a note and the original `added`
            # date survive a slot being toggled off and on -- two presses of
            # `f` used to destroy all four, silently, on the one store these
            # tools call the user's own. Every read filters on it.
            #
            # DEFAULT 1 is what makes the upgrade a no-op for existing rows:
            # everything already in the table is a live favourite.
            have = {
                row["name"]
                for row in self._db.execute("PRAGMA table_info(favorites)")
            }
            if "active" not in have:
                self._db.execute(
                    "ALTER TABLE favorites ADD COLUMN active INTEGER "
                    "NOT NULL DEFAULT 1"
                )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS favorites_active "
                "ON favorites (active)"
            )
        self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._db.commit()

    # --- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        try:
            self._db.commit()
        finally:
            self._db.close()

    def __enter__(self) -> Favorites:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # --- reading ------------------------------------------------------------

    def __contains__(self, key: str | tuple[str, int]) -> bool:
        bank_id, number = split_key(key)
        row = self._db.execute(
            "SELECT 1 FROM favorites WHERE bank_id = ? AND number = ? AND active = 1",
            (bank_id, number),
        ).fetchone()
        return row is not None

    def __len__(self) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM favorites WHERE active = 1"
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def get(self, bank_id: str, number: int) -> Favorite | None:
        """The live favourite for a slot, or ``None``."""
        row = self._db.execute(
            "SELECT * FROM favorites WHERE bank_id = ? AND number = ? AND active = 1",
            (bank_id, int(number)),
        ).fetchone()
        return _to_favorite(row) if row is not None else None

    def _row(self, bank_id: str, number: int) -> Favorite | None:
        """Like :meth:`get`, but sees un-favourited rows too.

        Private because every caller outside this class means "is this a
        favourite", and a dormant row is not one.
        """
        row = self._db.execute(
            "SELECT * FROM favorites WHERE bank_id = ? AND number = ?",
            (bank_id, int(number)),
        ).fetchone()
        return _to_favorite(row) if row is not None else None

    def keys(self) -> set[str]:
        """Every favourited slot, as ``BANK:NNN`` strings.

        One query for the whole set rather than a ``__contains__`` per row:
        the browser needs to mark every visible line, and a bank is over a
        hundred lines redrawn on every cursor move.
        """
        return {
            f"{row['bank_id']}:{row['number']:03d}"
            for row in self._db.execute(
                "SELECT bank_id, number FROM favorites WHERE active = 1"
            )
        }

    def keys_for_bank(self, bank_id: str) -> set[int]:
        """The favourited numbers in one bank."""
        return {
            row["number"]
            for row in self._db.execute(
                "SELECT number FROM favorites WHERE bank_id = ? AND active = 1",
                (bank_id,),
            )
        }

    def all(self, *, order: str = "added") -> list[Favorite]:
        """Every favourite, newest first by default.

        ``order`` is validated against a fixed set rather than interpolated:
        it reaches here from a command-line argument, and an ORDER BY is the
        one clause a parameter placeholder cannot carry.
        """
        clauses = {
            "added": "added DESC",
            "rating": "rating DESC, added DESC",
            "bank": "bank_id, number",
            "name": "name COLLATE NOCASE, bank_id, number",
        }
        if order not in clauses:
            raise ValueError(
                f"unknown order {order!r}; have {', '.join(sorted(clauses))}"
            )
        return [
            _to_favorite(row)
            for row in self._db.execute(
                f"SELECT * FROM favorites WHERE active = 1 ORDER BY {clauses[order]}"
            )
        ]

    def search(self, needle: str) -> list[Favorite]:
        """Favourites whose name, tags or note contain ``needle``."""
        # % and _ are LIKE wildcards. Without escaping them a search for
        # "%" matches every favourite and one for "_" matches every name of
        # any length -- silently, as a result that looks like a real hit.
        escaped = (
            needle.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        return [
            _to_favorite(row)
            for row in self._db.execute(
                "SELECT * FROM favorites WHERE active = 1 AND ("
                "name LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\' "
                "OR note LIKE ? ESCAPE '\\') "
                "ORDER BY bank_id, number",
                (pattern, pattern, pattern),
            )
        ]

    def with_tag(self, tag: str) -> list[Favorite]:
        """Favourites carrying ``tag``.

        Matched against the parsed list rather than with a ``LIKE '%tag%'``,
        which would make "pad" match "padded" and "lead" match
        "misleading". Tags are a short comma-separated string; filtering
        them in Python costs nothing at this size and is correct.

        The rows are filtered *before* each is turned into a
        :class:`Favorite`, so a bank that carries no match builds no
        objects.
        """
        wanted = tag.strip().lower()
        return [
            _to_favorite(row)
            for row in self._db.execute(
                "SELECT * FROM favorites WHERE active = 1 "
                "ORDER BY bank_id, number"
            )
            if wanted in _tag_set(row["tags"])
        ]

    def tags(self) -> dict[str, int]:
        """Every tag in use, with how many favourites carry it.

        Selects the one column it reads rather than every row whole.
        """
        counts: dict[str, int] = {}
        for row in self._db.execute(
            "SELECT tags FROM favorites WHERE active = 1"
        ):
            for tag in _split_tags(row["tags"]):
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    # --- writing ------------------------------------------------------------

    def add(
        self,
        bank_id: str,
        number: int,
        *,
        name: str = "",
        rating: int = 0,
        tags: str = "",
        note: str = "",
    ) -> Favorite:
        """Favourite a slot, or update the one that is already there.

        An upsert that **preserves ``added``** on an existing row: re-adding
        a favourite is an edit, not a re-acquisition, and quietly resetting
        the date would corrupt the one ordering the user cannot reconstruct.

        ``rating`` is 0-5 and is checked here, not only in
        :meth:`set_rating`. The column has no CHECK constraint, so this is
        the only thing standing between a caller and a favourites database
        holding a rating of 99.
        """
        if not 0 <= int(rating) <= 5:
            raise ValueError(f"rating {rating} is outside 0-5")
        existing = self._row(bank_id, number)
        added = existing.added if existing is not None else time.time()
        self._db.execute(
            "INSERT INTO favorites (bank_id, number, name, rating, tags, "
            "note, added, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT (bank_id, number) DO UPDATE SET "
            "name = excluded.name, rating = excluded.rating, "
            "tags = excluded.tags, note = excluded.note, active = 1",
            (bank_id, int(number), name, int(rating), tags, note, added),
        )
        self._db.commit()
        return Favorite(
            bank_id, int(number), name, int(rating), tags, note, added
        )

    def remove(self, bank_id: str, number: int) -> bool:
        """Un-favourite a slot. ``True`` if it was one.

        The row is kept and its ``active`` flag cleared, not deleted. A
        favourite carries a rating, tags, a note and the date it was made --
        the user's own work, and the only thing here that cannot be
        reconstructed from the instrument. Deleting the row put all four one
        keystroke from destruction, since the browser's ``f`` unfavourites
        without asking; keeping it means the same keystroke brings them
        back. :meth:`forget` is the one that really deletes.
        """
        cursor = self._db.execute(
            "UPDATE favorites SET active = 0 "
            "WHERE bank_id = ? AND number = ? AND active = 1",
            (bank_id, int(number)),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def forget(self, bank_id: str, number: int) -> bool:
        """Delete a slot's row outright, annotations and all.

        What :meth:`remove` used to do. No keystroke should be able to
        reach it; that is the whole reason :meth:`remove` does not do this.
        """
        cursor = self._db.execute(
            "DELETE FROM favorites WHERE bank_id = ? AND number = ?",
            (bank_id, int(number)),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def dormant(self) -> list[Favorite]:
        """Slots un-favourited but still holding annotations."""
        return [
            _to_favorite(row)
            for row in self._db.execute(
                "SELECT * FROM favorites WHERE active = 0 ORDER BY bank_id, number"
            )
        ]

    def toggle(self, bank_id: str, number: int, *, name: str = "") -> bool:
        """Flip a slot's favourite state. ``True`` if it is now a favourite.

        Re-favouriting restores whatever the slot carried when it was last
        un-favourited rather than starting it blank, which is the whole
        point of :meth:`remove` keeping the row. ``name`` is used only if
        there is nothing to restore, or if the stored one is empty: the name
        is a label that the instrument can supply again, unlike the rest.
        """
        if self.remove(bank_id, number):
            return False
        old = self._row(bank_id, number)
        if old is None:
            self.add(bank_id, number, name=name)
        else:
            self.add(
                bank_id,
                number,
                name=old.name or name,
                rating=old.rating,
                tags=old.tags,
                note=old.note,
            )
        return True

    def set_rating(self, bank_id: str, number: int, rating: int) -> None:
        """Set a slot's rating, 0-5, leaving its other annotations alone.

        Note what this does *not* do: it does not create a favourite, and it
        does not refuse to. It routes through :meth:`add`, which favourites
        a slot that is not one — so ``set_rating`` on a slot nobody
        favourited makes it one. That is deliberate rather than accidental,
        and it is pinned by a test in kwsed
        (``test_setting_on_something_not_favourited_creates_it``), which is
        why an attempt to make these annotate-only was reverted on
        2026-10-10. If the family ever wants the other contract, that test
        is the thing to move first.
        """
        if not 0 <= rating <= 5:
            raise ValueError(f"rating {rating} is outside 0-5")
        self.add(
            bank_id,
            number,
            **_merge(self.get(bank_id, number), rating=rating),
        )

    def set_tags(self, bank_id: str, number: int, tags: str) -> None:
        """Set a slot's tags, leaving its other annotations alone.

        As with :meth:`set_rating`, a slot that is not a favourite becomes
        one. See that method's docstring for why.
        """
        self.add(
            bank_id,
            number,
            **_merge(self.get(bank_id, number), tags=_clean_tags(tags)),
        )

    def set_note(self, bank_id: str, number: int, note: str) -> None:
        """Set a slot's note, leaving its other annotations alone.

        As with :meth:`set_rating`, a slot that is not a favourite becomes
        one. See that method's docstring for why.
        """
        self.add(
            bank_id, number, **_merge(self.get(bank_id, number), note=note)
        )

    def refresh_names(self, lookup: Callable[[str, int], str | None]) -> int:
        """Re-label favourites from a name source. Returns how many changed.

        Used after a catalog is generated or a bank is read from the device,
        so that favourites made before there were any names stop showing
        "--". ``lookup(bank_id, number)`` returns a name or ``None``.

        One transaction, because a re-label touches every row it changes and
        a commit per row turns a 500-favourite import into 500 fsyncs. Only
        :meth:`_LockedConnection.execute` is used inside it: ``add`` and
        friends commit, which would end the batch early.
        """
        changed = 0
        with self._db.transaction():
            for fav in self.all(order="bank") + self.dormant():
                fresh = lookup(fav.bank_id, fav.number)
                if fresh and fresh != fav.name:
                    self._db.execute(
                        "UPDATE favorites SET name = ? "
                        "WHERE bank_id = ? AND number = ?",
                        (fresh, fav.bank_id, fav.number),
                    )
                    changed += 1
        return changed


@dataclass(frozen=True)
class Bound:
    """One application's view of this module.

    The three names a project's ``favorites.py`` used to define for itself:
    the application name, where its data goes, and a store class that
    already knows both.
    """

    app_name: str
    db_name: str = DB_NAME

    def data_dir(self) -> str:
        """This application's data directory."""
        return data_dir(self.app_name)

    def default_path(self) -> str:
        """Where this application's favourites database lives."""
        return default_path(self.app_name, self.db_name)

    def store(self, path: str | None = None) -> Favorites:
        """A store for this application, at ``path`` or the default."""
        return Favorites(path, app_name=self.app_name, db_name=self.db_name)


def bind(app_name: str, db_name: str = DB_NAME) -> Bound:
    """A :class:`Bound` view for one application."""
    return Bound(app_name=app_name, db_name=db_name)


# --- helpers ---------------------------------------------------------------


def split_key(key: str | tuple[str, int]) -> tuple[str, int]:
    """Accept either a ``(bank, number)`` pair or ``"BANK:012"``."""
    if isinstance(key, tuple):
        return key[0], int(key[1])
    bank_id, _, number = str(key).partition(":")
    return bank_id, int(number)


def _to_favorite(row: sqlite3.Row) -> Favorite:
    return Favorite(
        bank_id=row["bank_id"],
        number=row["number"],
        name=row["name"],
        rating=row["rating"],
        tags=row["tags"],
        note=row["note"],
        added=row["added"],
    )


def _split_tags(tags: str) -> list[str]:
    """One row's tag text, trimmed and in order, empties dropped.

    Duplicates are kept, deliberately: a row that says ``"a, a"`` carries
    the tag twice as far as :meth:`Favorites.tags` counting is concerned,
    and silently de-duplicating here would make that count lie.
    """
    return [part.strip() for part in tags.split(",") if part.strip()]


def _tag_set(tags: str) -> set[str]:
    """One row's tag text as comparable names.

    ``_split_tags`` lower-cased, for :meth:`Favorites.with_tag`
    """
    return {tag.lower() for tag in _split_tags(tags)}


def _merge(existing: Favorite | None, **changes: Any) -> dict[str, Any]:
    """Fields for :meth:`Favorites.add` that change one thing, keep the rest.

    Without this, setting a rating on a favourite would blank its tags and
    note, because ``add`` takes every field and defaults the ones it is not
    given. This is also why ``set_*`` *creates* a favourite when there is
    none: ``_merge`` on ``None`` produces the empty defaults and ``add``
    upserts, which the family has decided is what it wants.
    """
    base: dict[str, Any] = {
        "name": existing.name if existing else "",
        "rating": existing.rating if existing else 0,
        "tags": existing.tags if existing else "",
        "note": existing.note if existing else "",
    }
    base.update(changes)
    return base


def _clean_tags(tags: str) -> str:
    """Normalise a comma-separated tag string: trimmed, de-duplicated."""
    seen: list[str] = []
    for part in tags.split(","):
        tag = part.strip()
        if tag and tag.lower() not in {t.lower() for t in seen}:
            seen.append(tag)
    return ", ".join(seen)
