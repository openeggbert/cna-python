# Foundation Milestone 8 evidence

Status date: 2026-08-23.

Foundation Milestone 8 closes every selected non-Media runtime/platform family:
`FrameworkDispatcher`, `GamerServicesComponent`, `OcclusionQuery`,
`RenderTargetCube`, the eight Touch types, and the three Storage types. The
strict projection is 233 complete types with zero partial types or missing
members; the only 24 missing types are Media.

## Dispatcher and GamerServices

`FrameworkDispatcher.Update` calls the canonical Game-scoped
`cna_framework_dispatcher_update` route exactly once. The existing CNA Game
loop still performs its one automatic pump after a successful `Game.Update`;
no second automatic Python pump was added. An explicit call is an additional
pump. Python callbacks are first contained by their ctypes trampoline, queued
to the one Game owner, and re-raised only after native control returns. ABI 0.7
cannot implement XNA's no-live-Game process dispatcher because its route
requires a Game handle; the binding raises an explicit capability error.

`GamerServicesComponent` is an ordinary `GameComponent`. Initialize supplies
the Game window handle, calls the native dispatcher initialize route, then the
base lifecycle. Update calls the native dispatcher before the base lifecycle,
matching XNA IL. Twenty components each initialized and updated exactly once
in native stress. Gamer, Guide, Avatar, achievements, networking, and
leaderboards are outside the selected profile and were not fabricated.

## Graphics

`OcclusionQuery` is an owned `GraphicsResource` with XNA's exact five-state
bookkeeping: new, active Begin/End pair, submitted result, completion queried,
and reusable second cycle. End-before-Begin, Begin-twice, reuse without an
intervening IsComplete query, early PixelCount, and disposed access are
rejected at the same managed boundary. The qualified HEADLESS renderer creates
a real query and completes it deterministically; Python reads the native
completion and pixel count and does not encode that backend value as XNA
golden behavior. Twenty two-cycle create/dispose runs pass, including
wrong-thread refusal followed by owner-thread retry.

`RenderTargetCube` inherits `TextureCube`; both selected constructors pass
size, mip-map choice, preferred surface/depth formats, multisample count, and
usage to `cna_render_target_cube_create`. Native result information supplies
the selected properties. All six cube faces round-trip through ordinary
`GraphicsDevice.SetRenderTarget`, `SetRenderTargets`, `GetRenderTargets`, and
`RenderTargetBinding`; no special renderer exists.

ABI 0.7 exposes current `is_content_lost` state but no real dynamic-resource
loss callback, so ContentLost subscription is structurally complete and no
event is synthesized. CNA can abort when a bound render target is destroyed.
Python detects its retained binding before native destruction, raises an
explicit upstream-capability error, preserves the owned handle, and permits a
later legal owner-thread Dispose after the caller restores the backbuffer. It
never silently changes the render target. Twenty guarded/retry cycles pass.

## Touch

The managed layer implements exact GestureType bits, GestureSample fields and
TimeSpan mapping, TouchLocation's deliberately different `Equals` and `==`
semantics, previous-location sentinel, string/hash behavior, capabilities, and
TouchCollection's fixed eight-value read-only IList behavior. Public
collection boundaries copy struct values. The nested CLR enumerator is
`TouchCollection.Enumerator`, supports the selected MoveNext/Current/Dispose
contract and Python iteration, and is not exported as a top-level type.

TouchPanel uses only canonical CNA state, capability, gesture, display, and
window routes. EnabledGestures validates the exact ten-bit mask and preserves
XNA's process-static “gestures have been enabled” precondition.
DisplayOrientation accepts only Default, LandscapeLeft, LandscapeRight, or
Portrait; width and height preserve all Int32 values. WindowHandle is the
existing signed 64-bit IntPtr mapping and is attached to the current Game
generation, then cleared before that Game is destroyed. HEADLESS reports its
real disconnected empty state and empty gesture queue. Physical input is
hardware-pending and positive gesture recognition is platform-pending.

