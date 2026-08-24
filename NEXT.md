# CNA-Python tactical handoff

Date: 2026-08-23.

`MILESTONE_8_COMPLETE=true`

Foundation Milestone 8 is complete. All fifteen selected non-Media runtime
types are complete, use real CNA ABI 0.7 routes wherever native behavior is
required, and retain explicit capability classifications where CNA, the
qualified backend, hardware, or platform cannot provide an XNA behavior. No
Media type was started and CNA was not modified.

The detailed implementation evidence is in `docs/milestone8-evidence.md`.

## Strict result

```text
                               M8 START  M8 FINAL
REFERENCE_TYPES                      257       257
REFERENCE_MEMBERS                   2964      2964
EXPECTED_PYTHON_TYPES                257       257
EXPECTED_PYTHON_MEMBERS             2887      2887
TARGET_TYPES                         218       233
TARGET_MEMBERS                      2061      2174
TOTAL_DIAGNOSTICS                     39        24
MISSING_TYPE                          39        24
MISSING_MEMBER                         0         0
COMPLETE_TYPES                       218       233
PARTIAL_TYPES                          0         0
MISSING_TYPES                         39        24
```

Every Milestone 8 type has zero local diagnostics. Normal strict `--check`
exits nonzero solely for the 24 whole missing Media types; leak-only passes.

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
ZERO_DIAGNOSTIC_TYPES=233
```

## FrameworkDispatcher

- Public `FrameworkDispatcher.Update()` invokes exactly one
  `cna_framework_dispatcher_update` on the current live Game generation.
- The existing Game loop is unchanged: a successful `Game.Update` is followed
  by its one automatic native pump; a throwing update has no automatic
  post-failure pump. An explicit call is one additional pump and is not
  suppressed just because Game also pumps.
- Native callbacks first terminate inside their ctypes trampoline. User work
  converges on the Game owner's single queue, and a stored exception is
  re-raised only after native control returns. Storage, Audio, Touch,
  GamerServices, and future families do not own parallel dispatchers.
- Reentrant explicit calls therefore remain ordinary explicit native calls;
  no hidden coalescing or second automatic pump exists.
- CNA ABI 0.7 requires a valid Game handle although XNA permits process-level
  dispatcher use without a live Game. Python raises an explicit
  `NativeCapabilityError`; it does not silently no-op or invent a dispatcher.
  This scenario is `UPSTREAM_CNA_BLOCKED`.

## GamerServices

- `GamerServicesComponent(Game)` is a normal `GameComponent` and participates
  in the existing Components ordering, one-initialize-per-Game-lifecycle, and
  inherited Enabled/Update behavior.
- Initialize copies the owning Game window handle to CNA, initializes the
  native GamerServices dispatcher, then calls the base lifecycle. Update calls
  the native dispatcher and then the base hook, matching the selected XNA IL.
- Construction, collection integration, initialize/update, disabled update,
  initialization and update failure boundaries, shutdown, and Game recreation
  are covered. Twenty lifecycle cycles pass.
- Gamer, Guide UI, Avatar, achievements, leaderboards, networking, and other
  GamerServices public types are outside the selected profile and were not
  fabricated. The selected component lifecycle is `VERIFIED_NATIVE`; the
  broader ecosystem is `BACKEND_BLOCKED` for this projection.

## OcclusionQuery

- `OcclusionQuery` is an owned `GraphicsResource` tied to one GraphicsDevice
  generation. Begin, End, IsComplete, and PixelCount use the canonical
  `cna_occlusion_query_*` routes; Python does not emulate pixel counts.
- The exact XNA state machine covers new, active, submitted, completion
  queried, reusable second cycle, Begin twice, End without Begin, PixelCount
  before completion, reuse before querying completion, and disposed access.
- The qualified HEADLESS renderer creates a real query, completes it, and
  returns its deterministic native count. That backend value is runtime
  evidence, not an XNA golden value. Status is `VERIFIED_NATIVE`.
- Explicit/context disposal, double disposal, wrong-thread refusal with later
  owner-thread retry, device invalidation, child-before-Game shutdown, strong
  Game ownership, and recreation pass twenty two-cycle stress iterations.

## RenderTargetCube

- The type inherits `TextureCube` and preserves both selected constructors.
  Size, mip-map selection, preferred SurfaceFormat, DepthFormat, MSAA count,
  and RenderTargetUsage all reach `cna_render_target_cube_create`; no argument
  is forced or dropped.
- Native result information supplies IsContentLost, DepthStencilFormat,
  MultiSampleCount, and RenderTargetUsage. The existing TextureCube ownership
  and codec foundation is reused.
- `GraphicsDevice.SetRenderTarget(cube, face)`, SetRenderTargets,
  GetRenderTargets, RenderTargetBinding.RenderTarget/CubeMapFace, all six
  CubeMapFace values, and backbuffer restoration use the ordinary CNA binding
  route. There is no cube-only renderer.
- ContentLost subscription/removal semantics are complete. ABI 0.7 can query
  current content-loss state but exposes no loss-transition callback, so no
  event is synthesized. Current state is `VERIFIED_NATIVE`; real event delivery
  is `UPSTREAM_CNA_BLOCKED`.
- CNA can abort the process if a currently bound render target is destroyed.
  Python detects the retained binding before native destruction, raises an
  accurate capability/native error, preserves the owned handle, and permits a
  legal owner-thread retry after explicit backbuffer restoration. It never
  restores the backbuffer silently. The unsafe CNA behavior is
  `UPSTREAM_CNA_BLOCKED`; twenty guarded/retry cycles have zero crashes.

## Touch

All eight types are complete: `GestureSample`, `GestureType`,
`TouchCollection`, `TouchCollection.Enumerator`, `TouchLocation`,
`TouchLocationState`, `TouchPanel`, and `TouchPanelCapabilities`.

- GestureType has the exact ten XNA flag bits. GestureSample preserves type,
  timestamp as `datetime.timedelta`, both positions, and both deltas.
- TouchLocation implements both constructors, previous-location sentinel,
  ToString, hash, copies, and XNA's observable distinction between `Equals`
  and `==`.
- TouchCollection preserves the XNA fixed-capacity, read-only IList behavior,
  connected flag, value-copy boundaries, indexing, FindById, IndexOf,
  Contains, CopyTo, and enumeration. Mutators remain present and reject as XNA
  does; it is not reduced to a plain mutable list.
- The nested CLR type projects only as `TouchCollection.Enumerator`; there is
  no top-level Enumerator. MoveNext, Current before/after range, Dispose,
  iterator protocol, and struct-like enumerator copy behavior are covered.
- TouchPanel capability, state, gesture, window, display, and configuration
  properties use canonical CNA routes. EnabledGestures validates exact bits
  and preserves XNA's process-static enabled precondition. DisplayOrientation
  accepts only the four exact defined identities. WindowHandle uses the
  bounded IntPtr-to-int mapping and is cleared before its Game generation is
  destroyed.
- ReadGesture when no gesture is available uses the real native invalid-state
  result; it never returns a fabricated default GestureSample. HEADLESS's
  disconnected, zero-touch, empty-gesture state is honest native evidence.
  Physical input is `HARDWARE_PENDING`; positive gesture recognition is
  `PLATFORM_PENDING`.

## Storage language mapping

The formal rules are recorded in `docs/xna-python-mapping.md`,
`tools/api_compat/mapping-rules.json`, and six passing verifier self-tests:

```text
System.IAsyncResult -> private opaque token, publicly object
System.AsyncCallback -> Callable[[object], None]
FileMode             -> canonical snake-case str
FileAccess           -> canonical snake-case str
FileShare            -> frozenset[str] flags; empty means None
System.IO.Stream     -> private binary stream facade by native capability
```

No fake public `System`, `System.IO`, or threading package exists, and no
mapping support object changes the XNA type count.

## Storage Begin/End and callbacks

- All four BeginShowSelector overloads and EndShowSelector are implemented,
  as are BeginOpenContainer and EndOpenContainer.
- Each opaque token retains user state, operation kind, native result
  ownership, originating device when applicable, Game host/generation,
  completion, and one-End state. Wrong End method, wrong device, double End,
  forged/foreign token, unrelated operation, failed Begin, and expired
  generation are rejected without leaking a native pointer.
- CNA 0.7 completes these fake-async operations synchronously. Its completion
  trampoline is required to fire exactly once before native return; the user
  callback then receives the exact token consumed by End. Callback exceptions
  cannot cross C. Off-owner event callbacks enter the shared
  FrameworkDispatcher queue; there is no Storage dispatcher.

## Storage filesystem, streams, containment, and events

- FreeSpace, TotalSpace, IsConnected, selector/device ownership,
  DeleteContainer, all container CRUD, both name-enumeration overloads, all
  three OpenFile overloads, and stream operations use canonical CNA Storage
  routes. Python never substitutes `os` or `pathlib` filesystem work.
- The stream facade exposes only supported read, write, seek/tell, length,
  truncate, flush, close/closed, capability, and context-manager operations.
  The native stream is released exactly once.
- Containment validation precedes CNA: empty/NUL names, Unix absolute paths,
  Windows drives, mixed-separator escape, lexical `..`, resolved escape, and
  symlink escape are rejected. This deliberately closes CNA 0.7's traversal
  mismatch while leaving actual I/O native.
- CNA wildcard routes supply `*`, `?`, extension matching, native case/order,
  and empty results; nested separators and invalid patterns are validated at
  the mapped boundary rather than silently adopting Python glob behavior.
- FileShare flags reach the exact ABI, but CNA's current StorageContainer does
  not enforce sharing locks. This is documented as `UPSTREAM_CNA_BLOCKED`.
- Ownership is Game -> retained StorageDevice lease -> StorageContainer ->
  native stream. Reverse-order release, failed Begin/open rollback,
  parent/child order, open-stream container disposal, double close/Dispose,
  shutdown, and recreation are stress-qualified.
- StorageContainer.Disposing uses the real native callback, is exactly once,
  and handles duplicate handlers, self-removal, reentrancy, and double Dispose.
  DeviceChanged has one strong native subscription and shared owner-thread
  delivery. Registration is `VERIFIED_NATIVE`; a real OS attach/remove event is
  `PLATFORM_PENDING` and is never fabricated.
- CNA deterministically selects its configured storage root without presenting
  UI. The storage operation is `VERIFIED_NATIVE`; selector UI is
  `PLATFORM_PENDING`.
- `StorageDeviceNotConnectedException` implements (), (message), and (message,
  innerException); invalid/disconnected device state maps precisely while
  unrelated I/O errors remain their real categories.

## Behavior corpus

```text
                         M8 START  M8 FINAL
