"""CNA's extended input: devices and capabilities XNA 4.0 never had.

This is a **CNA extension**, not part of XNA. Text input and IME composition,
mouse cursors, raw joysticks, haptics, input-device enumeration and hotplug, the
clipboard, and the sensors an input device carries have no
``Microsoft.Xna.Framework`` counterpart -- XNA reads keys rather than characters,
knows one keyboard and one mouse, exposes only ``Game.IsMouseVisible`` of the
cursor, and has two vibration motors where a haptic device has a whole effect
model. That is why they live here rather than there.

**The strict XNA projection is untouched by this package.** No name in
``Microsoft.Xna.Framework`` changes, gains a member, or learns that this package
exists. The dependency runs one way -- this package accepts a strict ``Game``,
``Texture2D``, ``Rectangle``, ``Point`` and ``Vector3`` -- and the extension gate
asserts in a fresh interpreter that importing the XNA namespace loads no ``cna``
module.

Two things this family gets right on purpose
--------------------------------------------

**UTF-16 is not characters.** Committed text arrives one UTF-16 code unit at a
time and a character above U+FFFF arrives as two. Nothing here hides that;
:class:`~cna.extensions.input.text.TextInputAccumulator` is the one explicit,
testable place a surrogate pair becomes a character, and an unpaired surrogate is
reported rather than replaced.

**An index is not an id.** Joysticks and haptic devices enumerate by index and
are opened by instance id, and the two are different numbers. Every function
below says which it takes.

Ownership is the same contract as everywhere in ``cna.extensions``: an explicit
``close``, a context manager, no ``__del__``, and no raw handle, ctypes object or
result code anywhere in the public surface. Text-input and hotplug registrations
are process-global, because CNA's subscribe routes take no game handle -- that is
stated rather than smoothed over.

Importing this module needs no native library. Constructing anything in it does.
"""

from __future__ import annotations

from . import (
    clipboard, comparison, cursor, devices, errors, haptics, joystick, text, values,
)
from .comparison import (
    haptic_capabilities_equal, haptic_direction_equal, haptic_effect_equal,
    input_device_info_equal, joystick_capabilities_equal, joystick_info_equal,
    sensor_info_equal,
)
from .clipboard import (
    clipboard_has_text, clipboard_text, clipboard_text_byte_length,
    set_clipboard_text,
)
from .cursor import MouseCursor, active_cursor, set_cursor
from .devices import (
    DevicePower, InputDeviceSubscription, device_power, device_sensor_count,
    device_sensors, gamepad_acceleration, gamepad_angular_velocity, keyboard_count,
    keyboards, mice, mouse_count, on_keyboard_connected, on_keyboard_disconnected,
    on_mouse_connected, on_mouse_disconnected, touch_device_count, touch_devices,
)
from .errors import (
    InputArgumentError, InputDisposedError, InputError, InputInternalError,
    InputStateError, InputThreadError, InputUnsupportedError,
)
from .haptics import (
    HapticDevice, haptic_count, haptic_id, haptic_name, haptics as haptic_devices,
    is_joystick_haptic, is_mouse_haptic, open_haptic, open_joystick_haptic,
    open_mouse_haptic,
)
from .joystick import (
    JoystickState, JoystickSubscription, capture_joystick_state,
    joystick_capabilities, joystick_count, joystick_info, joystick_name, joysticks,
    on_joystick_connected, on_joystick_disconnected,
)
from .text import (
    TextInputAccumulator, TextInputSubscription, is_screen_keyboard_shown,
    is_text_input_active, on_text_editing, on_text_editing_candidates,
    on_text_input, set_input_rectangle, start_text_input, stop_text_input,
    window_handle,
)
from .values import (
    HAPTIC_EFFECT_INFINITE_LENGTH, HapticCapabilities, HapticDirection,
    HapticDirectionType, HapticEffect, HapticEffectType, HapticFeature,
    InputDeviceInfo, JoystickCapabilities, JoystickHatPosition, JoystickInfo,
    JoystickType, MouseCursorStock, PowerState, SensorInfo, SensorType,
    TextEditing, TextEditingCandidates, TextInputType,
)

__all__ = [
    "clipboard", "comparison", "cursor", "devices", "errors", "haptics",
    "joystick", "text", "values",
    # comparison
    "haptic_capabilities_equal", "haptic_direction_equal", "haptic_effect_equal",
    "input_device_info_equal", "joystick_capabilities_equal", "joystick_info_equal",
    "sensor_info_equal",
    # clipboard
    "clipboard_has_text", "clipboard_text", "clipboard_text_byte_length",
    "set_clipboard_text",
    # cursor
    "MouseCursor", "active_cursor", "set_cursor",
    # devices
    "DevicePower", "InputDeviceSubscription", "device_power",
    "device_sensor_count", "device_sensors", "gamepad_acceleration",
    "gamepad_angular_velocity", "keyboard_count", "keyboards", "mice",
    "mouse_count", "on_keyboard_connected", "on_keyboard_disconnected",
    "on_mouse_connected", "on_mouse_disconnected", "touch_device_count",
    "touch_devices",
    # errors
    "InputArgumentError", "InputDisposedError", "InputError",
    "InputInternalError", "InputStateError", "InputThreadError",
    "InputUnsupportedError",
    # haptics
    "HapticDevice", "haptic_count", "haptic_devices", "haptic_id", "haptic_name",
    "is_joystick_haptic", "is_mouse_haptic", "open_haptic",
    "open_joystick_haptic", "open_mouse_haptic",
    # joystick
    "JoystickState", "JoystickSubscription", "capture_joystick_state",
    "joystick_capabilities", "joystick_count", "joystick_info", "joystick_name",
    "joysticks", "on_joystick_connected", "on_joystick_disconnected",
    # text
    "TextInputAccumulator", "TextInputSubscription", "is_screen_keyboard_shown",
    "is_text_input_active", "on_text_editing", "on_text_editing_candidates",
    "on_text_input", "set_input_rectangle", "start_text_input", "stop_text_input",
    "window_handle",
    # values
    "HAPTIC_EFFECT_INFINITE_LENGTH", "HapticCapabilities", "HapticDirection",
    "HapticDirectionType", "HapticEffect", "HapticEffectType", "HapticFeature",
    "InputDeviceInfo", "JoystickCapabilities", "JoystickHatPosition",
    "JoystickInfo", "JoystickType", "MouseCursorStock", "PowerState", "SensorInfo",
    "SensorType", "TextEditing", "TextEditingCandidates", "TextInputType",
]
