# Engine-layer upstream findings

Defects and documentation/implementation disagreements found in CNA's
`engine_layer.h` family while building `cna.extensions.engine`. Every entry was
measured on the artifact it names; none is carried over from another language
binding, and none is a conclusion quoted from prose.

Each finding records the exact revision, a reproducer, the expected contract,
the actual result, the public Python operation it affects, what this binding
does instead, and what would unblock it.

## Measurement environment

```text
cnanext            5347b52eae1311fbea1f89955ae8a48c6843a88a
CNA C ABI          0.21.0
engine layer       revision 2

control artifact   HEADLESS, no engine layer
                   cmake-build-headless/modules/c-api/libcna_c_api.so
                   94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d

gpu artifact       OPENGLES3, Mesa GL ES 3.2 (llvmpipe), isolated Xvfb display
                   cmake-build-opengles3/modules/c-api/libcna_c_api.so
                   65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9
```

The control artifact reports `cna_engine_layer_get_version() == 0` and
`cna_graphics_ext_is_available() == false`: **it has no engine layer at all**,
while still exporting all 857 engine symbols. That is CNA's stated design -- one
export list regardless of build options, so the recorded ABI baseline describes
every build -- and it is why availability is read from the version route rather
than from the symbol table.

---

## ENGINE-001 -- `cna_compute_shader_create` fails on source that does not compile

**Status:** open. Does not block; this binding reports what happens.

**Documented contract.** `engine_layer.h` says, of `cna_compute_shader_create`:

> Creation succeeds even when the source does not compile: ask
> `cna_compute_shader_is_valid` and read `cna_compute_shader_copy_compile_error`.
> That mirrors the canonical class, which records the failure rather than
> throwing, because a renderer without compute is a documented boundary rather
> than a defect.

**Actual result.** Creation fails and hands back no handle. Measured on the GPU
artifact with six sources rejected for six different reasons:

| Source | `create` result | handle |
|---|---:|---:|
| empty | 12 (`CNA_RESULT_INTERNAL`) | 0 |
| syntax error | 12 | 0 |
| no `main` | 12 | 0 |
| no `#version` | 12 | 0 |
| undeclared identifier | 12 | 0 |
| no `local_size` | 12 | 0 |
| a source that compiles | 0 | valid, `is_valid` true, no diagnostic |

CNA's error message carries the compiler log, for example
`CNA::Graphics::ComputeShader: the program did not compile: CS: 0:3(15): error:
illegal use of reserved word 'this'`.

**Reproducer.** In C, against the GPU artifact:

```c
CNA_ComputeShaderHandle shader = 0;
const char* source = "#version 310 es\nlayout(local_size_x=4) in;\nvoid other(){}\n";
CNA_StringView view = { source, strlen(source) };
CNA_Result result = cna_compute_shader_create(device, view, &shader);
/* documented: result == CNA_RESULT_SUCCESS and shader valid-but-not-compiled */
/* actual:     result == 12 and shader == 0                                   */
```

`tests/test_engine_compute.py::ComputeShaderTests::test_source_that_does_not_compile_raises_with_the_compiler_log`
is the same measurement as a test, and it fails if CNA later starts keeping the
documented contract, which is when this finding needs re-measuring.

**Two separate problems.** The failure mode is one; the category is another.
A source the caller wrote badly is reported as `CNA_RESULT_INTERNAL`, the
category reserved for CNA's own invariants running out. A caller cannot tell
"my shader is wrong" from "CNA broke" by result code alone.

**Affected Python operation.** `cna.extensions.engine.ComputeShader(device,
source)`.

**Local behaviour.** The constructor raises
`cna.extensions.engine.errors.ComputeShaderCompileError`, whose `result` stays
12 verbatim and which subclasses `EngineInternalError`, so nothing is
relabelled: `except EngineInternalError` still catches it, and CNA's compiler
log is on `native_message`. The subclass exists so a caller can tell a
diagnostic from an allocation failure without parsing a message. The documented
path is handled too: a shader CNA does return while calling it invalid is closed
and reported, rather than being handed out as something that can be dispatched.

**Unblock condition.** Either the header stops promising a non-throwing
creation, or the implementation starts keeping it. If the implementation
changes, this binding keeps working -- the invalid-shader branch is already
there -- and the test above is what will say so.

---

## ENGINE-002 -- every engine getter hands out a counted view, and one says not to release it

**Status:** open. Worked around by releasing every view; not doing so stops a
game being destroyed.

**The general shape.** Measured across the engine layer: **every route that
answers with a handle returns a fresh, distinct, releasable handle on every
call.** Asking twice gives two handles. This holds for a post-process pass's
effect, a shadow map's texture, its caster effect, its skinned caster effect, a
chain's target pool, a pool's acquired target, a factory's cached effect and an
effect's shadow map. Most of the header documents it correctly. One route
documents the opposite, and that one is the defect below.

**Documented contract.** `engine_layer.h` says of the returned handle:

> The returned handle is borrowed from the pass; do not destroy it.

**Actual result.** Each call returns a **different** handle from the one the
caller supplied, and each one is a counted borrow that **must** be destroyed.
Measured on the GPU artifact:

```text
factory acquire                      -> effect handle 4294967316
effect pass create with that effect  -> ok
get_effect (first call)              -> handle 4294967318   (a new handle)
get_effect (second call)             -> handle 4294967319   (another new one)
pass destroy                         -> ok
factory destroy, 3 handles alive     -> 3  (CNA_RESULT_INVALID_STATE)
cna_effect_destroy(second view)      -> ok
factory destroy, 2 handles alive     -> 3
cna_effect_destroy(first view)       -> ok
factory destroy, 1 handle alive      -> 3
cna_effect_destroy(acquired handle)  -> ok
factory destroy, 0 handles alive     -> 0
```

