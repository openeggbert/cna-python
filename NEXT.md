# CNA-Python tactical handoff

Date: 2026-09-02

```text
ABI_GENERATION=0.21.0
STRICT_TOTAL_DIAGNOSTICS=0
SELECTED_ENGINE_ACTIONABLE_LOCAL=0
ENGINE_UNREVIEWED=0
GLOBAL_ACTIONABLE_LOCAL=0
GLOBAL_UNREVIEWED=0
EXTENSION_SURFACE_DIAGNOSTICS=0
ABI_MISMATCHES=0
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE=0
REPOSITORY_MODE=maintenance/platform-qualification/selected-extension-families
```

The selected XNA 4.0 Windows runtime projection is unchanged and still closed.
This session opened, built and closed one new extension family: CNA's engine
layer. Every number below was re-measured today; none is quoted from the
previous handoff.

## 1. Start state

`931bf09 docs: close the CNB/CNJ family with re-measured numbers`, clean, on
`develop`.

Strict XNA closed at 257 types and 2,423 members with zero diagnostics. The CNA
0.21.x ABI migration complete. CNB/CNJ open and finished. 1,048 imported routes.
The engine layer covered by a single blanket census rule -- "engine layer is
outside the selected extension profile" -- over roughly 838 routes, which is one
decision standing in for hundreds.

## 2. Dependency and artifact identities

```text
cnanext            51d61ef42   unmodified by this session
sharp-runtimenext  9cc96cd5    unmodified by this session
```

| | control | gpu |
|---|---|---|
| Build | `cmake-build-headless` | `cmake-build-opengles3` |
| Renderer | `HEADLESS` | `OPENGLES3`, Mesa GL ES 3.2 (llvmpipe) |
| Display | none | isolated Xvfb `:171`, `SDL_VIDEODRIVER=x11` |
| Engine layer | absent | present, revision 2 |
| sha256 | `94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d` | `65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9` |

Neither was rebuilt. Both hashes match the previous handoff's.

No window was ever placed on the physical desktop: every rendering run used the
isolated display above, with `WAYLAND_DISPLAY` unset.

## 3. Closed baseline, reproduced

```text
strict XNA        257 types, 2,423 members, ZERO_DIAGNOSTIC_TYPES=257
                  --report, --check, --leak-only and the 7 verifier self-tests all clean
                  STUB_RUNTIME_MISMATCHES=0
ABI               MISSING_SYMBOLS=0  ABI_MISMATCHES=0
                  PROTOTYPE_CONFLICTS=0  ABSENT_FROM_HEADERS=0  RENDER_FAILURES=0
CNB/CNJ           285 routes, 283 bound, 0 unreviewed, 0 actionable-local
                  35 planted defects, 35 killed, 0 survivors
behaviour corpus  181 observations, 1,004 assertions, 0 failures
```

## 4. Extension product decision

**CNA-Python selects `engine_layer.h` as its third public `cna.extensions`
family.** `cna.extensions.engine` joins `cna.extensions.graphics` and
`cna.extensions.content`.

`Microsoft.Xna.Framework` is untouched by it. No engine class or member enters
that namespace -- a name there is a claim about XNA, and every one of these would
be false. The dependency runs `cna.extensions.engine -> strict XNA` and never
the reverse; a test in a fresh interpreter asserts importing XNA loads no `cna`
module. The only strict-XNA changes are two private members added so a counted
view can be adopted: `Texture2D._view_of` and `PbrMaterialExtensions._wrap`
(the latter is in the extension package), mirroring the existing
`RenderTarget2D._view_of`.

Sensors and device services, extended input, and Net remain **unopened**. So do
wider GamerServices/Avatar, the XNA Content Pipeline, Xbox and Windows Phone.
See section 36.

## 5. Engine route scoreboard

```text
engine_layer.h canonical routes           870   (live count from the headers)
  selected extension candidates           867
  bound                                   867
  managed by design                         3
  not useful for Python                     0
  blocked upstream                          0
  blocked renderer                          0
  blocked architecture                      0
  other blockers                            0
  unreviewed                                0
  actionable-local                          0
```

