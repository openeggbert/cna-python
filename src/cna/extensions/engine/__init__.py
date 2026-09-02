"""CNA's modern engine layer: rendering capability XNA 4.0 never had.

This is a **CNA extension**, not part of XNA. Physically based materials,
post-process chains, shadow cascades, clustered lighting, light probes, GPU
compute and the rest have no ``Microsoft.Xna.Framework`` counterpart at all,
which is exactly why they live here.

**The strict XNA projection is untouched by this package.** No name in
``Microsoft.Xna.Framework`` changes, gains a member, or learns that this package
exists. The dependency runs one way -- ``cna.extensions.engine`` accepts strict
``GraphicsDevice``, ``Texture2D``, ``Matrix``, ``Vector3`` and ``Color`` values
-- and the extension gate asserts in a fresh interpreter that importing the XNA
namespace loads no ``cna`` module.

Two kinds of "not supported"
----------------------------

Every engine route is exported in every CNA build. That is deliberate: a build
option that changed the export list would leave the recorded ABI baseline
describing neither build. So symbol presence proves nothing, and the routes that
need a native engine object answer ``CNA_RESULT_NOT_SUPPORTED`` when the layer
was configured out -- the same result code a renderer without a capability
gives.

This package never conflates the two. :func:`is_available` asks
``cna_engine_layer_get_version``; a zero means **this build has no engine
layer**, and :class:`~cna.extensions.engine.errors.EngineUnavailableError` says
so. A present layer that still cannot do something raises
:class:`~cna.extensions.engine.errors.EngineUnsupportedError`, and wherever CNA
offers a support query the public object exposes it so a caller can ask first.

Ownership
---------

Every object holding a CNA handle has an explicit ``close`` and works as a
context manager. Closing is deterministic and ordered by the caller. Nothing
relies on ``__del__``: interpreter shutdown may already have unloaded the
library, so a finalizer that called into it would be a crash rather than a
cleanup.

No raw handle, ctypes object or result code is public anywhere in this package.

Importing this module needs no native library. Constructing anything in it does.
"""

from __future__ import annotations

