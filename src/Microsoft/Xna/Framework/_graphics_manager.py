"""Root-namespace XNA GraphicsDeviceManager backed by CNA."""

from __future__ import annotations

import ctypes as c
from typing import List

from _cna_native import abi
from _cna_native.loader import get_library

from ._game import DisplayOrientation
from ._language import Event
from ._numeric import int32
from .Graphics import (
    DepthFormat, GraphicsAdapter, GraphicsDevice, GraphicsProfile,
    IGraphicsDeviceService, PresentationParameters, SurfaceFormat,
)


def _strict_bool(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("graphics preference must be bool")
    return value


class IGraphicsDeviceManager:
    def CreateDevice(self) -> None: raise NotImplementedError
    def BeginDraw(self) -> bool: raise NotImplementedError
    def EndDraw(self) -> None: raise NotImplementedError


class GraphicsDeviceInformation:
    def __init__(self) -> None:
        self._adapter = None
        self._graphics_profile = GraphicsProfile.Reach
        self._presentation_parameters = PresentationParameters()

    @property
    def Adapter(self) -> GraphicsAdapter | None: return self._adapter
    @Adapter.setter
    def Adapter(self, value: GraphicsAdapter | None) -> None:
        if value is not None and not isinstance(value, GraphicsAdapter):
            raise TypeError("Adapter must be GraphicsAdapter or None")
        self._adapter = value
    @property
    def GraphicsProfile(self) -> GraphicsProfile: return self._graphics_profile
    @GraphicsProfile.setter
    def GraphicsProfile(self, value: GraphicsProfile) -> None:
        self._graphics_profile = GraphicsProfile(value)
    @property
    def PresentationParameters(self) -> PresentationParameters:
        return self._presentation_parameters
    @PresentationParameters.setter
    def PresentationParameters(self, value: PresentationParameters) -> None:
        if not isinstance(value, PresentationParameters):
            raise TypeError("PresentationParameters must be PresentationParameters")
        self._presentation_parameters = value

    def Clone(self) -> "GraphicsDeviceInformation":
        result = GraphicsDeviceInformation()
        result.Adapter = self.Adapter
        result.GraphicsProfile = self.GraphicsProfile
        result.PresentationParameters = self.PresentationParameters.Clone()
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GraphicsDeviceInformation): return False
        left, right = self.PresentationParameters, other.PresentationParameters
        names = ("BackBufferWidth", "BackBufferHeight", "BackBufferFormat",
                 "DepthStencilFormat", "MultiSampleCount", "DisplayOrientation",
                 "PresentationInterval", "RenderTargetUsage", "DeviceWindowHandle",
                 "IsFullScreen")
        return (self.Adapter is other.Adapter and self.GraphicsProfile == other.GraphicsProfile
                and all(getattr(left, name) == getattr(right, name) for name in names))

    def __hash__(self) -> int:
        parameters = self.PresentationParameters
        return hash((self.Adapter, self.GraphicsProfile, parameters.BackBufferWidth,
                     parameters.BackBufferHeight, parameters.BackBufferFormat,
                     parameters.DepthStencilFormat, parameters.MultiSampleCount,
                     parameters.DisplayOrientation, parameters.PresentationInterval,
                     parameters.RenderTargetUsage, parameters.DeviceWindowHandle,
                     parameters.IsFullScreen))

    Equals = __eq__
    GetHashCode = __hash__

    @classmethod
    def _from_native(cls, value: abi.CNA_GraphicsDeviceInformation,
                     manager: "GraphicsDeviceManager") -> "GraphicsDeviceInformation":
        result = cls()
        result.Adapter = (None if value.adapter_index < 0 else
                          GraphicsAdapter._for_device(manager.GraphicsDevice,
                                                      int(value.adapter_index)))
        result.GraphicsProfile = GraphicsProfile(value.graphics_profile)
        result.PresentationParameters = PresentationParameters._from_native(
            value.presentation_parameters)
        return result

    def _write_native(self, value: abi.CNA_GraphicsDeviceInformation) -> None:
        if self.Adapter is None:
            value.adapter_index = -1
        elif not isinstance(self.Adapter, GraphicsAdapter):
            raise TypeError("Adapter must be GraphicsAdapter or None")
        else:
            value.adapter_index = self.Adapter._index
        value.graphics_profile = int(GraphicsProfile(self.GraphicsProfile))
        parameters = self.PresentationParameters
        if not isinstance(parameters, PresentationParameters):
            raise TypeError("PresentationParameters must be PresentationParameters")
        native = parameters._native_value()
        value.presentation_parameters = native


