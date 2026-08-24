"""Native MediaLibrary graph, sources, songs, pictures, and read-only collections."""

from __future__ import annotations

import ctypes as c
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from io import BytesIO
from collections.abc import Sequence

from .._numeric import int32
from ._runtime import (
    _IdentityDomain, _NativeHandle, _active, _copy_bytes, _copy_string, _runtime,
    _string_view,
)


class MediaSourceType(IntEnum):
    LocalDevice = 0
    WindowsMediaConnect = 4


class MediaState(IntEnum):
    Stopped = 0
    Playing = 1
    Paused = 2


class VideoSoundtrackType(IntEnum):
    Music = 0
    Dialog = 1
    MusicAndDialog = 2


class VisualizationData:
    def __init__(self) -> None:
        self._frequencies = (0.0,) * 256
        self._samples = (0.0,) * 256

    @property
    def Frequencies(self) -> tuple[float, ...]:
        return self._frequencies

    @property
    def Samples(self) -> tuple[float, ...]:
        return self._samples

    def _replace(self, frequencies, samples) -> None:
        self._frequencies = tuple(float(value) for value in frequencies)
        self._samples = tuple(float(value) for value in samples)


class MediaSource:
    def __init__(self, name: str, type_: MediaSourceType, generation: int) -> None:
        self._name, self._type, self._generation = name, type_, generation

    def _live(self) -> None:
        _game, _host, _library, _handle, generation = _active("MediaSource")
        if generation != self._generation:
            raise RuntimeError("MediaSource belongs to a stale Game generation")

    @staticmethod
    def GetAvailableMediaSources() -> list["MediaSource"]:
        _game, _host, library, game_handle, generation = _active(
            "MediaSource.GetAvailableMediaSources")
        count = c.c_uint32()
        library.check(library.cna_media_source_get_available_count(game_handle, c.byref(count)),
                      "cna_media_source_get_available_count")
        result = []
        for index in range(count.value):
            type_value = c.c_uint32()
            library.check(library.cna_media_source_get_type_at(
                game_handle, index, c.byref(type_value)), "cna_media_source_get_type_at")
            size = c.c_uint64()
            library.check(library.cna_media_source_get_name_size_at(
                game_handle, index, c.byref(size)), "cna_media_source_get_name_size_at")
            output = c.create_string_buffer(size.value) if size.value else None
            written = c.c_uint64()
            if size.value:
                library.check(library.cna_media_source_copy_name_at(
                    game_handle, index, output, size.value, c.byref(written)),
                    "cna_media_source_copy_name_at")
                name = bytes(output.raw[:written.value]).decode("utf-8", errors="strict")
            else:
                name = ""
            source_type = MediaSourceType(type_value.value)
            key = (generation, name, int(source_type))
            source = _runtime.sources.get(key)
            if source is None:
                source = MediaSource(name, source_type, generation)
                _runtime.sources[key] = source
            result.append(source)
        return result

    @property
    def Name(self) -> str:
        self._live()
        return self._name

    @property
    def MediaSourceType(self) -> MediaSourceType:
        self._live()
        return self._type

    def ToString(self) -> str:
        return self.Name

    def __str__(self) -> str:
        return self.ToString()


def _out(library: object, operation: str, handle: int, ctype):
    value = ctype()
    library.check(getattr(library, operation)(handle, c.byref(value)), operation)
    return value.value


def _wrap(cls, handle: int, generation: int, domain: _IdentityDomain):
    if not handle:
        raise RuntimeError(f"CNA returned a null {cls.__name__} handle")
    equals = getattr(cls, "_equals_symbol", "")
    if equals:
        library = _active(f"{cls.__name__} identity")[2]
        for current in domain.items.get(cls, ()):
            if current._handle:
                same = c.c_uint8()
                library.check(getattr(library, equals)(current._handle, handle, c.byref(same)), equals)
                if same.value:
                    library.check(getattr(library, cls._destroy_symbol)(handle), cls._destroy_symbol)
                    return current
    result = object.__new__(cls)
    result._init_handle(handle, generation, domain)
    domain.items.setdefault(cls, []).append(result)
    return result


