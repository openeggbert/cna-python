"""Haptic devices: capabilities, rumble, and the full effect model.

XNA has ``GamePad.SetVibration``: two motors, one strength each. A haptic device
is the whole force-feedback model -- constant forces, periodic waveforms, ramps,
conditions, custom sample data, gain, autocentring, pause and resume -- and none
of it fits in ``Microsoft.Xna.Framework``, which is why it is here.

What "applied" means
--------------------

Most routes here answer with a boolean rather than raising: CNA reports whether
the device *accepted* the request separately from whether the call was
well-formed. A device that cannot pause says so by answering ``False``; an
effect id that does not exist is an error. Both are passed through as they are,
and nothing is upgraded or downgraded on the way.

**Whether anything is physically felt is not observable from here and is never
claimed.** With no haptic device present, ``haptic_count`` is zero and every
opener refuses -- which is the honest answer for this host.
"""

from __future__ import annotations

import ctypes as c
from typing import Sequence, TYPE_CHECKING

from _cna_native import input_abi as _input
from _cna_native import input_support as _in
from _cna_native.family_support import checked, real, string_view

from .values import (
    HapticCapabilities, HapticDirection, HapticDirectionType, HapticEffect,
    HapticEffectType, HapticFeature,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "HapticDevice",
    "haptic_count",
    "haptic_name",
    "haptic_id",
    "haptics",
    "is_joystick_haptic",
    "is_mouse_haptic",
    "open_haptic",
    "open_joystick_haptic",
    "open_mouse_haptic",
]

_support = _in.support
_VERSION = 1

#: Fields that are arrays of three in the C structure.
_PER_AXIS = ("right_saturation", "left_saturation", "right_coefficient",
             "left_coefficient", "deadband", "center")
#: Fields that are one scalar each, with the native width to range-check against.
_SCALARS = {
    "length": "uint32", "delay": "uint16", "button": "uint16", "interval": "uint16",
    "level": "int16", "period": "uint16", "magnitude": "int16", "offset": "int16",
    "phase": "uint16", "ramp_start": "int16", "ramp_end": "int16",
    "large_magnitude": "uint16", "small_magnitude": "uint16",
    "custom_period": "uint16", "custom_channels": "uint8",
    "attack_length": "uint16", "attack_level": "uint16",
    "fade_length": "uint16", "fade_level": "uint16",
}
_PER_AXIS_WIDTH = {
    "right_saturation": "uint16", "left_saturation": "uint16",
    "right_coefficient": "int16", "left_coefficient": "int16",
    "deadband": "uint16", "center": "int16",
}


def _to_native(effect: HapticEffect):
    """One :class:`HapticEffect` as the C structure plus its custom samples.

    The samples are returned alongside because they are a *separate* borrowed
    array in the ABI, not a field: the caller has to keep them alive for the
    duration of the call, and returning them together is what makes that
    impossible to forget.
    """
    if not isinstance(effect, HapticEffect):
        raise TypeError(f"effect must be a HapticEffect, not {type(effect).__name__}")
    native = _in.in_struct(_input.CNA_HapticEffect, _VERSION)
    native.type = c.c_uint32(HapticEffectType(effect.type)).value
    native.direction.type = c.c_uint32(
        HapticDirectionType(effect.direction.type)).value
    for index, value in enumerate(effect.direction.values):
        native.direction.values[index] = checked(value, "int32", "direction value")
    for name, width in _SCALARS.items():
        setattr(native, name, checked(getattr(effect, name), width, name))
    for name in _PER_AXIS:
        width = _PER_AXIS_WIDTH[name]
        target = getattr(native, name)
        for index, value in enumerate(getattr(effect, name)):
            target[index] = checked(value, width, f"{name}[{index}]")
    samples = tuple(effect.custom_data)
    if not samples:
        return native, None, 0
    array = (c.c_uint16 * len(samples))(
        *(checked(value, "uint16", "custom_data") for value in samples))
    return native, array, len(samples)


