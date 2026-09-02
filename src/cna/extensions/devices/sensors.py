"""The four device sensors CNA exposes: accelerometer, compass, gyroscope, motion.

XNA 4.0 on Windows has no sensor API at all -- these are the Windows Phone
sensor family, which CNA implements for every target -- so nothing here belongs
in ``Microsoft.Xna.Framework`` and nothing here changes it.

Every sensor has the same shape, because CNA gives them the same shape: ask
whether the host supports it, create one over a running ``Game``, ``start`` it,
read ``current_value`` or subscribe to changes, ``stop`` it, and close it. The
differences are the reading each produces and the two extra events the compass
and the fused motion sensor raise when they want calibrating.

Timestamps
----------

Every reading carries a :class:`~cna.extensions.devices.values.DateTimeOffset`,
which is two exact 64-bit tick counts. Nothing here converts a tick count to a
float, and ``time_between_updates`` is available both as ticks and as a
:class:`datetime.timedelta`; the timedelta form refuses rather than rounds when
the interval is not a whole number of microseconds.

Lifetime
--------

``close`` is the mechanism and there is no ``__del__``: at interpreter shutdown
the library may already be unloaded, so a finalizer calling into it would be a
crash rather than a cleanup. Every sensor is a context manager. Closing a sensor
releases every subscription it still holds first, so no callback can arrive
after the object that owns it is gone.

CNA distinguishes ``dispose`` -- stop the sensor and release its hold on the
sensor subsystem, keeping the object usable -- from ``destroy``, which ends the
object. Both are here, under those names.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, TYPE_CHECKING

from Microsoft.Xna.Framework import Matrix, Quaternion, Vector3

from _cna_native import devices_abi as _devices
from _cna_native import devices_support as _dev
from _cna_native.family_support import CallbackRoot, checked, real

from .values import (
    DateTimeOffset, SensorState, TICKS_PER_MICROSECOND,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "AccelerometerReading",
    "GyroscopeReading",
    "AttitudeReading",
    "CompassReading",
    "MotionReading",
    "AccelerometerReadingEventInfo",
    "SensorSubscription",
    "Accelerometer",
    "Compass",
    "Gyroscope",
    "Motion",
    "last_sensor_error_id",
    "reading_text",
    "readings_equal",
    "reading_hash_code",
]

_support = _dev.support
#: Every versioned structure in this family is version 1, which is the only
#: version ``sensors.h`` declares.
_VERSION = 1


def _vector(value) -> Vector3:
    return Vector3(float(value.x), float(value.y), float(value.z))


def _to_vector(value: Vector3, what: str):
    if not isinstance(value, Vector3):
        raise TypeError(f"{what} must be a Vector3, not {type(value).__name__}")
    native = _devices.abi.CNA_Vector3()
    native.x, native.y, native.z = float(value.X), float(value.Y), float(value.Z)
    return native


def _interval(ticks: int) -> timedelta:
    if ticks % TICKS_PER_MICROSECOND:
        raise ValueError(
            "the update interval is not a whole number of microseconds and cannot "
            f"be a timedelta: {ticks} ticks")
    return timedelta(microseconds=ticks // TICKS_PER_MICROSECOND)


# --- readings ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AccelerometerReading:
    """One accelerometer sample: acceleration in g, per axis, and when it was taken."""

    timestamp: DateTimeOffset
    acceleration: Vector3

    @classmethod
    def _from_native(cls, value) -> "AccelerometerReading":
        return cls(DateTimeOffset._from_native(value.timestamp),
                   _vector(value.acceleration))

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_AccelerometerReading, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.acceleration = _to_vector(self.acceleration, "acceleration")
        return native


@dataclass(frozen=True, slots=True)
class GyroscopeReading:
    """One gyroscope sample: angular velocity in radians per second, per axis."""

    timestamp: DateTimeOffset
    rotation_rate: Vector3

    @classmethod
    def _from_native(cls, value) -> "GyroscopeReading":
        return cls(DateTimeOffset._from_native(value.timestamp),
                   _vector(value.rotation_rate))

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_GyroscopeReading, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.rotation_rate = _to_vector(self.rotation_rate, "rotation_rate")
        return native


@dataclass(frozen=True, slots=True)
class AttitudeReading:
    """One device-orientation sample, in all three forms CNA reports it in.

    ``pitch``, ``roll`` and ``yaw`` are radians; ``quaternion`` and
    ``rotation_matrix`` describe the same orientation. All three are CNA's, not
    derived here, because deriving one from another would create a second answer
    that can disagree with the sensor's.
    """

    timestamp: DateTimeOffset
    pitch: float
    roll: float
    yaw: float
    quaternion: Quaternion
    rotation_matrix: Matrix

    @classmethod
    def _from_native(cls, value) -> "AttitudeReading":
        quaternion = Quaternion(float(value.quaternion.x), float(value.quaternion.y),
                                float(value.quaternion.z), float(value.quaternion.w))
        matrix = Matrix(*(float(getattr(value.rotation_matrix, f"m{row}{column}"))
                          for row in range(1, 5) for column in range(1, 5)))
        return cls(DateTimeOffset._from_native(value.timestamp),
                   float(value.pitch), float(value.roll), float(value.yaw),
                   quaternion, matrix)

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_AttitudeReading, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.pitch = real(self.pitch, "pitch")
        native.roll = real(self.roll, "roll")
        native.yaw = real(self.yaw, "yaw")
        native.quaternion.x = float(self.quaternion.X)
        native.quaternion.y = float(self.quaternion.Y)
        native.quaternion.z = float(self.quaternion.Z)
        native.quaternion.w = float(self.quaternion.W)
        for row in range(1, 5):
            for column in range(1, 5):
                setattr(native.rotation_matrix, f"m{row}{column}",
                        float(getattr(self.rotation_matrix, f"M{row}{column}")))
        return native


@dataclass(frozen=True, slots=True)
class CompassReading:
    """One compass sample.

    Headings are degrees and are ``double`` in the ABI, which is why they are not
    narrowed to single precision anywhere on the way through.
    """

    timestamp: DateTimeOffset
    heading_accuracy: float
    magnetic_heading: float
    true_heading: float
    magnetometer_reading: Vector3

    @classmethod
    def _from_native(cls, value) -> "CompassReading":
        return cls(DateTimeOffset._from_native(value.timestamp),
                   float(value.heading_accuracy), float(value.magnetic_heading),
                   float(value.true_heading), _vector(value.magnetometer_reading))

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_CompassReading, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.heading_accuracy = real(self.heading_accuracy, "heading_accuracy")
        native.magnetic_heading = real(self.magnetic_heading, "magnetic_heading")
        native.true_heading = real(self.true_heading, "true_heading")
        native.magnetometer_reading = _to_vector(
            self.magnetometer_reading, "magnetometer_reading")
        return native


@dataclass(frozen=True, slots=True)
class MotionReading:
    """One fused motion sample: orientation, gravity, acceleration and rate."""

    timestamp: DateTimeOffset
    attitude: AttitudeReading
    device_acceleration: Vector3
    device_rotation_rate: Vector3
    gravity: Vector3

    @classmethod
    def _from_native(cls, value) -> "MotionReading":
        return cls(DateTimeOffset._from_native(value.timestamp),
                   AttitudeReading._from_native(value.attitude),
                   _vector(value.device_acceleration),
                   _vector(value.device_rotation_rate),
                   _vector(value.gravity))

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_MotionReading, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.attitude = self.attitude._to_native()
        native.device_acceleration = _to_vector(
            self.device_acceleration, "device_acceleration")
        native.device_rotation_rate = _to_vector(
            self.device_rotation_rate, "device_rotation_rate")
        native.gravity = _to_vector(self.gravity, "gravity")
        return native


@dataclass(frozen=True, slots=True)
class AccelerometerReadingEventInfo:
    """The payload of the accelerometer's second event.

    Distinct from :class:`AccelerometerReading` in CNA and therefore here: its
    axes are ``double`` rather than ``float``, so folding the two together would
    narrow a value the ABI carries at full width.
    """

    timestamp: DateTimeOffset
    x: float
    y: float
    z: float

    @classmethod
    def _from_native(cls, value) -> "AccelerometerReadingEventInfo":
        return cls(DateTimeOffset._from_native(value.timestamp),
                   float(value.x), float(value.y), float(value.z))

    def _to_native(self):
        native = _dev.in_struct(_devices.CNA_AccelerometerReadingEventInfo, _VERSION)
        native.timestamp = self.timestamp._to_native()
        native.x = real(self.x, "x")
        native.y = real(self.y, "y")
        native.z = real(self.z, "z")
        return native


#: Which CNA route family answers for each reading type, for the three canonical
#: value operations below.  Derived from the type rather than passed in, so a
#: caller cannot ask for one reading's text with another's route.
_READING_ROUTES = {
    AccelerometerReading: "cna_accelerometer_reading",
    GyroscopeReading: "cna_gyroscope_reading",
    AttitudeReading: "cna_attitude_reading",
    CompassReading: "cna_compass_reading",
    MotionReading: "cna_motion_reading",
    AccelerometerReadingEventInfo: "cna_accelerometer_reading_event_info",
}


def _routes(reading: object, what: str) -> str:
    prefix = _READING_ROUTES.get(type(reading))
    if prefix is None:
        raise TypeError(f"{what} must be a sensor reading, not {type(reading).__name__}")
    return prefix


def reading_text(reading: object) -> str:
    """CNA's own text for a reading.

    A reading's ``repr`` is Python's. This is the canonical rendering, asked of
    CNA rather than reproduced here, which is what makes it usable as evidence
    that the two agree.
    """
    prefix = _routes(reading, "reading")
    native = reading._to_native()
    return _support.copied_text(f"{prefix}_copy_string", (c.byref(native),),
                                "reading text")


def readings_equal(left: object, right: object) -> bool:
    """Whether CNA considers two readings of the same type equal.

    Python's ``==`` on these dataclasses compares fields, which is a second
    answer to the same question. Both are exact and they are expected to agree;
    the qualification asserts that they do rather than assuming it.
    """
    prefix = _routes(left, "left")
    if type(left) is not type(right):
        raise TypeError("readings_equal needs two readings of the same type")
    first, second = left._to_native(), right._to_native()
    return _support.out_bool(f"{prefix}_equals", c.byref(first), c.byref(second))


def reading_hash_code(reading: object) -> int:
    """CNA's hash code for a reading, as an unsigned 64-bit integer."""
    prefix = _routes(reading, "reading")
    native = reading._to_native()
    return _support.out_u64(f"{prefix}_get_hash_code", c.byref(native))


