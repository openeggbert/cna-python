"""Owned CNA Texture2D and SpriteBatch resources."""

from __future__ import annotations

import ctypes as c
import math
from typing import BinaryIO, MutableSequence, Sequence

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library
from _cna_native.ownership import NativeResource, Ownership

from .._geometry import Color, Rectangle
from .._math import Vector2
from .._numeric import int32
from ._device import GraphicsDevice, SpriteEffects, SpriteSortMode, SurfaceFormat


def _release(operation: str):
    def release(handle: int) -> None:
        library = get_library()
        library.check(getattr(library, operation)(handle), operation)
    return release


class GraphicsResource:
    __slots__ = ("_native", "_game", "_graphics_device", "_name", "_tag")

    def _init_resource(self, graphics_device: GraphicsDevice, handle: int, release) -> None:
        self._game = graphics_device._game
        self._graphics_device = graphics_device
        self._native = NativeResource(handle, Ownership.OWNED, release, self._game)
        self._name, self._tag = None, None

    def _require_handle(self) -> int:
        return self._native._require_handle()

    @property
    def IsDisposed(self) -> bool: return self._native.IsDisposed
    @property
    def GraphicsDevice(self) -> GraphicsDevice: return self._graphics_device
    @property
    def Name(self): return self._name
    @Name.setter
    def Name(self, value): self._name = value
    @property
    def Tag(self): return self._tag
    @Tag.setter
    def Tag(self, value): self._tag = value
    def Dispose(self) -> None: self._native.Dispose()
    def __enter__(self):
        self._require_handle(); return self
    def __exit__(self, exc_type, exc, traceback): self.Dispose()


class Texture(GraphicsResource):
    """Common owned texture resource state shared by Texture2D."""


