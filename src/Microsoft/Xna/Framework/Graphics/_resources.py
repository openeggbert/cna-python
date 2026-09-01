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
from .._math import Vector2, Vector3
from .._language import Event
from .._numeric import int32, uint32
from ._device import GraphicsDevice, SpriteEffects, SpriteSortMode, SurfaceFormat


def _release(operation: str):
    def release(handle: int) -> None:
        library = get_library()
        library.check(getattr(library, operation)(handle), operation)
    return release


class GraphicsResource:
    __slots__ = ("_native", "_game", "_graphics_device", "_name", "_tag",
                 "_disposing_callback", "_disposing_registration", "_dispose_error",
                 "_raise_dispose_event", "_native_dispose_event", "_managed_disposed",
                 "__weakref__")
    Disposing = Event()

    def _init_resource(self, graphics_device: GraphicsDevice | None, handle: int, release,
                       *, native_dispose_event: bool = True) -> None:
        self._game = None if graphics_device is None else graphics_device._game
        self._graphics_device = graphics_device
        self._native = NativeResource(handle, Ownership.OWNED, release, self._game)
        # Shutdown releases this handle through the owning generation rather than
        # through the facade, so the facade's own teardown is registered here too.
        self._native.set_before_release(self._before_dispose)
        self._name, self._tag = None, None
        self._dispose_error = None
        self._raise_dispose_event = True
        self._native_dispose_event = native_dispose_event
        self._managed_disposed = False
        @abi.CNA_GraphicsResourceDisposingCallback
        def callback(resource, context):
            if not self._raise_dispose_event:
                return
            try:
                self.Disposing(self, None)
            except BaseException as error:
                self._dispose_error = error
        self._disposing_callback = callback
        self._disposing_registration = 0
        if native_dispose_event:
            registration = c.c_uint64()
            library = get_library()
            library.check(
                library.cna_graphics_resource_subscribe_disposing(
                    handle, callback, None, c.byref(registration)
                ),
                "cna_graphics_resource_subscribe_disposing",
            )
            self._disposing_registration = int(registration.value)
            # CNA keeps the trampoline pointer until unregistration or resource
            # destruction, and the owning handle outlives this facade, so the
            # callback is rooted there rather than only here.
            self._native.retain_for_registration(callback)

    def _init_managed_resource(self, graphics_device: GraphicsDevice | None = None) -> None:
        self._game = None if graphics_device is None else graphics_device._game
        self._graphics_device = graphics_device
        self._native = None
        self._name, self._tag = None, None
        self._disposing_callback = None
        self._disposing_registration = 0
        self._dispose_error = None
        self._raise_dispose_event = True
        self._native_dispose_event = False
        self._managed_disposed = False

    def _require_handle(self) -> int:
        if self._native is None:
            if self._managed_disposed:
                raise RuntimeError(f"{type(self).__name__} is disposed")
            raise NativeCapabilityError(type(self).__name__, 6, None,
                                        "managed graphics-state descriptors have no native handle")
        return self._native._require_handle()

    @property
    def IsDisposed(self) -> bool:
        return self._managed_disposed if self._native is None else self._native.IsDisposed
    @property
    def GraphicsDevice(self) -> GraphicsDevice: return self._graphics_device
    @property
    def Name(self):
        if self._native is None:
            return self._name
        if self.IsDisposed:
            return self._name
        library = get_library()
        count = c.c_uint64()
        library.check(library.cna_graphics_resource_get_name_byte_count(
            self._require_handle(), c.byref(count)), "cna_graphics_resource_get_name_byte_count")
        if count.value == 0:
            return ""
        buffer = c.create_string_buffer(count.value)
        written = c.c_uint64()
        library.check(library.cna_graphics_resource_copy_name(
            self._require_handle(), buffer, count.value, c.byref(written)),
            "cna_graphics_resource_copy_name")
        self._name = bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")
        return self._name
    @Name.setter
    def Name(self, value):
        if not isinstance(value, str):
            raise TypeError("Name must be str")
        if "\0" in value:
            raise ValueError("Name cannot contain NUL")
        if self._native is None:
            if self._managed_disposed:
                raise RuntimeError(f"{type(self).__name__} is disposed")
            self._name = value
            return
        encoded = value.encode("utf-8", errors="strict")
        view = abi.CNA_StringView(encoded, len(encoded))
        library = get_library()
        library.check(library.cna_graphics_resource_set_name(self._require_handle(), view),
                      "cna_graphics_resource_set_name")
        self._name = value
    @property
    def Tag(self): return self._tag
    @Tag.setter
    def Tag(self, value): self._tag = value
    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self.IsDisposed:
            return
        self._before_dispose()
        self._raise_dispose_event = not args or bool(args[0])
        if self._native is None:
            if self._raise_dispose_event:
                self.Disposing(self, None)
            self._managed_disposed = True
            if self._game is not None:
                self._game._unregister_native_child(self)
            return
        if self._raise_dispose_event and not self._native_dispose_event:
            try:
                self.Disposing(self, None)
            except BaseException as error:
                self._dispose_error = error
        self._native.Dispose()
        first_error = self._dispose_error
        self._dispose_error = None
        # CNA consumes the owned registration as part of resource destruction.
        # Calling unsubscribe after the native destroy would use an invalid handle.
        self._disposing_registration = 0
        if first_error is not None: raise first_error
    def _before_dispose(self) -> None:
        return None
    def ToString(self) -> str:
        if self._native is None:
            return self._name or f"{type(self).__module__}.{type(self).__name__}"
        if self.IsDisposed:
            return self._name or f"{type(self).__module__}.{type(self).__name__}"
        library = get_library()
        count = c.c_uint64()
        library.check(library.cna_graphics_resource_get_string_byte_count(
            self._require_handle(), c.byref(count)), "cna_graphics_resource_get_string_byte_count")
        if count.value == 0:
            return ""
        buffer = c.create_string_buffer(count.value)
        written = c.c_uint64()
        library.check(library.cna_graphics_resource_copy_string(
            self._require_handle(), buffer, count.value, c.byref(written)),
            "cna_graphics_resource_copy_string")
        return bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")
    __str__ = ToString
    def __enter__(self):
        self._require_handle(); return self
    def __exit__(self, exc_type, exc, traceback): self.Dispose()


