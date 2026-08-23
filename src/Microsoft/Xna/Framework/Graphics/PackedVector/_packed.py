"""Bit-exact managed XNA 4.0 packed-vector values."""

from __future__ import annotations

import math
import struct
from typing import Generic, TypeVar

from ... import Vector2, Vector3, Vector4
from ..._numeric import div32, f32, uint8, uint16, uint32, uint64, wrap_int32


TPacked = TypeVar("TPacked")


def _round_ties_even(value: float) -> int:
    return int(round(value))


def _clamp_and_round(value: object, minimum: float, maximum: float) -> int:
    number = f32(value)
    if math.isnan(number):
        return 0
    if number <= minimum:
        return int(minimum)
    if number >= maximum:
        return int(maximum)
    return _round_ties_even(number)


def _pack_unsigned(mask: int, value: object) -> int:
    return _clamp_and_round(value, 0.0, float(mask))


def _pack_signed(mask: int, value: object) -> int:
    maximum = mask >> 1
    return _clamp_and_round(value, float(-maximum - 1), float(maximum)) & mask


def _pack_unorm(mask: int, value: object) -> int:
    scaled = f32(f32(value) * f32(mask))
    return _clamp_and_round(scaled, 0.0, float(mask))


def _unpack_unorm(mask: int, value: int) -> float:
    return div32(value & mask, mask)


def _pack_snorm(mask: int, value: object) -> int:
    maximum = mask >> 1
    scaled = f32(f32(value) * f32(maximum))
    return _clamp_and_round(scaled, float(-maximum), float(maximum)) & mask


def _unpack_snorm(mask: int, value: int) -> float:
    sign_bit = (mask + 1) >> 1
    lane = value & mask
    if lane & sign_bit:
        if lane == sign_bit:
            return f32(-1.0)
        lane -= mask + 1
    return div32(lane, mask >> 1)


def _pack_half(value: object) -> int:
    """XNA's historical half conversion (exponent 31 is finite, not IEEE infinity)."""

    bits = struct.unpack("=I", struct.pack("=f", f32(value)))[0]
    sign = (bits & 0x80000000) >> 16
    magnitude = bits & 0x7FFFFFFF
    if magnitude > 1_207_955_455:
        return sign | 0x7FFF
    if magnitude < 947_912_704:
        mantissa = (magnitude & 0x007FFFFF) | 0x00800000
        shift = 113 - (magnitude >> 23)
        magnitude = mantissa >> shift if shift <= 31 else 0
        return sign | ((magnitude + 4095 + ((magnitude >> 13) & 1)) >> 13)
    return sign | ((magnitude - 939_524_096 + 4095 + ((magnitude >> 13) & 1)) >> 13)


def _unpack_half(value: int) -> float:
    if value & 0x7C00 == 0:
        mantissa = value & 0x03FF
        if mantissa == 0:
            bits = (value & 0x8000) << 16
        else:
            exponent = -14
            while mantissa & 0x0400 == 0:
                exponent -= 1
                mantissa <<= 1
            mantissa &= ~0x0400
            bits = ((value & 0x8000) << 16) | ((exponent + 127) << 23) | (mantissa << 13)
    else:
        bits = ((value & 0x8000) << 16) | ((((value >> 10) & 0x1F) - 15 + 127) << 23) | ((value & 0x03FF) << 13)
    return struct.unpack("=f", struct.pack("=I", bits))[0]


def _signed16(value: int) -> int:
    value &= 0xFFFF
    return value if value < 0x8000 else value - 0x10000


class IPackedVector:
    def ToVector4(self) -> Vector4:
        return self._to_vector4()

    def PackFromVector4(self, vector: Vector4) -> None:
        if not isinstance(vector, Vector4):
            raise TypeError("vector must be Vector4")
        self._pack_vector4(vector)


class IPackedVectorOfT(IPackedVector, Generic[TPacked]):
    @property
    def PackedValue(self) -> TPacked:
        raise NotImplementedError

    @PackedValue.setter
    def PackedValue(self, value: TPacked) -> None:
        raise NotImplementedError