def haptic_count(game: "Game") -> int:
    """How many haptic devices the host reports. Zero is a real answer."""
    return _support.out_u32("cna_haptics_get_count",
                            _in.game_handle(game, "haptics"))


def haptic_name(game: "Game", index: int) -> str:
    """The name of the haptic device at ``index``."""
    return _support.sized_text(
        "cna_haptics_get_name_size_at", "cna_haptics_copy_name_at",
        (_in.game_handle(game, "haptics"),
         c.c_uint32(checked(index, "uint32", "index"))), "haptic device name")


def haptic_id(game: "Game", index: int) -> int:
    """The instance id of the haptic device at ``index``.

    Enumeration is by index and opening is by id; they are different numbers and
    are never used for each other.
    """
    return _support.out_u32("cna_haptics_get_id_at",
                            _in.game_handle(game, "haptics"),
                            c.c_uint32(checked(index, "uint32", "index")))


def haptics(game: "Game") -> list[tuple[int, str]]:
    """Every haptic device the host reports, as ``(id, name)`` in index order."""
    return [(haptic_id(game, index), haptic_name(game, index))
            for index in range(haptic_count(game))]


def is_joystick_haptic(game: "Game", joystick_id: int) -> bool:
    """Whether a joystick can also do haptics."""
    return _support.out_bool("cna_haptics_get_is_joystick_haptic",
                             _in.game_handle(game, "haptics"),
                             c.c_uint32(checked(joystick_id, "uint32", "joystick_id")))


def is_mouse_haptic(game: "Game") -> bool:
    """Whether the mouse can do haptics."""
    return _support.out_bool("cna_haptics_get_is_mouse_haptic",
                             _in.game_handle(game, "haptics"))


