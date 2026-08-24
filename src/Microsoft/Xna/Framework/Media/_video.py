"""Content-owned Video and owned VideoPlayer over canonical CNA routes."""

from __future__ import annotations

import ctypes as c
import math
from datetime import timedelta

from _cna_native.errors import NativeCapabilityError

from .._numeric import f32
from ._catalog import MediaState, VideoSoundtrackType
from ._runtime import _IdentityDomain, _NativeHandle, _active, _runtime, _string_view


class Video(_NativeHandle):
    _destroy_symbol = "cna_video_destroy"

    def __new__(cls, *args, **kwargs):
        raise TypeError("Video is created by ContentManager.Load")

    @classmethod
    def _create(cls, graphics_handle: int, path: str, duration_ms: int, width: int,
                height: int, frames_per_second: float,
                soundtrack_type: VideoSoundtrackType):
        _game, _host, library, _game_handle, generation = _active("Video content load")
        path_bytes, view = _string_view(path, "fileName")
        output = c.c_uint64()
        library.check(library.cna_video_create_with_metadata(
            graphics_handle, view, duration_ms, width, height, f32(frames_per_second),
            int(soundtrack_type), c.byref(output)), "cna_video_create_with_metadata")
        result = object.__new__(cls)
        result._init_handle(int(output.value), generation, _IdentityDomain())
        return result

    def _value(self, operation: str, ctype):
        library, handle = self._live_handle(operation)
        output = ctype()
        library.check(getattr(library, operation)(handle, c.byref(output)), operation)
        return output.value

    @property
    def Duration(self) -> timedelta:
        return timedelta(microseconds=self._value("cna_video_get_duration", c.c_int64) / 10)

    @property
    def Width(self) -> int: return int(self._value("cna_video_get_width", c.c_int32))
    @property
    def Height(self) -> int: return int(self._value("cna_video_get_height", c.c_int32))
    @property
    def FramesPerSecond(self) -> float:
        return float(self._value("cna_video_get_frames_per_second", c.c_float))
    @property
    def VideoSoundtrackType(self) -> VideoSoundtrackType:
        return VideoSoundtrackType(self._value("cna_video_get_soundtrack_type", c.c_uint32))

    def _content_before_unload(self) -> None:
        for value in tuple(_runtime.objects):
            if isinstance(value, VideoPlayer) and value._video is self:
                if value._handle and not value._disposed:
                    value.Stop()
                value._video = None

    def _dispose(self) -> None:
        self._live_handle("Video content unload")
        self._content_before_unload()
        self._destroy_native()
        _runtime.untrack(self)


