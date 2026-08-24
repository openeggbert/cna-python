# CNA-Python implementation plan

Status: Foundation Milestone 8 complete. Every selected non-Media runtime
family is dependency-complete and honestly qualified; only Media/Video remains.

Date: 2026-08-23.

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
- [x] Refresh structural, behavior, runtime-capability, ABI, ownership, package,
  and isolated installed-wheel evidence.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 233 types and 2,174 strict runtime members.
- Diagnostics: 24 total, all whole missing Media types. Missing members and partial
  types are zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. The full strict check remains intentionally red only for future types.
- Type status: 233 complete, 0 partial, 24 missing. Every Milestone 8 type has
  zero local diagnostics.
- Native manifest: 542 exact ABI-0.7 functions, 542 signature measurements,
  756 C and 756 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 171 PURE_XNA_DERIVED observations, 986 assertions, zero
  failures.
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

## Dependency boundary after Milestone 8

No Media family was started. The exact remaining 24 whole types are all Media;
that final milestone retains its distinct process-global queue, callback, and
video-frame ownership architecture.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
