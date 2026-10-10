<!--
SPDX-License-Identifier: GPL-2.0-or-later
SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
-->

# TODO

## Status, 2026-10-09

vinsynlib 0.2.0 is published on PyPI, and the ten consumer projects now
depend on `vinsynlib>=0.2.0` from the index rather than on a sibling
checkout. Nothing in this repository is blocked on anything outside it.

What follows is a full code review of the library itself, followed by an
analysis of whether the undo stack should move in here from the three
projects that carry one. Both are written up as findings with enough
reasoning attached that a later reader does not have to re-derive them.

**Undo: decided, Option A** — a shared `vinsynlib/undo.py`, because every
project will have an undo function and ten consumers is above the
threshold this library was built for. The analysis, the constraints the
module must satisfy, and the order of work are in §2.6; the reasoning and
the risks are above it, and they still apply.

---

# 1. Code review, 2026-10-09

All eleven modules read end to end; every finding below was reproduced
rather than inferred. Line numbers are against `main` at the time of
writing.

## 1.1 Bugs

### 1.1.1 `devchecks.config_saves_without_path` misses `save_ports` — FIXED 2026-10-10

The guard exists to stop a test writing `config.toml` into the checkout.
It decided a call "names a path" with `len(node.args) >= 2`, which assumes
`path` is the second positional argument. It is not, for the one method most
likely to be called: `save_ports(send_port, recv_port, path=None)` takes two
port names first, so `config.save_ports("A", "B")` in a test wrote into the
working directory and passed.

Fixed with a per-method arity table (`_WRITER_ARITY`), because the arity is
not uniform and a single number cannot be right: `save_ports` and the
family's `save_last_ports` take two values, everything else one, `update`
takes none. An unlisted project-specific writer falls back to 1, the shape
they share.

Checked before shipping, because this guard runs in nine projects' suites:
the fix flags **nothing new** anywhere in the family (run for real against
all nine), so no CI goes red on the change. Two tests added, including one
that pins the "receiver is named `config`" precondition the docstring states.

### 1.1.2 `spec.flag_names(tier="editor")` returns one flag — FIXED 2026-10-10

```python
f.name for f in CANONICAL_FLAGS if tier != "editor" or f.editor_only
```

For the editor tier this yielded `("allow-write",)` — only the
editor-*only* flag, dropping the fourteen shared flags an editor tool also
has. It read as "the flags for an editor" and returned the opposite.

Fixed so the editor tier is what its name promises: a **superset** of the
browser tier. An unknown tier now raises rather than silently returning the
browser set. No external caller passed `tier="editor"`.

### 1.1.3 `set_rating`/`set_tags`/`set_note` silently favourite a slot — ATTEMPTED AND REVERTED 2026-10-10

`Favorites.set_rating("A", 1, 5)` on an empty store created an active
favourite. The review called this a bug and made the three annotate-only:
they routed through `add()`, which upserts, so annotating an un-favourited
slot made it one.

**Reverted, because it is not a bug.** kwsed has
`tests/test_stores.py::TestFavouritesAnnotations::test_setting_on_something_not_favourited_creates_it`,
which asserts exactly the old behaviour:

```python
store.set_note("RAM1", 9, "made a note")
got = store.get("RAM1", 9)
assert got is not None and got.note == "made a note"
```

The behaviour is a decision another project tests, so the library does not
get to change it unilaterally. The review missed it because it looked at
consumer *call sites* — which all call `add` first — and not at consumer
*tests*, which pin the semantics. `set_rating`'s docstring now states the
contract and names the test, and vinsynlib has its own test pinning the
same thing, so the next person to try this finds the evidence in both
places.

Revisit only if kwsed's test moves first.

### 1.1.4 `Favorites.add` does not validate the rating — FIXED 2026-10-10

`set_rating` enforces 0-5; `add(rating=99)` stored 99, and the column
carries no CHECK constraint. The 0-5 range was documented in exactly one
docstring (`set_rating`) and nowhere in the schema.

