# CNA-Python tactical handoff

Date: 2026-08-23.

Foundation Milestone 3 is complete. The selected Game object model and 2D
graphics device/state/resource foundation is structurally complete except for
the intentionally deferred Content/XNB gateway. Runtime claims remain separate
from structural completeness in `docs/runtime-capabilities.json`.

## Strict before and after

```text
                                      BEFORE  AFTER
REFERENCE_TYPES                          257    257
REFERENCE_MEMBERS                       2964   2964
EXPECTED_PYTHON_TYPES                    257    257
EXPECTED_PYTHON_MEMBERS                 2887   2887
TARGET_TYPES                              51    115
TARGET_MEMBERS                          1003   1465
TOTAL_DIAGNOSTICS                        310    144
MISSING_TYPE                             206    142
MISSING_MEMBER                           104      2
COMPLETE_TYPES                            41    114
PARTIAL_TYPES                             10      1
MISSING_TYPES                            206    142
```

Every final mismatch/safety category is zero:

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
```

The normal strict `--check` remains nonzero only for genuine missing surface.
The leak-only gate passes.

The only partial type is:

```text
Microsoft.Xna.Framework.Content.ContentManager=2
    OpenStream(System.String)
    ReadAsset(System.String,System.Action`1[System.IDisposable])
```

`ContentManager.ServiceProvider` is complete and uses the owning Game's stable,
isolated service container.

## Game foundation

- `Game` local diagnostics: **0 / STRICT_COMPLETE**.
- `IGameComponent`, `IUpdateable`, `IDrawable`, `GameComponent`,
  `DrawableGameComponent`, `GameComponentCollection`, collection event args,
  `GameServiceContainer`, `LaunchParameters`, and `GameWindow` are complete.
- Component insertion/equal-order behavior, live Enabled/Visible checks,
  snapshot traversal, traversal-time removal, self-removal, order mutation,
  initialization, and collection events are **MANAGED_VERIFIED**.
- Services are exactly keyed, reject duplicate/null registrations, preserve
  provider identity, and are isolated per Game: **MANAGED_VERIFIED**.
- `ResetElapsedTime` and `SuppressDraw` reach the active CNA Game lifecycle:
  **NATIVE_VERIFIED**.
- Activation/deactivation and window event infrastructure is real, but HEADLESS
  produces no OS transition and no fake event: **BACKEND_BLOCKED** for delivery.
- HEADLESS `GameWindow.Handle` is the real null handle, never a Python object id.

## Graphics foundation

| Family | Structural status | Runtime qualification |
|---|---|---|
| `SurfaceFormat` and selected graphics enums | STRICT_COMPLETE | MANAGED_VERIFIED from XNA metadata |
| `Viewport.Project` / `Unproject` | STRICT_COMPLETE | MANAGED_VERIFIED binary32 behavior |
| `GraphicsResource` | STRICT_COMPLETE | NATIVE_VERIFIED disposal/name/tag; exactly-once event |
| resource-created/destroyed event args | STRICT_COMPLETE | Event delivery UPSTREAM_CNA_BLOCKED by identityless ABI payloads |
| adapters/display/presentation/device information | STRICT_COMPLETE | NATIVE_VERIFIED on the actual HEADLESS adapter |
| blend/depth/rasterizer/sampler states and stock states | STRICT_COMPLETE | MANAGED defaults/freeze + NATIVE binding verified |
| sampler/texture collections | STRICT_COMPLETE | NATIVE_VERIFIED durable per-device stage facades |
| `Texture` / `Texture2D` | STRICT_COMPLETE | NATIVE metadata, transfers, PNG and JPEG verified |
| vertex declarations and four built-in vertex codecs | STRICT_COMPLETE | MANAGED_VERIFIED deterministic layouts |
| static/dynamic vertex/index buffers and bindings | STRICT_COMPLETE | NATIVE_VERIFIED ownership, transfer, binding and lifetime guards |
| draw routes | STRICT_COMPLETE | Native dispatch verified; 3D draw output BACKEND_BLOCKED under HEADLESS |
| instanced draw | STRICT_COMPLETE | Real route bound; HARDWARE_PENDING, never emulated |
| `RenderTarget2D` and render-target binding | STRICT_COMPLETE | NATIVE command/lifetime verified; visible output HARDWARE_PENDING |
| `RenderTargetCube` | missing/deferred with TextureCube family | UNIMPLEMENTED_CNA_PYTHON |
| `GraphicsDevice` | STRICT_COMPLETE, local diagnostics 0 | Selected native state/binding/reset/present routes verified |
| `GraphicsDeviceManager` | STRICT_COMPLETE, local diagnostics 0 | Native lifecycle and mutable preparing-settings callback verified |
| `SpriteFont` / all selected `DrawString` overloads | STRICT_COMPLETE | Private legal glyph factory and native glyph submissions verified |

Important runtime qualifications:

- Default `Present()` reaches CNA. Rectangle/window Present has no ABI-0.7 route
  and raises `NativeCapabilityError`: **UPSTREAM_CNA_BLOCKED**.
- Resetting/Reset are real native transitions. Deterministic DeviceLost remains
  **BACKEND_BLOCKED** on HEADLESS and is never fabricated.
- `ResourceCreated`/`ResourceDestroyed` public infrastructure and argument types
  exist, but stable identity/Tag delivery is **UPSTREAM_CNA_BLOCKED**.
- ABI 0.7 cannot combine DynamicVertexBuffer raw destination offset with typed
  streaming options in one call: that combination is **UPSTREAM_CNA_BLOCKED**.
- Public SpriteFont loading is **FIXTURE_PENDING** on Content/XNB; runtime glyph
  metrics, measurement, missing-character/default-character behavior, and
  DrawString are implemented without rectangle fakes.
- HEADLESS command success is not visible GPU-rendering evidence.

## ABI evidence

Current CNA HEAD was rechecked read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. Its clean C-API build remains
blocked by the upstream renderer identity assertion `49 == 50`; CNA was not
modified. Its checkout has one unrelated pre-existing untracked discovery file.

Qualified artifact:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
ABI=0.7.0 / 0x00000700 exact
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
BOUND_FUNCTIONS=186
CTYPES_SIGNATURE_MEASUREMENTS=186
C_LAYOUT_MEASUREMENTS=526
CTYPES_LAYOUT_MEASUREMENTS=526
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

The binding uses only canonical ABI-0.7 C headers/symbols. It binds neither C++
nor another language binding. The qualified older artifact permits destroying
bound vertex/index buffers even though CNA HEAD rejects it; Python therefore
guards disposal and unbinds retained resources before parent shutdown.

## Behavior corpus

```text
OBSERVATIONS: 92 -> 98
ASSERTIONS: 360 -> 413
FAILURES: 0
PROVENANCE: PURE_XNA_DERIVED metadata/IL/algorithm evidence
```

New groups are:

```text
graphics.surface_format.values
graphics.viewport.project.bits
graphics.viewport.roundtrip.bits
graphics.presentation.defaults
graphics.state.defaults
graphics.vertex.strides
```

HEADLESS/backend observations are not encoded as XNA goldens.

## Ownership stress

```text
LIFECYCLE_CYCLES=20
CHILD_RESOURCE_CYCLES=20
EXPLICIT_DOUBLE_DISPOSE_CYCLES=10
PARENT_BEFORE_CHILD_CYCLES=20
BUFFER_FAMILY_CYCLES=20
RENDER_TARGET_CYCLES=20
SPRITE_FONT_CYCLES=20
GRAPHICS_STATE_CYCLES=20
CALLBACK_EXCEPTION_CYCLES=20
CRASHES=0
OBSERVED_UAF_OR_DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

Stress covers state/buffer/target/font resource families, child-before-parent,
parent-before-child, double dispose, bound-dispose rejection, replacement,
dynamic discard transfer, shutdown with live children, and handler exception.
No allocator-leak claim is made without sanitizer evidence, and no interpreter
finalizer calls CNA.

## Package and templates

Version remains `0.1.0.dev0`.

```text
wheel=cna_python-0.1.0.dev0-py3-none-any.whl
wheel SHA-256=3be58735aa12a4558a93c7a6c6a4f31e804520f35fc38b534d81c1115ff3990d
wheel entries=41
sdist=cna_python-0.1.0.dev0.tar.gz
sdist SHA-256=9b4c47c91aff7645f779223743479507eddcb1e2b7a8f3e78ec5e1f17e66112f
sdist entries=107
forbidden wheel entries=0
forbidden sdist entries=0
absolute developer path leaks=0
private/bundled CNA native library=0
```

The exact final wheel passed import and compile probes in a fresh venv. The
maintained template source was not changed; maintained 60/600 runs and generated
installed-wheel 60/600 runs all pass. Generated sources contain zero absolute
developer paths, sibling-source dependencies, or PYTHONPATH dependencies.

## Content, Curve, and next milestone

Full XNB was not started. `OpenStream` remains deferred until a formal title-
content path rule exists, and `ReadAsset` remains deferred until the complete
reader/type-reader/shared-resource/external-reference architecture can be built.

The optional Curve family remained deferred.

The next dependency-complete milestone is Content/XNB: implement the title-
content path, `ContentReader`, reader manager/type readers, shared resources,
external references, and LZX only when the full dependency chain requires it.
That milestone can then make public SpriteFont loading real. Effects/models,
audio/media, storage, touch, Texture3D/Cube content, and broad 3D remain deferred.

## Reproduction commands

```bash
python3 -m compileall -q src tests tools
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # expected nonzero for genuine missing surface
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/generate_runtime_capabilities.py
python3 tools/generate_milestone3_dependency_matrix.py
python3 tools/audit_cna_abi.py --cna-root ../../cna --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/native_ownership_stress.py --cycles 20
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```
