"""Graphics-device values and callback-scoped CNA device projection."""

from __future__ import annotations

import ctypes as c
from enum import IntEnum, IntFlag
import math

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._geometry import Color, Rectangle
from .._math import Vector3
from .._numeric import f32, int32


class SurfaceFormat(IntEnum):
    Color = 0


class DepthFormat(IntEnum):
    None_ = 0
    Depth16 = 1
    Depth24 = 2
    Depth24Stencil8 = 3


class GraphicsProfile(IntEnum):
    Reach = 0
    HiDef = 1


class SpriteSortMode(IntEnum):
    Deferred = 0
    Immediate = 1
    Texture = 2
    BackToFront = 3
    FrontToBack = 4


class SpriteEffects(IntFlag):
    None_ = 0
    FlipHorizontally = 1
    FlipVertically = 2


class Viewport:
    __slots__ = ("_x", "_y", "_width", "_height", "_min_depth", "_max_depth")

    def __init__(self, x: int | Rectangle = 0, y: int = 0, width: int = 0, height: int = 0) -> None:
        if isinstance(x, Rectangle):
            x, y, width, height = x.X, x.Y, x.Width, x.Height
        self.X, self.Y, self.Width, self.Height = x, y, width, height
        self.MinDepth, self.MaxDepth = 0.0, 1.0

    def _integer(name: str):
        private = "_" + name.lower()
        return property(lambda self: getattr(self, private),
                        lambda self, value: setattr(self, private, int32(value, name=name)))
    X = _integer("X"); Y = _integer("Y"); Width = _integer("Width"); Height = _integer("Height")
    @property
    def MinDepth(self) -> float: return self._min_depth
    @MinDepth.setter
    def MinDepth(self, value: float) -> None: self._min_depth = f32(value)
    @property
    def MaxDepth(self) -> float: return self._max_depth
    @MaxDepth.setter
    def MaxDepth(self, value: float) -> None: self._max_depth = f32(value)
    @property
    def Bounds(self) -> Rectangle: return Rectangle(self.X, self.Y, self.Width, self.Height)
    @Bounds.setter
    def Bounds(self, value: Rectangle) -> None: self.X, self.Y, self.Width, self.Height = tuple(value)
    @property
    def AspectRatio(self) -> float:
        return f32(self.Width / self.Height) if self.Height != 0 else 0.0
    @property
    def TitleSafeArea(self) -> Rectangle:
        output = abi.CNA_Rectangle()
        library = get_library()
        library.check(library.cna_viewport_get_title_safe_area(self._native(), c.byref(output)),
                      "cna_viewport_get_title_safe_area")
        return Rectangle(output.x, output.y, output.width, output.height)
    def _native(self) -> abi.CNA_Viewport:
        return abi.CNA_Viewport(self.X, self.Y, self.Width, self.Height, self.MinDepth, self.MaxDepth)
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Viewport) and tuple(self) == tuple(other)
    def __iter__(self): return iter((self.X, self.Y, self.Width, self.Height, self.MinDepth, self.MaxDepth))
    def ToString(self) -> str:
        return f"{{X:{self.X} Y:{self.Y} Width:{self.Width} Height:{self.Height} MinDepth:{self.MinDepth:g} MaxDepth:{self.MaxDepth:g}}}"
    __str__ = ToString


class GraphicsDevice:
    """Borrowed game-owned device, valid only during a native lifecycle callback."""

    __slots__ = ("_game", "_handle", "_disposed")

    def __init__(self, game: object) -> None:
        self._game = game
        self._handle = 0
        self._disposed = False

    def _enter_native_callback(self, handle: int) -> None:
        self._handle = handle

    def _leave_native_callback(self) -> None:
        self._handle = 0

    def _require_handle(self) -> int:
        if self._disposed:
            raise RuntimeError("GraphicsDevice is disposed")
        if self._handle == 0:
            raise RuntimeError("GraphicsDevice native access is only valid during a CNA lifecycle callback")
        return self._handle

    @property
    def Viewport(self) -> Viewport:
        value = abi.CNA_Viewport()
        library = get_library()
        library.check(library.cna_graphics_device_get_viewport(self._require_handle(), c.byref(value)),
                      "cna_graphics_device_get_viewport")
        result = Viewport(value.x, value.y, value.width, value.height)
        result.MinDepth, result.MaxDepth = value.min_depth, value.max_depth
        return result

    @Viewport.setter
    def Viewport(self, value: Viewport) -> None:
        if not isinstance(value, Viewport):
            raise TypeError("Viewport must be a Viewport value")
        library = get_library()
        library.check(library.cna_graphics_device_set_viewport(self._require_handle(), value._native()),
                      "cna_graphics_device_set_viewport")

    def Clear(self, *args: object) -> None:
        if len(args) != 1 or not isinstance(args[0], Color):
            raise NativeCapabilityError("GraphicsDevice.Clear", 6, None,
                                        "only the XNA Clear(Color) overload is bound in this milestone")
        color = args[0]
        channels = tuple(f32(channel / 255.0) for channel in color)
        library = get_library()
        library.check(library.cna_graphics_device_clear_rgba(self._require_handle(), *channels),
                      "cna_graphics_device_clear_rgba")

    def Dispose(self) -> None:
        raise NativeCapabilityError("GraphicsDevice.Dispose", 6, None,
                                    "CNA ABI 0.7 exposes only the game-owned GraphicsDevice")
