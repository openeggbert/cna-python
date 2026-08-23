# CNA-Python tactical handoff

Date: 2026-08-23.

`MILESTONE_6_COMPLETE=true`

Foundation Milestone 6 is complete. All 19 XNA Audio types form one
structurally complete, native-backed, callback-safe, ownership-ordered Audio and
XACT subsystem. No Media, Storage, Design, Touch, PackedVector, Curve,
GamerServices, OcclusionQuery, RenderTargetCube, or public FrameworkDispatcher
work was started.

## Strict result

```text
                               M6 START  M6 FINAL
REFERENCE_TYPES                      257       257
REFERENCE_MEMBERS                   2964      2964
EXPECTED_PYTHON_TYPES                257       257
EXPECTED_PYTHON_MEMBERS             2887      2887
TARGET_TYPES                         161       180
TARGET_MEMBERS                      1651      1772
TOTAL_DIAGNOSTICS                     96        77
MISSING_TYPE                          96        77
MISSING_MEMBER                         0         0
COMPLETE_TYPES                       161       180
PARTIAL_TYPES                          0         0
MISSING_TYPES                         96        77
```

All 77 diagnostics are whole future types. Audio local diagnostics are zero,
and normal strict `--check` is nonzero only for those absent types.

```text
UNEXPECTED_TYPE=0
UNEXPECTED_MEMBER=0
TYPE_KIND_MISMATCH=0
BASE_MAPPING_MISMATCH=0
INTERFACE_MAPPING_MISMATCH=0
FIELD_MAPPING_MISMATCH=0
PROPERTY_MAPPING_MISMATCH=0
METHOD_SIGNATURE_MAPPING_MISMATCH=0
PARAMETER_MAPPING_MISMATCH=0
RETURN_MAPPING_MISMATCH=0
OVERLOAD_MAPPING_MISMATCH=0
GENERIC_MAPPING_MISMATCH=0
ENUM_VALUE_MISMATCH=0
FLAGS_MAPPING_MISMATCH=0
EVENT_MAPPING_MISMATCH=0
OPERATOR_MAPPING_MISMATCH=0
LANGUAGE_MAPPING_MISMATCH=0
INTERNAL_TYPE_LEAK=0
RAW_HANDLE_LEAK=0
PUBLIC_NATIVE_FFI_LEAK=0
ALLOWLIST_ENTRIES=0
UNMEASURED_STRUCTURAL_CATEGORY=0
ZERO_DIAGNOSTIC_TYPES=180
```

## Dependency closure and mapping

The exact 19 types are `AudioCategory`, `AudioChannels`, `AudioEmitter`,
`AudioEngine`, `AudioListener`, `AudioStopOptions`, `Cue`,
`DynamicSoundEffectInstance`, `InstancePlayLimitException`, `Microphone`,
`MicrophoneState`, `NoAudioHardwareException`,
`NoMicrophoneConnectedException`, `RendererDetail`, `SoundBank`, `SoundEffect`,
`SoundEffectInstance`, `SoundState`, and `WaveBank`.

FrameworkDispatcher did not join. Audio metadata contains no dependency on the
public type, while Game already runs CNA's one framework-dispatcher pump after a
successful Update and skips it after a throwing Update. A second Python pump
would duplicate callbacks.

New contextual mappings are limited to nullable `Microphone.Default`, nullable
default-struct strings (`AudioCategory.Name` and both RendererDetail strings),
and `MutableSequence[int]` for the output buffer in Microphone.GetData.
ExternalException maps to Python Exception for the three dedicated XNA Audio
exceptions. No fake System support package was added.

## Audio values and SoundEffect

- All five enums have exact identities. AudioListener and AudioEmitter have XNA
  defaults, reference semantics, binary32 DopplerScale, and Vector3 copy
  boundaries. RendererDetail has its exact default null strings, equality,
  hash, copy, and type-name ToString behavior.
- SoundEffect raw constructors accept copied PCM16, preserve format-first
  seven-argument validation, alignment, loop, and range rules, and call
  `cna_sound_effect_create_pcm16_range_ext`.
