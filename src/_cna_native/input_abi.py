"""Generated ctypes layouts and constants for CNA's ``input_text.h``, ``input_cursor.h``, ``input_joystick.h``, ``input_haptics.h``, ``input_devices.h``.

Do not edit. ``tools/generate_family_abi.py`` derives this from the canonical
headers, and ``--check`` fails when the checked-in copy is not what the current
headers produce. Every size, alignment, field offset and constant here is
re-measured against the C compiler by ``tools/audit_cna_abi.py``.

Nothing in this module is public. ``cna.extensions.input`` holds the
public projection; a ctypes object never crosses that boundary.
"""

from __future__ import annotations

import ctypes as c

from . import abi
from . import devices_abi

# --- scalar identities -----------------------------------------------------

#: Fixed-width identities these headers declare as typedefs of a scalar.
#: They are enums in spirit and integers in the ABI; the public projection
#: turns them into Python enums, and this is only their width.
CNA_HapticDirectionType = c.c_uint32
CNA_HapticEffectType = c.c_uint32
CNA_HapticFeature = c.c_uint32
CNA_JoystickHatPosition = c.c_uint32
CNA_JoystickType = c.c_uint32
CNA_MouseCursorStock = c.c_uint32
CNA_PowerState = c.c_uint32
CNA_SensorType = c.c_uint32
CNA_TextInputType = c.c_uint32

#: Every opaque handle in this family is a ``CNA_Handle``. The names are kept
#: so a manifest entry can say which object a handle parameter refers to.
INPUT_HANDLE_TYPES = (
    "CNA_HapticDeviceHandle",
    "CNA_InputDeviceEventRegistrationHandle",
    "CNA_JoystickEventRegistrationHandle",
    "CNA_JoystickStateHandle",
    "CNA_MouseCursorHandle",
    "CNA_TextInputRegistrationHandle",
)


# --- constants -------------------------------------------------------------