OBSERVATIONS                   167       171
ASSERTIONS                     925       986
FAILURES                         0         0

TOUCH_NEW_OBSERVATIONS=4
PROVENANCE=PURE_XNA_DERIVED
```

The new groups cover GestureType bits, GestureSample values, TouchLocation
equality/previous-location behavior, TouchCollection, and enumerator
boundaries. HEADLESS query counts, absent touch hardware, storage selector
results, CNA errors, and platform events are intentionally excluded from XNA
golden data. The generated report remains green at 171/986.

## ABI

```text
                               M8 START  M8 FINAL
BOUND_FUNCTIONS                       471       542
CTYPES_SIGNATURE_MEASUREMENTS         471       542
C_LAYOUT_MEASUREMENTS                 708       756
CTYPES_LAYOUT_MEASUREMENTS            708       756
MISSING_SYMBOLS                         0         0
ABI_MISMATCHES                          0         0
ABI=0.7.0 / 0x00000700
```

All new enums, structures, fixed-width fields, callback prototypes, pointer
depths, argtypes, restypes, ownership, and result lifetimes are measured
against canonical C headers. Only used FrameworkDispatcher, GamerServices,
OcclusionQuery, RenderTargetCube/binding, Touch, and Storage routes were added.
No Media function, C++ ABI, ctypes default signature, raw handle, or public FFI
surface was introduced.

Qualified artifact:

```text
CNA revision=a09196a6477f69a7a57c8364f990658d31531a5b
Sharp Runtime revision=625476d5b5fff5fa89f392c3c9af8638ff237692
library SHA256=c62949d23d3745964f5e557a06665875621ed4cb6e2930e3f282afd5911f2dcb
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
```

CNA's unrelated static-archive aggregation target failed after this exact
shared library had successfully linked because its generated `link.txt` was
absent. The shared artifact itself passes every 542-function/756-layout ABI
measurement. CNA remained read-only.

## Ownership and native stress

```text
FRAMEWORK_DISPATCHER_CYCLES=20
GAMERSERVICES_INITIALIZE_CYCLES=20
GAMERSERVICES_COMPONENT_CYCLES=20
OCCLUSION_QUERY_CYCLES=20
RENDERTARGET_CUBE_CYCLES=20
RENDERTARGET_CUBE_FAILURE_CYCLES=20
TOUCH_STATE_CYCLES=20
TOUCH_GESTURE_EMPTY_CYCLES=20
STORAGE_DEVICE_CYCLES=20
STORAGE_CONTAINER_CYCLES=20
STORAGE_STREAM_CYCLES=20
STORAGE_CALLBACK_CYCLES=50
STORAGE_FAILURE_CYCLES=21
WRONG_THREAD_REFUSAL_CYCLES=2
GAME_RECREATION_CYCLES=20
NATIVE_CRASHES=0
OBSERVED_UAF=0
DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

