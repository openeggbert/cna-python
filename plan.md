# CNA-Python implementation plan

Status: Foundation Milestone 6 complete: the Audio/XACT implementation,
structural, behavior, ABI, ownership, package, isolated exact-wheel, and
maintained/generated 60/600-frame gates are green.

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
- [x] Refresh structural, behavior, runtime-capability, ABI, ownership, package,
  and isolated installed-wheel evidence.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 180 types and 1,772 strict runtime members.
- Diagnostics: 77 total, all whole missing types. Missing members and partial
  types are zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. The full strict check remains intentionally red only for future types.
- Type status: 180 complete, 0 partial, 77 missing. Every Audio type has zero
  local diagnostics.
- Native manifest: 471 exact ABI-0.7 functions, 471 signature measurements,
  708 C and 708 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 119 PURE_XNA_DERIVED observations, 538 assertions, zero
  failures.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Native
  SoundEffect construction/instance/3D routes, copied dynamic queues,
  BufferNeeded dispatch, zero-device microphone enumeration, and XACT failure
  rollback are verified. Audible output, microphone capture, and authored XACT
  playback are not inferred from this environment.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Foundation Milestone 6 evidence

- [x] The exact 19-type Audio closure is complete. FrameworkDispatcher remains
  absent because no Audio signature requires it and Game already owns the one
  correctly ordered native dispatcher pump.
- [x] Enum, mutable listener/emitter, RendererDetail, exception hierarchy, and
  contextual nullability/mutable-buffer projection rules are measured.
- [x] SoundEffect raw PCM16 and RIFF/WAVE constructors, process-global values,
  Play/CreateInstance, XNA binary32 sample arithmetic, and ownership are real.
- [x] SoundEffectInstance native state/transport/mixing, cached post-disposal
  properties, validation, looping, and single-listener Apply3D are verified.
  Multi-listener mixing is explicitly `UPSTREAM_CNA_BLOCKED` by ABI 0.7.
- [x] DynamicSoundEffectInstance uses CNA-copied submissions and the native
  pending queue. BufferNeeded is strongly rooted, owner-thread checked,
  exception-contained, and unsubscribed before destruction.
- [x] Microphone All/Default and zero-device enumeration are native. The full
  index API and callback lifetime are implemented; capture is
  `HARDWARE_PENDING` on the qualified host.
- [x] AudioEngine, RendererDetail, AudioCategory, WaveBank, SoundBank, and Cue
  are complete with child-before-parent ownership. Renderer/look-ahead are
  explicit upstream blockers; successful authored playback is `ASSET_PENDING`.
- [x] Dedicated 20-cycle resource/failure groups and 50 callback cycles have
  zero native crashes, observed UAF, or double-free. Sanitizers were not run.
- [x] Final package, isolated exact-wheel, and maintained/generated 60/600-frame
  evidence is green; archive hashes and exact consumer results are in `NEXT.md`.

## Dependency boundary after Milestone 6

No follow-on family is started. The remaining 77 whole types are Curve plus
FrameworkDispatcher (7), Design (13), GamerServices (1), unrelated Graphics
(2), PackedVector (19), Touch (8), Media (24), and Storage (3). A later
milestone must select one coherent dependency closure rather than optimize the
type count.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
