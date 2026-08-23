# CNA C ABI audit

Audit date: 2026-08-23.

The authoritative checkout was inspected read-only at CNA revision
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. It declares experimental C ABI
0.7.0 in 59 public headers and 2,861 unique exported functions. ABI primitives
used here are `uint32_t` results/enums, `uint8_t` Boolean, opaque generation-
checked `uint64_t` handles, versioned structures, UTF-8 views, and C callbacks.

Current CNA HEAD was not patched. Its checkout already contains an unrelated
untracked test-discovery file. A clean C-API build remains blocked at
`modules/c-api/src/CnaCApiCoreExt.cpp:250`: the compile-time renderer identity
guard sees 49 C identities for 50 canonical renderer entries.

Local native verification uses, only through `CNA_NATIVE_LIBRARY`:

```text
CNA source revision: a09196a6477f69a7a57c8364f990658d31531a5b
ABI: 0.7.0 (0x00000700), exact match required
Platform: Linux x86-64
Renderer/platform: HEADLESS
Audio: NULL
SHA-256: 42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
ELF CNA exports: 2861
```

The developer path used for this evidence is absent from package source,
metadata, templates, and wheel contents. The wheel contains no native library.

`_cna_native.loader.FUNCTION_MANIFEST` is the exact selected import manifest.
Every entry supplies `restype` and `argtypes`, including pointer depth and
fixed-width signedness. In addition to the established Game, 2D graphics, input,
SpriteFont, buffer, title, Effect, stock-effect, Texture3D/Cube, and Model
routes, Foundation Milestone 6 imports 96 used Audio/XACT routes. These cover
SoundEffect, instances, single/multiple-listener 3D calls, dynamic streaming,
microphones, one shared unsubscribe route, and the AudioEngine/category/bank/cue
graph. Unused Audio capability, native-disposed, renderer-equality, and XACT
observer routes are deliberately not imported. This is not a claim that all CNA
exports are bound.

The ABI probe compares `sizeof`, `_Alignof`, and every field offset for each
ctypes structure used. ELF verification compares every imported symbol against
the qualified artifact. Exact regenerated measurements are:

```text
BOUND_FUNCTIONS=471
CTYPES_SIGNATURE_MEASUREMENTS=471
C_LAYOUT_MEASUREMENTS=708
CTYPES_LAYOUT_MEASUREMENTS=708
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

`CNA_Bool` is bound as `uint8_t`, results and selected enums as `uint32_t`,
signed dimensions/ticks as `int32_t`/`int64_t`, and opaque handles as
`uint64_t`. Structures passed by value are distinguished from pointers to
caller-owned output. Callback objects and message buffers stay alive for the
full native registration/use lifetime.

The new ABI measurements include `CNA_AudioEventCallback` and exact size,
alignment, and offsets for `CNA_AudioCapabilities`,
`CNA_SoundEffectCreateInfo`, `CNA_SoundEffectInstanceInfo`,
`CNA_AudioEmitter`, `CNA_AudioListener`, and `CNA_CueInfo`. The callback is
exactly `void (*)(void*)`; CNA documents dynamic delivery on the thread that
advances the queue, which is the Game thread under the framework dispatcher.
ctypes callbacks are strongly retained until `cna_audio_unsubscribe_ext`
succeeds, and no Python exception crosses the C boundary.

The qualified artifact predates CNA HEAD's rejection of bound vertex/index
buffer destruction, so CNA-Python adds an explicit facade guard before calling
its destroy route. Shutdown first unbinds every retained buffer/render target.
No CNA call is made from an interpreter finalizer.

Runtime support and blockers are not inferred from structural or ABI presence.
The machine-readable classification is `docs/runtime-capabilities.json`; its
generated rendering documents HEADLESS limits, missing non-default Present,
identityless resource events, the split dynamic-vertex offset/options routes,
verified managed/native Content/XNB routes, erased-generic limitations, and the
separate Effect/Model command paths, Texture3D/Cube HEADLESS boundaries, and
granular Audio/XACT results. ABI 0.7 explicitly refuses multi-listener counts
other than one and explicitly ignores AudioEngine renderer/look-ahead values;
CNA-Python reports both instead of approximating them. Microphone capture is
hardware-pending on the zero-device NULL backend, authored XACT success is
asset-pending, and the unrelated RenderTargetCube family remains deferred.
