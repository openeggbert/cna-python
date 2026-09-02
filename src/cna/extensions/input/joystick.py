"""Raw joysticks: enumeration, capabilities, state and hotplug.

XNA has ``GamePad``, which is a *mapped* view of a controller: four buttons, two
sticks, two triggers, whatever the physical device is. A raw joystick is the
unmapped device -- however many axes, buttons, hats and balls it actually has --
and there is nowhere in ``Microsoft.Xna.Framework`` for that, which is why it is
here.

Two indexing schemes, kept apart
--------------------------------

Enumeration is by **index**, ``0..count-1``, and is stable only for as long as
nothing is plugged or unplugged. State and capabilities are by **instance id**,
which CNA assigns and which stays with a device. :class:`JoystickInfo` carries
the id so a caller can go from one to the other; nothing here ever passes an
index where an id belongs.

An empty list is host evidence. This machine has no joystick, and that is a
measurement, not a failure -- so nothing here fabricates a device.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, TYPE_CHECKING

from _cna_native import input_abi as _input
from _cna_native import input_support as _in
from _cna_native.family_support import CallbackRoot, checked

from .values import (
    JoystickCapabilities, JoystickHatPosition, JoystickInfo, JoystickType,
    PowerState,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game, Point

__all__ = [
    "JoystickState",
    "JoystickSubscription",
    "joystick_count",
    "joystick_name",
    "joystick_info",
    "joysticks",
    "joystick_capabilities",
    "capture_joystick_state",
    "on_joystick_connected",
    "on_joystick_disconnected",
    "callback_failures",
]

_support = _in.support
_VERSION = 1

#: Hotplug registrations are process-global: CNA's subscribe routes take no game
#: handle, so a registration outlives any one game and is released by closing it.
_roots = CallbackRoot()


def callback_failures() -> list:
    """``(handler, exception)`` for every hotplug handler that raised."""
    return list(_roots.failures)


class JoystickState:
    """One captured snapshot of a joystick's axes, balls, buttons and hats.

    A snapshot is an owned object because CNA makes it one; it is read as many
    times as the caller likes and closed when they are done. The counts and the
    copied ranges come from CNA, never from a guessed capacity: asking for a
    guessed number answers ``CNA_RESULT_BUFFER_TOO_SMALL`` rather than
    truncating, which is why the length is asked for first.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: int) -> None:
        self._handle = _support.handle(handle, "cna_joystick_state_destroy",
                                       "joystick state")

    @property
    def axis_count(self) -> int:
        return _support.out_u32("cna_joystick_state_get_axis_count",
                                self._handle.argument)

    @property
    def ball_count(self) -> int:
        return _support.out_u32("cna_joystick_state_get_ball_count",
                                self._handle.argument)

    @property
    def button_count(self) -> int:
        return _support.out_u32("cna_joystick_state_get_button_count",
                                self._handle.argument)

    @property
    def hat_count(self) -> int:
        return _support.out_u32("cna_joystick_state_get_hat_count",
                                self._handle.argument)

    @property
    def axes(self) -> tuple[int, ...]:
        """Every axis, as the signed 16-bit value the device reports."""
        values, count = _support.copied_values(
            c.c_int16, "cna_joystick_state_copy_axes", (self._handle.argument,))
        return tuple(int(values[index]) for index in range(count))

    @property
    def buttons(self) -> tuple[bool, ...]:
        values, count = _support.copied_values(
            c.c_uint8, "cna_joystick_state_copy_buttons", (self._handle.argument,))
        return tuple(bool(values[index]) for index in range(count))

    @property
    def hats(self) -> tuple[JoystickHatPosition, ...]:
        values, count = _support.copied_values(
            c.c_uint32, "cna_joystick_state_copy_hats", (self._handle.argument,))
        return tuple(JoystickHatPosition(int(values[index])) for index in range(count))

    @property
    def balls(self) -> tuple["Point", ...]:
        """Every trackball's relative motion since the last capture."""
        from Microsoft.Xna.Framework import Point

        values, count = _support.copied_values(
            _input.CNA_Point, "cna_joystick_state_copy_balls",
            (self._handle.argument,))
        return tuple(Point(int(values[index].x), int(values[index].y))
                     for index in range(count))

    def equals(self, other: "JoystickState") -> bool:
        """Whether CNA considers two snapshots equal."""
        if not isinstance(other, JoystickState):
            raise TypeError(
                f"other must be a JoystickState, not {type(other).__name__}")
        return _support.out_bool("cna_joystick_state_equals",
                                 self._handle.argument, other._handle.argument)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "JoystickState":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


