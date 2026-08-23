# Foundation Milestone 6: Audio and XACT evidence

Date: 2026-08-23. Status: complete on the qualified Linux x86-64 HEADLESS,
NULL-audio CNA ABI-0.7 runtime. Native route and ownership evidence is distinct
from audible output, physical capture, or successful authored-XACT evidence.

## Public dependency closure

The exact closure is the 19 XNA Audio types: `AudioCategory`, `AudioChannels`,
`AudioEmitter`, `AudioEngine`, `AudioListener`, `AudioStopOptions`, `Cue`,
`DynamicSoundEffectInstance`, `InstancePlayLimitException`, `Microphone`,
`MicrophoneState`, `NoAudioHardwareException`,
`NoMicrophoneConnectedException`, `RendererDetail`, `SoundBank`, `SoundEffect`,
`SoundEffectInstance`, `SoundState`, and `WaveBank`.

`FrameworkDispatcher` does not join the public closure. No Audio signature
references it, and the existing Game lifecycle already calls CNA's one native
dispatcher after each successful `Game.Update`. A throwing Update skips that
pump. Adding the public type would therefore add no dependency required by the
selected Audio behavior and could create a double-pump hazard.

The projection adds only contextual rules that XNA's pre-nullability metadata
cannot express: `Microphone.Default`, default `AudioCategory.Name`, and the two
default `RendererDetail` strings are nullable; `Microphone.GetData` takes a
mutable output sequence. XNA's three ExternalException-derived Audio
exceptions map to dedicated Python `Exception` subclasses. No `System.Audio`,
delegate, collection, or component-model support package was introduced.

## SoundEffect and sample arithmetic

Raw mono/stereo PCM16 construction and `FromStream` use the exact CNA copied-
buffer routes. The project-authored RIFF/WAVE fixtures cover 8, 44.1, and 48 kHz,
mono/stereo, an odd-sized padded extra chunk, truncation, malformed `fmt`/`data`,
unsupported encoding, and stream exceptions. Unsupported data is not
transcoded. SoundEffect owns its native resource; instances own their child
handles and strongly retain their effect. Parent-first, child-first, multiple
children, double disposal, context disposal, Game shutdown/recreation, failed
creation, and transactional wrong-thread refusal/retry are covered.

`GetSampleDuration` performs the XNA binary32 multiply/divide order before
whole-millisecond TimeSpan rounding. `GetSampleSizeInBytes` preserves the less
obvious XNA order in which `sampleRate / 1000` is binary32 and its multiplication
by `TotalMilliseconds` is binary64. Consequently one second of 44.1-kHz mono is
88,198 bytes, not the mathematically expected 88,200. Mono/stereo, odd sizes,
multiple rates, zero, invalid arguments, and overflow are golden-tested.

MasterVolume, DistanceScale, DopplerScale, and SpeedOfSound use CNA's real
process-global state. Binary32 narrowing, NaN/infinity/range rules, XNA's
positive float-epsilon clamp for zero DistanceScale, and persistence across Game
recreation are tested. No value is stored on a SoundEffect facade.

The qualified NULL backend accepts legal SoundEffect creation and all command
routes, but cannot demonstrate audible playback; it returns `false` for fire-
and-forget playback and reports zero native duration for accepted samples. Those
are recorded as backend observations, not substituted with Python playback or
duration state.

Exception translation is deliberately narrow: result 6 from legal SoundEffect
creation becomes `NoAudioHardwareException`; result 3 from CreateInstance,
which is CNA's `InstancePlayLimitException` barrier mapping, becomes
`InstancePlayLimitException`; and result 6 from Microphone.Start becomes
`NoMicrophoneConnectedException`. Unrelated invalid-state, platform, I/O,
thread, and internal failures remain `NativeError` rather than being relabeled.

## Instances, 3D, and dynamic streaming

SoundEffectInstance defaults, Volume/Pitch/Pan ranges (including NaN,
infinity, and signed zero), looping restrictions, transport overloads, repeated
Play, State, and disposal all use native routes. XNA's cached Volume, Pitch,
Pan, and IsLooped remain readable after disposal, while State, setters, and
transport reject the disposed instance; there is no universal disposed guard.

