# CNA C ABI audit

Audit date: 2026-08-23.

The authoritative checkout was inspected read-only at CNA revision
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. It declares experimental C ABI
0.7.0 in 59 public headers and 2,861 unique exported functions. ABI primitives
used here are `uint32_t` results/enums, `uint8_t` Boolean, opaque generation-
checked `uint64_t` handles, versioned structures, UTF-8 views, and C callbacks.

Current CNA HEAD was not patched. A clean C-API build is blocked at
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

The developer path used for this evidence is not present in package source,
metadata, templates, or wheel contents. The public wheel contains no native
library.

`_cna_native.loader.FUNCTION_MANIFEST` is the exact selected import manifest.
Every entry supplies `restype` and `argtypes`, including pointer depth and
fixed-width signedness. Current imports cover version/errors, lifecycle/frame
hooks and timing properties, dispatcher, graphics manager/device, viewport/clear, Texture2D encoded
decode and Color transfer, SpriteBatch scaled submission, keyboard, mouse, and
gamepad. Foundation Milestone 2 added only four reviewed input imports:
`cna_mouse_get_window_handle`, `cna_mouse_set_window_handle`,
`cna_gamepad_get_capabilities`, and `cna_gamepad_set_vibration`. This is not a
claim that all 2,861 exports are bound.

The ABI probe compares `sizeof`, `_Alignof`, and field offsets for every ctypes
structure used. ELF verification compares every imported symbol against the
qualified artifact. Exact reported measurements are regenerated into the audit
report rather than inferred from another language binding.

The current generated report records:

```text
BOUND_FUNCTIONS=59
CTYPES_SIGNATURE_MEASUREMENTS=59
C_LAYOUT_MEASUREMENTS=210
CTYPES_LAYOUT_MEASUREMENTS=210
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

`CNA_Bool` is bound as `uint8_t`, results and selected enums as `uint32_t`,
signed dimensions/ticks as `int32_t`/`int64_t`, and opaque handles as
`uint64_t`. Structures passed by value (`CNA_Viewport`) are distinguished from
pointers to caller-owned output. Callback objects and message buffers are kept
alive for their full native registration/use lifetime.

All selected non-touch input members now have real CNA routes. A HEADLESS/NULL
run verifies calls and state conversion but cannot verify a physical controller
or operating-system window association. Surface still absent in Python (typed
content/XNB, additional SpriteBatch states and overloads, effects, buffers,
indexed drawing, audio/media/storage/touch) is an unimplemented binding
milestone, not currently recorded as an upstream CNA defect. The separate
current-CNA build blocker is the renderer-identity enumeration assertion
described above.