class VideoPlayer(_NativeHandle):
    _destroy_symbol = "cna_video_player_destroy"

    def __init__(self) -> None:
        _game, _host, library, game_handle, generation = _active("VideoPlayer.__init__")
        output = c.c_uint64()
        library.check(library.cna_video_player_create(game_handle, c.byref(output)),
                      "cna_video_player_create")
        self._init_handle(int(output.value), generation, _IdentityDomain())
        self._video: Video | None = None
        self._disposed = False
        try:
            self._is_looped = self._native_bool("cna_video_player_get_is_looped")
            self._is_muted = self._native_bool("cna_video_player_get_is_muted")
            self._volume = self._native_float("cna_video_player_get_volume")
        except BaseException:
            self._destroy_native()
            _runtime.untrack(self)
            raise

    def _native_bool(self, operation: str) -> bool:
        library, handle = self._live_handle(operation)
        output = c.c_uint8()
        library.check(getattr(library, operation)(handle, c.byref(output)), operation)
        return bool(output.value)

    def _native_float(self, operation: str) -> float:
        library, handle = self._live_handle(operation)
        output = c.c_float()
        library.check(getattr(library, operation)(handle, c.byref(output)), operation)
        return float(output.value)

    def _open_handle(self, operation: str) -> tuple[object, int]:
        if self._disposed:
            raise RuntimeError("VideoPlayer is disposed")
        return self._live_handle(operation)

    @property
    def IsDisposed(self) -> bool:
        if self._disposed:
            return True
        return self._native_bool("cna_video_player_get_is_disposed")

    @property
    def Video(self) -> Video | None:
        return self._video

    @property
    def State(self) -> MediaState:
        library, handle = self._open_handle("VideoPlayer.State")
        output = c.c_uint32()
        library.check(library.cna_video_player_get_state(handle, c.byref(output)),
                      "cna_video_player_get_state")
        return MediaState(output.value)

    @property
    def PlayPosition(self) -> timedelta:
        library, handle = self._open_handle("VideoPlayer.PlayPosition")
        output = c.c_int64()
        library.check(library.cna_video_player_get_play_position_ticks(handle, c.byref(output)),
                      "cna_video_player_get_play_position_ticks")
        return timedelta(microseconds=output.value / 10)

    @property
    def IsLooped(self) -> bool:
        return self._is_looped

    @IsLooped.setter
    def IsLooped(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("IsLooped must be bool")
        library, handle = self._open_handle("VideoPlayer.IsLooped")
        library.check(library.cna_video_player_set_is_looped(handle, int(value)),
                      "cna_video_player_set_is_looped")
        self._is_looped = value

    @property
    def IsMuted(self) -> bool:
        return self._is_muted

    @IsMuted.setter
    def IsMuted(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("IsMuted must be bool")
        library, handle = self._open_handle("VideoPlayer.IsMuted")
        library.check(library.cna_video_player_set_is_muted(handle, int(value)),
                      "cna_video_player_set_is_muted")
        self._is_muted = value

    @property
    def Volume(self) -> float:
        return self._volume

    @Volume.setter
    def Volume(self, value: float) -> None:
        value = f32(value)
        if value < 0.0 or value > 1.0:
            raise ValueError("VideoPlayer.Volume must be within [0, 1] or NaN")
        library, handle = self._open_handle("VideoPlayer.Volume")
        library.check(library.cna_video_player_set_volume(handle, value),
                      "cna_video_player_set_volume")
        self._volume = value

    def Play(self, video: Video) -> None:
        if not isinstance(video, Video):
            raise TypeError("video must be Video")
        library, handle = self._open_handle("VideoPlayer.Play")
        _library2, video_handle = video._live_handle("VideoPlayer.Play")
        if video._generation != self._generation:
            raise RuntimeError("Video belongs to another Game generation")
        library.check(library.cna_video_player_play(handle, video_handle),
                      "cna_video_player_play")
        self._video = video

    def _operation(self, operation: str) -> None:
        library, handle = self._open_handle(operation)
        library.check(getattr(library, operation)(handle), operation)

    def Pause(self) -> None: self._operation("cna_video_player_pause")
    def Resume(self) -> None: self._operation("cna_video_player_resume")
    def Stop(self) -> None: self._operation("cna_video_player_stop")

    def GetTexture(self):
        library, handle = self._open_handle("VideoPlayer.GetTexture")
        if self._video is None:
            raise RuntimeError("VideoPlayer has no current Video")
        output, present = c.c_uint64(), c.c_uint8()
        library.check(library.cna_video_player_get_texture(
            handle, c.byref(output), c.byref(present)), "cna_video_player_get_texture")
        if not present.value:
            return None
        raise NativeCapabilityError(
            "cna_video_player_get_texture", 6, None,
            "CNA ABI 0.7 returns a VideoPlayer-owned frame handle valid only until the next "
            "player operation; it was neither wrapped nor destroyed because Python Texture2D "
            "requires stable XNA resource identity",
        )

    def Dispose(self) -> None:
        if self._disposed:
            return
        library, handle = self._live_handle("VideoPlayer.Dispose")
        library.check(library.cna_video_player_dispose(handle), "cna_video_player_dispose")
        self._disposed = True


VideoPlayer.__xna_arities__ = {
    "__init__": {0}, "Dispose": {0}, "Play": {1}, "Pause": {0},
    "Resume": {0}, "Stop": {0}, "GetTexture": {0},
}
