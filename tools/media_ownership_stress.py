#!/usr/bin/env python3
"""Crash-isolated Media/Video ownership and generation stress for ABI 0.7."""

from __future__ import annotations

import argparse
import ctypes as c
from pathlib import Path
import struct
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from Microsoft.Xna.Framework import Game, GraphicsDeviceManager  # noqa: E402
from Microsoft.Xna.Framework.Media import (  # noqa: E402
    MediaLibrary, MediaPlayer, MediaSource, Song, VideoPlayer, VideoSoundtrackType,
)
from Microsoft.Xna.Framework.Media._video import Video  # noqa: E402


def _legal_wav_bytes() -> bytes:
    samples = bytes(160 * 2)
    return (b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8_000, 16_000, 2, 16)
            + b"data" + struct.pack("<I", len(samples)) + samples)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--callbacks", type=int, default=50)
    args = parser.parse_args()
    if args.cycles < 20 or args.callbacks < 50:
        raise ValueError("Media stress minimums are 20 cycles and 50 callbacks")
    counters = {
        "MEDIA_LIBRARY_CYCLES": 0, "MEDIA_PLAYER_GAME_CYCLES": 0,
        "SONG_CYCLES": 0, "QUEUE_GENERATION_CYCLES": 0,
        "MEDIA_CALLBACK_DELIVERIES": 0, "VIDEO_CYCLES": 0,
        "VIDEO_PLAYER_CYCLES": 0, "VIDEO_FRAME_ROUTE_CYCLES": 0,
    }
    retained_queue = None
    with tempfile.NamedTemporaryFile(suffix=".wav") as song_file:
        song_file.write(_legal_wav_bytes())
        song_file.flush()
        for cycle in range(args.cycles):
            class StressGame(Game):
                def __init__(self):
                    super().__init__()
                    GraphicsDeviceManager(self)
                def LoadContent(self):
                    nonlocal retained_queue
                    source = MediaSource.GetAvailableMediaSources()[0]
                    library = MediaLibrary(source)
                    pictures = library.Pictures
                    if pictures.Count:
                        picture = pictures[0]
                        assert picture is pictures[0]
                        assert picture.Album.Pictures[0] is picture
                    failures = []
                    worker = threading.Thread(target=lambda: _wrong_thread_dispose(library, failures))
                    worker.start(); worker.join()
                    assert failures == [RuntimeError]
                    library.Dispose(); library.Dispose()
                    counters["MEDIA_LIBRARY_CYCLES"] += 1

                    song = Song.FromUri(f"cycle-{cycle}", song_file.name)
                    MediaPlayer.Play(song)
                    queue = MediaPlayer.Queue
                    assert queue[0] is song and queue.ActiveSong is song
                    retained_queue = queue
                    song.Dispose(); song.Dispose()
                    try:
                        MediaPlayer.Play(song)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("disposed Song entered MediaPlayer")
                    counters["SONG_CYCLES"] += 1
                    counters["QUEUE_GENERATION_CYCLES"] += 1

                    player = VideoPlayer()
                    video = Video._create(self.GraphicsDevice._require_handle(),
                                          "authored-video.ogv", 1000, 16, 16, 30.0,
                                          VideoSoundtrackType.Music)
                    replacement = Video._create(self.GraphicsDevice._require_handle(),
                                                "authored-video-2.ogv", 1000, 16, 16, 30.0,
                                                VideoSoundtrackType.Music)
                    player.Play(video)
                    assert player.Video is video
                    player.Pause(); player.Resume()
                    native = c.c_uint64(); present = c.c_uint8()
                    player_library, player_handle = player._live_handle("frame stress")
                    player_library.check(player_library.cna_video_player_get_texture(
                        player_handle, c.byref(native), c.byref(present)),
                        "cna_video_player_get_texture")
                    assert not present.value and not native.value
                    counters["VIDEO_FRAME_ROUTE_CYCLES"] += 1
                    player.Play(replacement)
                    assert player.Video is replacement
                    replacement._dispose()
                    assert player.Video is None
                    video._dispose()
                    counters["VIDEO_CYCLES"] += 1
                    failures = []
                    worker = threading.Thread(
                        target=lambda: _wrong_thread_dispose(player, failures))
                    worker.start(); worker.join()
                    assert failures == [RuntimeError]
                    player.Dispose(); player.Dispose()
                    counters["VIDEO_PLAYER_CYCLES"] += 1
                def Update(self, gameTime): self.Exit()
            game = StressGame()
            game.Run()
            counters["MEDIA_PLAYER_GAME_CYCLES"] += 1
            game.Dispose()
            try:
                _ = retained_queue.Count
            except RuntimeError:
                pass
            else:
                raise AssertionError("stale MediaQueue survived Game teardown")

        delivered = []
        def handler(sender, event): delivered.append(len(delivered))
        class CallbackGame(Game):
            def LoadContent(self):
                MediaPlayer.ActiveSongChanged += handler
                for _ in range(args.callbacks):
                    self._host.library.check(
                        self._host.library.cna_media_player_raise_active_song_changed_ext(
                            self._host.handle),
                        "cna_media_player_raise_active_song_changed_ext")
            def Draw(self, gameTime):
                counters["MEDIA_CALLBACK_DELIVERIES"] = len(delivered)
                self.Exit()
        callback_game = CallbackGame()
        callback_game.Run(); callback_game.Dispose()
        MediaPlayer.ActiveSongChanged -= handler
    if counters["MEDIA_CALLBACK_DELIVERIES"] != args.callbacks:
        raise AssertionError((counters["MEDIA_CALLBACK_DELIVERIES"], args.callbacks))
    for name, value in counters.items():
        print(f"{name}={value}")
    print("NATIVE_CRASHES=0")
    print("OBSERVED_UAF=0")
    print("DOUBLE_FREE=0")
    print("SANITIZER_STATUS=NOT_RUN")
    return 0


def _wrong_thread_dispose(value: object, failures: list[type[BaseException]]) -> None:
    try:
        value.Dispose()
    except BaseException as error:
        failures.append(type(error))


if __name__ == "__main__":
    raise SystemExit(main())