from . import (
    atmosphere, clustered, compute, errors, passes, pbr, pipeline, postprocess,
    scene, shadows, values,
)
from .compute import (
    ComputeShader, GpuTimer, ImageAccess, MemoryBarrier, StorageBuffer,
    barrier_contains,
)
from .pipeline import (
    FrameStatistics, MINIMUM_FXAA_EDGE_THRESHOLD, MINIMUM_GAMMA, RenderPipeline,
    RenderPipelineSettings, TonemappingMode,
)
from .postprocess import (
    BlitPass, EffectPass, FullscreenPass, PassTiming, PostProcessChain,
    PostProcessContext, PostProcessPass, RenderTargetPool, RenderTargetScope,
    ShaderEffectFactory, bind_render_target,
)
from .atmosphere import (
    AerialPerspectivePass, AtmosphericSky, ContactShadowPass,
    DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES, DepthOfFieldPass, HeightFogPass,
    LIGHT_SHAFT_STEP_COUNT, LightShaftPass, MotionBlurPass,
    SSR_MAXIMUM_STEP_COUNT, SSR_MINIMUM_STEP_COUNT, Skybox, SsaoPass, SsrPass,
    VOLUMETRIC_FOG_SLICE_COUNT, VOLUMETRIC_FOG_SLICE_RESOLUTION,
    VolumetricFogPass, air_mass_for_distance, circle_of_confusion_millimetres,
    combine_visibility, compute_skybox_view_ray, contact_shadow_occlusion_glsl,
    is_occluded, optical_depth, sky_model_glsl, sky_radiance,
    ssao_occlusion_glsl, ssao_sample_count_for, transmittance,
)
from .passes import (
    AsciiEffect, AsciiPass, AsciiQuantizeMode, AutoExposure, BloomPass,
    COLOR_GRADE_MAXIMUM_LUT_SIZE, CUBE_LUT_MAXIMUM_SIZE, CUBE_LUT_MINIMUM_SIZE,
    ChromaticAberrationPass, ColorGradePass, CubeLut, DisplayColorSpace,
    FilmGrainPass, FxaaPass, HDR_DEFAULT_PAPER_WHITE_NITS, HDR_DEFAULT_PEAK_NITS,
    HdrDisplayOutput, LENS_FLARE_GHOST_COUNT, LensFlarePass, LutInterpolation,
    MOTION_BLUR_SAMPLE_COUNT, SpatialUpscalePass, ToneMapPass,
    bloom_extract_channel, bloom_iterations_for, create_identity_lut, decode_pq,
    encode_for_display, encode_pq, fxaa_edge_threshold_for, fxaa_fragment_glsl,
    is_identity_scale, lut_size_for_strip, rec709_to_rec2020, roll_off,
    tonemap_channel,
)
from .pbr import (
    AlphaMode, GltfMaterialExtensionSource, GltfMaterialSource, PBR_TEXTURE_SLOT_COUNT,
    PbrEffect, PbrMaterial, PbrMaterialExtensions, PbrTextureSlot, SkinnedPbrEffect,
    TextureTransform, TransparencyMode, build_extensions, build_material,
    thin_film_iridescence, thin_film_iridescence_glsl,
)
from .clustered import (
    AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT, AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE,
    AREA_LIGHT_QUAD_CORNER_COUNT, AreaLightBrdfTable, AreaLightBrdfTerms,
    CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS, CLUSTERED_COMPUTE_DEFAULT_STRIDE,
    CLUSTERED_FORWARD_MAXIMUM_LIGHTS_PER_FRAGMENT, CLUSTERED_LIGHT_SET_MAXIMUM,
    CLUSTERED_SHADOW_DEFAULT_BUDGET, CLUSTERED_SHADOW_DEFAULT_HYSTERESIS,
    ClusteredForwardEffect, ClusteredLightAssignment, ClusteredLightBuffer,
    ClusteredLightCompute, ClusteredLightGrid, ClusteredLightSet,
    ClusteredShadowPolicy, area_light_contribution, area_light_coverage,
    area_light_quad, area_light_shading_glsl, brdf_lookup_glsl, evaluate_brdf,
    light_contribution, light_lookup_glsl, lobe_scale_for, volume_attenuation,
)
from .scene import (
    DecalPass, DepthEncoding, DepthNormalPrepass, PARTICLE_STORAGE_BINDING,
    PARTICLE_SYSTEM_DEFAULT_CAPACITY, Particle, ParticleEmitterSettings,
    ParticleSystem, TransparentDrawList, WeightedBlendedTransparency,
    camera_position_of, decode_velocity, depth_decode_glsl, has_velocity,
    is_inside_decal_box, pack_depth, particle_lookup_glsl, particle_random,
    sort_key, transparency_accumulation_glsl, transparency_weight, unpack_depth,
    uses_packed_depth, velocity_decode_glsl,
)
from .shadows import (
    CascadedShadowMap, CubeShadowMap, ShadowMap, ShadowReceiver, SpotShadowMap,
    compute_light_projection, compute_light_view, cube_shadow_map_size_for,
    shadow_filter_radius_for, shadow_map_size_for, supports_shadow_sampling,
)
from .values import (
    AreaLight, AreaLightShape, ClusteredLight, ClusteredLightKind,
    DirectionalLight, PointLight, PunctualLight, PunctualLightKind,
    RenderQuality, ShadowCascadeState, ShadowQuality, SpotLight,
    CUBE_SHADOW_FACE_COUNT, FRUSTUM_CORNER_COUNT, SHADOW_CASCADE_MAXIMUM,
)
from .errors import (
    ComputeShaderCompileError, EngineArgumentError, EngineDisposedError,
    EngineError, EngineInternalError, EngineStateError, EngineThreadError,
    EngineUnavailableError, EngineUnsupportedError,
)

