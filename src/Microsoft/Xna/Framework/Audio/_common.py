"""Private Audio validation, ABI value, and callback helpers."""

from __future__ import annotations

import ctypes as c
from datetime import timedelta
import math
import threading
from typing import Callable

from _cna_native import abi
from _cna_native.loader import get_library
from _cna_native.runtime_context import current_game

from .. import Vector3
from .._numeric import div32, f32, mul32


def _active_native() -> tuple[object, object, object, int]:
    game = current_game()
    host = getattr(game, "_host", None)
    if host is None or not host.handle:
        raise RuntimeError("audio requires an active CNA Game.Run owner thread")
    return game, host, host.library, int(host.handle)


def _string_view(value: object, name: str) -> tuple[bytes, abi.CNA_StringView]:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if "\0" in value:
        raise ValueError(f"{name} cannot contain NUL")
    encoded = value.encode("utf-8", errors="strict")
    return encoded, abi.CNA_StringView(encoded, len(encoded))


def _copy_string(library: object, handle: int, size_name: str, copy_name: str,
                 *prefix: object) -> str:
    size = c.c_uint64()
    library.check(getattr(library, size_name)(handle, *prefix, c.byref(size)), size_name)
    if size.value == 0:
        return ""
    output = c.create_string_buffer(size.value)
    written = c.c_uint64()
    library.check(
        getattr(library, copy_name)(handle, *prefix, output, size.value, c.byref(written)),
        copy_name,
    )
    return bytes(output.raw[:written.value]).decode("utf-8", errors="strict")


def _timedelta_ticks(value: object, name: str = "duration") -> int:
    if not isinstance(value, timedelta):
        raise TypeError(f"{name} must be datetime.timedelta")
    ticks = ((value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds) * 10
    if ticks < -9_223_372_036_854_775_808 or ticks > 9_223_372_036_854_775_807:
        raise OverflowError(f"{name} is outside the mapped TimeSpan range")
    return ticks


def _ticks_timedelta(ticks: int) -> timedelta:
    # Python cannot represent the last decimal tick; timedelta applies its
    # documented nearest-microsecond conversion here.
    return timedelta(microseconds=ticks / 10)


def _validate_sample_rate(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("sampleRate must be an Int32")
    if value < 8_000 or value > 48_000:
        raise ValueError("sampleRate must be between 8000 and 48000")
    return value


def _validate_channels(value: object):
    from ._sound import AudioChannels
    if not isinstance(value, AudioChannels):
        raise TypeError("channels must be AudioChannels")
    return value


def _sample_duration(size: object, sample_rate: object, channels: object) -> timedelta:
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("sizeInBytes must be an Int32")
    if size < 0:
        raise ValueError("sizeInBytes cannot be negative")
    if size > 2_147_483_647:
        raise OverflowError("sizeInBytes is outside the Int32 range")
    rate = _validate_sample_rate(sample_rate)
    channel_value = _validate_channels(channels)
    if size == 0:
        return timedelta(0)
    sample_count = size // (2 * int(channel_value))
    milliseconds = div32(mul32(f32(sample_count), f32(1000)), f32(rate))
    # .NET Framework TimeSpan.FromMilliseconds rounds to the nearest whole
    # millisecond, away from zero at the midpoint.
    rounded = math.floor(milliseconds + 0.5)
    return timedelta(milliseconds=rounded)


def _sample_size(duration: object, sample_rate: object, channels: object) -> int:
    ticks = _timedelta_ticks(duration)
    total_milliseconds = ticks / 10_000.0
    if total_milliseconds < 0 or total_milliseconds > 2_147_483_647:
        raise ValueError("duration is outside XNA's supported range")
    rate = _validate_sample_rate(sample_rate)
    channel_value = _validate_channels(channels)
    if ticks == 0:
        return 0
    # Preserve XNA's surprising evaluation order: only rate/1000 is Single;
    # multiplication by TimeSpan.TotalMilliseconds is then binary64.
    sample_count = int(total_milliseconds * div32(f32(rate), f32(1000)))
    if sample_count > 2_147_483_647:
        raise OverflowError("sample count overflows Int32")
    adjusted = sample_count + sample_count % int(channel_value)
    result = adjusted * (2 * int(channel_value))
    if adjusted > 2_147_483_647 or result > 2_147_483_647:
        raise OverflowError("sample size overflows Int32")
    return result


def _copy_vector(value: object, name: str) -> Vector3:
    if not isinstance(value, Vector3):
        raise TypeError(f"{name} must be Vector3")
    return value.__copy__()


def _native_vector(value: Vector3) -> abi.CNA_Vector3:
    return abi.CNA_Vector3(value.X, value.Y, value.Z)


def _native_listener(value: object) -> abi.CNA_AudioListener:
    from ._sound import AudioListener
    if not isinstance(value, AudioListener):
        raise TypeError("listener must be AudioListener")
    result = abi.CNA_AudioListener()
    result.struct_size, result.struct_version = c.sizeof(result), 1
    result.forward = _native_vector(value.Forward)
    result.position = _native_vector(value.Position)
    result.up = _native_vector(value.Up)
    result.velocity = _native_vector(value.Velocity)
    return result


def _native_emitter(value: object) -> abi.CNA_AudioEmitter:
    from ._sound import AudioEmitter
    if not isinstance(value, AudioEmitter):
        raise TypeError("emitter must be AudioEmitter")
    result = abi.CNA_AudioEmitter()
    result.struct_size, result.struct_version = c.sizeof(result), 1
    result.doppler_scale = value.DopplerScale
    result.forward = _native_vector(value.Forward)
    result.position = _native_vector(value.Position)
    result.up = _native_vector(value.Up)
    result.velocity = _native_vector(value.Velocity)
    return result


class _NativeAudioEventOwner:
    """Lazy, strongly rooted, exception-total native audio registration."""

    def _init_audio_events(self) -> None:
        self._audio_registrations: dict[str, tuple[int, object]] = {}

    def _event_registration_call(self, name: str) -> tuple[Callable[..., int], tuple[object, ...]]:
        raise NotImplementedError

    def _record_callback_error(self, error: BaseException) -> None:
        host = getattr(getattr(self, "_game", None), "_host", None)
        if host is not None and host.pending_exception is None:
            host.pending_exception = error

    def _event_subscribe(self, name: str) -> None:
        if name in self._audio_registrations:
            return
        function, prefix = self._event_registration_call(name)

        @abi.CNA_AudioEventCallback
        def callback(context: object) -> None:
            try:
                host = getattr(self._game, "_host", None)
                if host is not None and host.pending_exception is not None:
                    return
                if host is None or threading.get_ident() != host.owner_thread:
                    raise RuntimeError(f"CNA invoked {name} on a non-owner audio thread")
                getattr(self, name)(self, None)
            except BaseException as error:
                self._record_callback_error(error)

        output = c.c_uint64()
        library = get_library()
        library.check(function(*prefix, callback, None, c.byref(output)), function.__name__)
        self._audio_registrations[name] = (int(output.value), callback)

    def _event_unsubscribe(self, name: str) -> None:
        registration = self._audio_registrations.get(name)
        if registration is None:
            return
        library = get_library()
        library.check(library.cna_audio_unsubscribe_ext(registration[0]),
                      "cna_audio_unsubscribe_ext")
        del self._audio_registrations[name]

    def _unsubscribe_audio_events(self) -> None:
        for name in tuple(self._audio_registrations):
            self._event_unsubscribe(name)