def last_sensor_error_id() -> int | None:
    """The identity of the last sensor failure CNA recorded, or ``None``.

    CNA reports availability separately from the value, so an absent error is
    ``None`` here rather than a sentinel a caller has to know about.
    """
    error_id = c.c_int32()
    has_error = c.c_uint8()
    _support.call("cna_sensors_get_last_error_id_ext",
                  c.byref(error_id), c.byref(has_error))
    return int(error_id.value) if has_error.value else None


# --- subscriptions ----------------------------------------------------------


class SensorSubscription:
    """One live sensor event registration.

    Closing it is what stops the callbacks; the sensor closes every subscription
    it still holds when it is closed, so a handler cannot run after the object it
    was registered on is gone. Closing twice is not an error.
    """

    __slots__ = ("_sensor", "_handle", "_key", "_closed")

    def __init__(self, sensor: "_Sensor", handle: int, key: object) -> None:
        self._sensor = sensor
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
        self._sensor._release(self)

    def __enter__(self) -> "SensorSubscription":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


# --- the sensors ------------------------------------------------------------


class _Sensor:
    """What all four sensors share, which in CNA is nearly everything."""

    #: Route prefix, e.g. ``cna_accelerometer``.
    _prefix: str = ""
    #: The structure ``get_current_value`` fills.
    _reading_struct: type = None  # type: ignore[assignment]
    #: The public reading type it becomes.
    _reading_type: type = None  # type: ignore[assignment]
    #: What this sensor is called in an error message.
    _what: str = "sensor"

    __slots__ = ("_handle", "_callbacks", "_subscriptions")

    def __init__(self, game: "Game") -> None:
        handle = _support.out_handle(
            f"{self._prefix}_create", _dev.game_handle(game, self._what))
        self._handle = _support.handle(handle, f"{self._prefix}_destroy", self._what)
        self._callbacks = CallbackRoot()
        self._subscriptions: list[SensorSubscription] = []

    # -- support and state --------------------------------------------------

    @classmethod
    def is_supported(cls, game: "Game") -> bool:
        """Whether this host has the sensor, asked of CNA rather than assumed."""
        return _support.out_bool(f"{cls._prefix}_get_is_supported",
                                 _dev.game_handle(game, cls._what))

    @property
    def state(self) -> SensorState:
        return SensorState(_support.out_u32(f"{self._prefix}_get_state",
                                            self._handle.argument))

    @property
    def is_data_valid(self) -> bool:
        return _support.out_bool(f"{self._prefix}_get_is_data_valid",
                                 self._handle.argument)

    @property
    def current_value(self):
        """The most recent reading.

        Reading a sensor that was never started is a state error from CNA, and
        it is passed through rather than answered with a zeroed reading.
        """
        native = _support.out_struct(
            self._reading_struct, _VERSION,
            f"{self._prefix}_get_current_value", self._handle.argument)
        return self._reading_type._from_native(native)

    # -- update interval ----------------------------------------------------

    @property
    def time_between_updates_ticks(self) -> int:
        """The requested interval in exact 100-nanosecond ticks."""
        return _support.out_i64(f"{self._prefix}_get_time_between_updates_ticks",
                                self._handle.argument)

    @time_between_updates_ticks.setter
    def time_between_updates_ticks(self, ticks: int) -> None:
        _support.call(f"{self._prefix}_set_time_between_updates_ticks",
                      self._handle.argument,
                      c.c_int64(checked(ticks, "int64", "ticks")))

    @property
    def time_between_updates(self) -> timedelta:
        """The requested interval as a :class:`datetime.timedelta`.

        Refuses rather than rounds when the interval is not a whole number of
        microseconds; ``time_between_updates_ticks`` always answers exactly.
        """
        return _interval(self.time_between_updates_ticks)

    @time_between_updates.setter
    def time_between_updates(self, value: timedelta) -> None:
        if not isinstance(value, timedelta):
            raise TypeError(
                f"time_between_updates must be a timedelta, not {type(value).__name__}")
        microseconds = (value.days * 86_400_000_000
                        + value.seconds * 1_000_000 + value.microseconds)
        self.time_between_updates_ticks = microseconds * TICKS_PER_MICROSECOND

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        _support.call(f"{self._prefix}_start", self._handle.argument)

    def stop(self) -> None:
        _support.call(f"{self._prefix}_stop", self._handle.argument)

    def dispose(self) -> None:
        """Disposes the sensor the way the canonical API's ``Dispose`` does.

        It stops, and it releases its hold on the sensor subsystem. It is *not*
        :meth:`close`: the C handle is still a live object and still has to be
        closed, and this package never leaves that to a finalizer. But the
        canonical object behind the handle is disposed, so every later operation
        on it -- reading its state included -- fails as a use after disposal.
        Measured, not assumed: the qualification asserts both halves.
        """
        _support.call(f"{self._prefix}_dispose", self._handle.argument)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases every subscription, then destroys the sensor."""
        if self._handle.closed:
            return
        for subscription in list(self._subscriptions):
            subscription.close()
        self._callbacks.clear()
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    # -- subscriptions ------------------------------------------------------

    def _subscribe(self, route: str, factory: type, adapt) -> SensorSubscription:
        key = object()
        trampoline = self._callbacks.root(key, factory, adapt)
        registration = _support.out_handle(
            route, self._handle.argument, trampoline, None)
        subscription = SensorSubscription(self, registration, key)
        self._subscriptions.append(subscription)
        return subscription

    def _release(self, subscription: SensorSubscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)
        self._callbacks.release(subscription._key)
        if not self._handle.closed:
            _support.call("cna_sensor_unsubscribe_ext",
                          c.c_uint64(subscription._handle))

    @property
    def callback_failures(self) -> list:
        """``(handler, exception)`` for every handler of this sensor that raised.

        A Python exception must never unwind through C, so one raised inside a
        handler is caught at the boundary and recorded here instead of being
        lost.
        """
        return list(self._callbacks.failures)

    def on_current_value_changed(
            self, handler: Callable[[object], None]) -> SensorSubscription:
        """Calls ``handler(reading)`` whenever the current value changes."""
        reading_type = self._reading_type
        struct = self._reading_struct

        def adapt(pointer, _context) -> None:
            handler(reading_type._from_native(pointer.contents))

        return self._subscribe(
            f"{self._prefix}_subscribe_current_value_changed",
            self._current_value_callback, adapt)


class Accelerometer(_Sensor):
    """Three-axis acceleration in g."""

    _prefix = "cna_accelerometer"
    _reading_struct = _devices.CNA_AccelerometerReading
    _reading_type = AccelerometerReading
    _what = "accelerometer"
    _current_value_callback = _devices.CNA_AccelerometerReadingCallback

    __slots__ = ()

    def on_reading_changed(
            self, handler: Callable[[AccelerometerReadingEventInfo], None]
    ) -> SensorSubscription:
        """CNA's second accelerometer event, whose payload is double precision."""

        def adapt(pointer, _context) -> None:
            handler(AccelerometerReadingEventInfo._from_native(pointer.contents))

        return self._subscribe(
            "cna_accelerometer_subscribe_reading_changed",
            _devices.CNA_AccelerometerReadingEventCallback, adapt)


