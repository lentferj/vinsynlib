<!--
SPDX-License-Identifier: GPL-2.0-or-later
SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
-->

# unify2 — the second unification

The first unification took nine copies of the settings cache, the favourites
store, the keymap, the command line and the port listing and made them one
library. This is the second: what is still copied, now that the family has
a shared home for it and ten projects rather than nine.

It exists because a question was asked — *under the assumption that the five
quiet projects acquire the feature set the two loud ones have, what should
move into vinsynlib?* — and answering it turned up two places where the
library's own contract already says it does something it does not.

**Related documents.** `TODO.md` §2 carries the undo decision (Option A) and
§3 the version-gate adoption; this document does not repeat them. The
long-form reasoning for the first unification is in each project's history;
`docs/UX-SPEC.md` is the contract, and two of its sentences are load-bearing
here.

---

## 1. Evidence

Two kinds, and the first is stronger than the second.

### 1.1 The library already promised two things it does not do

**The launch reporter.** `docs/UX-SPEC.md` §4:

> A project may supply its own `on_fallback(port, error)` to name the reason
> in its own words; **otherwise the library prints the family's one-liner.**

It does not. With no hooks supplied,
`vinsynlib.midi.open_remembered_or_swept` prints nothing at all:

```
UX-SPEC says: 'otherwise the library prints the family's one-liner'
what it actually printed with no hooks: (NOTHING)
```

Meanwhile all ten projects hand-write their own — `p2ked` has a whole module
for it, whose docstring states the argument that should have put it in the
library in the first place:

> the fallback notice is the one thing that tells a user their launch took
> the slow path, and two copies drift until only one of them says so.

This is not a proposal. It is a contract violation of exactly the kind this
family keeps finding: a document saying one thing and the code saying
another, with nothing failing.

**`--json`.** `docs/UX-SPEC.md` §6 says *"No tool has it."* `p2ked` has it
(`p2ked/cli.py:513`). Minor, and in the section that is explicitly about
what is unsettled — but it is stale, and §6 is where a reader looks to find
out what is left.

### 1.2 What is copied today, measured

Counted across the ten, excluding `.venv`, `build`, `__pycache__`, `tests`,
`probes` and `tools`:

| Concept | Projects with their own copy |
|---|---|
| Modal text prompt | **10 / 10** |
| Launch/fallback notices | **10 / 10** |
| Demo device | **10 / 10** (concept only — see §4) |
| Catalog layer | **7 / 10** |
| Names read off the unit, cached | 1 today, several shortly |
| Rating glyph | 1 today, six shortly |
| History / undo screen | 4 |
| Confirm dialog | 4 |

The five quiet projects are assumed here to acquire rxved's and p2ked's
feature set. On that assumption the counts above rise less than they look
like they should, and the reasons differ per item: the prompt is already in
all ten; the catalog is already in seven, five of which are the quiet ones;
what the assumption adds is *depth* rather than copies — the live-name cache
that only rxved has, annotation rendering that only rxved has, a write path
that wants a confirm dialog. The one count that is genuinely brought forward
by the assumption is the catalog's interface: `UX-SPEC.md` §6 measured
*"Six copies at 55–100% identical"* when it was written, there are seven
now, and a uniform feature set is what makes the interface worth converging
rather than the copy count.

---

## 2. The rule

Unchanged from the first unification, and worth restating because it is what
decides every item below:

> What belongs here is what is *not* the manufacturer's: how a preference is
> remembered, where a favourite lives, what an error says, which key means
> what. What stays in each project is what the hardware owns: the wire
> format, the bank table, the meaning of a byte.

So an extraction must be **non-manufacturer**, and worth doing when it is
**copied or about to be**. Both halves matter: §4 is a list of things that
are copied ten times and still must not move.

---

## 3. What moves

In order of confidence. The first is a bug fix dressed as an extraction.

### 3.1 The launch reporter — spec-promised, all ten

**What.** The three sentences a launch prints: that it is probing a port,
that the remembered port did not answer and why, and (optionally) that the
remembered port answered.

**Why it is first.** It is the only item here the library has already
undertaken to do. Fixing it removes a contract violation rather than adding
a feature, and it is small.

**API.** Three functions in `vinsynlib.midi` — headless, no Textual, no new
import:

