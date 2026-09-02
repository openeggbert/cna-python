"""The three audio enumerations."""

from __future__ import annotations

from enum import IntEnum


class AudioFileType(IntEnum):
    """Which container an :class:`AudioContent` was read from."""

    Wav = 0
    Mp3 = 1
    Wma = 2


class ConversionFormat(IntEnum):
    """What ``AudioContent.ConvertFormat`` should re-encode the content as."""

    Pcm = 0
    Adpcm = 1
    WindowsMedia = 2
    Xma = 3


class ConversionQuality(IntEnum):
    """How hard the encoder should work, where the encoder has a choice."""

    Low = 0
    Medium = 1
    Best = 2
