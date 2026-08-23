"""Private, explicit ctypes codecs for XNA Effect reflection values."""

from __future__ import annotations

import ctypes as c
from collections.abc import Sequence

from _cna_native import abi
from _cna_native.loader import get_library

from .._math import Matrix, Quaternion, Vector2, Vector3, Vector4
from .._numeric import f32, int32


BOOLEAN = 0
INT32 = 1
SINGLE = 2
MATRIX = 3
MATRIX_TRANSPOSE = 4
QUATERNION = 5
VECTOR2 = 6
VECTOR3 = 7
VECTOR4 = 8

TEXTURE_BASE = 0
TEXTURE_2D = 1
TEXTURE_3D = 2
TEXTURE_CUBE = 3


def _matrix_to_native(value: Matrix) -> abi.CNA_Matrix:
    return abi.CNA_Matrix(*tuple(value))


def _matrix_from_native(value: abi.CNA_Matrix) -> Matrix:
    return Matrix(*(getattr(value, f"m{row}{column}")
                    for row in range(1, 5) for column in range(1, 5)))


_CODECS = {
    BOOLEAN: (c.c_uint8, lambda value: c.c_uint8(bool(value)), lambda value: bool(getattr(value,"value",value))),
    INT32: (c.c_int32, lambda value: c.c_int32(int32(value)), lambda value: int(getattr(value,"value",value))),
    SINGLE: (c.c_float, lambda value: c.c_float(f32(value)), lambda value: float(getattr(value,"value",value))),
    MATRIX: (abi.CNA_Matrix, _matrix_to_native, _matrix_from_native),
    MATRIX_TRANSPOSE: (abi.CNA_Matrix, _matrix_to_native, _matrix_from_native),
    QUATERNION: (abi.CNA_Quaternion, lambda value: abi.CNA_Quaternion(*tuple(value)),
                 lambda value: Quaternion(value.x, value.y, value.z, value.w)),
    VECTOR2: (abi.CNA_Vector2, lambda value: abi.CNA_Vector2(*tuple(value)),
              lambda value: Vector2(value.x, value.y)),
    VECTOR3: (abi.CNA_Vector3, lambda value: abi.CNA_Vector3(*tuple(value)),
              lambda value: Vector3(value.x, value.y, value.z)),
    VECTOR4: (abi.CNA_Vector4, lambda value: abi.CNA_Vector4(*tuple(value)),
              lambda value: Vector4(value.x, value.y, value.z, value.w)),
}


def copy_utf8(handle: int, size_operation: str, copy_operation: str) -> str:
    library = get_library()
    count = c.c_uint64()
    library.check(getattr(library, size_operation)(handle, c.byref(count)), size_operation)
    if count.value == 0:
        return ""
    buffer = c.create_string_buffer(count.value)
    written = c.c_uint64()
    library.check(getattr(library, copy_operation)(
        handle, buffer, count.value, c.byref(written)), copy_operation)
    return bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")


def get_parameter_value(handle: int, value_type: int):
    ctype, _, decode = _CODECS[value_type]
    value = ctype()
    library = get_library()
    library.check(library.cna_effect_parameter_get_value(
        handle, value_type, c.cast(c.byref(value), c.c_void_p)),
        "cna_effect_parameter_get_value")
    return decode(value)


def get_parameter_values(handle: int, value_type: int, count: int) -> list[object]:
    count = int32(count, name="count")
    if count < 0:
        raise ValueError("count cannot be negative")
    ctype, _, decode = _CODECS[value_type]
    values = (ctype * count)()
    actual = c.c_uint64()
    destination = None if count == 0 else c.cast(values, c.c_void_p)
    library = get_library()
    library.check(library.cna_effect_parameter_get_values(
        handle, value_type, count, destination, count, c.byref(actual)),
        "cna_effect_parameter_get_values")
    return [decode(values[index]) for index in range(actual.value)]


def set_parameter_value(handle: int, value_type: int, value: object) -> None:
    _, encode, _ = _CODECS[value_type]
    native = encode(value)
    library = get_library()
    library.check(library.cna_effect_parameter_set_value(
        handle, value_type, c.cast(c.byref(native), c.c_void_p)),
        "cna_effect_parameter_set_value")


def set_parameter_values(handle: int, value_type: int, values: Sequence[object]) -> None:
    ctype, encode, _ = _CODECS[value_type]
    native = (ctype * len(values))(*(encode(value) for value in values))
    pointer = None if not values else c.cast(native, c.c_void_p)
    library = get_library()
    library.check(library.cna_effect_parameter_set_values(
        handle, value_type, pointer, len(values)), "cna_effect_parameter_set_values")


def set_parameter_string(handle: int, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("value must be str")
    encoded = value.encode("utf-8", errors="strict")
    library = get_library()
    library.check(library.cna_effect_parameter_set_value_string(
        handle, abi.CNA_StringView(encoded, len(encoded))),
        "cna_effect_parameter_set_value_string")


def get_parameter_string(handle: int) -> str:
    return copy_utf8(handle, "cna_effect_parameter_get_value_string_byte_count",
                     "cna_effect_parameter_copy_value_string")


def dispatch_value(value: object, *, transpose: bool = False) -> tuple[str, int | None, object]:
    """Return ``(kind, native_tag, copied_value)`` for one XNA SetValue overload."""
    from ._resources import Texture

    if isinstance(value, Texture):
        return "texture", None, value
    if isinstance(value, str):
        return "string", None, value
    scalar = _scalar_tag(value, transpose=transpose)
    if scalar is not None:
        return "scalar", scalar, value
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray, memoryview)):
        raise TypeError("no matching EffectParameter.SetValue overload")
    copied = list(value)
    if not copied:
        raise ValueError("an empty sequence has no deterministic XNA SetValue overload")
    tag = _scalar_tag(copied[0], transpose=transpose)
    if tag is None or any(_scalar_tag(item, transpose=transpose) != tag for item in copied):
        raise TypeError("EffectParameter arrays must contain one exact supported value type")
    return "array", tag, copied


def _scalar_tag(value: object, *, transpose: bool) -> int | None:
    if type(value) is bool:
        return BOOLEAN
    if type(value) is int:
        return INT32
    if type(value) is float:
        return SINGLE
    if isinstance(value, Matrix):
        return MATRIX_TRANSPOSE if transpose else MATRIX
    if isinstance(value, Quaternion):
        return QUATERNION
    if isinstance(value, Vector2):
        return VECTOR2
    if isinstance(value, Vector3):
        return VECTOR3
    if isinstance(value, Vector4):
        return VECTOR4
    return None


def annotation_scalar(handle: int, suffix: str, ctype, decode=lambda value: value):
    value = ctype()
    operation = f"cna_effect_annotation_get_value_{suffix}"
    library = get_library()
    library.check(getattr(library, operation)(handle, c.byref(value)), operation)
    return decode(value)


def annotation_string(handle: int) -> str:
    return copy_utf8(handle, "cna_effect_annotation_get_value_string_byte_count",
                     "cna_effect_annotation_copy_value_string")


def annotation_vector(handle: int, suffix: str, ctype, decode):
    return annotation_scalar(handle, suffix, ctype, decode)


def annotation_matrix(handle: int) -> Matrix:
    return annotation_scalar(handle, "matrix", abi.CNA_Matrix, _matrix_from_native)
