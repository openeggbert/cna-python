# Foundation Milestone 5: Effect and Model evidence

> **Historical record.** This documents the state at its milestone, measured against
> the CNA `0.7.0` generation on a non-windowed backend with a null audio device. It is
> kept as written. The current boundary is CNA `0.21.0`; for what holds now see
> [`cna-abi-audit.md`](cna-abi-audit.md) and
> [`generated/runtime-capabilities.md`](generated/runtime-capabilities.md), which
> supersede every runtime claim below.

Date: 2026-08-23. Status: complete on the qualified Linux x86-64 HEADLESS ABI-0.7 runtime. This is command-path and ownership evidence, not visible 3D rendering evidence.

## Public dependency closure

The selected closure contains 35 types: `AlphaTestEffect`, `BasicEffect`, `DirectionalLight`, `DualTextureEffect`, `Effect`, `EffectAnnotation`, `EffectAnnotationCollection`, `EffectMaterial`, `EffectParameter`, `EffectParameterClass`, `EffectParameterCollection`, `EffectParameterType`, `EffectPass`, `EffectPassCollection`, `EffectTechnique`, `EffectTechniqueCollection`, `EnvironmentMapEffect`, `IEffectFog`, `IEffectLights`, `IEffectMatrices`, `SkinnedEffect`, `Model`, `ModelBone`, `ModelBoneCollection`, `ModelBoneCollection.Enumerator`, `ModelEffectCollection`, `ModelEffectCollection.Enumerator`, `ModelMesh`, `ModelMeshCollection`, `ModelMeshCollection.Enumerator`, `ModelMeshPart`, `ModelMeshPartCollection`, `ModelMeshPartCollection.Enumerator`, `Texture3D`, and `TextureCube`.

`Texture3D` and `TextureCube` are required by the selected `EffectParameter` texture getters and `SetValue(Texture)` overload and by `EnvironmentMapEffect.EnvironmentMap`. `OcclusionQuery`, `RenderTargetCube`, PackedVector, Curve, Touch, Audio, Media, Storage, Design, GamerServices, FrameworkDispatcher, and unrelated Graphics types were deliberately excluded.

## Effect ownership and native identity

`Effect` is one owned native game resource. Techniques, passes, parameters, annotations, directional lights, and their collection handles are real stable native views. Each Python child strongly retains its Effect, destroys only its own ABI-owned view handle, never destroys the Effect, and is invalidated before the Effect handle is destroyed. Repeat reads return the cached public facade while a native lookup is also performed and checked against the cache. CurrentTechnique resolves to the same cached technique facade. Clone owns a distinct native Effect; disposing either source or clone leaves the other usable.

No technique, pass, parameter, annotation, or light is a synthetic execution facade. `EffectPass.Apply` calls `cna_effect_pass_apply` with the reflected pass handle. Parent-before-child, child-before-parent, repeated Apply, clone separation, and post-disposal access are covered by integration tests and 20-cycle stress groups.

## Typed Effect codecs

One private `_effect_codec` layer implements the selected `EffectParameter` contract:

| Family | Get | Set | Arrays |
|---|---:|---:|---:|
| Boolean, Int32, Single | yes | yes | yes |
| UTF-8 String | yes | yes | not an XNA selected overload |
| Vector2, Vector3, Vector4 | yes | yes | yes |
| Quaternion | yes | yes | yes |
| Matrix | yes | yes | yes |
| Matrix transpose | yes | yes | yes |
| Texture2D, Texture3D, TextureCube | yes | one `SetValue(Texture)` dispatch | not an XNA selected overload |

Values cross as explicit fixed-width ctypes storage. Scalars and every array are copied; matrices are contiguous row-major `CNA_Matrix` values. Callers never receive ctypes pointers or temporary storage. Integer range, binary32 narrowing, UTF-8 copying, metadata class/type/dimension checks, exact runtime overload dispatch, heterogeneous and empty sequence rejection, disposed texture rejection, and GraphicsDevice identity are enforced. Texture getters return only the retained non-owning public resource facade for the native handle; no second owner is created.

`EffectAnnotation` uses the same read codec primitives without inheriting setters. Boolean, Int32, Single, String, Vector2/3/4, and Matrix getters validate native metadata before reading. Annotation and parameter collection name/semantic lookups, repeat identity, children, structure members, and parent invalidation use native reflection identities.

## Stock effects

| Effect | Strict | Managed validation/retention | Native create/state | Native Apply | Visible output |
|---|---|---|---|---|---|
| BasicEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| AlphaTestEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| DualTextureEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| EnvironmentMapEffect | complete | verified | verified | verified | not qualified on HEADLESS |
| SkinnedEffect | complete | verified | verified | verified | not qualified on HEADLESS |

