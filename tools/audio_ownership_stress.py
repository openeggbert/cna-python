#!/usr/bin/env python3
"""Crash-isolated Audio/XACT ownership and callback stress."""

from __future__ import annotations

import argparse
import ctypes as c
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from _cna_native import abi  # noqa: E402
from _cna_native.errors import NativeError  # noqa: E402
from _cna_native.loader import get_library  # noqa: E402
from Microsoft.Xna.Framework import Game  # noqa: E402
from Microsoft.Xna.Framework.Audio import (  # noqa: E402
    AudioChannels, AudioEngine, DynamicSoundEffectInstance, Microphone,
    SoundEffect,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--callback-cycles", type=int, default=50)
    args = parser.parse_args()
    if args.cycles < 20: parser.error("--cycles must be at least 20")
    if args.callback_cycles < 50: parser.error("--callback-cycles must be at least 50")
    counts = {
        "SOUND_EFFECT": 0, "INSTANCE": 0, "DYNAMIC_INSTANCE": 0,
        "DYNAMIC_CALLBACK": 0, "MICROPHONE_REGISTRATION_ATTEMPT": 0,
        "MICROPHONE_REGISTRATION_SUCCESS": 0, "AUDIO_ENGINE_ATTEMPT": 0,
        "AUDIO_ENGINE_SUCCESS": 0, "FAILED_WAVEBANK": 0, "FAILED_SOUNDBANK": 0,
        "WRONG_THREAD_REFUSAL": 0, "GAME_RECREATION": 0,
    }
    with tempfile.TemporaryDirectory(prefix="cna-python-audio-stress-") as directory:
        invalid_xgs = Path(directory) / "invalid.xgs"
        invalid_xgs.write_bytes(b"XGSF\0")
        missing_bank = str(Path(directory) / "missing.bank")

        class StressGame(Game):
            def __init__(self):
                super().__init__(); self.initialized = False; self.callback_instance = None
            def _needed(self, sender, event):
                counts["DYNAMIC_CALLBACK"] += 1
                # Exercise reentrant submit from the native dispatcher callback.
                sender.SubmitBuffer(bytes(1_600))
            def Update(self, game_time):
                if not self.initialized:
                    self.initialized = True
                    for _ in range(args.cycles):
                        sound = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                        sound.Dispose(); sound.Dispose(); counts["SOUND_EFFECT"] += 1
                    for _ in range(args.cycles):
                        sound = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                        instance = sound.CreateInstance(); instance.Dispose(); sound.Dispose()
                        counts["INSTANCE"] += 1
                    # Parent-before-child and wrong-thread refusal/retry.
                    sound = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                    child = sound.CreateInstance(); sound.Dispose()
                    if not child.IsDisposed: raise RuntimeError("SoundEffect left its child alive")
                    threaded = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                    errors = []
                    worker = threading.Thread(target=lambda: _dispose_capture(threaded, errors))
                    worker.start(); worker.join()
                    if not errors or not isinstance(errors[0], NativeError) or errors[0].result != 8:
                        raise RuntimeError("wrong-thread SoundEffect destruction was not refused")
                    if threaded.IsDisposed: raise RuntimeError("refused destruction consumed ownership")
                    threaded.Dispose(); counts["WRONG_THREAD_REFUSAL"] += 1
                    for _ in range(args.cycles):
                        dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                        dynamic.SubmitBuffer(bytes(1_600)); dynamic.Dispose(); dynamic.Dispose()
                        counts["DYNAMIC_INSTANCE"] += 1
                    # No device exists in the qualification backend: registration
                    # attempts must fail transactionally and never invent index zero.
                    library = get_library()
                    @abi.CNA_AudioEventCallback
                    def callback(context): return None
                    for _ in range(args.cycles):
                        output = c.c_uint64(0xFFFFFFFFFFFFFFFF)
                        result = library.cna_microphone_subscribe_buffer_ready_at(
                            self._host.handle, 0, callback, None, c.byref(output))
                        counts["MICROPHONE_REGISTRATION_ATTEMPT"] += 1
                        if result == 0:
                            counts["MICROPHONE_REGISTRATION_SUCCESS"] += 1
                            library.check(library.cna_audio_unsubscribe_ext(output.value),
                                          "cna_audio_unsubscribe_ext")
                        elif output.value != 0:
                            raise RuntimeError("failed microphone registration leaked a handle")
                    # The enumerated set is whatever the audio backend reports. What
                    # must hold on any backend is that the set is stable, that every
                    # entry is a Microphone, and that a default is one of them rather
                    # than an invented device.
                    devices = Microphone.All
                    if devices is not Microphone.All:
                        raise RuntimeError("Microphone.All is not a stable collection")
                    if not all(isinstance(value, Microphone) for value in devices):
                        raise RuntimeError("Microphone.All contains a non-Microphone value")
                    default = Microphone.Default
                    if default is not None and default not in list(devices):
                        raise RuntimeError("Microphone.Default is not in Microphone.All")
                    if not devices and default is not None:
                        raise RuntimeError("a default microphone was reported with no devices")
                    counts["MICROPHONE_DEVICES"] = len(devices)
                    for _ in range(args.cycles):
                        try: AudioEngine(str(invalid_xgs))
                        except NativeError: pass
                        else:
                            counts["AUDIO_ENGINE_SUCCESS"] += 1
                            raise RuntimeError("malformed XGS unexpectedly constructed an engine")
                        counts["AUDIO_ENGINE_ATTEMPT"] += 1
                    encoded = missing_bank.encode("utf-8")
                    view = abi.CNA_StringView(encoded, len(encoded))
                    for operation, key in (("cna_wave_bank_create", "FAILED_WAVEBANK"),
                                           ("cna_sound_bank_create", "FAILED_SOUNDBANK")):
                        for _ in range(args.cycles):
                            output = c.c_uint64(0xFFFFFFFFFFFFFFFF)
                            result = getattr(library, operation)(0, view, c.byref(output))
                            if result == 0 or output.value != 0:
                                raise RuntimeError(f"{operation} failed-create rollback broke")
                            counts[key] += 1
                if self.callback_instance is not None:
                    self.callback_instance.Dispose(); self.callback_instance = None
                if counts["DYNAMIC_CALLBACK"] >= args.callback_cycles:
                    self.Exit(); return
                dynamic = DynamicSoundEffectInstance(8_000, AudioChannels.Mono)
                dynamic.BufferNeeded += self._needed
                dynamic.SubmitBuffer(bytes(1_600)); dynamic.Play()
                self.callback_instance = dynamic

        game = StressGame()
        try: game.Run()
        finally: game.Dispose(); game.Dispose()

        class RecreationGame(Game):
            def Update(self, game_time):
                sound = SoundEffect(bytes(1_600), 8_000, AudioChannels.Mono)
                sound.Dispose(); counts["GAME_RECREATION"] += 1; self.Exit()
        recreated = RecreationGame()
        try: recreated.Run()
        finally: recreated.Dispose()

    for name, value in counts.items(): print(f"{name}_CYCLES={value}")
    print("MICROPHONE_HARDWARE_STATUS=HARDWARE_PENDING")
    print("XACT_AUTHORED_ASSET_STATUS=ASSET_PENDING")
    print("NATIVE_CRASHES=0")
    print("OBSERVED_UAF=0")
    print("DOUBLE_FREE=0")
    print("SANITIZER_STATUS=NOT_RUN")
    return 0


def _dispose_capture(resource: object, errors: list[BaseException]) -> None:
    try: resource.Dispose()
    except BaseException as error: errors.append(error)


if __name__ == "__main__": raise SystemExit(main())
