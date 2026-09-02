"""Audio content, read from the file the artist actually produced.

A ``.wav`` is read completely: the RIFF chunks give the format, the samples and
-- from the ``smpl`` chunk -- the loop region the artist marked, which is the
only place a sound effect's loop points can come from.

An ``.mp3`` or ``.wma`` is read as far as its container allows. Both are
*compressed* formats, and turning one into the PCM ``Data`` XNA hands to a
processor needs a decoder. There is none here, and there is none reachable: CNA
can decode either into a playable ``SoundEffect``, but declares no route that
reads a decoded effect's samples back out, so the bytes cannot be recovered
through it either. The format header is read and reported, because that much is
in the file and is true; ``Data`` raises and says exactly that. The unblock
condition is one route -- anything that copies a decoded sound effect's PCM.
"""

from __future__ import annotations

from datetime import timedelta
import struct

from .._collections import _ReadOnlyCollection
from .._errors import InvalidContentException
from .._identity import ContentIdentity, ContentItem
from ._enums import AudioFileType, ConversionFormat, ConversionQuality

#: ``WAVE_FORMAT_PCM``. XNA reports the format tag as an integer, and the tag is
#: the only thing that says what the samples in a ``data`` chunk actually are.
WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


class AudioFormat:
    """One audio stream's format, as the file declares it.

    ``NativeWaveFormat`` is the platform's own format structure -- on Windows a
    ``WAVEFORMATEX`` -- and XNA hands it through untouched because a codec may
    carry extra bytes after the fixed fields that only it understands. It is
    rebuilt here from the fields rather than sliced out of the file, so an
    ``AudioFormat`` built from an MP3 header has one too.
    """

    __slots__ = ("_format", "_channel_count", "_sample_rate",
                 "_average_bytes_per_second", "_block_align", "_bits_per_sample",
                 "_extra")

    def __init__(self, formatTag: int, channelCount: int, sampleRate: int,
                 averageBytesPerSecond: int, blockAlign: int, bitsPerSample: int,
                 extra: bytes = b"") -> None:
        self._format = int(formatTag)
        self._channel_count = int(channelCount)
        self._sample_rate = int(sampleRate)
        self._average_bytes_per_second = int(averageBytesPerSecond)
        self._block_align = int(blockAlign)
        self._bits_per_sample = int(bitsPerSample)
        self._extra = bytes(extra)

    @property
    def Format(self) -> int:
        return self._format

    @property
    def ChannelCount(self) -> int:
        return self._channel_count

    @property
    def SampleRate(self) -> int:
        return self._sample_rate

    @property
    def AverageBytesPerSecond(self) -> int:
        return self._average_bytes_per_second

    @property
    def BlockAlign(self) -> int:
        return self._block_align

    @property
    def BitsPerSample(self) -> int:
        return self._bits_per_sample

    @property
    def NativeWaveFormat(self) -> _ReadOnlyCollection[int]:
        """The ``WAVEFORMATEX`` bytes, little-endian, with the codec's extra."""
        header = struct.pack(
            "<HHIIHHH", self._format & 0xFFFF, self._channel_count,
            self._sample_rate, self._average_bytes_per_second,
            self._block_align, self._bits_per_sample, len(self._extra))
        return _ReadOnlyCollection(list(header + self._extra))

    def __repr__(self) -> str:
        return (f"AudioFormat(format={self._format}, channels={self._channel_count}, "
                f"rate={self._sample_rate}, bits={self._bits_per_sample})")


