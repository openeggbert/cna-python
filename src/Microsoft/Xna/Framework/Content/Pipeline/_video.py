"""Video content: what a video file says about itself.

XNA's ``VideoContent`` reads the container's header and stops there -- a video
is never decoded by the pipeline, only described and copied. The header of a
``.wmv`` is an ASF header, and everything the type reports is in it.
"""

from __future__ import annotations

from datetime import timedelta
import struct

from ._errors import InvalidContentException
from ._identity import ContentIdentity, ContentItem

#: ASF's object GUIDs, little-endian as they appear in the file.
_ASF_HEADER = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
_ASF_FILE_PROPERTIES = bytes.fromhex("a1dcab8c47a9cf118ee400c00c205365")
_ASF_STREAM_PROPERTIES = bytes.fromhex("9107dcb7b7a9cf118ee600c00c205365")
_ASF_VIDEO_MEDIA = bytes.fromhex("c0ef19bc4d5bcf11a8fd00805f5c442b")

#: ASF timestamps count 100-nanosecond ticks, the same unit XNA's TimeSpan does.
_TICKS_PER_SECOND = 10_000_000


class VideoContent(ContentItem):
    """One video file, described.

    ``FramesPerSecond`` is derived rather than read: ASF's video stream carries
    the *average time per frame* in 100-nanosecond ticks, and the reciprocal of
    that is the frame rate. Deriving it is exact where reading a nominal rate
    the encoder wrote would not be.
    """

    __slots__ = ("_filename", "_video_soundtrack_type", "_duration", "_width",
                 "_height", "_bits_per_second", "_frames_per_second", "_disposed")

    def __init__(self, filename: str) -> None:
        super().__init__()
        if not isinstance(filename, str):
            raise TypeError(f"filename must be a str, not {type(filename).__name__}")
        from ..Media import VideoSoundtrackType

        self._filename = filename
        self._video_soundtrack_type = VideoSoundtrackType.Music
        self._disposed = False
        self.Identity = ContentIdentity(filename, "VideoContent")
        with open(filename, "rb") as stream:
            raw = stream.read()
        (self._duration, self._width, self._height, self._bits_per_second,
         self._frames_per_second) = _read_asf(raw, filename)

    def Dispose(self) -> None:
        self._disposed = True

    def __enter__(self) -> "VideoContent":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    @property
    def Filename(self) -> str:
        return self._filename

    @property
    def VideoSoundtrackType(self):
        return self._video_soundtrack_type

    @VideoSoundtrackType.setter
    def VideoSoundtrackType(self, value) -> None:
        from ..Media import VideoSoundtrackType as Kind

        self._video_soundtrack_type = Kind(value)

    @property
    def Duration(self) -> timedelta:
        self._require_live()
        return self._duration

    @property
    def Width(self) -> int:
        self._require_live()
        return self._width

    @property
    def Height(self) -> int:
        self._require_live()
        return self._height

    @property
    def BitsPerSecond(self) -> int:
        self._require_live()
        return self._bits_per_second

    @property
    def FramesPerSecond(self) -> float:
        self._require_live()
        return self._frames_per_second

    def _require_live(self) -> None:
        if self._disposed:
            raise RuntimeError("VideoContent has been disposed")


def _read_asf(raw: bytes, filename: str
              ) -> tuple[timedelta, int, int, int, float]:
    if raw[:16] != _ASF_HEADER:
        raise InvalidContentException(
            f"{filename} is not an ASF/WMV file", ContentIdentity(filename))
    duration = timedelta(0)
    width = height = 0
    bits_per_second = 0
    frames_per_second = 0.0
    position = 30
    while position + 24 <= len(raw):
        guid = raw[position:position + 16]
        size = struct.unpack_from("<Q", raw, position + 16)[0]
        if size < 24 or position + size > len(raw):
            break
        body = raw[position + 24:position + size]
        if guid == _ASF_FILE_PROPERTIES and len(body) >= 80:
            play_ticks, preroll_ms = struct.unpack_from("<QQ", body, 40)
            # The preroll is buffering, not content: ASF states the play
            # duration includes it, and a video reported that much too long
            # would end on a frame that is not there.
            ticks = max(0, play_ticks - preroll_ms * (_TICKS_PER_SECOND // 1000))
            duration = timedelta(microseconds=ticks // 10)
            bits_per_second = struct.unpack_from("<I", body, 76)[0] * 8
        elif guid == _ASF_STREAM_PROPERTIES and body[:16] == _ASF_VIDEO_MEDIA \
                and len(body) >= 54 + 40:
            width, height = struct.unpack_from("<ii", body, 54)
            frame_ticks = struct.unpack_from("<Q", body, 32)[0]
            if frame_ticks:
                frames_per_second = _TICKS_PER_SECOND / frame_ticks
        position += size
    if width <= 0 or height <= 0:
        raise InvalidContentException(
            f"{filename} has no video stream-properties object",
            ContentIdentity(filename))
    return duration, width, height, bits_per_second, frames_per_second
