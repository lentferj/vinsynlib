# The family contract

Nine sibling programs browse nine instruments over MIDI from a terminal.
They grew separately, and this is the agreement they now keep.

The contract is in four parts, and each has a machine-readable form in the
library: the [terminology](#1-terminology), the [command
line](#2-the-command-line), the [keys](#3-the-keys), and the [paths and
formats](#4-paths-and-formats). Where a project disagrees with this
document, the project is wrong unless it can say why here.

---

## 1. Terminology

### Two tiers, and the reason for them

**Our words are the same in every tool.** These name things that belong to
the program, not to the manufacturer: *favourite*, *search*, *scan*,
*dump*, *port*, *device*. No tool may invent a synonym. The list is
`vinsynlib.terms.FAMILY`, and it is checked.

**The instrument's word is the instrument's.** The word for one stored
sound, and for the area it lives in, belong to the manufacturer. Each tool
declares both once, in a `Terminology`, and uses them consistently
*within itself*: in the CLI help, the legend, the pane headings and the
README.

Why not force one word on all nine: the unit prints its own word on its own
display. A Yamaha XV-2020 says PATCH. An E-mu Proteus says PRESET. A tool
that renames these is a tool that must translate, and a mistranslation
here is the difference between finding a sound and not.

### What each tool declares

| Tool | Stored sound | Lives in |
|---|---|---|
| `emorphed` | preset | region |
| `ensqsqed` | sound | group |
| `nanosyned` | program | bank |
| `p2ked` | preset | bank |
| `kwsed` | patch | bank |
| `x5ded` | program | bank |
| `rxved` | patch | bank |
| `s3ked` | program | memory |
| `eosed` | preset | bank |

Two of these need a note, and one needs a correction.

**`x5ded` said "slot" in its list view and "program" on the wire.** Both
were in the same program, in the same session. The wire's word stays in
the code that builds wire messages; the tool's word is used for everything
the user reads. It is a program, in a bank, and the list view now says so.

**`kwsed` has two kinds of thing in one bank.** A performance is up to
eight parts; a patch is one sound. Performance 7 is not patch 7, and the
tool says so. The favourite key is therefore `RAM1:performance`, not
`RAM1:patch` -- the *kind* is part of the identity, which is the one
documented exception to keying a favourite on the slot alone.

**`s3ked` and `eosed` have no favourites at all.** They are editors, not
browsers, and there is nothing to favourite. The keys and the flags for
favouriting are absent rather than present and broken. See
[§3](#3-the-keys) and [§2](#2-the-command-line).

### Words that are not ours to change

* **favourite**, not favorite, in every string a user reads. The
  `--favorites` flag keeps the American spelling because it is on nine
  command lines already and the file it names is `favorites.db`.
* **MIDI port**, for the connection. A *device* is the instrument; a
  *port* is the way to it. `--port` names a port, `i` opens a device report.
* **read names**, for asking the unit what things are called. Distinct from
  **scan**, which walks a bank by selecting every slot and therefore plays
  it. `rxved` draws that distinction in its help text and the distinction
  is the family's: a scan that plays the instrument says so.
* **settings cache** for `config.toml`, **favourites database** for
  `favorites.db`.

---

## 2. The command line

Every tool has two front ends with the same parser options: a browser
(`x5ded`) and a pipe (`x5cli`). Same flags, same help text, same exit
codes.

### Options

Canonical spellings, and the older ones that still work. A tool adds only
what its hardware needs; a flag that is accepted and then ignored is worse
than no flag, because it teaches the user that a flag can lie.

| Option | Means | Also accepted |
|---|---|---|
| `--port PORT` | MIDI port name | |
| `--scan` | probe every port again instead of trusting the remembered one, and update `config.toml` | |
| `--recv-port PORT` | input port, when it differs from `--port` | |
| `--channel N` | channel to send on, 1-16 | |
| `--device-channel N` | the unit's own base channel | `--midi-channel` |
| `--device-id N` | SysEx device ID | |
| `--exclusive-channel N` | SysEx exclusive channel | |
| `--demo` | the built-in demo device; opens no ports | |
| `--timeout SECONDS` | how long to wait for a reply | |
| `--catalog PATH` | generated name catalog | |
| `--config PATH` | settings cache | |
| `--favorites PATH` | favourites database | |
| `--yes` | do not ask before changing the unit | |
| `--allow-write` | start with the write gate armed; editors only | |

`--channel` and `--device-channel` are not synonyms, and mixing them up was
one of the worst of the old inconsistencies: one tool called the send
channel `--channel` in its CLI and `--midi-channel` in its own browser, and
nothing said which was which. They are different numbers on most of these
instruments.

### Commands

Canonical name, then the older names that still work as aliases.

| Command | Does | Also accepted |
|---|---|---|
| `ports` | MIDI ports on this host | |
| `status` | ask the unit who it is | |
| `banks` | the bank table | `groups`, `regions`, `roms` |
| `list BANK` | one bank's slots | |
| `find NAME` | search names | `search` |
| `fav` | the favourites database | `favorites` |
| `tags` | tags in use, with counts | |
| `names [BANK]` | read names off the unit | |
| `current` | what the unit is playing | |
| `select` | select a slot ON THE UNIT | `reach` |
| `read FILE` | read a dump file | `syx` |
| `dump` | dump a bank off the unit | |
| `send` | WRITE a dump into the unit | |
| `hardware` | what the unit reports about itself | `config`, `inquire` |
| `channels` | every MIDI channel, and what it selects | |
| `multi` | multi-mode setup | |
| `mixes` | the unit's mix slots | |
| `resolve` | what does this MSB/LSB/PC select? | |
| `params`, `programs`, `samples`, `audit`, `header`, `get`, `set`, `memory`, `catalog` | | |

Two of these renames were forced by a collision rather than by taste.

**`config` is no longer a command.** In `p2ked` it meant "which ROMs are
fitted", while the `--config` flag beside it meant the settings file: one
program using one word for two things, in one line of help output. The
command is `hardware`; `config` still works as an alias, so old command
lines do not break.

**`roms` is no longer the command for `p2ked`'s bank table.** The family
calls that table banks everywhere else, and `p2ked`'s own browser called it
banks while its CLI called it ROMs. `banks` is canonical; `roms` is an
alias.

### Help and exit codes

Every flag has help text. It was half the family that did not, and the
half that did not were the flags most worth explaining.

| Code | Means |
|---|---|
| 0 | it worked |
| 1 | it did not: nothing answered, it refused, the file was unreadable, the answer was declined |
| 2 | the command line was wrong (argparse's own code) |

An error is always `error: <what happened>` on **stderr**. One format, so a
message can be recognised without knowing which of the nine produced it.

Nothing that writes to hardware runs from a command line without an
explicit arm: `--yes`, or a typed confirmation, or both. `s3ked` and
`eosed` keep their destructive operations out of the CLI entirely and say
so in the epilog, which is a stronger version of the same rule.

---

## 3. The keys

### What the shared keys are

| Key | Does |
|---|---|
| `↑↓` | move |
| `tab` | switch pane |
| `⏎` | select on the unit |
| `r` | read names |
| `/` | search |
| `[` `]` | channel down, up |
| `c` | set channel |
| `f` | favourite |
| `F` | favourites view |
| `t` | tags |
| `n` | note |
| `i` | device |
| `?` | help |
| `q` | quit |

`rxved` has two more that mean the same everywhere it appears: `s` scan
bank, `x` probe SRX. They are its own, and other tools do not take them.

### The keys that needed a decision

**`m` meant five things.** Multi mode in `kwsed`, Channels in `p2ked`,
Multi-mode setup in `rxved`, Master in `s3ked`, Master in `eosed`. In a
browser it now means **channels**: `kwsed`'s Multisets *are* channel
assignments, so this clarifies rather than changes. In an editor it means
the **master menu**, where the destructive operations live.

**`r` meant "Read names" in seven tools and "Refresh" in two.** Both are
honest. The shared idea is *re-read from the device*, and the legend says
which of the two this tool is doing.

**`i` means "Device" in a browser and "Integrity" in an editor.** Not a
conflict: no tool is both. A browser that wanted `s` for "Save" would be.

### The editors' shared keys

`s3ked` and `eosed` are editors rather than browsers, and the shared
browser keys would be wrong for them -- there is no favourite to toggle in
a tool with no favourites database. They agree with each other instead:

`r` refresh, `w` write gate, `z` undo, `Z` undo all, `h` history,
`m` master menu, `?` help, `q` quit.

### The legend

The legend wraps rather than truncates: a footer that silently drops its
last keys teaches the user those keys do not exist. It is in the shared
order, and a tool's own hints go in one place -- after `n note`, before
`i device` -- so a reader's eye finds them in the same spot in all nine.

Two tools already built their legend from their bindings, which is the
better way round: a hand-written legend is a second list to keep in step,
and it drifts.

---

## 4. Paths and formats

### Two files, two very different jobs

`config.toml`, in the working directory, gitignored. **Disposable.** It
records which port answered last so that starting again does not mean
setting the same things again. Deleting it costs one re-entry of each.

`favorites.db`, in the per-platform *data* directory. **The user's own
work.** It is keyed on the slot rather than the name, so a favourite
survives a rename. It is SQLite, and that is not over-engineering for a
list: a rewritten-on-every-toggle JSON file loses everything to a crash
mid-write, and ratings, tags, notes and "when did I last use this" are all
things a flat file grows badly.

### Where the data directory is

| Platform | Path |
|---|---|
| Linux, BSD | `$XDG_DATA_HOME/<tool>`, else `~/.local/share/<tool>` |
| macOS | `~/Library/Application Support/<tool>` |
| Windows | `%LOCALAPPDATA%\<tool>` |

Local rather than Roaming on Windows, deliberately: a roaming profile
copies files wholesale at logon and logoff, and a SQLite database caught
mid-write by that copy is a known way to corrupt one. Both can be
overridden with `--favorites`.

### What is worth knowing about the settings cache

Both tools' settings handling had, independently, the same three traps.
They are now fixed in one place.

**A TOML boolean is not a channel.** `isinstance(True, int)` is true and
`0 <= True <= 15` is true, so `channel = true` came back as `True`, passed
every range check, and then `0xC0 | True` is `0xC1` -- MIDI channel 2. A
wrong channel is not an error anywhere: the instrument simply plays
nothing, or something else does. The same trap applies to `device_id`,
where the wrong value is device 1.

**A quote in a port name corrupts the file.** ALSA client names are
whatever the device reports. Writing one straight between quotes produces
something that is not TOML, and the writer refuses to overwrite a file it
cannot parse -- which means the cache never heals: every later run reads
nothing and writes nothing until somebody deletes it by hand. Everything
is escaped, including control characters.

**Only `OSError` is swallowed.** A read-only directory or a full disk, where
forgetting a preference beats refusing to run. Anything else is a bug and
should be heard -- one tool's first attempt caught everything and so never
noticed it was raising `NameError` on every call and writing nothing.

### How a launch finds the unit

This is the `--scan` policy, and every browser implements it the same way.

**The normal path is one Identity Request, to the remembered port.** Not
just an optimisation. A sweep sends an Identity Request to *every*
bidirectional port on the machine, which on a studio box with thirty of
them takes seconds, prints thirty lines, and pings every piece of hardware
on the chain once per launch -- and once the answer is known there is
nothing left to learn by asking again.

**Use the remembered port, sweep when there is none, sweep on request.**
`--scan` is that request.

**A remembered port that does not answer is not a licence to sweep.** The
guess is gone, but sweeping anyway would make a launch silently take the
slow path for a reason the user did not ask about, and would then quietly
overwrite the file it was told to trust. Naming `--scan` says what happened
and what to do about it. It is the wrong answer to "the unit moved to
another port", which is what USB re-enumeration causes: ALSA renumbers
clients out from under a saved name.

**When it does fall back, it says so.** A silent fallback is
indistinguishable, from the terminal, from the fast path having worked --
which is how a slow launch quietly becomes the normal one.

`vinsynlib.midi.open_remembered_or_swept` is this policy, written and
tested once. It was a paragraph in rxved, a docstring in x5ded saying it
had been ported from rxved, and nothing at all in the other seven.

---

## 5. Checks

Each project runs the same conformance test against its own front ends:

```python
from vinsynlib import conformance


def test_the_family_contract():
    problems = (
        conformance.check_flags(build_parser(), required={"port", "demo"})
        + conformance.check_bindings(X5dedApp, channel=True)
        + conformance.check_legend(KEY_HINTS)
    )
    assert not problems, "\n".join(problems)
```

It reports sentences rather than asserting, because
`--midi-channel is not a name this family uses; use --device-channel` is
worth more than `False`.

Two more checks exist because of bugs that actually happened:

**A test must not write `config.toml` into the checkout.** The path is
relative on purpose, and being gitignored is exactly what makes this worth
checking rather than remembering. One was found beside the source, dated
during a test run.

**A project must not import another project in the family.** `emorphed`
had a function importing `nano.config` -- `nanosyned`'s package, which of
course is not installed beside it. It worked in the project it was copied
from and raised `ImportError` the moment `--config` was used.

---

## 6. Not settled here

* **`--json`.** No tool has it. It is the obvious next uniformity and the
  one thing missing that a script cannot do without.
* **The `catalog.py` layer.** Six copies at 55-100% identical. The copies
  differ in what a key is made of -- `bank_id:kind:number` in `kwsed`,
  `bank_id:program_change` elsewhere -- so unifying it means deciding what
  a catalog entry *is*, which is a larger piece of work than a naming
  exercise.
* **The bank table.** Every tool has one and no two agree on shape,
  because the instruments do not agree. `kwsed` has banks of performances
  and patches, `s3ked` has memory and volumes on a disc, `eosed` has RAM
  banks and a flash card. Left alone deliberately.