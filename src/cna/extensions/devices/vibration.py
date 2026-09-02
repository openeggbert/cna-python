"""Controller vibration.

Whether anything physically vibrates is not something this package can observe,
and it never claims to. What it can qualify -- and what the tests do qualify --
is the request: support, argument validation, duration in exact ticks, intensity
and the two-motor split, stop semantics, and the device name.

CNA supplies a test backend that records every request instead of performing it,
and :func:`~cna.extensions.devices.testing.install_vibration_test_backend`
installs it. A result measured against that backend is
``SYNTHETIC_BACKEND_VERIFIED``, never physical evidence.

Durations are 100-nanosecond ticks, as everywhere in this ABI, and are passed as
Python integers. Nothing converts one to a float on the way through.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from _cna_native import devices_abi as _devices
from _cna_native import devices_support as _dev
from _cna_native.family_support import checked, real

from .values import TICKS_PER_MICROSECOND

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from Microsoft.Xna.Framework import Game

__all__ = [
    "VibrationTestLog",
    "is_vibration_supported",
    "vibration_device_name",
    "start_vibration",
    "start_vibration_with_intensity",
    "start_vibration_left_right",
    "stop_vibration",
    "ticks_for",
]

_support = _dev.support
_VERSION = 1


def ticks_for(duration: timedelta) -> int:
    """A :class:`datetime.timedelta` as exact 100-nanosecond ticks.

    ``timedelta`` resolves microseconds and ticks resolve hundreds of
    nanoseconds, so this direction is always exact; the reverse is not, which is
    why every duration in this module is an integer tick count.
    """
    if not isinstance(duration, timedelta):
        raise TypeError(f"duration must be a timedelta, not {type(duration).__name__}")
    microseconds = (duration.days * 86_400_000_000
                    + duration.seconds * 1_000_000 + duration.microseconds)
    return microseconds * TICKS_PER_MICROSECOND


@dataclass(frozen=True, slots=True)
class VibrationTestLog:
    """What the installed vibration test backend has been asked to do.

    ``last_duration_ticks`` is an exact integer. The three float fields are the
    strengths of the most recent requests, at the single precision the ABI
    carries them in.
    """

    start_calls: int
    stop_calls: int
    left_right_calls: int
    last_duration_ticks: int
    last_intensity: float
    last_large_motor: float
    last_small_motor: float


def is_vibration_supported(game: "Game") -> bool:
    """Whether a vibration device is present, asked of CNA rather than assumed."""
    return _support.out_bool("cna_vibrate_controller_get_is_supported_ext",
                             _dev.game_handle(game, "vibration"))


def vibration_device_name(game: "Game") -> str:
    """The vibration device's name; empty when there is none."""
    return _support.sized_text("cna_vibrate_controller_get_device_name_size_ext",
                               "cna_vibrate_controller_copy_device_name_ext",
                               (_dev.game_handle(game, "vibration"),),
                               "vibration device name")


def start_vibration(game: "Game", duration_ticks: int) -> None:
    """Starts vibration for ``duration_ticks`` 100-nanosecond ticks."""
    _support.call("cna_vibrate_controller_start",
                  _dev.game_handle(game, "vibration"),
                  c.c_int64(checked(duration_ticks, "int64", "duration_ticks")))


def start_vibration_with_intensity(game: "Game", duration_ticks: int,
                                   intensity: float) -> None:
    """Starts vibration at ``intensity``, which CNA clamps to zero..one."""
    _support.call("cna_vibrate_controller_start_with_intensity_ext",
                  _dev.game_handle(game, "vibration"),
                  c.c_int64(checked(duration_ticks, "int64", "duration_ticks")),
                  c.c_float(real(intensity, "intensity")))


def start_vibration_left_right(game: "Game", large_motor: float, small_motor: float,
                               duration_ticks: int) -> None:
    """Starts a two-motor vibration.

    The argument order is CNA's -- motors first, duration last -- rather than
    rearranged to match the single-motor route, because a caller reading the
    canonical header must find the same order here.
    """
    _support.call("cna_vibrate_controller_start_left_right_ext",
                  _dev.game_handle(game, "vibration"),
                  c.c_float(real(large_motor, "large_motor")),
                  c.c_float(real(small_motor, "small_motor")),
                  c.c_int64(checked(duration_ticks, "int64", "duration_ticks")))


def stop_vibration(game: "Game") -> None:
    """Stops any vibration in progress."""
    _support.call("cna_vibrate_controller_stop",
                  _dev.game_handle(game, "vibration"))
