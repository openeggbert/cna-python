# The engine layer, as a Python extension

`cna.extensions.engine` projects CNA's `engine_layer.h`: a rendering vocabulary
XNA never had. Compute shaders, physically based materials, cascaded and cube
shadows, a post-process chain, clustered lighting, light probes and image-based
lighting, culling and instancing, and a debug line batch.

It is the third public `cna.extensions` family, after `graphics` and `content`.

## What this is, and what it is not

It is **not** an XNA feature. Nothing here has an XNA counterpart, so nothing
here may appear in `Microsoft.Xna.Framework`: a name in that namespace is a
claim about XNA, and every one of these would be a false one. The dependency
runs one way only -- `cna.extensions.engine` imports strict XNA types where
those are exactly the right representation (`Vector3`, `Matrix`, `Color`,
`BoundingBox`, `BoundingSphere`, `BoundingFrustum`, `Effect`, `Texture2D`,
`TextureCube`, `RenderTarget2D`, `ModelMeshPart`), and the XNA namespace never
imports this package. `tools/verify_extensions.py` enforces both directions and
a test in a fresh interpreter asserts that importing XNA loads no `cna` module.

It is also not a renderer of its own. Every object here draws through the same
`GraphicsDevice` a strict XNA game already has.

## Route scoreboard

| | |
|---|---|
| Routes in `engine_layer.h` | 870 |
| Imported | 867 |
| Deliberate non-bindings | 3 |
| Unreviewed | 0 |
| Actionable-local | 0 |
| Public names in `cna.extensions.engine` | 248 |
| Modules | 14 |

Every route is either imported or carries a written decision. The census
(`tools/route_census.py`) is what says so, and `UNREVIEWED` is the one status it
may not ship.

### The three routes deliberately not bound

`cna_post_process_effect_pass_create_owning`, `cna_post_process_chain_add_owned_pass`
and `cna_skybox_set_owned_environment`.

Each is the C form of a `unique_ptr` parameter. They exist because C has no way
to say "keep this alive", so they transfer ownership and *invalidate the
caller's handle*. Python's reference already guarantees exactly that lifetime --
an `EffectPass` holds its effect, a `PostProcessChain` holds its passes, a
`Skybox` holds its environment cube -- so binding these would cost capability
rather than add it: CNA would invalidate a live `Effect` facade, which could then
no longer set a parameter. The borrowing constructors give the same guarantee
with nothing invalidated.

The census rule that says so is marked `boundIsError`, so importing one of them
would be reported as a contradiction rather than accepted.

### The three dependency slices

Opening this family needed a little of three other headers. Each is minimal,
each is written down as a rule with its reason, and none is a decision to bind
the header it comes from.

| Slice | Routes | Why it is unavoidable |
|---|---|---|
| PBR | `cna_pbr_material_ext_init`, `cna_pbr_effect_create`, `cna_skinned_pbr_effect_create`, `cna_pbr_effect_set_texture`, `cna_pbr_effect_get_texture` | `engine_layer.h` declares no route that *creates* a `PbrEffect`, and `cna_pbr_material_ext_init` is the only route that fills a 27-field material with CNA's own defaults. The texture pair is there because `apply_material` drops all seven texture slots (ENGINE-005), so without it a PBR effect could never have a texture at all. |
| ASCII | the eight `cna_ascii_post_process_effect_*` routes | `cna_ascii_pass_get_effect` hands out the effect carrying the pass's cell size and quantize mode, and no engine-layer route can read or write either. `create` and `draw` are here because they are the only way to quantize an arbitrary texture into an arbitrary rectangle; an `AsciiPass` runs inside a post-process chain and can do neither. |
| Mesh part | `cna_model_mesh_part_create`, `cna_model_mesh_part_destroy` | `cna_lod_group_ext_add_level` and `cna_instanced_renderer_ext_create` take a `CNA_ModelMeshPartHandle`, and strict XNA's `ModelMeshPart` is a managed object with no native handle -- CNA's native model runtime is a separate concept this binding deliberately does not bind. The native part is built from the strict part's own vertex buffer, index buffer and offsets, so it describes the same geometry rather than a copy. It is private, owned by whichever engine object needed it, and released with it. |

