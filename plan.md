# CNA-Python implementation plan

Status: Foundation Milestone 9 complete. The selected XNA 4.0 Windows runtime
projection is structurally complete; the repository is now in maintenance and
runtime/platform qualification mode.

Date: 2026-08-24.

This is the normative current-state plan. Missing XNA surface stays visible in
the strict verifier; no allowlist, fake backend state, fabricated asset, or
asset-name special case is an acceptable way to make it green.

## Completed foundation

- [x] Pin and measure the seven-assembly XNA 4.0 Windows projection: 257 types,
  2,964 CLR members, and 2,887 mapped Python members.
- [x] Implement the exact ABI-0.7 ctypes loader, callback exception boundary,
  OWNED/BORROWED/PARENT_OWNED lifetime model, and child-before-parent shutdown.
- [x] Complete core math/value, geometry/intersection, non-touch input, Game,
  components, services, window, and the selected 2D graphics foundation.
- [x] Complete Texture2D, render targets, buffers/declarations, SpriteBatch,
  SpriteFont, Content/XNB with LZX, custom readers, shared resources, external
  references, cache/rollback/Unload, and title-path integration.
- [x] Complete Effect reflection and typed codecs, five native stock Effects,
  Texture3D/Cube exact routes, EffectPass.Apply, the Model graph, uncompressed
  and compressed Model XNB, and ordinary indexed Model.Draw.
- [x] Complete all 19 Audio types with real SoundEffect, instance, dynamic,
  microphone, AudioEngine, category, bank, and cue ABI routes.
- [x] Complete all six Curve types with exact ordering, tangent, Hermite,
  loop, clone, collection, and binary32 behavior.
- [x] Complete both PackedVector interfaces and all seventeen concrete packed
  structs with fixed-width storage and XNA-exact bit conversion.
- [x] Complete all thirteen Design converters through a formal Python-native,
  locale-independent TypeConverter projection.
- [x] Complete FrameworkDispatcher, GamerServicesComponent, OcclusionQuery,
  RenderTargetCube, all eight Touch types, and all three Storage types with
  real ABI routes, one dispatcher, exact ownership, and formal BCL mappings.
- [x] Complete all 24 Media/Video types with native catalog collections and
  identity, MediaLibrary/provider ownership, Song, synchronized process-global
  MediaPlayer and generation-scoped MediaQueue/events, VisualizationData,
  private Video XNB loading, VideoPlayer, and a non-owning GetTexture policy.
- [x] Refresh structural, behavior, runtime-capability, ABI, ownership, package,
  and isolated installed-wheel evidence.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 257 types and 2,423 strict runtime members.
- Diagnostics: zero. Missing members, missing types, and partial types are zero;
  every mismatch, leak, allowlist, and unmeasured category is zero. Normal and
  leak-only strict checks pass.
- Type status: 257 complete, 0 partial, 0 missing.
- Native manifest: 744 exact ABI-0.7 functions, 744 signature measurements,
  775 C and 775 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 181 PURE_XNA_DERIVED observations, 1,004 assertions, zero
  failures, including 10 Media observations.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Native
  SoundEffect construction/instance/3D routes, copied dynamic queues,
  BufferNeeded dispatch, zero-device microphone enumeration, and XACT failure
  rollback are verified. Audible output, microphone capture, and authored XACT
  playback are not inferred from this environment.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Foundation Milestone 8 evidence

- [x] Public FrameworkDispatcher calls the same single native pump as Game;
  explicit calls are additional and callback failures reappear only after C.
- [x] GamerServicesComponent passes the Game window and preserves the exact
  Initialize/Update base order without projecting the wider ecosystem.
- [x] OcclusionQuery completes two real native cycles under HEADLESS; query
  state, PixelCount timing, disposal, wrong-thread refusal, and recreation are
  verified.
- [x] RenderTargetCube preserves every constructor argument, TextureCube
  inheritance, all six binding faces, current content-loss state, and a safe
  explicit guard around CNA's bound-destruction abort path.
- [x] Touch values/collection/nested enumerator are XNA-derived; TouchPanel uses
  native state and configuration without claiming physical hardware.
- [x] Storage has formal async, callback, FileMode/FileAccess/FileShare, and
  stream mappings; every filesystem operation uses CNA, while Python enforces
  XNA containment before CNA's traversal gap.
- [x] The dedicated Milestone 8 stress and every earlier ownership stress pass
  with zero crash, observed UAF, or double-free. See
  `docs/milestone8-evidence.md` and `NEXT.md`.

## Foundation Milestone 9 evidence

- [x] All exact 24 Media types and 204 mapped XNA contract members are present;
  collection protocol projections yield 2,423 measured target members.
- [x] MediaLibrary and its seven collections use the real CNA provider graph,
  stable facade identity, native ordering, explicit disposal, and Game-
  generation teardown without filesystem catalog substitution.
- [x] MediaPlayer uses one synchronized process-global manager, one queue facade
  per Game generation, real transport, and native events delivered through the
  existing owner-thread FrameworkDispatcher queue.
- [x] VisualizationData's 2,056-byte C/ctypes shape and native route are exact;
  public buffers are immutable tuples and no data is synthesized.
- [x] Video uses the ordinary Content/XNB cache/rollback/Unload architecture;
  VideoPlayer has operation-specific disposed behavior and never owns CNA's
  transient frame texture.
- [x] Media/Video stress passes all required 20-cycle groups and 50 callback
  deliveries with zero crash, observed UAF, or double-free. See
  `docs/media-video-evidence.md`.

## Post-zero boundary

There is no remaining selected-profile family. Large feature implementation is
stopped. Current work is maintenance, runtime/platform qualification, upstream
CNA blocker reconciliation, packaging/release qualification, and real-game
compatibility testing. Net, wider GamerServices/Avatar, Content Pipeline, Xbox,
and Windows Phone remain unopened future-profile decisions.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