class Gyroscope(_Sensor):
    """Angular velocity in radians per second, per axis."""

    _prefix = "cna_gyroscope"
    _reading_struct = _devices.CNA_GyroscopeReading
    _reading_type = GyroscopeReading
    _what = "gyroscope"
    _current_value_callback = _devices.CNA_GyroscopeReadingCallback

    __slots__ = ()


class _CalibratingSensor(_Sensor):
    """A sensor that can ask to be calibrated."""

    __slots__ = ()

    def on_calibrate(self, handler: Callable[[], None]) -> SensorSubscription:
        """Calls ``handler()`` when the sensor asks the user to calibrate it."""

        def adapt(_context) -> None:
            handler()

        return self._subscribe(f"{self._prefix}_subscribe_calibrate",
                               _devices.CNA_SensorEventCallback, adapt)


class Compass(_CalibratingSensor):
    """Magnetic and true heading in degrees, plus the raw magnetometer vector."""

    _prefix = "cna_compass"
    _reading_struct = _devices.CNA_CompassReading
    _reading_type = CompassReading
    _what = "compass"
    _current_value_callback = _devices.CNA_CompassReadingCallback

    __slots__ = ()


class Motion(_CalibratingSensor):
    """The fused sensor: orientation, gravity, device acceleration and rate."""

    _prefix = "cna_motion"
    _reading_struct = _devices.CNA_MotionReading
    _reading_type = MotionReading
    _what = "motion sensor"
    _current_value_callback = _devices.CNA_MotionReadingCallback

    __slots__ = ()

    @property
    def is_attitude_north_referenced(self) -> bool:
        """Whether the fused attitude is referenced to true north."""
        return _support.out_bool("cna_motion_get_is_attitude_north_referenced_ext",
                                 self._handle.argument)
