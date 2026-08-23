# CNA-Python implementation plan

Status: Foundation Milestone 5 complete: implementation, native, Content/XNB,
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
- [x] Complete Texture2D, render targets, buffers/declarations, SpriteBatch, and
  SpriteFont runtime metrics/DrawString through ordinary native ownership.
- [x] Define the formal Python mappings for BinaryReader composition,
  ResourceManager adapters, the generic/non-generic ContentTypeReader name
  collision, and erased runtime generic type tokens.
- [x] Complete all selected public Content types and TitleContainer with zero
  local structural diagnostics.
- [x] Resolve title content beneath one deterministic application root. Active
  Games use CNA title-location/read routes; managed opens use the same lexical
  and symlink-containment policy. Neither route falls back to process CWD.
- [x] Implement XNB Windows version 5 header validation, exact little-endian
  primitive decoding, reader tables, version checks, initialization ordering,
  exact built-in/custom-reader resolution, and chained ContentLoadException
  failures.
- [x] Implement existing-instance reads, deferred shared-resource fixups,
  normalized external references, circularity rejection, cache identity,
  failed-load rollback, reverse Unload, and idempotent Dispose.
- [x] Implement private primitive/value, collection, nullable, Texture2D,
  SpriteFont, VertexDeclaration, VertexBuffer, IndexBuffer, BasicEffect, and
  Model readers over ordinary public/native resource construction.
- [x] Implement XNA compressed-XNB framing and a persistent managed 64 KiB LZX
  decoder, including single/multi-frame, short/extended headers, exact output,
  malformed inputs, independent fixture comparison, and compressed native
  resource/external-reference graphs.
- [x] Make public SpriteFont Content loading real through the existing factory
  and validate MeasureString, DrawString, atlas lifetime, cache, and Unload.
- [x] Add a small legal synthetic Texture2D XNB canary to the maintained and
  generated template alongside the existing raw PNG canary.
- [x] Refresh structural, behavior, runtime-capability, ABI, ownership, package,
  and isolated installed-wheel evidence.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 161 types and 1,651 strict runtime members.
- Diagnostics: 96 total, all whole missing types. Missing members and partial
  types are zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. The full strict check remains intentionally red only for future types.
- Type status: 161 complete, 0 partial, 96 missing. Every selected Effect,
  Model, Texture3D, and TextureCube type has zero local diagnostics.
- Native manifest: 375 exact ABI-0.7 functions, 375 signature measurements,
  653 C and 653 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 111 PURE_XNA_DERIVED observations, 496 assertions, zero
  failures.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Effect state,
  stock Apply, Model XNB and indexed dispatch, Content ownership, and 60/600
  frame consumers are verified. No visible GPU, allocator-sanitizer, physical
  input, OS window, or device-loss claim is inferred from HEADLESS.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Current Milestone 5 evidence

- [x] Exact public Effect/Model dependency closure measured: 35 types,
  including the four collection enumerator projections and Texture3D/Cube.
- [x] Native ABI-0.7 Effect ownership/create/clone/apply/reflection routes
  imported with explicit ctypes signatures; qualified artifact audit is green.
- [x] Native stock-effect construction and effect apply are exercised against
  HEADLESS, with parent disposal invalidation and repeated-cycle coverage.
- [x] Model/Bone/Mesh/MeshPart graph and ordinary buffer/effect draw handoff
  are projected with stable collection identity and matrix-copy behavior.
- [x] Full selected typed EffectParameter getter/setter and read-only
  EffectAnnotation codec surfaces use real native reflection identities.
- [x] Texture3D/Cube exact ABI create/info/transfer/destruction routes are
  audited; HEADLESS creation/storage result-6 boundaries are repeated safely.
- [x] Dependency-complete uncompressed and compressed Model XNB readers use one
  legal synthetic graph with shared real buffers/BasicEffect, cache,
  Unload/reload, external-reference composition, rollback, and native draw.
- [x] Dedicated 20-cycle Effect, clone, parameter, parent/child, stock-effect,
  Model, compressed Model, draw, unload/reload, and volume-failure stress has
  zero crashes, observed UAF, or double-free. Sanitizers were not run.
- [x] Final package, isolated exact-wheel, and maintained/generated 60/600-frame
  evidence is green; archive hashes and exact final-wheel results are recorded
  in `NEXT.md` after the final reproducible build.

## Next dependency-complete architectural milestone

No follow-on family is started here. The next coherent boundary should be the
Audio runtime/content graph: SoundEffect and instances, dynamic streaming,
AudioEngine/WaveBank/SoundBank/Cue, microphone/capability boundaries, and
FrameworkDispatcher only where authoritative dependencies require it. That
choice is based on one ownership/playback/content architecture, not its type
count; Media, Storage, Curve, Touch, PackedVector, Design, GamerServices,
OcclusionQuery, and RenderTargetCube retain separate closures.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
