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

"""One word for each thing, and one place where that word is written down.

Nine sibling programs grew nine vocabularies for the same ideas. The same
program is a *preset* in one, a *sound* in another and a *program* in a
third; the thing it lives in is a *region*, a *group* or a *bank*. Each of
those is correct -- Ensoniq really did call it a patch, and a Yamaha
really does print VOICE on its display -- and the inconsistency is the
problem: a user who learns one of these tools has to learn that the next
one's word means the same thing.

So the rule is two-tier, and this module is the whole of it.

**Our words are the same everywhere.** The words in :data:`FAMILY` name
things that belong to us rather than to the manufacturer: a favourite, a
search, a scan, a dump, a port. No tool may invent a synonym for these. If
a tool needs a fifth one, that is a change here, made once.

**The instrument's word is the instrument's.** The word for one stored
sound and for the area it lives in are declared once per tool, in a
:class:`Terminology`, and used consistently *within* that tool -- in the
CLI help, in the legend, in the pane headings, in the README. A tool that
calls a slot a "slot" in its list view and a "program" on the wire has two
words for one thing; the wire's word stays in the code that builds the
wire message, and the tool's word is used for everything the user reads.

Why not force one word on all nine: the unit prints its own word on its own
display, and a tool that renames it is a tool that has to translate. The
manufacturer's name is data, and it wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ALLOWED_CONTAINER_WORDS",
    "ALLOWED_SOUND_WORDS",
    "FAMILY",
    "REGISTRY",
    "Terminology",
    "for_app",
    "plural",
    "register",
]


#: The words every tool uses, whatever it is browsing. These name *our*
#: concepts. Nothing here may be renamed in one project and not another.
FAMILY: dict[str, str] = {
    "favourite": "favourite",
    "favourites": "favourites",
    "rating": "rating",
    "tags": "tags",
    "note": "note",
    "search": "search",
    "read names": "read names",
    "select": "select",
    "status": "status",
    "ports": "ports",
    "dump": "dump",
    "scan": "scan",
    "device": "device",
    "help": "help",
    "quit": "quit",
    "settings cache": "settings cache",
    "favourites database": "favourites database",
}

#: Words a tool may use for its own hardware's concepts, with the sense
#: each must mean if it uses one. A conformance check reads this table: a
#: tool that says "voice" where the family means "program change" has a bug.
ALLOWED_SOUND_WORDS: frozenset[str] = frozenset(
    {
        "preset",
        "program",
        "patch",
        "sound",
        "voice",
        "performance",
        "sound slot",
    }
)

ALLOWED_CONTAINER_WORDS: frozenset[str] = frozenset(
    # "memory" is the Akai samplers' own word -- an S1000 or S3000 has memory
    # rather than banks, and the panel, the manual and the STAT reply all say
    # so. It was missing here while being assigned to `s3ked` in
    # docs/UX-SPEC.md section 1, which is how the spec and the code it is
    # checked against came to disagree: the table could not be satisfied by
    # the tool the table named.
    {"bank", "group", "region", "ROM", "card", "library", "memory"}
)

_IRREGULAR: dict[str, str] = {
    "ROM": "ROMs",
    "library": "libraries",
    "entry": "entries",
}


def plural(word: str) -> str:
    """The plural of a vocabulary word.

    Small and explicit on purpose. Anything clever here would be wrong
    about exactly the words it had not been shown, and the whole point is
    that the word is written down rather than computed.
    """
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return f"{word}es"
    return f"{word}s"


@dataclass(frozen=True)
class Terminology:
    """One tool's vocabulary.

    ``sound`` and ``container`` are the two words a tool must supply,
    because they are the two the manufacturer owns. Everything else is
    fixed by the family and needs no declaration.
    """

    app_name: str
    #: What the instrument calls one stored sound: "preset", "program",
    #: "patch", "sound", "voice", "performance".
    sound: str
    #: What the instrument calls the area sounds live in: "bank",
    #: "group", "region", "ROM".
    container: str
    #: What the instrument is called in prose, e.g. "the SQ-R Plus".
    device: str = ""
    #: Extra words this tool legitimately uses, for its own hardware's
    #: concepts that the family has no opinion about.
    own: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sound not in ALLOWED_SOUND_WORDS:
            raise ValueError(
                f"{self.app_name}: {self.sound!r} is not a sound word the "
                f"family knows; have "
                f"{', '.join(sorted(ALLOWED_SOUND_WORDS))}"
            )
        if self.container not in ALLOWED_CONTAINER_WORDS:
            raise ValueError(
                f"{self.app_name}: {self.container!r} is not a container word "
                f"the family knows; have "
                f"{', '.join(sorted(ALLOWED_CONTAINER_WORDS))}"
            )

    def one(self) -> str:
        """The singular: "a program"."""
        return self.sound

    def many(self) -> str:
        """The plural: "640 programs"."""
        return plural(self.sound)

    def one_container(self) -> str:
        """The singular: "Bank A"."""
        return self.container

    def many_containers(self) -> str:
        """The plural: "all banks"."""
        return plural(self.container)

    def word(self, concept: str) -> str:
        """The word for one of *our* concepts, or one of this tool's own."""
        if concept in self.own:
            return self.own[concept]
        if concept in FAMILY:
            return FAMILY[concept]
        if concept == "sound":
            return self.sound
        if concept == "container":
            return self.container
        raise KeyError(f"no word for {concept!r} in {self.app_name}")

    def sentence(self, template: str) -> str:
        """Fill ``{sound}``/``{sounds}``/``{container}``/``{containers}``.

        One way to write a sentence that needs the tool's own words, so
        that a string built for help text cannot accidentally hard-code the
        wrong one.
        """
        return template.format(
            sound=self.one(),
            sounds=self.many(),
            container=self.one_container(),
            containers=self.many_containers(),
            device=self.device or self.app_name,
        )


#: The vocabulary each tool declared on its ``unify`` branch. Kept here so
#: that the family can be read at a glance, and so that a new tool has
#: something to copy rather than to invent.
REGISTRY: dict[str, Terminology] = {}


def for_app(app_name: str) -> Terminology:
    """The declared vocabulary of one tool, by name.

    Raises :class:`KeyError` rather than inventing one: a tool that has not
    said what its instrument calls things has not finished being part of
    this family, and a default would let it drift without anyone noticing.
    """
    try:
        return REGISTRY[app_name]
    except KeyError:
        raise KeyError(
            f"{app_name} has not declared a Terminology; add it to "
            f"vinsynlib.terms.REGISTRY"
        ) from None


def register(terms: Terminology) -> None:
    """Record one tool's vocabulary in :data:`REGISTRY`."""
    REGISTRY[terms.app_name] = terms
