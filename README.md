<!--
SPDX-License-Identifier: GPL-2.0-or-later
SPDX-FileCopyrightText: Copyright (C) 2026  vinsynLib contributors
-->

# vinsynlib

The shared base of a family of terminal instrument browsers.

Nine sibling programs browse nine instruments over MIDI from a terminal:
[emorphed](https://github.com/lentferj/emorphed) (E-mu Morpheus),
[ensqsqed](https://github.com/lentferj/ensqsqed) (Ensoniq SQ-R Plus),
[eosed](https://github.com/lentferj/eosed) (E-mu E4XT),
[kwsed](https://github.com/lentferj/kwsed) (Korg Wavestation SR),
[nanosyned](https://github.com/lentferj/nanosyned) (Alesis NanoSynth),
[p2ked](https://github.com/lentferj/p2ked) (E-mu Proteus 2000),
[rxved](https://github.com/lentferj/rxved) (Roland XV-2020),
[s3ked](https://github.com/lentferj/s3ked) (Akai S1000/S3000) and
[x5ded](https://github.com/lentferj/x5ded) (Korg X5D/X5DR).

They grew separately, which is the right way to learn what an instrument
does and the wrong way to arrive at nine copies of the same code. This
library is where the parts that are *not* the manufacturer's live, so that
a change to one of them happens once instead of nine times.

---

## What is in here, and what is not

**In here:** how a preference is remembered, where a favourite lives, what
an error says, which key means what, how a port list is printed, how a
legend wraps.

**In each project:** the wire format, the bank table, the meaning of a
byte, the LCD glyphs.

The line is *ours* versus *the manufacturer's*. A MIDI port name is
whatever ALSA reports, so the port listing is shared; which SysEx byte
selects which bank is that instrument's business and stays put.

```
vinsynlib/
  config.py        the settings cache: port, channel, device ID
  favorites.py     the favourites database: SQLite, slots, ratings, tags
  keys.py          the keymap and the legend
  cli.py           the command line every tool builds the same way
  spec.py          that command line, as data: flags, commands, exit codes
  terms.py         the vocabulary: our words, and each tool's two
  midi.py          port listing, the shared error taxonomy, clean exit
  conformance.py   the checks a project runs against itself
  devchecks.py     checks that catch cross-project mistakes
  ui/hints.py      the legend widget
```

## Installing it, and who depends on it

This is a library, not a program, and it is **not on PyPI yet**. The ten tools
in the family depend on it, so it has to be a sibling checkout of whichever
one you are building:

```
git-repos/
  vinsynlib/     <- this one
  x5ded/         <- and the ten tools beside it
  emorphed/  ensqsqed/  eosed/  kwsed/  ...
```

```sh
cd ../x5ded                     # or any sibling
git clone https://github.com/lentferj/vinsynlib.git ../vinsynlib
python3 -m venv .venv
.venv/bin/pip install --no-deps -e ../vinsynlib   # --no-deps: its deps are theirs
.venv/bin/pip install -e .
```

Each of the ten writes those steps out in its own README, because a reader
starts from the tool and rarely from here. With `uv`, `uv sync` takes the path
from `[tool.uv.sources]` in that project's `pyproject.toml`, so the checkout
only has to exist and neither `pip` line is needed.

Publishing this to PyPI would replace all of it with an ordinary dependency
line. Until then, the sibling checkout *is* the install.

## Why it exists

Nine projects each grew a `config.py` (about 190 lines, 90-97% identical),
a `favorites.py` (about 620 lines, 85-100% identical), a `KeyHints` widget
and a `wrap_blocks` helper. Measured across the family: **8,101 lines of
cloned code, roughly 6,300 of them duplicates that need not exist.**

Three of those copies had already drifted into bugs worth naming:

* `emorphed`'s `LICENSE` file opened with the words "nanosyned — Terminal
  browser for the Alesis NanoSynth".
* `emorphed`'s `mypy` and `deptry` configuration still named the `nano`
  module, and one function imported `nano.config` -- `nanosyned`'s package,
  which is not installed beside it. That function worked in the project it
  was copied from and raised `ImportError` the moment `--config` was used.
* `eosed` wrote port names into `config.toml` without escaping them, so a
  port name containing a quote produced a file that is not TOML -- and its
  settings writer refuses to overwrite a file it cannot parse, so the
  cache never healed until somebody deleted it by hand.

None of these were visible in review. They were visible the moment there
was a second copy to compare against, which is what this library is.

## Using it

```python
from vinsynlib.config import Settings

settings = Settings("x5ded")
channel = settings.load_channel()  # 0-15, or None; a TOML bool is None
settings.save_port("Midi Out: X5D")
```

```python
from vinsynlib.favorites import Favorites

with Favorites(app_name="x5ded") as favourites:
    favourites.add("A", 7, name="Warm Pad", rating=4, tags="pad")
    favourites.toggle("A", 7)  # clears the flag, keeps the rating
```

```python
from vinsynlib import cli

parser = cli.make_parser("x5cli", "Browse a Korg X5D's sounds.")
cli.add_common_arguments(parser, port=True, scan=True, channel=True)
```

## Development

```console
$ uv venv && uv pip install -e ".[ui,midi]" && uv pip install \
      pytest pytest-cov mypy ruff vulture deptry detect-secrets pip-audit
$ make check
```

`make check` runs the whole gate in order and stops at the first failure:
ruff, mypy in strict mode, the test suite with coverage, then vulture,
deptry and pip-audit.

> **Legal:** [DISCLAIMER.md](DISCLAIMER.md) · [LICENSE](LICENSE)

## Where the rules are written down

**[docs/UX-SPEC.md](docs/UX-SPEC.md)** is the contract: terminology, the
command line, the keys, the paths, the exit codes, and the reasoning behind
the parts that are not obvious. It is the document to read before changing
anything here, and the document to argue with.

Three things in it are worth repeating, because they are the parts a new
contributor is most likely to get backwards:

**The instrument's word is the instrument's.** Each tool declares the word
for a stored sound and for the area it lives in, once, and uses it
consistently within itself. A Yamaha says PATCH; an E-mu says PRESET. The
unit's word wins, because a tool that renames it has to translate, and a
mistranslation is the difference between finding a sound and not.

**Our words are the same everywhere.** *favourite*, *search*, *scan*,
*dump*, *port*: no tool invents a synonym for a concept the family owns.

**`config.toml` is disposable; `favorites.db` is the user's own work.** The
first lives in the working directory and is safe to delete. The second
lives in the platform data directory, is keyed on the slot rather than the
name, and is the one file here worth backing up.