# CNA-Python tactical handoff

Date: 2026-08-23.

`MILESTONE_5_COMPLETE=true`

Foundation Milestone 5 is complete. The public Effect + stock-effect + Model
dependency closure is structurally complete, its native and Content/XNB paths
are qualified against the exact CNA ABI-0.7 artifact, and the final wheel has
passed both isolated consumers. No follow-on public XNA family was started.

## Strict result

```text
                                      M5 START  CONTINUATION  FINAL
REFERENCE_TYPES                            257           257    257
REFERENCE_MEMBERS                         2964          2964   2964
EXPECTED_PYTHON_TYPES                      257           257    257
EXPECTED_PYTHON_MEMBERS                   2887          2887   2887
TARGET_TYPES                               126           161    161
TARGET_MEMBERS                            1501          1643   1651
TOTAL_DIAGNOSTICS                          131            96     96
MISSING_TYPE                               131            96     96
MISSING_MEMBER                               0             0      0
COMPLETE_TYPES                             126           161    161
PARTIAL_TYPES                                0             0      0
MISSING_TYPES                              131            96     96
```

The final 1,651 member count is the freshly regenerated authoritative mapping
result; the continuation estimate of 1,643 was not forced. No new public type
was added during the continuation. All 96 diagnostics are whole future types.
The normal strict `--check` is nonzero only for those types.

```text
UNEXPECTED_TYPE=0
UNEXPECTED_MEMBER=0
TYPE_KIND_MISMATCH=0
BASE_MAPPING_MISMATCH=0
INTERFACE_MAPPING_MISMATCH=0
FIELD_MAPPING_MISMATCH=0
PROPERTY_MAPPING_MISMATCH=0
METHOD_SIGNATURE_MAPPING_MISMATCH=0
PARAMETER_MAPPING_MISMATCH=0
RETURN_MAPPING_MISMATCH=0
OVERLOAD_MAPPING_MISMATCH=0
GENERIC_MAPPING_MISMATCH=0
ENUM_VALUE_MISMATCH=0
FLAGS_MAPPING_MISMATCH=0
EVENT_MAPPING_MISMATCH=0
OPERATOR_MAPPING_MISMATCH=0
LANGUAGE_MAPPING_MISMATCH=0
INTERNAL_TYPE_LEAK=0
RAW_HANDLE_LEAK=0
PUBLIC_NATIVE_FFI_LEAK=0
ALLOWLIST_ENTRIES=0
UNMEASURED_STRUCTURAL_CATEGORY=0
ZERO_DIAGNOSTIC_TYPES=161
```

## Dependency closure

The exact 35-type closure is:

- Effects: `Effect`, `EffectTechnique`, `EffectPass`, `EffectParameter`,
  `EffectAnnotation`, their four collections, `EffectParameterClass`,
  `EffectParameterType`, and `EffectMaterial`;
- stock effects/interfaces: `BasicEffect`, `AlphaTestEffect`,
  `DualTextureEffect`, `EnvironmentMapEffect`, `SkinnedEffect`,
  `DirectionalLight`, `IEffectFog`, `IEffectLights`, and `IEffectMatrices`;
- Model: `Model`, `ModelBone`, `ModelMesh`, `ModelMeshPart`, four collections,
  and the four mapped collection enumerators;
- required texture dependencies: `Texture3D` and `TextureCube`, required by
  EffectParameter texture values and EnvironmentMapEffect.

`OcclusionQuery`, `RenderTargetCube`, Curve, Touch, PackedVector, Audio, Media,
Storage, Design, GamerServices, FrameworkDispatcher, and unrelated Graphics
types were deliberately excluded.

## Effect codecs and identity

`Effect` is the sole owned native resource. Techniques, passes, parameters,
annotations, directional lights, and collection handles are real native view
identities. Children retain the Effect, release only their ABI-owned view
handle, never destroy the Effect, and become invalid when the Effect is
disposed. Repeat lookup and `CurrentTechnique` preserve stable public facade
identity. Clone owns a distinct native Effect and independent reflection graph.

The private codec layer implements the complete selected surface:

| Value family | Getter | Setter | Array getter/setter |
|---|---:|---:|---:|
| Boolean, Int32, Single | yes | yes | yes |
| UTF-8 String | yes | yes | not selected by XNA |
| Vector2, Vector3, Vector4 | yes | yes | yes |
| Quaternion | yes | yes | yes |
| Matrix | yes | yes | yes |
| Matrix transpose | yes | yes | yes |
| Texture2D, Texture3D, TextureCube | yes | one native `SetValue` dispatch | not selected by XNA |

