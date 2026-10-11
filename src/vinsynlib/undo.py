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
    """Synchronous LIFO undo log; invariants owned and tested here."""

    def __init__(
        self,
        apply_hook: Callable[[Record], None] | None = None,
        gate_hook: Callable[[], str | None] | None = None,
        status_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.apply_hook = apply_hook
        self.gate_hook = gate_hook
        self.status_hook = status_hook
        self._log: list[Record] = []

    def push(self, record: Record) -> None:
        self._log.append(record)

    def undo(self, count: int = 1) -> str:
        refusal = self.gate_hook() if self.gate_hook else None
        if refusal is not None:
            msg = f"refused: {refusal}"
            if self.status_hook:
                self.status_hook(msg)
            return msg
        if not self._log:
            msg = "nothing to undo"
            if self.status_hook:
                self.status_hook(msg)
            return msg
        clamped = min(count, len(self._log))
        applied = 0
        for _ in range(clamped):
            if not self._log:
                break
            record = self._log[-1]
            try:
                if self.apply_hook:
                    self.apply_hook(record)
                applied += 1
                self._log.pop()
            except Exception:
                break
        msg = f"undid {applied}" if applied > 0 else "nothing to undo"
        if self.status_hook:
            self.status_hook(msg)
        return msg

    def undo_all(self) -> str:
        refusal = self.gate_hook() if self.gate_hook else None
        if refusal is not None:
            msg = f"refused: {refusal}"
            if self.status_hook:
                self.status_hook(msg)
            return msg
        if not self._log:
            msg = "nothing to undo"
            if self.status_hook:
                self.status_hook(msg)
            return msg
        applied = 0
        # Newest-first: process from end of list.
        while self._log:
            record = self._log[-1]
            try:
                if self.apply_hook:
                    self.apply_hook(record)
                applied += 1
                self._log.pop()
            except Exception:
                break
        msg = f"undid {applied}" if applied > 0 else "nothing to undo"
        if self.status_hook:
            self.status_hook(msg)
        return msg

    def __len__(self) -> int:
        return len(self._log)

    def __bool__(self) -> bool:
        return bool(self._log)
