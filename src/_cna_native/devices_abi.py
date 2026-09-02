"""Generated ctypes layouts and constants for CNA's ``sensors.h``, ``devices.h``.

Do not edit. ``tools/generate_family_abi.py`` derives this from the canonical
headers, and ``--check`` fails when the checked-in copy is not what the current
headers produce. Every size, alignment, field offset and constant here is
re-measured against the C compiler by ``tools/audit_cna_abi.py``.

Nothing in this module is public. ``cna.extensions.devices`` holds the
public projection; a ctypes object never crosses that boundary.
"""

from __future__ import annotations

import ctypes as c

from . import abi

# --- scalar identities -----------------------------------------------------

#: Fixed-width identities these headers declare as typedefs of a scalar.
#: They are enums in spirit and integers in the ABI; the public projection
#: turns them into Python enums, and this is only their width.
CNA_CameraPosition = c.c_uint32
CNA_CameraState = c.c_uint32
CNA_DeviceType = c.c_uint32
CNA_MessageBoxType = c.c_uint32
CNA_SensorState = c.c_uint32

#: Every opaque handle in this family is a ``CNA_Handle``. The names are kept
#: so a manifest entry can say which object a handle parameter refers to.
DEVICES_HANDLE_TYPES = (
    "CNA_AccelerometerHandle",
    "CNA_CameraHandle",
    "CNA_CompassHandle",
    "CNA_GyroscopeHandle",
    "CNA_MotionHandle",
    "CNA_SensorEventRegistrationHandle",
    "CNA_SystemTrayHandle",
)


# --- constants -------------------------------------------------------------

CNA_CAMERA_POSITION_BACK_FACING = 2
CNA_CAMERA_POSITION_FRONT_FACING = 1
CNA_CAMERA_POSITION_MAXIMUM = 2
CNA_CAMERA_POSITION_UNKNOWN = 0
CNA_CAMERA_STATE_CLOSED = 1
CNA_CAMERA_STATE_DENIED = 3
CNA_CAMERA_STATE_LOST = 5
CNA_CAMERA_STATE_MAXIMUM = 5
CNA_CAMERA_STATE_NOT_SUPPORTED = 0
CNA_CAMERA_STATE_OPENING = 2
CNA_CAMERA_STATE_READY = 4
CNA_DEVICE_TYPE_DEVICE = 0
CNA_DEVICE_TYPE_EMULATOR = 1
CNA_DEVICE_TYPE_MAXIMUM = 1
CNA_MESSAGE_BOX_TYPE_ERROR = 0
CNA_MESSAGE_BOX_TYPE_INFORMATION = 2
CNA_MESSAGE_BOX_TYPE_MAXIMUM = 2
CNA_MESSAGE_BOX_TYPE_WARNING = 1
CNA_POWER_STATE_MAXIMUM = 5
CNA_SENSOR_STATE_DISABLED = 5
CNA_SENSOR_STATE_INITIALIZING = 2
CNA_SENSOR_STATE_MAXIMUM = 5
CNA_SENSOR_STATE_NOT_SUPPORTED = 0
CNA_SENSOR_STATE_NO_DATA = 3
CNA_SENSOR_STATE_NO_PERMISSIONS = 4
CNA_SENSOR_STATE_READY = 1

# --- structures ------------------------------------------------------------

class CNA_DateTimeOffset(c.Structure):
    _fields_ = [
        ("ticks", c.c_int64),
        ("offset_ticks", c.c_int64),
    ]

class CNA_AccelerometerReading(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("acceleration", abi.CNA_Vector3),
    ]

class CNA_GyroscopeReading(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("rotation_rate", abi.CNA_Vector3),
    ]

class CNA_AttitudeReading(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("pitch", c.c_float),
        ("roll", c.c_float),
        ("yaw", c.c_float),
        ("quaternion", abi.CNA_Quaternion),
        ("rotation_matrix", abi.CNA_Matrix),
    ]

class CNA_CompassReading(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("heading_accuracy", c.c_double),
        ("magnetic_heading", c.c_double),
        ("true_heading", c.c_double),
        ("magnetometer_reading", abi.CNA_Vector3),
    ]

class CNA_MotionReading(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("attitude", CNA_AttitudeReading),
        ("device_acceleration", abi.CNA_Vector3),
        ("device_rotation_rate", abi.CNA_Vector3),
        ("gravity", abi.CNA_Vector3),
    ]

class CNA_AccelerometerReadingEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("timestamp", CNA_DateTimeOffset),
        ("x", c.c_double),
        ("y", c.c_double),
        ("z", c.c_double),
    ]

