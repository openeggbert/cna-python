# CNA-Python tactical handoff

Date: 2026-08-24

```text
MILESTONE_9_COMPLETE=true
STRICT_ZERO=true
REPOSITORY_MODE=maintenance/runtime-platform-qualification/upstream-reconciliation
```

Foundation Milestones 1–9 are complete. The selected XNA 4.0 Windows runtime
Python projection is structurally complete. This does not qualify other XNA
profiles, every platform, every provider, or every backend. Do not open Net,
wider GamerServices/Avatar, Content Pipeline, Xbox, or Windows Phone without a
deliberate future-profile decision.

## Strict projection

```text
REFERENCE_TYPES=257
REFERENCE_MEMBERS=2964
EXPECTED_PYTHON_TYPES=257
EXPECTED_PYTHON_MEMBERS=2887
TARGET_TYPES=257
TARGET_MEMBERS=2423
TOTAL_DIAGNOSTICS=0
MISSING_TYPE=0
MISSING_MEMBER=0
COMPLETE_TYPES=257
PARTIAL_TYPES=0
MISSING_TYPES=0

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
ZERO_DIAGNOSTIC_TYPES=257
```

Normal report, `--leak-only`, and `--check` exit zero. The regenerated 2,423
target members include established Python protocols on the seven Media
collections and were not forced to the CLR-member count.

All exact 24 Media types have zero local diagnostics:

```text
Album                    AlbumCollection
Artist                   ArtistCollection
Genre                    GenreCollection
MediaLibrary             MediaPlayer
MediaQueue               MediaSource
MediaSourceType          MediaState
Picture                  PictureAlbum
PictureAlbumCollection   PictureCollection
Playlist                 PlaylistCollection
Song                     SongCollection
Video                    VideoPlayer
VideoSoundtrackType      VisualizationData
```

## Media/Video boundary

- All seven read-only collections use native count/index/dispose/destroy,
  preserve native ordering, stable item identities, strict bounds, snapshot
  iteration, and deterministic Game-generation invalidation.
- Artist/Album/Genre/Playlist/Song/Picture/PictureAlbum share a provider
  identity domain. Relationship collections are cached. No catalog item is
  fabricated.
- MediaLibrary is the owned provider root. The qualified Local Device has an
  empty music catalog and native picture metadata. Positive picture stream,
  thumbnail/token, and save qualification remains `PLATFORM_PENDING`.
- MediaSource enumeration is native and stable. This host exposed only Local
  Device; removable/network coverage remains `PLATFORM_PENDING`.
- Song.FromUri uses `cna_song_create_from_uri` with a generated legal 8-kHz
  mono PCM WAV; it is not SoundEffect. Queue and relationship access preserve
  the native Song facade where identity permits. Missing/remote URIs fail, and
  disposed Songs plus empty/disposed collections are rejected before CNA.
- MediaPlayer is a synchronized, non-instantiable process-global facade. Its
  state object separates scalar state, current Game generation, handles,
  callback registrations, queue identity, and weak-generation queued work.
- Transport and scalars are native. MediaPlayer Volume clamps finite values and
  infinities to `[0,1]`, preserves NaN and signed zero, and follows CNA/XNA
  process-global persistence evidence across Game recreation.
- MediaQueue is one live facade per generation. Item/ActiveSong identity,
  replacement, and stale-generation rejection are verified.
- ActiveSongChanged and MediaStateChanged use canonical callbacks, contain
  `BaseException`, capture handler snapshots, and deliver only through the
  existing owner-thread FrameworkDispatcher queue. No handler runs in C and
  stale Game work is discarded.
- VisualizationData is a managed immutable pair of 256-float tuples. The real
  native route copies its result; nothing is synthesized.
- Video is private-VideoReader/ContentManager-created and uses the existing XNB
  reader table, cache, rollback, Unload, external-path, ownership, and an
  explicitly tested compressed-LZX path. No encoded video or proprietary sample
  is packaged.
- VideoPlayer uses native Play/replacement/Pause/Resume/Stop and is owned.
  Cached IsLooped/IsMuted/Volume remain readable after Dispose; setters,
  transport, state, and position reject after Dispose. Out-of-range finite or
  infinite Volume throws; NaN is preserved.
- GetTexture calls CNA. Before Play it throws; native no-frame maps to `None`.
  A nonzero CNA handle raises `NativeCapabilityError`: it is player-owned and
  valid only until the next player operation, so Python never wraps or destroys
  it as an owned Texture2D. Stable frame identity is `UPSTREAM_CNA_BLOCKED`.

See `docs/media-video-evidence.md` for the complete ownership and behavioral
argument.

## Behavior and ABI

```text
OBSERVATIONS=181
ASSERTIONS=1004
FAILURES=0
MEDIA_PURE_XNA_DERIVED=10

BOUND_FUNCTIONS=744
CTYPES_SIGNATURE_MEASUREMENTS=744
C_LAYOUT_MEASUREMENTS=775
CTYPES_LAYOUT_MEASUREMENTS=775
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0
```

