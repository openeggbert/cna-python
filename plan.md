# CNA-Python implementation plan

Status: Foundation Milestone 2 complete: measured core value/geometry/input
foundation over the real ABI-0.7 runtime.

Date: 2026-08-23.

This is the normative current-state plan. Missing XNA surface stays visible in
the strict verifier; no allowlist or placeholder class is an acceptable way to
make it green.

## Completed foundation

- [x] Pin the seven-assembly XNA 4.0 Windows runtime profile: 257 types and
  2,964 members.
- [x] Define the XNA-to-Python mapping, including PascalCase public identity,
  binary32 arithmetic, fixed integers, overloads, value copies, events,
  streams, and disposal.
- [x] Split namespace initializers from private math, geometry, lifecycle,
  graphics, input, content, ABI, loader, error, and ownership modules.
- [x] Replace `_cna_native.require_available()` with an exact ABI-0.7 ctypes
  loader using explicit signatures and deterministic absolute-path resolution.
- [x] Audit all selected imports against ELF exports and C/ctypes layouts.
- [x] Contain callback exceptions inside C trampolines and rethrow them from a
  safe Python boundary.
- [x] Implement one OWNED/BORROWED/PARENT_OWNED state model, idempotent
  `Dispose`, context managers, child-before-parent teardown, and no CNA calls
  from interpreter finalizers.
- [x] Complete MathHelper, Vector2/3/4, Quaternion, Matrix, Color, Point,
  Rectangle, and GameTime to local structural zero with XNA binary32 operation
  ordering, edge values, hashes, strings, overloads, and copy behavior.
- [x] Complete ContainmentType, PlaneIntersectionType, Plane, Ray,
  BoundingBox, BoundingSphere, and BoundingFrustum, including all selected
  containment/intersection combinations and frustum convex/GJK routes.
- [x] Complete the non-touch keyboard, mouse, and gamepad families, add
  GamePadCapabilities/GamePadType, preserve real CNA polling, and bind real
  mouse-window, capabilities, and vibration routes.
- [x] Implement real Game callbacks, timing properties, exit, callback failure
  propagation, recreation, and shutdown.
- [x] Implement real GraphicsDeviceManager, viewport get/set/title-safe-area,
  Clear(Color), Texture2D decode/Color transfer, and the template's real
  SpriteBatch overload.
- [x] Delete fabricated ContentManager texture loads, BasicEffect.Apply,
  DrawRect, fake hardware, and identity-returning matrix behavior.
- [x] Ship checked `.pyi` files and `py.typed` in the wheel.
- [x] Add strict report/check/leak-only modes, deterministic scoreboards,
  missing-type inventories, and deliberately broken verifier fixtures.
- [x] Make shipped `.pyi` files the measured overload/type/generic contract;
  measure fields, properties, callables, nullability, ref/out, interfaces,
  generics, language rules, and runtime/stub consistency. All structural
  mismatch counters and `UNMEASURED_STRUCTURAL_CATEGORY` are zero.
- [x] Expand the `PURE_XNA_DERIVED` core corpus from 16/35 to 92 observations /
  360 scalar assertions, including exact binary32 golden bits, NaN/infinity,
  singular/degenerate geometry, hashes, transforms, and frustum GJK cases.
- [x] Replace the sibling template with a desktop-only real CNA starter and a
  deterministic parameterized generator.
- [x] Build a wheel/sdist and verify a fresh installed-wheel generated consumer
  at 60 and 600 real Draw callbacks.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 51 types and 1,003 strict runtime members.
- Diagnostics: 310 total = 206 missing types + 104 missing members. All other
  categories, including overload and unmeasured structural categories, are
  zero. The full strict check therefore remains intentionally red.
- Type status: 41 complete, 10 partial, 206 missing. Every core math/value,
  geometry/intersection, and non-touch input type selected for this milestone
  is locally zero-diagnostic. Touch was not started.
- Zero-tolerance gate: unexpected types/members, private/native leaks, raw
  handles, public FFI leaks, and allowlist entries are all zero.
- Native manifest: 59 exact ABI-0.7 functions, 59 ctypes signature
  measurements, 210 C and 210 ctypes layout measurements, zero missing symbols
  and zero ABI mismatch.
- Native runtime evidence: Linux x86-64, CNA ABI 0.7.0, HEADLESS renderer, NULL
  audio artifact. Routes are verified; no GPU output, physical-controller,
  window-system, sanitizer, or audio claim is made.

## Next dependency-complete milestones

1. If continuing the pure foundation, implement Curve, CurveContinuity,
   CurveKey, CurveKeyCollection, CurveLoopType, and CurveTangent as one complete
   family. Do not expose a partial subset.
2. Complete the remaining GraphicsDevice/SpriteBatch overload dependencies and
   graphics state value groups.
3. Design and implement a coherent ContentManager/XNB reader slice using CNA's
   real typed content and foreign-reader routes; keep `Load` explicit until
   then.
4. Add effects/3D only as one complete chain: native effects and passes,
   vertex/index buffers, bindings, and indexed drawing. Never restore the fake
   cube path.
5. Add audio/media/storage/touch in dependency order with owner-thread queues
   for native callbacks that can originate on arbitrary threads.
6. Qualify Linux windowed/GPU, then Windows and macOS independently. Do not
   infer support from CNA or another binding.

The optional Curve family was not started. It remains a coherent pure-value
candidate, but it must not displace the next dependency-complete milestone or
be split into partial shells.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
