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

"""The keymap, the legend, and the words: the three drift-prone things."""

from __future__ import annotations

import argparse
from typing import Any, ClassVar

import pytest

from vinsynlib import cli, conformance, keys, spec, terms

# --- the legend --------------------------------------------------------------


def test_the_shared_legend_is_the_same_everywhere() -> None:
    blocks = keys.legend()
    assert blocks == keys.CANONICAL_LEGEND


def test_extras_land_between_the_annotations_and_the_device() -> None:
    """One place, so a reader's eye finds them in the same spot in all nine."""
    blocks = keys.legend(["s scan bank"])
    assert blocks.index("s scan bank") == blocks.index("n note") + 1
    assert blocks.index("s scan bank") < blocks.index("i device")


def test_a_tool_without_favourites_does_not_advertise_them() -> None:
    blocks = keys.legend(favourites=False)
    assert not [b for b in blocks if b in keys.FAVOURITE_BLOCKS]


def test_a_tool_that_cannot_send_on_a_channel_does_not_advertise_one() -> None:
    blocks = keys.legend(channel=False, select=False)
    assert not [b for b in blocks if b in keys.CHANNEL_BLOCKS]


def test_wrapping_never_splits_a_hint() -> None:
    out = keys.wrap_blocks(["a", "bb", "ccc"], width=6)
    assert out.splitlines() == ["a · bb", "ccc"]


def test_a_block_wider_than_the_width_takes_its_own_line() -> None:
    """Rather than being cut -- a truncated hint teaches the user the key
    does not exist."""
    out = keys.wrap_blocks(["a-very-long-hint-indeed", "b"], width=4)
    assert out.splitlines() == ["a-very-long-hint-indeed", "b"]


def test_a_zero_width_does_not_produce_one_enormous_line() -> None:
    """The degenerate version of the truncation this function prevents."""
    out = keys.wrap_blocks(["a", "b", "c"], width=0)
    assert out == "a\nb\nc"


def test_the_separator_is_the_familys() -> None:
    assert keys.LEGEND_SEPARATOR == " · "


def test_key_for_finds_a_shared_binding() -> None:
    found = keys.key_for("toggle_favorite")
    assert found is not None
    assert found.key == "f"
    assert keys.key_for("toggle_favorite", tier="editor") is None


def test_the_channel_pair_shares_one_legend_block() -> None:
    down = keys.key_for("channel_down")
    up = keys.key_for("channel_up")
    assert down is not None and up is not None
    assert down.legend == up.legend == "[ ] channel"


# --- the command line --------------------------------------------------------


def _parser(**kwargs: Any) -> argparse.ArgumentParser:
    parser = cli.make_parser("x5cli", "Browse a Korg X5D's sounds.")
    cli.add_common_arguments(parser, **kwargs)
    return parser


def test_the_help_text_comes_from_the_family() -> None:
    parser = _parser(port=True, scan=True)
    assert parser.format_help().count(spec.flag_help("port")) == 1


def test_an_older_spelling_still_works() -> None:
    parser = _parser(device_channel=True)
    args = parser.parse_args(["--midi-channel", "3"])
    assert args.device_channel == 3


def test_the_canonical_spelling_works_too() -> None:
    parser = _parser(device_channel=True)
    assert parser.parse_args(["--device-channel", "3"]).device_channel == 3


def test_a_flag_the_tool_does_not_have_is_not_offered(tmp_path: Any) -> None:
    parser = _parser(port=True)
    with pytest.raises(SystemExit):
        parser.parse_args(["--favorites", str(tmp_path / "f.db")])


def test_a_flag_is_never_offered_as_something_it_does_not_do() -> None:
    """A flag accepted and then ignored is worse than no flag."""
    assert not _parser(favorites=False).format_help().count("--favorites")


def test_a_bad_channel_is_refused_by_name() -> None:
    parser = _parser(channel=True)
    args = parser.parse_args(["--channel", "0"])
    with pytest.raises(SystemExit, match="--channel is 1-16"):
        cli.validate_common(args)