Arrays use copied contiguous fixed-width storage; binary32, signed zero,
NaN/Infinity, ordering, dimensions, count prefixes, heterogeneous/empty input,
wrong types, disposed parents/textures, and wrong-device textures are covered.
No ctypes object or native handle leaks through the public namespace. Texture
getters return the retained existing facade and never create a duplicate owner.

`EffectAnnotation` is read-only and implements native Boolean, Int32, Single,
String, Vector2/3/4, and Matrix getters with metadata validation. Collection
name/index lookup, repeat identity, UTF-8 copying, parent retention, and
post-disposal invalidation are verified.

## Stock effects

| Family | Strict | Managed state/validation | Native create/state | Native Apply | Visible output |
|---|---|---|---|---|---|
| BasicEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| AlphaTestEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| DualTextureEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| EnvironmentMapEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| SkinnedEffect | complete | verified | verified | verified | not qualified on HEADLESS |

All stock properties use the underlying CNA Effect state. Directional lights
are stable native child views; BasicEffect reflection/property coherence and
clone independence are verified. `EffectPass.Apply` uses the real reflected
pass and is `VERIFIED_NATIVE`, not an upstream blocker.

The legal project-authored conformance FXB (SHA-256
`2e1fe1dd74d67f4395ae6db4451c1a19ee4478dfe7906f9d665a499e28d2a074`)
reaches `cna_effect_create_compiled`. HEADLESS returns structured result 6, so
the route and rollback are `VERIFIED_NATIVE` while compiled execution is
`BACKEND_BLOCKED`. The fixture is not shipped.

## Texture3D and TextureCube

Exact canonical routes are bound and used:

```text
cna_texture3d_create/destroy/get_info/set_data/get_data
cna_texturecube_create/destroy/get_info/set_data/get_data
```

Both implement exact Color codecs, mip/region/box/face validation, typed
start/count, disposal, and device ownership. Unsupported formats are not
reinterpreted.

- Texture3D implementation and ABI are complete; HEADLESS returns result 6 at
  creation, so execution is `BACKEND_BLOCKED`. Twenty safe failed-create and
  rollback cycles pass.
- TextureCube create/info/dispose are `VERIFIED_NATIVE`; all six face contracts
  are implemented. HEADLESS returns result 6 for Color transfer, so transfer
  execution is `BACKEND_BLOCKED`. Twenty failed-transfer/dispose cycles pass.

## Model XNB and draw

The private general reader registry now contains `ModelReader` and
`BasicEffectReader` plus the already real VertexDeclaration, VertexBuffer,
IndexBuffer, value, and shared-resource readers. No reader is public and no
asset-name condition exists.

The deterministic legal Windows XNB v5 fixture is generated in tests and is
not wheel data. It contains two named bones and a hierarchy, one named mesh,
two tagged mesh parts, a bounding sphere, one real vertex declaration/buffer,
one real index buffer, and one shared native BasicEffect. Both parts receive
the same public buffer/effect facades, and ModelEffectCollection de-duplicates
that Effect exactly once.

Both uncompressed and LZX-compressed assets use the same reader table,
ModelReader, shared-resource fixups, public graph constructors, and native
resources. The compact Model payload uses one LZX frame; persistent multi-frame
state is separately covered by the existing two-frame LZX qualification. An
uncompressed external parent resolving to the compressed Model also passes.

```text
UNCOMPRESSED_MODEL_XNB=PASS
COMPRESSED_MODEL_XNB=PASS
SHARED_BUFFER_IDENTITY=PASS
SHARED_EFFECT_IDENTITY=PASS
CACHE_IDENTITY=PASS
UNLOAD_INVALIDATION=PASS
RELOAD_NEW_GRAPH=PASS
FAILURE_ROLLBACK=PASS
MODEL_DRAW_NATIVE_DISPATCH=PASS
MODEL_RENDERING_VISUALLY_VERIFIED=NO
```

The XNB-loaded draw path is Model -> Mesh/Parts -> shared buffers ->
BasicEffect World/View/Projection -> real Technique/Pass ->
`cna_effect_pass_apply` -> `cna_graphics_device_draw_indexed_primitives`.
There is no Model renderer or custom parameter rewrite.

Negative fixtures cover invalid root/parent/child/mesh-parent/shared-resource
indices, missing Effect, wrong reader type, truncated vertex/index data, and
injected buffer/Effect construction failure. Each failure rolls back, leaves
the cache clean, and permits a later successful load and Game shutdown.

## ABI and qualified runtime

```text
CONTINUATION_BOUND_FUNCTIONS: 214 -> 375
MILESTONE_BOUND_FUNCTIONS: 188 -> 375
CTYPES_SIGNATURE_MEASUREMENTS=375
C_LAYOUT_MEASUREMENTS=653
CTYPES_LAYOUT_MEASUREMENTS=653
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0 / 0x00000700
```

