<!-- SPDX-License-Identifier: GPL-2.0-or-later -->
<!-- SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors -->

# Changelog

Notable changes to vinsynlib. Dates are ISO. Versions follow
[semantic versioning](https://semver.org/), with the caveat that 0.x means
the interfaces may still move — and this library is depended on by ten
siblings, so a 0.x bump is not a licence to move one carelessly.

**Read this before upgrading.** Two of the changes in 0.3.0 make a check
*stricter*, which means a project that was passing can fail on the version
that fixed it. That is the point of both, but it is worth knowing before
CI goes red rather than after. Each such entry is marked **stricter**.

The reasoning behind almost every entry lives in `TODO.md`, which records
the 2026-10-09 code review the 0.3.0 work came from.

## [0.3.0] — 2026-10-10

Interfaces still moving, on the 0.x line. Nothing here is a deliberate
break for its own sake; the two that are breaks are listed under
**Breaking** with what to do about them.

### Breaking

- **`Favorites.add()` refuses a rating outside 0-5.** It now raises
  `ValueError`, where it used to store whatever it was given. The column
  carries no `CHECK` constraint, so the range was only ever as good as the
  code that wrote it — and `set_rating` was checking it while `add`, the
  method under it, was not. A caller passing an out-of-range rating to
  either one now gets the same refusal.

  Verified against all ten consumers before shipping: every observed call
  used 2-5, and the out-of-range ones were already wrapped in
  `pytest.raises`, so nothing in the family changes behaviour. A caller
  outside it that was relying on a stored `99` has been broken all along.

- **`spec.Subcommand.extra` is gone.** It was populated by nothing and read
  by nothing; it stayed behind a generated dataclass field. Removing it
  changes the constructor's arity, so a project constructing `Subcommand`
  positionally past `group` would notice.

### Changed

- **`devchecks.config_saves_without_path` catches a `save_ports` with no
  path** — the one writer most likely to be called, and the one whose
  `path` is the *third* argument rather than the second. It decides
  "names a path" from a per-method arity table now instead of one number,
  because the arity is not uniform across the writers. **Stricter:** a
  project whose test calls `config.save_ports("A", "B")` was writing
  `config.toml` into its checkout and passing; it is now reported. The
  guard runs in nine projects' suites, and the change was verified against
  all of them first — it flags nothing new anywhere in the family.

- **`favorites.tags()` and `favorites.with_tag()` read the columns they
  use.** Both were calling `all(order="bank")`, which is `SELECT *` over
  every active row; `tags()` needs one column and `with_tag()` needs the
  identity and the tags. `with_tag` now filters a row *before* building a
  `Favorite` for it, so a bank carrying no match builds no objects. Same
  results, less work — over 800 rows `tags()` went from 2.9 ms to 2.0 ms,
  which is not dramatic but is free.

- **`spec.flag_names(tier="editor")` is the editor tier, not one flag.** It
  returned `("allow-write",)`, so an editor tool asking the spec for its
  flags was handed the editor-*only* flag and none of the thirteen shared
  ones. It is now the superset the name promises — fourteen flags against
  the browser tier's thirteen — and an unknown tier raises rather than
  quietly returning the browser set.

- **`conformance.check_terms` reports a word that shadows a family word.**
  `Terminology.word()` looks in `own` *before* `FAMILY`, so a tool's own
  spelling of "favourite" silently replaced the family's everywhere
  `word()` is called — and the check never looked at `own`. **Stricter:** a
  project that shadows a family word now fails its own conformance test.

### Added

- **`_LockedConnection.transaction()`**, a context manager holding the lock
  for a block of statements and committing once, rolling back if the block
  raises. It is what `refresh_names` uses now; it exists for the caller
  that needs to write more than a handful of rows at once. It deliberately
  does *not* reduce commits in `refresh_names`, which never had more than
  one — sqlite3 was already holding the statements in a single implicit
  transaction, and an earlier claim that it did was wrong.

- **`_WRITER_ARITY`** in `devchecks`, the table the config-save check reads.
  A project whose own writer over the settings store is not in it falls back
  to arity 1, the shape they share.

- **`devchecks.own_namespaces` removed.** It was `frozenset(packages)` with
  no caller anywhere in the family -- no import in any of the ten siblings
  under any spelling, nothing in their git history, and its body never
  measured in this project's own coverage run. It had been out of
  `devchecks.__all__` since 0.2.0, so nothing could break by losing it.
  Nothing replaces it: `foreign_imports` takes `own` as any `Iterable[str]`
  and the family passes hand-written tuples, which is the direct form.

- **Twelve tests**, 170 to 182. The two gaps that mattered:
  `keys.legend_from_bindings` was unreached by the suite entirely and is
  the API that keeps a tool's legend and its `BINDINGS` from drifting into
  two lists; and `conformance.check_terms` had no test at all. Coverage
  94% to 96%, with `keys.py` at 100%.

- **`devchecks.release_parts_drift()` and `release_parts_invariants()`**,
  the check that every project's copy of the version gate still matches the
  library's. Each project carries its own copy on purpose — a gate must not
  import the library it is checking — and nothing was checking that the
  copies stayed identical. A drift lands in *one* tool, so the symptom was
  "one browser is broken with this library and the other nine work", which
  is a support ticket rather than a red build. The check normalises away the
  two spellings that are not drift, compares the rest against the
  **installed** library, and reports a diff rather than a verdict. The
  invariants are held against one file at a time rather than as a
  comparison, so the guard cannot be disarmed by editing the library's own
  copy and propagating the edit — and vinsynlib's suite runs them against
  its own copy for the same reason.

  No consumer calls this yet. Adopting it is one small change each, and
  `TODO.md` §3 records the order and the shape.

### Fixed

- **`midi.list_ports` no longer carries a branch that cannot run.**
  `except MidiUnavailable: raise` sat inside a `try` whose only source of
  `MidiUnavailable` was outside it — `_rtmidi()` runs before the `try` —
  and coverage confirmed it never fired. The docstring now says why there
  is no such branch, so the next reader does not have to work it out, and
  the `ImportError` arm of `_rtmidi` — the path a headless box or a
  container actually takes — has a test.

- **`favorites.data_dir`'s docstring argued against its own code.** Three
  paragraphs explain why Windows data goes under `%LOCALAPPDATA%` and not
  the roaming `%APPDATA%`, then the code falls back to roaming when
  `LOCALAPPDATA` is absent. The fallback is right — the profile that would
  corrupt a roaming database is the profile that sets `LOCALAPPDATA`, so an
  account without it is not on a roaming one — and the docstring now says
  that instead of the opposite.

- **`favorites`' `set_rating`/`set_tags`/`set_note` now say what they
  do.** They route through `add`, so annotating a slot nobody has
  favourited makes it one. That is a decision another project tests
  (`kwsed`'s `test_setting_on_something_not_favourited_creates_it`), not a
  side effect, and it is now written down in both places rather than left
  for someone to discover.

## [0.2.0] — 2026-10-09

First version on PyPI. Published from the `publish` workflow by trusted
publishing, with `v0.2.0` tagged and a GitHub Release.

- **`settings` refuses to touch a file that is not its own.** Nine tools
  default to the same relative `config.toml`, so two meet in one
  directory; the second now reads nothing from and writes nothing to a
  file whose header names another tool, refuses a file holding tables or
  lists, and writes through a temporary plus `os.replace` instead of
  truncating in place.
- **`midi` turns a missing backend into `MidiUnavailable`**, the one thing
  a caller has to catch, and deletes whichever client was built before the
  error leaves — rtmidi leaks its backend handle otherwise.
- **`open_remembered_or_swept` sweeps when the remembered port is gone**,
  and says so, rather than stopping to ask the user to type `--scan`; the
  fallback can name its reason through `on_fallback(port, error)`.
- **The version is single-sourced** from `vinsynlib.__version__`, and
  `is_compatible_version` tolerates a pre-release or build suffix and
  refuses a non-version rather than guessing at one.
- **`spec` declares the `hardware` subcommand as needing a unit**, which
  it does.

## [0.1.0] — 2026-10-06

The shared base of nine sibling browsers, assembled from nine copies of
the same modules that had drifted apart: the settings cache, the favourites
database, the keymap and legend, the parser, the port listing, the error
format, and the command-line conventions.
