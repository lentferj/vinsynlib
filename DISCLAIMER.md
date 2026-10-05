# Disclaimer

**vinsynlib is provided "as is", without warranty of any kind, express or
implied, and with no liability to the author for any loss, damage or
other harm arising from its use.**

You assume all risk. The authors accept no liability for lost data,
damaged hardware, corrupted media, or any other harm arising from your use
of this software, whether direct or consequential, whether in contract,
tort or otherwise.

## What this software is

This is a library of ordinary code: it reads and writes a settings file,
keeps a small SQLite database, lists MIDI ports, formats a table and draws
a line of text. It is not clever and it does not know anything about your
instrument.

## What it is not

It is not affiliated with, endorsed by, or connected to E-mu Systems,
Ensoniq, Korg, Alesis, Roland, Yamaha or any other manufacturer. The
instrument names and model designations used in this repository and in the
projects that use it are the trademarks of their respective owners, and
are used here only to identify which instrument a program is written for.

No manufacturer documentation is redistributed here. Everything in this
repository was written from manuals, from observing hardware, and from
protocol behaviour that the author measured. Where an external project is
consulted for facts, it is credited in the file that used it.

## About writing to hardware

**The programs that use this library can write to real instruments.**
Sending a System Exclusive message to some of these instruments overwrites
what is in them, and on some models there is no undo.

If you use any of these programs:

* **Back up the instrument's contents before writing to it.** A SysEx
  dump of the factory banks is the backup, and it is worth taking before
  you start rather than after something goes wrong.
* **Do not write to an instrument you cannot replace**, however confident
  you are about the dump format.
* **Do not write to an instrument you have not tested on a spare, a
  sacrificial unit, or a device you are willing to lose.**
* **Understand that the destructive operations in these programs are
  deliberately awkward** -- an explicit arm, a typed confirmation, or both
  -- and that the awkwardness is the safety mechanism. Anything that makes
  them easier to reach makes them more dangerous.

The library itself writes nothing to hardware. It is the projects that use
it, and their responsibility alone, and the same terms apply to them.

## About your data

`config.toml` in your working directory is disposable: it records which
MIDI port answered last, and deleting it costs you one re-entry of a
setting.

`favorites.db` is not. It is your work -- your ratings, your tags, your
notes -- and it is the only file these programs produce that cannot be
reconstructed from the instrument. It lives in your platform's application
data directory, outside any project checkout, precisely so that a
`git clean` cannot take it. **Back it up.**

No data leaves your machine. There is no network access anywhere in this
library: it does not read or write anything over a network, and it has no
telemetry, no update check and no phone-home of any kind.

## No warranty

The authors make no warranty that this software will:

* work without error, or with any particular result;
* be compatible with any instrument, firmware version, or MIDI interface;
* not damage, erase, or corrupt anything;
* remain available, supported, or free of defects.

The software is licensed under the GNU General Public License version 2 or
later. That licence disclaims warranty and limits liability in the same
terms, and those terms apply in full. See [LICENSE](LICENSE).