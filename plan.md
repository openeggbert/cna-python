# CNA-Python implementation plan

Status: the selected XNA 4.0 Windows projection is structurally complete, the
native boundary speaks the current CNA C ABI `0.21.0`, and two CNA extension
profiles are open. The second is CNA's own compiled content format, `.cnb`.

Date: 2026-09-02.

This is the normative current-state plan. Missing XNA surface stays visible in
the strict verifier; no allowlist, fake backend state, fabricated asset, or
asset-name special case is an acceptable way to make it green.

## Completed foundation

- [x] Pin and measure the seven-assembly XNA 4.0 Windows projection: 257 types,
  2,964 CLR members, and 2,887 mapped Python members.
- [x] Implement the exact ctypes loader, callback exception boundary,
  OWNED/BORROWED/PARENT_OWNED lifetime model, and child-before-parent shutdown.
- [x] Complete core math/value, geometry/intersection, non-touch input, Game,
  components, services, window, and the selected 2D graphics foundation.
- [x] Complete Texture2D, render targets, buffers/declarations, SpriteBatch,
  SpriteFont, Content/XNB with LZX, custom readers, shared resources, external
  references, cache/rollback/Unload, and title-path integration.
- [x] Complete Effect reflection and typed codecs, five native stock Effects,
  Texture3D/Cube exact routes, EffectPass.Apply, the Model graph, uncompressed
  and compressed Model XNB, and ordinary indexed Model.Draw.
- [x] Complete all 19 Audio types, all six Curve types, both PackedVector
  interfaces with seventeen concrete structs, and all thirteen Design converters.
- [x] Complete FrameworkDispatcher, GamerServicesComponent, OcclusionQuery,
  RenderTargetCube, all eight Touch types, and all three Storage types.
- [x] Complete all 24 Media/Video types with native catalog collections, Song,
  synchronized process-global MediaPlayer, generation-scoped MediaQueue/events,
  VisualizationData, private Video XNB loading, and VideoPlayer.

## Completed migration and requalification

- [x] Migrate the native boundary to CNA `0.21.0` with a version policy derived
  from CNA's own contract rather than a hard-coded constant.
- [x] Add compiler-backed prototype verification: every imported route's ctypes
  prototype is proven against the canonical C declaration by the C compiler,
  with planted defects proving the gate can fail.
- [x] Census all 4,055 canonical routes by purpose and binding status, with
  `UNREVIEWED = 0` and every non-binding carrying a written reason.
- [x] Gate route reachability from canonical declaration through to consumer,
  with `UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE = 0`; eight dead routes unbound.
- [x] Qualify a second artifact that actually rasterizes and produce
  rendered-pixel evidence for every draw path, SpriteBatch, render targets,
  Texture3D, TextureCube and Model.
- [x] Requalify all 119 runtime capability rows per artifact, closing five
  upstream blockers by measurement and confirming four unchanged.
- [x] Requalify audio against a real mixer, separating the verified state
  machine from audible output and physical capture, which remain unverified.
- [x] Open `cna.extensions` with renderer identity and a separate surface gate.

## Completed extension family: CNB/CNJ compiled content

- [x] Select CNB/CNJ as the second public `cna.extensions` family and replace the
  blanket "outside the selected profile" census rule with per-route decisions.
- [x] Bind 270 of `cnb.h`'s 272 routes, plus the two dependency slices the
  family needs: eleven `curve.h` routes for the curve codec and two `content.h`
  routes for loader invocation. The two unbound routes are checked integer
  arithmetic Python already does exactly.
- [x] Build `cna.extensions.content`: the container vocabulary, `CnbDocument`,
  the reader and both writers, every typed asset codec, the model graph, the
  source importers, `.cnj` compilation and the loader registry.
- [x] Keep the strict XNA `ContentManager` unchanged, with a test asserting it
  does not read a `.cnb` placed where it looks for a `.xnb`.
- [x] Measure every CNB structure and every frozen wire constant against the
  canonical headers with a compiler-backed probe.
