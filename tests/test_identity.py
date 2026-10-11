# ruff: noqa: PLR0913, PLR0917, RUF005
# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors

"""Byte-level identity (§3.9) tests — no real MIDI backend needed."""

from __future__ import annotations

import pytest

from vinsynlib import midi


def _build_reply(

    device: int = 0x7F,
    mfr_first: int = 0x01,
    family_lsb: int = 0x01,
    family_msb: int = 0x00,
    family_num_lsb: int = 0x02,
    family_num_msb: int = 0x00,
    version_bytes: bytes = b"\x00\x03\x00\x04",
) -> bytes:
    """Build an Identity Reply frame whose inner bytes sum to 0 mod 128."""
    inner = [
        0x7E,
        device,
        0x06,
        0x02,
        mfr_first,
        family_lsb,
        family_msb,
        family_num_lsb,
        family_num_msb,
    ] + list(version_bytes)
    checksum = (128 - (sum(inner) % 128)) % 128
    inner.append(checksum)
    return bytes([0xF0, *inner, 0xF7])


def test_identity_request_default() -> None:
    assert midi.identity_request() == bytes(
        [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]
    )


def test_identity_request_custom_device() -> None:
    assert midi.identity_request(0x42) == bytes(
        [0xF0, 0x7E, 0x42, 0x06, 0x01, 0xF7]
    )


def test_real_reply_parses() -> None:
    frame = _build_reply()
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F
    assert reply.family == 0x01
    # Wait: family_lsb=1, family_msb=0 -> family = 1 + 0*128 = 1
    # family_num_lsb=2, family_num_msb=0 -> family_number = 2
    assert reply.family == 1
    assert reply.family_number == 2
    # Revision from version_bytes big-endian
    assert reply.revision == int.from_bytes(b"\x00\x03\x00\x04", "big")


def test_echoed_request_is_rejected() -> None:
    request_frame = midi.identity_request()
    assert midi.parse_identity_reply(request_frame) is None


def test_truncated_frame_is_none() -> None:
    truncated = bytes([0xF0, 0x7E, 0x7F, 0x06, 0x02, 0xF7])
    assert midi.parse_identity_reply(truncated) is None


def test_broken_checksum_is_none() -> None:
    frame = _build_reply()
    broken = bytearray(frame)
    broken[-2] = (broken[-2] + 1) % 128  # corrupt checksum byte
    assert midi.parse_identity_reply(bytes(broken)) is None


def test_custom_manufacturer_reply_parses() -> None:
    frame = _build_reply(mfr_first=0x42)
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F


def test_three_byte_manufacturer_parses() -> None:
    inner_base = [0x7E, 0x7F, 0x06, 0x02, 0x00, 0x20, 0x00]
    inner_base += [0x01, 0x00, 0x02, 0x00]
    inner_base += list(b"\x00\x01\x00\x02")
    checksum = (128 - (sum(inner_base) % 128)) % 128
    inner_base.append(checksum)
    frame = bytes([0xF0, *inner_base, 0xF7])
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F
    assert reply.family == 1
    assert reply.family_number == 2


def test_foreign_manufacturer_parses() -> None:
    # A different manufacturer byte (e.g., 0x43 = Yamaha) must parse.
    frame = _build_reply(mfr_first=0x43)
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F


def test_f0_7d_is_rejected() -> None:
    # Custom/manufacturer header must be rejected.
    inner = [0x7D, 0x7F, 0x06, 0x02, 0x01, 0x01, 0x00, 0x02, 0x00]
    inner += list(b"\x00\x03\x00\x04")
    checksum = (128 - (sum(inner) % 128)) % 128
    inner.append(checksum)
    frame = bytes([0xF0, *inner, 0xF7])
    assert midi.parse_identity_reply(frame) is None


def test_identity_reply_dataclass_frozen() -> None:
    reply = midi.IdentityReply(
        device=1, family=2, family_number=3, revision=4
    )
    with pytest.raises(AttributeError):
        reply.device = 99  # type: ignore[misc]


def test_device_identity_dataclass_frozen() -> None:
    reply = midi.IdentityReply(
        device=1, family=2, family_number=3, revision=4
    )
    identity = midi.DeviceIdentity(
        send_port="out", recv_port="in", reply=reply
    )
    assert identity.send_port == "out"
    assert identity.recv_port == "in"
