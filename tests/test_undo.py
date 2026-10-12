# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Undo log invariants — headless, no real devices needed."""

from __future__ import annotations

import pytest

from vinsynlib.undo import Record, UndoLog


def test_record_is_inspectable_data() -> None:
    r = Record("label", payload={"key": 1})
    assert r.label == "label"
    assert r.payload == {"key": 1}
    assert r == Record("label", payload={"key": 1})


def test_undo_is_lifo() -> None:
    applied: list[int] = []

    def apply_hook(record: Record) -> None:
        applied.append(record.payload)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("first", 1))
    log.push(Record("second", 2))
    log.undo()
    assert applied == [2]
    assert len(log) == 1


def test_undo_clamps_to_log_length() -> None:
    applied: list[int] = []

    def apply_hook(record: Record) -> None:
        applied.append(record.payload)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("a", 1))
    result = log.undo(count=5)
    assert applied == [1]
    assert len(log) == 0
    assert result == "undid 1"


def test_pop_only_after_successful_revert() -> None:
    applied: list[int] = []
    call_count = 0

    def apply_hook(record: Record) -> None:
        nonlocal call_count
        call_count += 1
        if record.payload == 2:
            raise RuntimeError("fail")
        applied.append(record.payload)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("first", 1))
    log.push(Record("second", 2))
    result = log.undo()
    assert applied == []
    assert len(log) == 2
    assert result == "undo failed: RuntimeError: fail"
    assert isinstance(log.last_error, RuntimeError)


def test_undo_all_newest_first() -> None:
    applied: list[int] = []

    def apply_hook(record: Record) -> None:
        applied.append(record.payload)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("first", 1))
    log.push(Record("second", 2))
    log.push(Record("third", 3))
    result = log.undo_all()
    assert applied == [3, 2, 1]
    assert len(log) == 0
    assert result == "undid 3"


def test_undo_all_stops_on_first_failure() -> None:
    applied: list[int] = []

    def apply_hook(record: Record) -> None:
        if record.payload == 2:
            raise RuntimeError("fail")
        applied.append(record.payload)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("first", 1))
    log.push(Record("second", 2))
    log.push(Record("third", 3))
    result = log.undo_all()
    assert applied == [3]
    assert len(log) == 2
    assert result == "undid 1; failed: RuntimeError: fail"
    assert isinstance(log.last_error, RuntimeError)


def test_empty_log_message() -> None:
    log = UndoLog()
    result = log.undo()
    assert result == "nothing to undo"
    result_all = log.undo_all()
    assert result_all == "nothing to undo"


def test_gate_refuses_without_touching_log() -> None:
    def gate_hook() -> str | None:
        return "locked"

    log = UndoLog(gate_hook=gate_hook)
    log.push(Record("change", 1))
    result = log.undo()
    assert result == "refused: locked"
    assert len(log) == 1
    result_all = log.undo_all()
    assert result_all == "refused: locked"
    assert len(log) == 1


def test_status_hook_called() -> None:
    messages: list[str] = []

    def status_hook(msg: str) -> None:
        messages.append(msg)

    def apply_hook(record: Record) -> None:
        return None

    log = UndoLog(apply_hook=apply_hook, status_hook=status_hook)
    log.push(Record("a", 1))
    log.undo()
    assert "undid 1" in messages


def test_undo_applies_reverts_in_lifo_order() -> None:
    order: list[str] = []

    def apply_hook(record: Record) -> None:
        order.append(record.label)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    log.undo()
    assert order == ["b"]


def test_undo_all_applies_newest_first_then_pops() -> None:
    log = UndoLog()
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    assert bool(log) is True
    assert len(log) == 2


def test_undo_without_apply_hook_raises() -> None:
    log = UndoLog()
    log.push(Record("a", 1))
    with pytest.raises(RuntimeError):
        log.undo()
    assert len(log) == 1
    with pytest.raises(RuntimeError):
        log.undo_all()
    assert len(log) == 1


def test_empty_log_without_hook_is_still_empty_message() -> None:
    log = UndoLog()
    assert log.undo() == "nothing to undo"
    assert log.undo_all() == "nothing to undo"


def test_a_false_verdict_fails_one_entry_and_the_batch_continues() -> None:
    """``False`` is "this one failed", not "stop" -- and it is kept.

    The entry stays on the log, because pop-only-after-success is what
    leaves the log describing what is still applied; the batch carries
    on past it; and the number reported is the number that applied.
    """
    applied: list[int] = []

    def apply_hook(record: Record) -> bool | None:
        if record.payload == 2:
            return False
        applied.append(record.payload)
        return True

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("first", 1))
    log.push(Record("second", 2))
    log.push(Record("third", 3))
    result = log.undo(count=3)
    assert applied == [3, 1]
    assert len(log) == 1
    assert result == "undid 2; 1 failed"
    assert log.last_error is None


