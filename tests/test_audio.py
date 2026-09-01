from __future__ import annotations

from datetime import timedelta
import io
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest

from _cna_native.errors import NativeCapabilityError, NativeError
from Microsoft.Xna.Framework import Game, Vector3
from Microsoft.Xna.Framework.Audio import (
    AudioCategory, AudioChannels, AudioEmitter, AudioEngine, AudioListener,
    AudioStopOptions, DynamicSoundEffectInstance, InstancePlayLimitException,
    Microphone, MicrophoneState, NoAudioHardwareException,
    NoMicrophoneConnectedException, RendererDetail, SoundEffect,
    SoundEffectInstance, SoundState,
)


NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")


def wav_pcm16(sample_rate: int = 8_000, channels: int = 1,
              frames: int = 800, *, junk: bool = False) -> bytes:
    pcm = bytes(frames * channels * 2)
    block_align = channels * 2
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate,
                      sample_rate * block_align, block_align, 16)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if junk:
        chunks += b"JUNK" + struct.pack("<I", 3) + b"CNA" + b"\0"
    chunks += b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


class AudioValueTests(unittest.TestCase):
    def test_enum_identities(self) -> None:
        self.assertEqual((int(AudioChannels.Mono), int(AudioChannels.Stereo)), (1, 2))
        self.assertEqual((int(AudioStopOptions.AsAuthored), int(AudioStopOptions.Immediate)), (0, 1))
        self.assertEqual(tuple(map(int, SoundState)), (0, 1, 2))
        self.assertEqual(tuple(map(int, MicrophoneState)), (0, 1))

    def test_listener_emitter_defaults_and_vector_copy_boundaries(self) -> None:
        listener = AudioListener()
        self.assertEqual(listener.Position, Vector3.Zero)
        self.assertEqual(listener.Velocity, Vector3.Zero)
        self.assertEqual(listener.Forward, Vector3.Forward)
        self.assertEqual(listener.Up, Vector3.Up)
        value = Vector3(1, 2, 3)
        listener.Position = value
        value.X = 9
        self.assertEqual(listener.Position, Vector3(1, 2, 3))
        returned = listener.Position
        returned.Y = 8
        self.assertEqual(listener.Position, Vector3(1, 2, 3))
        emitter = AudioEmitter()
        self.assertEqual(emitter.DopplerScale, 1.0)
        emitter.DopplerScale = math.nan
        self.assertTrue(math.isnan(emitter.DopplerScale))
        with self.assertRaises(ValueError): emitter.DopplerScale = -0.01

    def test_sound_effect_sample_arithmetic_preserves_xna_single_order(self) -> None:
        self.assertEqual(SoundEffect.GetSampleDuration(0, 8_000, AudioChannels.Mono), timedelta(0))
        self.assertEqual(SoundEffect.GetSampleDuration(10, 8_000, AudioChannels.Mono),
                         timedelta(milliseconds=1))
        self.assertEqual(SoundEffect.GetSampleDuration(88_200, 44_100, AudioChannels.Mono),
                         timedelta(seconds=1))
        self.assertEqual(SoundEffect.GetSampleDuration(176_400, 44_100, AudioChannels.Stereo),
                         timedelta(seconds=1))
        self.assertEqual(SoundEffect.GetSampleDuration(3, 44_100, AudioChannels.Mono),
                         timedelta(0))
        # XNA's binary32 rate/1000 step deliberately produces 88,198 here.
        self.assertEqual(SoundEffect.GetSampleSizeInBytes(
            timedelta(seconds=1), 44_100, AudioChannels.Mono), 88_198)
        self.assertEqual(SoundEffect.GetSampleSizeInBytes(
            timedelta(seconds=1), 44_100, AudioChannels.Stereo), 176_400)
        self.assertEqual(SoundEffect.GetSampleSizeInBytes(
            timedelta(microseconds=1), 8_000, AudioChannels.Mono), 0)
        self.assertEqual(SoundEffect.GetSampleSizeInBytes(
            timedelta(milliseconds=1), 44_100, AudioChannels.Stereo), 176)
        with self.assertRaises(ValueError):
            SoundEffect.GetSampleDuration(-1, 8_000, AudioChannels.Mono)
        with self.assertRaises(ValueError):
            SoundEffect.GetSampleDuration(2, 7_999, AudioChannels.Mono)
        with self.assertRaises(TypeError):
            SoundEffect.GetSampleDuration(2, 8_000, 1)
        with self.assertRaises(ValueError):
            SoundEffect.GetSampleSizeInBytes(timedelta(microseconds=-1), 8_000, AudioChannels.Mono)
        with self.assertRaises(ValueError):
            SoundEffect.GetSampleSizeInBytes(
                timedelta(microseconds=922_337_203_685_477_580),
                48_000, AudioChannels.Stereo)
        with self.assertRaises(OverflowError):
            SoundEffect.GetSampleSizeInBytes(timedelta.max, 48_000, AudioChannels.Stereo)

    def test_sound_effect_constructor_validation_order_and_pcm_alignment(self) -> None:
        # These fail before the native/Game boundary and pin XNA's format-first
        # ordering for the seven-argument overload.
        with self.assertRaises(ValueError):
            SoundEffect(None, 0, 0, 7_999, AudioChannels.Mono, 0, 0)
        with self.assertRaises(TypeError):
            SoundEffect(None, 0, 0, 44_100, 0, 0, 0)
        with self.assertRaises(ValueError):
            SoundEffect(bytes(3), 0, 2, 44_100, AudioChannels.Mono, 0, 0)
        with self.assertRaises(ValueError):
            SoundEffect(bytes(16), 1, 2, 44_100, AudioChannels.Mono, 0, 0)
        with self.assertRaises(ValueError):
            SoundEffect(bytes(16), 0, 3, 44_100, AudioChannels.Mono, 0, 0)
        with self.assertRaises(ValueError):
            SoundEffect(bytes(16), 0, 16, 44_100, AudioChannels.Mono, 7, 2)

    def test_xna_audio_exception_projection(self) -> None:
        inner = ValueError("inner")
        for exception in (InstancePlayLimitException, NoAudioHardwareException,
                          NoMicrophoneConnectedException):
            self.assertIsInstance(exception(), Exception)
            self.assertEqual(str(exception("message")), "message")
            value = exception("outer", inner)
            self.assertIs(value.__cause__, inner)
            with self.assertRaises(TypeError): exception("a", inner, inner)

    def test_renderer_and_category_default_values(self) -> None:
        detail = RendererDetail()
        self.assertEqual((detail.FriendlyName, detail.RendererId, detail.GetHashCode()), (None, None, 0))
        self.assertEqual(detail, detail.__copy__())
        self.assertEqual(detail.ToString(), "Microsoft.Xna.Framework.Audio.RendererDetail")
        category = AudioCategory()
        self.assertEqual(category.ToString(), "")
        self.assertEqual(category, AudioCategory())
        self.assertEqual(category.GetHashCode(), 0)
        with self.assertRaises(RuntimeError): category.Pause()

    def test_wav_parser_rejects_truncation_encoding_and_malformed_fmt_before_native(self) -> None:
        samples = [b"not wave", wav_pcm16()[:-1]]
        encoded = bytearray(wav_pcm16()); encoded[20:22] = struct.pack("<H", 3); samples.append(bytes(encoded))
        malformed = bytearray(wav_pcm16()); malformed[32:34] = struct.pack("<H", 8); samples.append(bytes(malformed))
        for payload in samples:
            with self.subTest(length=len(payload)):
                with self.assertRaises(ValueError): SoundEffect.FromStream(io.BytesIO(payload))
        with self.assertRaises(TypeError): SoundEffect.FromStream(io.StringIO("text"))
        class BrokenStream:
            def read(self): raise OSError("stream sentinel")
        with self.assertRaisesRegex(OSError, "stream sentinel"):
            SoundEffect.FromStream(BrokenStream())


