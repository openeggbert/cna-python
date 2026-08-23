"""Index-backed, identity-stable XNA microphone facades."""

from __future__ import annotations

from collections.abc import MutableSequence
import ctypes as c
from datetime import timedelta
from weakref import WeakKeyDictionary

from _cna_native.errors import NativeError
from _cna_native.loader import get_library

from .._language import Event, classproperty
from ._common import (
    _NativeAudioEventOwner, _active_native, _copy_string, _ticks_timedelta,
    _timedelta_ticks,
)
from ._sound import MicrophoneState, NoMicrophoneConnectedException


_cache: WeakKeyDictionary[object, tuple["Microphone", ...]] = WeakKeyDictionary()


def _mutable_buffer(value: object) -> int:
    if isinstance(value, memoryview):
        if value.readonly or value.format not in ("B", "b", "c") or value.ndim != 1:
            raise TypeError("buffer must be a writable one-dimensional byte buffer")
        return len(value)
    if not isinstance(value, MutableSequence) or isinstance(value, str):
        raise TypeError("buffer must be a mutable byte sequence")
    return len(value)


class Microphone(_NativeAudioEventOwner):
    BufferReady = Event()
    Name: str = ""

    def __init__(self, *args: object) -> None:
        raise TypeError("Microphone instances are provided by Microphone.All")

    @classmethod
    def _from_index(cls, game: object, index: int, name: str) -> "Microphone":
        self = cls.__new__(cls)
        self._game, self._index, self.Name = game, index, name
        self._invalidated = False
        self._init_audio_events()
        return self

    def _native(self) -> tuple[object, int]:
        if self._invalidated:
            raise RuntimeError("Microphone is invalid because its Game is disposed")
        game, _, library, handle = _active_native()
        if game is not self._game:
            raise RuntimeError("Microphone belongs to a different active Game")
        return library, handle

    @classmethod
    def _all(cls) -> tuple["Microphone", ...]:
        game, _, library, handle = _active_native()
        cached = _cache.get(game)
        if cached is not None:
            return cached
        count = c.c_uint64()
        library.check(library.cna_microphone_get_count(handle, c.byref(count)),
                      "cna_microphone_get_count")
        values: list[Microphone] = []
        for index in range(count.value):
            name = _copy_string(library, handle, "cna_microphone_get_name_size_at",
                                "cna_microphone_copy_name_at", index)
            values.append(cls._from_index(game, index, name))
        result = tuple(values)
        _cache[game] = result
        return result

    @classproperty
    def All(cls) -> tuple["Microphone", ...]: return cls._all()

    @classproperty
    def Default(cls) -> "Microphone | None":
        game, _, library, handle = _active_native()
        values = cls._all()
        index = c.c_uint64(); available = c.c_uint8()
        library.check(library.cna_microphone_get_default_index_ext(
            handle, c.byref(index), c.byref(available)),
            "cna_microphone_get_default_index_ext")
        if not available.value:
            return None
        if index.value >= len(values):
            raise RuntimeError("CNA returned a default microphone outside Microphone.All")
        return values[index.value]

    def _event_registration_call(self, name: str):
        if name != "BufferReady": raise ValueError("unknown microphone event")
        library, handle = self._native()
        return library.cna_microphone_subscribe_buffer_ready_at, (handle, self._index)

    @property
    def State(self) -> MicrophoneState:
        library, handle = self._native(); output = c.c_uint32()
        library.check(library.cna_microphone_get_state_at(
            handle, self._index, c.byref(output)), "cna_microphone_get_state_at")
        return MicrophoneState(output.value)

    @property
    def BufferDuration(self) -> timedelta:
        library, handle = self._native(); output = c.c_int64()
        library.check(library.cna_microphone_get_buffer_duration_ticks_at(
            handle, self._index, c.byref(output)),
            "cna_microphone_get_buffer_duration_ticks_at")
        return _ticks_timedelta(int(output.value))
    @BufferDuration.setter
    def BufferDuration(self, value: timedelta) -> None:
        ticks = _timedelta_ticks(value); library, handle = self._native()
        library.check(library.cna_microphone_set_buffer_duration_ticks_at(
            handle, self._index, ticks), "cna_microphone_set_buffer_duration_ticks_at")

    @property
    def SampleRate(self) -> int:
        library, handle = self._native(); output = c.c_int32()
        library.check(library.cna_microphone_get_sample_rate_at(
            handle, self._index, c.byref(output)), "cna_microphone_get_sample_rate_at")
        return int(output.value)

    @property
    def IsHeadset(self) -> bool:
        library, handle = self._native(); output = c.c_uint8()
        library.check(library.cna_microphone_get_is_headset_at(
            handle, self._index, c.byref(output)), "cna_microphone_get_is_headset_at")
        return bool(output.value)

    def Start(self) -> None:
        library, handle = self._native()
        try:
            library.check(library.cna_microphone_start_at(handle, self._index),
                          "cna_microphone_start_at")
        except NativeError as error:
            # CNA's exception barrier maps NoMicrophoneConnectedException to
            # NOT_SUPPORTED. State/platform failures retain their native type.
            if error.result == 6:
                raise NoMicrophoneConnectedException("no microphone is connected", error) from error
            raise

    def Stop(self) -> None:
        library, handle = self._native()
        library.check(library.cna_microphone_stop_at(handle, self._index),
                      "cna_microphone_stop_at")

    def GetData(self, *args: object) -> int:
        if len(args) not in (1, 3):
            raise TypeError("GetData expects buffer or buffer, offset, count")
        buffer = args[0]; length = _mutable_buffer(buffer)
        if len(args) == 1:
            offset, count = 0, length
        else:
            offset, count = args[1], args[2]
            for value, name in ((offset, "offset"), (count, "count")):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"{name} must be an Int32")
        if offset < 0 or count < 0 or offset + count > length:
            raise ValueError("GetData range is outside buffer")
        native = (c.c_uint8 * count)(); written = c.c_uint64()
        library, handle = self._native()
        library.check(library.cna_microphone_get_data_at(
            handle, self._index, native, count, c.byref(written)),
            "cna_microphone_get_data_at")
        data = bytes(native[:written.value])
        if isinstance(buffer, memoryview):
            buffer[offset:offset + written.value] = data
        else:
            for index, value in enumerate(data, offset):
                buffer[index] = value
        return int(written.value)

    def GetSampleDuration(self, sizeInBytes: int) -> timedelta:
        if isinstance(sizeInBytes, bool) or not isinstance(sizeInBytes, int):
            raise TypeError("sizeInBytes must be an Int32")
        library, handle = self._native(); output = c.c_int64()
        library.check(library.cna_microphone_get_sample_duration_ticks_at(
            handle, self._index, sizeInBytes, c.byref(output)),
            "cna_microphone_get_sample_duration_ticks_at")
        return _ticks_timedelta(int(output.value))

    def GetSampleSizeInBytes(self, duration: timedelta) -> int:
        ticks = _timedelta_ticks(duration); library, handle = self._native(); output = c.c_int32()
        library.check(library.cna_microphone_get_sample_size_in_bytes_at(
            handle, self._index, ticks, c.byref(output)),
            "cna_microphone_get_sample_size_in_bytes_at")
        return int(output.value)

    def _invalidate(self) -> None:
        if self._invalidated: return
        self._unsubscribe_audio_events()
        self._invalidated = True


def _dispose_microphones_for_game(game: object) -> None:
    values = _cache.pop(game, ())
    first_error: BaseException | None = None
    for value in values:
        try: value._invalidate()
        except BaseException as error: first_error = first_error or error
    if first_error is not None: raise first_error


Microphone.__xna_arities__ = {
    "GetSampleSizeInBytes": {1}, "GetSampleDuration": {1}, "Start": {0},
    "Stop": {0}, "GetData": {1, 3},
}