```python
def say_probing(name: str, *, stream: TextIO = sys.stderr) -> None
def say_fallback(port: str, error: BaseException, *, stream: TextIO = sys.stderr) -> None
def say_connected(port: object, *, stream: TextIO = sys.stderr) -> None
```

Wording taken from the two that exist, so the family converges on the
wording it already reads rather than on a new one. `p2ked/p2ked/_report.py`:

```
  probing {name}...
  {port}: remembered, but {exc}. Probing every port (--scan does this on purpose).
  {port} (remembered)
```

**Wiring, precisely.** The spec's promise is about the *fallback* line, so
that is the minimum. `open_remembered_or_swept` installs a default only when
the caller supplies **neither** hook:

```python
if on_try is None and on_fallback is None:
    on_fallback = say_fallback
```

That is deliberate. A caller that passes `on_try` alone keeps the legacy
path (its fallback notice arrives through `on_try`); a caller that passes
`on_fallback` keeps its own words; a caller that passes both is untouched.
Only a caller that passes nothing — the case the spec describes, and
probably the common one once the five new tools exist — gets the library's
line. This must be tested for all four combinations, because the legacy
branch is easy to break from here.

`say_connected` is available but **not** wired by default. A fast launch
printing "remembered" on every run is noise, and the spec frames the fast
path as the unremarkable one. p2ked prints it and can keep doing so.

**Consumers.** Each of the ten deletes its own reporter and passes the
library's functions, or nothing at all. `p2ked`'s `_report.py` goes, and
with it the `on_try`/`on_fallback` wiring in `p2ked/cli.py` and
`p2ked/app.py`.

**Verification.** A test per combination of hooks (none / only `on_try` /
only `on_fallback` / both), asserting exactly what reaches stderr — not just
that something did. `p2ked`'s `tests/test_connect.py` already asserts on the
fallback text and is the model.

### 3.2 The modal prompt — ten copies

**What.** One line of text, asked and answered: the note editor, the tag
editor, the search box. Every one of the ten has a `ModalScreen[str]` for
it; `p2ked` gave it its own module for the reason that generalises — a
widget living inside one of its callers is a cycle waiting to happen.

**API.** `vinsynlib/ui/prompt.py`, beside `ui/hints.py`:

```python
class PromptScreen(ModalScreen[str | None]):
    def __init__(self, prompt: str, current: str = "", *,
                 placeholder: str = "", id: str | None = None, **kwargs) -> None
```

`None` on cancel, matching `p2ked`'s existing contract, and the `id` on the
inner `Input` matters because tests drive it.

**Why it is low-risk.** It is a self-contained widget with one job, its
shape is already agreed by ten independent copies, and `vinsynlib.ui` exists
for exactly this. The only thing to check is that each project's `BINDINGS`
expectations survive — `escape` cancels, `enter` submits.

**Consumers.** Ten. Each deletes its class and imports the library's; most
already re-export it under the old name, so call sites can be left alone
during the change and tidied separately.

### 3.3 Annotation rendering — one today, six shortly

**What.** How a rating reads in a table and how an annotation column reads.
rxved's is the only one that exists and its docstring already argues for the
library:

> both front ends show a rating and a second copy of a glyph is exactly the
> kind of thing that drifts

**API.** In `vinsynlib/favorites.py`, deliberately **not** in `ui`:

```python
def rating_cell(rating: int, *, scale: int = 5) -> str
```

rxved's own note explains the placement: *"it lives in this module rather
than in `rxved.screens` because the headless front door must not pay for
Textual: importing screens costs about 300ms, against about 75ms for the
whole of `rxved.cli` today."* Any extraction that forces Textual into a CLI
import path is the wrong extraction, and this is the item where that is
easiest to get wrong.

Keep the two decisions the function already encodes: show the value **and**
the scale (`★★★··`, not `★★★`), and blank for zero rather than five dots.
And keep `*` out of it — it already means "this name disagrees with the
catalogue" two columns over.

**Consumers.** rxved now; the five when they gain favourites with ratings.

### 3.4 The confirm dialog — four today

**What.** A yes/no modal for anything that cannot be undone. s3ked's
description is already generic: *"Generic yes/no, used for anything that
cannot be undone."*

**API.** `vinsynlib/ui/confirm.py`:

