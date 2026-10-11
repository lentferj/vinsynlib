# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Undo log — stdlib-only, inspectable records, no threads, no locks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["Record", "UndoLog"]


@dataclass(frozen=True, slots=True)
class Record:
    """Inspectable change data — never a closure."""

    label: str
    payload: Any = None


class UndoLog:
    """Synchronous LIFO undo log; invariants owned and tested here.

    Undoing requires an ``apply_hook``: undoing a non-empty log that
    has none raises ``RuntimeError`` rather than silently discarding
    records. A failed revert is named in the returned status message
    and kept on ``last_error``, so it cannot be mistaken for an empty
    log.
    """

    def __init__(
        self,
        apply_hook: Callable[[Record], None] | None = None,
        gate_hook: Callable[[], str | None] | None = None,
        status_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.apply_hook = apply_hook
        self.gate_hook = gate_hook
        self.status_hook = status_hook
        self.last_error: Exception | None = None
        self._log: list[Record] = []

    def push(self, record: Record) -> None:
        self._log.append(record)

    def undo(self, count: int = 1) -> str:
        self.last_error = None
        refusal = self.gate_hook() if self.gate_hook else None
        if refusal is not None:
            return self._emit(f"refused: {refusal}")
        if not self._log:
            return self._emit("nothing to undo")
        apply = self.apply_hook
        if apply is None:
            raise RuntimeError("undo requires an apply_hook")
        clamped = min(count, len(self._log))
        applied = 0
        for _ in range(clamped):
            if not self._log:
                break
            record = self._log[-1]
            try:
                apply(record)
            except Exception as exc:
                self.last_error = exc
                break
            applied += 1
            self._log.pop()
        return self._result(applied)

    def undo_all(self) -> str:
        self.last_error = None
        refusal = self.gate_hook() if self.gate_hook else None
        if refusal is not None:
            return self._emit(f"refused: {refusal}")
        if not self._log:
            return self._emit("nothing to undo")
        apply = self.apply_hook
        if apply is None:
            raise RuntimeError("undo requires an apply_hook")
        applied = 0
        # Newest-first: process from end of list.
        while self._log:
            record = self._log[-1]
            try:
                apply(record)
            except Exception as exc:
                self.last_error = exc
                break
            applied += 1
            self._log.pop()
        return self._result(applied)

    def _emit(self, message: str) -> str:
        if self.status_hook:
            self.status_hook(message)
        return message

    def _result(self, applied: int) -> str:
        error = self.last_error
        if error is not None:
            reason = f"{type(error).__name__}: {error}"
            if applied > 0:
                return self._emit(f"undid {applied}; failed: {reason}")
            return self._emit(f"undo failed: {reason}")
        if applied > 0:
            return self._emit(f"undid {applied}")
        return self._emit("nothing to undo")

    def __len__(self) -> int:
        return len(self._log)

    def __bool__(self) -> bool:
        return bool(self._log)
