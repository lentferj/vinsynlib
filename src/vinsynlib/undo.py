# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Undo log — stdlib-only, inspectable records, no threads, no locks."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
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

    Two doors, because the family has two failure modes and neither is
    a bug to fix into the other:

    - :meth:`undo` / :meth:`undo_all` pop **only after a successful
      revert**. The entry stays on the log -- which is what still says
      the old value is what the unit holds -- so a retry can put it
      back. That is right whenever undo means re-sending a value.
    - :meth:`plan` / :meth:`settle` **consume on take**. The entries
      are off the log before the work runs, on the tool's own thread,
      because a write the unit refused must not be replayed by the next
      press; :meth:`settle` reports what actually landed.

    An :attr:`apply_hook` may also answer ``False`` for "this entry
    failed": the batch carries on, the entry stays on the log, and the
    number reported is the number that actually applied. Raising still
    stops the batch and names the exception on :attr:`last_error` -- a
    raise is the hook saying it could not try, a ``False`` is it saying
    the unit refused, and a project gets to ask either question.
    """

    def __init__(
        self,
        apply_hook: Callable[[Record], bool | None] | None = None,
        gate_hook: Callable[[], str | None] | None = None,
        status_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.apply_hook = apply_hook
        self.gate_hook = gate_hook
        self.status_hook = status_hook
        self.last_error: Exception | None = None
        # Why the last undo or plan was refused by the gate, or None
        # when it was not. Not a failure: nothing was attempted, so it
        # is not :attr:`last_error` -- a tool reads this to tell "the
        # gate said no" from "the log was empty".
        self.last_refusal: str | None = None
        self._log: list[Record] = []

    def push(self, record: Record) -> None:
        self._log.append(record)

    def clear(self) -> None:
        """Drop every record; the timeline starts again from empty."""
        self._log.clear()

    def __iter__(self) -> Iterator[Record]:
        """The records, oldest first — inspectable, never replayed.

        The other half of inspectable data: a history screen renders
        the log without undoing it, so reading what is on it is not the
        same operation as taking it.
        """
        return iter(list(self._log))

    def __len__(self) -> int:
        return len(self._log)

    def __bool__(self) -> bool:
        return bool(self._log)

    def undo(self, count: int = 1) -> str:
        """Undo the last ``count`` changes, newest first.

        Pop-after-success: an entry leaves the log only once its
        revert succeeded, so a failure part-way leaves the log
        describing what is still applied.
        """
        self.last_error = None
        refusal = self._refusal()
        if refusal is not None:
            return self._emit(f"refused: {refusal}")
        if not self._log:
            return self._emit("nothing to undo")
        apply = self.apply_hook
        if apply is None:
            raise RuntimeError("undo requires an apply_hook")
        applied, failed = self._apply_batch(apply, min(count, len(self._log)))
        return self._result(applied, failed)

    def undo_all(self) -> str:
        """Undo every change there is, newest first."""
        self.last_error = None
        refusal = self._refusal()
        if refusal is not None:
            return self._emit(f"refused: {refusal}")
        if not self._log:
            return self._emit("nothing to undo")
        apply = self.apply_hook
        if apply is None:
            raise RuntimeError("undo requires an apply_hook")
        applied, failed = self._apply_batch(apply, len(self._log))
        return self._result(applied, failed)

    def plan(self, count: int) -> list[Record]:
        """Which entries to undo, newest first, taken off the log.

        The consume-on-take door, for the tool whose work runs on a
        thread of its own: the library owns *which* -- order, clamping
        and the gate -- and the tool owns *when* it runs them. The
        records are gone from the log as the plan is taken, so a
        half-failed batch cannot be replayed by the next press and a
        live count cannot claim an entry that is being undone right
        now. A tool whose failure mode is a retry pushes back what
        failed; one whose is not does nothing.

        A refusal by the gate returns ``[]`` and is named on
        :attr:`last_refusal`, with the log untouched.
        """
        self.last_error = None
        refusal = self._refusal()
        if refusal is not None:
            return []
        clamped = min(count, len(self._log))
        if clamped <= 0:
            return []
        taken = self._log[-clamped:]
        del self._log[-clamped:]
        return list(reversed(taken))

    def settle(self, results: Sequence[bool]) -> str:
        """Report a batch that ran elsewhere; one sentence, our facts.

        ``results`` answers the :meth:`plan` this settles, in its
        order: ``True`` where the work landed and ``False`` where it
        did not. A per-entry failure is a fact rather than an exception
        -- the tool collected them instead of stopping at the first --
        so the sentence counts them and says "failed" where the
        exception voice would have named a traceback. The log was
        settled when the plan was taken; nothing is popped here.

        The tool that keeps its own words reads the same facts off the
        plan it ran and off ``results``; this is the default voice.
        """
        if self.last_refusal is not None:
            return self._emit(f"refused: {self.last_refusal}")
        failed = sum(1 for ok in results if not ok)
        return self._emit(self._verdict(len(results) - failed, failed))

    def _refusal(self) -> str | None:
        """Ask the gate, and remember the answer as a fact."""
        refusal = self.gate_hook() if self.gate_hook else None
        self.last_refusal = refusal
        return refusal

    def _apply_batch(
        self, apply: Callable[[Record], bool | None], count: int
    ) -> tuple[int, int]:
        """Run up to ``count`` newest-first; return ``(applied, failed)``.

        One loop for both synchronous doors, because the difference
        between them is only how many they take: the pop-after-success
        rule and the two ways of saying no are the same in each.

        The rule needs a slice rather than a peek at the tail: an entry
        that failed is still at the head of the log -- that is what
        pop-after-success means -- so a loop reading ``self._log[-1]``
        would try the same refused entry again until the count ran out.
        So the batch takes its slice, works through it newest-first and
        puts back what it did not get through: the ``False`` verdicts
        and, after an exception, the entries it never reached. They go
        back in the order they happened, so the log still describes
        exactly what is applied.
        """
        taken_count = min(count, len(self._log))
        if taken_count <= 0:
            return 0, 0
        taken = self._log[-taken_count:]
        del self._log[-taken_count:]
        applied = 0
        failed = 0
        # Parallel to ``taken``: what the batch got through and may
        # therefore leave off the log.
        landed = [False] * len(taken)
        for index in range(len(taken) - 1, -1, -1):
            record = taken[index]
            try:
                verdict = apply(record)
            except Exception as exc:
                self.last_error = exc
                break
            if verdict is False:
                failed += 1
                continue
            applied += 1
            landed[index] = True
        self._log.extend(
            record
            for record, done in zip(taken, landed, strict=True)
            if not done
        )
        return applied, failed

    def _emit(self, message: str) -> str:
        if self.status_hook:
            self.status_hook(message)
        return message

    def _result(self, applied: int, failed: int) -> str:
        error = self.last_error
        if error is not None:
            reason = f"{type(error).__name__}: {error}"
            if applied > 0:
                return self._emit(f"undid {applied}; failed: {reason}")
            return self._emit(f"undo failed: {reason}")
        return self._emit(self._verdict(applied, failed))

    def _verdict(self, applied: int, failed: int) -> str:
        """The sentence for a batch that raised nothing."""
        if failed:
            if applied:
                return f"undid {applied}; {failed} failed"
            return f"undo failed: {failed}"
        if applied:
            return f"undid {applied}"
        return "nothing to undo"
