"""Deterministic XNA vertex declarations, built-in values, and owned buffers."""

from __future__ import annotations

import ctypes as c
import struct
from typing import MutableSequence, Sequence

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._geometry import Color
from .._language import Event
from .._math import Vector2, Vector3
from .._numeric import int32
from ._device import (
    BufferUsage, GraphicsDevice, IndexElementSize, SetDataOptions,
    VertexElementFormat, VertexElementUsage,
)
from ._resources import GraphicsResource, _release


_FORMAT_SIZES = {
    VertexElementFormat.Single: 4, VertexElementFormat.Vector2: 8,
    VertexElementFormat.Vector3: 12, VertexElementFormat.Vector4: 16,
    VertexElementFormat.Color: 4, VertexElementFormat.Byte4: 4,
    VertexElementFormat.Short2: 4, VertexElementFormat.Short4: 8,
    VertexElementFormat.NormalizedShort2: 4,
    VertexElementFormat.NormalizedShort4: 8,
    VertexElementFormat.HalfVector2: 4, VertexElementFormat.HalfVector4: 8,
}


class IVertexType:
    @property
    def VertexDeclaration(self) -> "VertexDeclaration":
        raise NotImplementedError


class VertexElement:
    __slots__ = ("_offset", "_format", "_usage", "_usage_index")

    def __init__(self, offset: int = 0,
                 elementFormat: VertexElementFormat = VertexElementFormat.Single,
                 elementUsage: VertexElementUsage = VertexElementUsage.Position,
                 usageIndex: int = 0) -> None:
        self.Offset = offset; self.VertexElementFormat = elementFormat
        self.VertexElementUsage = elementUsage; self.UsageIndex = usageIndex

    def _integer(name: str):
        private = "_" + name
        return property(lambda self: getattr(self, private),
                        lambda self, value: setattr(self, private, int32(value, name=name)))
    Offset = _integer("offset"); UsageIndex = _integer("usage_index")
    VertexElementFormat = property(lambda self: self._format,
        lambda self, value: setattr(self, "_format", VertexElementFormat(value)))
    VertexElementUsage = property(lambda self: self._usage,
        lambda self, value: setattr(self, "_usage", VertexElementUsage(value)))

    def _native(self) -> abi.CNA_VertexElement:
        return abi.CNA_VertexElement(self.Offset, int(self.VertexElementFormat),
                                     int(self.VertexElementUsage), self.UsageIndex)
    def __eq__(self, other: object) -> bool:
        return isinstance(other, VertexElement) and tuple(self) == tuple(other)
    def __hash__(self) -> int: return hash(tuple(self))
    def __iter__(self):
        return iter((self.Offset, self.VertexElementFormat,
                     self.VertexElementUsage, self.UsageIndex))
    def ToString(self) -> str:
        return (f"{{Offset:{self.Offset} Format:{self.VertexElementFormat.name} "
                f"Usage:{self.VertexElementUsage.name} UsageIndex:{self.UsageIndex}}}")
    __str__ = ToString; Equals = __eq__; GetHashCode = __hash__
    def __copy__(self): return VertexElement(*tuple(self))
    __deepcopy__ = lambda self, memo: self.__copy__()


