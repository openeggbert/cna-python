"""Compiled ``Song`` and ``Video``: metadata plus a reference to the real stream.

Neither schema embeds encoded media. A compiled song or video carries its
metadata and the **logical name** of the stream that holds the actual audio or
frames, so the media file stays one asset rather than being duplicated inside
every `.cnb` that mentions it. Playback is a runtime concern and is not part of
this family; what is here is exactly what the file stores.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum

from Microsoft.Xna.Framework.Media import VideoSoundtrackType

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

__all__ = [
    "MAX_VIDEO_DIMENSION",
    "MEDIA_SCHEMA_VERSION",
    "CnbSongData",
    "CnbVideoData",
    "MediaChunk",
    "decode_song",
    "decode_video",
    "encode_song",
    "encode_video",
]

#: Highest frame dimension a ``Video`` may declare, in pixels.
MAX_VIDEO_DIMENSION = _abi.CNA_CNB_MAX_VIDEO_DIMENSION
#: Highest ``Song`` and ``Video`` schema version this CNA generation understands.
MEDIA_SCHEMA_VERSION = _abi.CNA_CNB_MEDIA_SCHEMA_VERSION


class MediaChunk(IntEnum):
    """The chunk identifier each media schema writes."""

    SongHeader = _abi.CNA_CNB_MEDIA_CHUNK_SONG_HEADER
    VideoHeader = _abi.CNA_CNB_MEDIA_CHUNK_VIDEO_HEADER


@dataclass(frozen=True)
class CnbSongData:
    """A compiled ``Song``: its display name, duration and stream reference.

    ``duration_milliseconds`` is 0 when the compiler could not determine it,
    which is a real answer rather than a missing one.
    """

    stream_reference: str
    name: str
    duration_milliseconds: int


@dataclass(frozen=True)
class CnbVideoData:
    """A compiled ``Video``: its frame metadata and stream reference.

    ``soundtrack_type`` reuses the strict XNA identity, which is exactly what
    the field means; the dependency runs extension -> strict only.
    """

    stream_reference: str
    duration_milliseconds: int
    width: int
    height: int
    frames_per_second: float
    soundtrack_type: VideoSoundtrackType


def encode_song(song: CnbSongData, *, content_name: str = "") -> bytes:
    """Encodes a song as a complete `.cnb` byte image."""
    stream_view, keep_stream = _support.string_view(
        song.stream_reference, "stream_reference")
    name_view, keep_name = _support.string_view(song.name, "name")
    duration = c.c_uint32(_support.checked(
        song.duration_milliseconds, "uint32", "duration_milliseconds"))
    content_view, keep_content = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes(
        "cna_cnb_encode_song", (stream_view, name_view, duration, content_view))
    del keep_stream, keep_name, keep_content
    return result


def decode_song(document) -> CnbSongData:
    """Decodes a song from a parsed container."""
    handle = document._value
    return CnbSongData(
        stream_reference=_support.sized_text(
            "cna_cnb_decode_song_stream_reference_size",
            "cna_cnb_decode_song_stream_reference", (handle,), "song stream reference"),
        name=_support.sized_text(
            "cna_cnb_decode_song_name_size", "cna_cnb_decode_song_name",
            (handle,), "song name"),
        duration_milliseconds=_support.out_u32(
            "cna_cnb_decode_song_duration_milliseconds", handle),
    )


def encode_video(video: CnbVideoData, *, content_name: str = "") -> bytes:
    """Encodes a video as a complete `.cnb` byte image."""
    info = _abi.CNA_CnbVideoInfo()
    info.struct_size = c.sizeof(_abi.CNA_CnbVideoInfo)
    info.struct_version = _abi.CNA_CNB_VIDEO_INFO_STRUCT_VERSION
    info.duration_milliseconds = _support.checked(
        video.duration_milliseconds, "uint32", "duration_milliseconds")
    info.width = _support.checked(video.width, "uint32", "width")
    info.height = _support.checked(video.height, "uint32", "height")
    info.frames_per_second = float(video.frames_per_second)
    info.soundtrack_type = _support.checked(
        int(video.soundtrack_type), "uint32", "soundtrack_type")
    info.reserved = 0
    stream_view, keep_stream = _support.string_view(
        video.stream_reference, "stream_reference")
    content_view, keep_content = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes(
        "cna_cnb_encode_video", (stream_view, c.byref(info), content_view))
    del keep_stream, keep_content
    return result


def decode_video(document) -> CnbVideoData:
    """Decodes a video from a parsed container."""
    handle = document._value
    info = _support.out_struct(
        _abi.CNA_CnbVideoInfo, _abi.CNA_CNB_VIDEO_INFO_STRUCT_VERSION,
        "cna_cnb_decode_video", handle)
    return CnbVideoData(
        stream_reference=_support.sized_text(
            "cna_cnb_decode_video_stream_reference_size",
            "cna_cnb_decode_video_stream_reference", (handle,), "video stream reference"),
        duration_milliseconds=int(info.duration_milliseconds),
        width=int(info.width), height=int(info.height),
        frames_per_second=float(info.frames_per_second),
        soundtrack_type=VideoSoundtrackType(int(info.soundtrack_type)),
    )
