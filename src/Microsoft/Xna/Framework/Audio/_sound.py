"""XNA SoundEffect, controllable instances, and dynamic streaming audio."""

from __future__ import annotations

from collections.abc import Sequence
import ctypes as c
from datetime import timedelta
from enum import IntEnum
import math
import struct
import weakref

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError, NativeError
from _cna_native.loader import get_library
from _cna_native.ownership import NativeResource, Ownership

from .. import Vector3
from .._language import Event, staticproperty, staticpropertymeta
from .._numeric import f32
from ._common import (
    _NativeAudioEventOwner, _active_native, _copy_string, _copy_vector,
    _native_emitter, _native_listener, _sample_duration, _sample_size,
    _string_view, _ticks_timedelta, _timedelta_ticks, _validate_channels,
    _validate_sample_rate,
)


class AudioChannels(IntEnum):
    Mono = 1
    Stereo = 2


class AudioStopOptions(IntEnum):
    AsAuthored = 0
    Immediate = 1


class SoundState(IntEnum):
    Playing = 0
    Paused = 1
    Stopped = 2


class MicrophoneState(IntEnum):
    Started = 0
    Stopped = 1


class _AudioException(Exception):
    def __init__(self, *args: object) -> None:
        if len(args) > 2:
            raise TypeError(f"{type(self).__name__} expects zero, one, or two arguments")
        message = "" if not args else args[0]
        if not isinstance(message, str):
            raise TypeError("message must be str")
        if len(args) == 2 and not isinstance(args[1], Exception):
            raise TypeError("inner must be Exception")
        super().__init__(message)
        self.__cause__ = args[1] if len(args) == 2 else None


class InstancePlayLimitException(_AudioException):
    pass


class NoAudioHardwareException(_AudioException):
    pass


class NoMicrophoneConnectedException(_AudioException):
    pass


class AudioListener:
    def __init__(self) -> None:
        self._position = Vector3.Zero
        self._velocity = Vector3.Zero
        self._forward = Vector3.Forward
        self._up = Vector3.Up

    @property
    def Position(self) -> Vector3: return self._position.__copy__()
    @Position.setter
    def Position(self, value: Vector3) -> None: self._position = _copy_vector(value, "Position")
    @property
    def Velocity(self) -> Vector3: return self._velocity.__copy__()
    @Velocity.setter
    def Velocity(self, value: Vector3) -> None: self._velocity = _copy_vector(value, "Velocity")
    @property
    def Forward(self) -> Vector3: return self._forward.__copy__()
    @Forward.setter
    def Forward(self, value: Vector3) -> None: self._forward = _copy_vector(value, "Forward")
    @property
    def Up(self) -> Vector3: return self._up.__copy__()
    @Up.setter
    def Up(self, value: Vector3) -> None: self._up = _copy_vector(value, "Up")


class AudioEmitter(AudioListener):
    def __init__(self) -> None:
        super().__init__()
        self._doppler_scale = 1.0

    @property
    def DopplerScale(self) -> float: return self._doppler_scale
    @DopplerScale.setter
    def DopplerScale(self, value: float) -> None:
        narrowed = f32(value)
        # XNA checks only < 0 here, so NaN is intentionally accepted.
        if narrowed < 0.0:
            raise ValueError("DopplerScale cannot be negative")
        self._doppler_scale = narrowed


def _release(operation: str):
    def release(handle: int) -> None:
        library = get_library()
        library.check(getattr(library, operation)(handle), operation)
    return release


