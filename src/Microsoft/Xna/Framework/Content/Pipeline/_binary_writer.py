"""``System.IO.BinaryWriter``, as much of it as the pipeline writes.

The mirror of :class:`Microsoft.Xna.Framework.Content._binary._BinaryReader`,
and deliberately written against it: every method here is the inverse of one
there, so a value written by the compiler and read by the runtime goes through
one encoding rather than two that happen to agree.

``Write7BitEncodedInt`` and ``WriteString`` are the two that matter most. Both
are .NET's own encodings and both are what the XNB format uses for every count,
every type index and every string in a file.
"""

from __future__ import annotations

import struct
from typing import BinaryIO


class _BinaryWriter:
    """A little-endian binary writer over a stream."""

    __slots__ = ("_stream", "_closed")

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._closed = False

    @property
    def BaseStream(self) -> BinaryIO:
        self._ensure_open()
        return self._stream

    def Write(self, value: object) -> None:
        """Dispatches on the value's Python type.

        ``bool`` is checked before ``int`` because it is one, and a ``bool``
        written as an integer would be four bytes where the reader expects one.
        """
        if isinstance(value, bool):
            self.WriteBoolean(value)
        elif isinstance(value, int):
            self.WriteInt32(value)
        elif isinstance(value, float):
            self.WriteSingle(value)
        elif isinstance(value, str):
            self.WriteString(value)
        elif isinstance(value, (bytes, bytearray)):
            self.WriteBytes(value)
        else:
            raise TypeError(
                f"a BinaryWriter writes numbers, strings and bytes, not "
                f"{type(value).__name__}")

    def WriteBoolean(self, value: bool) -> None:
        self._write(b"\x01" if value else b"\x00")

    def WriteByte(self, value: int) -> None:
        self._write(struct.pack("<B", _ranged(value, 0, 255, "Byte")))

    def WriteSByte(self, value: int) -> None:
        self._write(struct.pack("<b", _ranged(value, -128, 127, "SByte")))

    def WriteInt16(self, value: int) -> None:
        self._write(struct.pack("<h", _ranged(value, -32768, 32767, "Int16")))

    def WriteUInt16(self, value: int) -> None:
        self._write(struct.pack("<H", _ranged(value, 0, 65535, "UInt16")))

    def WriteInt32(self, value: int) -> None:
        self._write(struct.pack(
            "<i", _ranged(value, -0x80000000, 0x7FFFFFFF, "Int32")))

    def WriteUInt32(self, value: int) -> None:
        self._write(struct.pack("<I", _ranged(value, 0, 0xFFFFFFFF, "UInt32")))

    def WriteInt64(self, value: int) -> None:
        self._write(struct.pack(
            "<q", _ranged(value, -(1 << 63), (1 << 63) - 1, "Int64")))

    def WriteUInt64(self, value: int) -> None:
        self._write(struct.pack("<Q", _ranged(value, 0, (1 << 64) - 1, "UInt64")))

    def WriteSingle(self, value: float) -> None:
        self._write(struct.pack("<f", float(value)))

    def WriteDouble(self, value: float) -> None:
        self._write(struct.pack("<d", float(value)))

    def WriteChar(self, value: str) -> None:
        if not isinstance(value, str) or len(value) != 1:
            raise TypeError("WriteChar takes a single character")
        self._write(value.encode("utf-8"))

    def WriteBytes(self, value: bytes) -> None:
        self._write(bytes(value))

    def Write7BitEncodedInt(self, value: int) -> None:
        """.NET's variable-length integer: seven bits per byte, high bit continues."""
        remaining = _ranged(value, 0, 0xFFFFFFFF, "7-bit encoded int")
        while remaining >= 0x80:
            self._write(bytes((remaining & 0x7F | 0x80,)))
            remaining >>= 7
        self._write(bytes((remaining,)))

    def WriteString(self, value: str) -> None:
        """A 7-bit encoded *byte* count, then the UTF-8 bytes.

        The count is bytes and not characters, which is the difference that
        matters the moment a string carries anything outside ASCII.
        """
        encoded = value.encode("utf-8")
        self.Write7BitEncodedInt(len(encoded))
        self._write(encoded)

    def Flush(self) -> None:
        self._ensure_open()
        self._stream.flush()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._stream.flush()

    def _write(self, raw: bytes) -> None:
        self._ensure_open()
        self._stream.write(raw)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("the writer has been closed")


def _ranged(value: object, low: int, high: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an int, not {type(value).__name__}")
    if not low <= value <= high:
        raise ValueError(f"{what} must be in {low}..{high}, got {value}")
    return value