`add` now validates before it writes. Safe for the family: every observed
consumer call used 2-5, and the only out-of-range calls were
`set_rating(x, 6)` wrapped in `pytest.raises`, which still behaves the same.

### 1.1.5 `data_dir`'s Windows fallback contradicts its own docstring — FIXED 2026-10-10 (in the docstring, not the code)

Three paragraphs of `data_dir` argued Local rather than Roaming because a
roaming profile corrupts SQLite, then the code fell back to `APPDATA` --
roaming -- whenever `LOCALAPPDATA` was absent.

**The code was right and the docstring was wrong.** There is a named test
for it (`test_windows_without_local_app_data_uses_roaming`) and a third one
for the neither-set case, so the fallback is a decision. The argument that
makes it coherent: the profile that corrupts a roaming database is the
profile that *sets* ``LOCALAPPDATA``, so an account without it is not on a
roaming one either; and the XDG layout on Windows is a path no other tool
knows. The docstring now says all of that instead of arguing the opposite
of the code beside it.

### 1.1.6 `midi.list_ports`'s `except MidiUnavailable: raise` is unreachable — FIXED 2026-10-10

`_rtmidi()` runs *outside* the `try`, so the only source of
`MidiUnavailable` cannot be caught inside it. Coverage confirms the branch
never runs. Harmless, but it advertises a path that cannot happen in the
one function whose job is telling callers what can.

## 1.2 Improvements

### 1.2.1 `spec.__all__` omits `aliases_for` — FIXED 2026-10-10

Four consumer projects import `spec.aliases_for`. This module exists to be
the declared contract for the family, and a name projects depend on being
undeclared is exactly the drift it guards against. `SILENT_SUFFIX` is
likewise unlisted (one user). The same applies to `Flag.options()`,
`Flag.option` and `Subcommand.extra`.

### 1.2.2 `devchecks.own_namespaces` is `frozenset(packages)` — REMOVED 2026-10-10

A function whose whole body is a constructor call. **The review's count was
wrong**: it claimed one project used it. The audit found **zero**.

Four independent confirmations that nothing consumes it:

- no import of the name in any of the ten siblings, under any spelling, in
  any file type (`grep -rn` across all 71 repos, case-insensitive, by
  substring, excluding the caches);
- `git log -S "own_namespaces" --all` in all eleven repos: no commit outside
  vinsynlib has ever added the string. Nothing was deleted and left behind;
- it has been out of `devchecks.__all__` since `82ee475` -- the very commit
  that set out to "declare the public names the projects actually import"
  -- and no project imported it even during the window it was declared;
- line 135 of `devchecks.py` was never measured in vinsynlib's own coverage
  run. The body had never executed.

So there was no second project to delete, and removal is a one-file change.
`foreign_imports` and `check_foreign_imports` take `own` as an
`Iterable[str]` and widen it with `set(own)`, so a tuple, a list and a
`frozenset` are all equivalent at the eleven places the family actually
passes one -- which are hand-written tuples like `own=("emorphed", "emu",
"vinsynlib")`, already in the direct form.

One thing the audit settled on the way: **`devchecks` has eight consumers,
not ten.** `k2kremote` and `p2ked` have no reference to it in any file.

### 1.2.3 `spec.Subcommand.extra` is never populated — FIXED 2026-10-10

`_s()` does not pass it and no entry in `SUBCOMMANDS` sets it. A dead
field on a frozen dataclass that the conformance check walks over.

### 1.2.4 `conformance.check_legend` computes `legend()` twice — FIXED 2026-10-10

`keys_module.legend(...)` is called at line 232 and again at line 249, and
the order check is three nested comprehensions that took a second read to
verify. Compute `expected` once and compare
`[b for b in shared]` against `[b for b in expected if b in shared]`.

### 1.2.5 `check_terms` ignores `terms.own` — FIXED 2026-10-10