class HapticDevice:
    """One opened haptic device."""

    __slots__ = ("_handle",)

    def __init__(self, handle: int) -> None:
        self._handle = _support.handle(handle, "cna_haptic_device_destroy",
                                       "haptic device")

    # -- identity and capability ---------------------------------------------

    @property
    def name(self) -> str:
        return _support.sized_text("cna_haptic_device_get_name_size",
                                   "cna_haptic_device_copy_name",
                                   (self._handle.argument,), "haptic device name")

    @property
    def is_open(self) -> bool:
        return _support.out_bool("cna_haptic_device_get_is_open",
                                 self._handle.argument)

    @property
    def capabilities(self) -> HapticCapabilities:
        native = _support.out_struct(
            _input.CNA_HapticCapabilities, _VERSION,
            "cna_haptic_device_get_capabilities", self._handle.argument)
        limit = int(native.max_effects)
        playing = int(native.max_effects_playing)
        return HapticCapabilities(
            HapticFeature(int(native.features)), int(native.axis_count),
            None if limit < 0 else limit, None if playing < 0 else playing,
            bool(native.is_open), bool(native.rumble_supported), self.name)

    def is_effect_supported(self, effect: HapticEffect) -> bool:
        """Whether this device can play ``effect`` as described."""
        native, samples, count = _to_native(effect)
        return _support.out_bool(
            "cna_haptic_device_get_is_effect_supported", self._handle.argument,
            c.byref(native), samples, c.c_uint64(count))

    # -- rumble ---------------------------------------------------------------

    def init_rumble(self) -> bool:
        """Prepares the simple rumble path; ``False`` when the device cannot."""
        return _support.out_bool("cna_haptic_device_init_rumble",
                                 self._handle.argument)

    def play_rumble(self, strength: float, length_ms: int) -> bool:
        """Plays simple rumble at ``strength`` for ``length_ms`` milliseconds."""
        return _support.out_bool(
            "cna_haptic_device_play_rumble", self._handle.argument,
            c.c_float(real(strength, "strength")),
            c.c_uint32(checked(length_ms, "uint32", "length_ms")))

    def stop_rumble(self) -> bool:
        return _support.out_bool("cna_haptic_device_stop_rumble",
                                 self._handle.argument)

    # -- effects --------------------------------------------------------------

    def create_effect(self, effect: HapticEffect) -> int:
        """Uploads ``effect`` and returns the id the device gave it."""
        native, samples, count = _to_native(effect)
        return _support.out_i32(
            "cna_haptic_device_create_effect", self._handle.argument,
            c.byref(native), samples, c.c_uint64(count))

    def update_effect(self, effect_id: int, effect: HapticEffect) -> bool:
        """Replaces an uploaded effect's description in place."""
        native, samples, count = _to_native(effect)
        return _support.out_bool(
            "cna_haptic_device_update_effect", self._handle.argument,
            c.c_int32(checked(effect_id, "int32", "effect_id")),
            c.byref(native), samples, c.c_uint64(count))

    def run_effect(self, effect_id: int, iterations: int = 1) -> bool:
        return _support.out_bool(
            "cna_haptic_device_run_effect", self._handle.argument,
            c.c_int32(checked(effect_id, "int32", "effect_id")),
            c.c_uint32(checked(iterations, "uint32", "iterations")))

    def stop_effect(self, effect_id: int) -> bool:
        return _support.out_bool(
            "cna_haptic_device_stop_effect", self._handle.argument,
            c.c_int32(checked(effect_id, "int32", "effect_id")))

    def stop_all_effects(self) -> bool:
        return _support.out_bool("cna_haptic_device_stop_all_effects",
                                 self._handle.argument)

    def effect_status(self, effect_id: int) -> bool:
        """Whether the effect is playing right now."""
        return _support.out_bool(
            "cna_haptic_device_get_effect_status", self._handle.argument,
            c.c_int32(checked(effect_id, "int32", "effect_id")))

    def destroy_effect(self, effect_id: int) -> None:
        """Frees an uploaded effect. The id is invalid afterwards."""
        _support.call("cna_haptic_device_destroy_effect", self._handle.argument,
                      c.c_int32(checked(effect_id, "int32", "effect_id")))

    # -- global device state ---------------------------------------------------

    def set_gain(self, gain: int) -> bool:
        return _support.out_bool("cna_haptic_device_set_gain",
                                 self._handle.argument,
                                 c.c_int32(checked(gain, "int32", "gain")))

    def set_autocenter(self, autocenter: int) -> bool:
        return _support.out_bool("cna_haptic_device_set_autocenter",
                                 self._handle.argument,
                                 c.c_int32(checked(autocenter, "int32", "autocenter")))

    def pause(self) -> bool:
        return _support.out_bool("cna_haptic_device_pause", self._handle.argument)

    def resume(self) -> bool:
        return _support.out_bool("cna_haptic_device_resume", self._handle.argument)

    # -- lifetime --------------------------------------------------------------

    def dispose(self) -> None:
        """Disposes the canonical device object, as its ``Dispose`` does."""
        _support.call("cna_haptic_device_dispose", self._handle.argument)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "HapticDevice":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


def open_haptic(game: "Game", haptic_identity: int) -> HapticDevice:
    """Opens the haptic device with that **instance id**.

    Failing to open is **not** an error, and this does not make it one: CNA hands
    back a real object whose :attr:`~HapticDevice.is_open` is ``False`` and whose
    every operation reports "not applied", exactly as the canonical factory
    returns a closed device. Ask :attr:`~HapticDevice.is_open` rather than
    assuming a returned object means a device.
    """
    return HapticDevice(_support.out_handle(
        "cna_haptics_open", _in.game_handle(game, "haptics"),
        c.c_uint32(checked(haptic_identity, "uint32", "haptic_identity"))))


def open_joystick_haptic(game: "Game", joystick_id: int) -> HapticDevice:
    """Opens the haptic side of a joystick."""
    return HapticDevice(_support.out_handle(
        "cna_haptics_open_from_joystick", _in.game_handle(game, "haptics"),
        c.c_uint32(checked(joystick_id, "uint32", "joystick_id"))))


def open_mouse_haptic(game: "Game") -> HapticDevice:
    """Opens the haptic side of the mouse."""
    return HapticDevice(_support.out_handle(
        "cna_haptics_open_from_mouse", _in.game_handle(game, "haptics")))