The brief's estimate was 857 canonical routes with ~838 behind the blanket rule
and 19 managed-by-design initialisers. The live header has 870; the blanket rule
is gone, replaced by 76 per-family rules plus three dependency-slice rules and
one exclusive ownership-transfer rule. Every initialiser the estimate counted as
managed-by-design is in fact bound, because each is the only route that fills a
value structure with CNA's own defaults and this package reads defaults rather
than transcribing them.

By group:

| Group | Bound / routes |
|---|---|
| Pure helpers and capabilities | 12 / 12 |
| Compute, storage, timer, indirect | 37 / 37 |
| Post-processing foundation | 41 / 44 |
| Shadows | 77 / 77 |
| PBR and glTF materials | 96 / 96 |
| Particles, decals, prepass, transparency | 85 / 85 |
| Render pipeline | 37 / 37 |
| Atmosphere, environment, IBL | 137 / 137 |
| Light probes | 46 / 46 |
| Clustered and area lighting | 117 / 117 |
| LOD, culling, instancing | 53 / 53 |
| HDR, auto exposure, tonemap | 62 / 62 |
| Advanced post-process | 46 / 46 |
| Debug draw | 21 / 21 |

The three unbound routes are all in the post-processing foundation group and are
listed in section 35.

## 6. Public engine API

```text
modules                          14
public names                    248
extension modules overall        33
public extension names overall  648
PUBLIC_CTYPES_LEAK                0
PRIVATE_NATIVE_LEAK               0
UNDOCUMENTED_PUBLIC               0
XNA_NAMESPACE_CONTAMINATION       0
PUBLIC_RAW_HANDLE_LEAK            0
PUBLIC_NATIVE_ANNOTATION_LEAK     0
EXTENSION_SURFACE_DIAGNOSTICS     0
```

`values`, `errors`, `compute`, `postprocess`, `passes`, `atmosphere`, `pbr`,
`shadows`, `scene`, `pipeline`, `clustered`, `probes`, `culling`, `debug`.

No handle, ctypes object, private native type or private native annotation is
reachable from any public name. All six diagnostics are planted and required to
fail; so is the converse, that a *private* helper may name exactly what it takes.

## 7. Pure and capability helpers

`layer_version`, `layer_version_string`, `is_available`, the light and quality
value types, and the capability predicates. Every default is read from CNA
through its own `*_ext_init` route rather than written down, because a
transcribed default survives CNA changing its mind.

The measured asymmetry, stated at both properties: `AreaLight.is_valid` and both
argument initialisers answer on a build with **no** engine layer, and
`ClusteredLight.is_usable` does not -- that rule belongs to the light *set*.
Documented that way in `engine_layer.h` and confirmed on the control artifact.

## 8. Post-processing

The pass vocabulary, the render-target pool, scoped targets, the shader-effect
factory, fullscreen and blit passes, and the chain. Three counted-view leaks
were found here and are the origin of ENGINE-002.

## 9. Shadows

Simple, cascaded, cube and spot shadow maps, and the receiver state an effect
samples with. Every light view, light projection, cascade split, frustum corner,
bounding sphere and texel snap is compared with an independent computation. A
shadow-map clear reads as `(0, 0, 128)` because the target is
`SurfaceFormat.Single` and that is float 1.0; the test decodes the bytes rather
than trusting the colour.

## 10. PBR and glTF materials

`PbrEffect`, `SkinnedPbrEffect`, a 27-field material, the glTF extension set, the
material bridge, and image-based lighting through `PbrEffect.image_based_light`.

ENGINE-005 lives here: `apply_material` carries every scalar and not one of the
seven texture slots. The public setter assigns the slots itself, says so, and a
test drives the raw route and asserts the defect so it fails when CNA fixes it.

## 11. Particles

Emitter settings, the system, `step`, the hash and the random source, and the
published GLSL. Emitter colours are `Vector4` and not `Color`; `active_count` is
rate times lifetime capped by the pool; `reset` returns particles to the emitter.

## 12. Decals

The decal pass and `is_inside_decal_box`, the projection test a shader runs.