Qualified artifact:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
```

Current CNA HEAD was rechecked read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`; its C-API build remains blocked
upstream at `CnaCApiCoreExt.cpp:250` by renderer identity `49 == 50`. CNA was
not modified.

## Behavior and ownership

```text
OBSERVATIONS: 108 -> 111
ASSERTIONS: 465 -> 496
FAILURES=0
PROVENANCE=pinned XNA metadata and IL/algorithm analysis; not HEADLESS behavior
```

New platform-neutral groups cover Effect enums/defaults/validation, light
identity/defaults, Model collection behavior, graph identity, and bone matrix
copying. CNA pointer/result/draw behavior remains integration evidence.

```text
EFFECT_BASE_CYCLES=20
EFFECT_CLONE_CYCLES=20
EFFECT_PARAMETER_CYCLES=20
EFFECT_PARENT_CHILD_CYCLES=20
STOCK_EFFECT_CYCLES=20
MODEL_DIRECT_GRAPH_CYCLES=20
MODEL_XNB_CYCLES=20
COMPRESSED_MODEL_CYCLES=20
MODEL_DRAW_CYCLES=20
MODEL_UNLOAD_RELOAD_CYCLES=20
TEXTURE3D_FAILED_CREATE_CYCLES=20
TEXTURECUBE_FAILED_TRANSFER_CYCLES=20
NATIVE_CRASHES=0
OBSERVED_UAF=0
DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

The pre-existing general native and Content stress suites also pass at 20
cycles. No allocator-level leak claim is made without sanitizers.

## Runtime capability inventory

The 57-row inventory records these Milestone 5 capabilities separately:

- `VERIFIED_NATIVE`: Effect reflection, typed parameters, annotations,
  EffectPass.Apply, compiled create route, all five stock effects,
  EffectMaterial, TextureCube creation/metadata, Model.Draw dispatch, Model XNB,
  and compressed Model XNB;
- `VERIFIED_MANAGED`: Model graph semantics;
- `BACKEND_BLOCKED`: compiled Effect execution, stock-effect visible output,
  Texture3D creation, TextureCube Color transfer, and Model visible output.

There is no coarse “Effects blocked” classification. No Milestone 5 row remains
`UNIMPLEMENTED_CNA_PYTHON`; unrelated `RenderTargetCube` remains explicitly
deferred.

## Final package and isolated consumers

Version remains `0.1.0.dev0`.

```text
WHEEL_FILENAME=cna_python-0.1.0.dev0-py3-none-any.whl
WHEEL_SHA256=a0c4167e87afe34bff78d96878c4f5196bf203b77191cf9338155878cb91da33
WHEEL_ENTRIES=49
SDIST_FILENAME=cna_python-0.1.0.dev0.tar.gz
SDIST_SHA256=2f290dce01e90722de9497dc78978d5b980a0ae1dbdf7988947f2d9cca2e6ce6
SDIST_ENTRIES=123
FORBIDDEN_WHEEL_ENTRIES=0
FORBIDDEN_SDIST_ENTRIES=0
ABSOLUTE_DEVELOPER_PATHS=0
BUNDLED_NATIVE_LIBRARIES=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0
```

A fresh generated consumer installed that exact wheel with no editable install,
source checkout import, sibling dependency, or `PYTHONPATH`. Import and compile
probes pass; 60 and 600 frame runs pass.

The maintained template source was unchanged in Milestone 5. A byte-identical
clean copy in `/tmp` installed the same exact wheel and passed import, compile,
60 frames, and 600 frames. The generated exact-wheel consumer also passed
60/600. No Effect, Model, shader, or 3D showcase was added.

## Remaining inventory

The 96 whole missing types are: Framework Curve/FrameworkDispatcher 7, Audio
19, Design 13, GamerServices 1, unrelated Graphics 2 (`OcclusionQuery`,
`RenderTargetCube`), PackedVector 19, Touch 8, Media 24, and Storage 3.

No follow-on family is started. The next coherent architectural boundary should
be the Audio runtime/content graph—SoundEffect/instances/dynamic streaming and
AudioEngine/WaveBank/SoundBank/Cue, with microphone and FrameworkDispatcher
only where authoritative dependencies require them—not whichever family has
the fewest types.

## Reproduction

```bash
python3 -m compileall -q src tests tools
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so CNA_PYTHON_COMPILED_EFFECT_FIXTURE=/absolute/path/CnaConformanceEffect.fxb python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # nonzero only for 96 absent types
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/generate_runtime_capabilities.py
python3 tools/audit_cna_abi.py --cna-root /qualified/cna/source --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/native_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/content_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/effect_model_ownership_stress.py --cycles 20
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```