CNA_HAPTIC_DIRECTION_TYPE_CARTESIAN = 1
CNA_HAPTIC_DIRECTION_TYPE_MAXIMUM = 3
CNA_HAPTIC_DIRECTION_TYPE_POLAR = 0
CNA_HAPTIC_DIRECTION_TYPE_SPHERICAL = 2
CNA_HAPTIC_DIRECTION_TYPE_STEERING_AXIS = 3
CNA_HAPTIC_EFFECT_INFINITE_LENGTH = 4294967295
CNA_HAPTIC_EFFECT_TYPE_CONSTANT = 0
CNA_HAPTIC_EFFECT_TYPE_CUSTOM = 12
CNA_HAPTIC_EFFECT_TYPE_DAMPER = 8
CNA_HAPTIC_EFFECT_TYPE_FRICTION = 10
CNA_HAPTIC_EFFECT_TYPE_INERTIA = 9
CNA_HAPTIC_EFFECT_TYPE_LEFT_RIGHT = 11
CNA_HAPTIC_EFFECT_TYPE_MAXIMUM = 12
CNA_HAPTIC_EFFECT_TYPE_RAMP = 6
CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_DOWN = 5
CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_UP = 4
CNA_HAPTIC_EFFECT_TYPE_SINE = 1
CNA_HAPTIC_EFFECT_TYPE_SPRING = 7
CNA_HAPTIC_EFFECT_TYPE_SQUARE = 2
CNA_HAPTIC_EFFECT_TYPE_TRIANGLE = 3
CNA_HAPTIC_FEATURE_ALL = 1019903
CNA_HAPTIC_FEATURE_AUTOCENTER = 131072
CNA_HAPTIC_FEATURE_CONSTANT = 1
CNA_HAPTIC_FEATURE_CUSTOM = 32768
CNA_HAPTIC_FEATURE_DAMPER = 256
CNA_HAPTIC_FEATURE_FRICTION = 1024
CNA_HAPTIC_FEATURE_GAIN = 65536
CNA_HAPTIC_FEATURE_INERTIA = 512
CNA_HAPTIC_FEATURE_LEFT_RIGHT = 2048
CNA_HAPTIC_FEATURE_NONE = 0
CNA_HAPTIC_FEATURE_PAUSE = 524288
CNA_HAPTIC_FEATURE_RAMP = 64
CNA_HAPTIC_FEATURE_SAWTOOTH_DOWN = 32
CNA_HAPTIC_FEATURE_SAWTOOTH_UP = 16
CNA_HAPTIC_FEATURE_SINE = 2
CNA_HAPTIC_FEATURE_SPRING = 128
CNA_HAPTIC_FEATURE_SQUARE = 4
CNA_HAPTIC_FEATURE_STATUS = 262144
CNA_HAPTIC_FEATURE_TRIANGLE = 8
CNA_JOYSTICK_HAT_POSITION_CENTERED = 0
CNA_JOYSTICK_HAT_POSITION_DOWN = 3
CNA_JOYSTICK_HAT_POSITION_LEFT = 4
CNA_JOYSTICK_HAT_POSITION_LEFT_DOWN = 8
CNA_JOYSTICK_HAT_POSITION_LEFT_UP = 7
CNA_JOYSTICK_HAT_POSITION_MAXIMUM = 8
CNA_JOYSTICK_HAT_POSITION_RIGHT = 2
CNA_JOYSTICK_HAT_POSITION_RIGHT_DOWN = 6
CNA_JOYSTICK_HAT_POSITION_RIGHT_UP = 5
CNA_JOYSTICK_HAT_POSITION_UP = 1
CNA_JOYSTICK_TYPE_ARCADE_PAD = 8
CNA_JOYSTICK_TYPE_ARCADE_STICK = 3
CNA_JOYSTICK_TYPE_DANCE_PAD = 5
CNA_JOYSTICK_TYPE_DRUM_KIT = 7
CNA_JOYSTICK_TYPE_FLIGHT_STICK = 4
CNA_JOYSTICK_TYPE_GAMEPAD = 1
CNA_JOYSTICK_TYPE_GUITAR = 6
CNA_JOYSTICK_TYPE_MAXIMUM = 9
CNA_JOYSTICK_TYPE_THROTTLE = 9
CNA_JOYSTICK_TYPE_UNKNOWN = 0
CNA_JOYSTICK_TYPE_WHEEL = 2
CNA_MOUSE_CURSOR_STOCK_ARROW = 0
CNA_MOUSE_CURSOR_STOCK_CROSSHAIR = 1
CNA_MOUSE_CURSOR_STOCK_HAND = 2
CNA_MOUSE_CURSOR_STOCK_IBEAM = 3
CNA_MOUSE_CURSOR_STOCK_NO = 4
CNA_MOUSE_CURSOR_STOCK_SIZE_ALL = 5
CNA_MOUSE_CURSOR_STOCK_SIZE_NESW = 6
CNA_MOUSE_CURSOR_STOCK_SIZE_NS = 7
CNA_MOUSE_CURSOR_STOCK_SIZE_NWSE = 8
CNA_MOUSE_CURSOR_STOCK_SIZE_WE = 9
CNA_MOUSE_CURSOR_STOCK_WAIT = 10
CNA_MOUSE_CURSOR_STOCK_WAIT_ARROW = 11
CNA_POWER_STATE_CHARGED = 5
CNA_POWER_STATE_CHARGING = 4
CNA_POWER_STATE_ERROR = 0
CNA_POWER_STATE_MAXIMUM = 5
CNA_POWER_STATE_NO_BATTERY = 3
CNA_POWER_STATE_ON_BATTERY = 2
CNA_POWER_STATE_UNKNOWN = 1
CNA_SENSOR_TYPE_ACCELEROMETER = 1
CNA_SENSOR_TYPE_ACCELEROMETER_LEFT = 3
CNA_SENSOR_TYPE_ACCELEROMETER_RIGHT = 5
CNA_SENSOR_TYPE_GYROSCOPE = 2
CNA_SENSOR_TYPE_GYROSCOPE_LEFT = 4
CNA_SENSOR_TYPE_GYROSCOPE_RIGHT = 6
CNA_SENSOR_TYPE_MAXIMUM = 6
CNA_SENSOR_TYPE_UNKNOWN = 0
CNA_TEXT_INPUT_TYPE_MAXIMUM = 8
CNA_TEXT_INPUT_TYPE_NUMBER = 6
CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_HIDDEN = 7
CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_VISIBLE = 8
CNA_TEXT_INPUT_TYPE_TEXT = 0
CNA_TEXT_INPUT_TYPE_TEXT_EMAIL = 2
CNA_TEXT_INPUT_TYPE_TEXT_NAME = 1
CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_HIDDEN = 4
CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_VISIBLE = 5
CNA_TEXT_INPUT_TYPE_TEXT_USERNAME = 3