No native model, mesh, part or ASCII effect leaks into the public surface from
any of these.

## The modules

| Module | What it is for |
|---|---|
| `values` | Light values, quality presets, cascade state. Pure data; every default is read from CNA rather than transcribed. |
| `errors` | The exception hierarchy, and the distinction below. |
| `compute` | Compute shaders, storage buffers, memory barriers, GPU timers. |
| `postprocess` | The pass vocabulary, the render-target pool, the chain. |
| `passes` | The concrete passes: tonemap, bloom, colour grade, FXAA, ASCII, and the rest. |
| `atmosphere` | Sky, fog, SSAO, SSR, depth of field, contact shadows, light shafts. |
| `pbr` | Physically based materials and their glTF extensions. |
| `shadows` | Shadow maps: simple, cascaded, cube and spot. |
| `scene` | Particles, decals, the depth/normal prepass, transparency. |
| `pipeline` | The whole-frame render pipeline and its settings. |
| `clustered` | Clustered lighting and area lights. |
| `probes` | Light probes, probe volumes, baking, image-based lighting. |
| `culling` | Level of detail, frustum culling, instancing, indirect draws. |
| `debug` | World-space debug lines and the gizmos built from engine objects. |

## Two kinds of "no"

`UNSUPPORTED` and `UNAVAILABLE` are different facts, and this package never
conflates them:

* `EngineUnavailableError` -- this CNA build has **no engine layer**. It is a
  supported configuration, and every route in the family says so rather than
  answering with a plausible number. The control artifact is this case, and its
  tests assert the answer.
* `EngineUnsupportedError` -- the engine layer is present and this *renderer*
  cannot serve the operation. Compute shaders on a renderer without them, GPU
  culling where a vertex shader may read no storage buffer.

A handful of routes answer in **every** build, because they describe a value
rather than an operation: both `*_ext_init` defaults, `AreaLight.is_valid`, and
the two indirect-draw argument initialisers. `ClusteredLight.is_usable` is the
deliberate opposite -- that rule belongs to the light *set* -- and each is stated
at the property and pinned by a test.

## Ownership

Every owned object is an explicit `close()` with a context manager, and no
`__del__` anywhere: a finaliser running at an arbitrary point on an arbitrary
thread is not a lifetime, and CNA objects are graphics-thread affine.

The systemic finding is **ENGINE-002**: every CNA engine getter that answers
with a handle answers with a *fresh counted view*, whatever its documentation
says, except when it hands back the handle it was given. Following the
documentation exactly leaks one handle per read, and the failure surfaces as an
unrelated game refusing to be destroyed.

That is solved once rather than per route. Two shapes:

* `_cna_native.engine_support.borrowed_view` compares the handle CNA answers
  with against the handle this binding supplied, and releases only a different
  one. Used where the object is the *caller's* -- an effect the caller set, a
  texture the caller bound.
* `_EngineObject._view` builds a facade once per key, caches it, and disposes it
  when the owner closes. Used where the object is CNA's own -- a pass's ASCII
  effect, a forward effect's shader, a BRDF table's texture.

Neither is a table of which routes hand out a view, because a table would go
stale the day CNA changes one.

## Callbacks

Three: the render-pipeline draw, the transparent-draw submission, and the light
probe bake. In each case the trampoline is rooted for exactly as long as CNA can
invoke it -- a bare `CFUNCTYPE(...)(function)` built at a call site is collected
the moment the expression ends -- and a Python exception raised inside is stored
and re-raised *after* the native call returns. An exception unwinding through a C
frame is undefined behaviour, and CNA has render state to unwind first.

## Qualification

Two artifacts, both of CNA 0.21.0:

| | control | gpu |
|---|---|---|
| Renderer | `HEADLESS` | `OPENGLES3`, Mesa GL ES 3.2 (llvmpipe) on an isolated Xvfb display |
| Engine layer | absent | present, revision 2 |
| sha256 | `94078be94dc1f1e6…` | `65ce46a49b754586…` |