## Storage mapping and ownership

The formal language projection is recorded in `docs/xna-python-mapping.md` and
the verifier rules:

```text
System.IAsyncResult -> private opaque Python token, publicly object
System.AsyncCallback -> Callable[[object], None]
FileMode             -> one canonical snake-case str
FileAccess           -> one canonical snake-case str
FileShare            -> frozenset[str] flags; empty means None
System.IO.Stream     -> private capability-based binary stream facade
```

No public `System`, `System.IO`, or threading package exists. Tokens retain
state, operation kind, originating device, Game host/generation, native result
ownership, completion, and one-End state. Wrong operation, wrong device,
foreign/forged token, double End, and expired generation are rejected without
consuming a valid result. CNA's completion callback is observed exactly once
and synchronously; user callbacks run only after the native call returns, may
consume the same token, and cannot throw through C.

All four selectors, capacity/connection properties, container open/delete,
filesystem CRUD, wildcard enumeration, all three OpenFile routes, and stream
read/write/seek/tell/length/truncate/flush/capabilities/close use CNA. The
selector deterministically chooses CNA's configured storage device and does
not display OS UI; UI is platform-pending. FileShare reaches the exact ABI but
the CNA StorageContainer implementation ignores enforcement, an upstream CNA
blocker.

Containment rejects empty/NUL names, absolute Unix paths, Windows drive roots,
mixed-separator escapes, lexical parent escapes, and resolved/symlink escapes
before CNA dispatch. Contained normalization remains valid. This closes a
known CNA 0.7 traversal mismatch without replacing native filesystem work.

Ownership is Game -> StorageDevice lease -> StorageContainer -> native stream.
Parents strongly retain children; release is reverse-order and changes Python
state only after CNA accepts it. Container Dispose closes streams first,
requires the actual synchronous native Disposing callback when subscribed,
delivers duplicate/self-removing handlers exactly once per subscription,
unsubscribes, then destroys. Failures preserve handles for owner-thread retry.
DeviceChanged uses one native registration and the shared FrameworkDispatcher
queue; worker-thread trampoline delivery is qualified, while a real OS device
transition remains platform-pending.

## Regenerated evidence

```text
REFERENCE_TYPES=257
REFERENCE_MEMBERS=2964
EXPECTED_PYTHON_TYPES=257
EXPECTED_PYTHON_MEMBERS=2887
TARGET_TYPES=233
TARGET_MEMBERS=2174
TOTAL_DIAGNOSTICS=24
MISSING_TYPE=24
MISSING_MEMBER=0
PARTIAL_TYPES=0
ZERO_DIAGNOSTIC_TYPES=233

OBSERVATIONS=171
ASSERTIONS=986
FAILURES=0
PROVENANCE=PURE_XNA_DERIVED

BOUND_FUNCTIONS=542
CTYPES_SIGNATURE_MEASUREMENTS=542
C_LAYOUT_MEASUREMENTS=756
CTYPES_LAYOUT_MEASUREMENTS=756
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0
```

The exact ABI artifact is CNA revision
`a09196a6477f69a7a57c8364f990658d31531a5b`, built with the contemporaneous
Sharp Runtime revision `625476d5b5fff5fa89f392c3c9af8638ff237692`, Linux
x86-64 HEADLESS/NULL. Its shared-library SHA-256 is
`c62949d23d3745964f5e557a06665875621ed4cb6e2930e3f282afd5911f2dcb`.
The unrelated CNA static-archive aggregation target failed after the shared
library had linked because its generated `link.txt` was absent; this did not
alter or weaken shared-library ABI qualification.

Dedicated stress results:

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
GAME_RECREATION_CYCLES=20
NATIVE_CRASHES=0
OBSERVED_UAF=0
DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

All earlier native, Content, Effect/Model, and Audio ownership stresses also
remain green. The behavior corpus adds four pure-XNA Touch observations; CNA
query counts, empty hardware, selector behavior, and platform events remain
runtime evidence rather than XNA golden values.