```python
class ConfirmScreen(ModalScreen[bool]):
    def __init__(self, prompt: str, *, confirm: str = "Yes",
                 cancel: str = "No", danger: bool = False) -> None
```

`y` confirms, `n`/`escape` cancels, matching s3ked. `danger` is there
because the destructive paths in these tools differ in how loudly they
should say so, and a plain yes/no styled identically for "delete this bank"
and "reload names" is the kind of uniformity that costs a user data.

**Consumers.** eosed, k2kremote, rxved, s3ked today; the five as they gain
write paths.

### 3.5 Undo — already decided

`TODO.md` §2 records the decision (Option A) and the six constraints the
module must satisfy. Not repeated here. What this document adds is the one
piece §2 does not cover: **`HistoryScreen`**, which four projects have and
which is the *rendering* of the log. It cannot move before the log does, and
when it does, it belongs in `vinsynlib/ui` — it needs Textual, while the log
itself must not.

### 3.6 The catalog layer — seven today, and the assumption deepens it

**What.** The generated names file, the live layer read off the instrument,
the disagreement between them, display, search, and the cache of live names
between runs.

**Why it is last of the real items.** `UX-SPEC.md` §6 has already declined
to decide it once:

> Six copies at 55-100% identical. The copies differ in what a key is made
> of -- `bank_id:kind:number` in `kwsed`, `bank_id:program_change` elsewhere
> -- so unifying it means deciding what a catalog entry *is*, which is a
> larger piece of work than a naming exercise.

That is correct, and it is still correct. What has changed since is not the
copy count — it is seven today, and all five of the quiet projects are among
them, so the assumption in §1 does not add catalogs — but the *pressure*.
Two things bring it forward:

- The interface is what the five converge on, and it is the one place where
  they would each independently answer the "what is a key" question and
  answer it differently. Divergence is cheapest to prevent now.
- The live-name cache (`livenames.py`) is part of this layer, and rxved is
  the only project that has noticed the problem it solves. If the five gain
  writable banks without it, they will each rediscover it — which is how the
  first unification's copies came to exist.

It should be done with the decision made first, and in its own release.

**The decision.** The three implementations agree on almost everything:

- `Entry` with a `key` property, and `Catalog` with `entry`, `name`, `has`,
  `__len__`, `__bool__`, `set_live_name`, `live_name`, `is_live`, `differs`,
  `display_name`, `search`; module-level `empty()` and `load(path)`.
- rxved adds `dump()`, categories, and `printed_list_void`.

They disagree on one thing: **the arity of a slot key.**

```python
rxved,  p2ked:  catalog.entry(bank_id, number)             # 2 arguments
kwsed:          catalog.entry(bank_id, kind, number)       # 3 arguments
```

kwsed needs the third because a Korg bank holds patches *and* performances
under one bank id. Two ways to settle it, and they are not equivalent:

1. **Every key carries a `kind`, defaulting to `""`.** Uniform, explicit, and
   every existing call site in nine projects grows an argument it does not
   have a value for. The machinery is then shared but the interface is
   noisier for the majority, which is the wrong trade at a 9:1 ratio.
2. **A key is `(bank_id, number)`, and a bank that holds two kinds of thing
   says so in its id.** kwsed already talks about `PAT-A` and `PRF-A` in its
   own bank table; folding the kind into the bank id makes the two-argument
   form correct everywhere and costs kwsed nothing but a rename in its
   `banks.py`, which is its own business and the manufacturer's.

**Recommendation: 2.** The key is not the family's to complicate; what a
bank is *called* is the manufacturer's, and kwsed already names its kinds.
The library would then ship `Entry`, `Catalog`, `load`, `empty`, and
`dump`, and would *not* ship categories — those are Roland's.

**Also included:** the live-name sidecar. rxved's `livenames.py` persists
the live layer between runs, and its docstring states the problem the other
implementations have not noticed they have:

> the catalog says what the factory shipped, and a USER bank that has been
> saved into says something else entirely... Every restart fell back to the
> printed list, so the browser confidently showed the factory USER bank for
> a machine full of the user's own patches.

That is not a Roland problem. Any tool with a writable bank has it, and the
five new ones will. The live cache belongs with the layer that owns the live
layer — `Catalog` keeps `set_live_name` in memory; the file that survives a
restart should be part of the same extraction, not a second one later.