class Texture2D(Texture):
    __slots__ = ("_width", "_height", "_level_count", "_format")

    def __init__(self, graphicsDevice: GraphicsDevice, width: int, height: int,
                 mipMap: bool = False, format: SurfaceFormat = SurfaceFormat.Color) -> None:
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be a GraphicsDevice")
        width, height = int32(width, name="width"), int32(height, name="height")
        if width <= 0 or height <= 0:
            raise ValueError("texture dimensions must be positive")
        info = abi.CNA_Texture2DCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.width, info.height, info.mip_map, info.format = width, height, bool(mipMap), int(format)
        output = c.c_uint64()
        library = get_library()
        library.check(library.cna_texture2d_create(graphicsDevice._require_handle(), c.byref(info), c.byref(output)),
                      "cna_texture2d_create")
        self._init_resource(graphicsDevice, int(output.value), _release("cna_texture2d_destroy"))
        self._read_info()

    @classmethod
    def _from_handle(cls, graphicsDevice: GraphicsDevice, handle: int) -> "Texture2D":
        self = cls.__new__(cls)
        self._init_resource(graphicsDevice, handle, _release("cna_texture2d_destroy"))
        self._read_info()
        return self

    def _read_info(self) -> None:
        value = abi.CNA_Texture2DInfo()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_texture2d_get_info(self._require_handle(), c.byref(value)),
                      "cna_texture2d_get_info")
        self._width, self._height = int(value.width), int(value.height)
        self._level_count, self._format = int(value.level_count), SurfaceFormat(value.format)

    @property
    def Width(self) -> int: return self._width
    @property
    def Height(self) -> int: return self._height
    @property
    def Bounds(self) -> Rectangle: return Rectangle(0, 0, self.Width, self.Height)

    @staticmethod
    def FromStream(graphicsDevice: GraphicsDevice, stream: BinaryIO, *args: object) -> "Texture2D":
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be a GraphicsDevice")
        if not hasattr(stream, "read"):
            raise TypeError("stream must be a binary file-like object")
        payload = stream.read()
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("stream.read() must return bytes")
        data = bytes(payload)
        if not data:
            raise ValueError("encoded image stream is empty")
        decode_pointer = None
        decode = abi.CNA_Texture2DDecodeInfo()
        if args:
            if len(args) != 3:
                raise TypeError("FromStream expects stream or stream, width, height, zoom")
            width, height, zoom = int32(args[0], name="width"), int32(args[1], name="height"), bool(args[2])
            if width <= 0 or height <= 0:
                raise ValueError("decode dimensions must be positive")
            decode.struct_size, decode.struct_version = c.sizeof(decode), 1
            decode.width, decode.height, decode.zoom = width, height, zoom
            decode_pointer = c.byref(decode)
        native_data = (c.c_uint8 * len(data)).from_buffer_copy(data)
        output = c.c_uint64()
        library = get_library()
        library.check(
            library.cna_texture2d_create_from_encoded_memory(
                graphicsDevice._require_handle(), native_data, len(data), decode_pointer, c.byref(output)
            ),
            "cna_texture2d_create_from_encoded_memory",
        )
        return Texture2D._from_handle(graphicsDevice, int(output.value))

    @staticmethod
    def _transfer(args: tuple[object, ...]) -> tuple[Sequence[Color], abi.CNA_Texture2DTransfer]:
        if len(args) == 1:
            data, level, rectangle, start, count = args[0], 0, None, 0, len(args[0])
        elif len(args) == 3:
            data, start, count = args
            level, rectangle = 0, None
        elif len(args) == 5:
            level, rectangle, data, start, count = args
        else:
            raise TypeError("SetData/GetData expects data; data,start,count; or level,rect,data,start,count")
        if not isinstance(data, Sequence) or not all(isinstance(value, Color) for value in data):
            raise NativeCapabilityError("Texture2D data transfer", 6, None,
                                        "this milestone binds only Color element arrays")
        start, count, level = int32(start, name="startIndex"), int32(count, name="elementCount"), int32(level, name="level")
        if start < 0 or count < 0 or start + count > len(data):
            raise ValueError("texture data range is outside the supplied array")
        if rectangle is not None and not isinstance(rectangle, Rectangle):
            raise TypeError("rect must be Rectangle or None")
        transfer = abi.CNA_Texture2DTransfer()
        transfer.struct_size, transfer.struct_version = c.sizeof(transfer), 1
        transfer.level, transfer.has_rectangle = level, rectangle is not None
        if rectangle is not None:
            transfer.rectangle = abi.CNA_Rectangle(*tuple(rectangle))
        transfer.start_index, transfer.element_count = start, count
        return data, transfer

    def SetData(self, *args: object) -> None:
        data, transfer = self._transfer(args)
        native = (abi.CNA_Color * len(data))(*(abi.CNA_Color(*tuple(value)) for value in data))
        library = get_library()
        library.check(library.cna_texture2d_set_data(self._require_handle(), 0, c.byref(transfer),
                                                     c.cast(native, c.c_void_p), len(data)),
                      "cna_texture2d_set_data")

    def GetData(self, *args: object) -> None:
        data, transfer = self._transfer(args)
        if not isinstance(data, MutableSequence):
            raise TypeError("GetData destination must be mutable")
        native = (abi.CNA_Color * len(data))()
        required = c.c_uint64()
        library = get_library()
        library.check(library.cna_texture2d_get_data(self._require_handle(), 0, c.byref(transfer),
                                                     c.cast(native, c.c_void_p), len(data), c.byref(required)),
                      "cna_texture2d_get_data")
        for index in range(transfer.start_index, transfer.start_index + transfer.element_count):
            value = native[index]
            data[index] = Color(value.r, value.g, value.b, value.a)


