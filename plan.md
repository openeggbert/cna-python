# CNA-Python implementation plan

Status: the selected XNA 4.0 Windows projection is structurally complete and the
native boundary has been migrated from the historical CNA C ABI `0.7.0` to the
current `0.21.0`, requalified on two artifacts including a real rendering
renderer. A first CNA extension profile is open.

Date: 2026-09-01.

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

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 257 types and 2,423 strict runtime members.
- Diagnostics: zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. Normal and leak-only strict checks pass.
- Native manifest: 765 imported routes, 765 compiler-verified prototypes, 796 C
  and 796 ctypes layout measurements, zero missing symbols, zero ABI mismatches.
- Route census: 4,055 canonical routes, zero unreviewed, zero actionable-local.
- Behavior evidence: 181 PURE_XNA_DERIVED observations, 1,004 assertions, zero
  failures.
- Runtime evidence: two artifacts. A non-windowed control and an OPENGLES3
  renderer on an isolated display, both with a real SDL3 mixer on a deterministic
  device. Every capability row names the artifact that produced it.
- Extension profile: `cna.extensions.graphics`, zero surface diagnostics, and no
  dependency from the XNA namespace on it.

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
future-profile decisions; CNB/CNJ native content, the engine layer, sensors and
device services remain unopened extension decisions, each recorded in the census
with its reason.