class _PackedValue:
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8

    @property
    def PackedValue(self) -> int:
        return self._packed_value

    @PackedValue.setter
    def PackedValue(self, value: int) -> None:
        self._packed_value = self._packed_validator(value, name="PackedValue")

    def ToString(self) -> str:
        return f"{self.PackedValue:0{self._hex_digits}X}"

    def GetHashCode(self) -> int:
        value = self.PackedValue
        if self._hex_digits == 16:
            return wrap_int32((value & 0xFFFFFFFF) ^ (value >> 32))
        return wrap_int32(value)

    def Equals(self, other: object) -> bool:
        return type(other) is type(self) and self.PackedValue == other.PackedValue

    def __eq__(self, other: object) -> bool:
        return self.Equals(other)

    def __ne__(self, other: object) -> bool:
        return not self.Equals(other)

    def __hash__(self) -> int:
        return self.GetHashCode()

    def __copy__(self):
        result = type(self)()
        result.PackedValue = self.PackedValue
        return result

    def __deepcopy__(self, memo: object):
        return self.__copy__()

    def __str__(self) -> str:
        return self.ToString()

    def __repr__(self) -> str:
        return f"{type(self).__name__}._from_packed({self.PackedValue})"


def _packed_value(cls):
    for name in (
        "PackedValue", "ToString", "GetHashCode", "Equals", "__eq__", "__ne__",
        "__hash__", "__copy__", "__deepcopy__", "__str__", "__repr__",
    ):
        setattr(cls, name, _PackedValue.__dict__[name])
    return cls


def _vector2_args(name: str, args: tuple[object, ...]) -> tuple[float, float]:
    if len(args) == 1 and isinstance(args[0], Vector2):
        return args[0].X, args[0].Y
    if len(args) == 2:
        return f32(args[0]), f32(args[1])
    raise TypeError(f"{name} expects (), Vector2, or x, y")


def _vector4_args(name: str, args: tuple[object, ...]) -> tuple[float, float, float, float]:
    if len(args) == 1 and isinstance(args[0], Vector4):
        return args[0].X, args[0].Y, args[0].Z, args[0].W
    if len(args) == 4:
        return tuple(f32(value) for value in args)  # type: ignore[return-value]
    raise TypeError(f"{name} expects (), Vector4, or x, y, z, w")


@_packed_value
class Alpha8(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint8)
    _hex_digits = 2

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
        elif len(args) == 1:
            self._packed_value = _pack_unorm(0xFF, args[0])
        else:
            raise TypeError("Alpha8 expects () or alpha")

    def ToAlpha(self) -> float:
        return _unpack_unorm(0xFF, self.PackedValue)

    def _to_vector4(self) -> Vector4:
        return Vector4(0.0, 0.0, 0.0, self.ToAlpha())

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = _pack_unorm(0xFF, vector.W)


@_packed_value
class Bgr565(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint16)
    _hex_digits = 4

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        if len(args) == 1 and isinstance(args[0], Vector3):
            x, y, z = args[0]
        elif len(args) == 3:
            x, y, z = args
        else:
            raise TypeError("Bgr565 expects (), Vector3, or x, y, z")
        self._packed_value = (_pack_unorm(31, x) << 11) | (_pack_unorm(63, y) << 5) | _pack_unorm(31, z)

    def ToVector3(self) -> Vector3:
        value = self.PackedValue
        return Vector3(_unpack_unorm(31, value >> 11), _unpack_unorm(63, value >> 5), _unpack_unorm(31, value))

    def _to_vector4(self) -> Vector4:
        value = self.ToVector3()
        return Vector4(value.X, value.Y, value.Z, 1.0)

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector.X, vector.Y, vector.Z).PackedValue


class _UNorm16Four(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint16)
    _hex_digits = 4
    _masks: tuple[int, int, int, int]
    _shifts: tuple[int, int, int, int]

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        values = _vector4_args(type(self).__name__, args)
        self._packed_value = sum(_pack_unorm(mask, value) << shift for mask, shift, value in zip(self._masks, self._shifts, values))

    def ToVector4(self) -> Vector4:
        value = self.PackedValue
        return Vector4(*(_unpack_unorm(mask, value >> shift) for mask, shift in zip(self._masks, self._shifts)))

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector).PackedValue


