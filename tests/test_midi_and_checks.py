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

"""Port listing, the shared error taxonomy, and the cross-project checks."""

from __future__ import annotations

from typing import Any

import pytest

from vinsynlib import devchecks, midi

PORTS = (["X5", "Alesis nano"], ["X5", "Korg S3K"])


def test_a_port_that_is_only_an_output_is_not_a_candidate() -> None:
    """A synthesizer that can be asked a question has both. Anything else
    cannot answer, so probing it costs a timeout for nothing."""
    assert midi.bidirectional_ports(PORTS) == ["X5"]


def test_a_name_hint_only_orders_the_search() -> None:
    assert midi.likely_ports(("x5", "korg"), PORTS) == ["X5", "Korg S3K"]


def test_the_hint_is_case_insensitive_and_may_match_the_middle() -> None:
    assert midi.likely_ports(("S3K",), PORTS) == ["Korg S3K"]
    assert midi.likely_ports(("s3k",), PORTS) == ["Korg S3K"]


def test_no_hint_means_no_guesses() -> None:
    assert midi.likely_ports((), PORTS) == []


def test_the_listing_marks_what_can_answer_and_what_looks_right() -> None:
    out = midi.render_ports(
        *PORTS, likely=["Korg S3K"], likely_label="name mentions Korg"
    )
    assert "inputs:" in out
    assert "  X5   [bidirectional]" in out
    assert "  Alesis nano" in out
    assert "  Korg S3K   [name mentions Korg]" in out


def test_the_listing_says_so_when_there_is_nothing() -> None:
    out = midi.render_ports([], [])
    assert "  (none)" in out


def test_the_listing_makes_no_judgement_it_cannot() -> None:
    """No hint, no mark: a tool without one passes none."""
    out = midi.render_ports(*PORTS)
    assert "name mentions" not in out


def test_the_note_is_optional() -> None:
    assert "A name hint" not in midi.render_ports(*PORTS)
    assert "A name hint" in midi.render_ports(
        *PORTS, note="A name hint is a hint."
    )


def test_fail_uses_the_familys_error_format() -> None:
    with pytest.raises(SystemExit) as exc:
        midi.fail("no unit answered")
    assert str(exc.value) == "error: no unit answered"


def test_the_error_taxonomy_distinguishes_silence_from_a_refusal() -> None:
    """A refusal is information; a timeout only says nothing arrived."""
    assert issubclass(midi.DeviceNotFound, midi.DeviceError)
    assert issubclass(midi.DeviceRefused, midi.DeviceError)
    assert not issubclass(midi.DeviceRefused, midi.DeviceNotFound)
    assert issubclass(midi.DeviceError, RuntimeError)


def test_installing_a_handler_off_the_main_thread_does_not_raise() -> None:
    """A Textual worker is not the main thread, and signal.signal refuses."""
    import threading

    errors: list[BaseException] = []

    def work() -> None:
        try:
            midi.install_clean_exit()
        except BaseException as exc:  # pragma: no cover - must not happen
            errors.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert errors == []


# --- the checks a project runs against itself --------------------------------


def test_a_config_save_with_no_path_is_reported(tmp_path: Any) -> None:
    test = tmp_path / "tests"
    test.mkdir()
    (test / "test_x.py").write_text(
        "import config\n"
        "def test_it():\n"
        "    config.save_channel(3)\n"
        "    config.save_port('x', '/tmp/c.toml')\n",
        encoding="utf-8",
    )
    offenders = devchecks.config_saves_without_path(str(test))
    assert len(offenders) == 1
    assert "save_channel" in offenders[0]


def test_a_sibling_projects_package_is_reported(tmp_path: Any) -> None:
    """emorphed had a function importing `nano.config` -- nanosyned's
    package, which is not installed beside it."""
    source = tmp_path / "app.py"
    source.write_text(
        "from nano import config\n"
        "import emu.messages\n"
        "from textual.app import App\n"
        "import vinsynlib.config\n"
        "from . import sibling\n",
        encoding="utf-8",
    )
    found = devchecks.foreign_imports(str(source), own=["emorphed", "emu"])
    assert found == ["app.py:1 nano"]


def test_standard_library_and_own_packages_are_not_foreign(
    tmp_path: Any,
) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        "import os\nimport ast\nimport x5.banks\nfrom . import app\n",
        encoding="utf-8",
    )
    assert devchecks.foreign_imports(str(source), own=["x5ded", "x5"]) == []


def test_several_files_can_be_checked_at_once(tmp_path: Any) -> None:
    (tmp_path / "a.py").write_text("import nano.config\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import sq.config\n", encoding="utf-8")
    found = devchecks.check_foreign_imports(
        [str(tmp_path / "a.py"), str(tmp_path / "b.py")],
        own=["emorphed", "emu"],
    )
    assert len(found) == 2


# --- the --scan policy -------------------------------------------------------


class FakeDevice:
    def __init__(self, port: str) -> None:
        self.port = port