class ResourceCreatedEventArgs:
    __slots__ = ("_resource",)

    def __init__(self, resource: object, _token: object = None) -> None:
        if _token is not ResourceCreatedEventArgs:
            raise TypeError("ResourceCreatedEventArgs instances are supplied by GraphicsDevice")
        self._resource = resource

    @classmethod
    def _create(cls, resource: object) -> "ResourceCreatedEventArgs":
        return cls(resource, cls)

    @property
    def Resource(self) -> object:
        return self._resource


class ResourceDestroyedEventArgs:
    __slots__ = ("_name", "_tag")

    def __init__(self, name: str, tag: object, _token: object = None) -> None:
        if _token is not ResourceDestroyedEventArgs:
            raise TypeError("ResourceDestroyedEventArgs instances are supplied by GraphicsDevice")
        if not isinstance(name, str):
            raise TypeError("name must be str")
        self._name, self._tag = name, tag

    @classmethod
    def _create(cls, name: str, tag: object) -> "ResourceDestroyedEventArgs":
        return cls(name, tag, cls)

    @property
    def Name(self) -> str:
        return self._name

    @property
    def Tag(self) -> object:
        return self._tag


class Texture(GraphicsResource):
    """Common owned texture resource state shared by Texture2D."""

    def _before_dispose(self) -> None:
        if self.GraphicsDevice is not None:
            self.GraphicsDevice._unbind_texture_resource(self)

    @property
    def Format(self) -> SurfaceFormat:
        self._require_handle()
        return self._format

    @property
    def LevelCount(self) -> int:
        self._require_handle()
        return self._level_count