`check_terms` reconstructed the `Terminology` from four fields and so never
looked at `own`. It also could not catch the one collision the module
docstring warns about: `Terminology.word()` looks in `own` **before**
`FAMILY`, so a tool's own word silently shadows the family's when the two
share a concept. Now checked, with the shadowing reported by concept and
the family word it hides.

### 1.2.6 `terms.REGISTRY` is mutable global state — DOCUMENTED, NOT FIXED 2026-10-10

`register()` appends to a module-level dict with no reset. No consumer
registers inside a test (checked across all ten), so the leak the review
imagined has no caller — which makes an `unregister()` API the answer to a
problem nobody has. `register()`'s docstring now says plainly that the
registry is process-global and that a test registering a name leaves it
there for the rest of the run, so the next person to want a reset knows why
there is nothing to call.

### 1.2.7 `_release_parts` is duplicated eleven times — OPEN, audited 2026-10-10

`vinsynlib/__init__.py` plus all ten consumer `entry.py` files carry a copy.
The duplication is *deliberate* — a version gate must not import the library
it is checking, which is the bug that was review F1 in p2ked.

**The audit corrected the review.** The claim that the copies "have already
diverged once (the padding bug)" is wrong. That bug was in the
pre-`_release_parts` `is_compatible_version` — a hardcoded `[:3]`, an
`except ValueError → False`, and a `[:len(minimum)]` truncation — and it was
fixed in `4c02cfc`. `_release_parts` landed in all eleven files *already*
carrying `[:width]`. The copies have never drifted. (Worth noting because the
p2ked review's *proposed* fix used `break` on an empty component where the
landed code uses `return None`, so the more dangerous variant was proposed
and correctly never applied.)

**Current state, measured:** all ten consumer copies are byte-for-byte
identical (SHA-256 `cd8c669559c59640…`); the canonical differs from them in
the parameter name (`version_string` vs `version`) and docstring wording
only. Zero logic drift. So the item reads as a hazard the family has been
lucky with, not as an overdue guard.

**What a drift would do.** The failures are ugly and, importantly,
asymmetric — a drifted copy lands in *one* tool, so the symptom is "s3ked is
broken with this vinsynlib but the other nine work", which is a support
ticket rather than a red build:

| Drift | Failure |
|---|---|
| `tuple(...)` → `list(...)` | `TypeError` on `>=`; **all ten tools refuse to start** |
| `return None` → `break`/`continue` on empty digits | the gate reports *compatible* for a version it cannot parse — the guess the docstring forbids |
| anything letting a non-digit into `digits` | `ValueError` raised **by the guard**, the exact failure it exists to prevent |
| reverting to the pre-`4c02cfc` algorithm | `error: eosed needs 0.2.0 or newer, and 0.2.0 is installed` — a message that is a lie |

**Recommended guard — an AST check in `vinsynlib.devchecks`.** A new
`release_parts_drift(entry_path)` alongside `foreign_imports` and
`config_saves_without_path`, which is where this family already keeps shared
checks. It parses the consumer's `entry.py` and the canonical at
`os.path.dirname(vinsynlib.__file__)/__init__.py` — i.e. **the installed**
library, which is what the gate runs against — drops each leading docstring,
renames the first parameter to a sentinel so `version` vs `version_string` is
neutralised, and compares `ast.dump(..., include_attributes=False)`. Plus
four invariants asserted explicitly on the consumer's copy so a failure names
the drift rather than dumping two ASTs: exactly two parameters with `width`
last; the slice's upper bound is the `width` argument; the empty-digits branch
is `return None`; the return is a `tuple(...)` over `parts + [0] * (width -
len(parts))`.

Runs as one new test module per consumer, `tests/test_version_gate_copy.py`,
following the `tests/test_config_paths.py` precedent — every consumer already
has a `make check → pytest` gate, so no Makefile changes. `vinsynlib` gains
the mirror-image self-check that the canonical satisfies the same
invariants, otherwise the guard can be defeated by editing the library's own
copy and propagating. Updating a copy is then: edit the canonical, run the
propagator (`python -m vinsynlib.entrycheck --write`), and let the failure
messages name what to change — leaving the family red until it is run, which
is the intended outcome.