def test_the_remembered_port_is_tried_first_and_nothing_else() -> None:
    """One Identity Request, not one per port on the machine."""
    probes: list[tuple[str, str]] = []
    sweeps: list[str] = []

    def probe(send: str, recv: str) -> FakeDevice:
        probes.append((send, recv))
        return FakeDevice(send)

    def sweep(on_try: Any = None) -> FakeDevice:
        sweeps.append("swept")
        return FakeDevice("found")

    device = midi.open_remembered_or_swept(
        probe=probe,
        sweep=sweep,
        remembered=("Midi Out: XV", "Midi In: XV"),
    )

    assert device.port == "Midi Out: XV"
    assert probes == [("Midi Out: XV", "Midi In: XV")]
    assert sweeps == []


def test_scan_asks_for_the_sweep_even_with_a_remembered_port() -> None:
    """This is what the flag is for: the unit moved, USB renumbered the
    client, and the saved name no longer answers."""
    probes: list[tuple[str, str]] = []
    sweeps: list[str] = []

    def probe(send: str, recv: str) -> FakeDevice:
        probes.append((send, recv))
        return FakeDevice(send)

    def sweep(on_try: Any = None) -> FakeDevice:
        sweeps.append("swept")
        return FakeDevice("found")

    device = midi.open_remembered_or_swept(
        probe=probe,
        sweep=sweep,
        remembered=("stale", "stale"),
        scan=True,
    )

    assert device.port == "found"
    assert probes == []
    assert sweeps == ["swept"]


def test_nothing_remembered_means_a_sweep() -> None:
    sweeps: list[str] = []

    def probe(send: str, recv: str) -> FakeDevice:
        raise AssertionError("nothing was remembered; do not probe a name")

    def sweep(on_try: Any = None) -> FakeDevice:
        sweeps.append("swept")
        return FakeDevice("found")

    device = midi.open_remembered_or_swept(probe=probe, sweep=sweep)
    assert device.port == "found"
    assert sweeps == ["swept"]


def test_a_remembered_port_that_does_not_answer_falls_back_to_a_sweep() -> (
    None
):
    def probe(send: str, recv: str) -> FakeDevice:
        raise midi.DeviceError("nothing came back")

    def sweep(on_try: Any = None) -> FakeDevice:
        return FakeDevice("found")

    device = midi.open_remembered_or_swept(
        probe=probe, sweep=sweep, remembered=("gone", "gone")
    )
    assert device.port == "found"


def test_the_fallback_says_so_rather_than_pretending_to_be_fast() -> None:
    """A silent sweep here would look exactly like the fast path having
    worked, which is how a slow launch becomes the normal one."""

    def probe(send: str, recv: str) -> FakeDevice:
        raise midi.DeviceError("nothing came back")

    def sweep(on_try: Any = None) -> FakeDevice:
        return FakeDevice("found")

    said: list[str] = []

    midi.open_remembered_or_swept(
        probe=probe,
        sweep=sweep,
        remembered=("gone", "gone"),
        on_try=said.append,
    )
    assert said
    assert "did not answer" in said[0]


def test_the_fast_path_reports_nothing() -> None:
    """One Identity Request, and silence about it."""

    def probe(send: str, recv: str) -> FakeDevice:
        return FakeDevice(send)

    said: list[str] = []

    def sweep(on_try: Any = None) -> FakeDevice:
        return FakeDevice("x")

    midi.open_remembered_or_swept(
        probe=probe,
        sweep=sweep,
        remembered=("ok", "ok"),
        on_try=said.append,
    )
    assert said == []


def test_what_the_sweep_learned_is_remembered() -> None:
    learned: list[FakeDevice] = []

    def probe(send: str, recv: str) -> FakeDevice:
        return FakeDevice(send)

    def sweep(on_try: Any = None) -> FakeDevice:
        return FakeDevice("found")

    midi.open_remembered_or_swept(
        probe=probe,
        sweep=sweep,
        scan=True,
        remember=learned.append,
    )
    assert [d.port for d in learned] == ["found"]


def test_a_probe_failure_is_not_swallowed_when_the_sweep_also_fails() -> None:
    """The sweep's own error is what the user needs to see, not the stale
    remembered port's."""

    def probe(send: str, recv: str) -> FakeDevice:
        raise midi.DeviceError("stale")

    def sweep(on_try: Any = None) -> FakeDevice:
        raise midi.DeviceNotFound("no unit answered") from None

    with pytest.raises(midi.DeviceNotFound, match="no unit answered"):
        midi.open_remembered_or_swept(
            probe=probe, sweep=sweep, remembered=("stale", "stale")
        )


def test_an_os_error_from_the_probe_also_falls_back() -> None:
    """A disconnected interface is an OSError, not a DeviceError, and it is
    the most common reason a remembered port stops answering."""

    def probe(send: str, recv: str) -> FakeDevice:
        raise OSError("no such device")

    def sweep(on_try: Any = None) -> FakeDevice:
        return FakeDevice("found")

    device = midi.open_remembered_or_swept(
        probe=probe, sweep=sweep, remembered=("gone", "gone")
    )
    assert device.port == "found"
