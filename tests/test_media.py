from __future__ import annotations

import math
import os
from pathlib import Path
import struct
import tempfile
import unittest

from _cna_native.errors import NativeError
from Microsoft.Xna.Framework import Game, GraphicsDeviceManager
from Microsoft.Xna.Framework.Content import ContentLoadException, ResourceContentManager
from Microsoft.Xna.Framework.Media import (
    MediaLibrary, MediaPlayer, MediaSource, MediaSourceType, MediaState, Song,
    VideoPlayer, VideoSoundtrackType, VisualizationData,
)

from .test_content import _compressed_xnb, _seven, _text, _xnb


NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
PREFIX = "Microsoft.Xna.Framework.Content."


def _legal_wav_bytes() -> bytes:
    samples = bytes(160 * 2)  # 20 ms of authored mono PCM silence at 8 kHz.
    return (b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8_000, 16_000, 2, 16)
            + b"data" + struct.pack("<I", len(samples)) + samples)


def _video_xnb(*, broken_shared: bool = False) -> bytes:
    readers = [
        (PREFIX + "VideoReader, Microsoft.Xna.Framework.Video", 0),
        (PREFIX + "StringReader, Microsoft.Xna.Framework", 0),
        (PREFIX + "Int32Reader, Microsoft.Xna.Framework", 0),
        (PREFIX + "SingleReader, Microsoft.Xna.Framework", 0),
    ]
    body = bytearray(_seven(1))
    body.extend(_seven(2) + _text("authored-video.ogv"))
    body.extend(_seven(3) + struct.pack("<i", 1500))
    body.extend(_seven(3) + struct.pack("<i", 320))
    body.extend(_seven(3) + struct.pack("<i", 180))
    body.extend(_seven(4) + struct.pack("<f", 24.0))
    body.extend(_seven(3) + struct.pack("<i", 2))
    if broken_shared:
        body.extend(_seven(99))
    return _xnb(readers, bytes(body), 1 if broken_shared else 0)


class MediaValueTests(unittest.TestCase):
    def test_enums_and_visualization_are_exact_readonly_values(self) -> None:
        self.assertEqual(tuple(map(int, MediaState)), (0, 1, 2))
        self.assertEqual(tuple(map(int, MediaSourceType)), (0, 4))
        self.assertEqual(tuple(map(int, VideoSoundtrackType)), (0, 1, 2))
        value = VisualizationData()
        self.assertEqual((len(value.Frequencies), len(value.Samples)), (256, 256))
        self.assertIs(value.Frequencies, value.Frequencies)
        self.assertIs(value.Samples, value.Samples)
        self.assertTrue(all(item == 0.0 for item in value.Frequencies + value.Samples))
        with self.assertRaises(TypeError):
            value.Frequencies[0] = 1.0