class VertexDeclaration(GraphicsResource):
    __slots__ = ("_elements", "_vertex_stride")

    def __init__(self, *args: object) -> None:
        if len(args) == 1:
            elements, explicit_stride = args[0], None
        elif len(args) == 2:
            explicit_stride, elements = int32(args[0], name="vertexStride"), args[1]
            if explicit_stride <= 0: raise ValueError("vertexStride must be positive")
        else:
            raise TypeError("VertexDeclaration expects elements or vertexStride, elements")
        if not isinstance(elements, Sequence) or not elements:
            raise ValueError("elements must be a non-empty sequence")
        if not all(isinstance(value, VertexElement) for value in elements):
            raise TypeError("elements must contain VertexElement values")
        copied = tuple(VertexElement(*tuple(value)) for value in elements)
        minimum_stride = max(value.Offset + _FORMAT_SIZES[value.VertexElementFormat]
                             for value in copied)
        if explicit_stride is not None and explicit_stride < minimum_stride:
            raise ValueError("vertexStride is smaller than the declared elements")
        self._elements = copied
        self._vertex_stride = minimum_stride if explicit_stride is None else explicit_stride
        self._init_managed_resource(None)

    def _ensure_native(self) -> int:
        if self._native is not None: return super()._require_handle()
        if self._managed_disposed: raise RuntimeError("VertexDeclaration is disposed")
        native = (abi.CNA_VertexElement * len(self._elements))(
            *(value._native() for value in self._elements))
        output = c.c_uint64(); library = get_library()
        operation = ("cna_vertex_declaration_create" if
                     self._vertex_stride == max(value.Offset + _FORMAT_SIZES[value.VertexElementFormat]
                                                for value in self._elements)
                     else "cna_vertex_declaration_create_with_stride")
        if operation.endswith("with_stride"):
            result = getattr(library, operation)(self._vertex_stride, native,
                                                 len(native), c.byref(output))
        else:
            result = getattr(library, operation)(native, len(native), c.byref(output))
        library.check(result, operation)
        name, tag = self._name, self._tag
        self._init_resource(None, int(output.value), _release("cna_vertex_declaration_destroy"))
        self._name, self._tag = name, tag
        return super()._require_handle()

    def _require_handle(self) -> int: return self._ensure_native()
    @property
    def VertexStride(self) -> int:
        if self.IsDisposed: raise RuntimeError("VertexDeclaration is disposed")
        return self._vertex_stride
    def GetVertexElements(self) -> list[VertexElement]:
        if self.IsDisposed: raise RuntimeError("VertexDeclaration is disposed")
        return [VertexElement(*tuple(value)) for value in self._elements]


class _VertexValue(IVertexType):
    _codec = ""; _vertex_type = -1
    @property
    def VertexDeclaration(self): return type(self).VertexDeclaration
    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and tuple(self) == tuple(other)
    def __hash__(self) -> int: return hash(tuple(self))
    Equals = __eq__; GetHashCode = __hash__
    def ToString(self) -> str:
        values = " ".join(f"{name}:{getattr(self, name)}" for name in self.__slots__)
        return "{" + values + "}"
    __str__ = ToString
    def __copy__(self): return type(self)(*tuple(self))
    __deepcopy__ = lambda self, memo: self.__copy__()


class VertexPositionColor(_VertexValue):
    __slots__ = ("Position", "Color")
    _codec = "<3f4B"; _vertex_type = 0
    def __init__(self, position: Vector3 = None, color: Color = None) -> None:
        self.Position = Vector3.Zero if position is None else position.__copy__()
        self.Color = Color.Transparent if color is None else color.__copy__()
        if not isinstance(self.Position, Vector3) or not isinstance(self.Color, Color):
            raise TypeError("position and color have the wrong XNA value type")
    def __iter__(self): return iter((self.Position, self.Color))


class VertexPositionColorTexture(_VertexValue):
    __slots__ = ("Position", "Color", "TextureCoordinate")
    _codec = "<3f4B2f"; _vertex_type = 1
    def __init__(self, position: Vector3 = None, color: Color = None,
                 textureCoordinate: Vector2 = None) -> None:
        self.Position = Vector3.Zero if position is None else position.__copy__()
        self.Color = Color.Transparent if color is None else color.__copy__()
        self.TextureCoordinate = Vector2.Zero if textureCoordinate is None else textureCoordinate.__copy__()
        if not isinstance(self.Position, Vector3) or not isinstance(self.Color, Color) or not isinstance(self.TextureCoordinate, Vector2):
            raise TypeError("vertex fields have the wrong XNA value type")
    def __iter__(self): return iter((self.Position, self.Color, self.TextureCoordinate))