**Rejected alternative:** each consumer asserting
`inspect.getsource(entry._release_parts) == CANONICAL_TEXT`. It needs a
twelfth copy of the text, so the drift moves rather than disappears; it
compares characters, so it is both too strict (false-fails on the legitimate
`version_string` rename) and too weak (a semantically identical but reworded
copy passes).

**Live evidence the general problem is real:** five consumer working trees
currently hold an untracked `config.toml` (`eosed`, `p2ked`, `rxved`, `s3ked`,
`x5ded`) — exactly the failure `config_saves_without_path` exists to catch,
produced by a test run and left to be found by hand.

### 1.2.8 `midi.likely_ports` docstring is truncated mid-sentence — FIXED 2026-10-10

"...where the user happens to have, and on a bench that was a *different" —
the sentence stops mid-clause.

## 1.3 Execution speed

Measured on tmpfs; **a real disk is worse, not better**, because every
mutation below pays an fsync.

| Operation | Cost |
|---|---|
| `add()` | 1.47 ms/op — 800 favourites in 1.18 s |
| `toggle()` | 1.1 ms/op (2-3 statements, each committed) |
| `refresh_names()` 800 rows | 14 ms, in 800 separately committed UPDATEs |
| `keys()` | 0.91 ms — already one query, this is the good case |
| `tags()` | 2.88 ms |

### 1.3.1 There is no way to batch a write — OPEN

Every public mutator commits. `add`, `remove`, `toggle`, `set_*`,
`refresh_names` each end in `commit()`. For a user toggling one favourite
that is correct and the cost is invisible; for anything that touches more
than a handful of rows the per-op fsync dominates. A transaction context
manager, or a `commit: bool = True` parameter on the mutators, gives a
caller one BEGIN/COMMIT.

### 1.3.2 ~~`refresh_names` should be one transaction~~ — WAS A MISREADING, 2026-10-09

The review claimed 800 separately committed UPDATEs. It is not so: sqlite3
opens a transaction on the first DML statement and holds it until
`commit()`, so the method already committed exactly once. Traced: 204
statements, 1 `COMMIT`.

`refresh_names` now uses `_LockedConnection.transaction()` regardless,
which buys an explicit transaction boundary and a rollback if `lookup`
raises — not fewer commits, since there were never more than one. The
measurement that started this (14 ms) was on tmpfs, where fsync is
effectively free, so the review mistook SQLite's own per-statement cost for
per-commit cost. Lesson recorded: measure on a disk before believing a
throughput number from this machine.

### 1.3.1 Every public mutator commits — by design, needs a caller not a change — OPEN

`add`, `remove`, `toggle`, `set_*` each end in `commit()`. For a single
toggle that is correct and the cost is invisible. There is no bulk API to
batch, and adding `commit=False` to six methods would be API churn no
consumer has asked for. `_LockedConnection.transaction()` now exists for
the caller that does; revisit when something actually imports a bank of
favourites rather than toggling one.

The number worth having is the real-disk one, not the tmpfs one. `add()`
measured 1.47 ms on tmpfs; on spinning disk the same op with
`synchronous=FULL` is an order of magnitude worse, and *that* is the
figure a batching decision should be made against. Measure it there first.

### 1.3.3 `tags()` and `with_tag()` select `*` — FIXED 2026-10-10

Both call `all(order="bank")`, which is `SELECT *` over every active row,
when `tags()` needs two columns and `with_tag()` needs tags plus the
identity columns. At 800 rows it is 2.9 ms; the shape is the problem, not
the number.

Not speed problems: `keys()` is correctly a single query, `wrap_blocks`
is linear, and the `spec`/`terms` lookups are trivial.