## 13. Depth/normal prepass

The prepass, its three depth encodings, packed-depth encode and decode, velocity
encode and decode. The packing oracle computes in float32: the top channel is
genuinely zero at that width, and a double oracle disagrees with a correct
implementation.

## 14. Render pipeline

The whole-frame pipeline, its settings projected from the measured structure
layout rather than a hand-written field list, frame statistics, and per-pass
timings. ENGINE-004 lives here: a chain's GPU timing flag is not observable until
it has run.

## 15. Atmosphere, environment and IBL

Sky, skybox, height fog, volumetric fog, aerial perspective, SSAO, SSR, depth of
field, contact shadows, light shafts, motion blur, and the environment
processor. Measured clamps that are not documented: SSR roughness blur at 0.25,
edge fade at 0.5, DoF max radius at 0.25, several setters ignoring a non-positive
value, and an SSR step count that is *not* clamped at set time -- the trace
clamps instead, and the test asserts what CNA does rather than what would be
tidier.

## 16. Light probes

Nine spherical-harmonic coefficients and six visibility moments per probe, a
grid of them, the baker that captures one by drawing the scene six times, the
environment processor that builds the IBL textures, and `ImageBasedLight`.

Irradiance is compared with a second-order evaluation written from the
Ramamoorthi-Hanrahan constants; visibility with Chebyshev's bound, whose
continuity is checked by *refining the angular step* rather than against a fixed
difference, because a steep ramp and a step discontinuity look alike at one
resolution and only the ramp shrinks. The bake callback is rooted for the call
and no longer, and an exception raised inside it is re-raised after the native
call returns.

ENGINE-007 lives here: `importance_sample_ggx` uses the normal as supplied.

## 17. Clustered and area lighting

The light set, the depth-sliced grid, the CPU and GPU assignments, the uploaded
buffer, the shadow budget, the forward effect, area lights and the BRDF table.

The assignment is compared **three** ways -- CNA's CPU sort, CNA's compute shader,
and a full reimplementation in the oracles -- entry for entry rather than by
totals, and under a view matrix that is not the identity. Slice boundaries are
compared *exactly*: the float32 oracle matches CNA to the bit over six
near/far/count combinations, and a double one is off by up to three units in the
last place, which no approximate comparison at that magnitude could tell from a
correct implementation.

Cluster boxes are measured to be **conservative rather than a partition**: they
meet exactly in depth and overlap across the screen, because an axis-aligned box
around a frustum slab is as wide as that slab's far face. The first version of
the test asserted a clean tiling, which is false.

ENGINE-006 lives here: four constructors document a game and accept a device.

## 18. LOD, culling and instancing

Level-of-detail groups and their hysteresis, CPU frustum culling, hardware
instancing with its per-instance fallback, GPU culling that writes its own draw
arguments, and the two indirect draws that read them.

The six frustum planes are extracted a second time by combining rows of the
view-projection; every box and sphere answer is compared with the positive-vertex
test over them, under an axis-aligned camera and again under one that is neither
at the origin nor looking down an axis. `cull_transforms` is measured to *keep* a
transform with no matching bound. A LOD threshold is an upper bound, and past
every threshold nothing is selected rather than the coarsest level.

ENGINE-008 lives here: a cullable instance's canonical world is zero.

## 19. Compute, storage, timer and indirect

All implemented, and all supported on the gpu artifact: compute shaders, storage
buffers, the memory-barrier mask, GPU timers, and both indirect draws. No
renderer block anywhere in this group.

ENGINE-001 and ENGINE-003 live here. Measured renderer facts recorded rather than
worked around: image binding is unsupported on this renderer, and the GPU
instance culler reports which of its four required capabilities is missing rather
than only that something is.

The indirect draws need a bound vertex buffer and an applied effect, and CNA
names which is missing; the test asserts the text rather than only the failure.

## 20. HDR and auto exposure

HDR display output, PQ encode and decode, Rec.709 to Rec.2020, the roll-off, auto
exposure, tonemapping, colour grading and cube LUTs. Bloom extraction is a *soft
knee*, not a cutoff, which the oracle models and the monotonicity claim was
relaxed to match.

