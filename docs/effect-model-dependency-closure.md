# Effect/Model dependency closure

Milestone 5 selected the following public closure from the pinned XNA contract:

| Type | Why required | Public dependency | Native dependency | XNB dependency |
|---|---|---|---|---|
| Effect, EffectTechnique, EffectPass | Core effect ownership and application | GraphicsResource, collections | `cna_effect_create_*`, reflection views, `cna_effect_pass_apply` | Effect/stock readers |
| EffectParameter, EffectAnnotation and collections/enums | Effect state and reflection contract | vectors, matrices, textures | typed parameter/reflection routes | compiled/stock material state |
| BasicEffect, AlphaTestEffect, DualTextureEffect, EnvironmentMapEffect, SkinnedEffect | XNA stock effect families | Effect, IEffect* | five canonical stock constructors and effect apply | stock-effect readers |
| DirectionalLight, IEffectFog, IEffectLights, IEffectMatrices | Stock-effect shared state | stock effects | parent-owned stock state | material graph |
| EffectMaterial | Public material graph node | Effect | Effect ownership | model material graph |
| Model, ModelBone, ModelMesh, ModelMeshPart and collections/enumerators | Model graph and ordinary draw pipeline | Matrix, BoundingSphere, buffers, Effect | existing buffer binding/draw routes | Model reader graph |
| Texture3D, TextureCube | Required by EffectParameter and EnvironmentMapEffect signatures | Texture, SurfaceFormat, CubeMapFace | volume texture transfer routes | texture dependencies |

Deliberately excluded: `OcclusionQuery`, `RenderTargetCube`, all PackedVector
types, and every Audio, Media, Storage, Design, Touch, Curve, GamerServices,
and unrelated graphics family. They are not in the selected public dependency
closure.
