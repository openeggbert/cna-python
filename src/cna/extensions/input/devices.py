"""Input-device enumeration, hotplug, and the sensors a device carries.

XNA assumes one keyboard and one mouse. A host can have several of each, and can
gain or lose one while a game runs, so enumeration and hotplug live here.

Also here: the sensors an *input device* carries -- a controller's own
accelerometer and gyroscope -- which are a different thing from the host's
sensors in :mod:`cna.extensions.devices.sensors`. CNA declares them in
``input_devices.h`` and this package keeps them there rather than folding two
different sources of the same physical quantity into one name.

Availability is reported, not inferred: the two gamepad sensor reads answer with
a value *and* whether the value means anything, and this module turns the second
into ``None`` rather than handing back a zero vector that looks like a reading.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, TYPE_CHECKING

from Microsoft.Xna.Framework import Vector3

from _cna_native import input_abi as _input
from _cna_native import input_support as _in
from _cna_native.family_support import CallbackRoot, checked

from .values import InputDeviceInfo, PowerState, SensorInfo, SensorType

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "DevicePower",
    "InputDeviceSubscription",
    "keyboards",
    "mice",
    "touch_devices",
    "keyboard_count",
    "mouse_count",
    "touch_device_count",
    "device_sensors",
    "device_sensor_count",
    "gamepad_acceleration",
    "gamepad_angular_velocity",
    "device_power",
    "on_keyboard_connected",
    "on_keyboard_disconnected",
    "on_mouse_connected",
    "on_mouse_disconnected",
    "callback_failures",
]

_support = _in.support
_VERSION = 1

_roots = CallbackRoot()


def callback_failures() -> list:
    """``(handler, exception)`` for every hotplug handler that raised."""
    return list(_roots.failures)


class DevicePower:
    """A device's power state, with the two unknown values as ``None``.

    CNA reports ``-1`` for an unknown percentage or an unknown remaining time,
    and that sentinel is turned into ``None`` here exactly once.
    """

    __slots__ = ("state", "seconds_remaining", "battery_percent")

    def __init__(self, state: PowerState, seconds_remaining: int | None,
                 battery_percent: int | None) -> None:
        self.state = state
        self.seconds_remaining = seconds_remaining
        self.battery_percent = battery_percent

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (f"DevicePower(state={self.state!r}, "
                f"seconds_remaining={self.seconds_remaining!r}, "
                f"battery_percent={self.battery_percent!r})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DevicePower):
            return NotImplemented
        return ((self.state, self.seconds_remaining, self.battery_percent)
                == (other.state, other.seconds_remaining, other.battery_percent))

    def __hash__(self) -> int:
        return hash((self.state, self.seconds_remaining, self.battery_percent))


class InputDeviceSubscription:
    """One live input-device hotplug registration."""

    __slots__ = ("_handle", "_key", "_closed")

    def __init__(self, handle: int, key: object) -> None:
        self._handle = int(handle)
        self._key = key
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _roots.release(self._key)
        _support.call("cna_input_devices_unsubscribe_ext", c.c_uint64(self._handle))

    def __enter__(self) -> "InputDeviceSubscription":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


def _count(route: str, game: "Game") -> int:
    return _support.out_u32(route, _in.game_handle(game, "input devices"))


def _devices(game: "Game", kind: str) -> list[InputDeviceInfo]:
    handle = _in.game_handle(game, "input devices")
    count = _support.out_u32(f"cna_input_devices_get_{kind}_count", handle)
    result = []
    for index in range(count):
        position = c.c_uint32(index)
        native = _support.out_struct(
            _input.CNA_InputDeviceInfo, _VERSION,
            f"cna_input_devices_get_{kind}_info_at", handle, position)
        result.append(InputDeviceInfo(
            int(native.id),
            _support.copied_text(f"cna_input_devices_copy_{kind}_name_at",
                                 (handle, position), "device name")))
    return result


def keyboard_count(game: "Game") -> int:
    """How many keyboards the host reports."""
    return _count("cna_input_devices_get_keyboard_count", game)


def mouse_count(game: "Game") -> int:
    """How many mice the host reports."""
    return _count("cna_input_devices_get_mouse_count", game)


def touch_device_count(game: "Game") -> int:
    """How many touch devices the host reports."""
    return _count("cna_input_devices_get_touch_device_count", game)


def keyboards(game: "Game") -> list[InputDeviceInfo]:
    """Every keyboard the host reports, in CNA's order."""
    return _devices(game, "keyboard")