class Texture2D(Texture):
    __slots__ = ("_width", "_height", "_level_count", "_format")

    def __init__(self, *args: object) -> None:
        if len(args) == 3:
            graphicsDevice, width, height = args
            mipMap, format = False, SurfaceFormat.Color
        elif len(args) == 5:
            graphicsDevice, width, height, mipMap, format = args
        else:
            raise TypeError("Texture2D expects graphicsDevice, width, height[, mipMap, format]")
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
    def _borrow_frame(cls, graphicsDevice: GraphicsDevice, handle: int,
                      validate) -> "Texture2D":
        """Wraps a frame texture the runtime owns and lends for a bounded time.

        The wrapper never destroys the handle and never registers a native event
        on it: a frame texture is handed out again on every read, so a per-frame
        subscription or ownership claim would be wrong on both counts.  ``validate``
        runs before every native use and refuses once the borrow has expired.
        """
        self = cls.__new__(cls)
        self._game = None if graphicsDevice is None else graphicsDevice._game
        self._graphics_device = graphicsDevice
        # Parent is deliberately omitted: the borrow is per frame, so registering
        # it as a child of the owning generation would accumulate one entry per
        # read for the life of the game.
        self._native = NativeResource(handle, Ownership.BORROWED, None)
        self._native.set_use_validator(validate)
        self._name, self._tag = None, None
        self._dispose_error = None
        self._raise_dispose_event = True
        self._native_dispose_event = False
        self._managed_disposed = False
        self._disposing_callback = None
        self._disposing_registration = 0
        self._read_info()
        return self

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

    def _save_encoded(self, stream: BinaryIO, width: int, height: int, image_format: int,
                      operation: str) -> None:
        if not hasattr(stream, "write"):
            raise TypeError("stream must be a writable binary file-like object")
        width, height = uint32(width, name="width"), uint32(height, name="height")
        if width == 0 or height == 0:
            raise ValueError("encoded dimensions must be positive")
        library = get_library()
        count = c.c_uint64()
        handle = self._require_handle()
        library.check(library.cna_texture2d_get_encoded_byte_count(
            handle, image_format, width, height, c.byref(count)), operation)
        native = (c.c_uint8 * count.value)()
        written = c.c_uint64()
        library.check(library.cna_texture2d_copy_encoded(
            handle, image_format, width, height, native, count.value, c.byref(written)), operation)
        payload = bytes(native[:written.value])
        rollback = None
        if all(hasattr(stream, name) for name in ("tell", "seek", "truncate")):
            try:
                rollback = stream.tell()
            except Exception:
                rollback = None
        try:
            result = stream.write(payload)
            if result is not None and result != len(payload):
                raise OSError(f"short stream write: {result} of {len(payload)} bytes")
        except BaseException:
            if rollback is not None:
                try:
                    stream.seek(rollback)
                    stream.truncate(rollback)
                except Exception:
                    pass
            raise

    def SaveAsPng(self, stream: BinaryIO, width: int, height: int) -> None:
        self._save_encoded(stream, width, height, 0, "cna_texture2d_copy_encoded(PNG)")

    def SaveAsJpeg(self, stream: BinaryIO, width: int, height: int) -> None:
        self._save_encoded(stream, width, height, 1, "cna_texture2d_copy_encoded(JPEG)")