class AudioContent(ContentItem):
    """One audio file, read.

    Disposal is explicit and idempotent, and it releases the sample bytes --
    which for a long ``.wav`` is the only large thing the pipeline holds. XNA
    also has a finalizer; Python's projection does not, because a finalizer that
    releases nothing the interpreter would not release anyway is a way to hide
    a leak rather than to fix one.
    """

    __slots__ = ("_file_name", "_file_type", "_format", "_data", "_duration",
                 "_loop_start", "_loop_length", "_disposed", "_undecodable")

    def __init__(self, audioFileName: str, audioFileType: AudioFileType) -> None:
        super().__init__()
        if not isinstance(audioFileName, str):
            raise TypeError(
                f"audioFileName must be a str, not {type(audioFileName).__name__}")
        file_type = AudioFileType(audioFileType)
        self._file_name = audioFileName
        self._file_type = file_type
        self._disposed = False
        self._undecodable: str | None = None
        self.Identity = ContentIdentity(audioFileName, "AudioContent")
        with open(audioFileName, "rb") as stream:
            raw = stream.read()
        if file_type is AudioFileType.Wav:
            (self._format, self._data, self._loop_start,
             self._loop_length) = _read_wav(raw, audioFileName)
        elif file_type is AudioFileType.Mp3:
            self._format = _read_mp3_format(raw, audioFileName)
            self._data = b""
            self._loop_start = 0
            self._loop_length = 0
            self._undecodable = "MPEG audio"
        else:
            self._format = _read_wma_format(raw, audioFileName)
            self._data = b""
            self._loop_start = 0
            self._loop_length = 0
            self._undecodable = "Windows Media audio"
        self._duration = _duration_of(self._format, self._data, raw, file_type)

    # -- lifetime -----------------------------------------------------------

    def Dispose(self) -> None:
        self._data = b""
        self._disposed = True

    def __enter__(self) -> "AudioContent":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()

    # -- what the file said --------------------------------------------------

    @property
    def FileName(self) -> str:
        return self._file_name

    @property
    def FileType(self) -> AudioFileType:
        return self._file_type

    @property
    def Format(self) -> AudioFormat:
        self._require_live()
        return self._format

    @property
    def Data(self) -> _ReadOnlyCollection[int]:
        self._require_live()
        if self._undecodable is not None:
            raise InvalidContentException(
                f"{self._undecodable} sample data cannot be produced: decoding "
                f"{self._file_name} needs a codec, and neither this projection "
                "nor CNA's C ABI exposes one -- CNA can decode the file into a "
                "playable SoundEffect but declares no route that reads a decoded "
                "effect's PCM back out. The format header above is read from the "
                "file and is exact.",
                self.Identity)
        return _ReadOnlyCollection(list(self._data))

    @property
    def Duration(self) -> timedelta:
        self._require_live()
        return self._duration

    @property
    def LoopStart(self) -> int:
        self._require_live()
        return self._loop_start

    @property
    def LoopLength(self) -> int:
        self._require_live()
        return self._loop_length

    def ConvertFormat(self, formatType: ConversionFormat,
                      quality: ConversionQuality, targetFileName: str | None) -> None:
        """Re-encodes the content, and writes it to ``targetFileName`` if given.

        ``ConversionFormat.Pcm`` is the one this projection performs: a ``.wav``
        already carrying PCM is left as it is, and one carrying IEEE floats is
        converted to 16-bit PCM, which is what every consumer of a
        ``SoundEffect`` in this repository actually reads.

        The other three are encoders. ``Adpcm`` and ``WindowsMedia`` need codecs
        that are not present, and ``Xma`` is an Xbox 360 hardware format with no
        public encoder at all. Each raises and says which it is, rather than
        writing a file that claims a format it does not contain.
        """
        self._require_live()
        target = ConversionFormat(formatType)
        ConversionQuality(quality)
        if target is not ConversionFormat.Pcm:
            raise InvalidContentException(
                f"converting to {target.name} needs an encoder for that format; "
                "this projection performs ConversionFormat.Pcm, and neither "
                "Python's standard library nor CNA's C ABI exposes an ADPCM, "
                "Windows Media or XMA encoder", self.Identity)
        if self._undecodable is not None:
            raise InvalidContentException(
                f"{self._undecodable} cannot be converted to PCM without a "
                f"decoder for it: {self._file_name}", self.Identity)
        if self._format.Format == WAVE_FORMAT_IEEE_FLOAT:
            self._data = _floats_to_pcm16(self._data, self._format.BitsPerSample)
            self._format = AudioFormat(
                WAVE_FORMAT_PCM, self._format.ChannelCount, self._format.SampleRate,
                self._format.SampleRate * self._format.ChannelCount * 2,
                self._format.ChannelCount * 2, 16)
        if targetFileName is not None:
            if not isinstance(targetFileName, str):
                raise TypeError("targetFileName must be a str or None, not "
                                f"{type(targetFileName).__name__}")
            _write_wav(targetFileName, self._format, self._data)

    def _require_live(self) -> None:
        if self._disposed:
            raise RuntimeError("AudioContent has been disposed")


