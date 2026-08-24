"""XNA touch values plus the canonical CNA ABI-0.7 touch panel."""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
from enum import IntEnum, IntFlag
from collections.abc import MutableSequence, Sequence

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import live_game

from ... import DisplayOrientation, Vector2
from ..._language import classproperty, staticproperty, staticpropertymeta
from ..._numeric import f32, hash32_sum, int32, single_hash


class GestureType(IntFlag):
    None_ = 0
    Tap = 1
    DoubleTap = 2
    Hold = 4
    HorizontalDrag = 8
    VerticalDrag = 16
    FreeDrag = 32
    Pinch = 64
    Flick = 128
    DragComplete = 256
    PinchComplete = 512


class TouchLocationState(IntEnum):
    Invalid = 0
    Released = 1
    Pressed = 2
    Moved = 3


def _vector(value: object, name: str) -> Vector2:
    if not isinstance(value, Vector2):
        raise TypeError(f"{name} must be Vector2")
    return Vector2(value.X, value.Y)


class GestureSample:
    __slots__ = ("_gesture_type", "_timestamp", "_position", "_position2", "_delta", "_delta2")

    def __init__(self, *args: object) -> None:
        if not args:
            gestureType, timestamp = GestureType.None_, timedelta()
            position = position2 = delta = delta2 = Vector2()
        elif len(args) == 6:
            gestureType, timestamp, position, position2, delta, delta2 = args
        else:
            raise TypeError("GestureSample expects zero or six arguments")
        try:
            selected = GestureType(gestureType)
        except (TypeError, ValueError) as error:
            raise ValueError("gestureType contains an undefined bit") from error
        if int(selected) & ~0x3FF:
            raise ValueError("gestureType contains an undefined bit")
        if not isinstance(timestamp, timedelta):
            raise TypeError("timestamp must be datetime.timedelta")
        self._gesture_type, self._timestamp = selected, timestamp
        self._position = _vector(position, "position")
        self._position2 = _vector(position2, "position2")
        self._delta = _vector(delta, "delta")
        self._delta2 = _vector(delta2, "delta2")

    @property
    def GestureType(self) -> GestureType: return self._gesture_type
    @property
    def Timestamp(self) -> timedelta: return self._timestamp
    @property
    def Position(self) -> Vector2: return _vector(self._position, "Position")
    @property
    def Position2(self) -> Vector2: return _vector(self._position2, "Position2")
    @property
    def Delta(self) -> Vector2: return _vector(self._delta, "Delta")
    @property
    def Delta2(self) -> Vector2: return _vector(self._delta2, "Delta2")

    @classmethod
    def _from_native(cls, value: abi.CNA_GestureSample) -> "GestureSample":
        return cls(
            GestureType(value.gesture_type), timedelta(microseconds=value.timestamp_ticks / 10),
            Vector2(value.position.x, value.position.y),
            Vector2(value.position2.x, value.position2.y),
            Vector2(value.delta.x, value.delta.y), Vector2(value.delta2.x, value.delta2.y),
        )

    def __copy__(self):
        return GestureSample(self.GestureType, self.Timestamp, self.Position, self.Position2,
                             self.Delta, self.Delta2)
    __deepcopy__ = lambda self, memo: self.__copy__()


