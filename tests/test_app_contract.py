# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Pilot-app conformance for BrowserApp (§3.11)."""

from __future__ import annotations

from typing import cast

import pytest

from vinsynlib.ui.browser import BrowserApp


def test_css_token_refused_present() -> None:
    assert "#status.refused" in BrowserApp.DEFAULT_CSS


@pytest.mark.asyncio
async def test_refused_flag_flips_and_restores() -> None:
    async with BrowserApp().run_test() as pilot:
        app = cast(BrowserApp, pilot.app)
        app.notify_status("hello")
        assert app.last_status == "hello"
        assert app.last_status_refused is False
        app.notify_status("refused", refused=True)
        assert app.last_status == "refused"
        assert app.last_status_refused is True
        app.notify_status("restored")
        assert app.last_status == "restored"
        assert app.last_status_refused is False


@pytest.mark.asyncio
async def test_progress_never_overwrites_refusal() -> None:
    async with BrowserApp().run_test() as pilot:
        app = cast(BrowserApp, pilot.app)
        app.notify_status("bad", refused=True)
        assert app.last_status_refused is True
        app.notify_progress("work", 2, 5)
        assert app.last_status == "work"
        assert app.last_status_refused is True