# -- readers ----------------------------------------------------------------


def _read_wav(raw: bytes, filename: str) -> tuple[AudioFormat, bytes, int, int]:
    """Every RIFF chunk that matters: ``fmt ``, ``data`` and ``smpl``."""
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise InvalidContentException(
            f"{filename} is not a RIFF/WAVE file", ContentIdentity(filename))
    audio_format: AudioFormat | None = None
    data = b""
    loop_start = 0
    loop_length = 0
    position = 12
    while position + 8 <= len(raw):
        identifier = raw[position:position + 4]
        size = struct.unpack_from("<I", raw, position + 4)[0]
        body = raw[position + 8:position + 8 + size]
        if identifier == b"fmt ":
            audio_format = _wave_format(body, filename)
        elif identifier == b"data":
            data = body
        elif identifier == b"smpl":
            loop_start, loop_length = _sample_loop(body)
        # RIFF chunks are word-aligned: an odd size is followed by a pad byte.
        position += 8 + size + (size & 1)
    if audio_format is None:
        raise InvalidContentException(
            f"{filename} has no fmt chunk", ContentIdentity(filename))
    return audio_format, data, loop_start, loop_length


def _wave_format(body: bytes, filename: str) -> AudioFormat:
    if len(body) < 16:
        raise InvalidContentException(
            f"{filename} has a truncated fmt chunk", ContentIdentity(filename))
    (tag, channels, rate, average, align, bits) = struct.unpack_from("<HHIIHH", body, 0)
    extra = b""
    if len(body) >= 18:
        extra_size = struct.unpack_from("<H", body, 16)[0]
        extra = body[18:18 + extra_size]
    return AudioFormat(tag, channels, rate, average, align, bits, extra)


def _sample_loop(body: bytes) -> tuple[int, int]:
    """The first loop the artist marked, in *sample frames*.

    XNA reports loop points in sample frames, and a ``smpl`` chunk stores them
    the same way, so the two agree with no arithmetic. A file with no loops
    reports ``(0, 0)``, which is what "play once" means.
    """
    if len(body) < 36:
        return 0, 0
    loop_count = struct.unpack_from("<I", body, 28)[0]
    if loop_count == 0 or len(body) < 36 + 24:
        return 0, 0
    start, end = struct.unpack_from("<II", body, 36 + 8)
    return start, max(0, end - start + 1)


