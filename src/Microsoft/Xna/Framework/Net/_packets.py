"""PacketReader and PacketWriter: the typed two sides of a network packet.

XNA derives these from ``BinaryReader`` and ``BinaryWriter``. Python's
``io`` has no equivalent pair with XNA's member set, so the projection uses
composition -- the same choice ``ContentReader`` already makes for
``BinaryReader`` -- and adds the base-class members XNA inherits.

The XNA types the two carry -- ``Vector2``, ``Vector3``, ``Vector4``, ``Matrix``,
``Quaternion`` and ``Color`` -- are read and written by CNA, so the wire layout
is CNA's rather than a second one written down here.
"""

from __future__ import annotations

import ctypes as c

from .. import Color, Matrix, Quaternion, Vector2, Vector3, Vector4
from _cna_native import abi as _abi
from _cna_native import online_support as _on
from _cna_native.family_support import checked

__all__ = ["PacketReader", "PacketWriter"]

_support = _on.support


def _vector2(value) -> Vector2:
    return Vector2(float(value.x), float(value.y))


def _vector3(value) -> Vector3:
    return Vector3(float(value.x), float(value.y), float(value.z))


def _vector4(value) -> Vector4:
    return Vector4(float(value.x), float(value.y), float(value.z), float(value.w))


def _matrix(value) -> Matrix:
    return Matrix(*(float(getattr(value, f"m{row}{column}"))
                    for row in range(1, 5) for column in range(1, 5)))


class _Packet:
    """What the reader and the writer share: a handle, a length and a position.

    XNA derives ``PacketReader`` from ``BinaryReader`` and ``PacketWriter`` from
    ``BinaryWriter``. Python has no compatible pair, so the two are projected by
    composition -- the relation the mapping rules record and the verifier checks
    -- exactly as ``ContentReader`` already is.

    The byte-level members XNA inherits from those bases are **not projected**:
    CNA's packet routes cover the typed XNA values and have no byte-level read
    or write. That is a measured upstream gap rather than an omission, so the
    inherited names raise an error naming the missing route instead of being
    absent.
    """

    __slots__ = ("_handle", "_disposed")
    _destroy = ""
    _prefix = ""
    #: What CNA has no route for, and therefore what this cannot do.
    _INHERITED = ()

    def _unsupported(self, name: str):
        return NotImplementedError(
            f"{type(self).__name__}.{name} is inherited from "
            f"{'BinaryReader' if self._prefix.endswith('reader') else 'BinaryWriter'}"
            f", and CNA's {self._prefix}_* routes carry only the typed XNA values: "
            "there is no byte-level route to project it onto")

    def __init__(self, capacity: int = 0) -> None:
        self._handle = _support.out_handle(
            f"{self._prefix}_create",
            c.c_int32(checked(capacity, "int32", "capacity")))
        self._disposed = False

    @property
    def _value(self) -> c.c_uint64:
        if self._disposed or not self._handle:
            raise RuntimeError(f"{type(self).__name__} has been disposed")
        return c.c_uint64(self._handle)

    @property
    def Length(self) -> int:
        return _support.out_i32(f"{self._prefix}_get_length", self._value)

    @property
    def Position(self) -> int:
        return _support.out_i32(f"{self._prefix}_get_position", self._value)

    @Position.setter
    def Position(self, value: int) -> None:
        _support.call(f"{self._prefix}_set_position", self._value,
                      c.c_int32(checked(value, "int32", "Position")))

    def Close(self) -> None:
        """Releases the packet. XNA inherits this from its stream base."""
        self.Dispose()

    def Dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._handle:
            _support.call(self._destroy, c.c_uint64(self._handle))
        self._handle = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


class _BinaryReader(_Packet):
    """The composition base ``PacketReader`` stands in for ``BinaryReader`` with."""

    __slots__ = ()

    def ReadByte(self) -> int:
        raise self._unsupported("ReadByte")

    def ReadBytes(self, count: int) -> bytes:
        raise self._unsupported("ReadBytes")

    def ReadBoolean(self) -> bool:
        raise self._unsupported("ReadBoolean")

    def ReadInt16(self) -> int:
        raise self._unsupported("ReadInt16")

    def ReadInt32(self) -> int:
        raise self._unsupported("ReadInt32")

    def ReadInt64(self) -> int:
        raise self._unsupported("ReadInt64")

    def ReadString(self) -> str:
        raise self._unsupported("ReadString")


class _BinaryWriter(_Packet):
    """The composition base ``PacketWriter`` stands in for ``BinaryWriter`` with."""

    __slots__ = ()

    def Flush(self) -> None:
        raise self._unsupported("Flush")

    def Seek(self, offset: int, origin: object) -> int:
        raise self._unsupported("Seek")