@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class MediaNativeTests(unittest.TestCase):
    def test_library_source_graph_collection_identity_and_dispose(self) -> None:
        case = self
        observations = {}
        class LibraryGame(Game):
            def LoadContent(self):
                sources = MediaSource.GetAvailableMediaSources()
                library = MediaLibrary(sources[0])
                pictures = library.Pictures
                songs = library.Songs
                with case.assertRaises(ValueError):
                    MediaPlayer.Play(songs)
                songs.Dispose()
                with case.assertRaises(RuntimeError):
                    MediaPlayer.Play(songs)
                observations["source"] = (sources[0] is library.MediaSource,
                                          library.MediaSource.Name,
                                          library.MediaSource.MediaSourceType)
                observations["collections"] = (
                    songs.Count, library.Albums.Count, library.Artists.Count,
                    library.Genres.Count, library.Playlists.Count,
                    pictures is library.Pictures,
                )
                with case.assertRaises(IndexError):
                    _ = pictures[-1]
                with case.assertRaises(IndexError):
                    _ = pictures[pictures.Count]
                if pictures.Count:
                    picture = pictures[0]
                    observations["picture"] = (
                        picture is pictures[0], picture.Name, picture.Width > 0,
                        picture.Height > 0, picture.Album.Pictures[0] is picture,
                    )
                    picture.Dispose()
                    observations["picture_disposed"] = (picture.IsDisposed, bool(picture.Name))
                pictures.Dispose()
                observations["collection_disposed"] = (pictures.IsDisposed, pictures.Count)
                library.Dispose()
                observations["library_disposed"] = (library.IsDisposed,
                                                       library.RootPictureAlbum.Name)
            def Update(self, gameTime): self.Exit()
        game = LibraryGame()
        game.Run()
        game.Dispose()
        self.assertEqual(observations["source"][0], True)
        self.assertEqual(observations["source"][2], MediaSourceType.LocalDevice)
        self.assertEqual(observations["collections"][:5], (0, 0, 0, 0, 0))
        self.assertTrue(observations["collections"][5])
        if "picture" in observations:
            self.assertEqual(observations["picture"][0], True)
            self.assertEqual(observations["picture"][2:], (True, True, True))
            self.assertEqual(observations["picture_disposed"], (True, True))
        self.assertEqual(observations["collection_disposed"], (True, 0))
        self.assertEqual(observations["library_disposed"][0], True)

    def test_song_player_queue_events_and_game_generation(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav") as fixture:
            fixture.write(_legal_wav_bytes())
            fixture.flush()
            case = self
            events, retained = [], {}
            def active(sender, args): events.append("active")
            def state(sender, args): events.append("state")
            class First(Game):
                def LoadContent(self):
                    MediaPlayer.ActiveSongChanged += active
                    MediaPlayer.MediaStateChanged += state
                    with case.assertRaises(NativeError):
                        Song.FromUri("Missing", fixture.name + ".missing")
                    with case.assertRaises(NativeError):
                        Song.FromUri("Remote", "https://example.invalid/song.wav")
                    song = Song.FromUri("Authored", fixture.name)
                    case.assertEqual(song.Name, "Authored")
                    case.assertEqual(song.Duration, song.Duration)
                    case.assertEqual((song.Artist, song.Album, song.Genre),
                                     (None, None, None))
                    case.assertEqual((song.IsProtected, song.IsRated, song.PlayCount,
                                      song.Rating, song.TrackNumber),
                                     (False, False, 0, 0, 0))
                    disposed = Song.FromUri("Disposed", fixture.name)
                    disposed.Dispose()
                    with case.assertRaises(RuntimeError):
                        MediaPlayer.Play(disposed)
                    MediaPlayer.IsMuted = True
                    MediaPlayer.IsRepeating = True
                    MediaPlayer.IsShuffled = False
                    MediaPlayer.Volume = float("-inf")
                    case.assertEqual(MediaPlayer.Volume, 0.0)
                    MediaPlayer.Volume = float("inf")
                    case.assertEqual(MediaPlayer.Volume, 1.0)
                    MediaPlayer.Volume = float("nan")
                    case.assertTrue(math.isnan(MediaPlayer.Volume))
                    MediaPlayer.Volume = -0.0
                    MediaPlayer.Play(song)
                    visualization = VisualizationData()
                    MediaPlayer.GetVisualizationData(visualization)
                    case.assertEqual((len(visualization.Frequencies),
                                      len(visualization.Samples)), (256, 256))
                    queue = MediaPlayer.Queue
                    retained.update(song=song, queue=queue)
                    case.assertEqual((queue.Count, queue.ActiveSongIndex), (1, 0))
                    case.assertIs(queue[0], song)
                    case.assertIs(queue.ActiveSong, song)
                def Draw(self, gameTime): self.Exit()
            first = First()
            try:
                first.Run()
            finally:
                first.Dispose()
            self.assertEqual(events, ["active", "state"])
            with self.assertRaises(RuntimeError):
                _ = retained["queue"].Count
            class Second(Game):
                def LoadContent(self):
                    case.assertTrue(MediaPlayer.IsMuted)
                    case.assertTrue(MediaPlayer.IsRepeating)
                    case.assertLess(math.copysign(1.0, MediaPlayer.Volume), 0.0)
                    case.assertIsNot(MediaPlayer.Queue, retained["queue"])
                    with case.assertRaises(RuntimeError):
                        MediaPlayer.Play(retained["song"])
                def Update(self, gameTime): self.Exit()
            second = Second()
            try:
                second.Run()
            finally:
                second.Dispose()
            MediaPlayer.ActiveSongChanged -= active
            MediaPlayer.MediaStateChanged -= state

    def test_video_xnb_cache_rollback_and_player_cached_disposed_properties(self) -> None:
        case = self
        observations = {}
        class VideoGame(Game):
            def __init__(self):
                super().__init__()
                GraphicsDeviceManager(self)
            def LoadContent(self):
                manager = ResourceContentManager(self.Services, {
                    "video": _video_xnb(), "video2": _video_xnb(),
                    "compressed": _compressed_xnb(_video_xnb()),
                    "broken": _video_xnb(broken_shared=True),
                })
                video = manager.Load("video")
                video2 = manager.Load("video2")
                compressed = manager.Load("compressed")
                observations["metadata"] = (
                    video is manager.Load("VIDEO"), video.Duration.total_seconds(),
                    video.Width, video.Height, video.FramesPerSecond,
                    video.VideoSoundtrackType,
                    compressed.Width,
                )
                player = VideoPlayer()
                player.IsLooped = True
                player.IsMuted = True
                with case.assertRaises(ValueError):
                    player.Volume = -0.01
                with case.assertRaises(ValueError):
                    player.Volume = 1.01
                with case.assertRaises(ValueError):
                    player.Volume = float("inf")
                player.Volume = float("nan")
                with case.assertRaises(RuntimeError):
                    player.GetTexture()
                player.Play(video)
                case.assertIs(player.Video, video)
                case.assertIsNone(player.GetTexture())
                player.Pause()
                player.Resume()
                player.Play(video2)
                case.assertIs(player.Video, video2)
                player.Stop()
                player.Dispose()
                observations["cached"] = (player.IsDisposed, player.IsLooped,
                                           player.IsMuted, math.isnan(player.Volume))
                with case.assertRaises(RuntimeError):
                    player.Stop()
                with case.assertRaises(RuntimeError):
                    player.IsMuted = False
                manager.Unload()
                case.assertIsNone(player.Video)
                with case.assertRaises(RuntimeError):
                    _ = video.Width
                with case.assertRaises(RuntimeError):
                    _ = compressed.Width
                with case.assertRaises(ContentLoadException):
                    manager.Load("broken")
                observations["rollback"] = manager._loaded_assets == {}
                manager.Dispose()
            def Update(self, gameTime): self.Exit()
        game = VideoGame()
        game.Run()
        game.Dispose()
        self.assertEqual(observations["metadata"],
                         (True, 1.5, 320, 180, 24.0,
                          VideoSoundtrackType.MusicAndDialog, 320))
        self.assertEqual(observations["cached"], (True, True, True, True))
        self.assertTrue(observations["rollback"])

    def test_media_event_snapshot_reentrancy_and_exception_containment(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav") as fixture:
            fixture.write(_legal_wav_bytes())
            fixture.flush()
            calls, holder = [], {}
            def late(sender, args): calls.append("late")
            def second(sender, args): calls.append("second")
            def first(sender, args):
                calls.append("first")
                MediaPlayer.ActiveSongChanged -= first
                MediaPlayer.ActiveSongChanged += late
                MediaPlayer.Stop()
                MediaPlayer.Play(holder["song"])
                host = holder["game"]._host
                host.library.check(
                    host.library.cna_media_player_raise_active_song_changed_ext(host.handle),
                    "cna_media_player_raise_active_song_changed_ext")
            class ReentrantGame(Game):
                def LoadContent(self):
                    holder["game"] = self
                    holder["song"] = Song.FromUri("event", fixture.name)
                    MediaPlayer.ActiveSongChanged += first
                    MediaPlayer.ActiveSongChanged += second
                    MediaPlayer.Play(holder["song"])
                def Draw(self, gameTime):
                    # Leave the CNA process-global player in a deterministic
                    # stopped state for the next independently asserted test.
                    MediaPlayer.Stop()
                    self.Exit()
            game = ReentrantGame()
            game.Run(); game.Dispose()
            MediaPlayer.ActiveSongChanged -= second
            MediaPlayer.ActiveSongChanged -= late
            self.assertEqual(calls[:2], ["first", "second"])
            self.assertGreaterEqual(calls.count("second"), 2)
            self.assertGreaterEqual(calls.count("late"), 1)

            failures = []
            def boom(sender, args):
                failures.append("boom")
                raise ValueError("media-handler")
            def later(sender, args): failures.append("later")
            class ExceptionGame(Game):
                def LoadContent(self):
                    MediaPlayer.ActiveSongChanged += boom
                    MediaPlayer.ActiveSongChanged += later
                    self._host.library.check(
                        self._host.library.cna_media_player_raise_active_song_changed_ext(
                            self._host.handle),
                        "cna_media_player_raise_active_song_changed_ext")
                def Draw(self, gameTime): self.Exit()
            game = ExceptionGame()
            with self.assertRaisesRegex(ValueError, "media-handler"):
                game.Run()
            MediaPlayer.ActiveSongChanged -= boom
            MediaPlayer.ActiveSongChanged -= later
            game.Dispose()
            self.assertEqual(failures, ["boom"])


if __name__ == "__main__":
    unittest.main()
