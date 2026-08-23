# CNA-Python implementation plan

Status: real ABI-0.7 foundation and desktop 2D vertical slice implemented.

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
- [x] Implement substantial binary32-aware MathHelper, Vector2/3/4,
  Quaternion, Matrix, Color, Point, Rectangle, and GameTime behavior.
- [x] Implement exact Keys plus coherent keyboard, mouse, and gamepad state
  groups and real CNA polling.
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
- [x] Replace the sibling template with a desktop-only real CNA starter and a
  deterministic parameterized generator.
- [x] Build a wheel/sdist and verify a fresh installed-wheel generated consumer
  at 60 and 600 real Draw callbacks.

## Current measured boundary

- Strict target: 42/257 types and 796 mapped runtime members.
- Full strict check: intentionally red for missing and partial XNA surface.
- Zero-tolerance gate: unexpected types/members, private/native leaks, raw
  handles, and allowlist entries are all zero.
- Structural audit limitation: full interface, field-type, parameter-type,
  return-type, and generic comparison remains explicitly counted as unmeasured
  for 30 implemented classes; it is not reported as silently green.
- Native runtime evidence: Linux x86-64, CNA ABI 0.7.0, HEADLESS renderer, NULL
  audio artifact. No GPU output, physical input, windowing, or audio claim.

## Next dependency-complete milestones

1. Complete stub-backed field/parameter/return/interface/generic verification,
   then remove `UNMEASURED_STRUCTURAL_CATEGORY` diagnostics family by family.
2. Complete the currently partial pure values before adding more shells:
   Matrix/Quaternion/Vector overloads, Plane, Ray, bounds, frustum, containment,
   and intersection behavior with a larger pinned corpus.
3. Complete input contracts: capabilities, vibration, all equality/hash/string
   behavior, mouse window association, and hardware-qualified observations.
4. Complete the remaining GraphicsDevice/SpriteBatch overload dependencies and
   graphics state value groups.
5. Design and implement a coherent ContentManager/XNB reader slice using CNA's
   real typed content and foreign-reader routes; keep `Load` explicit until
   then.
6. Add effects/3D only as one complete chain: native effects and passes,
   vertex/index buffers, bindings, and indexed drawing. Never restore the fake
   cube path.
7. Add audio/media/storage/touch in dependency order with owner-thread queues
   for native callbacks that can originate on arbitrary threads.
8. Qualify Linux windowed/GPU, then Windows and macOS independently. Do not
   infer support from CNA or another binding.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