class PacketReader(_BinaryReader):
    """Reads the typed values a packet carries."""

    __slots__ = ()
    _prefix = "cna_packet_reader"
    _destroy = "cna_packet_reader_destroy"

    def _read(self, route: str, structure, convert):
        value = structure()
        _support.call(route, self._value, c.byref(value))
        return convert(value)

    def ReadSingle(self) -> float:
        return _support.out_f32("cna_packet_reader_read_single", self._value)

    def ReadDouble(self) -> float:
        return _support.out_f64("cna_packet_reader_read_double", self._value)

    def ReadVector2(self) -> Vector2:
        return self._read("cna_packet_reader_read_vector2", _abi.CNA_Vector2, _vector2)

    def ReadVector3(self) -> Vector3:
        return self._read("cna_packet_reader_read_vector3", _abi.CNA_Vector3, _vector3)

    def ReadVector4(self) -> Vector4:
        return self._read("cna_packet_reader_read_vector4", _abi.CNA_Vector4, _vector4)

    def ReadMatrix(self) -> Matrix:
        return self._read("cna_packet_reader_read_matrix", _abi.CNA_Matrix, _matrix)

    def ReadQuaternion(self) -> Quaternion:
        return self._read(
            "cna_packet_reader_read_quaternion", _abi.CNA_Quaternion,
            lambda value: Quaternion(float(value.x), float(value.y),
                                     float(value.z), float(value.w)))

    def ReadColor(self) -> Color:
        return self._read(
            "cna_packet_reader_read_color", _abi.CNA_Color,
            lambda value: Color(int(value.r), int(value.g), int(value.b),
                                int(value.a)))

    def _set_data(self, data: bytes) -> None:
        """Fills the reader with bytes, as receiving into it would.

        The position is rewound afterwards, which states the contract a caller
        depends on rather than inheriting it: a reader handed fresh bytes reads
        the first value, not whatever follows where the last read stopped.

        CNA rewinds too -- measured on both paths, ``set_data`` and a session
        receive, on a reader that had already been drained -- so the assignment
        is redundant against this build and not against the contract. The
        qualification asserts the position itself on both paths, so if either
        side stops rewinding the tests say which one.
        """
        payload = bytes(data)
        buffer = (c.c_uint8 * len(payload))(*payload) if payload else None
        _support.call("cna_packet_reader_set_data_ext", self._value, buffer,
                      c.c_uint64(len(payload)))
        self.Position = 0


class PacketWriter(_BinaryWriter):
    """Writes the typed values a packet will carry."""

    __slots__ = ()
    _prefix = "cna_packet_writer"
    _destroy = "cna_packet_writer_destroy"

    def Write(self, value: object) -> None:
        """XNA's eight ``Write`` overloads, dispatched on the value's type.

        ``bool`` is refused: Python's ``bool`` is an ``int``, and XNA's
        ``Write(float)`` and ``Write(double)`` are already two overloads one
        Python float cannot tell apart -- silently writing ``True`` as a number
        would be a third surprise.
        """
        if isinstance(value, bool):
            raise TypeError("a packet value may not be a bool")
        if isinstance(value, Vector2):
            native = _abi.CNA_Vector2()
            native.x, native.y = float(value.X), float(value.Y)
            _support.call("cna_packet_writer_write_vector2", self._value, native)
        elif isinstance(value, Vector3):
            native = _abi.CNA_Vector3()
            native.x, native.y, native.z = (float(value.X), float(value.Y),
                                            float(value.Z))
            _support.call("cna_packet_writer_write_vector3", self._value, native)
        elif isinstance(value, Vector4):
            native = _abi.CNA_Vector4()
            native.x, native.y = float(value.X), float(value.Y)
            native.z, native.w = float(value.Z), float(value.W)
            _support.call("cna_packet_writer_write_vector4", self._value, native)
        elif isinstance(value, Matrix):
            native = _abi.CNA_Matrix()
            for row in range(1, 5):
                for column in range(1, 5):
                    setattr(native, f"m{row}{column}",
                            float(getattr(value, f"M{row}{column}")))
            _support.call("cna_packet_writer_write_matrix", self._value, native)
        elif isinstance(value, Quaternion):
            native = _abi.CNA_Quaternion()
            native.x, native.y = float(value.X), float(value.Y)
            native.z, native.w = float(value.Z), float(value.W)
            _support.call("cna_packet_writer_write_quaternion", self._value, native)
        elif isinstance(value, Color):
            native = _abi.CNA_Color()
            native.r, native.g = int(value.R), int(value.G)
            native.b, native.a = int(value.B), int(value.A)
            _support.call("cna_packet_writer_write_color", self._value, native)
        elif isinstance(value, (int, float)):
            _support.call("cna_packet_writer_write_double", self._value,
                          c.c_double(float(value)))
        else:
            raise TypeError(f"a packet value may not be a {type(value).__name__}")

    def _write_single(self, value: float) -> None:
        """XNA's ``Write(float)``, which Python's one floating type cannot select.

        A LANGUAGE_MAPPING_LIMITATION: ``Write`` takes the wider of the two
        overloads. XNA's public surface has no separate name for the narrower
        one, so neither does this -- it is private, and the qualification uses it
        to prove the narrow route works.
        """
        _support.call("cna_packet_writer_write_single", self._value,
                      c.c_float(float(value)))

    def _data(self) -> bytes:
        """Everything written so far, as it would go on the wire.

        Sized from :attr:`Length` rather than by a zero-capacity probe: unlike
        the text copy routes, CNA's packet copy refuses a destination smaller
        than the packet instead of reporting the size it needs. The writer
        already knows its own length, so there is nothing to ask for.
        """
        size = self.Length
        if size <= 0:
            return b""
        buffer = (c.c_uint8 * size)()
        written = c.c_uint64()
        _support.call("cna_packet_writer_copy_data_ext", self._value, buffer,
                      c.c_uint64(size), c.byref(written))
        return bytes(bytearray(buffer[: int(written.value)]))


PacketReader.__xna_arities__ = {"__init__": {0, 1}}
PacketWriter.__xna_arities__ = {"__init__": {0, 1}, "Write": {1}}