class VertexPositionNormalTexture(_VertexValue):
    __slots__ = ("Position", "Normal", "TextureCoordinate")
    _codec = "<3f3f2f"; _vertex_type = 4
    def __init__(self, position: Vector3 = None, normal: Vector3 = None,
                 textureCoordinate: Vector2 = None) -> None:
        self.Position = Vector3.Zero if position is None else position.__copy__()
        self.Normal = Vector3.Zero if normal is None else normal.__copy__()
        self.TextureCoordinate = Vector2.Zero if textureCoordinate is None else textureCoordinate.__copy__()
        if not all(isinstance(value, (Vector2, Vector3)) for value in (self.Position, self.Normal, self.TextureCoordinate)):
            raise TypeError("vertex fields have the wrong XNA value type")
    def __iter__(self): return iter((self.Position, self.Normal, self.TextureCoordinate))


class VertexPositionTexture(_VertexValue):
    __slots__ = ("Position", "TextureCoordinate")
    _codec = "<3f2f"; _vertex_type = 6
    def __init__(self, position: Vector3 = None, textureCoordinate: Vector2 = None) -> None:
        self.Position = Vector3.Zero if position is None else position.__copy__()
        self.TextureCoordinate = Vector2.Zero if textureCoordinate is None else textureCoordinate.__copy__()
        if not isinstance(self.Position, Vector3) or not isinstance(self.TextureCoordinate, Vector2):
            raise TypeError("vertex fields have the wrong XNA value type")
    def __iter__(self): return iter((self.Position, self.TextureCoordinate))


def _pack_vertex(value: _VertexValue) -> bytes:
    if isinstance(value, VertexPositionColor):
        return struct.pack(value._codec, *value.Position, *value.Color)
    if isinstance(value, VertexPositionColorTexture):
        return struct.pack(value._codec, *value.Position, *value.Color, *value.TextureCoordinate)
    if isinstance(value, VertexPositionNormalTexture):
        return struct.pack(value._codec, *value.Position, *value.Normal, *value.TextureCoordinate)
    if isinstance(value, VertexPositionTexture):
        return struct.pack(value._codec, *value.Position, *value.TextureCoordinate)
    raise TypeError("unsupported vertex value type")


def _unpack_vertex(kind: type[_VertexValue], payload: bytes) -> _VertexValue:
    values = struct.unpack(kind._codec, payload)
    if kind is VertexPositionColor: return kind(Vector3(*values[:3]), Color(*values[3:7]))
    if kind is VertexPositionColorTexture: return kind(Vector3(*values[:3]), Color(*values[3:7]), Vector2(*values[7:9]))
    if kind is VertexPositionNormalTexture: return kind(Vector3(*values[:3]), Vector3(*values[3:6]), Vector2(*values[6:8]))
    if kind is VertexPositionTexture: return kind(Vector3(*values[:3]), Vector2(*values[3:5]))
    raise TypeError("unsupported vertex value type")


def _native_vertex_array(values: Sequence[_VertexValue], kind: type[_VertexValue]):
    if kind is VertexPositionColor:
        item = abi.CNA_VertexPositionColor
        return (item * len(values))(*(item(abi.CNA_Vector3(*value.Position), abi.CNA_Color(*tuple(value.Color))) for value in values))
    if kind is VertexPositionColorTexture:
        item = abi.CNA_VertexPositionColorTexture
        return (item * len(values))(*(item(abi.CNA_Vector3(*value.Position), abi.CNA_Color(*tuple(value.Color)), abi.CNA_Vector2(*value.TextureCoordinate)) for value in values))
    if kind is VertexPositionNormalTexture:
        item = abi.CNA_VertexPositionNormalTexture
        return (item * len(values))(*(item(abi.CNA_Vector3(*value.Position), abi.CNA_Vector3(*value.Normal), abi.CNA_Vector2(*value.TextureCoordinate)) for value in values))
    if kind is VertexPositionTexture:
        item = abi.CNA_VertexPositionTexture
        return (item * len(values))(*(item(abi.CNA_Vector3(*value.Position), abi.CNA_Vector2(*value.TextureCoordinate)) for value in values))
    raise TypeError("unsupported vertex value type")


VertexPositionColor.VertexDeclaration = VertexDeclaration((
    VertexElement(0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0),
    VertexElement(12, VertexElementFormat.Color, VertexElementUsage.Color, 0)))