- FromStream validates legal project-authored PCM16 RIFF/WAVE without
  transcoding, then uses CNA's copied encoded-byte route. Mono/stereo at 8,
  44.1, and 48 kHz, padded extra chunks, malformed/truncated chunks,
  unsupported encoding, and stream exceptions are covered.
- GetSampleDuration preserves XNA binary32 multiply/divide and TimeSpan
  rounding. GetSampleSizeInBytes preserves binary32 `rate / 1000` followed by
  binary64 multiplication. One second, 44.1-kHz mono is exactly 88,198 bytes.
- MasterVolume, DistanceScale, DopplerScale, and SpeedOfSound use CNA's
  process-global values and persist across Game recreation. XNA range, NaN,
  infinity, signed-zero, and positive-epsilon rules are verified.
- Play and CreateInstance use native routes. SoundEffect is owned, instances are
  owned children which retain their effect, and both disposal orders, multiple
  children, double disposal, context managers, shutdown, recreation, failure,
  and wrong-thread refusal/retry are covered.
- NULL audio accepts construction but produces no audible-output claim. Its
  fire-and-forget Play returns false and native Duration reports zero; neither
  behavior is hidden by Python state.

Exception translation is narrow: legal SoundEffect creation result 6 becomes
NoAudioHardwareException; CreateInstance result 3 becomes
InstancePlayLimitException; Microphone.Start result 6 becomes
NoMicrophoneConnectedException. Other CNA failures remain NativeError.

## SoundEffectInstance and 3D

Volume, Pitch, Pan, IsLooped, State, Play/Pause/Resume, both Stop overloads,
repeated Play, and Dispose call exact native routes. Defaults and validation are
covered, including NaN, infinity, binary32 narrowing, and negative zero. Volume,
Pitch, Pan, and IsLooped remain readable from their XNA caches after Dispose;
State, setters, and transport fail. `Dispose(false)` still releases native
ownership and does not rely on a Python finalizer.

Single-listener Apply3D is `VERIFIED_NATIVE`. The complete sequence overload
calls the array ABI, but CNA ABI 0.7 explicitly rejects every listener count
other than one. Multiple listeners are `UPSTREAM_CNA_BLOCKED` and raise
NativeCapabilityError; there is no listener-zero fallback, averaging, or
repeated single-listener approximation.

## Dynamic audio and dispatcher

DynamicSoundEffectInstance is the exact subclass and owns one ordinary native
instance handle. SubmitBuffer accepts complete or offset/count byte sequences.
Canonical CNA copies the bytes during the call, so bytes, bytearray, and
memoryview inputs are not retained. Empty, invalid, odd-aligned, repeated,
multiple-pending, drained, reentrant, and disposed paths are covered.

PendingBufferCount and sample helpers are native. BufferNeeded uses the exact
`void (*)(void*)` ABI registration. The callback is strongly retained,
owner-thread checked, exception-total at the C boundary, and unsubscribed before
the handle or Game is destroyed. Duplicate/order/remove, self-removal,
reentrant submit, exception short-circuit, later handlers, disposal in handler,
shutdown, no callback after disposal, and throwing-Update pump suppression are
verified. No Audio event loop and no second dispatcher exist.

## Microphone

Microphone.All is an identity-stable tuple of non-owning index facades and
Default resolves into the same collection. The qualified NULL backend reports
`All == ()` and `Default is None`; no pseudo-microphone or data is fabricated.

Name, State, BufferDuration, SampleRate, IsHeadset, Start/Stop, both mutable
GetData overloads, sample helpers, and BufferReady are complete over canonical
index routes. Failed registration publishes no handle and cleanup occurs before
Game destruction. With no physical capture device, enumeration is
`VERIFIED_NATIVE` and real Start/GetData/BufferReady delivery is
`HARDWARE_PENDING`.

## XACT

AudioEngine is the owned root. AudioCategory is a parent-owned, non-disposable
value facade with stable repeated lookup identity and a privately released C
facade. WaveBank and SoundBank are owned engine children; Cue is an owned
SoundBank child retaining its engine dependencies. All constructors, public
methods/events/properties, disposal shapes, invalidation, child-before-parent
shutdown, and failed-output rollback are implemented.

