"""The one table that says what a pixel type *is*.

A bitmap's element type decides three separate things: which ``SurfaceFormat``
the built texture claims, how many bytes one pixel occupies, and how a pixel is
turned into those bytes. XNA scatters that across ``VectorConverter``,
``BitmapContent.TryGetFormat`` and each ``PixelBitmapContent<T>``; keeping it in
one table is what makes the three agree by construction.

``VectorConverter`` is the public half. Everything else here is what the bitmap
and vertex code reads.
"""

from __future__ import annotations

import struct
from typing import Callable, NamedTuple

from .... import Color, Vector2, Vector3, Vector4
from ....Graphics import SurfaceFormat, VertexElementFormat
from ....Graphics.PackedVector import (
    Alpha8, Bgr565, Bgra4444, Bgra5551, Byte4, HalfSingle, HalfVector2,
    HalfVector4, NormalizedByte2, NormalizedByte4, NormalizedShort2,
    NormalizedShort4, Rg32, Rgba1010102, Rgba64, Short2, Short4,
)


class PixelKind(NamedTuple):
    """Everything the pipeline needs to know about one pixel type."""

    #: The surface format a texture of these pixels claims.
    surface: SurfaceFormat | None
    #: Bytes one pixel occupies on the wire.
    size: int
    #: Packs one pixel into little-endian bytes.
    pack: Callable[[object], bytes]
    #: Rebuilds one pixel from those bytes.
    unpack: Callable[[bytes], object]


def _packed(kind: type, width: int, surface: SurfaceFormat | None) -> PixelKind:
    """A packed vector: its ``PackedValue`` is the wire form, little-endian."""
    code = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}[width]

    def pack(value: object) -> bytes:
        return struct.pack(code, value.PackedValue)

    def unpack(raw: bytes) -> object:
        # Built through the public ``PackedValue`` setter rather than by
        # assigning a private field, so the type's own range check runs and a
        # packed vector rebuilt from bytes is indistinguishable from one a
        # caller constructed.
        result = kind.__new__(kind)
        result.PackedValue = struct.unpack(code, raw)[0]
        return result

    return PixelKind(surface, width, pack, unpack)


def _color() -> PixelKind:
    def pack(value: Color) -> bytes:
        return bytes((value.R, value.G, value.B, value.A))

    def unpack(raw: bytes) -> Color:
        return Color(raw[0], raw[1], raw[2], raw[3])

    return PixelKind(SurfaceFormat.Color, 4, pack, unpack)


def _single() -> PixelKind:
    return PixelKind(SurfaceFormat.Single, 4,
                     lambda value: struct.pack("<f", float(value)),
                     lambda raw: struct.unpack("<f", raw)[0])


def _vector2() -> PixelKind:
    return PixelKind(SurfaceFormat.Vector2, 8,
                     lambda value: struct.pack("<2f", value.X, value.Y),
                     lambda raw: Vector2(*struct.unpack("<2f", raw)))


def _vector3() -> PixelKind:
    return PixelKind(None, 12,
                     lambda value: struct.pack("<3f", value.X, value.Y, value.Z),
                     lambda raw: Vector3(*struct.unpack("<3f", raw)))


def _vector4() -> PixelKind:
    return PixelKind(SurfaceFormat.Vector4, 16,
                     lambda value: struct.pack("<4f", value.X, value.Y, value.Z,
                                               value.W),
                     lambda raw: Vector4(*struct.unpack("<4f", raw)))


#: Every pixel type XNA's ``VectorConverter`` knows, and what it is.
#:
#: ``Vector3`` is deliberately present with no surface format: it is a valid
#: *vertex* element and not a valid texture format, and the two questions are
#: answered from the same row so neither can drift.
PIXEL_KINDS: dict[type, PixelKind] = {
    Color: _color(),
    Bgr565: _packed(Bgr565, 2, SurfaceFormat.Bgr565),
    Bgra5551: _packed(Bgra5551, 2, SurfaceFormat.Bgra5551),
    Bgra4444: _packed(Bgra4444, 2, SurfaceFormat.Bgra4444),
    NormalizedByte2: _packed(NormalizedByte2, 2, SurfaceFormat.NormalizedByte2),
    NormalizedByte4: _packed(NormalizedByte4, 4, SurfaceFormat.NormalizedByte4),
    Rgba1010102: _packed(Rgba1010102, 4, SurfaceFormat.Rgba1010102),
    Rg32: _packed(Rg32, 4, SurfaceFormat.Rg32),
    Rgba64: _packed(Rgba64, 8, SurfaceFormat.Rgba64),
    Alpha8: _packed(Alpha8, 1, SurfaceFormat.Alpha8),
    HalfSingle: _packed(HalfSingle, 2, SurfaceFormat.HalfSingle),
    HalfVector2: _packed(HalfVector2, 4, SurfaceFormat.HalfVector2),
    HalfVector4: _packed(HalfVector4, 8, SurfaceFormat.HalfVector4),
    Byte4: _packed(Byte4, 4, None),
    Short2: _packed(Short2, 4, None),
    Short4: _packed(Short4, 8, None),
    NormalizedShort2: _packed(NormalizedShort2, 4, None),
    NormalizedShort4: _packed(NormalizedShort4, 8, None),
    float: _single(),
    Vector2: _vector2(),
    Vector3: _vector3(),
    Vector4: _vector4(),
}