def _bytes(value: object, name: str = "buffer") -> bytes:
    if value is None:
        raise TypeError(f"{name} cannot be None")
    if isinstance(value, str):
        raise TypeError(f"{name} must be a byte sequence")
    try:
        return bytes(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise TypeError(f"{name} must be a byte sequence") from error


def _validate_pcm_range(payload: bytes, offset: object, count: object,
                        channels: AudioChannels) -> tuple[int, int]:
    for value, name in ((offset, "offset"), (count, "count")):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an Int32")
        if value < -2_147_483_648 or value > 2_147_483_647:
            raise OverflowError(f"{name} is outside the Int32 range")
    block = 2 * int(channels)
    if not payload:
        raise ValueError("buffer cannot be empty")
    if len(payload) % block:
        raise ValueError("buffer must contain complete channel frames")
    if offset < 0 or offset >= len(payload):
        raise ValueError("offset is outside buffer")
    if count <= 0 or offset + count > len(payload):
        raise ValueError("count is outside buffer")
    if offset % block or count % block:
        raise ValueError("PCM range must contain complete channel frames")
    return offset, count


def _validate_wav(payload: bytes) -> None:
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("stream is not a RIFF/WAVE file")
    declared_end = struct.unpack_from("<I", payload, 4)[0] + 8
    if declared_end > len(payload) or declared_end < 12:
        raise ValueError("RIFF stream is truncated")
    position = 12
    fmt: tuple[int, int, int, int, int, int] | None = None
    data_size: int | None = None
    while position < declared_end:
        if position + 8 > declared_end:
            raise ValueError("RIFF chunk header is truncated")
        identity = payload[position:position + 4]
        size = struct.unpack_from("<I", payload, position + 4)[0]
        start, end = position + 8, position + 8 + size
        if end > declared_end:
            raise ValueError("RIFF chunk payload is truncated")
        if identity == b"fmt " and fmt is None:
            if size < 16:
                raise ValueError("WAVE fmt chunk is malformed")
            fmt = struct.unpack_from("<HHIIHH", payload, start)
        elif identity == b"data" and data_size is None:
            data_size = size
        position = end + (size & 1)
    if position > declared_end + 1 or fmt is None or data_size is None:
        raise ValueError("WAVE stream lacks a complete fmt/data pair")
    encoding, channels, rate, byte_rate, block_align, bits = fmt
    if encoding != 1 or channels not in (1, 2) or bits != 16:
        raise ValueError("only mono/stereo PCM16 WAVE streams are supported")
    if rate < 8_000 or rate > 48_000 or block_align != channels * 2 or byte_rate != rate * block_align:
        raise ValueError("WAVE fmt values are invalid")
    if data_size == 0 or data_size % block_align:
        raise ValueError("WAVE data must contain complete non-empty frames")


def _audio_create_error(error: NativeError) -> BaseException:
    if error.result == 6:
        return NoAudioHardwareException("no audio playback hardware is available", error)
    return error


class SoundEffect(metaclass=staticpropertymeta):
    def __init__(self, *args: object) -> None:
        if len(args) not in (3, 7):
            raise TypeError("SoundEffect expects buffer, sampleRate, channels or the seven-argument range")
        if len(args) == 3:
            rate = _validate_sample_rate(args[1])
            channels = _validate_channels(args[2])
            payload = _bytes(args[0])
            offset, count, loop_start, loop_length = 0, len(payload), 0, 0
        else:
            rate = _validate_sample_rate(args[3])
            channels = _validate_channels(args[4])
            # XNA validates the format before touching the buffer in this
            # overload; preserve that observable exception ordering.
            payload = _bytes(args[0])
            offset, count = _validate_pcm_range(payload, args[1], args[2], channels)
            loop_start, loop_length = args[5], args[6]
            for value, name in ((loop_start, "loopStart"), (loop_length, "loopLength")):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"{name} must be an Int32")
                if value < 0 or value > 2_147_483_647:
                    raise ValueError(f"{name} must be a nonnegative Int32")
            sample_count = count // (2 * int(channels))
            if loop_start + loop_length > sample_count:
                raise ValueError("loop region is outside the PCM range")
        if len(args) == 3:
            offset, count = _validate_pcm_range(payload, offset, count, channels)
        game, _, library, game_handle = _active_native()
        info = abi.CNA_SoundEffectCreateInfo()
        info.struct_size, info.struct_version = c.sizeof(info), 1
        info.sample_rate, info.channels = rate, int(channels)
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload)
        output = c.c_uint64()
        try:
            library.check(library.cna_sound_effect_create_pcm16_range_ext(
                game_handle, c.byref(info), native, len(payload), offset, count,
                loop_start, loop_length, c.byref(output)),
                "cna_sound_effect_create_pcm16_range_ext")
        except NativeError as error:
            raise _audio_create_error(error) from error
        self._init_native(game, int(output.value))

    def _init_native(self, game: object, handle: int) -> None:
        self._game = game
        self._native = NativeResource(handle, Ownership.OWNED,
                                      _release("cna_sound_effect_destroy"))
        self._children: list[weakref.ReferenceType[SoundEffectInstance]] = []
        game._register_native_child(self)

    @classmethod
    def _from_handle(cls, game: object, handle: int) -> "SoundEffect":
        self = cls.__new__(cls)
        self._init_native(game, handle)
        return self

    @staticmethod
    def FromStream(stream: object) -> "SoundEffect":
        if stream is None or not hasattr(stream, "read"):
            raise TypeError("stream must provide read()")
        payload = stream.read()
        if not isinstance(payload, bytes):
            raise TypeError("stream.read() must return bytes")
        _validate_wav(payload)
        game, _, library, game_handle = _active_native()
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload)
        output = c.c_uint64()
        try:
            library.check(library.cna_sound_effect_create_from_encoded_ext(
                game_handle, native, len(payload), c.byref(output)),
                "cna_sound_effect_create_from_encoded_ext")
        except NativeError as error:
            raise _audio_create_error(error) from error
        return SoundEffect._from_handle(game, int(output.value))

    @property
    def IsDisposed(self) -> bool: return self._native.IsDisposed
    def _require_handle(self) -> int: return self._native._require_handle()

    @property
    def Name(self) -> str:
        library = get_library()
        return _copy_string(library, self._require_handle(),
                            "cna_sound_effect_get_name_size", "cna_sound_effect_copy_name")
    @Name.setter
    def Name(self, value: str) -> None:
        encoded, view = _string_view(value, "Name")
        library = get_library()
        library.check(library.cna_sound_effect_set_name(self._require_handle(), view),
                      "cna_sound_effect_set_name")
        _ = encoded

    @property
    def Duration(self) -> timedelta:
        ticks = c.c_int64(); library = get_library()
        library.check(library.cna_sound_effect_get_duration_ticks(
            self._require_handle(), c.byref(ticks)), "cna_sound_effect_get_duration_ticks")
        return _ticks_timedelta(int(ticks.value))

    @staticmethod
    def _get_global(operation: str) -> float:
        _, _, library, game_handle = _active_native(); output = c.c_float()
        library.check(getattr(library, operation)(game_handle, c.byref(output)), operation)
        return f32(output.value)

    @staticmethod
    def _set_global(operation: str, value: object, minimum: float,
                    maximum: float | None, allow_zero: bool = True) -> None:
        narrowed = f32(value)
        invalid = math.isnan(narrowed) or narrowed < minimum or (maximum is not None and narrowed > maximum)
        if not allow_zero and narrowed == 0.0:
            invalid = True
        if invalid:
            raise ValueError("audio static value is outside the XNA range")
        _, _, library, game_handle = _active_native()
        library.check(getattr(library, operation)(game_handle, narrowed), operation)

    MasterVolume = staticproperty(
        lambda cls: cls._get_global("cna_sound_effect_get_master_volume"),
        lambda cls, value: cls._set_global("cna_sound_effect_set_master_volume", value, 0.0, 1.0),
    )
    SpeedOfSound = staticproperty(
        lambda cls: cls._get_global("cna_sound_effect_get_speed_of_sound"),
        lambda cls, value: cls._set_global("cna_sound_effect_set_speed_of_sound", value, 0.0, None, False),
    )
    DopplerScale = staticproperty(
        lambda cls: cls._get_global("cna_sound_effect_get_doppler_scale"),
        lambda cls, value: cls._set_global("cna_sound_effect_set_doppler_scale", value, 0.0, None),
    )

    @classmethod
    def _set_distance(cls, value: object) -> None:
        narrowed = f32(value)
        if math.isnan(narrowed) or narrowed < 0.0:
            raise ValueError("DistanceScale cannot be negative or NaN")
        if narrowed == 0.0:
            narrowed = f32(1.401298464324817e-45)
        _, _, library, game_handle = _active_native()
        library.check(library.cna_sound_effect_set_distance_scale(game_handle, narrowed),
                      "cna_sound_effect_set_distance_scale")

    DistanceScale = staticproperty(
        lambda cls: cls._get_global("cna_sound_effect_get_distance_scale"),
        lambda cls, value: cls._set_distance(value),
    )

    def CreateInstance(self) -> "SoundEffectInstance":
        output = c.c_uint64(); library = get_library()
        try:
            library.check(library.cna_sound_effect_create_instance(
                self._require_handle(), c.byref(output)), "cna_sound_effect_create_instance")
        except NativeError as error:
            if error.result == 3:
                raise InstancePlayLimitException("the sound instance limit was reached", error) from error
            raise
        instance = SoundEffectInstance._from_handle(self._game, int(output.value), self)
        self._children.append(weakref.ref(instance))
        return instance

    def Play(self, *args: object) -> bool:
        if len(args) not in (0, 3):
            raise TypeError("Play expects no arguments or volume, pitch, pan")
        played = c.c_uint8(); library = get_library(); handle = self._require_handle()
        if not args:
            result = library.cna_sound_effect_play(handle, c.byref(played))
            operation = "cna_sound_effect_play"
        else:
            values = []
            for value, name, low, high in zip(args, ("volume", "pitch", "pan"),
                                               (0.0, -1.0, -1.0), (1.0, 1.0, 1.0)):
                narrowed = f32(value)
                if math.isnan(narrowed) or narrowed < low or narrowed > high:
                    raise ValueError(f"{name} is outside the XNA range")
                values.append(narrowed)
            result = library.cna_sound_effect_play_with_settings(
                handle, values[0], values[1], values[2], c.byref(played))
            operation = "cna_sound_effect_play_with_settings"
        library.check(result, operation)
        return bool(played.value)

    @staticmethod
    def GetSampleDuration(sizeInBytes: int, sampleRate: int,
                          channels: AudioChannels) -> timedelta:
        return _sample_duration(sizeInBytes, sampleRate, channels)

    @staticmethod
    def GetSampleSizeInBytes(duration: timedelta, sampleRate: int,
                             channels: AudioChannels) -> int:
        return _sample_size(duration, sampleRate, channels)

    def Dispose(self) -> None:
        if self.IsDisposed:
            return
        first_error: BaseException | None = None
        for reference in reversed(self._children):
            child = reference()
            if child is not None and not child.IsDisposed:
                try: child.Dispose()
                except BaseException as error: first_error = first_error or error
        if first_error is not None:
            raise first_error
        self._children.clear()
        self._native.Dispose()
        self._game._unregister_native_child(self)

    def __enter__(self) -> "SoundEffect": self._require_handle(); return self
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: self.Dispose()