def _read_mp3_format(raw: bytes, filename: str) -> AudioFormat:
    """The first MPEG audio frame header, which carries the whole format."""
    offset = _mp3_first_frame(raw)
    if offset is None:
        raise InvalidContentException(
            f"{filename} has no MPEG audio frame header",
            ContentIdentity(filename))
    header = struct.unpack_from(">I", raw, offset)[0]
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    rate_index = (header >> 10) & 0x3
    channel_mode = (header >> 6) & 0x3
    rate = _MPEG_SAMPLE_RATES[version][rate_index]
    bitrate = _MPEG_BITRATES[_bitrate_row(version, layer)][bitrate_index] * 1000
    channels = 1 if channel_mode == 3 else 2
    # 85 is WAVE_FORMAT_MPEGLAYER3, which is the tag a WAVEFORMATEX carries for
    # MP3 content; the bits-per-sample of a compressed stream is zero, and
    # saying 16 would be inventing a number the file does not have.
    return AudioFormat(85, channels, rate, bitrate // 8, 1, 0)


def _mp3_first_frame(raw: bytes) -> int | None:
    start = 0
    if raw[:3] == b"ID3" and len(raw) >= 10:
        # A synchsafe size: seven bits per byte, high bit always clear.
        size = 0
        for byte in raw[6:10]:
            size = (size << 7) | (byte & 0x7F)
        start = 10 + size
    for offset in range(start, min(len(raw) - 4, start + 0x10000)):
        if raw[offset] != 0xFF or (raw[offset + 1] & 0xE0) != 0xE0:
            continue
        header = struct.unpack_from(">I", raw, offset)[0]
        if ((header >> 19) & 0x3) == 1 or ((header >> 17) & 0x3) == 0:
            continue  # a reserved version or layer: not a real frame header
        if ((header >> 12) & 0xF) in (0, 0xF) or ((header >> 10) & 0x3) == 3:
            continue  # a free or reserved bitrate, or a reserved sample rate
        return offset
    return None


def _bitrate_row(version: int, layer: int) -> int:
    if version == 3:  # MPEG 1
        return {3: 0, 2: 1, 1: 2}[layer]
    return {3: 3, 2: 4, 1: 4}[layer]  # MPEG 2 and 2.5 share layers II and III


_MPEG_SAMPLE_RATES = {
    3: (44100, 48000, 32000, 0),   # MPEG 1
    2: (22050, 24000, 16000, 0),   # MPEG 2
    0: (11025, 12000, 8000, 0),    # MPEG 2.5
    1: (0, 0, 0, 0),               # reserved
}

_MPEG_BITRATES = (
    (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0),
    (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0),
    (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
    (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0),
    (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
)

#: ASF's stream-properties object, and the audio media type inside it.
_ASF_HEADER = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
_ASF_STREAM_PROPERTIES = bytes.fromhex("9107dcb7b7a9cf118ee600c00c205365")
_ASF_AUDIO_MEDIA = bytes.fromhex("409e69f84d5bcf11a8fd00805f5c442b")


def _read_wma_format(raw: bytes, filename: str) -> AudioFormat:
    """The ``WAVEFORMATEX`` inside an ASF stream-properties object.

    ASF stores the audio format as the very structure ``NativeWaveFormat``
    reports, so the header is read rather than reconstructed.
    """
    if raw[:16] != _ASF_HEADER:
        raise InvalidContentException(
            f"{filename} is not an ASF/WMA file", ContentIdentity(filename))
    position = 30
    while position + 24 <= len(raw):
        guid = raw[position:position + 16]
        size = struct.unpack_from("<Q", raw, position + 16)[0]
        if size < 24 or position + size > len(raw):
            break
        if guid == _ASF_STREAM_PROPERTIES:
            body = raw[position + 24:position + size]
            if body[:16] == _ASF_AUDIO_MEDIA and len(body) >= 78:
                return _wave_format(body[78 - 24:], filename)
        position += size
    raise InvalidContentException(
        f"{filename} has no audio stream-properties object",
        ContentIdentity(filename))


def _duration_of(audio_format: AudioFormat, data: bytes, raw: bytes,
                 file_type: AudioFileType) -> timedelta:
    """How long the content plays.

    For PCM this is exact: bytes divided by bytes per second. For a compressed
    stream there are no decoded bytes, so the answer comes from the file size
    and the declared bitrate, which is what the container itself claims.
    """
    per_second = audio_format.AverageBytesPerSecond
    if per_second <= 0:
        return timedelta(0)
    payload = len(data) if file_type is AudioFileType.Wav else len(raw)
    return timedelta(microseconds=round(payload * 1_000_000 / per_second))


def _floats_to_pcm16(data: bytes, bits: int) -> bytes:
    if bits != 32:
        raise InvalidContentException(
            f"{bits}-bit IEEE float samples are not a format this converts")
    count = len(data) // 4
    values = struct.unpack_from(f"<{count}f", data, 0)
    clamped = [max(-32768, min(32767, int(round(value * 32767.0)))) for value in values]
    return struct.pack(f"<{count}h", *clamped)


def _write_wav(path: str, audio_format: AudioFormat, data: bytes) -> None:
    header = bytes(audio_format.NativeWaveFormat)
    body = (b"WAVE"
            + b"fmt " + struct.pack("<I", len(header)) + header
            + b"data" + struct.pack("<I", len(data)) + data)
    with open(path, "wb") as stream:
        stream.write(b"RIFF" + struct.pack("<I", len(body)) + body)
