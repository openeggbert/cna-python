"""CNA's deterministic device backends, for qualification rather than for games.

Every function here installs or drives a backend CNA supplies **instead of** a
physical device or a host window. They exist so a sensor state machine, a frame
protocol, a dialog's exactly-once answer and a vibration request can be measured
without hardware and without putting anything on someone's desktop.

Read the boundary literally:

* A result obtained through this module is ``SYNTHETIC_BACKEND_VERIFIED``. It is
  evidence about the protocol, the state machine and this binding.
* It is **never** ``PHYSICAL_HARDWARE_VERIFIED``. No accelerometer was tilted,
  no camera was opened, no motor spun.

A shipping game should not import this module. Nothing else in
``cna.extensions.devices`` does, and the extension surface gate records that.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, Sequence, TYPE_CHECKING

from _cna_native import devices_abi as _devices
from _cna_native import devices_support as _dev
from _cna_native.family_support import CallbackRoot, checked, real, string_view

from .camera import Camera
from .dialogs import MessageBoxTestLog, SystemTray
from .sensors import (
    Accelerometer, CompassReading, Gyroscope, MotionReading, _Sensor,
)
from .values import CameraState, MessageBoxType
from .vibration import VibrationTestLog

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game
    from Microsoft.Xna.Framework.Graphics import Color

__all__ = [
    "inject_accelerometer_update",
    "inject_gyroscope_update",
    "inject_compass_reading",
    "inject_compass_calibration_request",
    "inject_motion_reading",
    "inject_motion_calibration_request",
    "install_compass_test_backend",
    "install_motion_test_backend",
    "set_sensor_supported",
    "set_sensor_started",
    "sensor_subsystem_held",
    "register_started_sensor",
    "unregister_started_sensor",
    "dispatch_to_started_sensors",
    "sensor_dispatch_exception_count",
    "last_sensor_dispatch_exception_message",
    "set_sensor_event_watch_registration_failure",
    "is_sensor_connected",
    "set_sensor_disposal_cleanup_hook",
    "open_test_camera",
    "set_camera_test_frame",
    "set_camera_test_state",
    "install_file_dialog_test_backend",
    "install_message_box_test_backend",
    "message_box_test_log",
    "open_test_system_tray",
    "click_tray_entry",
    "install_vibration_test_backend",
    "vibration_test_log",
]

_support = _dev.support
_VERSION = 1

#: Disposal hooks stay rooted for as long as CNA can call them.
_hooks = CallbackRoot()

#: Which sensors accept which test route, so a caller cannot ask the compass for
#: an accelerometer-only operation and get a confusing native error instead of a
#: Python one.
_THREE_AXIS = (Accelerometer, Gyroscope)


def _prefix(sensor: _Sensor, allowed=None, what: str = "sensor") -> str:
    if not isinstance(sensor, _Sensor):
        raise TypeError(f"{what} must be a sensor, not {type(sensor).__name__}")
    if allowed is not None and not isinstance(sensor, allowed):
        raise TypeError(
            f"{what} must be one of "
            + ", ".join(kind.__name__ for kind in allowed)
            + f", not {type(sensor).__name__}")
    return sensor._prefix


# --- sensors ----------------------------------------------------------------


def inject_accelerometer_update(sensor: Accelerometer, x: float, y: float,
                                z: float) -> None:
    """Delivers one synthetic accelerometer sample to ``sensor``."""
    _support.call("cna_accelerometer_inject_synthetic_update_ext",
                  sensor._handle.argument, c.c_float(real(x, "x")),
                  c.c_float(real(y, "y")), c.c_float(real(z, "z")))


def inject_gyroscope_update(sensor: Gyroscope, x: float, y: float, z: float) -> None:
    """Delivers one synthetic gyroscope sample to ``sensor``."""
    _support.call("cna_gyroscope_inject_synthetic_update_ext",
                  sensor._handle.argument, c.c_float(real(x, "x")),
                  c.c_float(real(y, "y")), c.c_float(real(z, "z")))


def inject_compass_reading(sensor, reading: CompassReading) -> None:
    """Delivers one whole synthetic compass reading, timestamp included."""
    native = reading._to_native()
    _support.call("cna_compass_inject_synthetic_update_ext",
                  sensor._handle.argument, c.byref(native))


def inject_motion_reading(sensor, reading: MotionReading) -> None:
    """Delivers one whole synthetic fused-motion reading."""
    native = reading._to_native()
    _support.call("cna_motion_inject_synthetic_update_ext",
                  sensor._handle.argument, c.byref(native))


def inject_compass_calibration_request(sensor) -> None:
    """Makes the compass ask to be calibrated."""
    _support.call("cna_compass_inject_calibration_request_ext",
                  sensor._handle.argument)


def inject_motion_calibration_request(sensor) -> None:
    """Makes the fused motion sensor ask to be calibrated."""
    _support.call("cna_motion_inject_calibration_request_ext",
                  sensor._handle.argument)


def install_compass_test_backend(sensor, *, installed: bool = True,
                                 supported: bool = True) -> None:
    """Installs or removes the compass's deterministic backend."""
    _support.call("cna_compass_set_test_backend_ext", sensor._handle.argument,
                  c.c_uint8(1 if installed else 0),
                  c.c_uint8(1 if supported else 0))


