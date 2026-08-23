"""Private XNA 4.0 runtime content readers for the implemented public surface."""

from __future__ import annotations

from datetime import timedelta
import re
import struct
from typing import Callable

from .._geometry import Color, Point, Rectangle
from .._math import Matrix, Quaternion, Vector2, Vector3, Vector4
from ._content import ContentLoadException, ContentReader, ContentTypeReader


_PREFIX = "Microsoft.Xna.Framework.Content."


class _Reader(ContentTypeReader):
    def __init__(self, target_type: type, read: Callable[[ContentReader], object]) -> None:
        super().__init__(target_type)
        self._read_value = read

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        return self._read_value(input)


class _TimeSpanReader(ContentTypeReader):
    def __init__(self) -> None:
        super().__init__(timedelta)

    def Read(self, input: ContentReader, existingInstance: object) -> timedelta:
        ticks = input.ReadInt64()
        # timedelta has microsecond precision. Reject rather than silently round an XNA
        # TimeSpan that cannot be represented by the formal Python mapping.
        if ticks % 10:
            raise input._failure(
                f"TimeSpan value {ticks} ticks cannot be represented exactly as datetime.timedelta"
            )
        try:
            return timedelta(microseconds=ticks // 10)
        except OverflowError as error:
            raise input._failure(f"TimeSpan value {ticks} ticks is outside datetime.timedelta") from error


class _CollectionReader(ContentTypeReader):
    def __init__(self, element_type_identity: str, *, array: bool) -> None:
        super().__init__(tuple if array else list)
        self._element_type_identity = element_type_identity
        self._element_reader: ContentTypeReader | None = None
        self._array = array

    def Initialize(self, manager) -> None:
        identity = _ELEMENT_READERS.get(self._element_type_identity)
        if identity is None:
            raise ContentLoadException(
                f"No built-in element-reader mapping exists for '{self._element_type_identity}'"
            )
        reader = manager._get_identity_reader(identity)
        if reader is None:
            raise ContentLoadException(
                f"The XNB reader table does not contain '{identity}' required by "
                f"'{self._serialized_identity}'"
            )
        self._element_reader = reader

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        count = input.ReadInt32()
        if count < 0 or count > 1_000_000:
            raise input._failure(f"invalid collection element count {count}")
        reader = self._element_reader
        if reader is None:
            raise input._failure("collection reader was not initialized")
        values = [input.ReadObject(reader) for _ in range(count)]
        return tuple(values) if self._array else values


class _NullableReader(ContentTypeReader):
    def __init__(self, element_type_identity: str) -> None:
        super().__init__(object)
        self._element_type_identity = element_type_identity
        self._element_reader: ContentTypeReader | None = None

    def Initialize(self, manager) -> None:
        identity = _ELEMENT_READERS.get(self._element_type_identity)
        if identity is None:
            raise ContentLoadException(
                f"No built-in nullable-reader mapping exists for '{self._element_type_identity}'"
            )
        self._element_reader = manager._get_identity_reader(identity)
        if self._element_reader is None:
            raise ContentLoadException(
                f"The XNB reader table does not contain '{identity}' required by "
                f"'{self._serialized_identity}'"
            )

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        if not input.ReadBoolean():
            return None
        if self._element_reader is None:
            raise input._failure("nullable reader was not initialized")
        return input.ReadObject(self._element_reader)


class _Texture2DReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import Texture2D

        super().__init__(Texture2D)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import SurfaceFormat, Texture2D

        if existingInstance is not None:
            raise ValueError("Texture2DReader cannot deserialize into an existing texture")
        try:
            format_ = SurfaceFormat(input.ReadInt32())
        except ValueError as error:
            raise input._failure("Texture2D contains an unknown SurfaceFormat") from error
        width = input.ReadUInt32()
        height = input.ReadUInt32()
        mip_count = input.ReadUInt32()
        if width == 0 or height == 0 or width > 65536 or height > 65536:
            raise input._failure(f"Texture2D has implausible dimensions {width}x{height}")
        complete_mips = max(width, height).bit_length()
        if mip_count not in (1, complete_mips):
            raise input._failure(
                f"Texture2D has invalid mip count {mip_count} for {width}x{height}"
            )
        if format_ is not SurfaceFormat.Color:
            raise input._failure(
                f"Texture2D SurfaceFormat.{format_.name} cannot be uploaded faithfully through "
                "CNA ABI 0.7's currently bound texture transfer route"
            )
        texture = Texture2D(
            input.ContentManager._graphics_device(), width, height, mip_count > 1, format_
        )
        try:
            for level in range(mip_count):
                byte_count = input.ReadUInt32()
                level_width = max(1, width >> level)
                level_height = max(1, height >> level)
                expected = level_width * level_height * 4
                if byte_count != expected:
                    raise input._failure(
                        f"Texture2D mip {level} has {byte_count} bytes; expected exactly {expected}"
                    )
                payload = input.ReadBytes(byte_count)
                colors = [Color(*payload[offset:offset + 4]) for offset in range(0, expected, 4)]
                texture.SetData(level, None, colors, 0, len(colors))
            return texture
        except BaseException:
            texture.Dispose()
            raise


class _SpriteFontReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import SpriteFont

        super().__init__(SpriteFont)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import SpriteFont, Texture2D

        if existingInstance is not None:
            raise ValueError("SpriteFontReader cannot deserialize into an existing SpriteFont")
        texture = input.ReadObject()
        glyph_bounds = input.ReadObject()
        cropping = input.ReadObject()
        characters = input.ReadObject()
        line_spacing = input.ReadInt32()
        spacing = input.ReadSingle()
        kerning = input.ReadObject()
        default_character = input.ReadObject()
        if not isinstance(texture, Texture2D):
            raise input._failure("SpriteFont texture is not a Texture2D")
        if not isinstance(glyph_bounds, (list, tuple)) or not all(
            isinstance(value, Rectangle) for value in glyph_bounds
        ):
            raise input._failure("SpriteFont glyph bounds are not a Rectangle collection")
        if not isinstance(cropping, (list, tuple)) or not all(
            isinstance(value, Rectangle) for value in cropping
        ):
            raise input._failure("SpriteFont cropping values are not a Rectangle collection")
        if not isinstance(characters, (list, tuple)) or not all(
            isinstance(value, str) and len(value) == 1 for value in characters
        ):
            raise input._failure("SpriteFont character map is not a Char collection")
        if not isinstance(kerning, (list, tuple)) or not all(
            isinstance(value, Vector3) for value in kerning
        ):
            raise input._failure("SpriteFont kerning values are not a Vector3 collection")
        if default_character is not None and not (
            isinstance(default_character, str) and len(default_character) == 1
        ):
            raise input._failure("SpriteFont default character is not a nullable Char")
        return SpriteFont._create(
            texture, glyph_bounds, cropping, characters, line_spacing, spacing,
            kerning, default_character,
        )


class _VertexDeclarationReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import VertexDeclaration

        super().__init__(VertexDeclaration)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import (
            VertexDeclaration, VertexElement, VertexElementFormat, VertexElementUsage,
        )

        stride = input.ReadInt32()
        count = input.ReadInt32()
        if stride <= 0 or count <= 0 or count > 1024:
            raise input._failure(
                f"VertexDeclaration has invalid stride/count {stride}/{count}"
            )
        elements = []
        for _ in range(count):
            offset = input.ReadInt32()
            try:
                format_ = VertexElementFormat(input.ReadInt32())
                usage = VertexElementUsage(input.ReadInt32())
            except ValueError as error:
                raise input._failure("VertexDeclaration contains an unknown enum value") from error
            usage_index = input.ReadInt32()
            elements.append(VertexElement(offset, format_, usage, usage_index))
        try:
            return VertexDeclaration(stride, elements)
        except Exception as error:
            raise input._failure(f"invalid VertexDeclaration: {error}") from error


class _VertexBufferReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import VertexBuffer

        super().__init__(VertexBuffer)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import BufferUsage, VertexBuffer

        if existingInstance is not None:
            raise ValueError("VertexBufferReader cannot deserialize into an existing buffer")
        declaration_reader = input._reader_manager._get_identity_reader(
            _PREFIX + "VertexDeclarationReader"
        )
        if declaration_reader is None:
            raise input._failure("VertexBufferReader requires VertexDeclarationReader in the table")
        declaration = input.ReadRawObject(declaration_reader)
        vertex_count = input.ReadUInt32()
        if vertex_count == 0 or vertex_count > 100_000_000:
            raise input._failure(f"invalid VertexBuffer vertex count {vertex_count}")
        byte_count = vertex_count * declaration.VertexStride
        if byte_count > 512 * 1024 * 1024:
            raise input._failure(f"implausible VertexBuffer payload size {byte_count}")
        payload = input.ReadBytes(byte_count)
        buffer = VertexBuffer(
            input.ContentManager._graphics_device(), declaration, vertex_count, BufferUsage.None_
        )
        try:
            buffer._set_raw_bytes(payload)
            return buffer
        except BaseException:
            buffer.Dispose()
            raise


class _IndexBufferReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import IndexBuffer

        super().__init__(IndexBuffer)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import BufferUsage, IndexBuffer, IndexElementSize

        if existingInstance is not None:
            raise ValueError("IndexBufferReader cannot deserialize into an existing buffer")
        element_size = (
            IndexElementSize.SixteenBits if input.ReadBoolean()
            else IndexElementSize.ThirtyTwoBits
        )
        byte_count = input.ReadInt32()
        width = 2 if element_size is IndexElementSize.SixteenBits else 4
        if byte_count <= 0 or byte_count > 512 * 1024 * 1024 or byte_count % width:
            raise input._failure(f"invalid IndexBuffer payload size {byte_count}")
        payload = input.ReadBytes(byte_count)
        buffer = IndexBuffer(
            input.ContentManager._graphics_device(), element_size,
            byte_count // width, BufferUsage.None_,
        )
        try:
            buffer._set_raw_bytes(payload)
            return buffer
        except BaseException:
            buffer.Dispose()
            raise


_SIMPLE_READERS: dict[str, tuple[type, Callable[[ContentReader], object]]] = {
    _PREFIX + "BooleanReader": (bool, lambda value: value.ReadBoolean()),
    _PREFIX + "ByteReader": (int, lambda value: value.ReadByte()),
    _PREFIX + "SByteReader": (int, lambda value: value.ReadSByte()),
    _PREFIX + "Int16Reader": (int, lambda value: value.ReadInt16()),
    _PREFIX + "UInt16Reader": (int, lambda value: value.ReadUInt16()),
    _PREFIX + "Int32Reader": (int, lambda value: value.ReadInt32()),
    _PREFIX + "UInt32Reader": (int, lambda value: value.ReadUInt32()),
    _PREFIX + "Int64Reader": (int, lambda value: value.ReadInt64()),
    _PREFIX + "UInt64Reader": (int, lambda value: value.ReadUInt64()),
    _PREFIX + "SingleReader": (float, lambda value: value.ReadSingle()),
    _PREFIX + "DoubleReader": (float, lambda value: value.ReadDouble()),
    _PREFIX + "CharReader": (str, lambda value: value.ReadChar()),
    _PREFIX + "StringReader": (str, lambda value: value.ReadString()),
    _PREFIX + "Vector2Reader": (Vector2, lambda value: value.ReadVector2()),
    _PREFIX + "Vector3Reader": (Vector3, lambda value: value.ReadVector3()),
    _PREFIX + "Vector4Reader": (Vector4, lambda value: value.ReadVector4()),
    _PREFIX + "QuaternionReader": (Quaternion, lambda value: value.ReadQuaternion()),
    _PREFIX + "MatrixReader": (Matrix, lambda value: value.ReadMatrix()),
    _PREFIX + "ColorReader": (Color, lambda value: value.ReadColor()),
    _PREFIX + "PointReader": (
        Point, lambda value: Point(value.ReadInt32(), value.ReadInt32()),
    ),
    _PREFIX + "RectangleReader": (
        Rectangle,
        lambda value: Rectangle(
            value.ReadInt32(), value.ReadInt32(), value.ReadInt32(), value.ReadInt32()
        ),
    ),
}


_SPECIAL_READERS: dict[str, type[ContentTypeReader]] = {
    _PREFIX + "TimeSpanReader": _TimeSpanReader,
    _PREFIX + "Texture2DReader": _Texture2DReader,
    _PREFIX + "SpriteFontReader": _SpriteFontReader,
    _PREFIX + "VertexDeclarationReader": _VertexDeclarationReader,
    _PREFIX + "VertexBufferReader": _VertexBufferReader,
    _PREFIX + "IndexBufferReader": _IndexBufferReader,
}


_ELEMENT_READERS = {
    "System.Boolean": _PREFIX + "BooleanReader",
    "System.Byte": _PREFIX + "ByteReader",
    "System.SByte": _PREFIX + "SByteReader",
    "System.Int16": _PREFIX + "Int16Reader",
    "System.UInt16": _PREFIX + "UInt16Reader",
    "System.Int32": _PREFIX + "Int32Reader",
    "System.UInt32": _PREFIX + "UInt32Reader",
    "System.Int64": _PREFIX + "Int64Reader",
    "System.UInt64": _PREFIX + "UInt64Reader",
    "System.Single": _PREFIX + "SingleReader",
    "System.Double": _PREFIX + "DoubleReader",
    "System.Char": _PREFIX + "CharReader",
    "System.String": _PREFIX + "StringReader",
    "System.TimeSpan": _PREFIX + "TimeSpanReader",
    "Microsoft.Xna.Framework.Vector2": _PREFIX + "Vector2Reader",
    "Microsoft.Xna.Framework.Vector3": _PREFIX + "Vector3Reader",
    "Microsoft.Xna.Framework.Vector4": _PREFIX + "Vector4Reader",
    "Microsoft.Xna.Framework.Quaternion": _PREFIX + "QuaternionReader",
    "Microsoft.Xna.Framework.Matrix": _PREFIX + "MatrixReader",
    "Microsoft.Xna.Framework.Color": _PREFIX + "ColorReader",
    "Microsoft.Xna.Framework.Point": _PREFIX + "PointReader",
    "Microsoft.Xna.Framework.Rectangle": _PREFIX + "RectangleReader",
}


_GENERIC_READER = re.compile(
    r"^Microsoft\.Xna\.Framework\.Content\.(ListReader|ArrayReader|NullableReader)`1\[\[(.+)\]\]$"
)


def _create_builtin_reader(identity: str) -> ContentTypeReader | None:
    simple = _SIMPLE_READERS.get(identity)
    if simple is not None:
        return _Reader(*simple)
    special = _SPECIAL_READERS.get(identity)
    if special is not None:
        return special()
    match = _GENERIC_READER.fullmatch(identity)
    if match is None:
        return None
    kind, element = match.groups()
    if element not in _ELEMENT_READERS:
        return None
    if kind == "NullableReader":
        return _NullableReader(element)
    return _CollectionReader(element, array=kind == "ArrayReader")