## 21. Debug draw

The line batch and its nine gizmos. Tested by counting rather than by looking:
every shape's line count is exact and determined by its arguments, and the
vertices are read back and checked against the geometry -- a box's twelve edges
each join two corners differing on exactly one axis, a sphere's every vertex is
on the sphere, a probe volume's crosses appear in the grid's own flat order.

A spot-light gizmo is measured to be **two** cones, the outer angle and the
inner; the first oracle said one and the test caught it.

## 22. Advanced post-process

Bloom, FXAA, film grain, chromatic aberration, lens flare, spatial upscale and
the ASCII pass. The standalone `AsciiEffect` is the only way to quantise an
arbitrary texture into an arbitrary rectangle. `last_grid_dimensions` is measured
to describe the **source**, not the destination; the property's own documentation
said the opposite and is corrected.

## 23. Native model dependency

`cna_lod_group_ext_add_level` and `cna_instanced_renderer_ext_create` take a
`CNA_ModelMeshPartHandle`. Strict XNA's `ModelMeshPart` is a managed Python
object with **no native handle at all**, and CNA's native model runtime is a
separate concept this binding deliberately does not bind (census rule
`native-models`).

The decision: import exactly `cna_model_mesh_part_create` and
`cna_model_mesh_part_destroy` and use them as a **private side-car**. A native
part is built from the strict part's own vertex buffer, index buffer,
`NumVertices`, `PrimitiveCount`, `StartIndex` and `VertexOffset`, so it describes
the same geometry rather than a copy; XNA's part is always a triangle list and
the native default is `PrimitiveType::TriangleList`, so the projection is
faithful. It is owned by whichever engine object needed it and released with it.

No native model, mesh or part is public. Every method takes and returns the
caller's own `ModelMeshPart`. **The strict managed XNA Model graph is not
replaced.**

No architecture blocker remains in this area.

## 24. Cross-header dependency slices

| Slice | Header(s) | Routes | Why, and why minimal |
|---|---|---|---|
| `engine-pbr-dependency` | `graphics_ext.h`, `effects.h` | `cna_pbr_material_ext_init`, `cna_pbr_effect_create`, `cna_skinned_pbr_effect_create`, `cna_pbr_effect_set_texture`, `cna_pbr_effect_get_texture` | `engine_layer.h` declares no route that creates a `PbrEffect`, and the init route is the only one that fills a 27-field material with CNA's defaults. The texture pair exists solely because ENGINE-005 drops all seven slots; without it a PBR effect could never have a texture. |
| `engine-ascii-dependency` | `graphics_ext.h` | the eight `cna_ascii_post_process_effect_*` routes | `cna_ascii_pass_get_effect` hands out the effect carrying cell size and quantize mode, and no engine-layer route reads or writes either. `create` and `draw` are the only way to quantise an arbitrary texture into an arbitrary rectangle. |
| `engine-model-part-dependency` | `models.h` | `cna_model_mesh_part_create`, `cna_model_mesh_part_destroy` | Section 23. Two routes, both private, no public native part. |

Each is a census rule with its own written reason, placed ahead of the
header-scoped rule it would otherwise be absorbed by, and the shadowing gate
added this session is what keeps that ordering honest.

## 25. ABI

| | before | after |
|---|---|---|
| Total bound routes | 1,048 | 1,917 |
| Engine routes bound | 0 | 867 |
| Compiler-proven prototypes | 1,048 | 1,917 |
| C layout measurements | 1,219 | 1,672 |
| ctypes layout measurements | 1,219 | 1,672 |
| Missing symbols | 0 | 0 |
| ABI mismatches | 0 | 0 |
| Prototype conflicts | 0 | 0 |

The engine ABI is **generated**, not transcribed: `tools/generate_engine_abi.py`
derives 28 structures, 109 constants and 3 callback types from the canonical
headers, together with a C probe that measures every offset and constant, and a
`--check` mode the gates run. Float constants are emitted at single precision and
the audit compares them at that width -- a header's `0.01F` is
`0.009999999776482582`, and emitting the double would make a caller comparing
CNA's own value against the constant find it one unit in the last place too
small, which is exactly how the render pipeline's gamma floor was caught.