def install_motion_test_backend(sensor, *, installed: bool = True,
                                supported: bool = True,
                                north_referenced: bool = False) -> None:
    """Installs or removes the fused motion sensor's deterministic backend."""
    _support.call("cna_motion_set_test_backend_ext", sensor._handle.argument,
                  c.c_uint8(1 if installed else 0),
                  c.c_uint8(1 if supported else 0),
                  c.c_uint8(1 if north_referenced else 0))


def set_sensor_supported(sensor, supported: bool) -> None:
    """Overrides whether the accelerometer or gyroscope reports itself supported."""
    _support.call(f"{_prefix(sensor, _THREE_AXIS)}_set_supported_for_tests_ext",
                  sensor._handle.argument, c.c_uint8(1 if supported else 0))


def set_sensor_started(sensor, started: bool) -> None:
    """Forces the started flag of the accelerometer or gyroscope."""
    _support.call(f"{_prefix(sensor, _THREE_AXIS)}_set_started_for_tests_ext",
                  sensor._handle.argument, c.c_uint8(1 if started else 0))


def sensor_subsystem_held(sensor) -> bool:
    """Whether the sensor still holds the sensor subsystem open.

    This is what makes ``dispose`` observable: a disposed sensor releases the
    hold, and nothing else about the object changes.
    """
    return _support.out_bool(
        f"{_prefix(sensor, _THREE_AXIS)}_get_subsystem_held_for_tests_ext",
        sensor._handle.argument)


def register_started_sensor(sensor) -> None:
    """Adds a sensor to the set a broadcast dispatch reaches."""
    _support.call(f"{_prefix(sensor, _THREE_AXIS)}_register_started_instance_for_tests_ext",
                  sensor._handle.argument)


def unregister_started_sensor(sensor) -> None:
    """Removes a sensor from the set a broadcast dispatch reaches."""
    _support.call(f"{_prefix(sensor, _THREE_AXIS)}_unregister_started_instance_for_tests_ext",
                  sensor._handle.argument)


def dispatch_to_started_sensors(game: "Game", sensors: Sequence, x: float,
                                y: float, z: float) -> None:
    """Delivers one sample to several sensors at once.

    All of ``sensors`` must be the same kind, because CNA's route is per kind and
    mixing them would silently deliver to only some.
    """
    sensors = tuple(sensors)
    if not sensors:
        raise ValueError("dispatch_to_started_sensors needs at least one sensor")
    kinds = {type(sensor) for sensor in sensors}
    if len(kinds) != 1:
        raise TypeError("every sensor in one dispatch must be the same kind")
    prefix = _prefix(sensors[0], _THREE_AXIS)
    handles = (c.c_uint64 * len(sensors))(
        *(sensor._handle.value for sensor in sensors))
    _support.call(f"{prefix}_dispatch_to_instances_for_tests_ext",
                  _dev.game_handle(game, "sensor dispatch"), handles,
                  c.c_uint64(len(sensors)), c.c_float(real(x, "x")),
                  c.c_float(real(y, "y")), c.c_float(real(z, "z")))