Single-listener Apply3D copies `CNA_AudioListener` and `CNA_AudioEmitter` into
the real native route. The canonical ABI explicitly returns result 6 for any
multi-listener count other than one. CNA-Python exposes the complete array
overload but reports `NativeCapabilityError`; it never selects listener zero,
averages listeners, or repeats the single-listener call.

DynamicSoundEffectInstance owns one ordinary instance handle and inherits the
same transport/mixing surface. CNA copies each submitted buffer during the call,
so temporary bytes, bytearray, and memoryview inputs require no retention.
Full/ranged input, alignment, empty/invalid ranges, repeated source buffers,
multiple pending buffers, drain, reentrant submission, and disposal are tested.

The canonical callback typedef is `void (*)(void*)`. CNA documents BufferNeeded
delivery from the thread advancing the queue and the Game path advances it in
the framework dispatcher. The callback checks owner-thread identity, is kept
strongly alive with its registration, catches every Python exception, and is
unregistered before native state is invalidated. Handler order, duplicates,
self-removal, reentrancy, exception short-circuit, disposal in a handler,
shutdown, no post-disposal callback, and skip-after-throwing-Update behavior are
covered. No Audio-specific event loop or second dispatcher exists.

## Microphone boundary

`Microphone.All` queries the native count and returns one stable read-only tuple
of stable index facades per Game. `Default` queries CNA independently and
resolves into that same tuple. The qualified NULL backend reports zero devices,
so `All == ()` and `Default is None`; no pseudo-device or samples are invented.

Name, State, BufferDuration, SampleRate, IsHeadset, Start/Stop, both GetData
overloads, sample math, and BufferReady use exact index-based routes. Mutable
output copying and callback registration lifetime are implemented. Repeated
failed registration publishes no handle. Real Start/GetData/event delivery is
`HARDWARE_PENDING`, because this host has no capture device.

## XACT graph and limitations

AudioEngine is the owned root. Its strict constructors validate an XGS header
then enter `cna_audio_engine_create` or the three-argument native route.
AudioCategory is a non-disposable value facade with stable per-engine public
identity and a privately owned C facade handle. WaveBank and SoundBank are owned
engine children; Cue is an owned SoundBank child while also retaining the
engine dependencies required by CNA. All children are released before parents,
failed outputs remain invalid, and disposal events are managed exactly once.

CNA ABI 0.7 documents that renderer id and look-ahead ticks are accepted but
ignored. Constructor shape and validation remain complete and the real route is
called, but both semantics are `UPSTREAM_CNA_BLOCKED`. RendererDetail default
null strings, equality/hash/copy/type-name behavior and native enumeration
shape are complete; NULL audio fabricates no renderer.

No legal redistributable XGS/XSB/XWB fixture was found in the project or its
reference bindings. Malformed settings and failed WaveBank/SoundBank creation
reach CNA repeatedly with clean rollback. Successful category/cue acquisition
and authored playback are `ASSET_PENDING`, not a claimed CNA defect and not a
reason to fabricate an XACT graph.

## Measured evidence

```text
TARGET_TYPES=180
TARGET_MEMBERS=1772
MISSING_TYPES=77
MISSING_MEMBERS=0
PARTIAL_TYPES=0
all mismatch/leak/allowlist/unmeasured categories=0

BOUND_FUNCTIONS=471
CTYPES_SIGNATURE_MEASUREMENTS=471
C_LAYOUT_MEASUREMENTS=708
CTYPES_LAYOUT_MEASUREMENTS=708
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0

OBSERVATIONS=119
ASSERTIONS=538
FAILURES=0
```

Dedicated stress runs 20 SoundEffect, instance, dynamic-instance, microphone-
registration, AudioEngine failure, failed WaveBank, and failed SoundBank cycles,
plus 50 dynamic callback cycles. Wrong-thread destruction refusal/retry and Game
recreation also pass. `NATIVE_CRASHES=0`, `OBSERVED_UAF=0`, and
`DOUBLE_FREE=0`. `SANITIZER_STATUS=NOT_RUN`; no allocator-level leak claim is
made without an instrumented exact ABI-0.7 artifact.