The generator also derives which of each callback's parameters are pointers to
const, because C declaration compatibility distinguishes `const T*` from `T*` and
ctypes cannot carry it. Without that the first callback-taking route in this
family failed the prototype gate correctly, with the gate having no way to know.

## 26. Route reachability

```text
BOUND_ROUTES                          1917
DIRECT_CALL_SITE                      1823
OBSERVED_CALLED_AT_RUNTIME             506
REACHED_BY_NAME_TEMPLATE                15
ADMITTED_WITH_REASON                    37
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE      0
STALE_ADMISSIONS                         0
```

No route was imported speculatively. Every engine route has a production caller;
none was admitted with a reason during this session. Shadow classes use explicit
literal route dictionaries rather than f-string names, because the gate is
AST-based and a name it cannot see is a route nothing can prove is called.

## 27. Ownership and callbacks

Every owned object is an explicit `close()` with a context manager, and there is
no `__del__` anywhere: a finaliser running at an arbitrary point on an arbitrary
thread is not a lifetime, and CNA objects are graphics-thread affine.

**ENGINE-002 is the systemic finding of this session.** Every CNA engine getter
that answers with a handle answers with a *fresh counted view*, whatever its
documentation says, except when it hands back the handle it was given. Following
the documentation exactly leaks one handle per read, and the failure surfaces as
"only one C-owned CNA game may be active at a time" on an unrelated test.

Solved once, in two shapes, neither of which is a table of affected routes:

* `engine_support.borrowed_view` compares the answered handle against the one
  this binding supplied and releases only a different one. For objects the
  *caller* owns.
* `_EngineObject._view` builds a facade once per key, caches it, and disposes it
  when the owner closes. For objects CNA owns.

Ownership classifications used: OWNED, BORROWED, COUNTED_BORROW, PARENT_OWNED,
RETAINED_DEPENDENCY, TRANSIENT_CALLBACK_VIEW, PROCESS_GLOBAL. Every manifest
entry carries its contract in its fourth column.

Three callbacks: the render-pipeline draw, transparent-draw submission, and the
light-probe bake. In each the trampoline is rooted for exactly as long as CNA can
invoke it, and a Python exception is stored and re-raised *after* the native call
returns. `test_an_exception_in_the_callback_reaches_the_caller_intact` asserts
both the exception and that the baker still works afterwards.

## 28. Mutation and falsifiability

```text
engine   PLANTED=47  KILLED=47  SURVIVED=0  INAPPLICABLE=0
CNB/CNJ  PLANTED=35  KILLED=35  SURVIVED=0  INAPPLICABLE=0
```

The oracles are mutated too, deliberately: an oracle wrong in the same way as
CNA would make a whole family agree on a defect.

The first engine run killed 37 of 46 and left nine survivors. **Eight were real
test gaps** and are closed: an approximate slice comparison that could not tell
float from double, shadow-policy lights that were all white and none inside the
falloff's distance floor, a zero-radius sphere never assigned, a disc quad never
compared with CNA, a probe-volume flat index no test used, hysteresis never tried
across two levels, and an ASCII destination rectangle invisible to every
assertion. The ninth was an **equivalent mutation** -- reversing the low sixteen
bits and shifting is identical to reversing thirty-two for every index the tests
use -- and was replaced by two that do change the sequence.

The gates are falsifiable too, each with a planted defect required to fail: all
six extension-surface diagnostics, a bound route nothing calls, a stale
admission, a rule shadowed by an earlier one, a rule that classifies nothing, and
a route CNA does not have landing in `UNREVIEWED`.

## 29. Upstream findings

Eight, in `docs/engine-upstream-findings.md`, each with the CNA revision, a
reproducer, expected against actual, the local behaviour and an unblock
condition. All against CNA `51d61ef42`, ABI 0.21.0, engine layer revision 2.