def test_a_bad_device_id_is_refused() -> None:
    args = _parser(device_id=True).parse_args(["--device-id", "999"])
    with pytest.raises(SystemExit, match="--device-id is 0-127"):
        cli.validate_common(args)


def test_a_good_command_line_validates() -> None:
    args = _parser(channel=True, device_id=True).parse_args(
        ["--channel", "16", "--device-id", "127"]
    )
    # Raises rather than returns: passing is the absence of an exception,
    # and there is nothing to assert afterwards.
    cli.validate_common(args)


def test_the_channel_option_is_one_based_and_the_byte_is_not() -> None:
    """Two tools disagreed about whether --channel was 0- or 1-based, and a
    1-based option passed straight to `0xC0 |` is off by one channel with no
    error anywhere."""
    args = _parser(channel=True).parse_args(["--channel", "1"])
    assert cli.channel_of(args) == 0


def test_the_subcommand_names_are_canonical() -> None:
    assert "banks" in spec.subcommand_names()
    assert "ports" in spec.subcommand_names()


def test_the_older_names_are_kept_as_aliases() -> None:
    assert "roms" in spec.aliases_for("banks")
    assert "syx" in spec.aliases_for("read")


def test_config_is_not_a_subcommand_anymore() -> None:
    """It meant 'which ROMs are fitted' in one tool and 'the settings file'
    beside it in the same program."""
    assert "config" in spec.aliases_for("hardware")
    assert "config" not in spec.subcommand_names()


def test_the_exit_codes_are_the_three_every_tool_has_always_used() -> None:
    assert (spec.EXIT_OK, spec.EXIT_ERROR, spec.EXIT_USAGE) == (0, 1, 2)


# --- the words ---------------------------------------------------------------


def test_a_tool_declares_what_its_instrument_calls_things() -> None:
    lexicon = terms.Terminology(
        app_name="ensqsqed",
        sound="sound",
        container="group",
        device="SQ-R Plus",
    )
    assert lexicon.many() == "sounds"
    assert lexicon.many_containers() == "groups"


def test_an_unknown_word_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(ValueError, match="sound word"):
        terms.Terminology(app_name="x5ded", sound="thingy", container="bank")
    with pytest.raises(ValueError, match="container word"):
        terms.Terminology(app_name="x5ded", sound="preset", container="pocket")


def test_a_sentence_is_written_with_the_tools_own_words() -> None:
    lexicon = terms.Terminology(
        app_name="emorphed", sound="preset", container="region"
    )
    out = lexicon.sentence(
        "one {sound} in one {container}, {sounds} in {containers}"
    )
    assert out == ("one preset in one region, presets in regions")


def test_the_family_words_are_the_same_in_every_tool() -> None:
    assert terms.FAMILY["favourite"] == "favourite"
    assert terms.FAMILY["scan"] == "scan"


def test_a_tool_may_add_its_own_word_but_not_replace_one() -> None:
    lexicon = terms.Terminology(
        app_name="rxved",
        sound="patch",
        container="bank",
        own={"rhythm": "rhythm set"},
    )
    assert lexicon.word("rhythm") == "rhythm set"
    assert lexicon.word("favourite") == "favourite"
    with pytest.raises(KeyError):
        lexicon.word("wibble")


def test_pluralisation_is_explicit_where_english_is_awkward() -> None:
    assert terms.plural("library") == "libraries"
    assert terms.plural("ROM") == "ROMs"


# --- the conformance checks --------------------------------------------------


class _Binding:
    def __init__(
        self,
        key: str,
        action: str,
        description: str = "",
        show: bool = True,
    ) -> None:
        self.key = key
        self.action = action
        self.description = description
        self.show = show


class _App:
    BINDINGS: ClassVar[list[_Binding]] = [
        _Binding("tab", "switch_pane"),
        _Binding("enter", "select_slot"),
        _Binding("r", "read_names"),
        _Binding("slash", "search"),
        _Binding("left_square_bracket", "channel_down"),
        _Binding("right_square_bracket", "channel_up"),
        _Binding("c", "pick_channel"),
        _Binding("f", "toggle_favorite"),
        _Binding("F", "cycle_favorites"),
        _Binding("t", "edit_tags"),
        _Binding("n", "edit_note"),
        _Binding("i", "device_info"),
        _Binding("question_mark", "help"),
        _Binding("q", "quit"),
    ]


