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
    compute, errors, passes, pbr, pipeline, postprocess, scene, shadows,
    values,
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
    "compute",
    "errors",
    "passes",
    "pbr",
    "pipeline",
    "postprocess",
    "scene",
    "shadows",
    "values",
    "layer_version",
    "layer_version_string",
    "is_available",
    "HEADER_LAYER_VERSION",
    "ComputeShader",
    "GpuTimer",
    "ImageAccess",
    "MemoryBarrier",
    "StorageBuffer",
    "barrier_contains",
    "BlitPass",
    "EffectPass",
    "FullscreenPass",
    "PassTiming",
    "PostProcessChain",
    "PostProcessContext",
    "PostProcessPass",
    "RenderTargetPool",
    "RenderTargetScope",
    "ShaderEffectFactory",
    "bind_render_target",
    "AlphaMode",
    "GltfMaterialExtensionSource",
    "GltfMaterialSource",
    "PBR_TEXTURE_SLOT_COUNT",
    "PbrEffect",
    "PbrMaterial",
    "PbrMaterialExtensions",
    "PbrTextureSlot",
    "SkinnedPbrEffect",
    "TextureTransform",
    "TransparencyMode",
    "build_extensions",
    "build_material",
    "thin_film_iridescence",
    "thin_film_iridescence_glsl",
    "AsciiEffect",
    "AsciiPass",
    "AsciiQuantizeMode",
    "AutoExposure",
    "BloomPass",
    "COLOR_GRADE_MAXIMUM_LUT_SIZE",
    "CUBE_LUT_MAXIMUM_SIZE",
    "CUBE_LUT_MINIMUM_SIZE",
    "ChromaticAberrationPass",
    "ColorGradePass",
    "CubeLut",
    "DisplayColorSpace",
    "FilmGrainPass",
    "FxaaPass",
    "HDR_DEFAULT_PAPER_WHITE_NITS",
    "HDR_DEFAULT_PEAK_NITS",
    "HdrDisplayOutput",
    "LENS_FLARE_GHOST_COUNT",
    "LensFlarePass",
    "LutInterpolation",
    "MOTION_BLUR_SAMPLE_COUNT",
    "SpatialUpscalePass",
    "ToneMapPass",
    "bloom_extract_channel",
    "bloom_iterations_for",
    "create_identity_lut",
    "decode_pq",
    "encode_for_display",
    "encode_pq",
    "fxaa_edge_threshold_for",
    "fxaa_fragment_glsl",
    "is_identity_scale",
    "lut_size_for_strip",
    "rec709_to_rec2020",
    "roll_off",
    "tonemap_channel",
    "FrameStatistics",
    "MINIMUM_FXAA_EDGE_THRESHOLD",
    "MINIMUM_GAMMA",
    "RenderPipeline",
    "RenderPipelineSettings",
    "TonemappingMode",
    "DecalPass",
    "DepthEncoding",
    "DepthNormalPrepass",
    "PARTICLE_STORAGE_BINDING",
    "PARTICLE_SYSTEM_DEFAULT_CAPACITY",
    "Particle",
    "ParticleEmitterSettings",
    "ParticleSystem",
    "TransparentDrawList",
    "WeightedBlendedTransparency",
    "camera_position_of",
    "decode_velocity",
    "depth_decode_glsl",
    "has_velocity",
    "is_inside_decal_box",
    "pack_depth",
    "particle_lookup_glsl",
    "particle_random",
    "sort_key",
    "transparency_accumulation_glsl",
    "transparency_weight",
    "unpack_depth",
    "uses_packed_depth",
    "velocity_decode_glsl",
    "CascadedShadowMap",
    "CubeShadowMap",
    "ShadowMap",
    "ShadowReceiver",
    "SpotShadowMap",
    "compute_light_projection",
    "compute_light_view",
    "cube_shadow_map_size_for",
    "shadow_filter_radius_for",
    "shadow_map_size_for",
    "supports_shadow_sampling",
    "DirectionalLight",
    "PointLight",
    "PunctualLight",
    "PunctualLightKind",
    "RenderQuality",
    "ShadowCascadeState",
    "ShadowQuality",
    "SpotLight",
    "CUBE_SHADOW_FACE_COUNT",
    "FRUSTUM_CORNER_COUNT",
    "SHADOW_CASCADE_MAXIMUM",
    "ComputeShaderCompileError",
    "EngineArgumentError",
    "EngineDisposedError",
    "EngineError",
    "EngineInternalError",
    "EngineStateError",
    "EngineThreadError",
    "EngineUnavailableError",
    "EngineUnsupportedError",
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