All earlier native Game/Graphics, Content, Effect/Model, and Audio ownership
stress suites also pass at their required cycle counts. The Game runtime root
strongly retains native children until legal reverse-order destruction, so an
unreachable Python wrapper cannot strand a CNA handle past its device/Game
generation.

## Runtime capabilities

The inventory has 96 granular rows:

```text
VERIFIED_NATIVE=53
VERIFIED_MANAGED=10
UPSTREAM_CNA_BLOCKED=10
BACKEND_BLOCKED=11
HARDWARE_PENDING=4
PLATFORM_PENDING=3
ASSET_PENDING=3
LANGUAGE_MAPPING_LIMITATION=2
UNIMPLEMENTED_CNA_PYTHON_FOR_M8=0
```

Milestone 8's blockers/pending rows are kept separate: dispatcher without
Game, ContentLost transitions, bound-target CNA destruction, FileShare
enforcement, broader GamerServices, physical Touch, positive gestures,
selector UI, and real DeviceChanged transitions. See
`docs/runtime-capabilities.json` for operation-level evidence.

## Tests and package

```text
COMPILEALL=PASS
UNITTESTS=133 total, 131 pass, 2 optional-fixture skips
VERIFIER_SELF_TESTS=6 PASS
FOCUSED_M8_TEST_METHODS=5 PASS
STRICT_REPORT=PASS
LEAK_ONLY=PASS
STRICT_CHECK=EXPECTED_NONZERO_ONLY_FOR_MEDIA_24
BEHAVIOR=171 observations / 986 assertions / 0 failures
RUNTIME_CAPABILITY_GENERATOR=96 PASS
ABI_AUDIT=542 signatures / 756 layouts / 0 mismatches
```