class TouchLocation:
    __slots__ = ("_id", "_state", "_position", "_previous_state", "_previous_position")

    def __init__(self, *args: object) -> None:
        if not args:
            identity, state, position = 0, TouchLocationState.Invalid, Vector2()
            previous_state, previous_position = TouchLocationState.Invalid, Vector2()
        elif len(args) == 3:
            identity, state, position = args
            previous_state, previous_position = TouchLocationState.Invalid, Vector2()
        elif len(args) == 5:
            identity, state, position, previous_state, previous_position = args
        else:
            raise TypeError("TouchLocation expects zero, three, or five arguments")
        self._id = int32(identity, name="id")
        try:
            self._state = TouchLocationState(state)
            self._previous_state = TouchLocationState(previous_state)
        except (TypeError, ValueError) as error:
            raise ValueError("touch location state is invalid") from error
        self._position = _vector(position, "position")
        self._previous_position = _vector(previous_position, "previousPosition")

    @property
    def State(self) -> TouchLocationState: return self._state
    @property
    def Id(self) -> int: return self._id
    @property
    def Position(self) -> Vector2: return _vector(self._position, "Position")

    def TryGetPreviousLocation(self) -> tuple[bool, "TouchLocation"]:
        if self._previous_state is TouchLocationState.Invalid:
            return False, TouchLocation(-1, TouchLocationState.Invalid, Vector2())
        return True, TouchLocation(self.Id, self._previous_state, self._previous_position)

    def Equals(self, other: object) -> bool:
        return (isinstance(other, TouchLocation) and self.Id == other.Id
                and self._position == other._position
                and self._previous_position == other._previous_position)

    def GetHashCode(self) -> int:
        return hash32_sum(self.Id, single_hash(self._position.X), single_hash(self._position.Y))

    def ToString(self) -> str:
        return f"{{Position:{self._position.ToString()}}}"
    __str__ = ToString
    def __hash__(self) -> int: return self.GetHashCode()
    def __eq__(self, other: object) -> bool:
        return (isinstance(other, TouchLocation) and self.Id == other.Id
                and self.State is other.State and self._position == other._position
                and self._previous_state is other._previous_state
                and self._previous_position == other._previous_position)
    def __ne__(self, other: object) -> bool: return not self == other
    def __copy__(self):
        return TouchLocation(self.Id, self.State, self._position,
                             self._previous_state, self._previous_position)
    __deepcopy__ = lambda self, memo: self.__copy__()

    @classmethod
    def _from_native(cls, value: abi.CNA_TouchLocation) -> "TouchLocation":
        return cls(value.id, TouchLocationState(value.state),
                   Vector2(value.position.x, value.position.y),
                   TouchLocationState(value.previous_state),
                   Vector2(value.previous_position.x, value.previous_position.y))


class TouchCollection:
    __slots__ = ("_locations", "_connected")

    def __init__(self, *args: object) -> None:
        if not args:
            touches, connected = (), False
        elif len(args) == 1:
            touches, connected = args[0], True
            if touches is None or not isinstance(touches, Sequence):
                raise TypeError("touches must be a sequence of TouchLocation values")
            if len(touches) > 8:
                raise IndexError("touches contains more than eight locations")
        else:
            raise TypeError("TouchCollection expects zero or one argument")
        if not all(isinstance(value, TouchLocation) for value in touches):
            raise TypeError("touches must contain TouchLocation values")
        self._locations = tuple(value.__copy__() for value in touches)
        self._connected = connected

    @classmethod
    def _from_values(cls, values: Sequence[TouchLocation], connected: bool) -> "TouchCollection":
        self = cls.__new__(cls)
        self._locations = tuple(value.__copy__() for value in values)
        self._connected = bool(connected)
        return self

    @property
    def IsConnected(self) -> bool: return self._connected
    @property
    def Count(self) -> int: return len(self._locations)
    @property
    def IsReadOnly(self) -> bool: return True
    def __len__(self) -> int: return self.Count
    def __getitem__(self, index: int) -> TouchLocation:
        index = int32(index, name="index")
        if index < 0 or index >= self.Count:
            raise IndexError("index")
        return self._locations[index].__copy__()
    def __setitem__(self, index: int, item: TouchLocation) -> None:
        raise TypeError("TouchCollection is read-only")
    def FindById(self, id: int) -> tuple[bool, TouchLocation]:
        selected = int32(id, name="id")
        for value in self._locations:
            if value.Id == selected:
                return True, value.__copy__()
        return False, TouchLocation()
    def IndexOf(self, item: TouchLocation) -> int:
        if not isinstance(item, TouchLocation): raise TypeError("item must be TouchLocation")
        return next((index for index, value in enumerate(self._locations) if value == item), -1)
    def Contains(self, item: TouchLocation) -> bool: return self.IndexOf(item) >= 0
    @staticmethod
    def _read_only() -> None: raise TypeError("TouchCollection is read-only")
    def Insert(self, index: int, item: TouchLocation) -> None: self._read_only()
    def RemoveAt(self, index: int) -> None: self._read_only()
    def Add(self, item: TouchLocation) -> None: self._read_only()
    def Clear(self) -> None: self._read_only()
    def Remove(self, item: TouchLocation) -> bool: self._read_only()
    def CopyTo(self, array: MutableSequence[TouchLocation], arrayIndex: int) -> None:
        if not isinstance(array, MutableSequence):
            raise TypeError("array must be a mutable sequence")
        start = int32(arrayIndex, name="arrayIndex")
        if start < 0 or start + self.Count > len(array):
            raise IndexError("arrayIndex")
        for index, value in enumerate(self._locations):
            array[start + index] = value.__copy__()
    def GetEnumerator(self) -> "TouchCollection.Enumerator":
        return TouchCollection.Enumerator._from_collection(self)
    def __iter__(self): return self.GetEnumerator()
    def __copy__(self): return TouchCollection._from_values(self._locations, self.IsConnected)
    __deepcopy__ = lambda self, memo: self.__copy__()

    class Enumerator:
        __slots__ = ("_collection", "_position")
        def __init__(self) -> None:
            self._collection, self._position = TouchCollection(), 0
        @classmethod
        def _from_collection(cls, collection: "TouchCollection"):
            self = cls.__new__(cls)
            self._collection, self._position = collection.__copy__(), -1
            return self
        @property
        def Current(self) -> TouchLocation: return self._collection[self._position]
        def MoveNext(self) -> bool:
            self._position += 1
            if self._position >= self._collection.Count:
                self._position = self._collection.Count
                return False
            return True
        def Dispose(self) -> None: return None
        def __iter__(self): return self
        def __next__(self) -> TouchLocation:
            if not self.MoveNext(): raise StopIteration
            return self.Current
        def __copy__(self):
            self_copy = type(self).__new__(type(self))
            self_copy._collection = self._collection.__copy__()
            self_copy._position = self._position
            return self_copy
        __deepcopy__ = lambda self, memo: self.__copy__()


