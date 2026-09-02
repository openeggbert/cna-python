"""Value types the device-services family reads and writes.

The one that matters most is :class:`DateTimeOffset`, because every sensor
reading carries one and getting it wrong is silent.

CNA reports a timestamp as **two 64-bit tick counts**: local time in
100-nanosecond ticks since 0001-01-01, and the offset from UTC in the same unit.
A current timestamp is around 6.4e17 ticks, which is far past 2**53, so a tick
count that goes through a Python ``float`` -- or through anything that converts
to ``datetime`` and back -- loses its low digits. This type therefore holds
integers and does every calculation on integers. Conversion to
:class:`datetime.datetime` is offered, and it is *lossy by construction*
(``datetime`` resolves microseconds, these ticks resolve hundreds of
nanoseconds), so the remainder is exposed rather than dropped: see
:attr:`sub_microsecond_ticks`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from _cna_native import devices_abi as _devices

__all__ = [
    "DateTimeOffset",
    "SensorState",
    "DeviceType",
    "CameraState",
    "CameraPosition",
    "MessageBoxType",
    "PowerState",
    "TICKS_PER_SECOND",
    "TICKS_PER_MICROSECOND",
]

#: 100-nanosecond ticks in one second, which is the unit of every duration and
#: every timestamp in this ABI.
TICKS_PER_SECOND = 10_000_000
#: 100-nanosecond ticks in one microsecond -- the resolution ``datetime`` stops
#: at, and therefore the size of what a conversion to it cannot carry.
TICKS_PER_MICROSECOND = 10

#: Ticks from 0001-01-01, the runtime's epoch, to 1970-01-01, the Unix one.
_UNIX_EPOCH_TICKS = 621_355_968_000_000_000


class SensorState(IntEnum):
    """What a sensor can currently do, exactly as CNA reports it."""

    NotSupported = _devices.CNA_SENSOR_STATE_NOT_SUPPORTED
    Ready = _devices.CNA_SENSOR_STATE_READY
    Initializing = _devices.CNA_SENSOR_STATE_INITIALIZING
    NoData = _devices.CNA_SENSOR_STATE_NO_DATA
    NoPermissions = _devices.CNA_SENSOR_STATE_NO_PERMISSIONS
    Disabled = _devices.CNA_SENSOR_STATE_DISABLED


class DeviceType(IntEnum):
    """Whether the process is on real hardware or an emulator."""

    Device = _devices.CNA_DEVICE_TYPE_DEVICE
    Emulator = _devices.CNA_DEVICE_TYPE_EMULATOR


class CameraState(IntEnum):
    """A camera's lifecycle state."""

    NotSupported = _devices.CNA_CAMERA_STATE_NOT_SUPPORTED
    Closed = _devices.CNA_CAMERA_STATE_CLOSED
    Opening = _devices.CNA_CAMERA_STATE_OPENING
    Denied = _devices.CNA_CAMERA_STATE_DENIED
    Ready = _devices.CNA_CAMERA_STATE_READY
    Lost = _devices.CNA_CAMERA_STATE_LOST


class CameraPosition(IntEnum):
    """Where on the device a camera faces."""

    Unknown = _devices.CNA_CAMERA_POSITION_UNKNOWN
    FrontFacing = _devices.CNA_CAMERA_POSITION_FRONT_FACING
    BackFacing = _devices.CNA_CAMERA_POSITION_BACK_FACING


class MessageBoxType(IntEnum):
    """The severity a host message box is shown with."""

    Error = _devices.CNA_MESSAGE_BOX_TYPE_ERROR
    Warning = _devices.CNA_MESSAGE_BOX_TYPE_WARNING
    Information = _devices.CNA_MESSAGE_BOX_TYPE_INFORMATION


class PowerState(IntEnum):
    """The host's power state.

    The same six values answer for a controller, because CNA declares one
    identity for both and this package does not invent a second.
    ``Error`` is a real answer the query produces, not a failure.
    """

    Error = 0
    Unknown = 1
    OnBattery = 2
    NoBattery = 3
    Charging = 4
    Charged = 5


@dataclass(frozen=True, slots=True)
class DateTimeOffset:
    """A point in time with a UTC offset, in exact 100-nanosecond ticks.

    :param ticks: local time in ticks since 0001-01-01.
    :param offset_ticks: the offset from UTC, in the same unit.

    Both are Python integers and stay integers. ``utc_ticks`` is
    ``ticks - offset_ticks``, which is what CNA's own equality and hashing
    compare.
    """

    ticks: int
    offset_ticks: int

    def __post_init__(self) -> None:
        for name in ("ticks", "offset_ticks"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, not {type(value).__name__}")
            if not -0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF:
                raise ValueError(f"{name} does not fit a signed 64-bit tick count")

    @property
    def utc_ticks(self) -> int:
        """Local ticks less the offset, computed with integers."""
        return self.ticks - self.offset_ticks

    @property
    def offset(self) -> timedelta:
        """The UTC offset.

        Exact whenever the offset is a whole number of microseconds, which every
        real time-zone offset is; a sub-microsecond offset would be a defect in
        the host and raises rather than rounding.
        """
        if self.offset_ticks % TICKS_PER_MICROSECOND:
            raise ValueError(
                "the UTC offset is not a whole number of microseconds and cannot "
                f"be a timedelta: {self.offset_ticks} ticks")
        return timedelta(microseconds=self.offset_ticks // TICKS_PER_MICROSECOND)

    @property
    def sub_microsecond_ticks(self) -> int:
        """The 0..9 ticks a conversion to :class:`datetime.datetime` cannot carry."""
        return self.ticks % TICKS_PER_MICROSECOND

    def to_datetime(self) -> datetime:
        """This instant as an aware :class:`datetime.datetime`.

        **Lossy by construction.** ``datetime`` stops at microseconds and these
        ticks do not, so anything in :attr:`sub_microsecond_ticks` is not in the
        result. Compare tick counts, not datetimes, when exactness matters.
        """
        unix_ticks = self.utc_ticks - _UNIX_EPOCH_TICKS
        microseconds, _remainder = divmod(unix_ticks, TICKS_PER_MICROSECOND)
        moment = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            microseconds=microseconds)
        return moment.astimezone(timezone(self.offset))

    @classmethod
    def _from_native(cls, value: "_devices.CNA_DateTimeOffset") -> "DateTimeOffset":
        return cls(int(value.ticks), int(value.offset_ticks))

    def _to_native(self) -> "_devices.CNA_DateTimeOffset":
        value = _devices.CNA_DateTimeOffset()
        value.ticks = self.ticks
        value.offset_ticks = self.offset_ticks
        return value