Neither was rebuilt for this work.

### Independent oracles

No CNA getter is its own oracle. `tests/engine_oracles.py` computes what CNA
should answer *without calling CNA*, from the algorithm rather than from the
output: the cluster grid's logarithmic slicing and its cluster boxes (with a 4x4
matrix inverse written out by hand), both cases of a spot light's cone sphere,
the whole compressed-row light assignment, Rec. 709 shadow scoring,
Beer-Lambert as a closed form, second-order spherical harmonics from the
Ramamoorthi-Hanrahan constants, Chebyshev visibility, the Hammersley sequence as
a literal bit reversal, GGX importance sampling, cube-face and panorama
conventions, six frustum planes, LOD selection and its hysteresis, and every
debug shape's line count.

The oracles are gated too. `tests/test_engine_oracles.py` checks each against a
case worked by hand *there*, from numbers small enough to verify by reading, and
needs no native library at all -- because an oracle checked against CNA would be
checking the thing it exists to check.

Where an independent implementation would be a transcription rather than a
derivation -- the BRDF table's Monte Carlo integral, the area-light coverage
integrator -- the tests assert what the integral must *be*: a fraction in zero to
one, a unit average direction, monotone in roughness, convergent in sample count,
deterministic. That is stated where it is done, rather than dressed up as an
oracle.

Three answers are also cross-checked against a *second CNA path*: the clustered
assignment's CPU sort against its compute shader (designed to agree exactly, and
asserted to), the GPU instance culler against the CPU frustum test, and the
volume's irradiance against sampling and evaluating separately.

### Falsifiability

`tools/mutation/engine_mutations.py` plants 47 defects one at a time -- an axis
swapped, a bound dropped, a counted view not released, a formula written in
double where CNA writes it in float -- and requires each to make a *focused* test
fail. The oracles are mutated too, deliberately: an oracle wrong in the same way
as CNA would make a whole family agree on a defect.

```text
PLANTED=47 KILLED=47 SURVIVED=0 INAPPLICABLE=0
```

The first run killed 37 and left nine survivors, every one a real gap; all are
closed and the ninth mutation was itself a no-op and was replaced.

The gates are falsifiable too: every extension-surface diagnostic is planted and
required to fail, a bound route nothing calls is rejected, a rule shadowed by an
earlier one is rejected, and a route CNA does not have is shown to land in
`UNREVIEWED`.

## Upstream findings

Eight, in `docs/engine-upstream-findings.md`, each with the exact revision, a
reproducer, expected against actual, what this binding does locally and what
would unblock it. In summary:

| | |
|---|---|
| ENGINE-001 | `cna_compute_shader_create` fails on source that does not compile, where the header says it succeeds and reports invalid |
| ENGINE-002 | every engine getter hands out a counted view, and one says not to release it |
| ENGINE-003 | the first GPU-timer sample is an unsigned 32-bit underflow |
| ENGINE-004 | a chain's GPU timing flag is not observable until it has run |
| ENGINE-005 | `cna_pbr_effect_apply_material` carries every scalar and no texture |
| ENGINE-006 | four clustered constructors document a game and accept a device |
| ENGINE-007 | `importance_sample_ggx` needs a unit normal and does not say so |
| ENGINE-008 | a cullable instance's canonical world is zero, not identity |

Nothing is silently worked around. Where a workaround exists it is visible, said
at the property, and pinned by a test that fails the day CNA fixes the defect.

## What this does not claim

* It does not claim the engine layer is *correct*. It claims that what CNA
  answers has been measured, compared with an independent computation where one
  is possible, and written down where it is not.
* It does not claim every route is exercised on a real GPU. The two artifacts
  are a software rasterizer and a headless build; a route needing a capability
  neither has is reported as blocked rather than assumed to work.
* It does not claim the numbers here hold for a different CNA build. Every
  measurement names the artifact it was taken on.
