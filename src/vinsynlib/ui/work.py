# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Worker infrastructure shared by the family: gate, error set, idle-close."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

__all__ = [
    "QUIET_BRIDGE_ERRORS",
    "BusyGate",
    "close_when_idle",
]


#: Family-wide quiet error set. Programming errors (TypeError,
#: ValueError, etc.) are never silenced by this set — only the
#: listed bridge-error types.
QUIET_BRIDGE_ERRORS: frozenset[type[BaseException]] = frozenset(
    {
        ConnectionError,
        TimeoutError,
        OSError,
    }
)


class BusyGate:
    """Gate that refuses on the main thread before any worker starts.

    Usage:
        gate = BusyGate()
        with gate:
            # do work on a worker thread
            ...

    If `refuse()` is called before the context is entered, the context
    manager raises `RuntimeError` immediately and the body does not run.

    Entering the context also marks the gate as *in progress* for the
    duration of the body; `is_busy()` reports this so that an idle-close
    can tell a live exchange (context held) apart from a pending refusal
    (`check()`). The gate clears both its refusal and its in-progress
    state in `__exit__` (a finally-safe path), so even cancellation or
    exceptions leave it clean.
    """

    def __init__(self) -> None:
        self._refused: str | None = None
        self._active = 0
        self._lock = threading.Lock()
        self._owner_thread = threading.current_thread()

    def refuse(self, reason: str) -> None:
        """Record a refusal reason. Must be called on the main thread."""
        current = threading.current_thread()
        if current is not self._owner_thread:
            raise RuntimeError(
                "BusyGate.refuse must be called on the main thread"
            )
        with self._lock:
            self._refused = reason

    def check(self) -> str | None:
        """Return the refusal reason if any, else None."""
        with self._lock:
            return self._refused

    def is_busy(self) -> bool:
        """Return True while a `with gate:` body is in progress.

        This is distinct from `check()`: `check()` reports a *pending
        refusal*, whereas `is_busy()` reports an *active exchange* whose
        context is currently held. Either means an idle-close must not
        happen.
        """
        with self._lock:
            return self._active > 0

    def __enter__(self) -> BusyGate:
        with self._lock:
            if self._refused is not None:
                reason = self._refused
                self._refused = None
                raise RuntimeError(reason)
            self._active += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        with self._lock:
            self._refused = None
            if self._active > 0:
                self._active -= 1


@contextmanager
def close_when_idle(
    bridge: Any,
    *,
    gate: BusyGate,
    grace: float = 0.25,
) -> Iterator[None]:
    """Wait for the bridge to go idle, then close it.

    This never closes mid-exchange. It waits for the gate to be neither
    refused (`check()`) nor in progress (`is_busy()`) for `grace`
    seconds, then calls the bridge's `close()` method. If either signal
    appears during the wait, the wait is aborted and the bridge is not
    closed by this context manager.

    The `grace` parameter is the quiescence window — the bridge must stay
    idle for this long before we close it.
    """
    try:
        yield
    finally:
        deadline = time.time() + grace
        should_close = True
        while time.time() < deadline:
            if gate.check() is not None or gate.is_busy():
                # An operation is pending or in flight; abort the close
                should_close = False
                break
            time.sleep(0.01)
        # Grace period elapsed with no activity
        if should_close and hasattr(bridge, "close"):
            bridge.close()


def _is_quiet_error(exc: BaseException) -> bool:
    """Return True if `exc` is in the family quiet set."""
    return any(isinstance(exc, etype) for etype in QUIET_BRIDGE_ERRORS)


def _filter_error(exc: BaseException) -> BaseException | None:
    """Return `exc` if it should be raised, else None (suppressed)."""
    if _is_quiet_error(exc):
        return None
    return exc