| | Finding | Local behaviour |
|---|---|---|
| ENGINE-001 | `cna_compute_shader_create` fails on source that does not compile, where the header says it succeeds and reports invalid | raises `ComputeShaderCompileError`, result 12 kept; six bad sources pinned |
| ENGINE-002 | every engine getter hands out a counted view, and one says not to release it | `borrowed_view` and cached views; released on close |
| ENGINE-003 | the first GPU-timer sample is an unsigned 32-bit underflow | the first sample is discarded, and the underflow is pinned |
| ENGINE-004 | a chain's GPU timing flag is not observable until it has run | documented at the property; the test runs a frame first |
| ENGINE-005 | `cna_pbr_effect_apply_material` carries every scalar and no texture | the setter assigns the seven slots itself, visibly |
| ENGINE-006 | four clustered constructors document a game and accept a device | every class takes a `GraphicsDevice`; both handles driven in a test |
| ENGINE-007 | `importance_sample_ggx` needs a unit normal and does not say so | stated at the function; *not* silently normalised, because that would make it disagree with the GLSL CNA publishes beside it |
| ENGINE-008 | a cullable instance's canonical world is zero, not identity | handed back unchanged; the trap stated at `default()` |

Each pinning test fails the day CNA fixes the defect.

Nothing was fixed in `cnanext` or `sharp-runtimenext`; both are unmodified.

## 30. Runtime capability registry

```text
CAPABILITIES=234
VERIFIED_NATIVE=182
VERIFIED_MANAGED=17
BLOCKED_UPSTREAM=13
BLOCKED_RENDERER=3
BLOCKED_PLATFORM=5
BLOCKED_HARDWARE=2
BLOCKED_FIXTURE=6
LANGUAGE_MAPPING_LIMITATION=3
NOT_USEFUL_FOR_PYTHON=1
DELIBERATE_OUT_OF_SCOPE=2
ACTIONABLE_LOCAL=0
ARTIFACTS=2
```

Grew from 140 rows to 234. Every row names the artifact that produced it, and no
row claims a capability on an artifact that cannot answer for it.

## 31. Defects found

**In this binding, before it shipped.** Ten `cna.extensions.content`
constructors published `_support.NativeHandle` in their `__init__` annotations,
found the moment the surface gate stopped exempting every dunder; all ten now
raise from `__init__` and adopt through a private `_wrap`. Three counted-view
leaks in the post-process family, each surfacing as an unrelated game refusing to
be destroyed. A stale material-extensions view kept after assignment, so reading
a clearcoat factor back answered zero. Three engine test modules that could not
be imported without a native library, found by the final qualification's
no-library run.

**In the tooling and verifiers.** The extension gate exempted every dunder, so
`__init__` annotations went unchecked -- and it then found the ten leaks above.
The reachability gate was blind to f-string route names. The ABI audit compared
float constants at double width. The engine ABI generator duplicated four
structures the XNA boundary already measures. The census never checked its rules
against each other: an ownership-transfer rule was shadowed by a prefix rule, so
a decision already made was reported as an outstanding task, and a dead `*_ext`
catch-all would have turned every future route into a reviewed decision nobody
made. Four census rules carried no bound reason. The CNB read-scaling check was
measuring glibc's mmap threshold rather than the copy's complexity, and adding an
unrelated test file was enough to flip it.

**In the test suite.** Nine engine mutation survivors, eight of them real gaps.
An oracle self-test that compared the two tiles straddling the screen centre,
where both boundaries are zero whatever the projection, and therefore checked
nothing.

**CNA upstream.** Eight findings, section 29. None blocking.

**Sharp Runtime.** None found; unmodified.

**Stale docs and evidence.** `engine_layer.h` documents a spot-light gizmo, a
cullable instance's defaults, a GGX normal, four constructor parameters and a
cube-face range in terms that measurement contradicts or does not cover; each is
either a numbered finding or pinned by a test. Inside this repository,
`AsciiEffect.last_grid_dimensions` documented itself backwards and is corrected.

## 32. Qualification

Executed on this session's ending state.