**Consumers.** Seven now, eleven eventually. Each keeps its own generated
JSON and its own categories; each loses its `Catalog` class.

### 3.7 `config_dir(tool)` — already recorded

`p2ked`'s review flagged this as "the proper long-term fix" for nine tools
defaulting to the same relative `config.toml`; the header guard in
`vinsynlib.config` works around it. At ten tools the workaround is load
bearing, and the fix — default the cache to a per-tool directory rather than
a shared relative path — is a library change with a `--config` help-text
consequence and a migration for anyone with an existing `config.toml`.
Cheap to do, but it *changes where a file is*, so it wants its own release
and a note louder than a bullet in a changelog.

---

## 4. What does not move

The rule in §2 cuts both ways, and these are the traps.

### 4.1 The demo device

Ten of ten have one, which looks like the strongest case on the list and is
in fact the weakest. The *flag* is family — `--demo`, "the built-in demo
device; opens no ports" — and already lives in `spec.py`. The *device* is
not: it answers the Identity Request of one instrument and models that
instrument's banks, and the method names barely coincide across the ten:

| method | projects (of 10) |
|---|---|
| `identify` | 5 |
| `select` | 7 |
| `send` / `read` / `open_port` / `close_port` | **0** |

They are shaped to their own bridges. Extract the flag's semantics if there
is anything left to extract; leave the fake devices where they are.

### 4.2 The bank table

`UX-SPEC.md` §6: *"Every tool has one and no two agree on shape, because the
instruments do not agree... Left alone deliberately."* Still right.

### 4.3 The protocol modules

rxved's `effects.py` (2,395 lines), p2ked's `multi.py` (2,361) and
`masteredit.py` (1,192), eosed's bridge. These are the instruments. They are
also where almost all of the lines are, which is the temptation — the first
unification was justified by 6,300 duplicated lines, and none of these are
duplicated at all.

### 4.4 Catalog *content*

The generated JSON, the categories, the printed-versus-live distinction as
it applies to one manufacturer's ROM set. Only the layer moves.

---

## 5. The plan

### 5.1 Ordering, and why

Dependency order, not preference order:

```
  3.1 reporter ──┐
  3.2 prompt   ──┤
  3.3 rating   ──┼─→ release 0.4.0 ─→ adopt in rxved, then the rest
  3.4 confirm  ──┤
  3.5 undo     ──┘   (constrained by TODO.md §2.6.2)

  3.6 catalog  ──────→ needs the key decision first, then its own release
  3.7 config_dir ────→ needs its own release, and a migration note
```

`3.1` through `3.5` are independent of each other and can share one release.
`3.6` needs a decision and is the largest change; it should not be in the
same release as five other things, because if the catalog change is wrong
the other five are harder to bisect. `3.7` changes where a file lives and
must be alone.

### 5.2 Per-extraction checklist

For each of `3.1`–`3.5`, the same five steps, in this order:

1. **Land it in vinsynlib with tests and no consumers.** A module nobody
   imports is the cheapest place to get it wrong. For `3.1` that includes
   the four hook combinations.
2. **Release it.** Publishing is the point at which a consumer can depend on
   it, and the family's own record is that a library that is *ahead of the
   index with no plan* is how drift starts (`TODO.md` §1.3.1).
3. **Adopt it in one project.** rxved where it applies, because it is the
   least hardware-bound and has the richest feature set, so it exercises the
   most of any extraction. Not a sweep — see §6.2.
4. **Adopt it in the remaining projects**, one commit each.
5. **Update `docs/UX-SPEC.md`** if the extraction changes the contract. For
   `3.1` this is mandatory: the spec already describes behaviour that did
   not exist, and it should end up describing behaviour that does.

### 5.3 What `3.1` looks like concretely

The first one, end to end, because it is the template for the rest:

- **`vinsynlib/src/vinsynlib/midi.py`** — add `say_probing`, `say_fallback`,
  `say_connected`; export them in `__all__`; install the `say_fallback`
  default in `open_remembered_or_swept` when both hooks are absent.
- **`vinsynlib/tests/test_midi_and_checks.py`** — the four hook
  combinations, asserting the exact text (following the existing
  `test_the_fallback_says_so_rather_than_pretending_to_be_fast`), and that a
  `say_*` writes to a passed `stream` rather than the real stderr.
