# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Rendering helpers — table and progress — with no Textual dependency."""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["progress", "table"]


def _line_for(values: Sequence[str], widths: list[int], col_count: int) -> str:
    parts: list[str] = []
    for i in range(col_count):
        val = values[i] if i < len(values) else ""
        w = max(widths[i], 1)
        if len(val) > w:
            val = (val[: w - 1] + "…") if w > 1 else val[:w]
        parts.append(f"{val:>{w}}")
    return " | ".join(parts)


def _cap_widths(widths: list[int], col_count: int) -> list[int]:
    overhead = max(0, (col_count - 1) * 3)
    max_content = max(79 - overhead, 0) if col_count > 0 else 79
    total_raw = sum(widths)
    if col_count > 0 and total_raw > max_content and total_raw > 0:
        scale = max_content / total_raw
        capped = [max(1, int(w * scale)) for w in widths]
        extra = max_content - sum(capped)
        idxs = sorted(
            range(col_count),
            key=lambda i: widths[i] / capped[i],
            reverse=True,
        )
        for k in range(extra):
            capped[idxs[k % col_count]] += 1
        return capped
    return widths


def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    empty: str = "",
) -> str:
    if not rows:
        return empty

    col_count = len(headers)
    for row in rows:
        col_count = max(col_count, len(row))

    widths: list[int] = [0] * col_count
    for i in range(col_count):
        text = headers[i] if i < len(headers) else ""
        widths[i] = len(text)
    for row in rows:
        for i in range(col_count):
            cell = row[i] if i < len(row) else ""
            widths[i] = max(widths[i], len(cell))

    widths = _cap_widths(widths, col_count)

    result_lines: list[str] = []
    if col_count > 0:
        result_lines.append(_line_for(headers, widths, col_count))
        result_lines.append(
            " | ".join("-" * max(widths[i], 1) for i in range(col_count))
        )
    for row in rows:
        result_lines.append(_line_for(row, widths, col_count))
    return "\n".join(result_lines)


def progress(label: str, done: int, total: int) -> str:
    return f"\r  {label} {done}/{total}"