class JoystickSubscription:
    """One live joystick hotplug registration."""

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
        _support.call("cna_joysticks_unsubscribe_ext", c.c_uint64(self._handle))

    def __enter__(self) -> "JoystickSubscription":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


def joystick_count(game: "Game") -> int:
    """How many joysticks the host reports. Zero is a real answer."""
    return _support.out_u32("cna_joysticks_get_count",
                            _in.game_handle(game, "joysticks"))


def joystick_name(game: "Game", index: int) -> str:
    """The name of the joystick at ``index``, by enumeration order."""
    return _support.sized_text(
        "cna_joysticks_get_name_size_at", "cna_joysticks_copy_name_at",
        (_in.game_handle(game, "joysticks"),
         c.c_uint32(checked(index, "uint32", "index"))), "joystick name")


def joystick_info(game: "Game", index: int) -> JoystickInfo:
    """The joystick at ``index``: its instance id, its kind and its name."""
    handle = _in.game_handle(game, "joysticks")
    native = _support.out_struct(
        _input.CNA_JoystickInfo, _VERSION, "cna_joysticks_get_info_at",
        handle, c.c_uint32(checked(index, "uint32", "index")))
    return JoystickInfo(int(native.id), JoystickType(int(native.type)),
                        joystick_name(game, index))


def joysticks(game: "Game") -> list[JoystickInfo]:
    """Every joystick the host reports, in CNA's enumeration order."""
    return [joystick_info(game, index) for index in range(joystick_count(game))]


def joystick_capabilities(game: "Game", joystick_id: int) -> JoystickCapabilities:
    """What one joystick has, **by instance id** rather than by index."""
    handle = _in.game_handle(game, "joysticks")
    identity = c.c_uint32(checked(joystick_id, "uint32", "joystick_id"))
    native = _support.out_struct(
        _input.CNA_JoystickCapabilities, _VERSION, "cna_joysticks_get_capabilities",
        handle, identity)
    percent = int(native.power_percent)
    return JoystickCapabilities(
        int(native.axis_count), int(native.button_count), int(native.hat_count),
        int(native.ball_count), JoystickType(int(native.type)),
        PowerState(int(native.power_state)),
        None if percent < 0 else percent, bool(native.is_connected),
        _support.sized_text("cna_joysticks_get_capabilities_name_size",
                            "cna_joysticks_copy_capabilities_name",
                            (handle, identity), "joystick name"),
        _support.sized_text("cna_joysticks_get_capabilities_guid_size",
                            "cna_joysticks_copy_capabilities_guid",
                            (handle, identity), "joystick guid"))


def capture_joystick_state(game: "Game", joystick_id: int) -> JoystickState:
    """Snapshots one joystick's current state, **by instance id**."""
    return JoystickState(_support.out_handle(
        "cna_joysticks_capture_state", _in.game_handle(game, "joysticks"),
        c.c_uint32(checked(joystick_id, "uint32", "joystick_id"))))


def _subscribe(route: str, handler: Callable[[int], None]) -> JoystickSubscription:
    if not callable(handler):
        raise TypeError("handler must be callable")
    key = object()

    def adapt(joystick_id, _context) -> None:
        handler(int(joystick_id))

    trampoline = _roots.root(key, _input.CNA_JoystickHotplugCallback, adapt)
    try:
        registration = _support.out_handle(route, trampoline, None)
    except BaseException:
        _roots.release(key)
        raise
    return JoystickSubscription(registration, key)


def on_joystick_connected(
        handler: Callable[[int], None]) -> JoystickSubscription:
    """Calls ``handler(joystick_id)`` when a joystick is plugged in."""
    return _subscribe("cna_joysticks_subscribe_connected_ext", handler)


def on_joystick_disconnected(
        handler: Callable[[int], None]) -> JoystickSubscription:
    """Calls ``handler(joystick_id)`` when a joystick is unplugged."""
    return _subscribe("cna_joysticks_subscribe_disconnected_ext", handler)
