# CNA-Python implementation plan

Status: Foundation Milestone 7 complete. The complete remaining managed/value
layer (Curve, PackedVector, and Design), structural, behavior, ABI regression,
package, isolated exact-wheel, and maintained/generated 60/600-frame gates are
green.

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
- [x] Refresh structural, behavior, runtime-capability, ABI, ownership, package,
  and isolated installed-wheel evidence.

## Current measured boundary

- Reference/expected projection: 257/2,964 CLR types/members and 257/2,887
  mapped Python types/members.
- Strict target: 218 types and 2,061 strict runtime members.
- Diagnostics: 39 total, all whole missing types. Missing members and partial
  types are zero. Every mismatch, leak, allowlist, and unmeasured category is
  zero. The full strict check remains intentionally red only for future types.
- Type status: 218 complete, 0 partial, 39 missing. Every Curve, PackedVector,
  and Design type has zero local diagnostics.
- Native manifest: 471 exact ABI-0.7 functions, 471 signature measurements,
  708 C and 708 ctypes layout measurements, zero missing symbols and zero ABI
  mismatches.
- Behavior evidence: 167 PURE_XNA_DERIVED observations, 925 assertions, zero
  failures.
- Runtime evidence: Linux x86-64, HEADLESS renderer, NULL audio. Native
  SoundEffect construction/instance/3D routes, copied dynamic queues,
  BufferNeeded dispatch, zero-device microphone enumeration, and XACT failure
  rollback are verified. Audible output, microphone capture, and authored XACT
  playback are not inferred from this environment.
- Runtime capability details are sourced from `docs/runtime-capabilities.json`
  and rendered to `docs/generated/runtime-capabilities.md`.

## Foundation Milestone 7 evidence

- [x] Generic and non-generic CLR PackedVector interfaces remain distinct:
  `IPackedVector` and deterministic `IPackedVectorOfT[TPacked]`. The verifier
  measures the TypeVar relation; there is no alias, allowlist, or synthetic
  XNA identity.
- [x] UInt8/16/32/64 PackedValue setters reject negative and oversized Python
  integers. All bit layouts, component order, clamping, nearest-even rounding,
  signed normalization/sign extension, NaN, infinity, and copy semantics are
  covered by exact-bit tests and seventeen corpus observations.
- [x] XNA's historical half conversion is implemented explicitly. Exponent 31
  is finite, `0x7C00` expands to binary32 65536, and non-finite inputs saturate
  to signed `0x7FFF`; IEEE `struct.pack('e')` is not used.
- [x] CurveKeyCollection preserves ascending Position order and stable insertion
  order for equal positions. Curve/collection clones copy the collection but
  retain key references, matching XNA. Every loop and tangent mode, Step versus
  Smooth, duplicate positions, negative cycles, and float32 evaluation are
  measured.
- [x] Design maps `System.Type` to `type`, culture to an explicit deterministic
  name string, descriptor collections and dictionaries to ordered mappings,
  and InstanceDescriptor to an executable `(callable, immutable args)` pair.
  Context/attribute parameters unused by XNA IL are formally omitted. No
  public `System.ComponentModel` or support-framework XNA types exist.
- [x] Design property order, snapshot decomposition, per-converter string
  support, invariant/en-US/de-DE formatting and parsing, explicit
  CreateInstance reconstruction, Matrix translation/scalar behavior, Color's
  byte domain, invalid inputs, and executable descriptors are verified.
- [x] No runtime-capability row and no native import was added. The ABI remains
  471 functions/signatures and 708/708 layout measurements.
- [x] Final package, isolated exact-wheel, and maintained/generated 60/600-frame
  evidence is green; archive hashes and exact consumer results are in `NEXT.md`.

## Dependency boundary after Milestone 7

No follow-on runtime family is started. The exact remaining 39 whole types are
FrameworkDispatcher (1), GamerServices (1), unrelated Graphics (2), Touch (8),
Media (24), and Storage (3). A later milestone must select one coherent runtime
or platform dependency closure rather than optimize the type count.

## Invariants

1. CNA canonical C headers are authoritative at the native boundary; the C++
   ABI and other language bindings never cross Python's boundary.
2. Public `Microsoft.Xna.Framework.*` names preserve XNA identity; private code
   is idiomatic Python.
3. A public operation reaches real behavior or throws an explicit, accurate
   error. It never silently succeeds, fabricates state, or drops arguments.
4. Exact evidence is regenerated and missing surface remains visible.