Visualization layout is independently measured as size 2,056, alignment 4,
with `struct_size`/`struct_version` at offsets 0/4 and the two 256-Single arrays
at offsets 8/1,032. Media callback typedefs are exact `void (*)(void*)` routes
with retained ctypes callback objects and native subscription tokens.

Qualified shared artifact:

```text
CNA_REVISION=a09196a6477f69a7a57c8364f990658d31531a5b
SHARP_RUNTIME_REVISION=625476d5b5fff5fa89f392c3c9af8638ff237692
SHARED_LIBRARY_SHA256=c62949d23d3745964f5e557a06665875621ed4cb6e2930e3f282afd5911f2dcb
PLATFORM=Linux x86-64
RENDERER=HEADLESS
AUDIO=NULL
```

The unrelated static-archive aggregation failure remains unrelated to this
successfully linked and fully measured shared library. CNA remained read-only.

## Verification and ownership

```text
COMPILEALL=PASS
UNITTESTS=138 total / 136 pass / 2 optional-fixture skips
VERIFIER_SELF_TESTS=7 PASS
MEDIA_TEST_METHODS=5 PASS
STRICT_REPORT=PASS
LEAK_ONLY=PASS
STRICT_CHECK=PASS
BEHAVIOR_CORPUS=PASS
RUNTIME_CAPABILITY_GENERATOR=119 PASS
ABI_AUDIT=PASS

MEDIA_LIBRARY_CYCLES=20
MEDIA_PLAYER_GAME_CYCLES=20
SONG_CYCLES=20
QUEUE_GENERATION_CYCLES=20
MEDIA_CALLBACK_DELIVERIES=50
VIDEO_CYCLES=20
VIDEO_PLAYER_CYCLES=20
VIDEO_FRAME_ROUTE_CYCLES=20
NATIVE_CRASHES=0
OBSERVED_UAF=0
DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

Media stress includes provider/catalog identity, retained children, double
Dispose, wrong-thread MediaLibrary and VideoPlayer refusal plus owner retry,
Song playback, queue recreation, callback delivery, Video Play/replacement,
Video-before-player teardown, and native no-frame access. All historical
Game/Graphics, Content, Effect/Model, Audio, and Milestone-8 stress suites also
pass at their required 20/50-cycle thresholds. Crash absence is not an
allocator-leak claim; no instrumented exact ABI-0.7 artifact was used.

## Runtime capabilities

```text
CAPABILITIES=119
VERIFIED_MANAGED=11
VERIFIED_NATIVE=69
UPSTREAM_CNA_BLOCKED=11
BACKEND_BLOCKED=13
HARDWARE_PENDING=4
PLATFORM_PENDING=5
ASSET_PENDING=4
LANGUAGE_MAPPING_LIMITATION=2
UNIMPLEMENTED_CNA_PYTHON=0
```

The remaining Media-specific qualification is deliberately split: populated
catalogs and picture bytes/tokens are platform-pending; real visualization and
HEADLESS decode are backend-blocked; a legal positive encoded-video fixture is
asset-pending; stable frame identity is upstream-CNA-blocked.

## Final package and exact-wheel qualification

```text
WHEEL_FILENAME=cna_python-0.1.0.dev0-py3-none-any.whl
WHEEL_SHA256=fdd12593563df9e86170fa5b511eadc5b9b5487196eada1e3c96bdc0fa8297a6
WHEEL_FILES=80
WHEEL_ENTRIES=80
SDIST_FILENAME=cna_python-0.1.0.dev0.tar.gz
SDIST_SHA256=133f6b85c2c98e669ada41fe16bdcf2c278578375e986aec3055b35dc9a8a0ec
SDIST_FILES=176
SDIST_ENTRIES=176
FORBIDDEN_WHEEL_ENTRIES=0
FORBIDDEN_SDIST_ENTRIES=0
ABSOLUTE_DEVELOPER_PATHS=0
BUNDLED_NATIVE_LIBRARIES=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0

ISOLATED_FINAL_WHEEL_IMPORT=PASS
ISOLATED_FINAL_WHEEL_COMPILE=PASS
MAINTAINED_IMPORT=PASS
MAINTAINED_COMPILE=PASS
MAINTAINED_60=PASS
MAINTAINED_600=PASS
GENERATED_IMPORT=PASS
GENERATED_COMPILE=PASS
GENERATED_60=PASS
GENERATED_600=PASS
GENERATED_ABSOLUTE_DEVELOPER_PATHS=0
GENERATED_SIBLING_SOURCE_DEPENDENCIES=0
GENERATED_PYTHONPATH_SOURCE_DEPENDENCIES=0
PYTHONPATH=UNSET
TEMPLATE_SOURCE_CHANGED=NO
```

The artifact SHA is for the exact wheel used in every installed-wheel gate.
The maintained starter was copied byte-for-byte to a writable temporary tree
because Sharp Runtime opens its XNB with read/write access; no template source
or asset bytes changed. The generated consumer had no absolute developer path,
sibling checkout, or `PYTHONPATH` dependency.

## Next work

Only maintenance, runtime/platform qualification, upstream CNA blocker
reconciliation, packaging/release work, and real-game compatibility testing are
in scope. Structural expansion requires a separately selected future profile.