def sensor_dispatch_exception_count(game: "Game", kind: type) -> int:
    """How many handler exceptions CNA swallowed during a broadcast dispatch."""
    prefix = _kind_probe(kind)._prefix
    return _support.out_i32(f"{prefix}_get_dispatch_exception_count_for_tests_ext",
                            _dev.game_handle(game, "sensor dispatch"))


def last_sensor_dispatch_exception_message(game: "Game", kind: type) -> str:
    """CNA's message for the most recent handler exception during a dispatch."""
    prefix = _kind_probe(kind)._prefix
    return _support.copied_text(
        f"{prefix}_copy_last_dispatch_exception_message_for_tests_ext",
        (_dev.game_handle(game, "sensor dispatch"),), "dispatch exception message")


def set_sensor_event_watch_registration_failure(game: "Game", kind: type,
                                                should_fail: bool) -> None:
    """Makes the next event-watch registration of ``kind`` fail."""
    prefix = _kind_probe(kind)._prefix
    _support.call(f"{prefix}_set_event_watch_registration_failure_for_tests_ext",
                  _dev.game_handle(game, "sensor dispatch"),
                  c.c_uint8(1 if should_fail else 0))


def is_sensor_connected(game: "Game", kind: type, sensor_id: int) -> bool:
    """Whether CNA considers a sensor of ``kind`` with ``sensor_id`` connected."""
    prefix = _kind_probe(kind)._prefix
    return _support.out_bool(f"{prefix}_is_sensor_connected_for_tests_ext",
                             _dev.game_handle(game, "sensor connection"),
                             c.c_int64(checked(sensor_id, "int64", "sensor_id")))


def set_sensor_disposal_cleanup_hook(sensor, handler: Callable[[], None] | None) -> None:
    """Calls ``handler()`` when CNA cleans the sensor up, or clears the hook."""
    prefix = _prefix(sensor, _THREE_AXIS)
    if handler is None:
        _hooks.release(sensor)
        _support.call(f"{prefix}_set_disposal_cleanup_hook_for_tests_ext",
                      sensor._handle.argument, _devices.CNA_SensorEventCallback(), None)
        return

    def adapt(_context) -> None:
        handler()

    trampoline = _hooks.root(sensor, _devices.CNA_SensorEventCallback, adapt)
    _support.call(f"{prefix}_set_disposal_cleanup_hook_for_tests_ext",
                  sensor._handle.argument, trampoline, None)


class _KindProbe:
    """A stand-in that carries only the route prefix a class-level route needs."""

    __slots__ = ("_prefix",)

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix


_PREFIXES = {Accelerometer: "cna_accelerometer", Gyroscope: "cna_gyroscope"}


def _kind_probe(kind: type):
    prefix = _PREFIXES.get(kind)
    if prefix is None:
        raise TypeError(
            "kind must be Accelerometer or Gyroscope, "
            f"not {getattr(kind, '__name__', kind)!r}")
    probe = _KindProbe(prefix)
    return probe


# --- camera -----------------------------------------------------------------


def open_test_camera(game: "Game") -> Camera:
    """Opens a camera over CNA's deterministic backend. No hardware is touched."""
    handle = _support.out_handle("cna_camera_create_with_test_backend_ext",
                                 _dev.game_handle(game, "test camera"))
    return Camera._adopt(handle)


def set_camera_test_frame(camera: Camera, width: int, height: int,
                          pixels: Sequence["Color"]) -> None:
    """Sets the frame the test backend hands out next.

    ``pixels`` is a row-major sequence of strict ``Color`` values, and its length
    must be ``width * height``; a short sequence is refused here rather than
    read past by CNA.
    """
    from _cna_native import abi

    width = checked(width, "int32", "width")
    height = checked(height, "int32", "height")
    pixels = tuple(pixels)
    if len(pixels) != width * height:
        raise ValueError(
            f"pixels must hold width * height = {width * height} entries, "
            f"got {len(pixels)}")
    array = (abi.CNA_Color * len(pixels))()
    for index, colour in enumerate(pixels):
        array[index].r = int(colour.R)
        array[index].g = int(colour.G)
        array[index].b = int(colour.B)
        array[index].a = int(colour.A)
    _support.call("cna_camera_set_test_frame_ext", camera._handle.argument,
                  c.c_int32(width), c.c_int32(height), array,
                  c.c_uint64(len(pixels)))