- **`CHANGELOG.md`** — under a new `[0.4.0]`: the fallback line the spec
  already promised, and the note that a caller passing neither hook now
  hears from the library.
- **`docs/UX-SPEC.md`** — no change needed if the wording lands as the spec
  describes it; a change needed if it does not.
- **`p2ked`** — delete `_report.py`, pass nothing (the library's line is
  what `p2ked` was printing) or pass `say_connected` if it wants the
  fast-path line back, and re-point `tests/test_connect.py`.
- Then the other nine.

### 5.4 Verification discipline

The lesson from the version-gate adoption applies to every item here, and
it cost two rounds to learn:

- **Test against the installed library, not the working tree.** A consumer
  suite run "to check the change" proves nothing if the consumer's venv
  still holds the old release — which is exactly what a first attempt at
  the gate verification did.
- **Verify the consumer's whole gate, not the new test alone.** `make check`
  for each project, because these extractions touch import paths and
  deleting a class can orphan a re-export.
- **One project at a time.** A flaw in a new shared widget presents as ten
  indistinguishable failures, and the gate adoption already showed what
  that costs: the first adopter found a path bug that the other nine would
  have hit simultaneously.

---

## 6. Mechanics

### 6.1 Releases

Each phase is a minor release on the 0.x line: `0.4.0` for `3.1`–`3.5`,
`0.5.0` for `3.6`, `1.0.0`-candidate for `3.7` if the file move warrants it.
The existing `publish` workflow and trusted publishing do the work; the
`0.3.0`/`0.3.1` cycle is the rehearsal that already happened.

Consumers raise their floor in the same commit that adopts the change, as
they did for `0.3.1`. A consumer that does not adopt does not move.

### 6.2 Adoption is not a sweep

Every extraction gets adopted by one project first and merged alone, then
the rest. The reason is not caution for its own sake: it is that a shared
widget's flaw is invisible until something mounts it, and the family has
already paid for learning this once.

### 6.3 The `_release_parts` guard, applied to this

`devchecks.release_parts_drift` exists because a deliberate copy drifts. The
same question applies to what this document leaves behind: after §4, there
are still ten demo devices and eleven bank tables. Neither wants a drift
check — they are *supposed* to differ — but the boundary between "supposed
to differ" and "has drifted" is exactly where a check pays for itself, and
it is worth asking per item whether one is needed before declaring it out of
scope.

---

## 7. Risks

- **`3.2` and `3.4` pull Textual into `vinsynlib.ui`.** It is already an
  extra (`[project.optional-dependencies] ui`), so nothing breaks, but a
  project that imports the widget for a headless path pays for it. `3.3` is
  the one where this is easy to get wrong, and the placement is specified
  above for that reason.
- **`3.6` is a design change wearing an extraction's clothes.** The key
  decision is genuinely a decision; getting it wrong is a rename in nine
  projects. Hence its own release.
- **`3.1` changes behaviour for a caller that passes no hooks** — from
  silent to speaking. That is the point, and it is still a behaviour change
  a project could notice in its test output. It is called out in the
  changelog as such.
- **The assumption may not hold.** This document is written on the premise
  that five projects acquire rxved's and p2ked's feature set. If they do
  not, `3.3`, `3.6` and the live-name cache lose most of their value, and
  `3.1`, `3.2`, `3.4` and `3.5` stand on their own regardless.

---

## 8. Open decisions

1. **The catalog key** — `kind` in every key, or folded into the bank id.
   §3.6 recommends the latter. This is the blocker for `3.6`.
2. **`say_connected` by default?** §3.1 says no; p2ked's existing behaviour
   says yes for p2ked. Settle whether a fast launch is silent family-wide.
3. **Does `--json` move?** The spec lists it as the next uniformity and is
   wrong that no tool has it. If it becomes uniform, the flag and a shared
   shape belong in `spec.py`/`cli.py`; that is a `3.8`, not started here.
4. **When is the demo flag's semantics more than the flag?** §4.1 says the
   devices stay. Worth one more look before the five new demos are written,
   because if there *is* a shared skeleton, discovering it afterwards is
   eleven rewrites rather than one extraction.
