"""Process-global MediaPlayer and generation-scoped MediaQueue."""

from __future__ import annotations

import ctypes as c
import math
from datetime import timedelta

from _cna_native import abi

from .._language import Event, classproperty, staticproperty, staticpropertymeta
from .._numeric import f32, int32
from ._catalog import MediaState, Song, SongCollection, VisualizationData, _wrap
from ._runtime import _IdentityDomain, _NativeHandle, _active, _runtime


def _bool_get(operation: str) -> bool:
    _game, _host, library, handle, _generation = _active(operation)
    value = c.c_uint8()
    library.check(getattr(library, operation)(handle, c.byref(value)), operation)
    return bool(value.value)


def _bool_set(operation: str, value: object) -> None:
    if type(value) is not bool:
        raise TypeError("value must be bool")
    _game, _host, library, handle, _generation = _active(operation)
    library.check(getattr(library, operation)(handle, int(value)), operation)


class MediaQueue(_NativeHandle):
    _destroy_symbol = "cna_media_queue_destroy"

    @property
    def Count(self) -> int:
        library, handle = self._live_handle("MediaQueue.Count")
        value = c.c_int32()
        library.check(library.cna_media_queue_get_count(handle, c.byref(value)),
                      "cna_media_queue_get_count")
        return int(value.value)

    @property
    def ActiveSongIndex(self) -> int:
        library, handle = self._live_handle("MediaQueue.ActiveSongIndex")
        value = c.c_int32()
        library.check(library.cna_media_queue_get_active_song_index(handle, c.byref(value)),
                      "cna_media_queue_get_active_song_index")
        return int(value.value)

    @ActiveSongIndex.setter
    def ActiveSongIndex(self, value: int) -> None:
        value = int32(value, name="value")
        library, handle = self._live_handle("MediaQueue.ActiveSongIndex")
        library.check(library.cna_media_queue_set_active_song_index(handle, value),
                      "cna_media_queue_set_active_song_index")

    def _item(self, output_handle: int, index: int | None):
        sources = getattr(_runtime, "queue_sources", ())
        candidate = (sources[index] if index is not None and 0 <= index < len(sources)
                     else None)
        if isinstance(candidate, Song) and candidate._handle:
            library, _handle = self._live_handle("MediaQueue identity")
            same = c.c_uint8()
            library.check(library.cna_song_equals(candidate._handle, output_handle,
                                                   c.byref(same)), "cna_song_equals")
            if same.value:
                library.check(library.cna_song_destroy(output_handle), "cna_song_destroy")
                return candidate
        return _wrap(Song, output_handle, self._generation, self._domain)

    @property
    def ActiveSong(self):
        library, handle = self._live_handle("MediaQueue.ActiveSong")
        output, present = c.c_uint64(), c.c_uint8()
        library.check(library.cna_media_queue_get_active_song(
            handle, c.byref(output), c.byref(present)), "cna_media_queue_get_active_song")
        return self._item(int(output.value), self.ActiveSongIndex) if present.value else None

    def __getitem__(self, index: int) -> Song:
        index = int32(index, name="index")
        if index < 0 or index >= self.Count:
            raise IndexError("media queue index out of range")
        library, handle = self._live_handle("MediaQueue.__getitem__")
        output = c.c_uint64()
        library.check(library.cna_media_queue_get_at(handle, index, c.byref(output)),
                      "cna_media_queue_get_at")
        return self._item(int(output.value), index)

    def __iter__(self):
        return iter(tuple(self[index] for index in range(self.Count)))

    def __len__(self):
        return self.Count


