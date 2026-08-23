"""Strict Microsoft.Xna.Framework.Audio namespace."""

from ._microphone import Microphone
from ._sound import (
    AudioChannels, AudioEmitter, AudioListener, AudioStopOptions,
    DynamicSoundEffectInstance, InstancePlayLimitException, MicrophoneState,
    NoAudioHardwareException, NoMicrophoneConnectedException, SoundEffect,
    SoundEffectInstance, SoundState,
)
from ._xact import AudioCategory, AudioEngine, Cue, RendererDetail, SoundBank, WaveBank

__all__ = [
    "AudioCategory", "AudioChannels", "AudioEmitter", "AudioEngine",
    "AudioListener", "AudioStopOptions", "Cue", "DynamicSoundEffectInstance",
    "InstancePlayLimitException", "Microphone", "MicrophoneState",
    "NoAudioHardwareException", "NoMicrophoneConnectedException", "RendererDetail",
    "SoundBank", "SoundEffect", "SoundEffectInstance", "SoundState", "WaveBank",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