VertexPositionColorTexture.VertexDeclaration = VertexDeclaration((
    VertexElement(0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0),
    VertexElement(12, VertexElementFormat.Color, VertexElementUsage.Color, 0),
    VertexElement(16, VertexElementFormat.Vector2, VertexElementUsage.TextureCoordinate, 0)))
VertexPositionNormalTexture.VertexDeclaration = VertexDeclaration((
    VertexElement(0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0),
    VertexElement(12, VertexElementFormat.Vector3, VertexElementUsage.Normal, 0),
    VertexElement(24, VertexElementFormat.Vector2, VertexElementUsage.TextureCoordinate, 0)))
VertexPositionTexture.VertexDeclaration = VertexDeclaration((
    VertexElement(0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0),
    VertexElement(12, VertexElementFormat.Vector2, VertexElementUsage.TextureCoordinate, 0)))


class VertexBufferBinding:
    __slots__ = ("_buffer", "_offset", "_frequency")
    def __init__(self, vertexBuffer: "VertexBuffer" = None, vertexOffset: int = 0,
                 instanceFrequency: int = 0) -> None:
        if vertexBuffer is None:
            if vertexOffset != 0 or instanceFrequency != 0: raise TypeError("default binding has no offsets")
            self._buffer, self._offset, self._frequency = None, 0, 0
            return
        if not isinstance(vertexBuffer, VertexBuffer): raise TypeError("vertexBuffer must be VertexBuffer")
        offset = int32(vertexOffset, name="vertexOffset")
        frequency = int32(instanceFrequency, name="instanceFrequency")
        if offset < 0 or frequency < 0: raise ValueError("offset and frequency cannot be negative")
        self._buffer, self._offset, self._frequency = vertexBuffer, offset, frequency
    @property
    def VertexBuffer(self): return self._buffer
    @property
    def VertexOffset(self): return self._offset
    @property
    def InstanceFrequency(self): return self._frequency
    def _native(self): return abi.CNA_VertexBufferBinding(self._buffer._require_handle(), self._offset, self._frequency)
    def __copy__(self):
        return VertexBufferBinding() if self._buffer is None else VertexBufferBinding(self._buffer, self._offset, self._frequency)
    __deepcopy__ = lambda self, memo: self.__copy__()