@_packed_value
class Bgra4444(_UNorm16Four):
    _masks = (15, 15, 15, 15)
    _shifts = (8, 4, 0, 12)


@_packed_value
class Bgra5551(_UNorm16Four):
    _masks = (31, 31, 31, 1)
    _shifts = (10, 5, 0, 15)


@_packed_value
class Byte4(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        values = _vector4_args(type(self).__name__, args)
        self._packed_value = sum(_pack_unsigned(255, value) << (index * 8) for index, value in enumerate(values))

    def ToVector4(self) -> Vector4:
        value = self.PackedValue
        return Vector4(*(f32((value >> (index * 8)) & 0xFF) for index in range(4)))

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector).PackedValue


@_packed_value
class HalfSingle(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint16)
    _hex_digits = 4

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
        elif len(args) == 1:
            self._packed_value = _pack_half(args[0])
        else:
            raise TypeError("HalfSingle expects () or value")

    def ToSingle(self) -> float:
        return _unpack_half(self.PackedValue)

    def _to_vector4(self) -> Vector4:
        return Vector4(self.ToSingle(), 0.0, 0.0, 1.0)

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = _pack_half(vector.X)


@_packed_value
class HalfVector2(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        x, y = _vector2_args(type(self).__name__, args)
        self._packed_value = _pack_half(x) | (_pack_half(y) << 16)

    def ToVector2(self) -> Vector2:
        return Vector2(_unpack_half(self.PackedValue), _unpack_half(self.PackedValue >> 16))

    def _to_vector4(self) -> Vector4:
        value = self.ToVector2()
        return Vector4(value.X, value.Y, 0.0, 1.0)

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector.X, vector.Y).PackedValue


@_packed_value
class HalfVector4(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint64)
    _hex_digits = 16

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        values = _vector4_args(type(self).__name__, args)
        self._packed_value = sum(_pack_half(value) << (index * 16) for index, value in enumerate(values))

    def ToVector4(self) -> Vector4:
        return Vector4(*(_unpack_half(self.PackedValue >> (index * 16)) for index in range(4)))

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector).PackedValue


class _PackedTwo(IPackedVectorOfT[int]):
    _lane_bits = 16
    _mask = 0xFFFF
    _pack = staticmethod(_pack_snorm)
    _unpack = staticmethod(_unpack_snorm)

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        x, y = _vector2_args(type(self).__name__, args)
        self._packed_value = self._pack(self._mask, x) | (self._pack(self._mask, y) << self._lane_bits)

    def ToVector2(self) -> Vector2:
        return Vector2(self._unpack(self._mask, self.PackedValue), self._unpack(self._mask, self.PackedValue >> self._lane_bits))

    def _to_vector4(self) -> Vector4:
        value = self.ToVector2()
        return Vector4(value.X, value.Y, 0.0, 1.0)

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector.X, vector.Y).PackedValue


@_packed_value
class NormalizedByte2(_PackedTwo):
    _packed_validator = staticmethod(uint16)
    _hex_digits = 4
    _lane_bits = 8
    _mask = 0xFF


@_packed_value
class NormalizedShort2(_PackedTwo):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8


@_packed_value
class Rg32(_PackedTwo):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8
    _pack = staticmethod(_pack_unorm)
    _unpack = staticmethod(_unpack_unorm)


class _PackedFour(IPackedVectorOfT[int]):
    _lane_bits = 8
    _mask = 0xFF
    _pack = staticmethod(_pack_snorm)
    _unpack = staticmethod(_unpack_snorm)

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        values = _vector4_args(type(self).__name__, args)
        self._packed_value = sum(self._pack(self._mask, value) << (index * self._lane_bits) for index, value in enumerate(values))

    def ToVector4(self) -> Vector4:
        return Vector4(*(self._unpack(self._mask, self.PackedValue >> (index * self._lane_bits)) for index in range(4)))

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector).PackedValue


