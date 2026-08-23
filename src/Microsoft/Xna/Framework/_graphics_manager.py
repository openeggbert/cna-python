"""Root-namespace XNA GraphicsDeviceManager backed by CNA."""

from __future__ import annotations

import ctypes as c

from _cna_native.loader import get_library
from _cna_native.errors import NativeCapabilityError

from ._game import DisplayOrientation
from ._language import Event
from ._numeric import int32
from .Graphics import DepthFormat, GraphicsDevice, GraphicsProfile, SurfaceFormat


class GraphicsDeviceManager:
    DeviceCreated = Event()
    DeviceResetting = Event()
    DeviceReset = Event()
    DeviceDisposing = Event()
    PreparingDeviceSettings = Event()
    Disposed = Event()
    DefaultBackBufferWidth = 800
    DefaultBackBufferHeight = 480

    _setters = {
        "GraphicsProfile": "cna_graphics_device_manager_set_graphics_profile",
        "PreferredDepthStencilFormat": "cna_graphics_device_manager_set_preferred_depth_stencil_format",
        "PreferredBackBufferFormat": "cna_graphics_device_manager_set_preferred_back_buffer_format",
        "PreferredBackBufferWidth": "cna_graphics_device_manager_set_preferred_back_buffer_width",
        "PreferredBackBufferHeight": "cna_graphics_device_manager_set_preferred_back_buffer_height",
        "IsFullScreen": "cna_graphics_device_manager_set_is_full_screen",
        "SynchronizeWithVerticalRetrace": "cna_graphics_device_manager_set_synchronize_with_vertical_retrace",
        "PreferMultiSampling": "cna_graphics_device_manager_set_prefer_multi_sampling",
        "SupportedOrientations": "cna_graphics_device_manager_set_supported_orientations",
    }

    def __init__(self, game: object) -> None:
        from ._game import Game
        if not isinstance(game, Game):
            raise TypeError("GraphicsDeviceManager expects a Game")
        self._game = game
        self._handle = 0
        self._disposed = False
        self._values = {
            "GraphicsProfile": GraphicsProfile.Reach,
            "PreferredDepthStencilFormat": DepthFormat.Depth24,
            "PreferredBackBufferFormat": SurfaceFormat.Color,
            "PreferredBackBufferWidth": self.DefaultBackBufferWidth,
            "PreferredBackBufferHeight": self.DefaultBackBufferHeight,
            "IsFullScreen": False,
            "SynchronizeWithVerticalRetrace": True,
            "PreferMultiSampling": False,
            "SupportedOrientations": DisplayOrientation.Default,
        }
        self._graphics_device = GraphicsDevice(game)
        game._attach_graphics_manager(self)

    @property
    def GraphicsDevice(self) -> GraphicsDevice:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        return self._graphics_device

    def _property(name: str, converter):
        def get(self): return self._values[name]
        def set(self, value):
            if self._disposed: raise RuntimeError("GraphicsDeviceManager is disposed")
            converted = converter(value)
            if name in ("PreferredBackBufferWidth", "PreferredBackBufferHeight") and converted <= 0:
                raise ValueError(f"{name} must be positive")
            self._values[name] = converted
            if self._handle:
                library = get_library()
                operation = self._setters[name]
                library.check(getattr(library, operation)(self._handle, int(converted)), operation)
        return property(get, set)
    GraphicsProfile = _property("GraphicsProfile", GraphicsProfile)
    PreferredDepthStencilFormat = _property("PreferredDepthStencilFormat", DepthFormat)
    PreferredBackBufferFormat = _property("PreferredBackBufferFormat", SurfaceFormat)
    PreferredBackBufferWidth = _property("PreferredBackBufferWidth", lambda value: int32(value, name="PreferredBackBufferWidth"))
    PreferredBackBufferHeight = _property("PreferredBackBufferHeight", lambda value: int32(value, name="PreferredBackBufferHeight"))
    IsFullScreen = _property("IsFullScreen", bool)
    SynchronizeWithVerticalRetrace = _property("SynchronizeWithVerticalRetrace", bool)
    PreferMultiSampling = _property("PreferMultiSampling", bool)
    SupportedOrientations = _property("SupportedOrientations", DisplayOrientation)

    def _create_native(self, host: object) -> None:
        output = c.c_uint64()
        library = get_library()
        library.check(library.cna_graphics_device_manager_create(host.handle, c.byref(output)),
                      "cna_graphics_device_manager_create")
        self._handle = int(output.value)
        for name, value in self._values.items():
            operation = self._setters[name]
            library.check(getattr(library, operation)(self._handle, int(value)), operation)

    def _begin_native_callback(self, game_handle: int) -> None:
        if not self._handle:
            return
        output = c.c_uint64()
        library = get_library()
        result = library.cna_graphics_device_manager_get_graphics_device(self._handle, c.byref(output))
        if result == 0:
            self._graphics_device._enter_native_callback(int(output.value))

    def _end_native_callback(self) -> None:
        self._graphics_device._leave_native_callback()

    def ApplyChanges(self) -> None:
        if not self._handle:
            self._game._ensure_host()
        library = get_library()
        library.check(library.cna_graphics_device_manager_apply_changes(self._handle),
                      "cna_graphics_device_manager_apply_changes")

    def ToggleFullScreen(self) -> None:
        if not self._handle:
            self._game._ensure_host()
        library = get_library()
        library.check(library.cna_graphics_device_manager_toggle_full_screen(self._handle),
                      "cna_graphics_device_manager_toggle_full_screen")
        self._values["IsFullScreen"] = not self._values["IsFullScreen"]

    def CreateDevice(self) -> None:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        self._game._ensure_host()

    def BeginDraw(self) -> bool:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        raise NativeCapabilityError(
            "GraphicsDeviceManager.BeginDraw", 6, None,
            "CNA ABI 0.7 owns BeginDraw inside the native Game lifecycle",
        )

    def EndDraw(self) -> None:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        raise NativeCapabilityError(
            "GraphicsDeviceManager.EndDraw", 6, None,
            "CNA ABI 0.7 owns EndDraw inside the native Game lifecycle",
        )

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self._disposed:
            return
        if self._handle:
            library = get_library()
            library.check(library.cna_graphics_device_manager_destroy(self._handle),
                          "cna_graphics_device_manager_destroy")
            self._handle = 0
        self._graphics_device._disposed = True
        self._disposed = True
        self.Disposed(self, None)

    def __enter__(self) -> "GraphicsDeviceManager":
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


GraphicsDeviceManager.__xna_arities__ = {"Dispose": {0, 1}}