#: The vertex-element format each type takes in a vertex declaration.
VERTEX_FORMATS: dict[type, VertexElementFormat] = {
    float: VertexElementFormat.Single,
    Vector2: VertexElementFormat.Vector2,
    Vector3: VertexElementFormat.Vector3,
    Vector4: VertexElementFormat.Vector4,
    Color: VertexElementFormat.Color,
    Byte4: VertexElementFormat.Byte4,
    Short2: VertexElementFormat.Short2,
    Short4: VertexElementFormat.Short4,
    NormalizedShort2: VertexElementFormat.NormalizedShort2,
    NormalizedShort4: VertexElementFormat.NormalizedShort4,
    HalfVector2: VertexElementFormat.HalfVector2,
    HalfVector4: VertexElementFormat.HalfVector4,
}

#: Read the other way, for a bitmap that has to answer "what type is this?"
_BY_SURFACE = {kind.surface: element for element, kind in PIXEL_KINDS.items()
               if kind.surface is not None}
_BY_VERTEX_FORMAT = {value: element for element, value in VERTEX_FORMATS.items()}


def kind_of(element: type) -> PixelKind:
    kind = PIXEL_KINDS.get(element)
    if kind is None:
        raise TypeError(
            f"{getattr(element, '__name__', element)!r} is not a pixel type the "
            "content pipeline knows; the pixel types are Color, the seventeen "
            "packed vectors, float, Vector2, Vector3 and Vector4")
    return kind


def to_vector4(value: object) -> Vector4:
    """One pixel as an unpacked colour, whatever type it started as."""
    if isinstance(value, Vector4):
        return value
    if isinstance(value, Vector3):
        return Vector4(value.X, value.Y, value.Z, 1.0)
    if isinstance(value, Vector2):
        return Vector4(value.X, value.Y, 0.0, 1.0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Vector4(float(value), 0.0, 0.0, 1.0)
    return value.ToVector4()


def from_vector4(element: type, value: Vector4) -> object:
    """The reverse: one unpacked colour as a pixel of ``element``'s type."""
    if element is Vector4:
        return value
    if element is Vector3:
        return Vector3(value.X, value.Y, value.Z)
    if element is Vector2:
        return Vector2(value.X, value.Y)
    if element is float:
        return float(value.X)
    if element is Color:
        return Color(_byte(value.X), _byte(value.Y), _byte(value.Z), _byte(value.W))
    result = element.__new__(element)
    result.PackFromVector4(value)
    return result


def _byte(value: float) -> int:
    return max(0, min(255, int(round(float(value) * 255.0))))


class VectorConverter:
    """XNA's map between pixel types and the formats that describe them.

    Every method answers ``(bool, value)``: XNA's ``out`` parameter becomes the
    second half of the return, which is this projection's rule everywhere. A
    type that is not a pixel type answers ``(False, None)`` rather than raising,
    because "is this a texture format?" is a question with a *no*.
    """

    __slots__ = ()

    @staticmethod
    def TryGetSurfaceFormat(vectorType: type) -> tuple[bool, SurfaceFormat | None]:
        kind = PIXEL_KINDS.get(vectorType)
        if kind is None or kind.surface is None:
            return False, None
        return True, kind.surface

    @staticmethod
    def TryGetVectorType(value) -> tuple[bool, type | None]:
        """XNA's two overloads: one from a surface format, one from a vertex one.

        They are one method here because Python dispatches on the value, and the
        two enums are distinct types -- so the dispatch is exact rather than a
        guess about which enum an integer came from.
        """
        if isinstance(value, SurfaceFormat):
            element = _BY_SURFACE.get(value)
            return (element is not None), element
        if isinstance(value, VertexElementFormat):
            element = _BY_VERTEX_FORMAT.get(value)
            return (element is not None), element
        raise TypeError(
            "TryGetVectorType takes a SurfaceFormat or a VertexElementFormat, "
            f"not {type(value).__name__}")

    @staticmethod
    def TryGetVertexElementFormat(
            vectorType: type) -> tuple[bool, VertexElementFormat | None]:
        value = VERTEX_FORMATS.get(vectorType)
        return (value is not None), value

    @staticmethod
    def GetConverter(*, sourceType: type, destinationType: type):
        """A callable that turns one pixel type into another.

        XNA answers a ``Converter<TInput, TOutput>`` delegate and takes no
        arguments at all -- both types are type arguments. A Python call carries
        none, so they are keyword arguments: the positional signature is still
        XNA's, and the two types are named at the call the way C# names them.

        Both ends go through the unpacked ``Vector4``, which is what makes any
        pair convertible without a table of every pair.
        """
        kind_of(sourceType)
        kind_of(destinationType)
        if sourceType is destinationType:
            return lambda value: value
        return lambda value: from_vector4(destinationType, to_vector4(value))


VectorConverter.__xna_arities__ = {"TryGetVectorType": {1}, "GetConverter": {0}}