__all__ = [
    "air_mass_for_distance",
    "area_light_contribution",
    "area_light_coverage",
    "area_light_quad",
    "area_light_shading_glsl",
    "atmosphere",
    "barrier_contains",
    "bind_render_target",
    "bloom_extract_channel",
    "bloom_iterations_for",
    "brdf_lookup_glsl",
    "build_extensions",
    "build_material",
    "camera_position_of",
    "circle_of_confusion_millimetres",
    "clustered",
    "combine_visibility",
    "compute",
    "compute_light_projection",
    "compute_light_view",
    "compute_skybox_view_ray",
    "contact_shadow_occlusion_glsl",
    "create_identity_lut",
    "cube_shadow_map_size_for",
    "decode_pq",
    "decode_velocity",
    "depth_decode_glsl",
    "encode_for_display",
    "encode_pq",
    "errors",
    "evaluate_brdf",
    "fxaa_edge_threshold_for",
    "fxaa_fragment_glsl",
    "has_velocity",
    "is_available",
    "is_identity_scale",
    "is_inside_decal_box",
    "is_occluded",
    "layer_version",
    "layer_version_string",
    "light_contribution",
    "light_lookup_glsl",
    "lobe_scale_for",
    "lut_size_for_strip",
    "optical_depth",
    "pack_depth",
    "particle_lookup_glsl",
    "particle_random",
    "passes",
    "pbr",
    "pipeline",
    "postprocess",
    "rec709_to_rec2020",
    "roll_off",
    "scene",
    "shadows",
    "shadow_filter_radius_for",
    "shadow_map_size_for",
    "sky_model_glsl",
    "sky_radiance",
    "sort_key",
    "ssao_occlusion_glsl",
    "ssao_sample_count_for",
    "supports_shadow_sampling",
    "thin_film_iridescence",
    "thin_film_iridescence_glsl",
    "tonemap_channel",
    "transmittance",
    "transparency_accumulation_glsl",
    "transparency_weight",
    "unpack_depth",
    "uses_packed_depth",
    "values",
    "velocity_decode_glsl",
    "volume_attenuation",
    "AerialPerspectivePass",
    "AlphaMode",
    "AreaLight",
    "AreaLightBrdfTable",
    "AreaLightBrdfTerms",
    "AreaLightShape",
    "AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT",
    "AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE",
    "AREA_LIGHT_QUAD_CORNER_COUNT",
    "AsciiEffect",
    "AsciiPass",
    "AsciiQuantizeMode",
    "AtmosphericSky",
    "AutoExposure",
    "BlitPass",
    "BloomPass",
    "CascadedShadowMap",
    "ChromaticAberrationPass",
    "ClusteredForwardEffect",
    "ClusteredLight",
    "ClusteredLightAssignment",
    "ClusteredLightBuffer",
    "ClusteredLightCompute",
    "ClusteredLightGrid",
    "ClusteredLightKind",
    "ClusteredLightSet",
    "ClusteredShadowPolicy",
    "CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS",
    "CLUSTERED_COMPUTE_DEFAULT_STRIDE",
    "CLUSTERED_FORWARD_MAXIMUM_LIGHTS_PER_FRAGMENT",
    "CLUSTERED_LIGHT_SET_MAXIMUM",
    "CLUSTERED_SHADOW_DEFAULT_BUDGET",
    "CLUSTERED_SHADOW_DEFAULT_HYSTERESIS",
    "ColorGradePass",
    "COLOR_GRADE_MAXIMUM_LUT_SIZE",
    "ComputeShader",
    "ComputeShaderCompileError",
    "ContactShadowPass",
    "CubeLut",
    "CubeShadowMap",
    "CUBE_LUT_MAXIMUM_SIZE",
    "CUBE_LUT_MINIMUM_SIZE",
    "CUBE_SHADOW_FACE_COUNT",
    "DecalPass",
    "DepthEncoding",
    "DepthNormalPrepass",
    "DepthOfFieldPass",
    "DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES",
    "DirectionalLight",
    "DisplayColorSpace",
    "EffectPass",
    "EngineArgumentError",
    "EngineDisposedError",
    "EngineError",
    "EngineInternalError",
    "EngineStateError",
    "EngineThreadError",
    "EngineUnavailableError",
    "EngineUnsupportedError",
    "FilmGrainPass",
    "FrameStatistics",
    "FRUSTUM_CORNER_COUNT",
    "FullscreenPass",
    "FxaaPass",
    "GltfMaterialExtensionSource",
    "GltfMaterialSource",
    "GpuTimer",
    "HdrDisplayOutput",
    "HDR_DEFAULT_PAPER_WHITE_NITS",
    "HDR_DEFAULT_PEAK_NITS",
    "HEADER_LAYER_VERSION",
    "HeightFogPass",
    "ImageAccess",
    "LensFlarePass",
    "LENS_FLARE_GHOST_COUNT",
    "LightShaftPass",
    "LIGHT_SHAFT_STEP_COUNT",
    "LutInterpolation",
    "MemoryBarrier",
    "MINIMUM_FXAA_EDGE_THRESHOLD",
    "MINIMUM_GAMMA",
    "MotionBlurPass",
    "MOTION_BLUR_SAMPLE_COUNT",
    "Particle",
    "ParticleEmitterSettings",
    "ParticleSystem",
    "PARTICLE_STORAGE_BINDING",
    "PARTICLE_SYSTEM_DEFAULT_CAPACITY",
    "PassTiming",
    "PbrEffect",
    "PbrMaterial",
    "PbrMaterialExtensions",
    "PbrTextureSlot",
    "PBR_TEXTURE_SLOT_COUNT",
    "PointLight",
    "PostProcessChain",
    "PostProcessContext",
    "PostProcessPass",
    "PunctualLight",
    "PunctualLightKind",
    "RenderPipeline",
    "RenderPipelineSettings",
    "RenderQuality",
    "RenderTargetPool",
    "RenderTargetScope",
    "ShaderEffectFactory",
    "ShadowCascadeState",
    "ShadowMap",
    "ShadowQuality",
    "ShadowReceiver",
    "SHADOW_CASCADE_MAXIMUM",
    "SkinnedPbrEffect",
    "Skybox",
    "SpatialUpscalePass",
    "SpotLight",
    "SpotShadowMap",
    "SsaoPass",
    "SsrPass",
    "SSR_MAXIMUM_STEP_COUNT",
    "SSR_MINIMUM_STEP_COUNT",
    "StorageBuffer",
    "TextureTransform",
    "ToneMapPass",
    "TonemappingMode",
    "TransparencyMode",
    "TransparentDrawList",
    "VolumetricFogPass",
    "VOLUMETRIC_FOG_SLICE_COUNT",
    "VOLUMETRIC_FOG_SLICE_RESOLUTION",
    "WeightedBlendedTransparency",
]

