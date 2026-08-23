"""Fixed-width numeric operations used by Single/Int32 XNA values."""

from __future__ import annotations

import math
import struct


def f32(value: object) -> float:
    """Narrow to IEEE-754 binary32 using round-to-nearest, ties-to-even."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Single values must be int or float, not bool or a coercible object")
    number = float(value)
    try:
        return struct.unpack("=f", struct.pack("=f", number))[0]
    except OverflowError:
        return math.copysign(math.inf, number)


def add32(left: object, right: object) -> float:
    return f32(f32(left) + f32(right))


def sub32(left: object, right: object) -> float:
    return f32(f32(left) - f32(right))


def mul32(left: object, right: object) -> float:
    return f32(f32(left) * f32(right))


def div32(left: object, right: object) -> float:
    a, b = f32(left), f32(right)
    if math.isnan(a) or math.isnan(b):
        return math.nan
    if b == 0.0:
        if a == 0.0:
            return math.nan
        return math.copysign(math.inf, a * b if b != 0.0 else a * math.copysign(1.0, b))
    return f32(a / b)


def int32(value: object, *, name: str = "value") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an Int32")
    if value < -2_147_483_648 or value > 2_147_483_647:
        raise OverflowError(f"{name} is outside the Int32 range")
    return value


def uint32(value: object, *, name: str = "value") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a UInt32")
    if value < 0 or value > 4_294_967_295:
        raise OverflowError(f"{name} is outside the UInt32 range")
    return value


def wrap_int32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def single_hash(value: object) -> int:
    """Reproduce .NET Framework ``System.Single.GetHashCode``."""

    bits = struct.unpack("=I", struct.pack("=f", f32(value)))[0]
    if ((bits - 1) & 0x7FFFFFFF) >= 0x7F800000:
        bits &= 0x7F800000
    return wrap_int32(bits)


def hash32_sum(*values: int) -> int:
    result = 0
    for value in values:
        result = wrap_int32(result + value)
    return result