## 1.4 Test gaps

What the suite does not currently guard, by uncovered line:

| Uncovered | Why it matters |
|---|---|
| `keys.legend_from_bindings` (258-267) | Public API, used by tools to build a legend from `BINDINGS`, and **entirely untested** |
| `conformance.check_terms` (264-274) | The vocabulary contract's own checker, **entirely untested** |
| `check_flags` forbidden branch (125-126) | The refusing direction of the flag check |
| `terms.for_app` KeyError, `register()` (223-234) | The two things a project calls at import time |
| `midi._rtmidi` ImportError (109-115) | The no-MIDI-stack path a headless box or container hits |
| `favorites.tags()` (493-497), `set_note` (616) | The annotations half of the store |
| `is_compatible_version` with `minimum=()` | Returns `False` today; unpinned, so the behaviour is an accident |
| `config._toml_string` control-character escape (336) | The `\\uXXXX` branch — the one part of the writer no test reaches |

The pattern: the *error* paths and the *helpers that produce rather than
validate* are what is missing. The core read/write paths of `config` and
`favorites` are well covered; the guards around them are not.

## 1.5 How these were verified — a method worth repeating

Two mistakes were made while working through this list, and both are the
same mistake, so the method matters more than the individual finding.

1. **A measurement was taken on tmpfs and believed.** `refresh_names`
   looked like 800 commits because it was slow; it was one commit all
   along, and SQLite's per-statement cost was what was being measured. A
   throughput number from this machine means nothing until it has been
   taken on a disk.
2. **Consumers were tested against the published wheel, not the change.**
   Running emorphed's suite "to check the library change" proved nothing:
   its venv had vinsynlib 0.2.0 from PyPI and never saw the edit. It looked
   like verification and verified nothing.

The lesson for any change to this library that a consumer could notice:
**install the working tree into the consumer's venv and run its suite
there**, then restore the published version afterwards. The check that the
right code is loaded has to be for something that only exists in the working
tree — `hasattr(devchecks, "_WRITER_ARITY")` — not for a symbol that may
have been added or removed by the change itself, which is what made the
first attempt at this silently wrong.

The corollary is the one that cost most: **a consumer's tests are the
contract.** Call sites showed every consumer calling `add` before `set_*`,
and that read as "nobody relies on annotating creating a row". A test named
`test_setting_on_something_not_favourited_creates_it` said otherwise. Read
the tests, not just the calls.

---

# 2. Centralising undo — analysis

## 2.1 What undo looks like today

`vinsynlib` carries the key **contract** and nothing else. `keys.EDITOR_KEYS`
binds `z` to `undo` and `Z` to `undo_all` (lines 131-132), and
`conformance.check_bindings(tier="editor")` will require an editor's App
class to bind exactly those. No stack, no change record, no replay.

Three projects implement it themselves, each with a different change
record:

| Project | Record | What a change *is* |
|---|---|---|
| s3ked | `_Change(region, index, keygroup, name, old, new)` | a wire write to a stateless-addressed slot |
| eosed | `_Change(param_id, old, new, voice, link, scope)` | a wire write in a **stateful** protocol — the selection must be restored first |
| rxved | `_Change(kind, bank_id, number, old, new, name)` | an edit to the **favourites store**, which is already library code |

Roughly 35-60 lines of machinery each, ~150 duplicated in total plus the
three records.

## 2.2 What is genuinely common

Reading the three side by side, the shared parts are not the obvious ones:

1. **LIFO order with clamping** — `min(count, len(log))`, newest first.
   Identical in all three.
2. **Pop only after the revert succeeded.** All three do this, and two of
   them spell the rule out in a comment; rxved's says explicitly "the same
   rule the sibling editors' undo follows". A failure part-way must leave
   the log describing what is *still applied*.
3. **An undo is a write, so it is gated like one.** s3ked: "write gate is
   locked — undo is a write". eosed: "writes disabled — press 'w' to arm
   write mode". rxved has no gate, because favourites are not the
   instrument. The *rule* is common; its applicability varies.
