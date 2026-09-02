"""CNA's own equality for the extended-input value structures.

Python's ``==`` on the dataclasses in :mod:`cna.extensions.input.values`
compares fields. CNA has its own comparison for each of them, and the two are
different answers to the same question -- both exact, and expected to agree.
Exposing CNA's is what makes either usable as evidence: the qualification
asserts that they agree rather than assuming it, and a change in CNA's
comparison that Python did not follow shows up as a failure here.

Names are part of these comparisons in CNA, which is why every function takes
the name alongside the structure: two joysticks with identical capabilities and
different names are not the same device.
"""

from __future__ import annotations

import ctypes as c

from _cna_native import input_abi as _input
from _cna_native import input_support as _in
from _cna_native.family_support import checked, string_view

from .haptics import _to_native as _effect_to_native
from .values import (
    HapticCapabilities, HapticDirection, HapticDirectionType, HapticEffect,
    InputDeviceInfo, JoystickCapabilities, JoystickInfo, JoystickType, PowerState,
    SensorInfo, SensorType,
)

__all__ = [
    "joystick_info_equal", "joystick_capabilities_equal", "haptic_direction_equal",
    "haptic_capabilities_equal", "haptic_effect_equal", "input_device_info_equal",
    "sensor_info_equal",
]

_support = _in.support
_VERSION = 1


def _joystick_info(value: JoystickInfo):
    native = _in.in_struct(_input.CNA_JoystickInfo, _VERSION)
    native.id = checked(value.id, "uint32", "id")
    native.type = int(JoystickType(value.type))
    return native


def joystick_info_equal(left: JoystickInfo, right: JoystickInfo) -> bool:
    """Whether CNA considers two enumerated joysticks the same."""
    first, second = _joystick_info(left), _joystick_info(right)
    left_name, _keep_left = string_view(left.name, "left.name")
    right_name, _keep_right = string_view(right.name, "right.name")
    return _support.out_bool("cna_joystick_info_equals", c.byref(first), left_name,
                             c.byref(second), right_name)


def _joystick_capabilities(value: JoystickCapabilities):
    native = _in.in_struct(_input.CNA_JoystickCapabilities, _VERSION)
    native.axis_count = checked(value.axis_count, "int32", "axis_count")
    native.button_count = checked(value.button_count, "int32", "button_count")
    native.hat_count = checked(value.hat_count, "int32", "hat_count")
    native.ball_count = checked(value.ball_count, "int32", "ball_count")
    native.type = int(JoystickType(value.type))
    native.power_state = int(PowerState(value.power_state))
    native.power_percent = (-1 if value.power_percent is None
                            else checked(value.power_percent, "int32", "power_percent"))
    native.is_connected = 1 if value.is_connected else 0
    return native


def joystick_capabilities_equal(left: JoystickCapabilities,
                                right: JoystickCapabilities) -> bool:
    """Whether CNA considers two joysticks' capabilities the same."""
    first, second = _joystick_capabilities(left), _joystick_capabilities(right)
    left_name, _kln = string_view(left.name, "left.name")
    left_guid, _klg = string_view(left.guid, "left.guid")
    right_name, _krn = string_view(right.name, "right.name")
    right_guid, _krg = string_view(right.guid, "right.guid")
    return _support.out_bool("cna_joystick_capabilities_equals", c.byref(first),
                             left_name, left_guid, c.byref(second), right_name,
                             right_guid)


def _direction(value: HapticDirection):
    native = _input.CNA_HapticDirection()
    native.type = int(HapticDirectionType(value.type))
    for index, entry in enumerate(value.values):
        native.values[index] = checked(entry, "int32", "direction value")
    return native


def haptic_direction_equal(left: HapticDirection, right: HapticDirection) -> bool:
    """Whether CNA considers two haptic directions the same."""
    first, second = _direction(left), _direction(right)
    return _support.out_bool("cna_haptic_direction_equals", c.byref(first),
                             c.byref(second))


def _capabilities(value: HapticCapabilities):
    native = _in.in_struct(_input.CNA_HapticCapabilities, _VERSION)
    native.features = int(value.features)
    native.axis_count = checked(value.axis_count, "int32", "axis_count")
    native.max_effects = (-1 if value.max_effects is None
                          else checked(value.max_effects, "int32", "max_effects"))
    native.max_effects_playing = (
        -1 if value.max_effects_playing is None
        else checked(value.max_effects_playing, "int32", "max_effects_playing"))
    native.is_open = 1 if value.is_open else 0
    native.rumble_supported = 1 if value.rumble_supported else 0
    return native


def haptic_capabilities_equal(left: HapticCapabilities,
                              right: HapticCapabilities) -> bool:
    """Whether CNA considers two haptic devices' capabilities the same."""
    first, second = _capabilities(left), _capabilities(right)
    left_name, _keep_left = string_view(left.name, "left.name")
    right_name, _keep_right = string_view(right.name, "right.name")
    return _support.out_bool("cna_haptic_capabilities_equals", c.byref(first),
                             left_name, c.byref(second), right_name)


def haptic_effect_equal(left: HapticEffect, right: HapticEffect) -> bool:
    """Whether CNA considers two haptic effects the same, custom samples included."""
    first, first_samples, first_count = _effect_to_native(left)
    second, second_samples, second_count = _effect_to_native(right)
    return _support.out_bool(
        "cna_haptic_effect_equals", c.byref(first), first_samples,
        c.c_uint64(first_count), c.byref(second), second_samples,
        c.c_uint64(second_count))


def _device_info(value: InputDeviceInfo):
    native = _in.in_struct(_input.CNA_InputDeviceInfo, _VERSION)
    native.id = checked(value.id, "uint32", "id")
    return native


def input_device_info_equal(left: InputDeviceInfo, right: InputDeviceInfo) -> bool:
    """Whether CNA considers two enumerated input devices the same."""
    first, second = _device_info(left), _device_info(right)
    left_name, _keep_left = string_view(left.name, "left.name")
    right_name, _keep_right = string_view(right.name, "right.name")
    return _support.out_bool("cna_input_device_info_equals", c.byref(first),
                             left_name, c.byref(second), right_name)


def _sensor_info(value: SensorInfo):
    native = _in.in_struct(_input.CNA_SensorInfo, _VERSION)
    native.id = checked(value.id, "uint32", "id")
    native.type = int(SensorType(value.type))
    return native


def sensor_info_equal(left: SensorInfo, right: SensorInfo) -> bool:
    """Whether CNA considers two device sensors the same."""
    first, second = _sensor_info(left), _sensor_info(right)
    left_name, _keep_left = string_view(left.name, "left.name")
    right_name, _keep_right = string_view(right.name, "right.name")
    return _support.out_bool("cna_sensor_info_equals", c.byref(first), left_name,
                             c.byref(second), right_name)
