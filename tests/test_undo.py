# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Undo log invariants — headless, no real devices needed."""

from __future__ import annotations

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
    assert result == "nothing to undo"


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
    assert result == "undid 1"


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

    log = UndoLog(status_hook=status_hook)
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