class PreparingDeviceSettingsEventArgs:
    def __init__(self, graphicsDeviceInformation: GraphicsDeviceInformation) -> None:
        if not isinstance(graphicsDeviceInformation, GraphicsDeviceInformation):
            raise TypeError("graphicsDeviceInformation must be GraphicsDeviceInformation")
        self._information = graphicsDeviceInformation

    @property
    def GraphicsDeviceInformation(self) -> GraphicsDeviceInformation:
        return self._information


class GraphicsDeviceManager(IGraphicsDeviceManager, IGraphicsDeviceService):
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
        self._event_callbacks: list[object] = []
        self._event_registrations: list[int] = []
        game._attach_graphics_manager(self)
        game.Services.AddService(IGraphicsDeviceManager, self)
        game.Services.AddService(IGraphicsDeviceService, self)

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
    IsFullScreen = _property("IsFullScreen", _strict_bool)
    SynchronizeWithVerticalRetrace = _property("SynchronizeWithVerticalRetrace", _strict_bool)
    PreferMultiSampling = _property("PreferMultiSampling", _strict_bool)
    SupportedOrientations = _property("SupportedOrientations", DisplayOrientation)

    def _create_native(self, host: object) -> None:
        output = c.c_uint64()
        library = get_library()
        library.check(library.cna_graphics_device_manager_create(host.handle, c.byref(output)),
                      "cna_graphics_device_manager_create")
        self._handle = int(output.value)
        self._subscribe_native_events()
        for name, value in self._values.items():
            operation = self._setters[name]
            library.check(getattr(library, operation)(self._handle, int(value)), operation)

    def _subscribe_native_events(self) -> None:
        library = get_library()
        events = (
            (0, self.Disposed), (1, self.OnDeviceCreated),
            (2, self.OnDeviceDisposing), (3, self.OnDeviceReset),
            (4, self.OnDeviceResetting),
        )
        for identity, method in events:
            @abi.CNA_GameEventCallback
            def callback(context, selected=method):
                try:
                    selected(self, None)
                except BaseException as error:
                    host = self._game._host
                    if host is not None and host.pending_exception is None:
                        host.pending_exception = error
            registration = c.c_uint64()
            library.check(library.cna_graphics_device_manager_subscribe(
                self._handle, identity, callback, None, c.byref(registration)),
                "cna_graphics_device_manager_subscribe")
            self._event_callbacks.append(callback)
            self._event_registrations.append(int(registration.value))

        @abi.CNA_PreparingDeviceSettingsMutatorEXT
        def preparing(information, context):
            try:
                value = GraphicsDeviceInformation._from_native(information.contents, self)
                self.OnPreparingDeviceSettings(
                    self, PreparingDeviceSettingsEventArgs(value))
                value._write_native(information.contents)
            except BaseException as error:
                host = self._game._host
                if host is not None and host.pending_exception is None:
                    host.pending_exception = error
        registration = c.c_uint64()
        library.check(library.cna_graphics_device_manager_subscribe_preparing_device_settings_ext(
            self._handle, preparing, None, c.byref(registration)),
            "cna_graphics_device_manager_subscribe_preparing_device_settings_ext")
        self._event_callbacks.append(preparing)
        self._event_registrations.append(int(registration.value))

    def _unsubscribe_native_events(self) -> None:
        library = get_library(); first_error = None
        for registration in reversed(self._event_registrations):
            try:
                library.check(library.cna_game_unsubscribe(registration),
                              "cna_game_unsubscribe")
            except BaseException as error:
                first_error = first_error or error
        self._event_registrations.clear(); self._event_callbacks.clear()
        if first_error is not None: raise first_error

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
        if not self._handle: self._game._ensure_host()
        library = get_library()
        library.check(library.cna_graphics_device_manager_create_device(self._handle),
                      "cna_graphics_device_manager_create_device")

    def BeginDraw(self) -> bool:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        if not self._handle: self._game._ensure_host()
        should_draw = c.c_uint8(); library = get_library()
        library.check(library.cna_graphics_device_manager_begin_draw(
            self._handle, c.byref(should_draw)), "cna_graphics_device_manager_begin_draw")
        return should_draw.value != 0

    def EndDraw(self) -> None:
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        if not self._handle: self._game._ensure_host()
        library = get_library()
        library.check(library.cna_graphics_device_manager_end_draw(self._handle),
                      "cna_graphics_device_manager_end_draw")

    def CanResetDevice(self, newDeviceInfo: GraphicsDeviceInformation) -> bool:
        if not isinstance(newDeviceInfo, GraphicsDeviceInformation):
            raise TypeError("newDeviceInfo must be GraphicsDeviceInformation")
        return self.GraphicsDevice.GraphicsProfile == newDeviceInfo.GraphicsProfile

    def FindBestDevice(self, anySuitableDevice: bool) -> GraphicsDeviceInformation:
        if type(anySuitableDevice) is not bool:
            raise TypeError("anySuitableDevice must be bool")
        if not self._handle: self._game._ensure_host()
        result = GraphicsDeviceInformation()
        result.Adapter = self._graphics_device.Adapter
        result.GraphicsProfile = self.GraphicsProfile
        result.PresentationParameters = self._graphics_device.PresentationParameters.Clone()
        return result

    def RankDevices(self, foundDevices: List[GraphicsDeviceInformation]) -> None:
        if not isinstance(foundDevices, list):
            raise TypeError("foundDevices must be list[GraphicsDeviceInformation]")
        if not all(isinstance(value, GraphicsDeviceInformation) for value in foundDevices):
            raise TypeError("foundDevices must contain GraphicsDeviceInformation values")
        preferred_profile = self.GraphicsProfile
        foundDevices.sort(key=lambda value: (
            value.GraphicsProfile != preferred_profile,
            value.Adapter is None or not value.Adapter.IsDefaultAdapter,
            value.PresentationParameters.BackBufferFormat != self.PreferredBackBufferFormat,
        ))

    def OnDeviceCreated(self, sender: object, args: object) -> None:
        self.DeviceCreated(sender, args)
    def OnDeviceDisposing(self, sender: object, args: object) -> None:
        self.DeviceDisposing(sender, args)
    def OnDeviceReset(self, sender: object, args: object) -> None:
        self.DeviceReset(sender, args)
    def OnDeviceResetting(self, sender: object, args: object) -> None:
        self.DeviceResetting(sender, args)
    def OnPreparingDeviceSettings(self, sender: object,
                                  args: PreparingDeviceSettingsEventArgs) -> None:
        self.PreparingDeviceSettings(sender, args)

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if args and not args[0]:
            return
        if self._disposed:
            return
        if self._handle:
            library = get_library()
            first_error = None
            try:
                library.check(library.cna_graphics_device_manager_dispose(self._handle),
                              "cna_graphics_device_manager_dispose")
            except BaseException as error:
                first_error = error
            for action in (self._unsubscribe_native_events,
                           self._graphics_device._release_device_events):
                try: action()
                except BaseException as error: first_error = first_error or error
            try:
                library.check(library.cna_graphics_device_manager_destroy(self._handle),
                              "cna_graphics_device_manager_destroy")
            except BaseException as error:
                first_error = first_error or error
            self._handle = 0
            if first_error is not None: raise first_error
        self._graphics_device._disposed = True
        self._disposed = True
        self._game.Services.RemoveService(IGraphicsDeviceManager)
        self._game.Services.RemoveService(IGraphicsDeviceService)

    def __enter__(self) -> "GraphicsDeviceManager":
        if self._disposed:
            raise RuntimeError("GraphicsDeviceManager is disposed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.Dispose()


GraphicsDeviceManager.__xna_arities__ = {"Dispose": {0, 1}}