class MediaPlayer(metaclass=staticpropertymeta):
    ActiveSongChanged = Event(static=True)
    MediaStateChanged = Event(static=True)

    def __new__(cls, *args, **kwargs):
        raise TypeError("MediaPlayer is static")

    @classmethod
    def _event_subscribe(cls, name: str) -> None:
        _runtime.want_event(name)

    @classmethod
    def _event_unsubscribe(cls, name: str) -> None:
        _runtime.unwant_event(name)

    @staticmethod
    def Play(value, startIndex=None) -> None:
        _game, _host, library, handle, generation = _active("MediaPlayer.Play")
        if isinstance(value, Song):
            if startIndex is not None:
                raise TypeError("Song Play overload has no startIndex")
            if value.IsDisposed:
                raise RuntimeError("Song is disposed")
            _library2, song_handle = value._live_handle("MediaPlayer.Play")
            library.check(library.cna_media_player_play_song(handle, song_handle),
                          "cna_media_player_play_song")
            _runtime.queue_sources = (value,)
            return
        if not isinstance(value, SongCollection):
            raise TypeError("value must be Song or SongCollection")
        if value.IsDisposed:
            raise RuntimeError("SongCollection is disposed")
        _library2, songs_handle = value._live_handle("MediaPlayer.Play")
        sources = tuple(value)
        if not sources:
            raise ValueError("SongCollection cannot be empty")
        if startIndex is None:
            library.check(library.cna_media_player_play_songs(handle, songs_handle),
                          "cna_media_player_play_songs")
        else:
            index = int32(startIndex, name="startIndex")
            if index < 0 or index >= len(sources):
                raise IndexError("startIndex is outside the SongCollection")
            library.check(library.cna_media_player_play_songs_from(handle, songs_handle, index),
                          "cna_media_player_play_songs_from")
        _runtime.queue_sources = sources

    @staticmethod
    def _transport(operation: str) -> None:
        _game, _host, library, handle, _generation = _active(operation)
        library.check(getattr(library, operation)(handle), operation)

    @staticmethod
    def Pause() -> None: MediaPlayer._transport("cna_media_player_pause")
    @staticmethod
    def Resume() -> None: MediaPlayer._transport("cna_media_player_resume")
    @staticmethod
    def Stop() -> None: MediaPlayer._transport("cna_media_player_stop")
    @staticmethod
    def MoveNext() -> None: MediaPlayer._transport("cna_media_player_move_next")
    @staticmethod
    def MovePrevious() -> None: MediaPlayer._transport("cna_media_player_move_previous")

    @staticmethod
    def GetVisualizationData(data: VisualizationData) -> None:
        if not isinstance(data, VisualizationData):
            raise TypeError("data must be VisualizationData")
        _game, _host, library, handle, _generation = _active(
            "MediaPlayer.GetVisualizationData")
        native = abi.CNA_VisualizationData()
        native.struct_size, native.struct_version = c.sizeof(native), 1
        library.check(library.cna_media_player_get_visualization_data(
            handle, c.byref(native)), "cna_media_player_get_visualization_data")
        data._replace(native.frequencies, native.samples)

    @classproperty
    def Queue(cls) -> MediaQueue:
        _game, _host, library, handle, generation = _active("MediaPlayer.Queue")
        current = _runtime.queue
        if isinstance(current, MediaQueue) and current._generation == generation and current._handle:
            return current
        output = c.c_uint64()
        library.check(library.cna_media_player_get_queue(handle, c.byref(output)),
                      "cna_media_player_get_queue")
        current = object.__new__(MediaQueue)
        current._init_handle(int(output.value), generation, _IdentityDomain())
        # Queue has a distinct teardown slot and must not also be in objects.
        _runtime.untrack(current)
        _runtime.queue = current
        return current

    @classproperty
    def State(cls) -> MediaState:
        _game, _host, library, handle, _generation = _active("MediaPlayer.State")
        value = c.c_uint32()
        library.check(library.cna_media_player_get_state(handle, c.byref(value)),
                      "cna_media_player_get_state")
        return MediaState(value.value)

    @classproperty
    def PlayPosition(cls) -> timedelta:
        _game, _host, library, handle, _generation = _active("MediaPlayer.PlayPosition")
        value = c.c_int64()
        library.check(library.cna_media_player_get_play_position_ticks(handle, c.byref(value)),
                      "cna_media_player_get_play_position_ticks")
        return timedelta(microseconds=value.value / 10)

    @classproperty
    def GameHasControl(cls) -> bool:
        return _bool_get("cna_media_player_get_game_has_control")

    IsMuted = staticproperty(lambda cls: _bool_get("cna_media_player_get_is_muted"),
                             lambda cls, value: _bool_set("cna_media_player_set_is_muted", value))
    IsRepeating = staticproperty(lambda cls: _bool_get("cna_media_player_get_is_repeating"),
                                 lambda cls, value: _bool_set("cna_media_player_set_is_repeating", value))
    IsShuffled = staticproperty(lambda cls: _bool_get("cna_media_player_get_is_shuffled"),
                                lambda cls, value: _bool_set("cna_media_player_set_is_shuffled", value))
    IsVisualizationEnabled = staticproperty(
        lambda cls: _bool_get("cna_media_player_get_is_visualization_enabled"),
        lambda cls, value: _bool_set("cna_media_player_set_is_visualization_enabled", value))

    @staticmethod
    def _get_volume(cls) -> float:
        _game, _host, library, handle, _generation = _active("MediaPlayer.Volume")
        value = c.c_float()
        library.check(library.cna_media_player_get_volume(handle, c.byref(value)),
                      "cna_media_player_get_volume")
        return float(value.value)

    @staticmethod
    def _set_volume(cls, value: object) -> None:
        value = f32(value)
        # XNA MediaPlayer clamps finite and infinite values; comparisons leave
        # NaN untouched and preserve the sign of zero.
        if value < 0.0:
            value = 0.0
        elif value > 1.0:
            value = 1.0
        _game, _host, library, handle, _generation = _active("MediaPlayer.Volume")
        library.check(library.cna_media_player_set_volume(handle, value),
                      "cna_media_player_set_volume")

    Volume = staticproperty(_get_volume, _set_volume)


MediaQueue.__xna_arities__ = {"__getitem__": {1}}
MediaPlayer.__xna_arities__ = {
    "Play": {1, 2}, "Pause": {0}, "Resume": {0}, "Stop": {0},
    "MoveNext": {0}, "MovePrevious": {0}, "GetVisualizationData": {1},
}


def _update_media_game(game: object) -> None:
    host = getattr(game, "_host", None)
    if host is None or not host.handle:
        return
    with _runtime.lock:
        if _runtime.game_ref is None or _runtime.game_ref() is not game:
            return
    host.library.check(host.library.cna_media_player_update_ext(host.handle),
                       "cna_media_player_update_ext")
