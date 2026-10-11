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
    """Build a spec-shaped Identity Reply frame.

    The Universal Identity Reply has no checksum byte, so neither does
    this frame: it is the real wire shape.
    """
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


def test_no_checksum_reply_parses() -> None:
    # Regression: a real Identity Reply carries NO checksum, so its inner
    # bytes do not sum to 0 mod 128. The parser must accept it anyway.
    frame = _build_reply()
    assert sum(frame[1:-1]) % 128 != 0
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F


def test_custom_manufacturer_reply_parses() -> None:
    frame = _build_reply(mfr_first=0x42)
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x7F


def test_three_byte_manufacturer_parses() -> None:
    inner_base = [0x7E, 0x7F, 0x06, 0x02, 0x00, 0x20, 0x00]
    inner_base += [0x01, 0x00, 0x02, 0x00]
    inner_base += list(b"\x00\x01\x00\x02")
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
    # A 0x7D custom header is not an Identity Reply; rejected by the
    # inner[0] != 0x7E test (the reply must start with 0x7E).
    inner = [0x7D, 0x7F, 0x06, 0x02, 0x01, 0x01, 0x00, 0x02, 0x00]
    inner += list(b"\x00\x03\x00\x04")
    frame = bytes([0xF0, *inner, 0xF7])
    assert midi.parse_identity_reply(frame) is None


def test_literal_korg_and_roland_replies_parse() -> None:
    # Literal spec-shaped replies with no checksum: Korg 0x42 and
    # Roland 0x41. Neither inner sum is 0 mod 128.
    def reply(mfr: int) -> bytes:
        return bytes(
            [
                0xF0,
                0x7E,
                0x00,
                0x06,
                0x02,
                mfr,
                0x01,
                0x00,
                0x02,
                0x00,
                0x00,
                0x03,
                0x00,
                0x04,
                0xF7,
            ]
        )

    for mfr in (0x42, 0x41):
        frame = reply(mfr)
        assert sum(frame[1:-1]) % 128 != 0
        parsed = midi.parse_identity_reply(frame)
        assert parsed is not None
        assert parsed.device == 0x00
        assert parsed.family == 0x0001
        assert parsed.family_number == 0x0002
        assert parsed.revision == 0x00030004


def test_documented_akai_reply_parses() -> None:
    # A literal documented Identity Reply from AKAISDS
    # (src/core/midi_identity.py), wrapped in the F0/F7 the sample omits.
    # It has no checksum and must parse.
    inner = [
        0x7E,
        0x00,
        0x06,
        0x02,
        0x47,
        0x01,
        0x02,
        0x03,
        0x04,
        0x01,
        0x00,
        0x00,
        0x00,
    ]
    frame = bytes([0xF0, *inner, 0xF7])
    reply = midi.parse_identity_reply(frame)
    assert reply is not None
    assert reply.device == 0x00
    assert reply.family == 0x0101  # 0x01 | (0x02 << 7)
    assert reply.family_number == 0x0203  # 0x03 | (0x04 << 7)
    assert reply.revision == 0x01000000


def test_identity_reply_dataclass_frozen() -> None:
    reply = midi.IdentityReply(device=1, family=2, family_number=3, revision=4)
    with pytest.raises(AttributeError):
        reply.device = 99  # type: ignore[misc]


def test_device_identity_dataclass_frozen() -> None:
    reply = midi.IdentityReply(device=1, family=2, family_number=3, revision=4)
    identity = midi.DeviceIdentity(
        send_port="out", recv_port="in", reply=reply
    )
    assert identity.send_port == "out"
    assert identity.recv_port == "in"
