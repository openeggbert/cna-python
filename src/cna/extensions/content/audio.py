"""Compiled sound data: the samples a `.cnb` holds, with no audio device.

:class:`CnbSoundEffectData` is asset data, not a
``Microsoft.Xna.Framework.Audio.SoundEffect``. It has no mixer, no voice and no
device behind it, so encoding and decoding are fully exercisable on a machine
with no sound hardware at all.
"""

from __future__ import annotations

import ctypes as c
from enum import IntEnum

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

__all__ = [
    "MAX_AUDIO_SAMPLE_RATE",
    "SOUND_EFFECT_SCHEMA_VERSION",
    "AudioFormat",
    "CnbSoundEffectData",
    "CnbSoundEffectInfo",
    "SoundEffectChunk",
    "audio_format_name",
    "audio_frame_bytes",
    "decode_sound_effect",
    "encode_sound_effect",
]

#: Highest sample rate a file may declare, in Hz.
MAX_AUDIO_SAMPLE_RATE = _abi.CNA_CNB_MAX_AUDIO_SAMPLE_RATE
#: Highest ``SoundEffect`` schema version this CNA generation understands.
SOUND_EFFECT_SCHEMA_VERSION = _abi.CNA_CNB_SOUND_EFFECT_SCHEMA_VERSION


class AudioFormat(IntEnum):
    """A sample format identifier as a `.cnb` sound effect stores it.

    A serialization numbering of CNB's own: a file format must not depend on the
    declaration order of a runtime enumeration, and no audio backend's
    identifiers are a serialisation ABI. **These values are wire format.**

    Four of the six are identifiers with no schema-1 codec. They are named
    because a file may legally declare one and a reader must be able to say
    which it found, not because this build can decode one.
    """

    Unknown = _abi.CNA_CNB_AUDIO_FORMAT_UNKNOWN
    Pcm16 = _abi.CNA_CNB_AUDIO_FORMAT_PCM16
    Pcm8 = _abi.CNA_CNB_AUDIO_FORMAT_PCM8
    PcmFloat32 = _abi.CNA_CNB_AUDIO_FORMAT_PCM_FLOAT32
    Adpcm = _abi.CNA_CNB_AUDIO_FORMAT_ADPCM
    Vorbis = _abi.CNA_CNB_AUDIO_FORMAT_VORBIS


class SoundEffectChunk(IntEnum):
    """The two chunk identifiers the sound effect schema writes."""

    Header = _abi.CNA_CNB_SOUND_EFFECT_CHUNK_HEADER
    Data = _abi.CNA_CNB_SOUND_EFFECT_CHUNK_DATA


def audio_frame_bytes(audio_format: AudioFormat | int, channels: int) -> int:
    """Bytes one sample frame occupies: one sample per channel."""
    return _support.out_u32(
        "cna_cnb_audio_frame_bytes",
        c.c_uint32(_support.checked(int(audio_format), "uint32", "audio_format")),
        c.c_uint32(_support.checked(channels, "uint32", "channels")))


def audio_format_name(audio_format: AudioFormat | int) -> str:
    """Renders an audio format identifier for diagnostics."""
    value = c.c_uint32(_support.checked(int(audio_format), "uint32", "audio_format"))
    return _support.sized_text(
        "cna_cnb_get_audio_format_name_size", "cna_cnb_copy_audio_format_name",
        (value,), "audio format name")