class VertexBuffer(GraphicsResource):
    __slots__ = ("_declaration", "_vertex_count", "_buffer_usage", "_vertex_kind")
    def __init__(self, graphicsDevice: GraphicsDevice, vertexType, vertexCount: int,
                 usage: BufferUsage) -> None:
        self._create(graphicsDevice, vertexType, vertexCount, usage, False)
    def _create(self, graphicsDevice, vertexType, vertexCount, usage, dynamic):
        if not isinstance(graphicsDevice, GraphicsDevice): raise TypeError("graphicsDevice must be GraphicsDevice")
        kind = None
        if isinstance(vertexType, VertexDeclaration): declaration = vertexType
        elif isinstance(vertexType, type) and issubclass(vertexType, _VertexValue):
            declaration, kind = vertexType.VertexDeclaration, vertexType
        else: raise TypeError("vertexType must be a built-in vertex class or VertexDeclaration")
        count = int32(vertexCount, name="vertexCount")
        if count <= 0: raise ValueError("vertexCount must be positive")
        usage = BufferUsage(usage)
        info = abi.CNA_VertexBufferCreateInfo(); info.struct_size, info.struct_version = c.sizeof(info), 1
        info.vertex_declaration = declaration._require_handle(); info.vertex_count = count
        info.buffer_usage = int(usage); info.dynamic = dynamic
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_vertex_buffer_create(graphicsDevice._require_handle(), c.byref(info), c.byref(output)), "cna_vertex_buffer_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_vertex_buffer_destroy"))
        self._declaration, self._vertex_count, self._buffer_usage, self._vertex_kind = declaration, count, usage, kind
    @property
    def VertexDeclaration(self): self._require_handle(); return self._declaration
    @property
    def VertexCount(self): self._require_handle(); return self._vertex_count
    @property
    def BufferUsage(self): self._require_handle(); return self._buffer_usage
    def _transfer(self, args, options=SetDataOptions.None_, *, read=False):
        offset = 0
        if len(args) == 1: data, start, count, stride = args[0], 0, len(args[0]), self._declaration.VertexStride
        elif len(args) == 3: data, start, count = args; stride = self._declaration.VertexStride
        elif len(args) == 5: offset, data, start, count, stride = args
        else: raise TypeError("no matching VertexBuffer data overload")
        if not isinstance(data, Sequence): raise TypeError("data must be a sequence")
        start, count, offset, stride = (int32(start, name="startIndex"), int32(count, name="elementCount"), int32(offset, name="offsetInBytes"), int32(stride, name="vertexStride"))
        if start < 0 or count < 0 or start + count > len(data) or offset < 0 or stride <= 0: raise ValueError("invalid vertex data range")
        if count and self._vertex_kind is None: raise TypeError("custom declarations require explicit raw bytes")
        if not read and self._vertex_kind is not None and not all(type(value) is self._vertex_kind for value in data[start:start+count]): raise TypeError("vertex values do not match the buffer declaration")
        payload = b"" if read else b"".join(_pack_vertex(value) for value in data[start:start+count])
        if stride != self._declaration.VertexStride: raise ValueError("vertexStride must match the declaration")
        return data, start, count, offset, stride, payload, SetDataOptions(options)
    def SetData(self, *args: object) -> None:
        _, _, count, offset, stride, payload, _ = self._transfer(args)
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload) if payload else None
        library = get_library(); operation = "cna_vertex_buffer_set_data_raw" if offset == 0 else "cna_vertex_buffer_set_data_raw_at"
        if offset == 0: result = getattr(library, operation)(self._require_handle(), native, len(payload), count, stride)
        else: result = getattr(library, operation)(self._require_handle(), offset, native, len(payload), count, stride)
        library.check(result, operation)
    def _set_raw_bytes(self, payload: bytes) -> None:
        """Upload one complete XNB vertex payload without inventing a public byte overload."""
        if not isinstance(payload, bytes): raise TypeError("payload must be bytes")
        stride = self._declaration.VertexStride
        expected = self._vertex_count * stride
        if len(payload) != expected: raise ValueError(f"vertex payload has {len(payload)} bytes; expected {expected}")
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload)
        library = get_library()
        library.check(library.cna_vertex_buffer_set_data_raw(
            self._require_handle(), native, len(payload), self._vertex_count, stride),
            "cna_vertex_buffer_set_data_raw")
    def GetData(self, *args: object) -> None:
        data, start, count, offset, stride, _, _ = self._transfer(args, read=True)
        if not isinstance(data, MutableSequence): raise TypeError("GetData destination must be mutable")
        payload = (c.c_uint8 * (count * stride))(); library = get_library()
        library.check(library.cna_vertex_buffer_get_data_raw(self._require_handle(), offset, payload, len(payload), count, stride), "cna_vertex_buffer_get_data_raw")
        for index in range(count): data[start + index] = _unpack_vertex(self._vertex_kind, bytes(payload[index*stride:(index+1)*stride]))
    def Dispose(self, *args: object) -> None:
        if not self.IsDisposed and self.GraphicsDevice is not None:
            bindings = getattr(self.GraphicsDevice, "_vertex_bindings", ())
            if any(value.VertexBuffer is self for value in bindings):
                raise RuntimeError("a bound VertexBuffer cannot be disposed")
        super().Dispose(*args)