```text
compileall (src, tools, tests)                              PASS

strict verifier --report        257 zero-diagnostic types, all counters 0
strict verifier --check         PASS
strict verifier --leak-only     all counters 0
strict verifier self-tests      7 tests, OK
verify_stubs                    STUB_RUNTIME_MISMATCHES=0

extension surface verifier      33 modules, 648 names, all 6 diagnostics 0
behaviour corpus                181 observations, 1,004 assertions, 0 failures

ABI audit                       1,917 signatures, 1,672 C and 1,672 ctypes layouts,
                                MISSING_SYMBOLS=0, ABI_MISMATCHES=0
prototype gate                  1,917 compiler-verified, 0 conflicts,
                                0 absent from headers, 0 render failures
engine ABI generator --check    up to date
route census                    4,055 routes, 0 unreviewed, 0 actionable-local,
                                0 contradictions, 0 shadowed or dead rules
route reachability              0 unjustified, 0 stale admissions

unittest, no native library     1,148 tests, OK, 852 skipped
unittest, control artifact      1,148 tests, OK, 536 skipped
unittest, gpu artifact          1,148 tests, OK,  14 skipped

mutation, engine                47 planted, 47 killed, 0 survivors
mutation, CNB/CNJ               35 planted, 35 killed, 0 survivors
```

Per-family engine suites on the gpu artifact: oracles 155, compute 23,
postprocess 20, passes 29, atmosphere 30, pbr 27, shadows 31, scene 40,
pipeline 19, clustered 154, probes 77, culling 60, debug 33 -- all OK.

**Skips, and why none of them is an unsupported GPU feature reported as a pass.**

* gpu artifact, 14 skipped: 12 need `CNA_PYTHON_LZX_FIXTURE_DIR` or
  `CNA_PYTHON_COMPILED_EFFECT_FIXTURE`, which are optional authored fixtures this
  environment does not have; 2 are the absence tests, which are only meaningful
  on a build *without* an engine layer. Running with `CNA_SOURCE_ROOT` set turns
  14 further skips into executed cross-checks against CNA's own tools.
* control artifact, 536 skipped: 343 because the build has no engine layer, 183
  because they need an engine layer *and* a rasterizer, 8 because it cannot
  rasterize, 2 optional fixtures.
* no library, 852 skipped: everything needing a configured library.

No test was skipped because a GPU feature was unavailable. Every capability the
gpu artifact lacks is recorded as a blocked capability row, not as a skip.

## 33. Template and package

```text
wheel      cna_python-0.1.0.dev0-py3-none-any.whl, 120 files
sdist      cna_python-0.1.0.dev0.tar.gz, 271 files
package audit                    every check PASS
  FORBIDDEN_WHEEL_ENTRIES        0
  FORBIDDEN_SDIST_ENTRIES        0
  ABSOLUTE_DEVELOPER_PATHS       0
  BUNDLED_NATIVE_LIBRARIES       0
  MICROSOFT_OR_PROPRIETARY       0
reproducibility
  WHEEL_BYTE_REPRODUCIBLE        1
  WHEEL_CONTENT_REPRODUCIBLE     1
  SDIST_BYTE_REPRODUCIBLE        0    (setuptools and gzip timestamps; not ours)
  SDIST_CONTENT_REPRODUCIBLE     1
```

The engine package ships: 14 modules under `cna/extensions/engine/` plus the
three private `_cna_native` engine modules.

The template gains `--verify-engine`, beside `--verify-cnb` and separate for the
same reason. Device-free, four exact checks, and a build with no engine layer
reports "absent" and exits cleanly, because conflating "absent" with "broken"
would make the check worse than none.

Installed-wheel consumer, generated with no source checkout on its path, on both
artifacts:

```text
                        control        gpu
IMPORT_PROBE            PASS           PASS
COMPILE_PROBE           PASS           PASS
SMOKE_60                PASS           PASS
STABILITY_600           PASS           PASS
EXTENSION_IMPORT        PASS           PASS
CNB_SMOKE               PASS           PASS
ENGINE_SMOKE            PASS           PASS
ENGINE_LAYER            absent         present
ABSOLUTE_DEVELOPER_PATHS       0              0
SIBLING_SOURCE_DEPENDENCIES    0              0
PYTHONPATH_SOURCE_DEPENDENCIES 0              0
```