@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class AudioNativeTests(unittest.TestCase):
    def test_sound_effect_wav_instance_properties_3d_and_ownership(self) -> None:
        case = self
        class Probe(Game):
            def Update(self, gameTime):
                raw = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                encoded = SoundEffect.FromStream(io.BytesIO(wav_pcm16(junk=True)))
                stereo = SoundEffect.FromStream(io.BytesIO(
                    wav_pcm16(sample_rate=44_100, channels=2, frames=441)))
                high_rate = SoundEffect.FromStream(io.BytesIO(
                    wav_pcm16(sample_rate=48_000, channels=1, frames=480)))
                case.assertIsInstance(raw.Duration, timedelta)
                case.assertIsInstance(encoded.Duration, timedelta)
                raw.Name = "CNA π"
                case.assertEqual(raw.Name, "CNA π")
                case.assertIsInstance(raw.Play(), bool)
                case.assertIsInstance(raw.Play(0.5, -0.25, 0.25), bool)
                instance = raw.CreateInstance()
                case.assertIsInstance(instance, SoundEffectInstance)
                case.assertEqual((instance.Volume, instance.Pitch, instance.Pan,
                                  instance.IsLooped, instance.State),
                                 (1.0, 0.0, 0.0, False, SoundState.Stopped))
                instance.Volume = 0.5; instance.Pitch = -0.5; instance.Pan = -0.0
                instance.IsLooped = True
                instance.Apply3D(AudioListener(), AudioEmitter())
                # CNA accepts any positive listener count; the nearest listener decides.
                instance.Apply3D([AudioListener()], AudioEmitter())
                instance.Apply3D([AudioListener(), AudioListener()], AudioEmitter())
                with case.assertRaises(NativeCapabilityError) as caught:
                    instance.Apply3D([], AudioEmitter())
                case.assertEqual(caught.exception.result, 1)
                instance.Play(); instance.Play(); instance.Pause(); instance.Resume(); instance.Stop(False); instance.Stop()
                instance.Dispose(); instance.Dispose()
                case.assertEqual((instance.Volume, instance.Pitch, instance.IsLooped), (0.5, -0.5, True))
                case.assertLess(math.copysign(1.0, instance.Pan), 0.0)
                with case.assertRaises(RuntimeError): _ = instance.State
                with case.assertRaises(RuntimeError): instance.Play()
                with case.assertRaises(RuntimeError): setattr(instance, "Volume", 0.25)
                encoded.Dispose(); stereo.Dispose(); high_rate.Dispose()
                # Parent-first disposal walks all remaining owned children.
                child = raw.CreateInstance(); raw.Dispose(); raw.Dispose()
                case.assertTrue(child.IsDisposed); case.assertTrue(raw.IsDisposed)
                self.Exit()
        game = Probe()
        try: game.Run()
        finally: game.Dispose(); game.Dispose()

    def test_protected_dispose_false_still_releases_without_managed_finalizer(self) -> None:
        case = self
        class Probe(Game):
            def Update(self, gameTime):
                effect = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                instance = effect.CreateInstance()
                instance.Dispose(False)
                case.assertTrue(instance.IsDisposed)
                dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                dynamic.BufferNeeded += lambda sender, args: None
                dynamic.Dispose(False)
                case.assertTrue(dynamic.IsDisposed)
                effect.Dispose(); self.Exit()
        game = Probe()
        try: game.Run()
        finally: game.Dispose()

    def test_static_state_validation_and_microphone_enumeration(self) -> None:
        case = self
        class Probe(Game):
            def Update(self, gameTime):
                originals = (SoundEffect.MasterVolume, SoundEffect.DistanceScale,
                             SoundEffect.DopplerScale, SoundEffect.SpeedOfSound)
                SoundEffect.MasterVolume = 0.25
                SoundEffect.DistanceScale = 0.0
                SoundEffect.DopplerScale = 2.0
                SoundEffect.SpeedOfSound = 300.0
                case.assertEqual(SoundEffect.MasterVolume, 0.25)
                case.assertGreater(SoundEffect.DistanceScale, 0.0)
                with case.assertRaises(ValueError): SoundEffect.MasterVolume = math.nan
                with case.assertRaises(ValueError): SoundEffect.SpeedOfSound = 0.0
                with case.assertRaises(ValueError): SoundEffect.DopplerScale = -1.0
                SoundEffect.MasterVolume, SoundEffect.DistanceScale = originals[:2]
                SoundEffect.DopplerScale, SoundEffect.SpeedOfSound = originals[2:]
                # The enumerated set is whatever the qualified audio backend reports on
                # this host; the contract under test is identity, membership and defaulting,
                # never a host-specific device count.
                first = Microphone.All
                case.assertIs(first, Microphone.All)
                case.assertTrue(all(isinstance(value, Microphone) for value in first))
                default = Microphone.Default
                if len(first) == 0:
                    case.assertIsNone(default)
                else:
                    case.assertTrue(default is None or default in list(first))
                self.Exit()
        game = Probe()
        try: game.Run()
        finally: game.Dispose()

    def test_audio_static_state_is_process_global_across_game_recreation(self) -> None:
        case = self; original = []
        class First(Game):
            def Update(self, gameTime):
                original[:] = [SoundEffect.MasterVolume, SoundEffect.DistanceScale,
                               SoundEffect.DopplerScale, SoundEffect.SpeedOfSound]
                SoundEffect.MasterVolume = 0.375; SoundEffect.DistanceScale = 3.0
                SoundEffect.DopplerScale = 2.0; SoundEffect.SpeedOfSound = 250.0
                self.Exit()
        class Second(Game):
            def Update(self, gameTime):
                case.assertEqual((SoundEffect.MasterVolume, SoundEffect.DistanceScale,
                                  SoundEffect.DopplerScale, SoundEffect.SpeedOfSound),
                                 (0.375, 3.0, 2.0, 250.0))
                SoundEffect.MasterVolume, SoundEffect.DistanceScale = original[:2]
                SoundEffect.DopplerScale, SoundEffect.SpeedOfSound = original[2:]
                self.Exit()
        for game_type in (First, Second):
            game = game_type()
            try: game.Run()
            finally: game.Dispose()

    def test_dynamic_buffer_copy_callback_order_self_removal_and_disposal(self) -> None:
        case = self
        class Probe(Game):
            def __init__(self):
                super().__init__(); self.frame = 0; self.events = []
            def first(self, sender, args):
                self.events.append(("first", self.frame))
                self.dynamic.BufferNeeded -= self.first
                self.dynamic.SubmitBuffer(bytearray(1_600))
            def second(self, sender, args):
                self.events.append(("second", self.frame))
                if len(self.events) >= 2: self.dynamic.Dispose()
            def Update(self, gameTime):
                self.frame += 1
                if self.frame == 1:
                    validation = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                    for args in ((b"",), (bytes(3),), (bytes(320), -1, 2),
                                 (bytes(320), 0, 3), (bytes(320), 320, 2)):
                        with case.assertRaises(ValueError): validation.SubmitBuffer(*args)
                    repeated = bytearray(320)
                    validation.SubmitBuffer(repeated)
                    validation.SubmitBuffer(memoryview(repeated), 0, len(repeated))
                    case.assertEqual(validation.PendingBufferCount, 2)
                    validation.Dispose()
                    self.dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                    self.dynamic.BufferNeeded += self.first
                    self.dynamic.BufferNeeded += self.second
                    source = bytearray(1_600)
                    self.dynamic.SubmitBuffer(source)
                    source[:] = b"\xff" * len(source)
                    case.assertEqual(self.dynamic.PendingBufferCount, 1)
                    case.assertEqual(self.dynamic.GetSampleDuration(1_600), timedelta(milliseconds=100))
                    case.assertEqual(self.dynamic.GetSampleSizeInBytes(timedelta(milliseconds=100)), 1_600)
                    self.dynamic.Play()
                elif self.frame == 2:
                    case.assertEqual(self.events, [("first", 1), ("second", 1)])
                    case.assertTrue(self.dynamic.IsDisposed)
                    self.Exit()
        game = Probe()
        try: game.Run()
        finally: game.Dispose()

    def test_dynamic_callback_exception_is_contained_and_later_handlers_stop(self) -> None:
        case = self
        class Probe(Game):
            def __init__(self): super().__init__(); self.later = 0
            def throwing(self, sender, args): raise LookupError("audio callback sentinel")
            def later_handler(self, sender, args): self.later += 1
            def Update(self, gameTime):
                self.dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                self.dynamic.BufferNeeded += self.throwing
                self.dynamic.BufferNeeded += self.later_handler
                self.dynamic.SubmitBuffer(bytes(1_600)); self.dynamic.Play()
        game = Probe()
        try:
            with case.assertRaisesRegex(LookupError, "audio callback sentinel"): game.Run()
            case.assertEqual(game.later, 0)
        finally:
            game.Dispose()

    def test_throwing_game_update_skips_dispatcher_delivery(self) -> None:
        case = self
        class Probe(Game):
            def __init__(self): super().__init__(); self.events = 0
            def Initialize(self):
                self.dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                self.dynamic.BufferNeeded += self.needed
                self.dynamic.SubmitBuffer(bytes(1_600)); self.dynamic.Play()
            def needed(self, sender, args): self.events += 1
            def Update(self, gameTime): raise LookupError("update sentinel")
        game = Probe()
        try:
            with case.assertRaisesRegex(LookupError, "update sentinel"): game.Run()
            case.assertEqual(game.events, 0)
        finally:
            game.Dispose()

    def test_xact_real_constructor_and_error_routes_without_authored_fixture(self) -> None:
        case = self
        with tempfile.TemporaryDirectory(prefix="cna-python-xact-") as directory:
            root = Path(directory)
            malformed = root / "malformed.xgs"; malformed.write_bytes(b"bad")
            native_invalid = root / "native-invalid.xgs"; native_invalid.write_bytes(b"XGSF\0")
            class Probe(Game):
                def Update(self, gameTime):
                    with case.assertRaises(ValueError): AudioEngine(str(malformed))
                    for args in ((str(native_invalid),),
                                 (str(native_invalid), timedelta(milliseconds=250), "renderer")):
                        with case.assertRaises(NativeError) as caught: AudioEngine(*args)
                        case.assertIn(caught.exception.operation,
                                      ("cna_audio_engine_create", "cna_audio_engine_create_with_renderer"))
                    self.Exit()
            game = Probe()
            try: game.Run()
            finally: game.Dispose()


if __name__ == "__main__":
    unittest.main()