class DynamicVertexBuffer(VertexBuffer):
    ContentLost = Event()
    def __init__(self, graphicsDevice, vertexType, vertexCount, usage):
        self._create(graphicsDevice, vertexType, vertexCount, usage, True)
    @property
    def IsContentLost(self):
        info = abi.CNA_VertexBufferInfo(); info.struct_size, info.struct_version = c.sizeof(info), 1
        library = get_library(); library.check(library.cna_vertex_buffer_get_info(self._require_handle(), c.byref(info)), "cna_vertex_buffer_get_info")
        return info.is_content_lost != 0
    def SetData(self, *args: object) -> None:
        if len(args) in (4, 6):
            *base, options = args
            _, _, count, offset, stride, payload, options = self._transfer(tuple(base), options)
            if options == SetDataOptions.None_:
                return super().SetData(*base)
            # The options-carrying raw uploads take the same destination offset as the
            # plain raw family, so the offset and the streaming hint reach CNA together.
            native = (c.c_uint8 * len(payload)).from_buffer_copy(payload) if payload else None
            library = get_library()
            operation = ("cna_vertex_buffer_set_data_raw_with_options" if offset == 0
                         else "cna_vertex_buffer_set_data_raw_at_with_options")
            if offset == 0:
                result = library.cna_vertex_buffer_set_data_raw_with_options(
                    self._require_handle(), native, len(payload), count, stride, int(options))
            else:
                result = library.cna_vertex_buffer_set_data_raw_at_with_options(
                    self._require_handle(), offset, native, len(payload), count, stride, int(options))
            library.check(result, operation)
            return
        return super().SetData(*args)


class IndexBuffer(GraphicsResource):
    __slots__ = ("_index_count", "_element_size", "_buffer_usage")
    def __init__(self, graphicsDevice, indexType, indexCount, usage): self._create(graphicsDevice, indexType, indexCount, usage, False)
    def _create(self, graphicsDevice, indexType, indexCount, usage, dynamic):
        if not isinstance(graphicsDevice, GraphicsDevice): raise TypeError("graphicsDevice must be GraphicsDevice")
        if indexType is int: element = IndexElementSize.ThirtyTwoBits
        else: element = IndexElementSize(indexType)
        count = int32(indexCount, name="indexCount"); usage = BufferUsage(usage)
        if count <= 0: raise ValueError("indexCount must be positive")
        info = abi.CNA_IndexBufferCreateInfo(); info.struct_size, info.struct_version = c.sizeof(info), 1
        info.index_count, info.index_element_size, info.buffer_usage, info.dynamic = count, int(element), int(usage), dynamic
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_index_buffer_create(graphicsDevice._require_handle(), c.byref(info), c.byref(output)), "cna_index_buffer_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_index_buffer_destroy"))
        self._index_count, self._element_size, self._buffer_usage = count, element, usage
    @property
    def IndexCount(self): self._require_handle(); return self._index_count
    @property
    def IndexElementSize(self): self._require_handle(); return self._element_size
    @property
    def BufferUsage(self): self._require_handle(); return self._buffer_usage
    def _transfer(self, args, options=SetDataOptions.None_):
        offset = 0
        if len(args) == 1: data, start, count = args[0], 0, len(args[0])
        elif len(args) == 3: data, start, count = args
        elif len(args) == 4: offset, data, start, count = args
        else: raise TypeError("no matching IndexBuffer data overload")
        if not isinstance(data, Sequence): raise TypeError("data must be a sequence")
        start, count, offset = int32(start, name="startIndex"), int32(count, name="elementCount"), int32(offset, name="offsetInBytes")
        if start < 0 or count < 0 or start + count > len(data) or offset < 0: raise ValueError("invalid index data range")
        maximum = 65535 if self._element_size == IndexElementSize.SixteenBits else 4294967295
        values = data[start:start+count]
        if not all(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= maximum for value in values): raise ValueError("index value is outside the buffer element width")
        native_type = c.c_uint16 if self._element_size == IndexElementSize.SixteenBits else c.c_uint32
        native = (native_type * count)(*values)
        transfer = abi.CNA_IndexBufferTransfer(); transfer.struct_size, transfer.struct_version = c.sizeof(transfer), 1
        transfer.index_element_size, transfer.options = int(self._element_size), int(SetDataOptions(options))
        transfer.start_index, transfer.element_count = 0, count
        return data, start, count, offset, native, transfer
    def SetData(self, *args: object) -> None:
        _, _, _, offset, native, transfer = self._transfer(args)
        library = get_library(); operation = "cna_index_buffer_set_data" if offset == 0 else "cna_index_buffer_set_data_at"
        if offset == 0: result = getattr(library, operation)(self._require_handle(), c.byref(transfer), native, len(native))
        else: result = getattr(library, operation)(self._require_handle(), offset, c.byref(transfer), native, len(native))
        library.check(result, operation)
    def _set_raw_bytes(self, payload: bytes) -> None:
        """Upload one complete XNB index payload through the ordinary typed ABI route."""
        if not isinstance(payload, bytes): raise TypeError("payload must be bytes")
        width = 2 if self._element_size == IndexElementSize.SixteenBits else 4
        expected = self._index_count * width
        if len(payload) != expected: raise ValueError(f"index payload has {len(payload)} bytes; expected {expected}")
        format_ = "<" + ("H" if width == 2 else "I") * self._index_count
        self.SetData(struct.unpack(format_, payload))
    def GetData(self, *args: object) -> None:
        data, start, _, offset, native, transfer = self._transfer(args)
        if not isinstance(data, MutableSequence): raise TypeError("GetData destination must be mutable")
        if offset:
            raise NativeCapabilityError(
                "IndexBuffer.GetData(offset)", 6, None,
                "ABI 0.7 has no index-buffer readback route with a native byte offset",
            )
        required = c.c_uint64(); library = get_library()
        library.check(library.cna_index_buffer_get_data(self._require_handle(), c.byref(transfer), native, len(native), c.byref(required)), "cna_index_buffer_get_data")
        for index, value in enumerate(native): data[start + index] = int(value)
    def Dispose(self, *args: object) -> None:
        if (not self.IsDisposed and self.GraphicsDevice is not None and
                getattr(self.GraphicsDevice, "_index_buffer", None) is self):
            raise RuntimeError("a bound IndexBuffer cannot be disposed")
        super().Dispose(*args)