#: The engine-layer revision the canonical header this binding was generated
#: against declares. Compare it with :func:`layer_version`, which reports what
#: the *loaded* library was built with; a disagreement means a header and a
#: library from different builds have been mixed. It is a revision marker, not
#: an ABI compatibility promise -- the ABI generation is the loader's business.
HEADER_LAYER_VERSION = 2


def layer_version() -> int:
    """The engine-layer revision the loaded CNA library was built with.

    Zero means the build has no engine layer. Needs a native library; it does
    not need a graphics device.
    """
    from _cna_native import engine_support as _support

    return _support.engine_layer_version()


def layer_version_string() -> str:
    """The engine layer's revision as CNA's own descriptive UTF-8 text.

    CNA answers a sentence, not a bare number -- ``"CNA engine layer 2"`` on the
    qualified artifact -- so this is a label to show a user, and
    :func:`layer_version` is the number to compare.
    """
    from _cna_native import engine_support as _support

    return _support.copied_text("cna_engine_layer_copy_version_string", (),
                                "engine layer version")


def is_available() -> bool:
    """Whether the loaded CNA build contains an engine layer.

    This is the question to ask before constructing anything here. It is
    measured from CNA, never inferred from the renderer's name or from a route
    existing.
    """
    return layer_version() != 0
