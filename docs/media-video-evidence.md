# Foundation Milestone 9: Media and Video evidence

Date: 2026-08-24.

`MILESTONE_9_COMPLETE=true`
`STRICT_ZERO=true`

The selected XNA 4.0 Windows runtime Python projection is structurally
complete. This statement is limited to the selected 257-type profile; it does
not claim all XNA profiles, platforms, media providers, audio/video backends,
or encoded assets are qualified.

## Structural result

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
```

Every mismatch category, internal/native leak counter, allowlist entry, and
unmeasured category is zero. Normal strict, leak-only, and `--check` all exit
zero. All exact 24 Media types have zero local diagnostics:

`Album`, `AlbumCollection`, `Artist`, `ArtistCollection`, `Genre`,
`GenreCollection`, `MediaLibrary`, `MediaPlayer`, `MediaQueue`, `MediaSource`,
`MediaSourceType`, `MediaState`, `Picture`, `PictureAlbum`,
`PictureAlbumCollection`, `PictureCollection`, `Playlist`,
`PlaylistCollection`, `Song`, `SongCollection`, `Video`, `VideoPlayer`,
`VideoSoundtrackType`, and `VisualizationData`.

The 2,423 target-member count is regenerated evidence, not a forced target. It
includes established Python language-protocol members on the seven collection
classes in addition to the 204 mapped Media contract members.

## Language mapping

`System.Uri` is an unmodified `str`; the consuming CNA route validates scheme
and path. `System.DateTime` is `datetime.datetime`; Media picture Unix ticks are
timezone-aware UTC. Existing mappings remain: `TimeSpan` is `timedelta`,
`Stream` is a private capability stream/`BinaryIO`, read-only collections are
tuple snapshots where XNA exposes a value collection, and events use the
existing descriptor. Nullable pre-annotation reference members have explicit
contextual rules. No public `System`, `System.Collections`, `System.IO`, or
`System.Uri` package exists.

## Collections, graph, and provider boundary

All seven collections use their canonical CNA count/index/dispose/destroy
routes. They expose native order, strict non-negative bounds, stable facade
identity, snapshot iteration, `len`, and no mutable backing list. Public
Dispose empties the native collection while independently retained items remain
valid; Game teardown invalidates both.

One provider identity domain canonicalizes `Artist`, `Album`, `Genre`, `Song`,
`Playlist`, `Picture`, and `PictureAlbum` handles with native equality. Parent
relationship properties cache collection facades. The qualified Local Device
provider returned an honest empty music catalog and native Picture/PictureAlbum
metadata. It did not cause Python to scan Music, Pictures, XDG directories, or
the filesystem. Repeated picture and nested-album access demonstrated element
identity. Music relationship coverage on a populated provider remains platform
qualification, not structural debt.

`MediaLibrary` is an owned provider root. Public Dispose marks its CNA object
disposed but preserves CNA/XNA-documented readable catalog metadata; final
destroy occurs at Game-generation teardown after child handles. Double Dispose,
retained children, wrong-thread refusal, owner-thread retry, and recreation were
exercised. Image/thumbnail copy routes are real, but the qualified provider
referenced host picture files unavailable to the isolated run; positive picture
streams/tokens and saving are `PLATFORM_PENDING` rather than fabricated.

`MediaSource.GetAvailableMediaSources` snapshots the native enumeration. The
qualified host exposed only `LocalDevice` named `Local Device`; library/source
access reused its generation-scoped facade. Windows Media Connect and other
platform source coverage remains `PLATFORM_PENDING`.

## Song, MediaPlayer, queue, and events

`Song.FromUri` reaches `cna_song_create_from_uri` with a deterministic,
project-authored legal 8-kHz mono PCM WAV. Name, duration, track/rating/play metadata,
protection/disposal, equality/hash, and nullable relationships are native. Song
is never implemented through SoundEffect. Missing/remote URIs fail through the
real CNA factory. Python rejects disposed Songs and empty/disposed collections
before CNA (which otherwise accepts a disposed Song handle). The player/queue
retains the exact Song facade supplied to Play, and stale-generation Songs
cannot enter a new Game.

MediaPlayer is non-instantiable and backed by one `RLock`-protected process
state. It separates CNA process scalars from Game generation, handles, queue
identity, callback registrations, and queued events. No unsynchronized global
raw pointer exists and the lock is not held while user handlers execute.
Game teardown unsubscribes, calls native program exit, discards weak-generation
work, destroys the queue, and releases all generation objects. CNA-preserved
mute/repeat/shuffle/volume state was observed in Game #2, while no Game #1
handle survived.

All Play overloads and Pause/Resume/Stop/MoveNext/MovePrevious use real CNA
routes. MediaPlayer Volume narrows to Single and preserves XNA comparisons:
finite/infinite values clamp to `[0,1]`, NaN survives, and negative zero retains
its sign. Queue is one stable facade per generation; item and ActiveSong access
reuse Song identity, replacement is native, and an old facade fails after Game
teardown.

ActiveSongChanged and MediaStateChanged are canonical
`void (*)(void*)` registrations. A ctypes trampoline catches `BaseException`,
captures only generation and handler snapshot state, and queues work on the
existing FrameworkDispatcher owner queue. No user handler runs inside C. The
stress gate delivered 50 native callbacks and verified stale-generation
discard. Existing event rules retain duplicates, subscription order, snapshot
cutoff/self-removal, and first-exception propagation without a parallel Media
dispatcher.

## Visualization

Independent C and ctypes measurement agrees:

```text
sizeof(CNA_VisualizationData)=2056
alignof(CNA_VisualizationData)=4
struct_size=0
struct_version=4
frequencies=8
samples=1032
```

Both public views are stable immutable tuples of 256 floats. The real
`cna_media_player_get_visualization_data` route copies native values into those
tuples. No ctypes array escapes and no samples, spectra, sine waves, or
meaningless success values are synthesized. Real decoded spectrum evidence is
`BACKEND_BLOCKED` on NULL audio; backend zeros are not XNA golden behavior.

## Video and Content

The private VideoReader consumes the authoritative XNB object sequence:
filename, duration milliseconds, width, height, frame rate, and soundtrack
identity. It resolves the filename relative to the asset and Content root, then
uses `cna_video_create_with_metadata`. It participates in the normal reader
table, cache identity, ResourceContentManager, Unload, reverse ownership,
post-create failure rollback, stale retained-object checks, and an explicit
LZX-compressed Video XNB load/unload path. The legal deterministic fixtures
contain metadata only; no encoded video is packaged.

VideoPlayer is owned. Create, Play/replacement, Pause, Resume, Stop, state, play
position, property mutation, Dispose, double Dispose, wrong-thread refusal and
owner-thread retry, wrong-generation checks, and teardown are canonical routes.
IsLooped, IsMuted, and Volume are intentionally cached/readable after Dispose;
setters, transport, and native state queries retain operation-specific disposed
guards even where CNA itself accepts a post-dispose setter. Finite Volume
outside `[0,1]` and infinities throw; NaN is accepted and preserved. The player
strongly retains a selected Video, unload stops and detaches it, and teardown
releases every VideoPlayer before any Video regardless of construction order.

No legal supported encoded video fixture is present, so positive decode is
`ASSET_PENDING`; decoded output on HEADLESS is separately `BACKEND_BLOCKED`.
Neither limitation is disguised as XNA behavior.

## GetTexture ownership decision

Canonical CNA 0.7 says a nonzero frame texture is owned by VideoPlayer, borrowed
by the caller, and valid only until the next player operation. Python has no
native destruction right. The existing public Texture2D owner requires stable
resource identity and cannot prove XNA-compatible frame generations from this
handle.

Therefore GetTexture rejects calls with no current Video, maps CNA's ordinary
no-frame result to `None`, and raises `NativeCapabilityError` for a nonzero
transient handle. It never constructs an owning Texture2D and never destroys
the borrowed handle. Twenty direct no-frame route cycles passed. Stable frame
identity/generation is `UPSTREAM_CNA_BLOCKED`.

## Behavior, ABI, and ownership gates

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

The qualified artifact remains CNA revision
`a09196a6477f69a7a57c8364f990658d31531a5b`, Sharp Runtime revision
`625476d5b5fff5fa89f392c3c9af8638ff237692`, and shared-library SHA-256
`c62949d23d3745964f5e557a06665875621ed4cb6e2930e3f282afd5911f2dcb`
on Linux x86-64 HEADLESS/NULL audio.

```text
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

No instrumented exact ABI-0.7 artifact was used, so crash absence is not
reported as allocator leak freedom.

The final source-tree gates are:

```text
COMPILEALL=PASS
UNITTESTS=138 total / 136 pass / 2 optional-fixture skips
VERIFIER_SELF_TESTS=7 PASS
MEDIA_TEST_METHODS=5 PASS
STRICT_REPORT=PASS
LEAK_ONLY=PASS
STRICT_CHECK=PASS
RUNTIME_CAPABILITIES=119
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

## Remaining qualification

The runtime inventory contains no `UNIMPLEMENTED_CNA_PYTHON` row for the
selected profile. Remaining rows are honest upstream, backend, platform,
hardware, asset, or language-mapping boundaries. Large feature work now stops;
Net, wider GamerServices/Avatar, Content Pipeline, Xbox, and Windows Phone are
not silently added. The repository moves to maintenance, runtime/platform
qualification, upstream CNA reconciliation, release qualification, and
real-game compatibility testing.