def set_camera_test_state(camera: Camera, state: CameraState) -> None:
    """Forces the state the test-backed camera reports."""
    _support.call("cna_camera_set_test_state_ext", camera._handle.argument,
                  c.c_uint32(CameraState(state)))


# --- host UI ----------------------------------------------------------------


def install_file_dialog_test_backend(game: "Game", *, installed: bool = True,
                                     results: Sequence[str] | None = None) -> None:
    """Installs a file-dialog backend that answers with ``results`` immediately.

    ``results=None`` or an empty sequence answers with nothing, which is how the
    canonical dialog reports cancellation.
    """
    from _cna_native import abi

    results = tuple(results or ())
    keep: list[bytes] = []
    array = (abi.CNA_StringView * len(results))() if results else None
    for index, value in enumerate(results):
        view, encoded = string_view(value, f"results[{index}]")
        array[index] = view
        keep.append(encoded)
    _support.call("cna_file_dialog_set_test_backend_ext",
                  _dev.game_handle(game, "file dialog test backend"),
                  c.c_uint8(1 if installed else 0), array, c.c_uint64(len(results)))


def install_message_box_test_backend(game: "Game", *, installed: bool = True,
                                     chosen_button: int = 0) -> None:
    """Installs a message-box backend that chooses ``chosen_button`` and logs."""
    _support.call("cna_message_box_set_test_backend_ext",
                  _dev.game_handle(game, "message box test backend"),
                  c.c_uint8(1 if installed else 0),
                  c.c_int32(checked(chosen_button, "int32", "chosen_button")))


def message_box_test_log(game: "Game") -> MessageBoxTestLog:
    """What the installed message-box test backend has been asked to do."""
    native = _support.out_struct(
        _devices.CNA_MessageBoxTestLog, _VERSION, "cna_message_box_get_test_log_ext",
        _dev.game_handle(game, "message box test log"))
    return MessageBoxTestLog(int(native.simple_calls), int(native.choice_calls),
                             MessageBoxType(int(native.last_type)),
                             int(native.last_button_count))


def open_test_system_tray(game: "Game", tooltip: str = "") -> SystemTray:
    """Creates a tray over CNA's deterministic backend; nothing reaches a desktop."""
    view, _keep = string_view(tooltip, "tooltip")
    handle = _support.out_handle("cna_system_tray_create_with_test_backend_ext",
                                 _dev.game_handle(game, "test system tray"), view)
    return SystemTray._over(handle)


def click_tray_entry(tray: SystemTray, index: int) -> None:
    """Clicks one entry of a test-backed tray."""
    _support.call("cna_system_tray_click_entry_for_tests_ext", tray._handle.argument,
                  c.c_uint64(checked(index, "uint64", "index")))


# --- vibration --------------------------------------------------------------


def install_vibration_test_backend(game: "Game", *, installed: bool = True,
                                   supported: bool = True,
                                   device_name: str = "") -> None:
    """Installs a vibration backend that records requests instead of performing them.

    Installing resets the log, which is CNA's behaviour and is relied on rather
    than worked around.
    """
    view, _keep = string_view(device_name, "device_name")
    _support.call("cna_vibrate_controller_set_test_backend_ext",
                  _dev.game_handle(game, "vibration test backend"),
                  c.c_uint8(1 if installed else 0),
                  c.c_uint8(1 if supported else 0), view)


def vibration_test_log(game: "Game") -> VibrationTestLog:
    """What the installed vibration test backend has been asked to do."""
    native = _support.out_struct(
        _devices.CNA_VibrationTestLog, _VERSION,
        "cna_vibrate_controller_get_test_log_ext",
        _dev.game_handle(game, "vibration test log"))
    return VibrationTestLog(
        int(native.start_calls), int(native.stop_calls), int(native.left_right_calls),
        int(native.last_duration_ticks), float(native.last_intensity),
        float(native.last_large_motor), float(native.last_small_motor))