class SpriteBatch(GraphicsResource):
    __slots__ = ("_begun",)

    def __init__(self, graphicsDevice: GraphicsDevice) -> None:
        if not isinstance(graphicsDevice, GraphicsDevice):
            raise TypeError("graphicsDevice must be a GraphicsDevice")
        output = c.c_uint64()
        library = get_library()
        library.check(library.cna_sprite_batch_create(graphicsDevice._require_handle(), c.byref(output)),
                      "cna_sprite_batch_create")
        game = graphicsDevice._game
        self._init_resource(graphicsDevice, int(output.value), _release("cna_sprite_batch_destroy"))
        self._begun = False

    def _require_handle(self) -> int: return self._native._require_handle()

    def Begin(self, *args: object) -> None:
        if self._begun:
            raise RuntimeError("SpriteBatch.Begin cannot be called twice without End")
        sort_mode = SpriteSortMode.Deferred
        if args:
            if len(args) > 7:
                raise TypeError("Begin received too many arguments")
            sort_mode = SpriteSortMode(args[0])
            if any(value is not None for value in args[1:]):
                raise NativeCapabilityError("SpriteBatch.Begin", 6, None,
                                            "ABI 0.7 Python slice currently binds only default states/effect/transform")
        info = abi.CNA_SpriteBatchBeginInfo()
        info.struct_size, info.struct_version, info.sort_mode = c.sizeof(info), 1, int(sort_mode)
        library = get_library()
        library.check(library.cna_sprite_batch_begin(self._require_handle(), c.byref(info)),
                      "cna_sprite_batch_begin")
        self._begun = True

    def Draw(self, *args: object) -> None:
        if not self._begun:
            raise RuntimeError("SpriteBatch.Draw requires an active Begin/End interval")
        if len(args) < 3:
            raise TypeError("Draw expects at least texture, position, color")
        texture, position = args[0], args[1]
        if not isinstance(texture, Texture2D):
            raise TypeError("texture must be Texture2D")
        if isinstance(position, Rectangle):
            raise NativeCapabilityError("SpriteBatch.Draw(Rectangle)", 6, None,
                                        "destination-rectangle overloads are not bound in this Python slice")
        if not isinstance(position, Vector2):
            raise TypeError("position must be Vector2")
        if len(args) == 3:
            source, color, rotation, origin, scale, effects, depth = None, args[2], 0.0, Vector2.Zero, 1.0, SpriteEffects.None_, 0.0
        elif len(args) == 4:
            source, color, rotation, origin, scale, effects, depth = args[2], args[3], 0.0, Vector2.Zero, 1.0, SpriteEffects.None_, 0.0
        elif len(args) == 9:
            source, color, rotation, origin, scale, effects, depth = args[2:]
        else:
            raise TypeError("no matching XNA SpriteBatch.Draw overload")
        if source is not None and not isinstance(source, Rectangle):
            raise TypeError("sourceRectangle must be Rectangle or None")
        if not isinstance(color, Color) or not isinstance(origin, Vector2):
            raise TypeError("color and origin have the wrong XNA value type")
        if isinstance(scale, (int, float)):
            scale = Vector2(scale)
        if not isinstance(scale, Vector2):
            raise TypeError("scale must be Single or Vector2")
        values = (*position, float(rotation), *origin, *scale, float(depth))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("SpriteBatch transform values must be finite")
        command = abi.CNA_SpriteScaledCommand()
        command.struct_size, command.struct_version = c.sizeof(command), 1
        command.texture = texture._require_handle()
        command.position = abi.CNA_Vector2(*position)
        command.source = abi.CNA_Rectangle(*(tuple(source) if source is not None else (0, 0, 0, 0)))
        command.color = abi.CNA_Color(*tuple(color))
        command.rotation, command.origin, command.scale = rotation, abi.CNA_Vector2(*origin), abi.CNA_Vector2(*scale)
        command.effects, command.layer_depth = int(SpriteEffects(effects)), depth
        library = get_library()
        library.check(library.cna_sprite_batch_submit_scaled_many(self._require_handle(), c.byref(command), 1),
                      "cna_sprite_batch_submit_scaled_many")

    def End(self) -> None:
        if not self._begun:
            raise RuntimeError("SpriteBatch.End requires Begin")
        library = get_library()
        try:
            library.check(library.cna_sprite_batch_end(self._require_handle()), "cna_sprite_batch_end")
        finally:
            self._begun = False

    def Dispose(self) -> None:
        self._begun = False
        self._native.Dispose()

    def __enter__(self):
        self._require_handle(); return self
    def __exit__(self, exc_type, exc, traceback): self.Dispose()