CNA's own diagnostic names the rule: *"Every borrowed cached effect handle must
be released before the factory."* And once the factory cannot be destroyed,
`cna_game_destroy` answers *"All owned C child resources must be destroyed
before the game."* -- so a program that follows the documentation exactly leaks
one handle per read and eventually cannot shut down.

**Affected Python operation.** `cna.extensions.engine.EffectPass.effect`.

**Local behaviour.** The property calls the route, releases the view it gets
with `cna_effect_destroy` immediately, and returns the caller's own `Effect`
object. Reading it any number of times leaks nothing. The reason is stated at
the property rather than hidden, because a caller reading the C header would
otherwise conclude the opposite.

**A second route with the same shape, documented by omission.**
`cna_effect_get_shadow_map_ext` also returns a new handle per call -- measured
with both a `Texture2D` and a `RenderTarget2D` assigned, giving handles
`4294967324`, `8589934620`, `12884901916` for three consecutive reads -- and
each is released by `cna_render_target_destroy` whichever kind was set. The
header says nothing either way there, so nothing contradicts the measurement;
it is recorded because a caller reading only the header would leak. The same
applies to `cna_shadow_map_get_caster_effect` and
`cna_shadow_map_get_skinned_caster_effect`, which the header calls "borrowed
from the map" without saying that the borrow is counted.

**Local behaviour, generally.** Where the view is useful the object hands it out
**once** and disposes it on `close`: `ShadowMap.shadow_texture` and
`ShadowMap.caster_effect` return the same object however often they are read.
Where the view carries nothing the caller does not already have -- an effect
pass's effect, an effect's shadow map -- it is released immediately and the
caller's own object is returned.

**Unblock condition.** Either the header stops saying "do not destroy it", or
the route stops counting the handle it returns. Neither changes this binding's
behaviour: releasing a view that is no longer counted is still correct.

---

## ENGINE-003 -- the first GPU-timer sample is an unsigned 32-bit underflow

**Status:** open. Reported verbatim; not hidden.

**Actual result.** The **first** duration a `GpuTimer` collects is exactly
`4294.967295` ms, which is `(2**32 - 1)` nanoseconds. Every later sample is a
plausible microsecond-scale duration. Measured on the GPU artifact, six
consecutive measurements of one 4x4 `Clear`:

```text
run=0 collected=True samples=1 ms=4294.967295
run=1 collected=True samples=2 ms=0.017193
run=2 collected=True samples=3 ms=0.007895
run=3 collected=True samples=4 ms=0.014116
run=4 collected=True samples=5 ms=0.007053
run=5 collected=True samples=6 ms=0.006512
```

`4294.967295 ms` is not a measurement: nothing clears a 4x4 back buffer for 4.3
seconds. It is an elapsed of `-1` nanosecond wrapped into 32 unsigned bits,
which is what a first sample computed against an uninitialised or zero start
timestamp produces.

The post-process chain shows the same value through its own timer -- the first
sample it collects reads `4294.9673` ms and every later frame reads about
`0.003` ms -- so the defect is in the timer rather than in one caller of it.

**Reproducer.** Create a `GpuTimer`, bracket any draw with `begin`/`end`, poll
until `is_result_available`, and read `get_last_milliseconds`. The first
answer is the wrap value on every run.

**Affected Python operation.** `cna.extensions.engine.GpuTimer.last_milliseconds`
and `PostProcessChain.pass_timings`.

**Local behaviour.** CNA's number is returned unchanged. Discarding the first
sample in Python would hide a real defect and would silently disagree with
`sample_count`, which counts it. The docstring says so, and
`tests/test_engine_compute.py` and `tests/test_engine_postprocess.py` both
*pin* the wrap value, so the day CNA fixes it the tests fail and this finding is
re-measured rather than quietly outliving the defect.

**Unblock condition.** A first sample that is a duration.

---

## ENGINE-004 -- a chain's GPU timing flag is not observable until it has run

**Status:** open. Does not block; the documented protocol is what misleads.

**Documented contract.** Of `cna_post_process_chain_set_gpu_timing_enabled`:

> A renderer without GPU timers accepts the request and reports `CNA_FALSE`
> afterwards rather than refusing, so ask
> `cna_post_process_chain_is_gpu_timing_enabled` what it got.

**Actual result.** On a renderer whose GPU timer demonstrably works, the read
straight after the write still answers `CNA_FALSE`. It answers `CNA_TRUE` only
after the chain has applied once:

```text
standalone GpuTimer is_supported     -> true
chain is_gpu_timing_enabled          -> false
set_gpu_timing_enabled(true)
chain is_gpu_timing_enabled          -> false     <- the documented check
after the first apply                -> true
after eight applies                  -> true, 7 samples, ~0.003 ms
```

So the documented way to find out whether timing is on reports "no timing" on a
device that is about to time perfectly well. The distinction the documentation
draws -- between a renderer that accepts and stays off and one that turns on --
cannot be made at the moment it says to make it.

**Affected Python operation.**
`cna.extensions.engine.PostProcessChain.gpu_timing_enabled`.

**Local behaviour.** The property reports what CNA reports, and its
documentation says when the answer becomes meaningful instead of repeating the
header's protocol.

---

Findings are added as each engine family is qualified. A family that has not
been measured yet has no entry here, and an absent entry is not a claim that it
is clean.
