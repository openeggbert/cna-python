"""Little-endian BinaryReader composition used by the managed XNB pipeline."""

from __future__ import annotations

import struct
from typing import BinaryIO


class _BinaryReader:
    def __init__(self, stream: BinaryIO) -> None:
        if not hasattr(stream, "read"):
            raise TypeError("stream must be a readable binary stream")
        self._stream = stream
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed or bool(getattr(self._stream, "closed", False)):
            raise ValueError("I/O operation on closed content stream")

    def _read_exact(self, count: int) -> bytes:
        self._ensure_open()
        if type(count) is not int or count < 0:
            raise ValueError("byte count must be a non-negative int")
        result = bytearray()
        while len(result) < count:
            chunk = self._stream.read(count - len(result))
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise TypeError("stream.read() must return bytes")
            if not chunk:
                raise EOFError(f"content stream ended after {len(result)} of {count} bytes")
            result.extend(chunk)
        return bytes(result)

    def _unpack(self, format_: str):
        return struct.unpack("<" + format_, self._read_exact(struct.calcsize("<" + format_)))[0]

    def ReadBoolean(self) -> bool:
        return self.ReadByte() != 0

    def ReadByte(self) -> int:
        return self._read_exact(1)[0]

    def ReadSByte(self) -> int:
        return self._unpack("b")

    def ReadInt16(self) -> int:
        return self._unpack("h")

    def ReadUInt16(self) -> int:
        return self._unpack("H")

    def ReadInt32(self) -> int:
        return self._unpack("i")

    def ReadUInt32(self) -> int:
        return self._unpack("I")

    def ReadInt64(self) -> int:
        return self._unpack("q")

    def ReadUInt64(self) -> int:
        return self._unpack("Q")

    def ReadSingle(self) -> float:
        return self._unpack("f")

    def ReadDouble(self) -> float:
        return self._unpack("d")

    def ReadBytes(self, count: int) -> bytes:
        return self._read_exact(count)

    def Read7BitEncodedInt(self) -> int:
        value = 0
        for index in range(5):
            byte = self.ReadByte()
            if index == 4 and byte > 0x0F:
                raise ValueError("invalid 7-bit encoded Int32")
            value |= (byte & 0x7F) << (index * 7)
            if byte & 0x80 == 0:
                value &= 0xFFFFFFFF
                return value - 0x100000000 if value & 0x80000000 else value
        raise ValueError("invalid 7-bit encoded Int32")

    def ReadString(self) -> str:
        count = self.Read7BitEncodedInt()
        if count < 0:
            raise ValueError("string byte length is negative")
        return self._read_exact(count).decode("utf-8", errors="strict")

    def ReadChar(self) -> str:
        first = self.ReadByte()
        if first < 0x80:
            return chr(first)
        if 0xC2 <= first <= 0xDF:
            count = 2
        elif 0xE0 <= first <= 0xEF:
            count = 3
        else:
            # The selected System.Char mapping is one non-surrogate BMP code unit.
            raise UnicodeDecodeError("utf-8", bytes((first,)), 0, 1,
                                     "XNB Char is not a mapped BMP code unit")
        encoded = bytes((first,)) + self._read_exact(count - 1)
        value = encoded.decode("utf-8", errors="strict")
        if len(value) != 1 or ord(value) > 0xFFFF or 0xD800 <= ord(value) <= 0xDFFF:
            raise UnicodeDecodeError("utf-8", encoded, 0, len(encoded),
                                     "XNB Char is not a mapped BMP code unit")
        return value

    @property
    def Remaining(self) -> int | None:
        self._ensure_open()
        if not all(hasattr(self._stream, name) for name in ("tell", "seek")):
            return None
        position = self._stream.tell()
        end = self._stream.seek(0, 2)
        self._stream.seek(position)
        return int(end - position)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._stream, "close", None)
        if callable(close):
            close()

    def Dispose(self) -> None:
        self.close()

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