# --- structures ------------------------------------------------------------

class CNA_TextEditingEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("text", abi.CNA_StringView),
        ("start", c.c_int32),
        ("length", c.c_int32),
    ]

class CNA_TextEditingCandidatesEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("candidates", c.c_void_p),
        ("candidate_count", c.c_int32),
        ("selected", c.c_int32),
        ("horizontal", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]

class CNA_JoystickInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("id", c.c_uint32),
        ("type", c.c_uint32),
    ]

class CNA_JoystickCapabilities(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("axis_count", c.c_int32),
        ("button_count", c.c_int32),
        ("hat_count", c.c_int32),
        ("ball_count", c.c_int32),
        ("type", c.c_uint32),
        ("power_state", c.c_uint32),
        ("power_percent", c.c_int32),
        ("is_connected", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]

class CNA_HapticDirection(c.Structure):
    _fields_ = [
        ("type", c.c_uint32),
        ("values", c.c_int32 * 3),
    ]

class CNA_HapticCapabilities(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("features", c.c_uint32),
        ("axis_count", c.c_int32),
        ("max_effects", c.c_int32),
        ("max_effects_playing", c.c_int32),
        ("is_open", c.c_uint8),
        ("rumble_supported", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
    ]

class CNA_HapticEffect(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("type", c.c_uint32),
        ("reserved", c.c_uint32),
        ("direction", CNA_HapticDirection),
        ("length", c.c_uint32),
        ("delay", c.c_uint16),
        ("button", c.c_uint16),
        ("interval", c.c_uint16),
        ("level", c.c_int16),
        ("period", c.c_uint16),
        ("magnitude", c.c_int16),
        ("offset", c.c_int16),
        ("phase", c.c_uint16),
        ("ramp_start", c.c_int16),
        ("ramp_end", c.c_int16),
        ("right_saturation", c.c_uint16 * 3),
        ("left_saturation", c.c_uint16 * 3),
        ("right_coefficient", c.c_int16 * 3),
        ("left_coefficient", c.c_int16 * 3),
        ("deadband", c.c_uint16 * 3),
        ("center", c.c_int16 * 3),
        ("large_magnitude", c.c_uint16),
        ("small_magnitude", c.c_uint16),
        ("custom_period", c.c_uint16),
        ("custom_channels", c.c_uint8),
        ("reserved2", c.c_uint8),
        ("attack_length", c.c_uint16),
        ("attack_level", c.c_uint16),
        ("fade_length", c.c_uint16),
        ("fade_level", c.c_uint16),
    ]

class CNA_SensorInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("id", c.c_uint32),
        ("type", c.c_uint32),
    ]

class CNA_InputDeviceInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("id", c.c_uint64),
    ]

class CNA_Point(c.Structure):
    _fields_ = [
        ("x", c.c_int32),
        ("y", c.c_int32),
    ]


#: Function pointers this family hands to CNA. A Python callable
#: bound to one of these must be rooted for as long as CNA can call it;
#: the trampoline is what CNA holds, not the Python object.
CNA_TextInputCallback = c.CFUNCTYPE(None, c.c_uint16, c.c_void_p)
CNA_TextEditingCallback = c.CFUNCTYPE(None, c.POINTER(CNA_TextEditingEventInfo), c.c_void_p)
CNA_TextEditingCandidatesCallback = c.CFUNCTYPE(None, c.POINTER(CNA_TextEditingCandidatesEventInfo), c.c_void_p)
CNA_JoystickHotplugCallback = c.CFUNCTYPE(None, c.c_uint32, c.c_void_p)
CNA_InputDeviceHotplugCallback = c.CFUNCTYPE(None, c.c_uint32, c.c_void_p)

#: Every generated callback type, for the ABI audit.
INPUT_CALLBACKS = (
    "CNA_TextInputCallback",
    "CNA_TextEditingCallback",
    "CNA_TextEditingCandidatesCallback",
    "CNA_JoystickHotplugCallback",
    "CNA_InputDeviceHotplugCallback",
)

#: Which of each callback's parameters are pointers to const.
#:
#: ``const`` is not an ABI property and ctypes cannot carry it, but C
#: declaration compatibility distinguishes ``const T*`` from ``T*`` -- so
#: the compiler-backed prototype gate needs it to spell a function-pointer
#: parameter the way the canonical typedef does. Derived here rather than
#: written down there, because it is a fact about the header.
INPUT_CALLBACK_CONST_PARAMETERS = {
    "CNA_TextInputCallback": (False, False),
    "CNA_TextEditingCallback": (True, False),
    "CNA_TextEditingCandidatesCallback": (True, False),
    "CNA_JoystickHotplugCallback": (False, False),
    "CNA_InputDeviceHotplugCallback": (False, False),
}