All public matrices, fog, light, material, texture, alpha, and effect-specific properties call canonical CNA getters/setters instead of a parallel Python state graph. Managed state stores only strong texture-facade retention and stable light views. `DirectionalLight0/1/2` each cache one native view. Skinned bone transforms use exact contiguous native arrays and enforce the CNA/XNA 1-through-72 bound. `EffectMaterial` uses `cna_effect_material_create` and owns a distinct Effect.

The project-authored legal `CnaConformanceEffect.fxb` fixture (SHA-256 `2e1fe1dd74d67f4395ae6db4451c1a19ee4478dfe7906f9d665a499e28d2a074`) reaches `cna_effect_create_compiled`. The qualified HEADLESS library returns structured result 6 because it does not advertise compiled-effect execution. The ABI route and rollback are verified; compiled shader execution and visible output are `BACKEND_BLOCKED`.

## Texture3D and TextureCube

Both types bind canonical ABI-0.7 create/destroy/info/set/get routes, exact versioned descriptors, mip/region validation, typed start/count ranges, disposal, and Color storage. Unsupported formats are not reinterpreted.

- Texture3D: HEADLESS returns structured result 6 at creation. Twenty repeated failures publish no object and leave Game shutdown clean. Implementation is complete; execution is `BACKEND_BLOCKED`.
- TextureCube: create/info/dispose are `VERIFIED_NATIVE`. All six face, mip, and rectangle contracts are implemented. HEADLESS returns result 6 for Color storage transfer; twenty create/failed-transfer/dispose cycles pass. Transfer execution is `BACKEND_BLOCKED`.

## Model XNB graph

The private built-in `ModelReader` and `BasicEffectReader` use the ordinary Content registry. The deterministic Windows XNB v5 fixture is generated by tests and is not wheel package data. It contains two named bones with a valid parent/child hierarchy, a non-root mesh parent, one named mesh, two tagged mesh parts, a bounding sphere, one real vertex declaration/buffer, one real index buffer, one shared BasicEffect, and model/mesh/part tags. Both parts receive the same public VertexBuffer, IndexBuffer, and BasicEffect facades. `ModelEffectCollection` identity-deduplicates the shared Effect.

The uncompressed and LZX-compressed assets enter through the same XNB header, reader table, `ModelReader`, shared-resource fixups, and public graph constructors. The compact 654-byte payload needs one canonical LZX frame; persistent two-frame LZX state is independently covered by the existing full-32-KiB first-frame test. An uncompressed external-reference parent resolves to the compressed Model and observes the same Content cache identity.

Repeated Load returns one cached Model. Unload unbinds device resources, invalidates the Model and retained bone/mesh/part/pass facades, and destroys the shared resources once in reverse ownership order. Reload returns a new valid graph. Negative fixtures cover invalid root, parent, child, mesh-parent and shared-resource references, null/missing Effect, wrong resource reader type, truncated vertex/index data, and injected native buffer/Effect construction failures. Each becomes `ContentLoadException`, leaves the cache clean, and permits a later successful load and Game shutdown.

## Model.Draw

The XNB-loaded path is:

```text
Model.Draw
  -> ModelMesh / two ModelMeshParts
  -> shared VertexBuffer + IndexBuffer binding
  -> BasicEffect World/View/Projection
  -> CurrentTechnique / EffectPass
  -> cna_effect_pass_apply
  -> GraphicsDevice.DrawIndexedPrimitives
  -> cna_graphics_device_draw_indexed_primitives
```

`MODEL_DRAW_NATIVE_DISPATCH=PASS`. There is no special Model renderer and no arbitrary custom parameter rewrite. The qualified backend is HEADLESS, so `MODEL_RENDERING_VISUALLY_VERIFIED=NO`.

## Measured evidence

```text
TARGET_TYPES=161
TARGET_MEMBERS=1651
MISSING_TYPES=96
MISSING_MEMBERS=0
PARTIAL_TYPES=0
all mismatch/leak/allowlist/unmeasured categories=0

BOUND_FUNCTIONS=375
CTYPES_SIGNATURE_MEASUREMENTS=375
C_LAYOUT_MEASUREMENTS=653
CTYPES_LAYOUT_MEASUREMENTS=653
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0

OBSERVATIONS=111
ASSERTIONS=496
FAILURES=0
```

Dedicated stress runs 20 cycles each for base Effect, clone, parameters, parent/child views, all stock effects, direct Model graphs, uncompressed Model XNB, compressed Model XNB, Model draw, Model unload/reload, Texture3D safe failed creation, and TextureCube safe failed transfer. `NATIVE_CRASHES=0`, `OBSERVED_UAF=0`, and `DOUBLE_FREE=0`. Sanitizers were not run, so no allocator-level leak claim is made.