4. **An empty log says "nothing to undo"** rather than raising.
5. **A pending-change indicator in the subtitle** (s3ked "N change(s)",
   eosed `ΔN`, rxved `ΔN`).
6. **In-memory and unbounded, on purpose.** rxved states it: "nothing here
   worth surviving a restart, and a cap would only ever be hit by the
   person who wants it least."
7. **Device writes run on a worker thread** (s3ked, eosed) because a MIDI
   write blocks.

Items 2 and 3 are the valuable ones. They are *invariants*, currently
stated in prose in three files and enforced by nothing. `conformance.py`
checks flags, bindings, legend and terms — it has nothing to say about
undo. So a fourth editor, or a refactor of one of these three, can drop
the gate check or pop-before-write and nothing will notice.

That is precisely the argument this library was built on: nine copies of
the settings cache drifted, so the cache moved here and a conformance
check now guards the contract.

## 2.3 What genuinely varies

1. **The change record.** This is the crux. It is about the thing being
   written, so it is protocol-shaped and cannot be centralised as data
   without becoming `Any`.
2. **Scope restore before replay.** eosed must restore `VOICE_SELECT` /
   `LINK_SELECT` before writing the old value back, or it lands on
   whatever is selected now. s3ked explicitly does not — stateless
   addressing — and says so in its `_Change` docstring. The projects have
   already identified the axis of variation themselves.
3. **Dispatch.** rxved's `_apply_undo` is a four-way `kind` switch calling
   `Favorites` methods.
4. **Coalescing.** s3ked merges a run of consecutive nudges on the same
   address into one entry so one `z` puts the whole run back — and it
   carries a hardware-found bug in the comment explaining why (a hardcoded
   keygroup zero, where every synthetic test passed because nobody pressed
   `z` and then looked at the log).
5. **UI surface.** eosed has a `HistoryScreen` that *renders* the log
   without replaying it. That requires the record to stay inspectable
   data, not a closure.
6. **Threading and locking.** eosed holds `self._bridge_lock` across the
   whole batch and uses `call_from_thread`; s3ked uses `@work(thread=True)`
   per change. Threading policy is per-project and must not be owned by a
   shared loop.

## 2.4 The gain, honestly

A library module that owns the loop and leaves the record and the replay
to the project would absorb items 1, 2, 3, 4 and 6 from §2.2 — call it
30-40 lines per project. Converted to a tested implementation once:

- The invariants move from prose in three files to code with tests.
- `conformance` gains something to check: an editor's log is the family's
  type, `z`/`Z` are bound, and its replay path goes through it.
- A fourth editor gets them free.

That is real, but it is ~100 lines of duplicated machinery — an order of
magnitude less than the ~6,300 lines this library already absorbed, and
spread over three consumers rather than nine.

## 2.5 The cost, honestly

1. **A generic record is nearly empty.** With the record project-shaped
   and the replay a callback, the library's type is roughly
   `(label, payload)` plus a log. The projects keep their `_Change`, so
   what is actually shared is the loop and the guards.
2. **The record must stay data, not a closure**, or eosed's history
   screen and rxved's "carry a preset write when editing arrives" plan
   both break. That rules out the simplest possible API
   (`record(lambda: undo())`).
3. **Three refactors of hardware-tested code**, for ~30 lines each.
   s3ked's undo was corrected against a real instrument and its comment
   records that synthetic tests never caught it. This library's own
   history is the warning: F1 was "one patch, applied ten times", and a
   one-line class of bug in it reached every project.
4. **Only 3 of 10 projects have undo** at all.

## 2.6 Decision — Option A

**Decided, 2026-10-09: Option A.** Every project in the family will have an
undo function, which changes the arithmetic this library was built on.