# --- constants derived from a generated layout ------------------------------


#: Each structure field's own ``@brief`` from the canonical header, so a
#: public projection documents a field with CNA's own words rather than a
#: second summary that can drift from it.
INPUT_FIELD_DOCUMENTATION = {
    "CNA_TextEditingEventInfo": {
        "struct_size": "Size of this structure in bytes.",
        "struct_version": "Version of this structure.",
        "text": "The draft composition as UTF-8 bytes, borrowed for the duration of the callback.",
        "start": "Byte offset of the active editing region inside @ref text.",
        "length": "Byte length of the active editing region inside @ref text.",
    },
    "CNA_TextEditingCandidatesEventInfo": {
        "struct_size": "Size of this structure in bytes.",
        "struct_version": "Version of this structure.",
        "candidates": "The candidate strings as UTF-8 views, borrowed for the duration of the callback.",
        "candidate_count": "Number of entries in @ref candidates.",
        "selected": "Index of the pre-selected candidate, or -1 when none is selected.",
        "horizontal": "`CNA_TRUE` when the candidate list is laid out horizontally.",
        "reserved": "Reserved padding; always zero.",
    },
    "CNA_JoystickInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "id": "The native joystick instance identifier.",
        "type": "One `CNA_JOYSTICK_TYPE_ ` identity.",
    },
    "CNA_JoystickCapabilities": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "axis_count": "Number of axes the device reports.",
        "button_count": "Number of buttons the device reports.",
        "hat_count": "Number of POV hats the device reports.",
        "ball_count": "Number of trackballs the device reports.",
        "type": "One `CNA_JOYSTICK_TYPE_ ` identity.",
        "power_state": "One `CNA_POWER_STATE_ ` identity; `CNA_POWER_STATE_UNKNOWN` when disconnected.",
        "power_percent": "Battery charge percent from 0 through 100, or -1 when unknown or disconnected.",
        "is_connected": "`CNA_TRUE` when a joystick with this instance identifier is currently connected.",
        "reserved": "Reserved padding; always zero.",
    },
    "CNA_HapticDirection": {
        "type": "One `CNA_HAPTIC_DIRECTION_TYPE_ ` identity.",
        "values": "The encoded direction components.",
    },
    "CNA_HapticCapabilities": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "features": "The effect families and global capabilities the device supports.",
        "axis_count": "Number of axes the device reports.",
        "max_effects": "Maximum stored effects, or -1 when the device is closed or the count is unknown.",
        "max_effects_playing": "Maximum simultaneously playing effects, or -1 when closed or unknown.",
        "is_open": "`CNA_TRUE` when the device handle is currently open.",
        "rumble_supported": "`CNA_TRUE` when the simple rumble convenience is supported.",
        "reserved": "Reserved padding; always zero.",
    },
    "CNA_HapticEffect": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "type": "One `CNA_HAPTIC_EFFECT_TYPE_ ` identity.",
        "reserved": "Reserved padding; always zero.",
        "direction": "Direction the force comes from.",
        "length": "Duration in milliseconds, or @ref CNA_HAPTIC_EFFECT_INFINITE_LENGTH.",
        "delay": "Delay before the effect starts, in milliseconds.",
        "button": "One-based button index that triggers the effect, or zero for none.",
        "interval": "Minimum time between button-triggered replays, in milliseconds.",
        "level": "Strength of a constant effect.",
        "period": "Wave period of a periodic effect, in milliseconds.",
        "magnitude": "Peak value of a periodic effect; a negative value shifts the phase by 180 degrees.",
        "offset": "Mean offset of a periodic effect's wave.",
        "phase": "Positive phase shift of a periodic effect, in hundredths of a degree.",
        "ramp_start": "Starting strength of a ramp effect.",
        "ramp_end": "Ending strength of a ramp effect.",
        "right_saturation": "Per-axis positive-side saturation, for condition effects.",
        "left_saturation": "Per-axis negative-side saturation, for condition effects.",
        "right_coefficient": "Per-axis positive-side force growth rate, for condition effects.",
        "left_coefficient": "Per-axis negative-side force growth rate, for condition effects.",
        "deadband": "Per-axis dead-zone size, for condition effects.",
        "center": "Per-axis dead-zone center, for condition effects.",
        "large_magnitude": "Large (low-frequency) motor strength, for a left/right effect.",
        "small_magnitude": "Small (high-frequency) motor strength, for a left/right effect.",
        "custom_period": "Sample period of a custom waveform, in milliseconds.",
        "custom_channels": "Number of axes a custom waveform drives; one rotates using the direction.",
        "reserved2": "Reserved padding; always zero.",
        "attack_length": "Duration of the attack ramp-in, in milliseconds.",
        "attack_level": "Effect level at the start of the attack.",
        "fade_length": "Duration of the fade ramp-out, in milliseconds.",
        "fade_level": "Effect level at the end of the fade.",
    },
    "CNA_SensorInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "id": "The native sensor instance identifier.",
        "type": "One `CNA_SENSOR_TYPE_ ` identity.",
    },
    "CNA_InputDeviceInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "id": "The native device instance identifier. Wider than the sensor and joystick ones, because a touch-device identifier is 64-bit natively.",
    },
}

