"""Managed XNA game components, services, launch parameters, and window facade."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping, MutableSequence
import ctypes as c
from typing import TYPE_CHECKING

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from ._geometry import Rectangle
from ._language import Event
from ._numeric import int32

if TYPE_CHECKING:
    from ._game import DisplayOrientation, Game, GameTime


def _string_view(value: str, *, name: str) -> tuple[bytes, abi.CNA_StringView]:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if "\0" in value:
        raise ValueError(f"{name} cannot contain NUL")
    encoded = value.encode("utf-8", errors="strict")
    return encoded, abi.CNA_StringView(encoded, len(encoded))


def _copy_native_string(library: object, handle: int, size_name: str, copy_name: str,
                        *prefix: object) -> str:
    size = c.c_uint64()
    operation = size_name
    library.check(getattr(library, operation)(handle, *prefix, c.byref(size)), operation)
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    operation = copy_name
    library.check(
        getattr(library, operation)(handle, *prefix, buffer, size.value, c.byref(written)),
        operation,
    )
    return bytes(buffer.raw[:written.value]).decode("utf-8", errors="strict")


class IGameComponent:
    def Initialize(self) -> None:
        raise NotImplementedError


class IUpdateable:
    EnabledChanged = Event()
    UpdateOrderChanged = Event()

    @property
    def Enabled(self) -> bool:
        raise NotImplementedError

    @property
    def UpdateOrder(self) -> int:
        raise NotImplementedError

    def Update(self, gameTime: "GameTime") -> None:
        raise NotImplementedError


class IDrawable:
    VisibleChanged = Event()
    DrawOrderChanged = Event()

    @property
    def Visible(self) -> bool:
        raise NotImplementedError

    @property
    def DrawOrder(self) -> int:
        raise NotImplementedError

    def Draw(self, gameTime: "GameTime") -> None:
        raise NotImplementedError


class GameComponent(IGameComponent, IUpdateable):
    EnabledChanged = Event()
    UpdateOrderChanged = Event()
    Disposed = Event()

    def __init__(self, game: "Game") -> None:
        from ._game import Game
        if not isinstance(game, Game):
            raise TypeError("game must be a Game")
        self._game = game
        self._enabled = True
        self._update_order = 0
        self._disposed = False
        self._initialized = False

    @property
    def Game(self) -> "Game":
        return self._game

    @property
    def Enabled(self) -> bool:
        return self._enabled

    @Enabled.setter
    def Enabled(self, value: bool) -> None:
        if self._disposed:
            raise RuntimeError("GameComponent is disposed")
        if type(value) is not bool:
            raise TypeError("Enabled must be bool")
        if self._enabled != value:
            self._enabled = value
            self.OnEnabledChanged(self, None)

    @property
    def UpdateOrder(self) -> int:
        return self._update_order

    @UpdateOrder.setter
    def UpdateOrder(self, value: int) -> None:
        if self._disposed:
            raise RuntimeError("GameComponent is disposed")
        converted = int32(value, name="UpdateOrder")
        if self._update_order != converted:
            self._update_order = converted
            self.OnUpdateOrderChanged(self, None)

    def Initialize(self) -> None:
        self._initialized = True

    def Update(self, gameTime: "GameTime") -> None:
        from ._game import GameTime
        if not isinstance(gameTime, GameTime):
            raise TypeError("gameTime must be GameTime")

    def OnUpdateOrderChanged(self, sender: object, args: object) -> None:
        self.UpdateOrderChanged(sender, args)

    def OnEnabledChanged(self, sender: object, args: object) -> None:
        self.EnabledChanged(sender, args)

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if args and not args[0]:
            return
        if self._disposed:
            return
        self.Game.Components.Remove(self)
        self._disposed = True
        self.Disposed(self, None)

    def __enter__(self) -> "GameComponent":
        if self._disposed:
            raise RuntimeError("GameComponent is disposed")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.Dispose()


class DrawableGameComponent(GameComponent, IDrawable):
    VisibleChanged = Event()
    DrawOrderChanged = Event()

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._visible = True
        self._draw_order = 0
        self._content_loaded = False

    @property
    def GraphicsDevice(self):
        return self.Game.GraphicsDevice

    @property
    def Visible(self) -> bool:
        return self._visible

    @Visible.setter
    def Visible(self, value: bool) -> None:
        if self._disposed:
            raise RuntimeError("DrawableGameComponent is disposed")
        if type(value) is not bool:
            raise TypeError("Visible must be bool")
        if self._visible != value:
            self._visible = value
            self.OnVisibleChanged(self, None)

    @property
    def DrawOrder(self) -> int:
        return self._draw_order

    @DrawOrder.setter
    def DrawOrder(self, value: int) -> None:
        if self._disposed:
            raise RuntimeError("DrawableGameComponent is disposed")
        converted = int32(value, name="DrawOrder")
        if self._draw_order != converted:
            self._draw_order = converted
            self.OnDrawOrderChanged(self, None)

    def Initialize(self) -> None:
        super().Initialize()
        if not self._content_loaded:
            self.LoadContent()
            self._content_loaded = True

    def Draw(self, gameTime: "GameTime") -> None:
        from ._game import GameTime
        if not isinstance(gameTime, GameTime):
            raise TypeError("gameTime must be GameTime")

    def LoadContent(self) -> None:
        return None

    def UnloadContent(self) -> None:
        return None

    def OnDrawOrderChanged(self, sender: object, args: object) -> None:
        self.DrawOrderChanged(sender, args)

    def OnVisibleChanged(self, sender: object, args: object) -> None:
        self.VisibleChanged(sender, args)

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self._disposed:
            return
        if not args or args[0]:
            self.UnloadContent()
            self._content_loaded = False
        super().Dispose(*(args or (True,)))


class _ComponentSequence(MutableSequence[IGameComponent]):
    @property
    def Count(self) -> int:
        return len(self)

    def Add(self, item: IGameComponent) -> None:
        self.InsertItem(len(self), item)

    def Remove(self, item: IGameComponent) -> bool:
        try:
            index = next(index for index, value in enumerate(self) if value == item)
        except StopIteration:
            return False
        self.RemoveItem(index)
        return True

    def Clear(self) -> None:
        self.ClearItems()


class GameComponentCollection(_ComponentSequence):
    ComponentAdded = Event()
    ComponentRemoved = Event()

    def __init__(self) -> None:
        self._items: list[IGameComponent] = []

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def __setitem__(self, index, item) -> None:
        if isinstance(index, slice):
            raise TypeError("slice assignment is not part of GameComponentCollection")
        self.SetItem(index, item)

    def __delitem__(self, index) -> None:
        if isinstance(index, slice):
            for value in reversed(range(*index.indices(len(self)))):
                self.RemoveItem(value)
            return
        self.RemoveItem(index)

    def insert(self, index: int, item: IGameComponent) -> None:
        self.InsertItem(index, item)

    @staticmethod
    def _validate(item: object) -> IGameComponent:
        if not isinstance(item, IGameComponent):
            raise TypeError("item must implement IGameComponent")
        return item

    def InsertItem(self, index: int, item: IGameComponent) -> None:
        converted = int32(index, name="index")
        if converted < 0 or converted > len(self._items):
            raise IndexError("index is outside the collection")
        value = self._validate(item)
        if any(current == value for current in self._items):
            raise ValueError("the same component cannot be added more than once")
        self._items.insert(converted, value)
        self.ComponentAdded(self, GameComponentCollectionEventArgs(value))

    def RemoveItem(self, index: int) -> None:
        converted = int32(index, name="index")
        if converted < 0 or converted >= len(self._items):
            raise IndexError("index is outside the collection")
        value = self._items.pop(converted)
        self.ComponentRemoved(self, GameComponentCollectionEventArgs(value))

    def SetItem(self, index: int, item: IGameComponent) -> None:
        raise RuntimeError("items cannot be replaced in a GameComponentCollection")

    def ClearItems(self) -> None:
        index = 0
        while index < len(self._items):
            self.ComponentRemoved(
                self, GameComponentCollectionEventArgs(self._items[index]))
            index += 1
        self._items.clear()


class GameComponentCollectionEventArgs:
    def __init__(self, gameComponent: IGameComponent) -> None:
        if not isinstance(gameComponent, IGameComponent):
            raise TypeError("gameComponent must implement IGameComponent")
        self._game_component = gameComponent

    @property
    def GameComponent(self) -> IGameComponent:
        return self._game_component


class GameServiceContainer:
    def __init__(self) -> None:
        self._services: dict[type, object] = {}

    @staticmethod
    def _service_type(value: object) -> type:
        if not isinstance(value, type):
            raise TypeError("service type token must be a Python class")
        return value

    def AddService(self, type: type, provider: object) -> None:
        service_type = self._service_type(type)
        if provider is None:
            raise TypeError("provider cannot be None")
        if not isinstance(provider, service_type):
            raise ValueError("provider does not implement the registered service type")
        if service_type in self._services:
            raise ValueError("a service is already registered for this type")
        self._services[service_type] = provider

    def GetService(self, type: type) -> object:
        return self._services.get(self._service_type(type))

    def RemoveService(self, type: type) -> None:
        self._services.pop(self._service_type(type), None)


class _StringDictionary(MutableMapping[str, str]):
    def Add(self, key: str, value: str) -> None:
        if key in self:
            raise ValueError("the key is already present")
        self[key] = value

    def ContainsKey(self, key: str) -> bool:
        return key in self

    @property
    def Count(self) -> int:
        return len(self)


class LaunchParameters(_StringDictionary):
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._game: Game | None = None

    @staticmethod
    def _entry(value: object, name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be str")
        if "\0" in value:
            raise ValueError(f"{name} cannot contain NUL")
        return value

    def __getitem__(self, key: str) -> str:
        return self._values[self._entry(key, "key")]

    def __setitem__(self, key: str, value: str) -> None:
        key = self._entry(key, "key")
        value = self._entry(value, "value")
        if self._game is not None and self._game._host is not None and self._game._host.handle:
            key_bytes, key_view = _string_view(key, name="key")
            value_bytes, value_view = _string_view(value, name="value")
            library = self._game._host.library
            library.check(
                library.cna_game_launch_parameters_add(self._game._host.handle, key_view, value_view),
                "cna_game_launch_parameters_add",
            )
            del key_bytes, value_bytes
        self._values[key] = value

    def __delitem__(self, key: str) -> None:
        key = self._entry(key, "key")
        if self._game is not None and self._game._host is not None and self._game._host.handle:
            raise NativeCapabilityError(
                "LaunchParameters.Remove", 6, None,
                "CNA ABI 0.7 has no launch-parameter removal route after native game creation",
            )
        del self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(tuple(self._values))

    def __len__(self) -> int:
        return len(self._values)

    def _attach_native(self, game: "Game") -> None:
        pending = tuple(self._values.items())
        self._game = game
        host = game._host
        if host is None or not host.handle:
            return
        library = host.library
        count = c.c_uint64()
        library.check(
            library.cna_game_launch_parameters_get_count(host.handle, c.byref(count)),
            "cna_game_launch_parameters_get_count",
        )
        self._values.clear()
        for index in range(count.value):
            key = _copy_native_string(
                library, host.handle,
                "cna_game_launch_parameters_get_key_size",
                "cna_game_launch_parameters_copy_key",
                index,
            )
            key_bytes, key_view = _string_view(key, name="key")
            value = _copy_native_string(
                library, host.handle,
                "cna_game_launch_parameters_get_value_size",
                "cna_game_launch_parameters_copy_value",
                key_view,
            )
            del key_bytes
            self._values[key] = value
        for key, value in pending:
            self[key] = value


class GameWindow:
    ScreenDeviceNameChanged = Event()
    ClientSizeChanged = Event()
    OrientationChanged = Event()

    def __init__(self, game: "Game", _token: object = None) -> None:
        if _token is not game:
            raise TypeError("GameWindow instances are created by Game")
        self._game = game
        self._title = type(game).__name__
        self._allow_user_resizing = False

    def _native(self) -> tuple[object, int] | None:
        host = self._game._host
        return None if host is None or not host.handle else (host.library, host.handle)

    @property
    def Title(self) -> str:
        native = self._native()
        if native is None:
            return self._title
        return _copy_native_string(native[0], native[1], "cna_game_window_get_title_size",
                                   "cna_game_window_copy_title")

    @Title.setter
    def Title(self, value: str) -> None:
        self.SetTitle(value)

    def SetTitle(self, title: str) -> None:
        encoded, view = _string_view(title, name="title")
        native = self._native()
        if native is not None:
            native[0].check(native[0].cna_game_set_window_title(native[1], view),
                            "cna_game_set_window_title")
        self._title = title
        del encoded

    @property
    def Handle(self) -> int:
        native = self._native()
        if native is None:
            return 0
        value = c.c_uint64()
        native[0].check(native[0].cna_game_window_get_native_handle_ext(native[1], c.byref(value)),
                        "cna_game_window_get_native_handle_ext")
        return int(value.value)

    @property
    def AllowUserResizing(self) -> bool:
        native = self._native()
        if native is None:
            return self._allow_user_resizing
        value = c.c_uint8()
        native[0].check(native[0].cna_game_window_get_allow_user_resizing(native[1], c.byref(value)),
                        "cna_game_window_get_allow_user_resizing")
        return value.value != 0

    @AllowUserResizing.setter
    def AllowUserResizing(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("AllowUserResizing must be bool")
        native = self._native()
        if native is not None:
            native[0].check(native[0].cna_game_window_set_allow_user_resizing(native[1], value),
                            "cna_game_window_set_allow_user_resizing")
        self._allow_user_resizing = value

    @property
    def ClientBounds(self) -> Rectangle:
        native = self._native()
        if native is None:
            return Rectangle()
        value = abi.CNA_Rectangle()
        native[0].check(native[0].cna_game_window_get_client_bounds(native[1], c.byref(value)),
                        "cna_game_window_get_client_bounds")
        return Rectangle(value.x, value.y, value.width, value.height)

    @property
    def CurrentOrientation(self) -> "DisplayOrientation":
        from ._game import DisplayOrientation
        native = self._native()
        if native is None:
            return DisplayOrientation.Default
        value = c.c_uint32()
        native[0].check(native[0].cna_game_window_get_current_orientation(native[1], c.byref(value)),
                        "cna_game_window_get_current_orientation")
        return DisplayOrientation(value.value)

    @property
    def ScreenDeviceName(self) -> str:
        native = self._native()
        if native is None:
            return ""
        return _copy_native_string(
            native[0], native[1],
            "cna_game_window_get_screen_device_name_size",
            "cna_game_window_copy_screen_device_name",
        )

    def BeginScreenDeviceChange(self, willBeFullScreen: bool) -> None:
        if type(willBeFullScreen) is not bool:
            raise TypeError("willBeFullScreen must be bool")
        host = self._game._ensure_host()
        host.library.check(
            host.library.cna_game_window_begin_screen_device_change(host.handle, willBeFullScreen),
            "cna_game_window_begin_screen_device_change",
        )

    def EndScreenDeviceChange(self, *args: object) -> None:
        if len(args) == 1:
            screenDeviceName, clientWidth, clientHeight = args[0], 0, 0
        elif len(args) == 3:
            screenDeviceName, clientWidth, clientHeight = args
        else:
            raise TypeError("EndScreenDeviceChange expects one or three arguments")
        encoded, view = _string_view(screenDeviceName, name="screenDeviceName")
        width = int32(clientWidth, name="clientWidth")
        height = int32(clientHeight, name="clientHeight")
        host = self._game._ensure_host()
        host.library.check(
            host.library.cna_game_window_end_screen_device_change(
                host.handle, view, width, height
            ),
            "cna_game_window_end_screen_device_change",
        )
        del encoded

    def SetSupportedOrientations(self, orientations: "DisplayOrientation") -> None:
        from ._game import DisplayOrientation
        value = DisplayOrientation(orientations)
        manager = self._game._graphics_manager
        if manager is None:
            self._game._window_supported_orientations = value
        else:
            manager.SupportedOrientations = value

    def OnActivated(self) -> None:
        return None

    def OnDeactivated(self) -> None:
        return None

    def OnPaint(self) -> None:
        return None

    def OnScreenDeviceNameChanged(self) -> None:
        self.ScreenDeviceNameChanged(self, None)

    def OnClientSizeChanged(self) -> None:
        self.ClientSizeChanged(self, None)

    def OnOrientationChanged(self) -> None:
        self.OrientationChanged(self, None)

    def _attach_native(self) -> None:
        host = self._game._host
        if host is None or not host.handle:
            return
        encoded, view = _string_view(self._title, name="Title")
        host.library.check(host.library.cna_game_set_window_title(host.handle, view),
                           "cna_game_set_window_title")
        del encoded


GameComponent.__xna_arities__ = {"Dispose": {0, 1}}
DrawableGameComponent.__xna_arities__ = {"Dispose": {0, 1}}
GameWindow.__xna_arities__ = {"EndScreenDeviceChange": {1, 3}}
