# CNA C ABI audit

Audit date: 2026-09-01. Supersedes the 2026-08-23 audit of the historical
`0.7.0` generation.

## The generation this binding speaks

```text
CNA_ABI_VERSION      = 0.21.0 (0x00001500)
cnanext revision     = 7712534d3d22c7e284714e0e87afebba3f3cb472
sharp-runtimenext    = 9cc96cd57cde394940cc24d58743edf9bf63d3fb
canonical public C headers = 61
canonical CNA_C_API routes = 4,055
exported cna_* symbols     = 4,055
```

CNA's own contract (`docs/c-api/ABI_VERSIONING.md`) states that ABI `0.x` is
experimental, that a consumer "must reject a different major and may require a
minimum minor", and that within `0.x` **an incompatible change requires a
minor-version increment**. A minor therefore names one compatibility generation.

CNA-Python supports exactly one generation, the one it qualifies against. It
accepts any patch inside that minor and rejects every other minor and major. It
is deliberately not multiplexed across generations: a single ctypes manifest
cannot be truthful for two `0.x` minors that are permitted to differ
incompatibly, and no artifact of the historical `0.7.0` generation still exists
to test against, so supporting it would be an unverified claim.

`HISTORICAL_ARTIFACT_AVAILABLE = false`. The `0.7.0` library the previous audit
measured (SHA-256 `c62949d2…`) is not present in any checkout on this machine,
and no equivalent was rebuilt to stand in for it. Its measurements are quoted
below only as the *before* side of a migration, never as a current claim.

## What the migration measured

Symbol presence and manifest shape do not establish that a signature is
unchanged, so three independent measurements were taken.

**Symbols.** All 744 historical routes still exist as exported symbols in
`0.21.0`. Exports are version-tagged `@@CNA_C_API_0.1`.

**Layout.** Every `sizeof`, `_Alignof` and used field offset is compared between
the canonical C headers and the ctypes declarations by a compiled probe. Of 775
historical measurements, exactly one differed: `CNA_ABI_VERSION` itself. Every
structure this binding uses has the same layout in both generations.

**Prototypes.** This is the measurement the previous audit did not make. Each
imported route's prototype is rendered *from the ctypes manifest alone* and
emitted as a redundant C declaration in a translation unit that includes the
canonical headers. C requires all declarations of a function to be compatible,
so the compiler rejects a wrong width, a wrong signedness, a wrong pointer
depth, a wrong arity, a swapped parameter, a struct passed by value instead of
by pointer, or a wrong callback signature. Only `const` is taken from the
canonical declaration: it is not an ABI property, but C declaration
compatibility distinguishes `const T*` from `T*`.

Fourteen falsifiability tests plant a real ABI defect in a real route and
require the compiler to reject each one, so the gate is known to be capable of
failing.

## Current measurements

```text
BOUND_FUNCTIONS                = 765
CTYPES_SIGNATURE_MEASUREMENTS  = 765
PROTOTYPES_COMPILER_VERIFIED   = 765
PROTOTYPE_CONFLICTS            = 0
C_LAYOUT_MEASUREMENTS          = 796
CTYPES_LAYOUT_MEASUREMENTS     = 796
MISSING_SYMBOLS                = 0
ABI_MISMATCHES                 = 0
```

Before the migration the same manifest held 744 routes and 775 layout
measurements against `0.7.0`.

`CNA_Bool` is bound as `uint8_t`, results and identity typedefs as `uint32_t`,
signed dimensions and ticks as `int32_t`/`int64_t`, and opaque handles as
`uint64_t`. Every typed handle alias CNA has added (`CNA_EffectHandle`,
`CNA_SongHandle`, `CNA_VideoPlayerHandle` and the rest) is a transparent typedef
of `CNA_Handle`, which the compiler check proves rather than assumes.
Structures passed by value are distinguished from pointers to caller-owned
output.

## Route census

The binding used to know only its own imported set, so a route CNA gained was
invisible. All 4,055 canonical routes are now classified by purpose and by
binding status, which are separate questions: a route can back XNA and still be
unbound, and a route can be bound while its purpose is only tooling.

```text
CANONICAL_ROUTES           = 4055
BOUND                      = 765
UNREVIEWED                 = 0
RULE_CONTRADICTIONS        = 0

XNA_BACKING                = 1175
CNA_EXTENSION_CANDIDATE    = 1791
MANAGED_BY_DESIGN          = 566
OUT_OF_SELECTED_PROFILE    = 414
NOT_USEFUL_FOR_PYTHON      = 108
TOOLING_ONLY               = 1
```

`ACTIONABLE_LOCAL` is zero. A capability CNA offers that this product has not
selected is a deliberate non-binding with its reason recorded, not an
outstanding task: binding a route nothing calls is not progress.

## Reachability

Every bound route is traced through to a consumer, because a route that nothing
calls passes the ABI audit and the prototype gate while doing nothing.

```text
BOUND_ROUTES                          = 765
DIRECT_CALL_SITE                      = 671
OBSERVED_CALLED_AT_RUNTIME            = 506
REACHED_BY_NAME_TEMPLATE              = 15
ADMITTED_WITH_REASON                  = 37
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE   = 0
```

Text search is not the authority: a route named in a docstring must not count.
The analysis walks the AST and follows the two ways this codebase builds a route
name from constants. What it cannot follow is settled by recording the routes
that actually executed during both suites.

## Callbacks

Every callback type is measured for size and its full signature is proven by the
compiler check. `CNA_GameLifecycleCallback`, `CNA_GameBeginDrawCallback`,
`CNA_GameEventCallback`, `CNA_GraphicsResourceDisposingCallback`,
`CNA_GraphicsDeviceEventCallback`, `CNA_RenderTargetContentLostCallback`,
`CNA_PreparingDeviceSettingsMutatorEXT`, `CNA_AudioEventCallback`,
`CNA_StorageCompletionCallback` and `CNA_MediaPlayerEventCallback` are all bound
at their exact declared shapes.

A ctypes callback stays caller-owned until unregistration or resource
destruction. It is rooted on the **owning handle**, not on the public facade:
the facade and its closure form a cycle the collector may reclaim while CNA
still holds the trampoline pointer, which is a use-after-free rather than a
leak. No Python exception crosses the C boundary; every trampoline contains
`BaseException`, records a diagnostic and re-raises after native control
returns.

## Qualified artifacts

Two artifacts are qualified, and every runtime claim names the one that produced
it. A result measured where nothing rasterizes is a command-path result, not a
rendering result, and the registry records which is which.

```text
control  HEADLESS   does not rasterize   SDL3 mixer, dummy device
         sha256 94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d

gpu      OPENGLES3  Mesa GL ES 3.2 (llvmpipe) on an isolated Xvfb display
         sha256 65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9
```

Both are read-only consumers of an existing CNA build tree. CNA and Sharp
Runtime were not modified.

The developer paths used for this evidence are absent from package source,
metadata, templates and wheel contents. The wheel contains no native library.