def _nullable(owner: _NativeHandle, operation: str, cls):
    library, handle = owner._live_handle(operation)
    output, present = c.c_uint64(), c.c_uint8()
    library.check(getattr(library, operation)(handle, c.byref(output), c.byref(present)), operation)
    return _wrap(cls, int(output.value), owner._generation, owner._domain) if present.value else None


class _CatalogObject(_NativeHandle):
    _stem = ""
    _equals_symbol = ""

    def Dispose(self) -> None:
        library, handle = self._live_handle(f"{type(self).__name__}.Dispose")
        operation = f"cna_{self._stem}_dispose"
        library.check(getattr(library, operation)(handle), operation)

    @property
    def IsDisposed(self) -> bool:
        library, handle = self._live_handle(f"{type(self).__name__}.IsDisposed")
        return bool(_out(library, f"cna_{self._stem}_get_is_disposed", handle, c.c_uint8))

    @property
    def Name(self) -> str:
        library, handle = self._live_handle(f"{type(self).__name__}.Name")
        return _copy_string(library, handle, f"cna_{self._stem}")

    def Equals(self, obj: object) -> bool:
        if type(obj) is not type(self):
            return False
        library, handle = self._live_handle(f"{type(self).__name__}.Equals")
        _library2, other = obj._live_handle(f"{type(self).__name__}.Equals")
        value = c.c_uint8()
        library.check(getattr(library, self._equals_symbol)(handle, other, c.byref(value)),
                      self._equals_symbol)
        return bool(value.value)

    def GetHashCode(self) -> int:
        library, handle = self._live_handle(f"{type(self).__name__}.GetHashCode")
        return int(_out(library, f"cna_{self._stem}_get_hash_code", handle, c.c_int32))

    def ToString(self) -> str:
        return self.Name

    def __eq__(self, other: object) -> bool:
        return self.Equals(other)

    def __ne__(self, other: object) -> bool:
        return not self.Equals(other)

    def __hash__(self) -> int:
        return self.GetHashCode()

    def __str__(self) -> str:
        return self.ToString()


class _Collection(_NativeHandle):
    _stem = ""
    _item_type = object

    @property
    def Count(self) -> int:
        library, handle = self._live_handle(f"{type(self).__name__}.Count")
        return int(_out(library, f"cna_{self._stem}_get_count", handle, c.c_int32))

    @property
    def IsDisposed(self) -> bool:
        library, handle = self._live_handle(f"{type(self).__name__}.IsDisposed")
        return bool(_out(library, f"cna_{self._stem}_get_is_disposed", handle, c.c_uint8))

    def Dispose(self) -> None:
        library, handle = self._live_handle(f"{type(self).__name__}.Dispose")
        operation = f"cna_{self._stem}_dispose"
        library.check(getattr(library, operation)(handle), operation)

    def __getitem__(self, index: int):
        index = int32(index, name="index")
        count = self.Count
        if index < 0 or index >= count:
            raise IndexError("collection index out of range")
        library, handle = self._live_handle(f"{type(self).__name__}.__getitem__")
        output = c.c_uint64()
        operation = f"cna_{self._stem}_get_at"
        library.check(getattr(library, operation)(handle, index, c.byref(output)), operation)
        return _wrap(self._item_type, int(output.value), self._generation, self._domain)

    def GetEnumerator(self):
        return iter(tuple(self[index] for index in range(self.Count)))

    def __iter__(self):
        return self.GetEnumerator()

    def __len__(self) -> int:
        return self.Count


