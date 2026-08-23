# CNA-Python implementation plan

Status: Foundation Milestone 3 complete: Game object model and 2D graphics
device/state/resource foundation over the exact CNA C ABI 0.7 runtime.

Date: 2026-08-23.

This is the normative current-state plan. Missing XNA surface stays visible in
the strict verifier; no allowlist, fake backend state, or placeholder class is
an acceptable way to make it green.

## Completed foundation

- [x] Pin and measure the seven-assembly XNA 4.0 Windows runtime projection:
  257 types, 2,964 CLR members, and 2,887 mapped Python members.
- [x] Implement the exact ABI-0.7 ctypes loader, callback exception boundary,
  OWNED/BORROWED/PARENT_OWNED lifetime model, and child-before-parent shutdown.
- [x] Complete the selected math/value, geometry/intersection, and non-touch
  input foundations with XNA binary32 behavior and zero local diagnostics.
- [x] Complete `Game`, components, component collections, per-Game services,
  launch parameters, and `GameWindow`. Component update/draw traversal uses
  stable snapshot ordering and exact event infrastructure.
- [x] Route `ResetElapsedTime` and `SuppressDraw` to the active native Game.
  HEADLESS activation, resize, and orientation transitions are never invented.
- [x] Complete graphics enums and value dependencies, including all selected
  `SurfaceFormat` values and binary32 `Viewport.Project`/`Unproject`.
- [x] Complete adapter/display/presentation/device-information facades with
  native discovery and XNA-derived presentation defaults/copy behavior.
- [x] Complete `GraphicsResource` identity, name/tag, exactly-once disposing
  events, idempotent disposal, and native subscription lifetime.
- [x] Complete blend/depth-stencil/rasterizer/sampler state descriptors, stock
  instances, XNA defaults, and post-bind freeze behavior.
- [x] Complete durable pixel/vertex sampler and texture collections with fixed
  stage counts, validation, and stable Python resource identity.
- [x] Complete texture metadata, Color transfer, and CNA-backed PNG/JPEG
  encoding with caller-stream rollback on failed writes.
- [x] Complete vertex declarations, the four selected built-in vertex values,
  deterministic explicit byte codecs, static/dynamic vertex and index buffers,
  binding facades, transfer validation, and bound-resource lifetime guards.
- [x] Complete `RenderTarget2D` creation/binding/query and render-target binding
  identity. Visible rendering remains hardware-pending under HEADLESS.
- [x] Complete the selected `GraphicsDevice` contract: states, collections,
  buffer/target bindings, real draw dispatch, back-buffer readback, Present,
  Reset, and event infrastructure. Unsupported ABI/backend operations raise
  explicit capability/native errors.
- [x] Complete `GraphicsDeviceManager` selection and lifecycle hooks using real
  CNA creation/reset/preparing-settings transitions.
- [x] Complete `SpriteFont` metrics through a safe private glyph factory and all
  selected `SpriteBatch.DrawString` overloads using actual glyph submissions.
  Public font loading remains part of future Content/XNB work.
- [x] Add machine-readable runtime capability status and generated human
  documentation, separate from the structural verifier.
- [x] Expand ABI verification, behavior corpus, ownership stress, stubs,
  package audit, and isolated 60/600-frame installed-wheel consumers.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 115 types and 1,465 strict runtime members.
- Diagnostics: 144 total = 142 missing types + 2 missing members. Every mismatch,
  leak, allowlist, and unmeasured category is zero. The full strict check remains
  intentionally red for genuine missing XNA surface.
- Type status: 114 complete, 1 partial, 142 missing. The sole partial type is
  `Microsoft.Xna.Framework.Content.ContentManager`, missing `OpenStream` and
  `ReadAsset` only.
- Native manifest: 186 exact ABI-0.7 functions, 186 signature measurements,
  526 C and 526 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 98 `PURE_XNA_DERIVED` observations, 413 assertions, zero
  failures.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Native command
  paths are verified; no visible GPU, physical input device, OS window, device
  loss, or sanitizer claim is inferred from HEADLESS.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Next dependency-complete milestone

1. Scope Content/XNB separately and implement the complete reader architecture:
   title-content path rules, `OpenStream`, `ReadAsset`, `ContentReader`, reader
   manager/type readers, shared resources, external references, and LZX only
   when the dependency chain requires it. Do not reduce this to a texture-only
   loader or process-CWD convention.
2. Use that Content foundation to make SpriteFont public loading real and then
   qualify resource creation/destruction identity only if CNA supplies stable
   event payloads.
3. Qualify the completed graphics command paths on a Linux windowed/GPU backend;
   keep DeviceLost, visible render targets, instancing, and window events in the
   runtime capability inventory until directly observed.
4. Defer effects/models, audio/media, storage, touch, Texture3D/Cube, and broad
   3D until their own dependency-complete milestones.

The optional six-type Curve family remained deferred. It is still a coherent
pure family, but it did not displace the mandatory Game/graphics architecture.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