class CNA_VibrationTestLog(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("start_calls", c.c_uint32),
        ("stop_calls", c.c_uint32),
        ("left_right_calls", c.c_uint32),
        ("reserved", c.c_uint32),
        ("last_duration_ticks", c.c_int64),
        ("last_intensity", c.c_float),
        ("last_large_motor", c.c_float),
        ("last_small_motor", c.c_float),
        ("reserved_float", c.c_float),
    ]

class CNA_MessageBoxTestLog(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("simple_calls", c.c_uint32),
        ("choice_calls", c.c_uint32),
        ("last_type", c.c_uint32),
        ("last_button_count", c.c_uint32),
    ]

class CNA_FileDialogFilter(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("name", abi.CNA_StringView),
        ("pattern", abi.CNA_StringView),
    ]

class CNA_CameraDeviceInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("position", c.c_uint32),
    ]


#: Function pointers this family hands to CNA. A Python callable
#: bound to one of these must be rooted for as long as CNA can call it;
#: the trampoline is what CNA holds, not the Python object.
CNA_SensorEventCallback = c.CFUNCTYPE(None, c.c_void_p)
CNA_AccelerometerReadingCallback = c.CFUNCTYPE(None, c.POINTER(CNA_AccelerometerReading), c.c_void_p)
CNA_GyroscopeReadingCallback = c.CFUNCTYPE(None, c.POINTER(CNA_GyroscopeReading), c.c_void_p)
CNA_AccelerometerReadingEventCallback = c.CFUNCTYPE(None, c.POINTER(CNA_AccelerometerReadingEventInfo), c.c_void_p)
CNA_CompassReadingCallback = c.CFUNCTYPE(None, c.POINTER(CNA_CompassReading), c.c_void_p)
CNA_MotionReadingCallback = c.CFUNCTYPE(None, c.POINTER(CNA_MotionReading), c.c_void_p)
CNA_FileDialogResultCallback = c.CFUNCTYPE(None, c.POINTER(abi.CNA_StringView), c.c_uint64, c.c_void_p)
CNA_TrayEntryClickCallback = c.CFUNCTYPE(None, c.c_void_p)

#: Every generated callback type, for the ABI audit.
DEVICES_CALLBACKS = (
    "CNA_SensorEventCallback",
    "CNA_AccelerometerReadingCallback",
    "CNA_GyroscopeReadingCallback",
    "CNA_AccelerometerReadingEventCallback",
    "CNA_CompassReadingCallback",
    "CNA_MotionReadingCallback",
    "CNA_FileDialogResultCallback",
    "CNA_TrayEntryClickCallback",
)

#: Which of each callback's parameters are pointers to const.
#:
#: ``const`` is not an ABI property and ctypes cannot carry it, but C
#: declaration compatibility distinguishes ``const T*`` from ``T*`` -- so
#: the compiler-backed prototype gate needs it to spell a function-pointer
#: parameter the way the canonical typedef does. Derived here rather than
#: written down there, because it is a fact about the header.
DEVICES_CALLBACK_CONST_PARAMETERS = {
    "CNA_SensorEventCallback": (False,),
    "CNA_AccelerometerReadingCallback": (True, False),
    "CNA_GyroscopeReadingCallback": (True, False),
    "CNA_AccelerometerReadingEventCallback": (True, False),
    "CNA_CompassReadingCallback": (True, False),
    "CNA_MotionReadingCallback": (True, False),
    "CNA_FileDialogResultCallback": (True, False, False),
    "CNA_TrayEntryClickCallback": (False,),
}

# --- constants derived from a generated layout ------------------------------