class Album(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "album", "cna_album_destroy", "cna_album_equals"

    @property
    def Artist(self): return _nullable(self, "cna_album_get_artist", Artist)
    @property
    def Genre(self): return _nullable(self, "cna_album_get_genre", Genre)
    @property
    def Songs(self): return _cached_collection(self, "Songs", "cna_album_get_songs", SongCollection)
    @property
    def Duration(self): return _ticks(self, "cna_album_get_duration")
    @property
    def HasArt(self): return _bool(self, "cna_album_get_has_art")
    def GetAlbumArt(self): return BytesIO(_buffer(self, "cna_album_get_art"))
    def GetThumbnail(self): return BytesIO(_buffer(self, "cna_album_get_thumbnail"))


class Artist(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "artist", "cna_artist_destroy", "cna_artist_equals"
    @property
    def Songs(self): return _cached_collection(self, "Songs", "cna_artist_get_songs", SongCollection)
    @property
    def Albums(self): return _cached_collection(self, "Albums", "cna_artist_get_albums", AlbumCollection)


class Genre(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "genre", "cna_genre_destroy", "cna_genre_equals"
    @property
    def Songs(self): return _cached_collection(self, "Songs", "cna_genre_get_songs", SongCollection)
    @property
    def Albums(self): return _cached_collection(self, "Albums", "cna_genre_get_albums", AlbumCollection)


class Playlist(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "playlist", "cna_playlist_destroy", "cna_playlist_equals"
    @property
    def Songs(self): return _cached_collection(self, "Songs", "cna_playlist_get_songs", SongCollection)
    @property
    def Duration(self): return _ticks(self, "cna_playlist_get_duration")


class Song(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "song", "cna_song_destroy", "cna_song_equals"

    @staticmethod
    def FromUri(name: str, uri: str):
        _game, _host, library, game_handle, generation = _active("Song.FromUri")
        name_bytes, name_view = _string_view(name, "name")
        uri_bytes, uri_view = _string_view(uri, "uri")
        output = c.c_uint64()
        library.check(library.cna_song_create_from_uri(
            game_handle, name_view, uri_view, c.byref(output)), "cna_song_create_from_uri")
        return _wrap(Song, int(output.value), generation, _IdentityDomain())

    @property
    def Artist(self): return _nullable(self, "cna_song_get_artist", Artist)
    @property
    def Album(self): return _nullable(self, "cna_song_get_album", Album)
    @property
    def Genre(self): return _nullable(self, "cna_song_get_genre", Genre)
    @property
    def Duration(self): return _ticks(self, "cna_song_get_duration")
    @property
    def IsProtected(self): return _bool(self, "cna_song_get_is_protected")
    @property
    def IsRated(self): return _bool(self, "cna_song_get_is_rated")
    @property
    def PlayCount(self): return _int(self, "cna_song_get_play_count")
    @property
    def Rating(self): return _int(self, "cna_song_get_rating")
    @property
    def TrackNumber(self): return _int(self, "cna_song_get_track_number")


class Picture(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "picture", "cna_picture_destroy", "cna_picture_equals"
    @property
    def Album(self): return _nullable(self, "cna_picture_get_album", PictureAlbum)
    @property
    def Date(self):
        ticks = _raw_int(self, "cna_picture_get_date_unix_ticks", c.c_int64)
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks / 10)
    @property
    def Width(self): return _int(self, "cna_picture_get_width")
    @property
    def Height(self): return _int(self, "cna_picture_get_height")
    def GetImage(self): return BytesIO(_buffer(self, "cna_picture_get_image"))
    def GetThumbnail(self): return BytesIO(_buffer(self, "cna_picture_get_thumbnail"))


class PictureAlbum(_CatalogObject):
    _stem, _destroy_symbol, _equals_symbol = "picture_album", "cna_picture_album_destroy", "cna_picture_album_equals"
    @property
    def Parent(self): return _nullable(self, "cna_picture_album_get_parent", PictureAlbum)
    @property
    def Albums(self): return _cached_collection(self, "Albums", "cna_picture_album_get_albums", PictureAlbumCollection)
    @property
    def Pictures(self): return _cached_collection(self, "Pictures", "cna_picture_album_get_pictures", PictureCollection)


def _raw_int(owner, operation, ctype):
    library, handle = owner._live_handle(operation)
    return int(_out(library, operation, handle, ctype))


def _int(owner, operation): return _raw_int(owner, operation, c.c_int32)
def _bool(owner, operation): return bool(_raw_int(owner, operation, c.c_uint8))
def _ticks(owner, operation): return timedelta(microseconds=_raw_int(owner, operation, c.c_int64) / 10)


def _buffer(owner, stem):
    library, handle = owner._live_handle(stem)
    return _copy_bytes(library, handle, stem)


def _cached_collection(owner, key, operation, cls):
    current = owner._properties.get(key)
    if current is not None:
        return current
    library, handle = owner._live_handle(operation)
    output = c.c_uint64()
    library.check(getattr(library, operation)(handle, c.byref(output)), operation)
    result = object.__new__(cls)
    result._init_handle(int(output.value), owner._generation, owner._domain)
    owner._properties[key] = result
    return result


class SongCollection(_Collection): pass
class AlbumCollection(_Collection): pass
class ArtistCollection(_Collection): pass
class GenreCollection(_Collection): pass
class PlaylistCollection(_Collection): pass
class PictureCollection(_Collection): pass
class PictureAlbumCollection(_Collection): pass


for _collection, _stem, _item in (
    (SongCollection, "song_collection", Song),
    (AlbumCollection, "album_collection", Album),
    (ArtistCollection, "artist_collection", Artist),
    (GenreCollection, "genre_collection", Genre),
    (PlaylistCollection, "playlist_collection", Playlist),
    (PictureCollection, "picture_collection", Picture),
    (PictureAlbumCollection, "picture_album_collection", PictureAlbum),
):
    _collection._stem = _stem
    _collection._destroy_symbol = f"cna_{_stem}_destroy"
    _collection._item_type = _item
    for _name in ("Dispose", "GetEnumerator", "IsDisposed", "Count", "__getitem__",
                  "__iter__", "__len__", "__enter__", "__exit__"):
        setattr(_collection, _name,
                _Collection.__dict__.get(_name, _NativeHandle.__dict__.get(_name)))


for _object in (Album, Artist, Genre, Playlist, Song, Picture, PictureAlbum):
    for _name in ("Dispose", "Equals", "ToString", "GetHashCode", "IsDisposed", "Name",
                  "__eq__", "__ne__", "__hash__", "__str__", "__enter__", "__exit__"):
        setattr(_object, _name,
                _CatalogObject.__dict__.get(_name, _NativeHandle.__dict__.get(_name)))


_MISSING = object()


class MediaLibrary(_NativeHandle):
    _destroy_symbol = "cna_media_library_destroy"

    def __init__(self, mediaSource=_MISSING) -> None:
        _game, _host, library, game_handle, generation = _active("MediaLibrary.__init__")
        output = c.c_uint64()
        if mediaSource is _MISSING:
            result = library.cna_media_library_create(game_handle, c.byref(output))
            operation = "cna_media_library_create"
        else:
            if not isinstance(mediaSource, MediaSource):
                raise TypeError("mediaSource must be MediaSource")
            mediaSource._live()
            result = library.cna_media_library_create_from_source(
                game_handle, int(mediaSource.MediaSourceType), c.byref(output))
            operation = "cna_media_library_create_from_source"
        library.check(result, operation)
        self._init_handle(int(output.value), generation, _IdentityDomain())

    def Dispose(self) -> None:
        library, handle = self._live_handle("MediaLibrary.Dispose")
        library.check(library.cna_media_library_dispose(handle), "cna_media_library_dispose")

    @property
    def IsDisposed(self) -> bool:
        library, handle = self._live_handle("MediaLibrary.IsDisposed")
        return bool(_out(library, "cna_media_library_get_is_disposed", handle, c.c_uint8))

    @property
    def MediaSource(self) -> MediaSource:
        current = self._properties.get("MediaSource")
        if current is not None:
            return current
        library, handle = self._live_handle("MediaLibrary.MediaSource")
        type_value = c.c_uint32()
        library.check(library.cna_media_library_get_media_source_type(handle, c.byref(type_value)),
                      "cna_media_library_get_media_source_type")
        size = c.c_uint64()
        library.check(library.cna_media_library_get_media_source_name_size(
            handle, c.byref(size)), "cna_media_library_get_media_source_name_size")
        output = c.create_string_buffer(size.value) if size.value else None
        written = c.c_uint64()
        if size.value:
            library.check(library.cna_media_library_copy_media_source_name(
                handle, output, size.value, c.byref(written)),
                "cna_media_library_copy_media_source_name")
            name = bytes(output.raw[:written.value]).decode("utf-8", errors="strict")
        else:
            name = ""
        key = (self._generation, name, int(type_value.value))
        source = _runtime.sources.get(key)
        if source is None:
            source = MediaSource(name, MediaSourceType(type_value.value), self._generation)
            _runtime.sources[key] = source
        self._properties["MediaSource"] = source
        return source

    def _collection(self, name, operation, cls):
        return _cached_collection(self, name, operation, cls)

    @property
    def Songs(self): return self._collection("Songs", "cna_media_library_get_songs", SongCollection)
    @property
    def Albums(self): return self._collection("Albums", "cna_media_library_get_albums", AlbumCollection)
    @property
    def Artists(self): return self._collection("Artists", "cna_media_library_get_artists", ArtistCollection)
    @property
    def Genres(self): return self._collection("Genres", "cna_media_library_get_genres", GenreCollection)
    @property
    def Playlists(self): return self._collection("Playlists", "cna_media_library_get_playlists", PlaylistCollection)
    @property
    def Pictures(self): return self._collection("Pictures", "cna_media_library_get_pictures", PictureCollection)
    @property
    def SavedPictures(self): return self._collection("SavedPictures", "cna_media_library_get_saved_pictures", PictureCollection)

    @property
    def RootPictureAlbum(self):
        current = self._properties.get("RootPictureAlbum")
        if current is not None:
            return current
        value = _nullable(self, "cna_media_library_get_root_picture_album", PictureAlbum)
        if value is not None:
            self._properties["RootPictureAlbum"] = value
        return value

    def GetPictureFromToken(self, token: str):
        library, handle = self._live_handle("MediaLibrary.GetPictureFromToken")
        token_bytes, view = _string_view(token, "token")
        output, present = c.c_uint64(), c.c_uint8()
        library.check(library.cna_media_library_get_picture_from_token(
            handle, view, c.byref(output), c.byref(present)),
            "cna_media_library_get_picture_from_token")
        return _wrap(Picture, int(output.value), self._generation, self._domain) if present.value else None

    def SavePicture(self, name: str, data) -> None:
        library, handle = self._live_handle("MediaLibrary.SavePicture")
        name_bytes, view = _string_view(name, "name")
        if isinstance(data, (bytes, bytearray, memoryview)):
            payload = bytes(data)
        elif hasattr(data, "read"):
            payload = data.read()
            if not isinstance(payload, bytes):
                raise TypeError("stream.read() must return bytes")
        elif isinstance(data, Sequence) and not isinstance(data, str):
            try:
                payload = bytes(data)
            except (TypeError, ValueError) as error:
                raise ValueError("data elements must be Byte values") from error
        else:
            raise TypeError("data must be a Byte sequence or a readable binary stream")
        buffer = (c.c_uint8 * len(payload)).from_buffer_copy(payload) if payload else None
        output = c.c_uint64()
        library.check(library.cna_media_library_save_picture(
            handle, view, buffer, len(payload), c.byref(output)), "cna_media_library_save_picture")
        # SavePicture is void in XNA. Destroy the result handle after admitting it
        # into no public identity graph; SavedPictures will enumerate its own view.
        if output.value:
            library.check(library.cna_picture_destroy(output.value), "cna_picture_destroy")


VisualizationData.__xna_arities__ = {"__init__": {0}}
MediaSource.__xna_arities__ = {"GetAvailableMediaSources": {0}, "ToString": {0}}
Song.__xna_arities__ = {"FromUri": {2}, "Dispose": {0}}
MediaLibrary.__xna_arities__ = {"__init__": {0, 1}, "SavePicture": {2},
                                "GetPictureFromToken": {1}, "Dispose": {0}}
for _value in (Album, Artist, Genre, Playlist, Picture, PictureAlbum):
    _value.__xna_arities__ = {"Dispose": {0}, "Equals": {1}, "ToString": {0},
                              "GetHashCode": {0}}
for _value in (SongCollection, AlbumCollection, ArtistCollection, GenreCollection,
               PlaylistCollection, PictureCollection, PictureAlbumCollection):
    _value.__xna_arities__ = {"Dispose": {0}, "GetEnumerator": {0}, "__getitem__": {1}}