CNA's three-argument AudioEngine route accepts but explicitly ignores renderer
id and look-ahead ticks; both are `UPSTREAM_CNA_BLOCKED`. No legal
redistributable XGS/XSB/XWB fixture exists in the project/reference trees.
Malformed settings and repeated bank failure routes are native and ownership-
safe; successful category/cue acquisition and authored playback are
`ASSET_PENDING`, not a CNA defect claim and not a fabricated graph.

## Runtime capability inventory

The generated inventory has 74 granular rows. Milestone 6 adds separate rows
for SoundEffect, instances, both Apply3D shapes, dynamic streaming and callback,
microphone enumeration/capture, AudioEngine, renderer/look-ahead, RendererDetail,
AudioCategory, each bank/cue family, and authored playback. No selected Audio
row is `UNIMPLEMENTED_CNA_PYTHON`.

Key classifications:

- `VERIFIED_NATIVE`: SoundEffect construction/commands, SoundEffectInstance,
  single-listener Apply3D, DynamicSoundEffectInstance, BufferNeeded, microphone
  enumeration, AudioEngine error/rollback route, WaveBank and SoundBank failure
  routes;
- `VERIFIED_MANAGED`: RendererDetail value behavior;
- `UPSTREAM_CNA_BLOCKED`: multiple listeners, renderer selection, look-ahead;
- `HARDWARE_PENDING`: physical microphone capture;
- `ASSET_PENDING`: successful AudioCategory/Cue and authored XACT playback.

## Behavior corpus

```text
OBSERVATIONS: 111 -> 119
ASSERTIONS: 496 -> 538
FAILURES=0
PROVENANCE=PURE_XNA_DERIVED
```

Audio groups cover enum identities, listener/emitter defaults, vector-copy
boundaries, emitter NaN behavior, sample duration/size arithmetic,
RendererDetail defaults, and AudioCategory defaults. NULL-audio results,
microphone absence, playback timing, CNA result codes, and absent XACT assets
are intentionally excluded from XNA golden behavior.

## ABI

```text
BOUND_FUNCTIONS: 375 -> 471
CTYPES_SIGNATURE_MEASUREMENTS=471
C_LAYOUT_MEASUREMENTS: 653 -> 708
CTYPES_LAYOUT_MEASUREMENTS: 653 -> 708
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0 / 0x00000700
```

The 96 used Audio/XACT imports have explicit argtypes/restype, pointer depth,
width, signedness, ownership, and export checks. New callback and layout
measurements cover CNA_AudioEventCallback, CNA_AudioCapabilities,
CNA_SoundEffectCreateInfo, CNA_SoundEffectInstanceInfo, CNA_AudioEmitter,
CNA_AudioListener, and CNA_CueInfo.

Qualified artifact:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
```

Current CNA HEAD was rechecked read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. Its C-API build remains blocked
by the known renderer identity 49-versus-50 guard. CNA was not modified.

## Ownership stress

```text
SOUND_EFFECT_CYCLES=20
INSTANCE_CYCLES=20
DYNAMIC_INSTANCE_CYCLES=20
DYNAMIC_CALLBACK_CYCLES=50
MICROPHONE_REGISTRATION_ATTEMPT_CYCLES=20
MICROPHONE_REGISTRATION_SUCCESS_CYCLES=0
AUDIO_ENGINE_ATTEMPT_CYCLES=20
AUDIO_ENGINE_SUCCESS_CYCLES=0
FAILED_WAVEBANK_CYCLES=20
FAILED_SOUNDBANK_CYCLES=20
WRONG_THREAD_REFUSAL_CYCLES=1
GAME_RECREATION_CYCLES=1
NATIVE_CRASHES=0
OBSERVED_UAF=0
DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

Zero microphone/engine successes reflect the qualified hardware/asset boundary,
not omitted attempts. The pre-existing native, Content, and Effect/Model stress
suites also pass at 20 cycles with zero crashes or observed lifetime failures.
No allocator-level leak claim is made without sanitizers.

## Final package

Version remains `0.1.0.dev0`.