@_packed_value
class NormalizedByte4(_PackedFour):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8


@_packed_value
class NormalizedShort4(_PackedFour):
    _packed_validator = staticmethod(uint64)
    _hex_digits = 16
    _lane_bits = 16
    _mask = 0xFFFF


@_packed_value
class Rgba64(_PackedFour):
    _packed_validator = staticmethod(uint64)
    _hex_digits = 16
    _lane_bits = 16
    _mask = 0xFFFF
    _pack = staticmethod(_pack_unorm)
    _unpack = staticmethod(_unpack_unorm)


@_packed_value
class Rgba1010102(IPackedVectorOfT[int]):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        x, y, z, w = _vector4_args(type(self).__name__, args)
        self._packed_value = _pack_unorm(1023, x) | (_pack_unorm(1023, y) << 10) | (_pack_unorm(1023, z) << 20) | (_pack_unorm(3, w) << 30)

    def ToVector4(self) -> Vector4:
        value = self.PackedValue
        return Vector4(_unpack_unorm(1023, value), _unpack_unorm(1023, value >> 10), _unpack_unorm(1023, value >> 20), _unpack_unorm(3, value >> 30))

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()

    def _pack_vector4(self, vector: Vector4) -> None:
        self._packed_value = type(self)(vector).PackedValue


class _ShortBase(IPackedVectorOfT[int]):
    _lane_count = 2

    def __init__(self, *args: object) -> None:
        if not args:
            self._packed_value = 0
            return
        values = _vector2_args(type(self).__name__, args) if self._lane_count == 2 else _vector4_args(type(self).__name__, args)
        self._packed_value = sum(_pack_signed(0xFFFF, value) << (index * 16) for index, value in enumerate(values))

    def _values(self) -> tuple[float, ...]:
        return tuple(f32(_signed16(self.PackedValue >> (index * 16))) for index in range(self._lane_count))

    def _pack_vector4(self, vector: Vector4) -> None:
        values = (vector.X, vector.Y) if self._lane_count == 2 else (vector.X, vector.Y, vector.Z, vector.W)
        self._packed_value = type(self)(*values).PackedValue


@_packed_value
class Short2(_ShortBase):
    _packed_validator = staticmethod(uint32)
    _hex_digits = 8

    def ToVector2(self) -> Vector2:
        return Vector2(*self._values())

    def _to_vector4(self) -> Vector4:
        value = self.ToVector2()
        return Vector4(value.X, value.Y, 0.0, 1.0)


@_packed_value
class Short4(_ShortBase):
    _packed_validator = staticmethod(uint64)
    _hex_digits = 16
    _lane_count = 4

    def ToVector4(self) -> Vector4:
        return Vector4(*self._values())

    def _to_vector4(self) -> Vector4:
        return self.ToVector4()


for _type, _arities in {
    IPackedVector: {"ToVector4": {0}, "PackFromVector4": {1}},
    Alpha8: {"__init__": {0, 1}, "ToAlpha": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    Bgr565: {"__init__": {0, 1, 3}, "ToVector3": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    HalfSingle: {"__init__": {0, 1}, "ToSingle": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    HalfVector2: {"__init__": {0, 1, 2}, "ToVector2": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    NormalizedByte2: {"__init__": {0, 1, 2}, "ToVector2": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    NormalizedShort2: {"__init__": {0, 1, 2}, "ToVector2": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    Rg32: {"__init__": {0, 1, 2}, "ToVector2": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
    Short2: {"__init__": {0, 1, 2}, "ToVector2": {0}, "ToString": {0}, "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1}},
}.items():
    _type.__xna_arities__ = _arities

for _type in (Bgra4444, Bgra5551, Byte4, HalfVector4, NormalizedByte4, NormalizedShort4, Rgba1010102, Rgba64, Short4):
    _type.__xna_arities__ = {
        "__init__": {0, 1, 4}, "ToVector4": {0}, "ToString": {0},
        "GetHashCode": {0}, "Equals": {1}, "__eq__": {1}, "__ne__": {1},
    }

IPackedVectorOfT.__xna_arities__ = {}
