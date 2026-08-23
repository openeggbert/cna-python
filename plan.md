# CNA-Python implementation plan

Status: Foundation Milestone 4 complete: general-purpose Content/XNB, title
storage, shared/external object graphs, native resources, and managed LZX over
the exact CNA C ABI 0.7 runtime.

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
  SpriteFont, VertexDeclaration, VertexBuffer, and IndexBuffer readers. Effect
  and Model readers remain absent until their public object graphs exist.
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
- Strict target: 126 types and 1,501 strict runtime members.
- Diagnostics: 131 total, all whole missing types. Missing members and partial
  types are zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. The full strict check remains intentionally red only for future types.
- Type status: 126 complete, 0 partial, 131 missing. Every public Content type
  and TitleContainer has zero local diagnostics.
- Native manifest: 188 exact ABI-0.7 functions, 188 signature measurements,
  526 C and 526 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 108 PURE_XNA_DERIVED observations, 465 assertions, zero
  failures.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Content native
  resources and 60/600-frame command paths are verified; no visible GPU,
  physical input, OS window, allocator-sanitizer, or device-loss claim is
  inferred from HEADLESS.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Next dependency-complete architectural milestone

The next coherent asset/runtime boundary is the Effect + Model graph: public
Effect parameter/technique/pass types, stock effects, Model/Mesh/MeshPart, their
graphics dependencies, and then their exact XNB readers. Content now provides
the resolver and ownership extension points required for that graph, but no
Effect or Model implementation was started here.

Do not select the next work merely by smallest type count. Curve, touch,
PackedVector, audio/media, storage, design, gamer services, Texture3D/Cube, and
other families retain their own dependency-complete milestones. Windowed/GPU
qualification is also independent runtime evidence, not structural API work.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