- [x] Qualify every slice against an oracle other than its own decoder,
  including byte-identical agreement with CNA's own `cnj_to_cnb` tool across two
  OS processes.
- [x] Plant 35 defects across the family and kill all of them; four survivors on
  the first run were real test gaps and were closed.

## Completed extension family: the engine layer

- [x] Select `engine_layer.h` as the third public `cna.extensions` family and
  replace the blanket "outside the selected extension profile" census rule
  covering ~838 routes with per-family, per-route decisions.
- [x] Bind 867 of its 870 routes, plus three dependency slices: five routes for
  PBR effects and materials, eight for the ASCII effect, and two `models.h`
  routes to project a strict `ModelMeshPart` into the native handle
  level-of-detail and instancing demand. The three unbound routes are C
  ownership transfers that would invalidate a live Python facade.
- [x] Build `cna.extensions.engine` across fourteen modules: values, errors,
  compute, post-processing, the concrete passes, atmosphere, PBR, shadows,
  scene, the render pipeline, clustered lighting, light probes, culling and
  instancing, and debug drawing.
- [x] Keep `Microsoft.Xna.Framework` unchanged: no engine class or member enters
  it, the dependency runs extension -> strict only, and only private members
  were added to strict types (`Texture2D._view_of`, `RenderTarget2D._view_of`).
- [x] Generate the engine ABI -- structures, constants, callbacks and their
  parameter constness -- from the canonical headers rather than transcribing it,
  and measure every structure with a compiler-backed probe.
- [x] Qualify every family against an oracle other than its own getter, with the
  oracles themselves gated by hand-worked cases that touch no native library.
- [x] Plant 47 defects across the family and kill all of them; nine survivors on
  the first run were real test gaps and were closed.
- [x] Record eight upstream findings, each with a reproducer, expected against
  actual, the local behaviour and an unblock condition.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 257 types and 2,423 strict runtime members.
- Diagnostics: zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. Normal and leak-only strict checks pass.
- Native manifest: 1,917 imported routes, 1,917 compiler-verified prototypes,
  1,672 C and 1,672 ctypes layout measurements, zero missing symbols, zero ABI
  mismatches.
- Route census: 4,055 canonical routes, zero unreviewed, zero actionable-local,
  zero rule contradictions, zero shadowed or dead rules. Inside the selected
  CNB/CNJ family: 285 routes, 283 bound. Inside the selected engine family: 870
  routes, 867 bound. Both zero unreviewed and zero actionable-local.
- Behavior evidence: 181 PURE_XNA_DERIVED observations, 1,004 assertions, zero
  failures.
- Runtime evidence: two artifacts. A non-windowed control and an OPENGLES3
  renderer on an isolated display, both with a real SDL3 mixer on a deterministic
  device. Every capability row names the artifact that produced it.
- Extension profile: `cna.extensions.graphics`, `cna.extensions.content` and
  `cna.extensions.engine`, 33 modules and 648 public names, zero surface
  diagnostics, and no dependency from the XNA namespace on any of them.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity and contain
   only the selected XNA profile; private code is idiomatic Python, and CNA-only
   capability lives under `cna.extensions`.
3. A public operation reaches real behavior or throws an explicit, accurate
   error naming the measured reason. It never silently succeeds, fabricates
   state, or drops arguments.
4. Exact evidence is regenerated, attributed to the artifact that produced it,
   and missing surface remains visible.

## Post-zero boundary

There is no remaining selected-profile family and no actionable-local route.
Current work is maintenance, further platform qualification, upstream blocker
reconciliation, packaging/release qualification, real-game compatibility
testing, and deliberately selected extension families. Net, wider
GamerServices/Avatar, Content Pipeline, Xbox, and Windows Phone remain unopened
future-profile decisions; sensors and device services, and extended input,
remain unopened extension decisions, each recorded in the census with its
reason. CNB/CNJ and the engine layer are no longer among them: both are open and
finished, and `docs/cnb-cnj-extensions.md` and `docs/engine-extensions.md` are
their evidence.
