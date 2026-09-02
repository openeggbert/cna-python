"""Compiled ``AnimationClipEXT``: bone tracks and their keyframes.

A clip is a duration, a target space, and a list of tracks each naming a bone and
holding its keyframes. The **target space** is load-bearing and must never be
guessed: a joint's skinning-palette slot has nothing to do with its position in
the scene graph, and a rigid scene node has no palette slot at all.

:class:`CnbAnimationClip` is the decoded, owned form; :class:`CnbAnimationTrack`
and :class:`CnbKeyframe <cna.extensions.content.CnbKeyframe>` are plain values.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import Sequence

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .primitives import CnbKeyframe

__all__ = [
    "ANIMATION_CLIP_SCHEMA_VERSION",
    "AnimationClipChunk",
    "ClipTargetSpace",
    "CnbAnimationClip",
    "CnbAnimationTrack",
    "decode_animation_clip",
    "encode_animation_clip",
]

#: Highest ``AnimationClip`` schema version this CNA generation understands.
ANIMATION_CLIP_SCHEMA_VERSION = _abi.CNA_CNB_ANIMATION_CLIP_SCHEMA_VERSION


class ClipTargetSpace(IntEnum):
    """Which index space a clip's bone indices are in.

    The two spaces are deliberately distinct and must never be interchanged.
    """

    JointPalette = _abi.CNA_CLIP_TARGET_SPACE_JOINT_PALETTE_EXT
    SceneNode = _abi.CNA_CLIP_TARGET_SPACE_SCENE_NODE_EXT


class AnimationClipChunk(IntEnum):
    """The three chunk identifiers the animation clip schema writes."""

    Header = _abi.CNA_CNB_ANIMATION_CLIP_CHUNK_HEADER
    Tracks = _abi.CNA_CNB_ANIMATION_CLIP_CHUNK_TRACKS
    Keys = _abi.CNA_CNB_ANIMATION_CLIP_CHUNK_KEYS


@dataclass(frozen=True)
class CnbAnimationTrack:
    """One bone's keyframes.

    ``bone_index`` is signed: an out-of-range track keeps CNA's own skip
    behaviour rather than being an error at decode time.
    """

    bone_index: int
    keyframes: tuple[CnbKeyframe, ...]


class CnbAnimationClip:
    """A decoded standalone ``AnimationClipEXT``.

    Owns native memory, so it has an explicit :meth:`close` and works as a
    context manager. Read :attr:`tracks` for the whole graph as plain values,
    which is what most callers want; the indexed accessors exist for a clip
    large enough that materialising it all is the wrong default.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @classmethod
    def _adopt(cls, handle: int) -> "CnbAnimationClip":
        return cls(_support.NativeHandle(
            handle, "cna_cnb_animation_clip_destroy", "animation clip"))

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the clip and its keyframes."""
        self._handle.close()

    def __enter__(self) -> "CnbAnimationClip":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    def _shape(self) -> tuple[float, int, ClipTargetSpace]:
        duration = c.c_double()
        track_count = c.c_uint64()
        target_space = c.c_uint32()
        _support.call("cna_cnb_animation_clip_get", self._value, c.byref(duration),
                      c.byref(track_count), c.byref(target_space))
        return (float(duration.value), int(track_count.value),
                ClipTargetSpace(int(target_space.value)))

    @property
    def duration_seconds(self) -> float:
        """The clip's duration in seconds."""
        return self._shape()[0]

    @property
    def track_count(self) -> int:
        """Number of bone tracks."""
        return self._shape()[1]

    @property
    def target_space(self) -> ClipTargetSpace:
        """Which index space this clip's bone indices are in."""
        return self._shape()[2]

    def track(self, index: int) -> CnbAnimationTrack:
        """One track's bone index and keyframes."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        bone_index = c.c_int32()
        keyframe_count = c.c_uint64()
        _support.call("cna_cnb_animation_clip_get_track", self._value, position,
                      c.byref(bone_index), c.byref(keyframe_count))
        frames = _support.two_call_structs(
            _abi.CNA_KeyframeEXT, "cna_cnb_animation_clip_copy_keyframes",
            (self._value, position))
        return CnbAnimationTrack(
            bone_index=int(bone_index.value),
            keyframes=tuple(CnbKeyframe._from_native(frame) for frame in frames))

    @property
    def tracks(self) -> tuple[CnbAnimationTrack, ...]:
        """Every track, in the order the file stores them."""
        return tuple(self.track(index) for index in range(self.track_count))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbAnimationClip closed>"
        duration, count, space = self._shape()
        return f"<CnbAnimationClip {duration}s tracks {count} {space.name}>"


def _clip_descriptor(duration_seconds: float, tracks: Sequence[CnbAnimationTrack]):
    """Builds the borrowed descriptor CNA's encode direction takes.

    Every array is kept alive in the returned tuple: the descriptor holds raw
    pointers into them, and letting one be collected would leave CNA reading
    freed memory.
    """
    keep: list[object] = []
    native_tracks = (_abi.CNA_BoneTrackEXTDescriptor * len(tracks))() if tracks else None
    for index, track in enumerate(tracks):
        frames = [frame._to_native() for frame in track.keyframes]
        array = (_abi.CNA_KeyframeEXT * len(frames))(*frames) if frames else None
        keep.append(array)
        native_tracks[index].bone_index = _support.checked(
            track.bone_index, "int32", "bone_index")
        native_tracks[index].reserved = 0
        native_tracks[index].keyframes = (
            c.cast(array, c.POINTER(_abi.CNA_KeyframeEXT)) if array else None)
        native_tracks[index].keyframe_count = len(frames)
    descriptor = _abi.CNA_AnimationClipEXTDescriptor()
    descriptor.duration_seconds = float(duration_seconds)
    descriptor.tracks = (c.cast(native_tracks, c.POINTER(_abi.CNA_BoneTrackEXTDescriptor))
                         if native_tracks else None)
    descriptor.track_count = len(tracks)
    keep.append(native_tracks)
    return descriptor, keep


def encode_animation_clip(duration_seconds: float, tracks: Sequence[CnbAnimationTrack], *,
                          target_space: ClipTargetSpace = ClipTargetSpace.SceneNode,
                          content_name: str = "") -> bytes:
    """Encodes a clip as a complete `.cnb` byte image.

    ``target_space`` is required content rather than a default worth guessing;
    it is spelled out here so a caller has to state which space its bone indices
    are in.
    """
    descriptor, keep = _clip_descriptor(duration_seconds, tuple(tracks))
    view, keep_name = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes(
        "cna_cnb_encode_animation_clip",
        (c.byref(descriptor),
         c.c_uint32(_support.checked(int(target_space), "uint32", "target_space")),
         view))
    del keep, keep_name
    return result


def decode_animation_clip(document) -> CnbAnimationClip:
    """Decodes a standalone animation clip from a parsed container."""
    return CnbAnimationClip._adopt(
        _support.out_handle("cna_cnb_decode_animation_clip", document._value))
