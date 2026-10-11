# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Tests for ui/work.py — six invariants against a scripted fake bridge."""

from __future__ import annotations

import threading
import time

import pytest

from vinsynlib.ui.work import QUIET_BRIDGE_ERRORS, BusyGate, close_when_idle


class FakeBridge:
    def __init__(self) -> None:
        self.closed = False
        self.exchanges = 0

    def close(self) -> None:
        self.closed = True

    def do_exchange(self) -> None:
        self.exchanges += 1


def test_1_busy_check_main_thread() -> None:
    """BusyGate.refuse must be called on the main thread."""
    gate = BusyGate()
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            gate.refuse("from worker")
        except BaseException as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "main thread" in str(errors[0])


def test_2_lock_across_exchange() -> None:
    """BusyGate holds refusal across an exchange (context manager)."""
    gate = BusyGate()
    gate.refuse("busy")

    with pytest.raises(RuntimeError, match="busy"), gate:
        pass  # body should not run

    # After exit, gate is clear
    assert gate.check() is None


def test_3_quiet_set_only() -> None:
    """QUIET_BRIDGE_ERRORS has only the family quiet set; programming
    errors raise."""
    assert ConnectionError in QUIET_BRIDGE_ERRORS
    assert TimeoutError in QUIET_BRIDGE_ERRORS
    assert OSError in QUIET_BRIDGE_ERRORS

    # Programming errors are NOT in the quiet set
    assert TypeError not in QUIET_BRIDGE_ERRORS
    assert ValueError not in QUIET_BRIDGE_ERRORS
    assert RuntimeError not in QUIET_BRIDGE_ERRORS


def test_4_finally_on_cancel_needs_cancelled_worker() -> None:
    """BusyGate.__exit__ clears state even when cancelled (exception
    in body)."""
    gate = BusyGate()

    class CancelledError(Exception):
        pass

    with pytest.raises(CancelledError), gate:
        raise CancelledError("cancelled")

    assert gate.check() is None


def test_5_call_from_thread() -> None:
    """BusyGate can be checked from a worker thread (read-only)."""
    gate = BusyGate()
    results: list[str | None] = []

    def worker() -> None:
        results.append(gate.check())

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert results == [None]

    gate.refuse("blocked")
    results.clear()
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert results == ["blocked"]


def test_6_read_back_pinned_by_consumer_fakes() -> None:
    """close_when_idle waits for grace, then closes; aborts if gate
    becomes busy."""
    bridge = FakeBridge()
    gate = BusyGate()

    # Idle close: gate stays clear, bridge closes after grace
    with close_when_idle(bridge, gate=gate, grace=0.05):
        pass

    assert bridge.closed is True

    # Second test: gate becomes busy during grace -> no close
    # Use a flag to signal the main thread to refuse during grace
    bridge2 = FakeBridge()
    gate2 = BusyGate()
    signal = threading.Event()

    def wait_and_signal() -> None:
        time.sleep(0.02)
        signal.set()

    t = threading.Thread(target=wait_and_signal)
    with close_when_idle(bridge2, gate=gate2, grace=0.2):
        t.start()
        # Main thread waits for signal, then refuses
        while not signal.is_set():
            time.sleep(0.01)
        gate2.refuse("new op")
    t.join()

    # Bridge should NOT be closed because gate became busy during grace
    assert bridge2.closed is False


def test_gate_context_allows_when_clear() -> None:
    """Gate with no refusal allows the body to run."""
    gate = BusyGate()
    ran = False
    with gate:
        ran = True
    assert ran is True


def test_gate_clear_after_normal_exit() -> None:
    """Gate clears refusal after normal context exit."""
    gate = BusyGate()
    gate.refuse("reason")
    with pytest.raises(RuntimeError), gate:
        pass
    assert gate.check() is None


def test_close_when_idle_no_grace_if_already_busy() -> None:
    """If gate is already busy on entry, close_when_idle skips wait."""
    bridge = FakeBridge()
    gate = BusyGate()
    gate.refuse("already busy")

    with close_when_idle(bridge, gate=gate, grace=0.5):
        pass

    # Should not close because gate was busy
    assert bridge.closed is False
