# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""App contract — screens depend on this, never on BrowserApp."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["AppProtocol"]


@runtime_checkable
class AppProtocol(Protocol):
    """What every screen types its caller as."""

    def notify_status(
        self, message: str, *, refused: bool = False
    ) -> None: ...

    def notify_progress(self, label: str, done: int, total: int) -> None: ...

    def push_screen(
        self, screen: object, *, wait_for_dismiss: bool = False
    ) -> None: ...
