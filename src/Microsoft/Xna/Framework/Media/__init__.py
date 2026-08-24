"""Microsoft.Xna.Framework.Media selected XNA 4.0 projection."""

from ._catalog import (
    Album, AlbumCollection, Artist, ArtistCollection, Genre, GenreCollection,
    MediaLibrary, MediaSource, MediaSourceType, MediaState, Picture, PictureAlbum,
    PictureAlbumCollection, PictureCollection, Playlist, PlaylistCollection, Song,
    SongCollection, VideoSoundtrackType, VisualizationData,
)
from ._player import MediaPlayer, MediaQueue
from ._video import Video, VideoPlayer

__all__ = [
    "Album", "AlbumCollection", "Artist", "ArtistCollection", "Genre",
    "GenreCollection", "MediaLibrary", "MediaPlayer", "MediaQueue", "MediaSource",
    "MediaSourceType", "MediaState", "Picture", "PictureAlbum",
    "PictureAlbumCollection", "PictureCollection", "Playlist", "PlaylistCollection",
    "Song", "SongCollection", "Video", "VideoPlayer", "VideoSoundtrackType",
    "VisualizationData",
]