The threshold that justified vinsynlib was *nine* copies of the same code.
Undo sits at three today and is headed for ten. That is above the line, and
it is the same line: the parts worth sharing are invariants that are
currently stated in prose in three files and enforced by nothing, and the
moment a tenth project needs them they will be written an eleventh time.
Landing them once, with tests, is cheaper than writing them again and
cheaper still than debugging the copy that gets it wrong — which, on this
family's record, happens (s3ked's keygroup zero, F1's padding bug).

**The cost analysis in §2.5 still stands.** Option A is a real refactor of
hardware-tested code for ~30 lines of savings per project. What the
decision changes is the *order of work*, not the risk, and the ordering
below exists to keep the risk from being paid three times over.

### 2.6.1 Requirements the module must satisfy

Derived from §2.3. These are not preferences; getting one wrong breaks a
working project.

- **R1 — the record stays inspectable data, not a closure.** eosed's
  `HistoryScreen` renders the log without replaying it, and rxved's
  `_Change` docstring says it chose data over a closure precisely so the
  same log can carry a preset write when editing arrives. The simplest API
  (`record(lambda: undo())`) is therefore ruled out.
- **R2 — the library owns no threads and no locks.** eosed holds
  `self._bridge_lock` across the whole batch and uses `call_from_thread`;
  s3ked runs `@work(thread=True)` per change. Threading policy stays with
  the project; the log is a plain synchronous object.
- **R3 — hooks, not assumptions.** `apply(change)` is the project's replay
  and includes its scope restore; `gate()` returns a refusal reason or
  `None` (an undo is a write, gated exactly like one); `status(message)`
  is how it speaks to that project's status line or notifications.
- **R4 — the library owns, and tests, the invariants.** LIFO order,
  `min(count, len)` clamping, **pop only after a successful revert** (so a
  failure part-way leaves the log describing what is still applied),
  `undo_all` newest-first, the empty-log message, and the gate refusing
  *without touching the log*.
- **R5 — coalescing stays project-side or becomes an opt-in helper.**
  s3ked merges a run of consecutive nudges on the same address key into
  one entry; that logic is address-shaped and belongs to it.
- **R6 — no new dependency, stdlib only,** in a new `vinsynlib/undo.py`.

### 2.6.2 Order of work

1. **Land `vinsynlib/undo.py` with its tests and no consumers.** The
   invariants in R4 are the deliverable; a module nobody imports yet is
   the cheapest place to get them wrong.
2. **Convert rxved first.** It is the least hardware-bound of the three,
   and its `_apply_undo` is a dispatch over `Favorites` — library-owned
   state — so its replay function is the simplest one to write. Option B's
   work is subsumed here rather than wasted: rxved's store rollback
   becomes the first `apply()` implementation instead of a separate
   method on `Favorites`.
3. **Convert eosed and s3ked as two separate changes**, one commit each,
   each with its own `make check`. s3ked's undo was corrected against a
   real instrument and its comment records that synthetic tests never
   caught that; a change to it is not verifiable by CI alone, so it wants
   its own commit and its own hardware note.
4. **Give `conformance` something to check:** an editor's log is the
   family's type, `z`/`Z` are bound to `undo`/`undo_all`, and its replay
   path goes through the log. This is the step that makes the module pay
   for itself — without it, the next project can bypass it.
5. **Then the `docs/UX-SPEC.md` paragraph in §2.7.**

### 2.6.3 What this does not decide

The change *record* stays project-shaped. A shared record would have to be
`(label, payload)` with the payload opaque, which is a generic that buys
nothing — the three records differ in what they need to say, and §2.3 lists
exactly how. If a later refactor wants to unify them, that is a separate
decision about protocols, not about undo.

## 2.7 A note either way

Wherever undo ends up, the write-gate interaction should be stated in the
library's docs — `spec`'s `allow-write` flag says "start with the write
gate armed", and the family rule that an undo *is* a write and is gated
like one currently exists only in two status strings. That is a
one-paragraph change to `docs/UX-SPEC.md` and is worth doing regardless
of which option is chosen.