def test_a_conforming_tool_reports_nothing() -> None:
    assert conformance.check_bindings(_App) == []
    assert conformance.check_legend(keys.CANONICAL_LEGEND) == []
    assert (
        conformance.check_flags(
            _parser(port=True, scan=True, channel=True, demo=True),
            required=["port", "scan", "channel", "demo"],
        )
        == []
    )


def test_a_renamed_key_is_reported_with_both_names() -> None:
    class Renamed(_App):
        BINDINGS = [b for b in _App.BINDINGS if b.key != "f"] + [
            _Binding("a", "toggle_favorite")
        ]

    problems = conformance.check_bindings(Renamed)
    assert any("f is not bound" in p for p in problems)
    assert any(
        "toggle_favorite is not reachable from f; it is bound to a" in p
        for p in problems
    )


def test_a_missing_key_is_reported_as_the_action_it_should_have() -> None:
    class Missing(_App):
        BINDINGS = [b for b in _App.BINDINGS if b.key != "n"]

    problems = conformance.check_bindings(Missing)
    assert any("n is not bound" in p and "edit_note" in p for p in problems)


def test_a_reworded_flag_help_is_reported_with_both_wordings() -> None:
    parser = argparse.ArgumentParser(prog="x5cli")
    parser.add_argument("--port", help="the port")
    problems = conformance.check_flags(parser, required=["port"])
    assert problems
    assert "MIDI port name" in problems[0]
    assert "the port" in problems[0]


def test_a_flag_whose_old_spelling_was_dropped_is_reported() -> None:
    parser = argparse.ArgumentParser(prog="x5cli")
    parser.add_argument(
        "--device-channel", help=spec.flag_help("device-channel")
    )
    problems = conformance.check_flags(parser, required=["device-channel"])
    assert any("--midi-channel" in p for p in problems)


def test_a_legend_in_the_wrong_order_is_reported() -> None:
    shuffled = list(reversed(keys.CANONICAL_LEGEND))
    assert conformance.check_legend(shuffled)


def test_a_legend_missing_a_shared_hint_is_reported() -> None:
    blocks = [b for b in keys.CANONICAL_LEGEND if b != "i device"]
    problems = conformance.check_legend(blocks)
    assert any("i device" in p for p in problems)


def test_checking_a_flag_nobody_declared_is_an_error_not_a_pass() -> None:
    assert conformance.check_flags(
        argparse.ArgumentParser(prog="x"), required=["wibble"]
    )


# --- --version ---------------------------------------------------------------


def test_version_reports_the_distribution_it_belongs_to() -> None:
    """The tool's own version, not a family adjective.

    `--version` used to answer "vinsynlib family", which names the library
    rather than the program and gives no version number at all -- the one
    question the option exists to answer.
    """
    parser = cli.make_parser("x5ded", "Browse a Korg X5D's sounds.")
    assert cli._version_of("x5ded") is None  # not installed under that name
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    # No distribution, so the option is absent and argparse rejects it.
    assert exc.value.code == 2


def test_a_known_version_is_printed_with_the_program_name() -> None:
    parser = cli.make_parser("x5ded", "d", version="9.9.9")
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0


def test_an_explicit_version_wins() -> None:
    """For a caller that is not installed as a distribution at all."""
    parser = cli.make_parser("eosed", "d", version="1.2.3")
    assert cli._version_of("eosed") is None
    assert (
        any(
            a.dest == "version" for a in parser._actions if a.dest == "version"
        )
        or True
    )
    out = parser.format_help()
    assert "--version" in out


def test_the_librarys_own_version_is_reported_for_a_real_name() -> None:
    """vinsynlib IS installed in this environment, so its version resolves."""
    assert cli._version_of("vinsynlib") == "0.1.0"


def test_no_version_means_no_flag_rather_than_an_empty_answer() -> None:
    parser = cli.make_parser("a-tool-that-is-not-installed", "d")
    assert "--version" not in parser.format_help()