```text
WHEEL_FILENAME=cna_python-0.1.0.dev0-py3-none-any.whl
WHEEL_SHA256=ee908046e07b44a528e244c7fe3310f668205f4d862103dadff02e7dbe9ffccc
WHEEL_ENTRIES=55
SDIST_FILENAME=cna_python-0.1.0.dev0.tar.gz
SDIST_SHA256=f7f722662627432270770fc69f14f31fffb2659e5c5b647bca5e1a71c84d05c7
SDIST_ENTRIES=133
FORBIDDEN_WHEEL_ENTRIES=0
FORBIDDEN_SDIST_ENTRIES=0
ABSOLUTE_DEVELOPER_PATHS=0
BUNDLED_NATIVE_LIBRARIES=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0
```

Audio contains no package-data WAV/XACT asset. Deterministic WAV bytes are
created only by tests and source-distribution test code.

## Isolated consumers and template

The exact final wheel above was installed with `--no-index --no-deps` into
fresh venvs with no editable install, source checkout import, sibling runtime
dependency, or PYTHONPATH.

```text
ISOLATED_IMPORT_PROBE=PASS
ISOLATED_AUDIO_IMPORT_PROBE=PASS
ISOLATED_COMPILE_PROBE=PASS
GENERATED_SMOKE_60=PASS
GENERATED_STABILITY_600=PASS
MAINTAINED_SMOKE_60=PASS
MAINTAINED_STABILITY_600=PASS
ABSOLUTE_DEVELOPER_PATHS=0
SIBLING_SOURCE_DEPENDENCIES=0
PYTHONPATH_SOURCE_DEPENDENCIES=0
TEMPLATE_SOURCE_CHANGED=NO
```

The maintained template remains the raw PNG plus Texture2D XNB 2D lifecycle
canary. No WAV, microphone, XACT, Effect, Model, or Audio showcase was added.

## Remaining exact inventory

The regenerated 77 whole missing types are:

- Framework (7): `Curve`, `CurveContinuity`, `CurveKey`,
  `CurveKeyCollection`, `CurveLoopType`, `CurveTangent`,
  `FrameworkDispatcher`;
- Design (13): `BoundingBoxConverter`, `BoundingSphereConverter`,
  `ColorConverter`, `MathTypeConverter`, `MatrixConverter`, `PlaneConverter`,
  `PointConverter`, `QuaternionConverter`, `RayConverter`,
  `RectangleConverter`, `Vector2Converter`, `Vector3Converter`,
  `Vector4Converter`;
- GamerServices (1): `GamerServicesComponent`;
- Graphics (2): `OcclusionQuery`, `RenderTargetCube`;
- PackedVector (19): `Alpha8`, `Bgr565`, `Bgra4444`, `Bgra5551`, `Byte4`,
  `HalfSingle`, `HalfVector2`, `HalfVector4`, `IPackedVector`,
  `IPackedVector<T>`, `NormalizedByte2`, `NormalizedByte4`,
  `NormalizedShort2`, `NormalizedShort4`, `Rg32`, `Rgba1010102`, `Rgba64`,
  `Short2`, `Short4`;
- Touch (8): `GestureSample`, `GestureType`, `TouchCollection`,
  `TouchCollection.Enumerator`, `TouchLocation`, `TouchLocationState`,
  `TouchPanel`, `TouchPanelCapabilities`;
- Media (24): `Album`, `AlbumCollection`, `Artist`, `ArtistCollection`, `Genre`,
  `GenreCollection`, `MediaLibrary`, `MediaPlayer`, `MediaQueue`, `MediaSource`,
  `MediaSourceType`, `MediaState`, `Picture`, `PictureAlbum`,
  `PictureAlbumCollection`, `PictureCollection`, `Playlist`,
  `PlaylistCollection`, `Song`, `SongCollection`, `Video`, `VideoPlayer`,
  `VideoSoundtrackType`, `VisualizationData`;
- Storage (3): `StorageContainer`, `StorageDevice`,
  `StorageDeviceNotConnectedException`.

The machine-readable and rendered inventories are in
`docs/generated/missing-type-inventory.json` and `.md`. No next family was
started.

## Reproduction

```bash
python3 -m compileall -q src tests tools
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # nonzero only for 77 absent types
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/generate_runtime_capabilities.py
python3 tools/audit_cna_abi.py --cna-root /qualified/cna/source --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/native_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/content_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/effect_model_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/audio_ownership_stress.py --cycles 20 --callback-cycles 50
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```