class TouchPanelCapabilities:
    __slots__ = ("_connected", "_maximum")
    def __init__(self) -> None:
        self._connected, self._maximum = False, 0
    @classmethod
    def _from_native(cls, value: abi.CNA_TouchCapabilities):
        self = cls.__new__(cls)
        self._connected, self._maximum = value.is_connected != 0, int(value.maximum_touch_count)
        return self
    @property
    def IsConnected(self) -> bool: return self._connected
    @property
    def MaximumTouchCount(self) -> int: return self._maximum
    def __copy__(self):
        result = type(self)(); result._connected, result._maximum = self._connected, self._maximum
        return result
    __deepcopy__ = lambda self, memo: self.__copy__()


def _game_handle(operation: str) -> tuple[object, int]:
    game = live_game(operation)
    host = game._host
    return game, host.handle


def _get_u32(operation: str, result_type: type[c._SimpleCData] = c.c_uint32) -> int:
    _, handle = _game_handle(operation)
    value = result_type(); library = get_library()
    library.check(getattr(library, operation)(handle, c.byref(value)), operation)
    return int(value.value)


def _get_enabled(cls: type) -> GestureType:
    return GestureType(_get_u32("cna_touch_panel_get_enabled_gestures"))
_have_gestures_been_enabled = False
def _set_enabled(cls: type, value: object) -> None:
    global _have_gestures_been_enabled
    try: selected = GestureType(value)
    except (TypeError, ValueError) as error: raise ValueError("EnabledGestures is invalid") from error
    if int(selected) & ~0x3FF: raise ValueError("EnabledGestures contains an undefined bit")
    game, handle = _game_handle("cna_touch_panel_set_enabled_gestures")
    library = get_library(); library.check(
        library.cna_touch_panel_set_enabled_gestures(handle, int(selected)),
        "cna_touch_panel_set_enabled_gestures")
    _have_gestures_been_enabled = True
def _get_available(cls: type) -> bool:
    if not _have_gestures_been_enabled:
        raise RuntimeError("EnabledGestures must be set before querying gestures")
    _, handle = _game_handle("cna_touch_panel_get_is_gesture_available")
    value = c.c_uint8(); library = get_library(); library.check(
        library.cna_touch_panel_get_is_gesture_available(handle, c.byref(value)),
        "cna_touch_panel_get_is_gesture_available")
    return value.value != 0
def _get_window(cls: type) -> int:
    raw = _get_u32("cna_touch_panel_get_window_handle", c.c_uint64)
    return raw if raw <= 0x7FFFFFFFFFFFFFFF else raw - 0x10000000000000000
def _set_window(cls: type, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int): raise TypeError("WindowHandle must be an IntPtr integer")
    if not -0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF: raise OverflowError("WindowHandle is outside the 64-bit IntPtr range")
    _, handle = _game_handle("cna_touch_panel_set_window_handle"); library = get_library()
    library.check(library.cna_touch_panel_set_window_handle(handle, value & 0xFFFFFFFFFFFFFFFF),
                  "cna_touch_panel_set_window_handle")
