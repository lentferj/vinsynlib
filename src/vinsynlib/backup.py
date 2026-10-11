# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Stdlib-only JSON envelope for device backups — no MIDI, no Textual."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

FORMAT = 1

__all__ = ["FORMAT", "Backup", "list_backups", "load", "save"]


@dataclass(frozen=True)
class Backup:
    kind: str
    slot: str
    name: str
    saved: float
    device_id: str
    source: str
    blocks: dict[str, bytes]
    error: str | None = None


def _encode_blocks(blocks: dict[str, bytes]) -> dict[str, str]:
    return {
        k: base64.b64encode(v).decode("ascii") for k, v in blocks.items()
    }


def _decode_blocks(blocks: dict[str, str]) -> dict[str, bytes]:
    return {k: base64.b64decode(v) for k, v in blocks.items()}


def _sanitize(part: str) -> str:
    safe = []
    for ch in part:
        if ch.isalnum() or ch in ("_", "-", "."):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe)


def save(  # noqa: PLR0913
    target_dir: str,
    *,
    kind: str,
    slot: str,
    name: str,
    device_id: str,
    source: str,
    blocks: dict[str, bytes],
) -> str:
    os.makedirs(target_dir, exist_ok=True)
    saved = time.time()
    backup = Backup(
        kind=kind,
        slot=slot,
        name=name,
        saved=saved,
        device_id=device_id,
        source=source,
        blocks=blocks,
    )
    base = (
        f"{_sanitize(kind)}_"
        f"{_sanitize(slot)}_"
        f"{_sanitize(name)}_"
        f"{saved:.6f}"
    )
    filename = f"{base}.json"
    path = os.path.join(target_dir, filename)
    count = 1
    while os.path.exists(path):
        filename = f"{base}_{count}.json"
        path = os.path.join(target_dir, filename)
        count += 1
    payload = {
        "format": FORMAT,
        "kind": backup.kind,
        "slot": backup.slot,
        "name": backup.name,
        "saved": backup.saved,
        "device_id": backup.device_id,
        "source": backup.source,
        "blocks": _encode_blocks(backup.blocks),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def load(path: str) -> Backup:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("not a dict")
    if data.get("format") != FORMAT:
        raise ValueError(f"wrong version: expected {FORMAT}")
    kind = data.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError("wrong kind")
    raw_blocks: dict[str, Any] = data.get("blocks", {})
    if isinstance(raw_blocks, dict) and all(
        isinstance(k, str) and isinstance(v, str)
        for k, v in raw_blocks.items()
    ):
        blocks = _decode_blocks(raw_blocks)
    else:
        blocks = {}
    return Backup(
        kind=kind,
        slot=data.get("slot", "")
        if isinstance(data.get("slot"), str)
        else "",
        name=data.get("name", "")
        if isinstance(data.get("name"), str)
        else "",
        saved=float(data.get("saved", 0))
        if isinstance(data.get("saved"), (int, float))
        else 0.0,
        device_id=data.get("device_id", "")
        if isinstance(data.get("device_id"), str)
        else "",
        source=data.get("source", "")
        if isinstance(data.get("source"), str)
        else "",
        blocks=blocks,
    )


def list_backups(target_dir: str) -> list[Backup]:  # noqa: C901
    result: list[Backup] = []
    if not os.path.isdir(target_dir):
        return result
    for entry in sorted(os.listdir(target_dir)):
        path = os.path.join(target_dir, entry)
        if not os.path.isfile(path):
            continue
        try:
            result.append(load(path))
        except Exception as exc:
            partial: dict[str, Any] = {}
            with contextlib.suppress(Exception), open(
                path, encoding="utf-8"
            ) as f:
                partial = json.load(f)
            kind_str = partial.get("kind", "")
            if not isinstance(kind_str, str):
                kind_str = ""
            slot_str = partial.get("slot", "")
            if not isinstance(slot_str, str):
                slot_str = ""
            name_str = partial.get("name", "")
            if not isinstance(name_str, str):
                name_str = ""
            saved_f = 0.0
            with contextlib.suppress(Exception):
                saved_f = float(partial.get("saved", 0))
            raw_blocks_partial = partial.get("blocks", {})
            blocks_partial: dict[str, bytes] = {}
            if isinstance(raw_blocks_partial, dict):
                for k, v in raw_blocks_partial.items():
                    if isinstance(k, str) and isinstance(v, str):
                        with contextlib.suppress(Exception):
                            blocks_partial[k] = base64.b64decode(v)
            result.append(
                Backup(
                    kind=kind_str,
                    slot=slot_str,
                    name=name_str,
                    saved=saved_f,
                    device_id=partial.get("device_id", "")
                    if isinstance(partial.get("device_id"), str)
                    else "",
                    source=partial.get("source", "")
                    if isinstance(partial.get("source"), str)
                    else "",
                    blocks=blocks_partial,
                    error=str(exc),
                )
            )
    return result