class CnbSoundEffectInfo:
    """A compiled sound's encoding, rate, shape and loop region, without its samples.

    ``loop_length`` of 0 means no loop. ``frame_count`` is samples per channel,
    which is what a duration is computed from.
    """

    __slots__ = ("format", "sample_rate", "channels", "frame_count", "loop_start",
                 "loop_length")

    def __init__(self, format: AudioFormat | int, sample_rate: int, channels: int,
                 frame_count: int, loop_start: int = 0, loop_length: int = 0) -> None:
        self.format = AudioFormat(int(format))
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.frame_count = int(frame_count)
        self.loop_start = int(loop_start)
        self.loop_length = int(loop_length)

    @property
    def duration_seconds(self) -> float:
        """The sound's duration, derived from its frame count and rate.

        Derived rather than stored: the format carries the two numbers it is
        computed from, so publishing a third would let them disagree.
        """
        return 0.0 if self.sample_rate == 0 else self.frame_count / self.sample_rate

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CnbSoundEffectInfo):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))

    def __repr__(self) -> str:
        return (f"CnbSoundEffectInfo(format={self.format!r}, "
                f"sample_rate={self.sample_rate}, channels={self.channels}, "
                f"frame_count={self.frame_count}, loop_start={self.loop_start}, "
                f"loop_length={self.loop_length})")

    def _to_native(self) -> _abi.CNA_CnbSoundEffectInfo:
        value = _abi.CNA_CnbSoundEffectInfo()
        value.struct_size = c.sizeof(_abi.CNA_CnbSoundEffectInfo)
        value.struct_version = _abi.CNA_CNB_SOUND_EFFECT_INFO_STRUCT_VERSION
        value.format = _support.checked(int(self.format), "uint32", "format")
        value.sample_rate = _support.checked(self.sample_rate, "uint32", "sample_rate")
        value.channels = _support.checked(self.channels, "uint32", "channels")
        value.frame_count = _support.checked(self.frame_count, "uint32", "frame_count")
        value.loop_start = _support.checked(self.loop_start, "uint32", "loop_start")
        value.loop_length = _support.checked(self.loop_length, "uint32", "loop_length")
        return value

    @classmethod
    def _from_native(cls, value: _abi.CNA_CnbSoundEffectInfo) -> "CnbSoundEffectInfo":
        return cls(int(value.format), int(value.sample_rate), int(value.channels),
                   int(value.frame_count), int(value.loop_start), int(value.loop_length))


class CnbSoundEffectData:
    """The decoded contents of a ``SoundEffect`` `.cnb`.

    Owns its sample bytes, so it has an explicit :meth:`close` and works as a
    context manager.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @classmethod
    def _adopt(cls, handle: int) -> "CnbSoundEffectData":
        return cls(_support.NativeHandle(
            handle, "cna_cnb_sound_effect_data_destroy", "sound effect data"))

    @classmethod
    def create(cls, info: CnbSoundEffectInfo, samples: bytes) -> "CnbSoundEffectData":
        """A description holding a **copy** of ``samples``.

        The sample bytes must be exactly
        ``frame_count * audio_frame_bytes(format, channels)`` long, which is
        checked here rather than at encode time: the caller that built a
        mismatched pair is the one that can fix it, and by encode time the
        diagnostic would name a file. The measured native behaviour accepts the
        mismatch and refuses later, so this enforces CNA's stated contract
        earlier rather than adding one.
        """
        frame_bytes = audio_frame_bytes(info.format, info.channels)
        expected = _support.checked_product(
            info.frame_count, frame_bytes, "frame_count * frame bytes")
        actual = len(memoryview(samples).cast("B"))
        if actual != expected:
            raise ValueError(
                f"{info.frame_count} frames of {info.channels}-channel "
                f"{info.format.name} need exactly {expected} bytes, got {actual}")
        native = info._to_native()
        pointer, count, keep = _support.read_only_bytes(samples, "samples")
        handle = _support.out_handle(
            "cna_cnb_sound_effect_data_create", c.byref(native), pointer, c.c_uint64(count))
        del keep
        return cls._adopt(handle)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the description and its samples."""
        self._handle.close()

    def __enter__(self) -> "CnbSoundEffectData":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    @property
    def info(self) -> CnbSoundEffectInfo:
        """The sound's encoding, rate, shape and loop region."""
        value = _support.out_struct(
            _abi.CNA_CnbSoundEffectInfo, _abi.CNA_CNB_SOUND_EFFECT_INFO_STRUCT_VERSION,
            "cna_cnb_sound_effect_data_get_info", self._value)
        return CnbSoundEffectInfo._from_native(value)

    @property
    def samples(self) -> bytes:
        """A copy of the sample bytes.

        This is a copy of native memory. For a long sound it is the largest
        allocation this package makes, which is why it is a property that says
        so rather than something that looks free.
        """
        return _support.two_call_bytes(
            "cna_cnb_sound_effect_data_copy_samples", (self._value,))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbSoundEffectData closed>"
        info = self.info
        return (f"<CnbSoundEffectData {info.format.name} {info.sample_rate}Hz "
                f"x{info.channels} frames {info.frame_count}>")


def encode_sound_effect(sound: CnbSoundEffectData, *, content_name: str = "") -> bytes:
    """Encodes a sound effect as a complete `.cnb` byte image."""
    view, keep = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes(
        "cna_cnb_encode_sound_effect", (sound._value, view))
    del keep
    return result


def decode_sound_effect(document) -> CnbSoundEffectData:
    """Decodes a sound effect from a parsed container."""
    return CnbSoundEffectData._adopt(
        _support.out_handle("cna_cnb_decode_sound_effect", document._value))
