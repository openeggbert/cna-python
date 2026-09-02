"""CNA's sensors and device services: hardware XNA 4.0 on Windows never had.

This is a **CNA extension**, not part of XNA. The accelerometer, compass,
gyroscope and fused motion sensor are the Windows Phone sensor family; the
camera, clipboard, locales, power, display metrics, file dialogs, message boxes,
system tray and controller vibration are host services. None of them has a
``Microsoft.Xna.Framework`` counterpart on the selected profile, which is
exactly why they live here.

**The strict XNA projection is untouched by this package.** No name in
``Microsoft.Xna.Framework`` changes, gains a member, or learns that this package
exists. The dependency runs one way -- this package accepts a strict ``Game``,
``Texture2D``, ``Vector3``, ``Matrix``, ``Quaternion``, ``Color`` and
``Rectangle`` -- and the extension gate asserts in a fresh interpreter that
importing the XNA namespace loads no ``cna`` module.

Two kinds of "not supported"
----------------------------

Every device route is exported in every CNA build. The ones that need the
device-services layer answer ``CNA_RESULT_NOT_SUPPORTED`` when it was configured
out, which is the same result code a host without a battery gives. This package
never conflates the two: :func:`~cna.extensions.devices.host.device_services_available`
asks ``cna_devices_ext_is_available``, and a build with no layer raises
:class:`~cna.extensions.devices.errors.DeviceServicesUnavailableError` rather
than the generic unsupported error.

Time
----

Every timestamp and every duration is an exact 64-bit count of 100-nanosecond
ticks, and stays an integer.
:class:`~cna.extensions.devices.values.DateTimeOffset` holds two of them.
Conversion to :class:`datetime.datetime` is offered and is lossy by
construction, so the part it cannot carry is exposed rather than dropped.

Privacy
-------

Nothing here opens a camera, records audio, or shows a window unless a caller
explicitly asks for it. Enumeration opens nothing.
:mod:`cna.extensions.devices.testing` installs CNA's deterministic backends, and
that is what the qualification uses: a result obtained through it is evidence
about the protocol, never about hardware.

Ownership
---------

Every object holding a CNA handle has an explicit ``close`` and works as a
context manager. Closing is deterministic and ordered by the caller. Nothing
relies on ``__del__``: interpreter shutdown may already have unloaded the
library, so a finalizer that called into it would be a crash rather than a
cleanup. Closing a sensor releases every subscription it still holds first, so a
handler can never run after the object it was registered on is gone.

No raw handle, ctypes object or result code is public anywhere in this package.

Importing this module needs no native library. Constructing anything in it does.
"""

from __future__ import annotations

from . import camera, dialogs, errors, host, sensors, values, vibration
from .camera import (
    Camera, CameraDeviceInfo, camera_count, camera_info, camera_name, cameras,
    is_camera_supported,
)
from .dialogs import (
    FileDialogFilter, MessageBoxTestLog, SystemTray, are_file_dialogs_supported,
    is_message_box_supported, is_system_tray_supported, pending_dialog_count,
    show_message_box, show_open_file_dialog, show_open_folder_dialog,
    show_save_file_dialog, show_simple_message_box,
)
from .errors import (
    DeviceArgumentError, DeviceDisposedError, DeviceError, DeviceInternalError,
    DeviceServicesUnavailableError, DeviceStateError, DeviceThreadError,
    DeviceUnsupportedError,
)
from .host import (
    Locale, PowerInformation, SystemInformation, clipboard_text, content_scale,
    device_services_available, device_type, open_url, power_information,
    preferred_locales, safe_area, set_clipboard_text, system_information,
)
from .sensors import (
    Accelerometer, AccelerometerReading, AccelerometerReadingEventInfo,
    AttitudeReading, Compass, CompassReading, Gyroscope, GyroscopeReading, Motion,
    MotionReading, SensorSubscription, last_sensor_error_id, reading_hash_code,
    reading_text, readings_equal,
)
from .values import (
    CameraPosition, CameraState, DateTimeOffset, DeviceType, MessageBoxType,
    PowerState, SensorState, TICKS_PER_MICROSECOND, TICKS_PER_SECOND,
)
from .vibration import (
    VibrationTestLog, is_vibration_supported, start_vibration,
    start_vibration_left_right, start_vibration_with_intensity, stop_vibration,
    ticks_for, vibration_device_name,
)

__all__ = [
    "camera", "dialogs", "errors", "host", "sensors", "values", "vibration",
    # camera
    "Camera", "CameraDeviceInfo", "camera_count", "camera_info", "camera_name",
    "cameras", "is_camera_supported",
    # dialogs
    "FileDialogFilter", "MessageBoxTestLog", "SystemTray",
    "are_file_dialogs_supported", "is_message_box_supported",
    "is_system_tray_supported", "pending_dialog_count", "show_message_box",
    "show_open_file_dialog", "show_open_folder_dialog", "show_save_file_dialog",
    "show_simple_message_box",
    # errors
    "DeviceArgumentError", "DeviceDisposedError", "DeviceError",
    "DeviceInternalError", "DeviceServicesUnavailableError", "DeviceStateError",
    "DeviceThreadError", "DeviceUnsupportedError",
    # host
    "Locale", "PowerInformation", "SystemInformation", "clipboard_text",
    "content_scale", "device_services_available", "device_type", "open_url",
    "power_information", "preferred_locales", "safe_area", "set_clipboard_text",
    "system_information",
    # sensors
    "Accelerometer", "AccelerometerReading", "AccelerometerReadingEventInfo",
    "AttitudeReading", "Compass", "CompassReading", "Gyroscope",
    "GyroscopeReading", "Motion", "MotionReading", "SensorSubscription",
    "last_sensor_error_id", "reading_hash_code", "reading_text", "readings_equal",
    # values
    "CameraPosition", "CameraState", "DateTimeOffset", "DeviceType",
    "MessageBoxType", "PowerState", "SensorState", "TICKS_PER_MICROSECOND",
    "TICKS_PER_SECOND",
    # vibration
    "VibrationTestLog", "is_vibration_supported", "start_vibration",
    "start_vibration_left_right", "start_vibration_with_intensity",
    "stop_vibration", "ticks_for", "vibration_device_name",
]
