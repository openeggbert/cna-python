"""ctypes manifest for CNA's ``input_text.h``, ``input_cursor.h``, ``input_joystick.h``, ``input_haptics.h``, ``input_devices.h`` family.

Do not edit. ``tools/generate_family_manifest.py`` derives every prototype
from the canonical headers, and ``--check`` fails when the checked-in copy is
not what the current headers produce. Every entry is proven against the
canonical C declaration by ``tools/verify_prototypes.py`` -- being generated is
not a reason to trust it.

The fourth column is the ownership contract the Python wrapper has to keep.
"""

from __future__ import annotations

import ctypes as c

from . import abi
from . import devices_abi
from . import input_abi

Entry = tuple[str, object, list[object], str]

#: The host clipboard's read side. ``devices.h`` writes it and
#: ``input_devices.h`` reads it; the two are one clipboard.
INPUT_CLIPBOARD_MANIFEST: tuple[Entry, ...] = (
    ("cna_clipboard_copy_text", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_clipboard_get_has_text", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_clipboard_get_text_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_clipboard_set_text", c.c_uint32, [c.c_uint64, abi.CNA_StringView],
     "borrowed handle; copies the value, retains nothing"),
)

#: Text input and IME composition: committed text, editing updates,
#: candidate lists, the input rectangle and the screen keyboard.
INPUT_TEXT_INPUT_MANIFEST: tuple[Entry, ...] = (
    ("cna_text_input_get_window_handle_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_text_input_is_active_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_text_input_is_screen_keyboard_shown_ext", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_text_input_is_screen_keyboard_shown_for_window_ext", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_text_input_raise_text_editing_candidates_ext", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_StringView), c.c_int32, c.c_int32, c.c_uint8],
     "borrowed handle; retains nothing"),
    ("cna_text_input_raise_text_editing_ext", c.c_uint32, [c.c_uint64, abi.CNA_StringView, c.c_int32, c.c_int32],
     "borrowed handle; retains nothing"),
    ("cna_text_input_raise_text_input_ext", c.c_uint32, [c.c_uint64, c.c_uint16],
     "borrowed handle; retains nothing"),
    ("cna_text_input_reset_for_tests_ext", c.c_uint32, [c.c_uint64],
     "borrowed handle; retains nothing"),
    ("cna_text_input_set_input_rectangle_ext", c.c_uint32, [c.c_uint64, abi.CNA_Rectangle],
     "borrowed handle; copies the value, retains nothing"),
    ("cna_text_input_set_window_handle_ext", c.c_uint32, [c.c_uint64, c.c_uint64],
     "borrowed handle; copies the value, retains nothing"),
    ("cna_text_input_start_ext", c.c_uint32, [c.c_uint64],
     "borrowed handle; retains nothing"),
    ("cna_text_input_start_with_type_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_text_input_stop_ext", c.c_uint32, [c.c_uint64],
     "borrowed handle; retains nothing"),
    ("cna_text_input_subscribe_text_editing_candidates_ext", c.c_uint32, [input_abi.CNA_TextEditingCandidatesCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_text_input_subscribe_text_editing_ext", c.c_uint32, [input_abi.CNA_TextEditingCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_text_input_subscribe_text_input_ext", c.c_uint32, [input_abi.CNA_TextInputCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_text_input_unsubscribe_ext", c.c_uint32, [c.c_uint64],
     "consumes a subscription registration; no callback arrives afterwards"),
)

#: Mouse cursors: stock cursors, cursors built from a Texture2D, and the
#: one that is currently active.
INPUT_CURSOR_MANIFEST: tuple[Entry, ...] = (
    ("cna_mouse_cursor_create_ext", c.c_uint32, [c.POINTER(c.c_uint64)],
     "owned handle; the caller closes it and nothing else may"),
    ("cna_mouse_cursor_create_from_texture2d", c.c_uint32, [c.c_uint64, c.c_uint64, c.c_int32, c.c_int32, c.POINTER(c.c_uint64)],
     "owned cursor; the Texture2D is read during the call and not retained"),
    ("cna_mouse_cursor_destroy", c.c_uint32, [c.c_uint64],
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    ("cna_mouse_cursor_dispose", c.c_uint32, [c.c_uint64],
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    ("cna_mouse_cursor_get_stock_ext", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_mouse_set_cursor_ext", c.c_uint32, [c.c_uint64, c.c_uint64],
     "the cursor is BORROWED for as long as it is the active one"),
)

#: Raw joysticks: enumeration, capabilities, axis/ball/button/hat state,
#: and connect/disconnect events.
INPUT_JOYSTICK_MANIFEST: tuple[Entry, ...] = (
    ("cna_joystick_capabilities_equals", c.c_uint32, [c.POINTER(input_abi.CNA_JoystickCapabilities), abi.CNA_StringView, abi.CNA_StringView, c.POINTER(input_abi.CNA_JoystickCapabilities), abi.CNA_StringView, abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_joystick_info_equals", c.c_uint32, [c.POINTER(input_abi.CNA_JoystickInfo), abi.CNA_StringView, c.POINTER(input_abi.CNA_JoystickInfo), abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_joystick_state_copy_axes", c.c_uint32, [c.c_uint64, c.POINTER(c.c_int16), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joystick_state_copy_balls", c.c_uint32, [c.c_uint64, c.POINTER(input_abi.CNA_Point), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joystick_state_copy_buttons", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joystick_state_copy_hats", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joystick_state_destroy", c.c_uint32, [c.c_uint64],
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    ("cna_joystick_state_equals", c.c_uint32, [c.c_uint64, c.c_uint64, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_joystick_state_get_axis_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joystick_state_get_ball_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joystick_state_get_button_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joystick_state_get_hat_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joysticks_capture_state", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "borrowed handle; retains nothing"),
    ("cna_joysticks_copy_capabilities_guid", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joysticks_copy_capabilities_name", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joysticks_copy_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_joysticks_get_capabilities", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_JoystickCapabilities)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joysticks_get_capabilities_guid_size", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_joysticks_get_capabilities_name_size", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_joysticks_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joysticks_get_info_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_JoystickInfo)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_joysticks_get_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_joysticks_raise_connected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_joysticks_raise_disconnected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_joysticks_reset_for_tests_ext", c.c_uint32, [c.c_uint64],
     "borrowed handle; retains nothing"),
    ("cna_joysticks_subscribe_connected_ext", c.c_uint32, [input_abi.CNA_JoystickHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_joysticks_subscribe_disconnected_ext", c.c_uint32, [input_abi.CNA_JoystickHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_joysticks_unsubscribe_ext", c.c_uint32, [c.c_uint64],
     "consumes a subscription registration; no callback arrives afterwards"),
)

#: Haptic devices: capabilities, rumble, and the full effect model.
INPUT_HAPTICS_MANIFEST: tuple[Entry, ...] = (
    ("cna_haptic_capabilities_equals", c.c_uint32, [c.POINTER(input_abi.CNA_HapticCapabilities), abi.CNA_StringView, c.POINTER(input_abi.CNA_HapticCapabilities), abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_haptic_device_copy_name", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_haptic_device_create_effect", c.c_uint32, [c.c_uint64, c.POINTER(input_abi.CNA_HapticEffect), c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(c.c_int32)],
     "owned handle; the caller closes it and nothing else may"),
    ("cna_haptic_device_destroy", c.c_uint32, [c.c_uint64],
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    ("cna_haptic_device_destroy_effect", c.c_uint32, [c.c_uint64, c.c_int32],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_dispose", c.c_uint32, [c.c_uint64],
     "consumes the handle; every borrowed view of it is invalid afterwards"),
    ("cna_haptic_device_get_capabilities", c.c_uint32, [c.c_uint64, c.POINTER(input_abi.CNA_HapticCapabilities)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptic_device_get_effect_status", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptic_device_get_is_effect_supported", c.c_uint32, [c.c_uint64, c.POINTER(input_abi.CNA_HapticEffect), c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptic_device_get_is_open", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "owned handle; the caller closes it and nothing else may"),
    ("cna_haptic_device_get_name_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_haptic_device_init_rumble", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "pure value initialiser over caller-owned storage"),
    ("cna_haptic_device_pause", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_play_rumble", c.c_uint32, [c.c_uint64, c.c_float, c.c_uint32, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_resume", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_run_effect", c.c_uint32, [c.c_uint64, c.c_int32, c.c_uint32, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_set_autocenter", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(c.c_uint8)],
     "borrowed handle; copies the value, retains nothing"),
    ("cna_haptic_device_set_gain", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(c.c_uint8)],
     "borrowed handle; copies the value, retains nothing"),
    ("cna_haptic_device_stop_all_effects", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_stop_effect", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_stop_rumble", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_device_update_effect", c.c_uint32, [c.c_uint64, c.c_int32, c.POINTER(input_abi.CNA_HapticEffect), c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(c.c_uint8)],
     "borrowed handle; retains nothing"),
    ("cna_haptic_direction_equals", c.c_uint32, [c.POINTER(input_abi.CNA_HapticDirection), c.POINTER(input_abi.CNA_HapticDirection), c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_haptic_effect_equals", c.c_uint32, [c.POINTER(input_abi.CNA_HapticEffect), c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(input_abi.CNA_HapticEffect), c.POINTER(c.c_uint16), c.c_uint64, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_haptics_copy_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_haptics_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptics_get_id_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptics_get_is_joystick_haptic", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptics_get_is_mouse_haptic", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_haptics_get_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_haptics_open", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "owned handle; the caller closes it and nothing else may"),
    ("cna_haptics_open_from_joystick", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "owned handle; the caller closes it and nothing else may"),
    ("cna_haptics_open_from_mouse", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "owned handle; the caller closes it and nothing else may"),
)

#: Keyboard, mouse and touch device enumeration, and their hotplug events.
INPUT_DEVICE_ENUMERATION_MANIFEST: tuple[Entry, ...] = (
    ("cna_input_device_info_equals", c.c_uint32, [c.POINTER(input_abi.CNA_InputDeviceInfo), abi.CNA_StringView, c.POINTER(input_abi.CNA_InputDeviceInfo), abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_input_devices_copy_keyboard_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_input_devices_copy_mouse_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_input_devices_copy_touch_device_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_input_devices_get_keyboard_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_keyboard_info_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_InputDeviceInfo)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_keyboard_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_input_devices_get_mouse_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_mouse_info_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_InputDeviceInfo)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_mouse_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_input_devices_get_touch_device_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_touch_device_info_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_InputDeviceInfo)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_input_devices_get_touch_device_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_input_devices_raise_keyboard_connected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_input_devices_raise_keyboard_disconnected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_input_devices_raise_mouse_connected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_input_devices_raise_mouse_disconnected_ext", c.c_uint32, [c.c_uint64, c.c_uint32],
     "borrowed handle; retains nothing"),
    ("cna_input_devices_reset_for_tests_ext", c.c_uint32, [c.c_uint64],
     "borrowed handle; retains nothing"),
    ("cna_input_devices_subscribe_keyboard_connected_ext", c.c_uint32, [input_abi.CNA_InputDeviceHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_input_devices_subscribe_keyboard_disconnected_ext", c.c_uint32, [input_abi.CNA_InputDeviceHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_input_devices_subscribe_mouse_connected_ext", c.c_uint32, [input_abi.CNA_InputDeviceHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_input_devices_subscribe_mouse_disconnected_ext", c.c_uint32, [input_abi.CNA_InputDeviceHotplugCallback, c.c_void_p, c.POINTER(c.c_uint64)],
     "roots a callback trampoline; the registration is owned and must be released before the owner is destroyed"),
    ("cna_input_devices_unsubscribe_ext", c.c_uint32, [c.c_uint64],
     "consumes a subscription registration; no callback arrives afterwards"),
)

#: Sensors carried by an input device rather than by the host: a gamepad's
#: accelerometer, gyro and power.
INPUT_GAMEPAD_SENSORS_MANIFEST: tuple[Entry, ...] = (
    ("cna_power_get_info", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32), c.POINTER(c.c_int32), c.POINTER(c.c_int32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_sensor_info_equals", c.c_uint32, [c.POINTER(input_abi.CNA_SensorInfo), abi.CNA_StringView, c.POINTER(input_abi.CNA_SensorInfo), abi.CNA_StringView, c.POINTER(c.c_uint8)],
     "pure function over caller-owned input; nothing is retained"),
    ("cna_sensors_copy_name_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_sensors_get_accelerometer", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3), c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_sensors_get_count", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint32)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_sensors_get_gyroscope", c.c_uint32, [c.c_uint64, c.POINTER(abi.CNA_Vector3), c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_sensors_get_info_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(input_abi.CNA_SensorInfo)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_sensors_get_name_size_at", c.c_uint32, [c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
)

#: Every group above, in one tuple for :mod:`_cna_native.loader`.
INPUT_FUNCTION_MANIFEST: tuple[Entry, ...] = (
    INPUT_CLIPBOARD_MANIFEST
    +
    INPUT_TEXT_INPUT_MANIFEST
    +
    INPUT_CURSOR_MANIFEST
    +
    INPUT_JOYSTICK_MANIFEST
    +
    INPUT_HAPTICS_MANIFEST
    +
    INPUT_DEVICE_ENUMERATION_MANIFEST
    +
    INPUT_GAMEPAD_SENSORS_MANIFEST
)