#: Each structure field's own ``@brief`` from the canonical header, so a
#: public projection documents a field with CNA's own words rather than a
#: second summary that can drift from it.
DEVICES_FIELD_DOCUMENTATION = {
    "CNA_DateTimeOffset": {
        "ticks": "Local time in 100-nanosecond ticks since 0001-01-01.",
        "offset_ticks": "Offset from UTC in 100-nanosecond ticks.",
    },
    "CNA_AccelerometerReading": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "acceleration": "Acceleration in g, per axis.",
    },
    "CNA_GyroscopeReading": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "rotation_rate": "Angular velocity in radians per second, per axis.",
    },
    "CNA_AttitudeReading": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "pitch": "Rotation around the X axis, in radians.",
        "roll": "Rotation around the Y axis, in radians.",
        "yaw": "Rotation around the Z axis, in radians.",
        "quaternion": "The same orientation as a quaternion.",
        "rotation_matrix": "The same orientation as a rotation matrix.",
    },
    "CNA_CompassReading": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "heading_accuracy": "Accuracy of the heading, in degrees.",
        "magnetic_heading": "Heading relative to magnetic north, in degrees.",
        "true_heading": "Heading relative to true north, in degrees.",
        "magnetometer_reading": "Raw magnetometer reading in micro-teslas, per axis.",
    },
    "CNA_MotionReading": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "attitude": "The fused device orientation.",
        "device_acceleration": "Acceleration excluding gravity, in g, per axis.",
        "device_rotation_rate": "Angular velocity in radians per second, per axis.",
        "gravity": "The gravity vector, in g, per axis.",
    },
    "CNA_AccelerometerReadingEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "timestamp": "When the reading was taken.",
        "x": "Acceleration along the X axis, in g.",
        "y": "Acceleration along the Y axis, in g.",
        "z": "Acceleration along the Z axis, in g.",
    },
    "CNA_VibrationTestLog": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "start_calls": "Number of single-motor start requests received.",
        "stop_calls": "Number of stop requests received.",
        "left_right_calls": "Number of two-motor start requests received.",
        "reserved": "Padding; always zero.",
        "last_duration_ticks": "Duration of the most recent start request, in 100-nanosecond ticks.",
        "last_intensity": "Intensity of the most recent single-motor start request.",
        "last_large_motor": "Large-motor strength of the most recent two-motor start request.",
        "last_small_motor": "Small-motor strength of the most recent two-motor start request.",
        "reserved_float": "Padding; always zero.",
    },
    "CNA_MessageBoxTestLog": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "simple_calls": "Number of dismiss-only message boxes requested.",
        "choice_calls": "Number of button-answering message boxes requested.",
        "last_type": "Severity of the most recent request.",
        "last_button_count": "Number of button labels in the most recent button-answering request.",
    },
    "CNA_FileDialogFilter": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "name": "Human-readable filter name.",
        "pattern": "Platform filter pattern.",
    },
    "CNA_CameraDeviceInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "position": "One `CNA_CAMERA_POSITION_ ` identity.",
    },
}

#: Every generated structure, in declaration order, for the ABI audit.
DEVICES_STRUCTURES = (
    CNA_DateTimeOffset,
    CNA_AccelerometerReading,
    CNA_GyroscopeReading,
    CNA_AttitudeReading,
    CNA_CompassReading,
    CNA_MotionReading,
    CNA_AccelerometerReadingEventInfo,
    CNA_VibrationTestLog,
    CNA_MessageBoxTestLog,
    CNA_FileDialogFilter,
    CNA_CameraDeviceInfo,
)

#: Every generated constant, for the ABI audit to re-read from C.
DEVICES_CONSTANTS = (
    "CNA_CAMERA_POSITION_BACK_FACING",
    "CNA_CAMERA_POSITION_FRONT_FACING",
    "CNA_CAMERA_POSITION_MAXIMUM",
    "CNA_CAMERA_POSITION_UNKNOWN",
    "CNA_CAMERA_STATE_CLOSED",
    "CNA_CAMERA_STATE_DENIED",
    "CNA_CAMERA_STATE_LOST",
    "CNA_CAMERA_STATE_MAXIMUM",
    "CNA_CAMERA_STATE_NOT_SUPPORTED",
    "CNA_CAMERA_STATE_OPENING",
    "CNA_CAMERA_STATE_READY",
    "CNA_DEVICE_TYPE_DEVICE",
    "CNA_DEVICE_TYPE_EMULATOR",
    "CNA_DEVICE_TYPE_MAXIMUM",
    "CNA_MESSAGE_BOX_TYPE_ERROR",
    "CNA_MESSAGE_BOX_TYPE_INFORMATION",
    "CNA_MESSAGE_BOX_TYPE_MAXIMUM",
    "CNA_MESSAGE_BOX_TYPE_WARNING",
    "CNA_POWER_STATE_MAXIMUM",
    "CNA_SENSOR_STATE_DISABLED",
    "CNA_SENSOR_STATE_INITIALIZING",
    "CNA_SENSOR_STATE_MAXIMUM",
    "CNA_SENSOR_STATE_NOT_SUPPORTED",
    "CNA_SENSOR_STATE_NO_DATA",
    "CNA_SENSOR_STATE_NO_PERMISSIONS",
    "CNA_SENSOR_STATE_READY",
)