def _get_orientation(cls: type) -> DisplayOrientation:
    return DisplayOrientation(_get_u32("cna_touch_panel_get_display_orientation"))
def _set_orientation(cls: type, value: object) -> None:
    try: selected = DisplayOrientation(value)
    except (TypeError, ValueError) as error: raise ValueError("DisplayOrientation is invalid") from error
    if selected not in (DisplayOrientation.Default, DisplayOrientation.LandscapeLeft,
                        DisplayOrientation.LandscapeRight, DisplayOrientation.Portrait):
        raise ValueError("DisplayOrientation must be one defined XNA orientation")
    _, handle = _game_handle("cna_touch_panel_set_display_orientation"); library = get_library()
    library.check(library.cna_touch_panel_set_display_orientation(handle, int(selected)),
                  "cna_touch_panel_set_display_orientation")
def _get_width(cls: type) -> int: return _get_u32("cna_touch_panel_get_display_width", c.c_int32)
def _set_width(cls: type, value: object) -> None:
    selected = int32(value, name="DisplayWidth"); _, handle = _game_handle("cna_touch_panel_set_display_width")
    library = get_library(); library.check(library.cna_touch_panel_set_display_width(handle, selected), "cna_touch_panel_set_display_width")
def _get_height(cls: type) -> int: return _get_u32("cna_touch_panel_get_display_height", c.c_int32)
def _set_height(cls: type, value: object) -> None:
    selected = int32(value, name="DisplayHeight"); _, handle = _game_handle("cna_touch_panel_set_display_height")
    library = get_library(); library.check(library.cna_touch_panel_set_display_height(handle, selected), "cna_touch_panel_set_display_height")


class TouchPanel(metaclass=staticpropertymeta):
    EnabledGestures = staticproperty(_get_enabled, _set_enabled)
    IsGestureAvailable = classproperty(_get_available)
    WindowHandle = staticproperty(_get_window, _set_window)
    DisplayOrientation = staticproperty(_get_orientation, _set_orientation)
    DisplayWidth = staticproperty(_get_width, _set_width)
    DisplayHeight = staticproperty(_get_height, _set_height)
    def __new__(cls): raise TypeError("TouchPanel is static")
    @staticmethod
    def GetCapabilities() -> TouchPanelCapabilities:
        _, handle = _game_handle("cna_touch_get_capabilities")
        value = abi.CNA_TouchCapabilities(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_touch_get_capabilities(handle, c.byref(value)), "cna_touch_get_capabilities")
        return TouchPanelCapabilities._from_native(value)
    @staticmethod
    def GetState() -> TouchCollection:
        _, handle = _game_handle("cna_touch_get_state")
        value = abi.CNA_TouchState(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_touch_get_state(handle, c.byref(value)), "cna_touch_get_state")
        locations = [TouchLocation._from_native(value.touches[index]) for index in range(value.touch_count)]
        return TouchCollection._from_values(locations, value.is_connected != 0)
    @staticmethod
    def ReadGesture() -> GestureSample:
        if not _have_gestures_been_enabled:
            raise RuntimeError("EnabledGestures must be set before reading gestures")
        _, handle = _game_handle("cna_touch_panel_read_gesture")
        value = abi.CNA_GestureSample(); value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library(); library.check(library.cna_touch_panel_read_gesture(handle, c.byref(value)), "cna_touch_panel_read_gesture")
        return GestureSample._from_native(value)


def _attach_touch_game(game: object) -> None:
    """Associate CNA's process-static touch panel with this Game generation."""
    host = game._host
    get_library().check(
        get_library().cna_touch_panel_set_window_handle(host.handle, game.Window.Handle),
        "cna_touch_panel_set_window_handle",
    )


def _detach_touch_game(game: object) -> None:
    """Clear the generation-owned window identity before CNA destroys its Game."""
    host = game._host
    if host is not None and host.handle:
        get_library().check(
            get_library().cna_touch_panel_set_window_handle(host.handle, 0),
            "cna_touch_panel_set_window_handle",
        )


GestureSample.__xna_arities__ = {"__init__": {0, 6}}
TouchLocation.__xna_arities__ = {"__init__": {0, 3, 5}, "Equals": {1}}
TouchCollection.__xna_arities__ = {"__init__": {0, 1}}