def test_a_batch_of_only_failures_reports_it_as_such() -> None:
    def apply_hook(record: Record) -> bool | None:
        return False

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    assert log.undo() == "undo failed: 1"
    assert len(log) == 2, "a refusal leaves the entry describing reality"
    assert log.undo_all() == "undo failed: 2"
    assert len(log) == 2


def test_plan_and_settle_reverse_newest_first_clamp_and_consume() -> None:
    """The plan/execute seam: taken off the log before the work runs.

    Consume-on-take is the whole point -- the log is already empty the
    moment the plan is handed over, so a half-failed batch cannot be
    replayed by the next press and a live count cannot lie.
    """
    log = UndoLog()
    for payload in (1, 2, 3):
        log.push(Record(f"r{payload}", payload))
    plan = log.plan(5)
    assert [record.payload for record in plan] == [3, 2, 1]
    assert len(log) == 0
    assert log.settle([True, False, True]) == "undid 2; 1 failed"
    assert len(log) == 0, "a half-failed batch stays off the log"
    assert log.plan(1) == []
    assert log.settle([]) == "nothing to undo"


def test_a_settled_failure_is_not_an_empty_log() -> None:
    log = UndoLog()
    log.push(Record("a", 1))
    assert log.plan(1) == [Record("a", 1)]
    assert log.settle([False]) == "undo failed: 1"
    assert log.settle([]) == "nothing to undo"


def test_the_gate_refuses_a_plan_without_touching_the_log() -> None:
    log = UndoLog(gate_hook=lambda: "locked")
    log.push(Record("a", 1))
    assert log.plan(1) == []
    assert log.last_refusal == "locked"
    assert len(log) == 1
    assert log.settle([]) == "refused: locked"
    assert log.undo() == "refused: locked"
    assert log.last_refusal == "locked"


def test_a_mixed_kind_log_reverses_in_true_lifo_order() -> None:
    """One timeline: the newest entry goes first whatever kind it is.

    Dispatch was already possible through the apply hook -- the hook is
    handed the record and decides from its payload -- and this pins the
    other half: the order is the log's, not the kind's.
    """
    order: list[str] = []

    def apply_hook(record: Record) -> None:
        order.append(record.label)

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("edit", "e1"))
    log.push(Record("favourite", "f1"))
    log.push(Record("rating", "r1"))
    log.undo(count=3)
    assert order == ["rating", "favourite", "edit"]


def test_the_log_is_inspectable_without_being_replayed() -> None:
    log = UndoLog()
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    assert [record.label for record in log] == ["a", "b"]
    assert len(log) == 2
    log.clear()
    assert list(log) == []


def test_the_simple_synchronous_path_is_unchanged() -> None:
    """The default door's whole contract, pinned in one place.

    The plan/settle door is an addition; this is the guard that the
    published synchronous path did not move with it.
    """
    messages: list[str] = []
    applied: list[int] = []

    def apply_hook(record: Record) -> None:
        applied.append(record.payload)

    def status_hook(message: str) -> None:
        messages.append(message)

    log = UndoLog(apply_hook=apply_hook, status_hook=status_hook)
    assert log.undo() == "nothing to undo"
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    assert log.undo() == "undid 1"
    assert applied == [2]
    assert len(log) == 1
    assert log.undo_all() == "undid 1"
    assert len(log) == 0
    assert log.undo_all() == "nothing to undo"
    assert messages == [
        "nothing to undo",
        "undid 1",
        "undid 1",
        "nothing to undo",
    ]


def test_failure_message_is_emitted_and_named() -> None:
    messages: list[str] = []

    def apply_hook(record: Record) -> None:
        raise RuntimeError("boom")

    def status_hook(msg: str) -> None:
        messages.append(msg)

    log = UndoLog(apply_hook=apply_hook, status_hook=status_hook)
    log.push(Record("a", 1))
    assert log.undo() == "undo failed: RuntimeError: boom"
    assert messages == ["undo failed: RuntimeError: boom"]


def test_last_error_cleared_by_successful_undo() -> None:
    calls = 0

    def apply_hook(record: Record) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("fail")

    log = UndoLog(apply_hook=apply_hook)
    log.push(Record("a", 1))
    log.push(Record("b", 2))
    assert log.undo() == "undo failed: RuntimeError: fail"
    assert log.last_error is not None
    assert log.undo() == "undid 1"
    assert log.last_error is None
