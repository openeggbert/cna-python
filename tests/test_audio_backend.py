"""Audio requalified against a real mixer rather than a null backend.

These run in a subprocess with ``SDL_AUDIODRIVER=dummy``. That is a deliberate
choice on both counts: it is a real backend that runs the whole mixer and state
machine, so the results are not a null backend's silence, and it never opens the
machine's sound device, so a test run cannot interrupt whatever the user is
listening to. Setting it in-process would be too late and would leak into the
rest of the suite, hence the subprocess.

What this proves and what it does not:

* ``REAL_AUDIO_STATE_MACHINE`` -- transitions, callbacks, capture plumbing and a
  decoded visualization signal all execute for real.
* It is **not** audible-output evidence: the dummy device produces no sound.
* It is **not** physical-capture evidence: the captured buffer is real but the
  device supplies silence, so a non-zero sample would have to come from hardware.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
LIBRARY = os.environ.get("CNA_NATIVE_LIBRARY")


def _run(script: str) -> dict:
    environment = dict(os.environ)
    environment["SDL_AUDIODRIVER"] = "dummy"
    environment["PYTHONPATH"] = str(SOURCE) + os.pathsep + environment.get("PYTHONPATH", "")
    environment.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env=environment, timeout=300)
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith("RESULT "):
            _, key, value = line.split(" ", 2)
            values[key] = value
    if not values:
        raise AssertionError(f"probe produced no results\nstdout:\n{result.stdout}\n"
                             f"stderr:\n{result.stderr}")
    return values


_STATE_MACHINE = r'''
import math, struct
from Microsoft.Xna.Framework import Game, Color, GraphicsDeviceManager
from Microsoft.Xna.Framework.Audio import (
    SoundEffect, AudioChannels, DynamicSoundEffectInstance, Microphone)

def tone(rate=8000, frames=4000, freq=440.0):
    return b"".join(struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / rate)))
                    for i in range(frames))

out = {}
class Probe(Game):
    def __init__(self):
        super().__init__(); self.manager = GraphicsDeviceManager(self)
        self.n = 0; self.needed = []
    def Update(self, gameTime):
        self.n += 1
        if self.n == 1:
            self.effect = SoundEffect(tone(), 8000, AudioChannels.Mono)
            self.instance = self.effect.CreateInstance()
            out["before"] = int(self.instance.State)
            self.instance.Play();   out["playing"] = int(self.instance.State)
            self.instance.Pause();  out["paused"] = int(self.instance.State)
            self.instance.Resume(); out["resumed"] = int(self.instance.State)
            self.dynamic = DynamicSoundEffectInstance(8000, AudioChannels.Mono)
            self.dynamic.BufferNeeded += lambda s, a: self.needed.append(1)
            self.dynamic.SubmitBuffer(tone(frames=800))
            out["pending"] = self.dynamic.PendingBufferCount
            self.dynamic.Play()
        if self.n >= 30:
            out["buffer_needed"] = len(self.needed)
            self.instance.Stop(); out["stopped"] = int(self.instance.State)
            self.dynamic.Dispose(); self.instance.Dispose(); self.effect.Dispose()
            self.Exit()
    def Draw(self, gameTime):
        self.GraphicsDevice.Clear(Color.Black)

game = Probe()
try: game.Run()
finally: game.Dispose()
for key, value in out.items(): print("RESULT", key, value)
'''

_MICROPHONE = r'''
from datetime import timedelta
from Microsoft.Xna.Framework import Game, Color, GraphicsDeviceManager
from Microsoft.Xna.Framework.Audio import Microphone

out = {}
class Probe(Game):
    def __init__(self):
        super().__init__(); self.manager = GraphicsDeviceManager(self)
        self.n = 0; self.mic = None
    def Update(self, gameTime):
        self.n += 1
        if self.n == 1:
            devices = Microphone.All
            out["count"] = len(devices)
            if len(devices) == 0:
                self.Exit(); return
            self.mic = devices[0]
            out["rate"] = self.mic.SampleRate
            out["initial_state"] = int(self.mic.State)
            self.mic.BufferDuration = timedelta(milliseconds=200)
            out["buffer_ms"] = int(self.mic.BufferDuration.total_seconds() * 1000)
            try:
                self.mic.BufferDuration = timedelta(milliseconds=10)
                out["too_small_refused"] = 0
            except Exception:
                out["too_small_refused"] = 1
            out["sample_size"] = self.mic.GetSampleSizeInBytes(timedelta(milliseconds=200))
            self.mic.Start(); out["started_state"] = int(self.mic.State)
        if self.n == 12 and self.mic is not None:
            buffer = bytearray(self.mic.GetSampleSizeInBytes(timedelta(milliseconds=200)))
            out["captured_bytes"] = self.mic.GetData(buffer)
            out["captured_nonzero"] = 1 if any(buffer) else 0
            self.mic.Stop(); out["stopped_state"] = int(self.mic.State)
            self.Exit()
        elif self.n > 40:
            self.Exit()
    def Draw(self, gameTime):
        self.GraphicsDevice.Clear(Color.Black)

game = Probe()
try: game.Run()
finally: game.Dispose()
for key, value in out.items(): print("RESULT", key, value)
'''

_VISUALIZATION = r'''
import math, struct, tempfile
from Microsoft.Xna.Framework import Game, Color, GraphicsDeviceManager
from Microsoft.Xna.Framework.Media import MediaPlayer, Song, VisualizationData

def wav(rate=44100, seconds=2, freq=440.0):
    frames = rate * seconds
    pcm = b"".join(struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / rate)))
                   for i in range(frames))
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks

out = {}
class Probe(Game):
    def __init__(self, path):
        super().__init__(); self.manager = GraphicsDeviceManager(self)
        self.n = 0; self.path = path
    def Update(self, gameTime):
        self.n += 1
        if self.n == 1:
            out["visualization_default"] = 1 if MediaPlayer.IsVisualizationEnabled else 0
            MediaPlayer.IsVisualizationEnabled = True
            self.song = Song.FromUri("tone", self.path)
            MediaPlayer.Play(self.song)
            out["state"] = int(MediaPlayer.State)
        if self.n == 25:
            data = VisualizationData()
            MediaPlayer.GetVisualizationData(data)
            out["frequency_peak"] = 1 if max(data.Frequencies) > 0.0 else 0
            out["sample_peak"] = 1 if max(data.Samples) > 0.0 else 0
            out["sample_trough"] = 1 if min(data.Samples) < 0.0 else 0
            out["lengths"] = "%d/%d" % (len(data.Frequencies), len(data.Samples))
            MediaPlayer.Stop(); self.song.Dispose(); self.Exit()
        elif self.n > 60:
            self.Exit()
    def Draw(self, gameTime):
        self.GraphicsDevice.Clear(Color.Black)

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
    handle.write(wav()); path = handle.name
game = Probe(path)
try: game.Run()
finally: game.Dispose()
for key, value in out.items(): print("RESULT", key, value)
'''


@unittest.skipUnless(LIBRARY and Path(LIBRARY).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class RealAudioBackendTests(unittest.TestCase):
    def test_sound_effect_instance_runs_the_real_state_machine(self) -> None:
        values = _run(_STATE_MACHINE)
        # SoundState: Playing=0, Paused=1, Stopped=2.
        self.assertEqual(values["before"], "2")
        self.assertEqual(values["playing"], "0")
        self.assertEqual(values["paused"], "1")
        self.assertEqual(values["resumed"], "0")
        self.assertEqual(values["stopped"], "2")

    def test_dynamic_instance_consumes_buffers_and_asks_for_more(self) -> None:
        values = _run(_STATE_MACHINE)
        self.assertEqual(values["pending"], "1")
        # A null backend never drains a queue, so it never asks for another buffer.
        self.assertGreater(int(values["buffer_needed"]), 0)

    def test_microphone_capture_plumbing_is_real_and_its_signal_is_not_claimed(self) -> None:
        values = _run(_MICROPHONE)
        if values.get("count") == "0":
            self.skipTest("the audio backend enumerated no capture device")
        # MicrophoneState: Started=0, Stopped=1.
        self.assertEqual(values["initial_state"], "1")
        self.assertEqual(values["started_state"], "0")
        self.assertEqual(values["stopped_state"], "1")
        self.assertEqual(values["buffer_ms"], "200")
        self.assertEqual(values["too_small_refused"], "1")
        rate = int(values["rate"])
        # Two bytes per mono sample over 200 ms, checked against the reported rate
        # rather than against the routine that computed it.
        self.assertEqual(int(values["sample_size"]), rate // 5 * 2)
        self.assertGreater(int(values["captured_bytes"]), 0)
        # The bytes are real; the silence in them is the device's, and a non-zero
        # sample would be physical-capture evidence this backend cannot give.
        self.assertEqual(values["captured_nonzero"], "0")

    def test_visualization_reports_a_decoded_signal(self) -> None:
        values = _run(_VISUALIZATION)
        self.assertEqual(values["visualization_default"], "0")
        self.assertEqual(values["state"], "1")
        self.assertEqual(values["lengths"], "256/256")
        # A tone is playing, so the spectrum and the waveform must both be alive.
        self.assertEqual(values["frequency_peak"], "1")
        self.assertEqual(values["sample_peak"], "1")
        self.assertEqual(values["sample_trough"], "1")


if __name__ == "__main__":
    unittest.main()