class SpriteFont:
    """Content-owned bitmap font; constructed only through the private glyph factory."""

    __slots__ = ("_native", "_texture", "_glyph_bounds", "_cropping", "_characters",
                 "_kerning", "_character_index")

    @classmethod
    def _create(cls, texture: Texture2D, glyphBounds: Sequence[Rectangle],
                cropping: Sequence[Rectangle], characters: Sequence[str],
                lineSpacing: int, spacing: float, kerning: Sequence[Vector3],
                defaultCharacter: str | None = None) -> "SpriteFont":
        if not isinstance(texture, Texture2D): raise TypeError("texture must be Texture2D")
        count = len(characters)
        if not (len(glyphBounds) == len(cropping) == len(kerning) == count) or count == 0:
            raise ValueError("SpriteFont glyph arrays must have one equal, nonzero length")
        if not all(isinstance(value, Rectangle) for value in (*glyphBounds, *cropping)):
            raise TypeError("glyphBounds and cropping must contain Rectangle values")
        if not all(isinstance(value, Vector3) for value in kerning):
            raise TypeError("kerning must contain Vector3 values")
        values = tuple(cls._character(value, "character") for value in characters)
        if len(set(values)) != len(values): raise ValueError("SpriteFont characters must be unique")
        fallback = None if defaultCharacter is None else cls._character(defaultCharacter, "defaultCharacter")
        if fallback is not None and fallback not in values:
            raise ValueError("defaultCharacter must be present in characters")
        line_spacing = int32(lineSpacing, name="lineSpacing")
        spacing = float(spacing)
        if not math.isfinite(spacing): raise ValueError("spacing must be finite")
        native_glyphs = (abi.CNA_SpriteFontGlyph * count)()
        for index, character in enumerate(values):
            glyph = native_glyphs[index]
            glyph.struct_size, glyph.struct_version = c.sizeof(glyph), 1
            glyph.glyph_bounds = abi.CNA_Rectangle(*tuple(glyphBounds[index]))
            glyph.cropping = abi.CNA_Rectangle(*tuple(cropping[index]))
            glyph.character = ord(character)
            glyph.kerning = abi.CNA_Vector3(*kerning[index])
        info = abi.CNA_SpriteFontCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.texture, info.glyphs, info.glyph_count = texture._require_handle(), native_glyphs, count
        info.line_spacing, info.spacing = line_spacing, spacing
        info.has_default_character = fallback is not None
        info.default_character = 0 if fallback is None else ord(fallback)
        output = c.c_uint64(); library = get_library()
        library.check(library.cna_sprite_font_create(c.byref(info), c.byref(output)),
                      "cna_sprite_font_create")
        result = cls()
        result._native = NativeResource(int(output.value), Ownership.OWNED,
                                        _release("cna_sprite_font_destroy"), texture._game)
        result._texture = texture
        result._glyph_bounds = tuple(value.__copy__() for value in glyphBounds)
        result._cropping = tuple(value.__copy__() for value in cropping)
        result._characters = values
        result._kerning = tuple(value.__copy__() for value in kerning)
        result._character_index = {value: index for index, value in enumerate(values)}
        return result

    @staticmethod
    def _character(value: object, name: str) -> str:
        if not isinstance(value, str) or len(value) != 1 or ord(value) > 0xFFFF or 0xD800 <= ord(value) <= 0xDFFF:
            raise ValueError(f"{name} must be one Unicode BMP character")
        return value

    def _require_handle(self) -> int:
        native = getattr(self, "_native", None)
        if native is None: raise TypeError("SpriteFont instances are provided by Content or the private glyph factory")
        return native._require_handle()

    def _info(self) -> abi.CNA_SpriteFontInfo:
        value = abi.CNA_SpriteFontInfo(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_sprite_font_get_info(
            self._require_handle(), c.byref(value)), "cna_sprite_font_get_info")
        return value

    @property
    def Characters(self) -> tuple[str, ...]: self._require_handle(); return self._characters
    @property
    def DefaultCharacter(self) -> str | None:
        value = self._info(); return chr(value.default_character) if value.has_default_character else None
    @DefaultCharacter.setter
    def DefaultCharacter(self, value: str | None) -> None:
        selected = None if value is None else self._character(value, "DefaultCharacter")
        if selected is not None and selected not in self._character_index:
            raise ValueError("DefaultCharacter must be present in Characters")
        library = get_library(); library.check(library.cna_sprite_font_set_default_character(
            self._require_handle(), selected is not None, 0 if selected is None else ord(selected)),
            "cna_sprite_font_set_default_character")
    @property
    def LineSpacing(self) -> int: return int(self._info().line_spacing)
    @LineSpacing.setter
    def LineSpacing(self, value: int) -> None:
        selected = int32(value, name="LineSpacing"); library = get_library()
        library.check(library.cna_sprite_font_set_line_spacing(self._require_handle(), selected),
                      "cna_sprite_font_set_line_spacing")
    @property
    def Spacing(self) -> float: return float(self._info().spacing)
    @Spacing.setter
    def Spacing(self, value: float) -> None:
        selected = float(value)
        if not math.isfinite(selected): raise ValueError("Spacing must be finite")
        library = get_library(); library.check(library.cna_sprite_font_set_spacing(
            self._require_handle(), selected), "cna_sprite_font_set_spacing")
    def MeasureString(self, text: str) -> Vector2:
        if not isinstance(text, str): raise TypeError("text must be str")
        encoded = text.encode("utf-8", errors="strict")
        output = abi.CNA_Vector2(); library = get_library()
        library.check(library.cna_sprite_font_measure_utf8(
            self._require_handle(), abi.CNA_StringView(encoded, len(encoded)), c.byref(output)),
            "cna_sprite_font_measure_utf8")
        return Vector2(output.x, output.y)

    def _placements(self, text: str):
        if not isinstance(text, str): raise TypeError("text must be str")
        spacing, line_spacing = self.Spacing, self.LineSpacing
        offset_x = offset_y = 0.0; first = True
        for character in text:
            if character == "\r": continue
            if character == "\n":
                offset_x = 0.0; offset_y += line_spacing; first = True; continue
            index = self._character_index.get(character)
            if index is None:
                fallback = self.DefaultCharacter
                index = None if fallback is None else self._character_index.get(fallback)
            if index is None:
                raise ValueError(f"character {character!r} is not present and no default is set")
            kern, crop = self._kerning[index], self._cropping[index]
            offset_x += max(kern.X, 0.0) if first else spacing + kern.X
            first = False
            yield self._glyph_bounds[index], Vector2(offset_x + crop.X, offset_y + crop.Y)
            offset_x += kern.Y + kern.Z

    def _dispose(self) -> None:
        native = getattr(self, "_native", None)
        if native is not None: native.Dispose()


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
        # CNA does not classify SpriteBatch as a graphics-resource handle
        # for the common subscription route.  It still has deterministic owned
        # lifetime, so its inherited event is emitted synchronously immediately
        # before the native destroy call.
        self._init_resource(graphicsDevice, int(output.value), _release("cna_sprite_batch_destroy"),
                            native_dispose_event=False)
        self._begun = False

    def _require_handle(self) -> int: return self._native._require_handle()

    def Begin(self, *args: object) -> None:
        if self._begun:
            raise RuntimeError("SpriteBatch.Begin cannot be called twice without End")
        sort_mode = SpriteSortMode.Deferred
        if args:
            if len(args) not in (2, 5, 6, 7):
                raise TypeError("no matching XNA SpriteBatch.Begin overload")
            sort_mode = SpriteSortMode(args[0])
            if any(value is not None for value in args[1:]):
                raise NativeCapabilityError(
                    "SpriteBatch.Begin", 6, None,
                    "CNA's begin route carries only a sort mode and its state field is "
                    "reserved and must be zero, so the interval always uses AlphaBlend, "
                    "LinearClamp, DepthStencilState.None, CullCounterClockwise, the identity "
                    "transform and no custom effect")
        info = abi.CNA_SpriteBatchBeginInfo()
        info.struct_size, info.struct_version, info.sort_mode = c.sizeof(info), 1, int(sort_mode)
        library = get_library()
        library.check(library.cna_sprite_batch_begin(self._require_handle(), c.byref(info)),
                      "cna_sprite_batch_begin")
        self._begun = True

    def Draw(self, *args: object) -> None:
        if not self._begun:
            raise RuntimeError("SpriteBatch.Draw requires an active Begin/End interval")
        if len(args) not in (3, 4, 8, 9):
            raise TypeError("no matching XNA SpriteBatch.Draw overload")
        texture, position = args[0], args[1]
        if not isinstance(texture, Texture2D):
            raise TypeError("texture must be Texture2D")
        destination = None
        if isinstance(position, Rectangle):
            # The destination-rectangle overloads take no scale argument, which is
            # what separates their arities from the position ones.
            destination, position = position, None
            if len(args) == 3:
                source, color, rotation, origin, effects, depth = (
                    None, args[2], 0.0, Vector2.Zero, SpriteEffects.None_, 0.0)
            elif len(args) == 4:
                source, color, rotation, origin, effects, depth = (
                    args[2], args[3], 0.0, Vector2.Zero, SpriteEffects.None_, 0.0)
            elif len(args) == 8:
                source, color, rotation, origin, effects, depth = args[2:]
            else:
                raise TypeError("no matching XNA SpriteBatch.Draw overload")
            if source is not None and not isinstance(source, Rectangle):
                raise TypeError("sourceRectangle must be Rectangle or None")
        else:
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
            if isinstance(scale, (int, float)):
                scale = Vector2(scale)
            if not isinstance(scale, Vector2):
                raise TypeError("scale must be Single or Vector2")
        if not isinstance(color, Color) or not isinstance(origin, Vector2):
            raise TypeError("color and origin have the wrong XNA value type")
        library = get_library()
        if destination is not None:
            # A destination rectangle is its own native command rather than a
            # derived scale: with a position the origin is measured in source
            # pixels and the scale applies after that offset, so the two shapes
            # are not interchangeable and converting between them would repeat
            # arithmetic the runtime already does.
            if not all(math.isfinite(value) for value in (float(rotation), *origin, float(depth))):
                raise ValueError("SpriteBatch transform values must be finite")
            command = abi.CNA_SpriteCommand()
            command.struct_size, command.struct_version = c.sizeof(command), 1
            command.texture = texture._require_handle()
            command.destination = abi.CNA_Rectangle(*tuple(destination))
            # Unlike the position command, this one has no "zero size means the
            # whole texture" rule, so an absent source rectangle is spelled out.
            command.source = abi.CNA_Rectangle(*(
                tuple(source) if source is not None
                else (0, 0, texture.Width, texture.Height)))
            command.color = abi.CNA_Color(*tuple(color))
            command.rotation, command.origin = rotation, abi.CNA_Vector2(*origin)
            command.effects, command.layer_depth = int(SpriteEffects(effects)), depth
            library.check(library.cna_sprite_batch_submit_many(
                self._require_handle(), c.byref(command), 1),
                "cna_sprite_batch_submit_many")
            return
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

    def DrawString(self, *args: object) -> None:
        if not self._begun: raise RuntimeError("SpriteBatch.DrawString requires an active Begin/End interval")
        if len(args) not in (4, 9): raise TypeError("no matching XNA SpriteBatch.DrawString overload")
        font, text, position, color = args[:4]
        if not isinstance(font, SpriteFont): raise TypeError("spriteFont must be SpriteFont")
        font._require_handle()
        if not isinstance(text, str): raise TypeError("text must be str")
        if not isinstance(position, Vector2) or not isinstance(color, Color):
            raise TypeError("position and color have the wrong XNA value type")
        if len(args) == 4:
            rotation, origin, scale, effects, depth = 0.0, Vector2.Zero, Vector2.One, SpriteEffects.None_, 0.0
        else:
            rotation, origin, scale, effects, depth = args[4:]
            if isinstance(scale, (int, float)): scale = Vector2(scale)
        if not isinstance(origin, Vector2) or not isinstance(scale, Vector2):
            raise TypeError("origin and scale have the wrong XNA value type")
        for source, anchor in font._placements(text):
            self.Draw(font._texture, position, source, color, rotation,
                      origin - anchor, scale, effects, depth)

    def End(self) -> None:
        if not self._begun:
            raise RuntimeError("SpriteBatch.End requires Begin")
        library = get_library()
        try:
            library.check(library.cna_sprite_batch_end(self._require_handle()), "cna_sprite_batch_end")
        finally:
            self._begun = False

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        self._begun = False
        super().Dispose(*args)

    def __enter__(self):
        self._require_handle(); return self
    def __exit__(self, exc_type, exc, traceback): self.Dispose()


GraphicsResource.__xna_arities__ = {"Dispose": {0, 1}}
Texture2D.__xna_arities__ = {
    "__init__": {3, 5}, "FromStream": {2, 5}, "SetData": {1, 3, 5},
    "GetData": {1, 3, 5}, "Dispose": {0, 1},
}
SpriteBatch.__xna_arities__ = {
    "Begin": {0, 2, 5, 6, 7}, "Draw": {3, 4, 8, 9}, "DrawString": {4, 9},
    "Dispose": {0, 1},
}