class SoundEffectInstance:
    def __init__(self, *args: object) -> None:
        raise TypeError("SoundEffectInstance instances are created by SoundEffect.CreateInstance")

    def _init_instance(self, game: object, handle: int, effect: SoundEffect | None,
                       *, register_game: bool = False) -> None:
        self._game, self._effect = game, effect
        self._native = NativeResource(handle, Ownership.OWNED,
                                      _release("cna_sound_effect_instance_destroy"))
        self._volume, self._pitch, self._pan, self._is_looped = 1.0, 0.0, 0.0, False
        self._has_played = False
        self._registered_game = register_game
        if register_game:
            game._register_native_child(self)

    @classmethod
    def _from_handle(cls, game: object, handle: int,
                     effect: SoundEffect | None) -> "SoundEffectInstance":
        self = cls.__new__(cls)
        self._init_instance(game, handle, effect)
        return self

    def _require_handle(self) -> int: return self._native._require_handle()
    @property
    def IsDisposed(self) -> bool: return self._native.IsDisposed

    def _info(self) -> abi.CNA_SoundEffectInstanceInfo:
        value = abi.CNA_SoundEffectInstanceInfo()
        value.struct_size, value.struct_version = c.sizeof(value), 1
        library = get_library()
        library.check(library.cna_sound_effect_instance_get_info(
            self._require_handle(), c.byref(value)), "cna_sound_effect_instance_get_info")
        return value

    @property
    def Volume(self) -> float: return self._volume
    @Volume.setter
    def Volume(self, value: float) -> None:
        self._set_float("Volume", value, 0.0, 1.0, "cna_sound_effect_instance_set_volume", "_volume")
    @property
    def Pitch(self) -> float: return self._pitch
    @Pitch.setter
    def Pitch(self, value: float) -> None:
        self._set_float("Pitch", value, -1.0, 1.0, "cna_sound_effect_instance_set_pitch", "_pitch")
    @property
    def Pan(self) -> float: return self._pan
    @Pan.setter
    def Pan(self, value: float) -> None:
        self._set_float("Pan", value, -1.0, 1.0, "cna_sound_effect_instance_set_pan", "_pan")

    def _set_float(self, name: str, value: object, low: float, high: float,
                   operation: str, attribute: str) -> None:
        narrowed = f32(value)
        if math.isnan(narrowed) or narrowed < low or narrowed > high:
            raise ValueError(f"{name} is outside the XNA range")
        library = get_library()
        library.check(getattr(library, operation)(self._require_handle(), narrowed), operation)
        setattr(self, attribute, narrowed)

    @property
    def IsLooped(self) -> bool: return self._is_looped
    @IsLooped.setter
    def IsLooped(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("IsLooped must be bool")
        if self._has_played:
            raise RuntimeError("IsLooped cannot change after playback begins")
        library = get_library()
        library.check(library.cna_sound_effect_instance_set_is_looped(
            self._require_handle(), value), "cna_sound_effect_instance_set_is_looped")
        self._is_looped = value

    @property
    def State(self) -> SoundState: return SoundState(self._info().state)

    def Play(self) -> None:
        library = get_library()
        library.check(library.cna_sound_effect_instance_play(self._require_handle()),
                      "cna_sound_effect_instance_play")
        self._has_played = True
    def Pause(self) -> None:
        library = get_library(); library.check(
            library.cna_sound_effect_instance_pause(self._require_handle()),
            "cna_sound_effect_instance_pause")
    def Resume(self) -> None:
        library = get_library(); library.check(
            library.cna_sound_effect_instance_resume(self._require_handle()),
            "cna_sound_effect_instance_resume"); self._has_played = True
    def Stop(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Stop expects no arguments or an immediate bool")
        immediate = True if not args else args[0]
        library = get_library(); library.check(
            library.cna_sound_effect_instance_stop(self._require_handle(), immediate),
            "cna_sound_effect_instance_stop")

    def _apply_3d_unpositioned(self, overload: str, result: int) -> None:
        """Reports CNA's aim-before-you-play refusal, which XNA does not impose."""
        raise NativeCapabilityError(
            overload, result, 3,
            "CNA refuses Apply3D on an instance that is playing and was never positioned, "
            "because playback fixes the choice between 3D and pan on the first play; "
            "position the instance before playing it, or stop it, position it, and play again")

    def Apply3D(self, listeners: object, emitter: AudioEmitter) -> None:
        native_emitter = _native_emitter(emitter); library = get_library(); handle = self._require_handle()
        if isinstance(listeners, AudioListener):
            native_listener = _native_listener(listeners)
            result = library.cna_sound_effect_instance_apply_3d(
                handle, c.byref(native_listener), c.byref(native_emitter))
            if result == 3 and not self.IsDisposed:
                self._apply_3d_unpositioned("SoundEffectInstance.Apply3D(listener)", result)
            library.check(result, "cna_sound_effect_instance_apply_3d")
            return
        if not isinstance(listeners, Sequence) or isinstance(listeners, (str, bytes, bytearray)):
            raise TypeError("listeners must be AudioListener or a sequence of AudioListener")
        native_values = [_native_listener(value) for value in listeners]
        if not native_values:
            # CNA refuses a zero count rather than guessing; XNA reaches XACT with
            # zero listeners and surfaces whatever it returns, which is not established.
            raise NativeCapabilityError(
                "SoundEffectInstance.Apply3D(listeners)", 1, 1,
                "CNA refuses an empty listener array and XNA's zero-listener XACT outcome "
                "is not established")
        array = (abi.CNA_AudioListener * len(native_values))(*native_values)
        result = library.cna_sound_effect_instance_apply_3d_multi_ext(
            handle, array, len(native_values), c.byref(native_emitter))
        if result == 3 and not self.IsDisposed:
            self._apply_3d_unpositioned("SoundEffectInstance.Apply3D(listeners)", result)
        library.check(result, "cna_sound_effect_instance_apply_3d_multi_ext")

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self.IsDisposed: return
        self._native.Dispose()
        if self._registered_game:
            self._game._unregister_native_child(self)
        self._effect = None

    def __enter__(self) -> "SoundEffectInstance": self._require_handle(); return self
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: self.Dispose()


class DynamicSoundEffectInstance(SoundEffectInstance, _NativeAudioEventOwner):
    BufferNeeded = Event()

    def __init__(self, sampleRate: int, channels: AudioChannels) -> None:
        rate = _validate_sample_rate(sampleRate); selected = _validate_channels(channels)
        game, _, library, game_handle = _active_native(); output = c.c_uint64()
        try:
            library.check(library.cna_dynamic_sound_effect_instance_create(
                game_handle, rate, int(selected), c.byref(output)),
                "cna_dynamic_sound_effect_instance_create")
        except NativeError as error:
            raise _audio_create_error(error) from error
        self._init_instance(game, int(output.value), None, register_game=True)
        self._sample_rate, self._channels = rate, selected
        self._init_audio_events()

    def _event_registration_call(self, name: str):
        if name != "BufferNeeded": raise ValueError("unknown dynamic-audio event")
        library = get_library()
        return library.cna_dynamic_sound_effect_instance_subscribe_buffer_needed, (self._require_handle(),)

    @property
    def IsLooped(self) -> bool:
        self._require_handle()
        return False
    @IsLooped.setter
    def IsLooped(self, value: bool) -> None:
        self._require_handle()
        if type(value) is not bool: raise TypeError("IsLooped must be bool")
        if value: raise RuntimeError("dynamic sound effects cannot loop")

    @property
    def PendingBufferCount(self) -> int:
        value = c.c_int32(); library = get_library()
        library.check(library.cna_dynamic_sound_effect_instance_get_pending_buffer_count(
            self._require_handle(), c.byref(value)),
            "cna_dynamic_sound_effect_instance_get_pending_buffer_count")
        return int(value.value)

    def SubmitBuffer(self, *args: object) -> None:
        if len(args) not in (1, 3):
            raise TypeError("SubmitBuffer expects buffer or buffer, offset, count")
        payload = _bytes(args[0])
        offset, count = (0, len(payload)) if len(args) == 1 else (args[1], args[2])
        offset, count = _validate_pcm_range(payload, offset, count, self._channels)
        native = (c.c_uint8 * len(payload)).from_buffer_copy(payload)
        library = get_library(); library.check(
            library.cna_dynamic_sound_effect_instance_submit_buffer(
                self._require_handle(), native, len(payload), offset, count),
            "cna_dynamic_sound_effect_instance_submit_buffer")

    def GetSampleDuration(self, sizeInBytes: int) -> timedelta:
        if isinstance(sizeInBytes, bool) or not isinstance(sizeInBytes, int):
            raise TypeError("sizeInBytes must be an Int32")
        ticks = c.c_int64(); library = get_library(); library.check(
            library.cna_dynamic_sound_effect_instance_get_sample_duration_ticks(
                self._require_handle(), sizeInBytes, c.byref(ticks)),
            "cna_dynamic_sound_effect_instance_get_sample_duration_ticks")
        return _ticks_timedelta(int(ticks.value))

    def GetSampleSizeInBytes(self, duration: timedelta) -> int:
        ticks = _timedelta_ticks(duration); output = c.c_int32(); library = get_library()
        library.check(library.cna_dynamic_sound_effect_instance_get_sample_size_in_bytes(
            self._require_handle(), ticks, c.byref(output)),
            "cna_dynamic_sound_effect_instance_get_sample_size_in_bytes")
        return int(output.value)

    def Play(self) -> None: super().Play()

    def Dispose(self, *args: object) -> None:
        if len(args) > 1 or (args and type(args[0]) is not bool):
            raise TypeError("Dispose expects no arguments or a bool disposing value")
        if self.IsDisposed: return
        self._unsubscribe_audio_events()
        super().Dispose(*args)


AudioListener.__xna_arities__ = {"__init__": {0}}
AudioEmitter.__xna_arities__ = {"__init__": {0}}
for _exception in (InstancePlayLimitException, NoAudioHardwareException,
                   NoMicrophoneConnectedException):
    _exception.__xna_arities__ = {"__init__": {0, 1, 2}}
SoundEffect.__xna_arities__ = {
    "__init__": {3, 7}, "FromStream": {1}, "Dispose": {0},
    "CreateInstance": {0}, "Play": {0, 3}, "GetSampleDuration": {3},
    "GetSampleSizeInBytes": {3},
}
SoundEffectInstance.__xna_arities__ = {
    "Dispose": {0, 1}, "Play": {0}, "Pause": {0}, "Resume": {0},
    "Stop": {0, 1}, "Apply3D": {2},
}
DynamicSoundEffectInstance.__xna_arities__ = {
    "__init__": {2}, "Dispose": {0, 1}, "SubmitBuffer": {1, 3},
    "GetSampleDuration": {1}, "GetSampleSizeInBytes": {1}, "Play": {0},
}