Version remains `0.1.0.dev0`. Final artifacts:

```text
WHEEL_FILENAME=cna_python-0.1.0.dev0-py3-none-any.whl
WHEEL_SHA256=228274ac77ca5286750adb396eb559e4f30132fdc8c39fb5a74acac0c296ed27
WHEEL_FILES=73
WHEEL_ENTRIES=73
SDIST_FILENAME=cna_python-0.1.0.dev0.tar.gz
SDIST_SHA256=fec2e15775d46947315107eee5fe6d3a8d5d3b4edd59560569a123d44ffbbd7e
SDIST_FILES=165
SDIST_ENTRIES=165
FORBIDDEN_WHEEL_ENTRIES=0
FORBIDDEN_SDIST_ENTRIES=0
ABSOLUTE_DEVELOPER_PATHS=0
BUNDLED_NATIVE_LIBRARIES=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0
```

The exact final wheel passes fresh-venv import and compile probes. The generated
consumer passes 60/600 real CNA frames with zero developer paths, sibling
source dependencies, or PYTHONPATH source dependencies.

The maintained template source was not changed. Its exact-wheel import,
compile, 60-frame, and 600-frame gates pass with `PYTHONPATH` unset. In this
sandbox its unchanged tree was copied to a writable temporary directory for
the native XNB run because Sharp Runtime currently opens a read-only content
file with read-write access; no template source or asset bytes changed.

```text
TEMPLATE_SOURCE_CHANGED=NO
MAINTAINED_IMPORT=PASS
MAINTAINED_COMPILE=PASS
MAINTAINED_60=PASS
MAINTAINED_600=PASS
GENERATED_IMPORT=PASS
GENERATED_COMPILE=PASS
GENERATED_60=PASS
GENERATED_600=PASS
PYTHONPATH=UNSET
```

## Remaining boundary

The regenerated missing inventory is exactly:

```text
Microsoft.Xna.Framework.Media.Album
Microsoft.Xna.Framework.Media.AlbumCollection
Microsoft.Xna.Framework.Media.Artist
Microsoft.Xna.Framework.Media.ArtistCollection
Microsoft.Xna.Framework.Media.Genre
Microsoft.Xna.Framework.Media.GenreCollection
Microsoft.Xna.Framework.Media.MediaLibrary
Microsoft.Xna.Framework.Media.MediaPlayer
Microsoft.Xna.Framework.Media.MediaQueue
Microsoft.Xna.Framework.Media.MediaSource
Microsoft.Xna.Framework.Media.MediaSourceType
Microsoft.Xna.Framework.Media.MediaState
Microsoft.Xna.Framework.Media.Picture
Microsoft.Xna.Framework.Media.PictureAlbum
Microsoft.Xna.Framework.Media.PictureAlbumCollection
Microsoft.Xna.Framework.Media.PictureCollection
Microsoft.Xna.Framework.Media.Playlist
Microsoft.Xna.Framework.Media.PlaylistCollection
Microsoft.Xna.Framework.Media.Song
Microsoft.Xna.Framework.Media.SongCollection
Microsoft.Xna.Framework.Media.Video
Microsoft.Xna.Framework.Media.VideoPlayer
Microsoft.Xna.Framework.Media.VideoSoundtrackType
Microsoft.Xna.Framework.Media.VisualizationData
```

That is `Media=24`, with no non-Media remainder. Foundation Milestone 8 stops
here deliberately; Media/Video retains its separate process-global queue,
callback, and video-frame ownership architecture.