def mice(game: "Game") -> list[InputDeviceInfo]:
    """Every mouse the host reports, in CNA's order."""
    return _devices(game, "mouse")


def touch_devices(game: "Game") -> list[InputDeviceInfo]:
    """Every touch device the host reports, in CNA's order."""
    return _devices(game, "touch_device")


def device_sensor_count(game: "Game") -> int:
    """How many sensors the host's input devices carry between them."""
    return _support.out_u32("cna_sensors_get_count",
                            _in.game_handle(game, "device sensors"))


def device_sensors(game: "Game") -> list[SensorInfo]:
    """Every sensor an input device carries, in CNA's order."""
    handle = _in.game_handle(game, "device sensors")
    count = _support.out_u32("cna_sensors_get_count", handle)
    result = []
    for index in range(count):
        position = c.c_uint32(index)
        native = _support.out_struct(
            _input.CNA_SensorInfo, _VERSION, "cna_sensors_get_info_at",
            handle, position)
        result.append(SensorInfo(
            int(native.id), SensorType(int(native.type)),
            _support.sized_text("cna_sensors_get_name_size_at",
                                "cna_sensors_copy_name_at", (handle, position),
                                "sensor name")))
    return result


def _sensor_vector(route: str, game: "Game") -> Vector3 | None:
    from _cna_native import abi

    value = abi.CNA_Vector3()
    available = c.c_uint8()
    _support.call(route, _in.game_handle(game, "device sensors"),
                  c.byref(value), c.byref(available))
    if not available.value:
        return None
    return Vector3(float(value.x), float(value.y), float(value.z))


def gamepad_acceleration(game: "Game") -> Vector3 | None:
    """The controller's own accelerometer, or ``None`` when it has none.

    ``None`` rather than a zero vector: a controller lying flat reports a real
    reading that is nearly zero on two axes, and a caller must be able to tell
    that apart from "there is no accelerometer".
    """
    return _sensor_vector("cna_sensors_get_accelerometer", game)


def gamepad_angular_velocity(game: "Game") -> Vector3 | None:
    """The controller's own gyroscope, or ``None`` when it has none."""
    return _sensor_vector("cna_sensors_get_gyroscope", game)


def device_power(game: "Game") -> DevicePower:
    """A device's power state, remaining seconds and battery percentage.

    All three come from one route, so they describe one moment rather than three
    separate ones.
    """
    state = c.c_uint32()
    seconds = c.c_int32()
    percent = c.c_int32()
    _support.call("cna_power_get_info", _in.game_handle(game, "device power"),
                  c.byref(state), c.byref(seconds), c.byref(percent))
    return DevicePower(
        PowerState(int(state.value)),
        None if seconds.value < 0 else int(seconds.value),
        None if percent.value < 0 else int(percent.value))


def _subscribe(route: str, handler: Callable[[int], None]) -> InputDeviceSubscription:
    if not callable(handler):
        raise TypeError("handler must be callable")
    key = object()

    def adapt(device_id, _context) -> None:
        handler(int(device_id))

    trampoline = _roots.root(key, _input.CNA_InputDeviceHotplugCallback, adapt)
    try:
        registration = _support.out_handle(route, trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    return InputDeviceSubscription(registration, key)


def on_keyboard_connected(handler: Callable[[int], None]) -> InputDeviceSubscription:
    """Calls ``handler(device_id)`` when a keyboard is plugged in."""
    return _subscribe("cna_input_devices_subscribe_keyboard_connected_ext", handler)


def on_keyboard_disconnected(
        handler: Callable[[int], None]) -> InputDeviceSubscription:
    """Calls ``handler(device_id)`` when a keyboard is unplugged."""
    return _subscribe("cna_input_devices_subscribe_keyboard_disconnected_ext", handler)


def on_mouse_connected(handler: Callable[[int], None]) -> InputDeviceSubscription:
    """Calls ``handler(device_id)`` when a mouse is plugged in."""
    return _subscribe("cna_input_devices_subscribe_mouse_connected_ext", handler)


def on_mouse_disconnected(handler: Callable[[int], None]) -> InputDeviceSubscription:
    """Calls ``handler(device_id)`` when a mouse is unplugged."""
    return _subscribe("cna_input_devices_subscribe_mouse_disconnected_ext", handler)