#: Every generated structure, in declaration order, for the ABI audit.
INPUT_STRUCTURES = (
    CNA_TextEditingEventInfo,
    CNA_TextEditingCandidatesEventInfo,
    CNA_JoystickInfo,
    CNA_JoystickCapabilities,
    CNA_HapticDirection,
    CNA_HapticCapabilities,
    CNA_HapticEffect,
    CNA_SensorInfo,
    CNA_InputDeviceInfo,
    CNA_Point,
)

#: Every generated constant, for the ABI audit to re-read from C.
INPUT_CONSTANTS = (
    "CNA_HAPTIC_DIRECTION_TYPE_CARTESIAN",
    "CNA_HAPTIC_DIRECTION_TYPE_MAXIMUM",
    "CNA_HAPTIC_DIRECTION_TYPE_POLAR",
    "CNA_HAPTIC_DIRECTION_TYPE_SPHERICAL",
    "CNA_HAPTIC_DIRECTION_TYPE_STEERING_AXIS",
    "CNA_HAPTIC_EFFECT_INFINITE_LENGTH",
    "CNA_HAPTIC_EFFECT_TYPE_CONSTANT",
    "CNA_HAPTIC_EFFECT_TYPE_CUSTOM",
    "CNA_HAPTIC_EFFECT_TYPE_DAMPER",
    "CNA_HAPTIC_EFFECT_TYPE_FRICTION",
    "CNA_HAPTIC_EFFECT_TYPE_INERTIA",
    "CNA_HAPTIC_EFFECT_TYPE_LEFT_RIGHT",
    "CNA_HAPTIC_EFFECT_TYPE_MAXIMUM",
    "CNA_HAPTIC_EFFECT_TYPE_RAMP",
    "CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_DOWN",
    "CNA_HAPTIC_EFFECT_TYPE_SAWTOOTH_UP",
    "CNA_HAPTIC_EFFECT_TYPE_SINE",
    "CNA_HAPTIC_EFFECT_TYPE_SPRING",
    "CNA_HAPTIC_EFFECT_TYPE_SQUARE",
    "CNA_HAPTIC_EFFECT_TYPE_TRIANGLE",
    "CNA_HAPTIC_FEATURE_ALL",
    "CNA_HAPTIC_FEATURE_AUTOCENTER",
    "CNA_HAPTIC_FEATURE_CONSTANT",
    "CNA_HAPTIC_FEATURE_CUSTOM",
    "CNA_HAPTIC_FEATURE_DAMPER",
    "CNA_HAPTIC_FEATURE_FRICTION",
    "CNA_HAPTIC_FEATURE_GAIN",
    "CNA_HAPTIC_FEATURE_INERTIA",
    "CNA_HAPTIC_FEATURE_LEFT_RIGHT",
    "CNA_HAPTIC_FEATURE_NONE",
    "CNA_HAPTIC_FEATURE_PAUSE",
    "CNA_HAPTIC_FEATURE_RAMP",
    "CNA_HAPTIC_FEATURE_SAWTOOTH_DOWN",
    "CNA_HAPTIC_FEATURE_SAWTOOTH_UP",
    "CNA_HAPTIC_FEATURE_SINE",
    "CNA_HAPTIC_FEATURE_SPRING",
    "CNA_HAPTIC_FEATURE_SQUARE",
    "CNA_HAPTIC_FEATURE_STATUS",
    "CNA_HAPTIC_FEATURE_TRIANGLE",
    "CNA_JOYSTICK_HAT_POSITION_CENTERED",
    "CNA_JOYSTICK_HAT_POSITION_DOWN",
    "CNA_JOYSTICK_HAT_POSITION_LEFT",
    "CNA_JOYSTICK_HAT_POSITION_LEFT_DOWN",
    "CNA_JOYSTICK_HAT_POSITION_LEFT_UP",
    "CNA_JOYSTICK_HAT_POSITION_MAXIMUM",
    "CNA_JOYSTICK_HAT_POSITION_RIGHT",
    "CNA_JOYSTICK_HAT_POSITION_RIGHT_DOWN",
    "CNA_JOYSTICK_HAT_POSITION_RIGHT_UP",
    "CNA_JOYSTICK_HAT_POSITION_UP",
    "CNA_JOYSTICK_TYPE_ARCADE_PAD",
    "CNA_JOYSTICK_TYPE_ARCADE_STICK",
    "CNA_JOYSTICK_TYPE_DANCE_PAD",
    "CNA_JOYSTICK_TYPE_DRUM_KIT",
    "CNA_JOYSTICK_TYPE_FLIGHT_STICK",
    "CNA_JOYSTICK_TYPE_GAMEPAD",
    "CNA_JOYSTICK_TYPE_GUITAR",
    "CNA_JOYSTICK_TYPE_MAXIMUM",
    "CNA_JOYSTICK_TYPE_THROTTLE",
    "CNA_JOYSTICK_TYPE_UNKNOWN",
    "CNA_JOYSTICK_TYPE_WHEEL",
    "CNA_MOUSE_CURSOR_STOCK_ARROW",
    "CNA_MOUSE_CURSOR_STOCK_CROSSHAIR",
    "CNA_MOUSE_CURSOR_STOCK_HAND",
    "CNA_MOUSE_CURSOR_STOCK_IBEAM",
    "CNA_MOUSE_CURSOR_STOCK_NO",
    "CNA_MOUSE_CURSOR_STOCK_SIZE_ALL",
    "CNA_MOUSE_CURSOR_STOCK_SIZE_NESW",
    "CNA_MOUSE_CURSOR_STOCK_SIZE_NS",
    "CNA_MOUSE_CURSOR_STOCK_SIZE_NWSE",
    "CNA_MOUSE_CURSOR_STOCK_SIZE_WE",
    "CNA_MOUSE_CURSOR_STOCK_WAIT",
    "CNA_MOUSE_CURSOR_STOCK_WAIT_ARROW",
    "CNA_POWER_STATE_CHARGED",
    "CNA_POWER_STATE_CHARGING",
    "CNA_POWER_STATE_ERROR",
    "CNA_POWER_STATE_MAXIMUM",
    "CNA_POWER_STATE_NO_BATTERY",
    "CNA_POWER_STATE_ON_BATTERY",
    "CNA_POWER_STATE_UNKNOWN",
    "CNA_SENSOR_TYPE_ACCELEROMETER",
    "CNA_SENSOR_TYPE_ACCELEROMETER_LEFT",
    "CNA_SENSOR_TYPE_ACCELEROMETER_RIGHT",
    "CNA_SENSOR_TYPE_GYROSCOPE",
    "CNA_SENSOR_TYPE_GYROSCOPE_LEFT",
    "CNA_SENSOR_TYPE_GYROSCOPE_RIGHT",
    "CNA_SENSOR_TYPE_MAXIMUM",
    "CNA_SENSOR_TYPE_UNKNOWN",
    "CNA_TEXT_INPUT_TYPE_MAXIMUM",
    "CNA_TEXT_INPUT_TYPE_NUMBER",
    "CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_HIDDEN",
    "CNA_TEXT_INPUT_TYPE_NUMBER_PASSWORD_VISIBLE",
    "CNA_TEXT_INPUT_TYPE_TEXT",
    "CNA_TEXT_INPUT_TYPE_TEXT_EMAIL",
    "CNA_TEXT_INPUT_TYPE_TEXT_NAME",
    "CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_HIDDEN",
    "CNA_TEXT_INPUT_TYPE_TEXT_PASSWORD_VISIBLE",
    "CNA_TEXT_INPUT_TYPE_TEXT_USERNAME",
)