## 34. Git

```text
cna-python           develop  43f3af129d457e32aaa9956045d1090355be4283
                     clean, 18 commits ahead of origin/develop, 0 behind
                     pushed = NO

cna-python-template  develop  fe84cd7c4b3b95450d5046cfa841ffc333d6a38b
                     clean, 1 commit ahead of origin/develop, 0 behind
                     pushed = NO

cnanext              51d61ef42   files modified by this session = 0
sharp-runtimenext    9cc96cd5    files modified by this session = 0
```

No dependency was committed to, reset, reverted, cleaned or switched. No build
artifact is staged; `dist/` and `build/` are ignored.

## 35. Remaining selected engine work

```text
SELECTED_ENGINE_ACTIONABLE_LOCAL = 0
ENGINE_UNREVIEWED                = 0
GLOBAL_ACTIONABLE_LOCAL          = 0
GLOBAL_UNREVIEWED                = 0
STRICT_TOTAL_DIAGNOSTICS         = 0
EXTENSION_SURFACE_DIAGNOSTICS    = 0
ABI_MISMATCHES                   = 0
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE = 0
```

Everything that remains unbound in the selected engine family is
`MANAGED_BY_DESIGN` / `DELIBERATE_NON_BINDING`, and it is three routes:

* `cna_post_process_effect_pass_create_owning`
* `cna_post_process_chain_add_owned_pass`
* `cna_skybox_set_owned_environment`

Each is the C form of a `unique_ptr` parameter, existing because C has no way to
say "keep this alive". They transfer ownership and **invalidate the caller's
handle**. Python's reference already guarantees that lifetime, so binding them
would cost capability rather than add it: CNA would invalidate a live `Effect`
facade that could then no longer set a parameter. The borrowing constructors give
the same guarantee with nothing invalidated. The rule is marked `boundIsError`,
so importing one would be reported as a contradiction.

No route in the family is BLOCKED_UPSTREAM, BLOCKED_RENDERER, BLOCKED_PLATFORM,
BLOCKED_HARDWARE, BLOCKED_FIXTURE, BLOCKED_ARCHITECTURE, LANGUAGE_MAPPING_LIMITATION
or NOT_USEFUL_FOR_PYTHON.

## 36. Unopened future extension and profile families

These are **product decisions**, not backlog. Each is recorded in
`docs/generated/cna-route-census.md` with its reason, and opening any of them
requires a new explicit decision.

| Family | Standing decision |
|---|---|
| Sensors and device services | Unopened extension family. No XNA counterpart on the selected profile. |
| Extended input | Unopened extension family. Beyond XNA 4.0's input surface. |
| Net | Unopened future profile. XNA's networking is a Live-service surface with no CNA-side equivalent selected. |
| Wider GamerServices / Avatar | Unopened future profile, beyond the sliver the selected profile already projects. |
| XNA Content Pipeline | Unopened future profile. This binding projects the *runtime* content surface; the pipeline is a build-time product. |
| Xbox | Unopened future profile. |
| Windows Phone | Unopened future profile. |

`graphics_ext.h` beyond the three dependency slices remains outside the selected
profile as a whole-header decision, which is why a route added to it inherits
that decision correctly rather than arriving unreviewed.

## 37. Next frontier

There is no remaining selected-scope work, and no genuine external engine blocker
holds anything back: every one of the eight upstream findings has a local
behaviour that ships, and none of them prevents a capability from working.

What is left is one of two things, and neither is a local task:

1. **Reconciliation with upstream.** When CNA fixes any of ENGINE-001 through
   ENGINE-008, the pinning test for it fails by design. That is the signal to
   remove the workaround and the pin together.
2. **Another extension or profile family**, which requires a **new explicit
   future product decision** from section 36. Nothing in this repository should
   open one on its own initiative.

Ordinary maintenance continues: further platform qualification, packaging and
release work, and real-game compatibility testing.