class DynamicIndexBuffer(IndexBuffer):
    ContentLost = Event()
    def __init__(self, graphicsDevice, indexType, indexCount, usage): self._create(graphicsDevice, indexType, indexCount, usage, True)
    @property
    def IsContentLost(self):
        info = abi.CNA_IndexBufferInfo(); info.struct_size, info.struct_version = c.sizeof(info), 1
        library = get_library(); library.check(library.cna_index_buffer_get_info(self._require_handle(), c.byref(info)), "cna_index_buffer_get_info")
        return info.is_content_lost != 0
    def SetData(self, *args: object) -> None:
        if len(args) in (4, 5):
            *base, options = args
            data, start, count, offset, native, transfer = self._transfer(tuple(base), options)
            library = get_library(); operation = "cna_index_buffer_set_data" if offset == 0 else "cna_index_buffer_set_data_at"
            if offset == 0: result = getattr(library, operation)(self._require_handle(), c.byref(transfer), native, len(native))
            else: result = getattr(library, operation)(self._require_handle(), offset, c.byref(transfer), native, len(native))
            library.check(result, operation); return
        return super().SetData(*args)


VertexDeclaration.__xna_arities__ = {"__init__": {1, 2}, "Dispose": {0, 1}}
VertexElement.__xna_arities__ = {"__init__": {0, 4}}
VertexPositionColor.__xna_arities__ = {"__init__": {0, 2}}
VertexPositionColorTexture.__xna_arities__ = {"__init__": {0, 3}}
VertexPositionNormalTexture.__xna_arities__ = {"__init__": {0, 3}}
VertexPositionTexture.__xna_arities__ = {"__init__": {0, 2}}
VertexBufferBinding.__xna_arities__ = {"__init__": {0, 1, 2, 3}}
VertexBuffer.__xna_arities__ = {"__init__": {4}, "SetData": {1, 3, 5}, "GetData": {1, 3, 5}, "Dispose": {0, 1}}
DynamicVertexBuffer.__xna_arities__ = {"__init__": {4}, "SetData": {4, 6}, "GetData": {1, 3, 5}, "Dispose": {0, 1}}
IndexBuffer.__xna_arities__ = {"__init__": {4}, "SetData": {1, 3, 4}, "GetData": {1, 3, 4}, "Dispose": {0, 1}}
DynamicIndexBuffer.__xna_arities__ = {"__init__": {4}, "SetData": {4, 5}, "GetData": {1, 3, 4}, "Dispose": {0, 1}}
