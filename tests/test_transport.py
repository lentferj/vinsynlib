# SPDX-License-Identifier: GPL-2.0-or-later
"""Transport (§3.8) tests: fake objects, no real ALSA."""

from __future__ import annotations

import time
from typing import Any

import pytest

from vinsynlib import midi


class FakePort:
    """A stand-in rtmidi MidiOut / MidiIn for headless testing."""

    def __init__(self, ports: list[str] | None = None) -> None:
        self.ports = ports if ports is not None else ["fake"]
        self.sent: list[Any] = []
        self.closed = False
        self.deleted = False
        self.sysex_on = False

    def get_ports(self) -> list[str]:
        return self.ports

    def open_port(self, index: int) -> None:
        if index < 0 or index >= len(self.ports):
            raise RuntimeError("bad index")

    def send_message(self, message: Any) -> None:
        self.sent.append(message)

    def get_message(self) -> Any:
        return None

    def ignore_types(self, sysex: bool = True, **_kw: Any) -> None:
        # sysex=False means sysex messages are enabled (not ignored)
        self.sysex_on = not sysex

    def close_port(self) -> None:
        self.closed = True

    def delete(self) -> None:
        self.deleted = True


class FakeRtmidi:
    """A fake rtmidi module for transport tests."""

    @staticmethod
    def MidiIn(**_kw: Any) -> FakePort:
        return FakePort()

    @staticmethod
    def MidiOut(**_kw: Any) -> FakePort:
        return FakePort()


def test_sysex_gap_is_floor_constant() -> None:
    assert isinstance(midi.SYSEX_GAP, float)
    assert midi.SYSEX_GAP == 0.075


def test_throttled_out_short_frames_never_sleep(monkeypatch: Any) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)

    fake = FakePort()
    throttle = midi.ThrottledOut(fake)
    throttle.send_message([0x90, 0x40, 0x7F])  # ordinary MIDI
    assert sleeps == []
    throttle.send_message([])  # empty / short frame
    assert sleeps == []


def test_throttled_out_sysex_sleeps_with_owed_gap(monkeypatch: Any) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)

    fake = FakePort()
    throttle = midi.ThrottledOut(fake)
    throttle.send_message([0xF0, 0x00, 0x01])  # sysex start (first, no sleep)
    assert len(sleeps) == 0  # gap owed after send, not before first
    throttle.send_message([0xF0, 0x00, 0x02])  # second sysex triggers sleep
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(midi.SYSEX_GAP, abs=0.002)
    assert fake.sent[-1][0] == 0xF0


def test_throttled_out_write_gap_param_is_independent() -> None:
    fake = FakePort()
    throttle = midi.ThrottledOut(fake, gap=0.010, write_gap=0.200)
    assert throttle._gap == 0.010
    assert throttle._write_gap == 0.200


def test_throttled_out_default_write_gap_falls_back_to_sysex_gap() -> None:
    fake = FakePort()
    throttle = midi.ThrottledOut(fake)
    assert throttle._write_gap == midi.SYSEX_GAP


def test_multiin_enum_list_seam(monkeypatch: Any) -> None:
    monkeypatch.setattr(midi, "_rtmidi", lambda: FakeRtmidi)
    multi = midi.MultiIn("fake", exact=True)
    assert isinstance(multi.ports, list)
    assert len(multi.ports) >= 1
    assert multi.get_ports() == ["fake"]
    multi.close_port()
    for p in multi.ports:
        assert p.closed is True or p.deleted is True


def test_multiin_no_match_raises(monkeypatch: Any) -> None:
    monkeypatch.setattr(midi, "_rtmidi", lambda: FakeRtmidi)
    with pytest.raises(RuntimeError, match="no input port"):
        midi.MultiIn("nonexistent", exact=True)


def test_open_input_and_output_leak_free(monkeypatch: Any) -> None:
    monkeypatch.setattr(midi, "_rtmidi", lambda: FakeRtmidi)
    out = midi.open_output("fake")
    # MidiOut does not call ignore_types; sysex_on stays False.
    assert out.sysex_on is False
    inp = midi.open_input("fake")
    assert inp.sysex_on is True
    inp.close_port()
    inp.delete()
    out.close_port()
    out.delete()


def test_open_input_closes_on_missing_port(monkeypatch: Any) -> None:
    monkeypatch.setattr(midi, "_rtmidi", lambda: FakeRtmidi)
    with pytest.raises(RuntimeError, match="no input port"):
        midi.open_input("missing")


def test_close_and_delete_param_handles_errors() -> None:
    fake = FakePort()
    midi._close_and_delete(fake)
    assert fake.closed is True
    assert fake.deleted is True
