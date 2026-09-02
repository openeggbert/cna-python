"""Generated ctypes layouts and constants for CNA's ``engine_layer.h``.

Do not edit. ``tools/generate_engine_abi.py`` derives this from the canonical
header, and ``--check`` fails when the checked-in copy is not what the current
header produces. Every size, alignment, field offset and constant here is
re-measured against the C compiler by ``tools/audit_cna_abi.py``.

Nothing in this module is public. ``cna.extensions.engine`` holds the public
projection; a ctypes object never crosses that boundary.
"""

from __future__ import annotations

import ctypes as c

from . import abi

# --- scalar identities -----------------------------------------------------

#: Fixed-width identities the engine layer declares as typedefs of a scalar.
#: They are enums in spirit and integers in the ABI; the public projection
#: turns them into Python enums, and this is only their width.
CNA_AlphaModeEXT = c.c_uint32
CNA_AreaLightShapeEXT = c.c_uint32
CNA_ClusteredLightType = c.c_uint32
CNA_DepthEncoding = c.c_uint32
CNA_DisplayColorSpace = c.c_uint32
CNA_GraphicsImageAccess = c.c_uint32
CNA_GraphicsMemoryBarrier = c.c_uint32
CNA_LodSelectionMode = c.c_uint32
CNA_LutInterpolation = c.c_uint32
CNA_PunctualLightKindEXT = c.c_uint32
CNA_RenderQuality = c.c_uint32
CNA_ShadowQuality = c.c_uint32
CNA_TextureAddressMode = c.c_uint32
CNA_TextureFilter = c.c_uint32
CNA_TonemappingMode = c.c_uint32
CNA_TransparencyMode = c.c_uint32
CNA_VertexElementFormat = c.c_uint32
CNA_VertexElementUsage = c.c_uint32

#: Every opaque engine handle is a ``CNA_Handle``. The names are kept so a
#: manifest entry can say which object a handle parameter refers to.
ENGINE_HANDLE_TYPES = (
    "CNA_AreaLightBrdfTableHandle",
    "CNA_AtmosphericSkyHandle",
    "CNA_AutoExposureHandle",
    "CNA_CascadedShadowMapHandle",
    "CNA_ClusteredForwardEffectHandle",
    "CNA_ClusteredLightAssignmentHandle",
    "CNA_ClusteredLightBufferHandle",
    "CNA_ClusteredLightComputeHandle",
    "CNA_ClusteredLightGridHandle",
    "CNA_ClusteredLightSetHandle",
    "CNA_ClusteredShadowPolicyHandle",
    "CNA_ComputeShaderHandle",
    "CNA_CubeLutHandle",
    "CNA_CubeShadowMapHandle",
    "CNA_DebugDrawHandle",
    "CNA_DecalPassHandle",
    "CNA_DepthNormalPrepassHandle",
    "CNA_EnvironmentProcessorHandle",
    "CNA_FrustumCullerEXTHandle",
    "CNA_FullscreenPassHandle",
    "CNA_GpuInstanceCullerHandle",
    "CNA_GpuTimerHandle",
    "CNA_HdrDisplayOutputHandle",
    "CNA_InstancedRendererEXTHandle",
    "CNA_LightProbeBakerHandle",
    "CNA_LightProbeHandle",
    "CNA_LightProbeVolumeHandle",
    "CNA_LodGroupEXTHandle",
    "CNA_ParticleSystemHandle",
    "CNA_PbrMaterialExtensionsHandle",
    "CNA_PostProcessChainHandle",
    "CNA_PostProcessPassHandle",
    "CNA_RenderPipelineHandle",
    "CNA_RenderTargetPoolHandle",
    "CNA_ScopedRenderTargetHandle",
    "CNA_ShaderEffectFactoryHandle",
    "CNA_ShadowMapHandle",
    "CNA_SkyboxHandle",
    "CNA_SpatialUpscalePassHandle",
    "CNA_SpotShadowMapHandle",
    "CNA_StorageBufferHandle",
    "CNA_TransparentDrawListHandle",
    "CNA_WeightedBlendedTransparencyHandle",
)

# --- constants -------------------------------------------------------------

CNA_ALPHA_MODE_BLEND_EXT = 2
CNA_ALPHA_MODE_MASK_EXT = 1
CNA_ALPHA_MODE_MAXIMUM_EXT = 2
CNA_ALPHA_MODE_OPAQUE_EXT = 0
CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT = 64
CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE = 32
CNA_AREA_LIGHT_QUAD_CORNER_COUNT = 4
CNA_AREA_LIGHT_SHAPE_DISC_EXT = 1
CNA_AREA_LIGHT_SHAPE_RECTANGLE_EXT = 0
CNA_AREA_LIGHT_SHAPE_TUBE_EXT = 2
CNA_CLUSTERED_ASSIGNMENT_MAX_LIGHTS_EXT = 1024
CNA_CLUSTERED_COMPUTE_DEFAULT_STRIDE_EXT = 64
CNA_CLUSTERED_FORWARD_MAX_LIGHTS_PER_FRAGMENT_EXT = 128
CNA_CLUSTERED_LIGHT_SET_MAX_EXT = 256
CNA_CLUSTERED_LIGHT_TYPE_POINT = 0
CNA_CLUSTERED_LIGHT_TYPE_SPOT = 1
CNA_CLUSTERED_SHADOW_DEFAULT_BUDGET_EXT = 4
CNA_CLUSTERED_SHADOW_DEFAULT_HYSTERESIS_EXT = 1.25
CNA_CLUSTER_GRID_DEFAULT_SLICE_COUNT_EXT = 24
CNA_CLUSTER_GRID_DEFAULT_TILES_X_EXT = 16
CNA_CLUSTER_GRID_DEFAULT_TILES_Y_EXT = 8
CNA_CLUSTER_GRID_MAX_SLICE_COUNT_EXT = 256
CNA_CLUSTER_GRID_MAX_TILES_PER_AXIS_EXT = 128
CNA_COLOR_GRADE_MAX_LUT_SIZE_EXT = 64
CNA_CUBE_LUT_MAX_SIZE_EXT = 64
CNA_CUBE_LUT_MIN_SIZE_EXT = 2
CNA_CUBE_SHADOW_FACE_COUNT_EXT = 6
CNA_DEBUG_DRAW_MAX_SEGMENTS = 128
CNA_DEBUG_DRAW_MIN_SEGMENTS = 4
CNA_DEPTH_ENCODING_AUTOMATIC = 0
CNA_DEPTH_ENCODING_HALF_FLOAT = 2
CNA_DEPTH_ENCODING_PACKED = 1
CNA_DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES_EXT = 24.0
CNA_DISPLAY_COLOR_SPACE_HDR10 = 2
CNA_DISPLAY_COLOR_SPACE_SCRGB = 1
CNA_DISPLAY_COLOR_SPACE_SRGB = 0
CNA_ENGINE_LAYER_VERSION = 2
CNA_FRUSTUM_CORNER_COUNT_EXT = 8
CNA_GPU_INSTANCE_BINDING = 6
CNA_GRAPHICS_IMAGE_ACCESS_READ_ONLY = 0
CNA_GRAPHICS_IMAGE_ACCESS_READ_WRITE = 2
CNA_GRAPHICS_IMAGE_ACCESS_WRITE_ONLY = 1
CNA_GRAPHICS_MEMORY_BARRIER_ALL = 511
CNA_GRAPHICS_MEMORY_BARRIER_BUFFER_UPDATE = 64
CNA_GRAPHICS_MEMORY_BARRIER_ELEMENT_ARRAY = 2
CNA_GRAPHICS_MEMORY_BARRIER_FRAMEBUFFER = 128
CNA_GRAPHICS_MEMORY_BARRIER_INDIRECT_COMMAND = 256
CNA_GRAPHICS_MEMORY_BARRIER_NONE = 0
CNA_GRAPHICS_MEMORY_BARRIER_SHADER_IMAGE_ACCESS = 16
CNA_GRAPHICS_MEMORY_BARRIER_SHADER_STORAGE = 32
CNA_GRAPHICS_MEMORY_BARRIER_TEXTURE_FETCH = 8
CNA_GRAPHICS_MEMORY_BARRIER_UNIFORM = 4
CNA_GRAPHICS_MEMORY_BARRIER_VERTEX_ATTRIB_ARRAY = 1
CNA_HDR_DISPLAY_DEFAULT_PAPER_WHITE_NITS_EXT = 200.0
CNA_HDR_DISPLAY_DEFAULT_PEAK_NITS_EXT = 1000.0
CNA_LENS_FLARE_GHOST_COUNT_EXT = 4
CNA_LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE = 32
CNA_LIGHT_PROBE_BAKER_FACE_COUNT = 6
CNA_LIGHT_PROBE_COEFFICIENT_COUNT_EXT = 9
CNA_LIGHT_PROBE_VISIBILITY_DIRECTIONS_EXT = 6
CNA_LIGHT_PROBE_VOLUME_MAX_PROBES_EXT = 32768
CNA_LIGHT_SHAFT_STEP_COUNT_EXT = 24
CNA_LOD_SELECTION_MODE_DISTANCE = 0
CNA_LOD_SELECTION_MODE_SCREEN_SPACE_ERROR = 1
CNA_LUT_INTERPOLATION_TETRAHEDRAL = 1
CNA_LUT_INTERPOLATION_TRILINEAR = 0
CNA_MOTION_BLUR_SAMPLE_COUNT_EXT = 8
CNA_PARTICLE_BINDING = 7
CNA_PARTICLE_SYSTEM_DEFAULT_CAPACITY = 1024
CNA_PBR_TEXTURE_BASE_COLOR = 0
CNA_PBR_TEXTURE_EMISSIVE = 3
CNA_PBR_TEXTURE_MAXIMUM = 6
CNA_PBR_TEXTURE_METALLIC_ROUGHNESS = 2
CNA_PBR_TEXTURE_NORMAL = 1
CNA_PBR_TEXTURE_OCCLUSION = 4
CNA_PBR_TEXTURE_SLOT_COUNT = 7
CNA_PBR_TEXTURE_SPECULAR_COLOR_EXT = 6
CNA_PBR_TEXTURE_SPECULAR_EXT = 5
CNA_POST_PROCESS_CONTEXT_VERSION_2 = 2
CNA_PUNCTUAL_LIGHT_KIND_EXT_NONE = 0
CNA_PUNCTUAL_LIGHT_KIND_EXT_POINT = 1
CNA_PUNCTUAL_LIGHT_KIND_EXT_SPOT = 2
CNA_RENDER_PIPELINE_MINIMUM_FXAA_EDGE_THRESHOLD_EXT = 0.001
CNA_RENDER_PIPELINE_MINIMUM_GAMMA_EXT = 0.01
CNA_RENDER_QUALITY_HIGH = 2
CNA_RENDER_QUALITY_LOW = 0
CNA_RENDER_QUALITY_MEDIUM = 1
CNA_RENDER_QUALITY_ULTRA = 3
CNA_SHADOW_CASCADE_MAX_EXT = 4
CNA_SHADOW_QUALITY_DISABLED = 0
CNA_SHADOW_QUALITY_HIGH = 3
CNA_SHADOW_QUALITY_LOW = 1
CNA_SHADOW_QUALITY_MEDIUM = 2
CNA_SHADOW_QUALITY_ULTRA = 4
CNA_SSR_PASS_MAX_STEP_COUNT_EXT = 64
CNA_SSR_PASS_MIN_STEP_COUNT_EXT = 4
CNA_TEXTURE_FILTER_ANISOTROPIC = 2
CNA_TEXTURE_FILTER_LINEAR = 0
CNA_TEXTURE_FILTER_LINEAR_MIP_POINT = 3
CNA_TEXTURE_FILTER_MIN_LINEAR_MAG_POINT_MIP_LINEAR = 5
CNA_TEXTURE_FILTER_MIN_LINEAR_MAG_POINT_MIP_POINT = 6
CNA_TEXTURE_FILTER_MIN_POINT_MAG_LINEAR_MIP_LINEAR = 7
CNA_TEXTURE_FILTER_MIN_POINT_MAG_LINEAR_MIP_POINT = 8
CNA_TEXTURE_FILTER_POINT = 1
CNA_TEXTURE_FILTER_POINT_MIP_LINEAR = 4
CNA_TONEMAPPING_MODE_ACES = 3
CNA_TONEMAPPING_MODE_FILMIC = 2
CNA_TONEMAPPING_MODE_NONE = 0
CNA_TONEMAPPING_MODE_REINHARD = 1
CNA_TONEMAPPING_MODE_UNCHARTED2 = 4
CNA_TRANSPARENCY_MODE_NONE = 0
CNA_TRANSPARENCY_MODE_ORDER_INDEPENDENT = 2
CNA_TRANSPARENCY_MODE_SORTED = 1
CNA_VERTEX_ELEMENT_FORMAT_BYTE4 = 5
CNA_VERTEX_ELEMENT_FORMAT_COLOR = 4
CNA_VERTEX_ELEMENT_FORMAT_HALF_VECTOR2 = 10
CNA_VERTEX_ELEMENT_FORMAT_HALF_VECTOR4 = 11
CNA_VERTEX_ELEMENT_FORMAT_NORMALIZED_SHORT2 = 8
CNA_VERTEX_ELEMENT_FORMAT_NORMALIZED_SHORT4 = 9
CNA_VERTEX_ELEMENT_FORMAT_SHORT2 = 6
CNA_VERTEX_ELEMENT_FORMAT_SHORT4 = 7
CNA_VERTEX_ELEMENT_FORMAT_SINGLE = 0
CNA_VERTEX_ELEMENT_FORMAT_VECTOR2 = 1
CNA_VERTEX_ELEMENT_FORMAT_VECTOR3 = 2
CNA_VERTEX_ELEMENT_FORMAT_VECTOR4 = 3
CNA_VERTEX_ELEMENT_USAGE_BINORMAL = 4
CNA_VERTEX_ELEMENT_USAGE_BLEND_INDICES = 6
CNA_VERTEX_ELEMENT_USAGE_BLEND_WEIGHT = 7
CNA_VERTEX_ELEMENT_USAGE_COLOR = 1
CNA_VERTEX_ELEMENT_USAGE_DEPTH = 8
CNA_VERTEX_ELEMENT_USAGE_FOG = 9
CNA_VERTEX_ELEMENT_USAGE_NORMAL = 3
CNA_VERTEX_ELEMENT_USAGE_POINT_SIZE = 10
CNA_VERTEX_ELEMENT_USAGE_POSITION = 0
CNA_VERTEX_ELEMENT_USAGE_SAMPLE = 11
CNA_VERTEX_ELEMENT_USAGE_TANGENT = 5
CNA_VERTEX_ELEMENT_USAGE_TESSELLATE_FACTOR = 12
CNA_VERTEX_ELEMENT_USAGE_TEXTURE_COORDINATE = 2
CNA_VOLUMETRIC_FOG_SLICE_COUNT_EXT = 32
CNA_VOLUMETRIC_FOG_SLICE_RESOLUTION_EXT = 96

# --- structures ------------------------------------------------------------

class CNA_TextureTransformEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("offset", abi.CNA_Vector2),
        ("scale", abi.CNA_Vector2),
        ("rotation", c.c_float),
    ]


class CNA_PostProcessContext(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("source", c.c_uint64),
        ("source_depth", c.c_uint64),
        ("source_normals", c.c_uint64),
        ("source_velocity", c.c_uint64),
        ("destination", c.c_uint64),
        ("width", c.c_int32),
        ("height", c.c_int32),
        ("elapsed_seconds", c.c_float),
        ("near_plane", c.c_float),
        ("far_plane", c.c_float),
        ("has_previous_frame", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("projection", abi.CNA_Matrix),
        ("inverse_projection", abi.CNA_Matrix),
        ("inverse_view", abi.CNA_Matrix),
        ("previous_view_projection", abi.CNA_Matrix),
        ("settings", c.c_void_p),
    ]


class CNA_DirectionalLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("direction", abi.CNA_Vector3),
        ("color", abi.CNA_Vector3),
        ("intensity", c.c_float),
        ("casts_shadows", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]


class CNA_PointLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("position", abi.CNA_Vector3),
        ("color", abi.CNA_Vector3),
        ("intensity", c.c_float),
        ("range", c.c_float),
        ("casts_shadows", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]


class CNA_SpotLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("position", abi.CNA_Vector3),
        ("direction", abi.CNA_Vector3),
        ("color", abi.CNA_Vector3),
        ("intensity", c.c_float),
        ("range", c.c_float),
        ("inner_angle", c.c_float),
        ("outer_angle", c.c_float),
        ("casts_shadows", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]


class CNA_PunctualLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("kind", c.c_uint32),
        ("reserved", c.c_uint32),
        ("position", abi.CNA_Vector3),
        ("direction", abi.CNA_Vector3),
        ("diffuse_color", abi.CNA_Vector3),
        ("range", c.c_float),
        ("inner_angle", c.c_float),
        ("outer_angle", c.c_float),
        ("shadow_depth_bias", c.c_float),
        ("shadow_cube", c.c_uint64),
        ("shadow_map", c.c_uint64),
        ("shadow_view_projection", abi.CNA_Matrix),
    ]


class CNA_ShadowCascadeStateEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("count", c.c_int32),
        ("blend_band", c.c_float),
        ("world_to_atlas", abi.CNA_Matrix * 4),
        ("split_distance", c.c_float * 4),
        ("camera_view", abi.CNA_Matrix),
        ("debug_tint", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]


class CNA_ClusteredLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("type", c.c_uint32),
        ("casts_shadows", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("position", abi.CNA_Vector3),
        ("direction", abi.CNA_Vector3),
        ("color", abi.CNA_Vector3),
        ("intensity", c.c_float),
        ("range", c.c_float),
        ("inner_angle", c.c_float),
        ("outer_angle", c.c_float),
    ]


class CNA_GltfMaterialTexturesEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("slots", c.c_uint64 * 7),
    ]


class CNA_GltfMaterialExtensionTexturesEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("clearcoat", c.c_uint64),
        ("clearcoat_roughness", c.c_uint64),
        ("clearcoat_normal", c.c_uint64),
        ("sheen_color", c.c_uint64),
        ("sheen_roughness", c.c_uint64),
        ("transmission", c.c_uint64),
        ("thickness", c.c_uint64),
        ("iridescence", c.c_uint64),
        ("iridescence_thickness", c.c_uint64),
    ]


class CNA_GltfMaterialSourceEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("base_color_factor", abi.CNA_Vector4),
        ("metallic_factor", c.c_float),
        ("roughness_factor", c.c_float),
        ("emissive_factor", abi.CNA_Vector3),
        ("normal_scale", c.c_float),
        ("occlusion_strength", c.c_float),
        ("ior_ext", c.c_float),
        ("specular_factor_ext", c.c_float),
        ("specular_color_factor_ext", abi.CNA_Vector3),
        ("alpha_mode", c.c_uint32),
        ("alpha_cutoff", c.c_float),
        ("double_sided", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("texture_coordinate_sets_ext", c.c_int32 * 7),
        ("texture_transforms_ext", CNA_TextureTransformEXT * 7),
    ]


class CNA_GltfMaterialExtensionSourceEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("clearcoat_factor_ext", c.c_float),
        ("clearcoat_roughness_factor_ext", c.c_float),
        ("sheen_color_factor_ext", abi.CNA_Vector3),
        ("sheen_roughness_factor_ext", c.c_float),
        ("transmission_factor_ext", c.c_float),
        ("thickness_factor_ext", c.c_float),
        ("attenuation_distance_ext", c.c_float),
        ("attenuation_color_ext", abi.CNA_Vector3),
        ("iridescence_factor_ext", c.c_float),
        ("iridescence_ior_ext", c.c_float),
        ("iridescence_thickness_minimum_ext", c.c_float),
        ("iridescence_thickness_maximum_ext", c.c_float),
    ]


class CNA_RenderPipelineSettingsEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("hdr_enabled", c.c_uint8),
        ("exposure", c.c_float),
        ("gamma", c.c_float),
        ("tonemapping_mode", c.c_uint32),
        ("bloom_enabled", c.c_uint8),
        ("bloom_intensity", c.c_float),
        ("bloom_threshold", c.c_float),
        ("bloom_iterations", c.c_int32),
        ("ssao_enabled", c.c_uint8),
        ("transparency_mode", c.c_uint32),
        ("ssao_radius", c.c_float),
        ("ssao_intensity", c.c_float),
        ("ssao_sample_count", c.c_int32),
        ("ssr_enabled", c.c_uint8),
        ("ssr_max_distance", c.c_float),
        ("ssr_step_count", c.c_int32),
        ("ssr_thickness", c.c_float),
        ("ssr_depth_bias", c.c_float),
        ("ssr_edge_fade", c.c_float),
        ("volumetric_fog_density", c.c_float),
        ("light_shaft_threshold", c.c_float),
        ("light_shaft_intensity", c.c_float),
        ("light_shaft_decay", c.c_float),
        ("height_fog_density", c.c_float),
        ("height_fog_falloff", c.c_float),
        ("height_fog_base_height", c.c_float),
        ("motion_blur_strength", c.c_float),
        ("motion_blur_max_distance", c.c_float),
        ("chromatic_aberration_strength", c.c_float),
        ("film_grain_intensity", c.c_float),
        ("lens_flare_threshold", c.c_float),
        ("lens_flare_intensity", c.c_float),
        ("lens_flare_dispersal", c.c_float),
        ("color_grade_enabled", c.c_uint8),
        ("color_grade_strength", c.c_float),
        ("dof_enabled", c.c_uint8),
        ("dof_focus_distance", c.c_float),
        ("dof_focal_length", c.c_float),
        ("doff_number", c.c_float),
        ("dof_max_radius", c.c_float),
        ("ssr_roughness_blur", c.c_float),
        ("ssr_intensity", c.c_float),
        ("fxaa_enabled", c.c_uint8),
        ("fxaa_edge_threshold_ext", c.c_float),
        ("render_quality", c.c_uint32),
        ("shadow_quality", c.c_uint32),
        ("shadows_enabled", c.c_uint8),
        ("reserved", c.c_uint8 * 4),
    ]


class CNA_RenderPipelineFrameStatisticsEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("passes_run", c.c_int32),
        ("target_switches", c.c_int32),
        ("used_scene_target", c.c_uint8),
        ("drew_skybox", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
        ("gpu_memory_estimate_bytes", c.c_uint64),
    ]


class CNA_PassTimingEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("sample_count", c.c_int32),
        ("reserved", c.c_uint8 * 4),
        ("milliseconds", c.c_double),
    ]


class CNA_ImageBasedLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("irradiance", c.c_uint64),
        ("prefiltered_specular", c.c_uint64),
        ("brdf_lut", c.c_uint64),
        ("prefiltered_mip_count", c.c_int32),
        ("intensity", c.c_float),
    ]


class CNA_AreaLightEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("shape", c.c_uint32),
        ("two_sided", c.c_uint8),
        ("reserved0", c.c_uint8 * 3),
        ("position", abi.CNA_Vector3),
        ("right_axis", abi.CNA_Vector3),
        ("up_axis", abi.CNA_Vector3),
        ("color", abi.CNA_Vector3),
        ("intensity", c.c_float),
        ("range", c.c_float),
    ]


class CNA_AreaLightBrdfTerms(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("magnitude", c.c_float),
        ("fresnel", c.c_float),
        ("average_tangent", c.c_float),
        ("average_normal", c.c_float),
    ]


class CNA_ParticleEmitterSettings(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("position", abi.CNA_Vector3),
        ("direction", abi.CNA_Vector3),
        ("gravity", abi.CNA_Vector3),
        ("start_color", abi.CNA_Vector4),
        ("end_color", abi.CNA_Vector4),
        ("cone_angle", c.c_float),
        ("speed", c.c_float),
        ("speed_variance", c.c_float),
        ("lifetime", c.c_float),
        ("lifetime_variance", c.c_float),
        ("drag", c.c_float),
        ("emission_rate", c.c_float),
        ("start_size", c.c_float),
        ("end_size", c.c_float),
    ]


class CNA_Particle(c.Structure):
    _fields_ = [
        ("position", abi.CNA_Vector4),
        ("velocity", abi.CNA_Vector4),
        ("state", abi.CNA_Vector4),
    ]


class CNA_LodLevelEXT(c.Structure):
    _fields_ = [
        ("part", c.c_uint64),
        ("max_distance", c.c_float),
        ("reserved0", c.c_uint32),
    ]


class CNA_IndirectDrawArguments(c.Structure):
    _fields_ = [
        ("vertex_count", c.c_uint32),
        ("instance_count", c.c_uint32),
        ("first_vertex", c.c_uint32),
        ("base_instance", c.c_uint32),
    ]


class CNA_IndirectDrawIndexedArguments(c.Structure):
    _fields_ = [
        ("index_count", c.c_uint32),
        ("instance_count", c.c_uint32),
        ("first_index", c.c_uint32),
        ("base_vertex", c.c_int32),
        ("base_instance", c.c_uint32),
    ]


class CNA_BoundingBox(c.Structure):
    _fields_ = [
        ("min", abi.CNA_Vector3),
        ("max", abi.CNA_Vector3),
    ]


class CNA_GpuCullableInstance(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("world", abi.CNA_Matrix),
        ("bounds", CNA_BoundingBox),
    ]


class CNA_SamplerState(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("address_u", c.c_uint32),
        ("address_v", c.c_uint32),
        ("address_w", c.c_uint32),
        ("filter", c.c_uint32),
        ("max_anisotropy", c.c_int32),
        ("max_mip_level", c.c_int32),
        ("mip_map_level_of_detail_bias", c.c_float),
        ("reserved", c.c_uint32),
    ]


class CNA_PbrMaterialEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("albedo_texture", c.c_uint64),
        ("normal_texture", c.c_uint64),
        ("metallic_roughness_texture", c.c_uint64),
        ("ambient_occlusion_texture", c.c_uint64),
        ("emissive_texture", c.c_uint64),
        ("specular_texture", c.c_uint64),
        ("specular_color_texture", c.c_uint64),
        ("albedo_color", abi.CNA_Color),
        ("emissive_factor", abi.CNA_Vector3),
        ("specular_color_factor", abi.CNA_Vector3),
        ("metallic_factor", c.c_float),
        ("roughness_factor", c.c_float),
        ("normal_scale", c.c_float),
        ("occlusion_strength", c.c_float),
        ("ior", c.c_float),
        ("specular_factor", c.c_float),
        ("alpha_cutoff", c.c_float),
        ("alpha_mode", c.c_uint32),
        ("double_sided", c.c_uint8),
        ("base_color_texture_srgb", c.c_uint8),
        ("emissive_texture_srgb", c.c_uint8),
        ("specular_color_texture_srgb", c.c_uint8),
        ("output_encoded_to_srgb", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("texture_coordinate_sets", c.c_int32 * 7),
        ("texture_transforms", CNA_TextureTransformEXT * 7),
    ]


class CNA_BoundingSphere(c.Structure):
    _fields_ = [
        ("center", abi.CNA_Vector3),
        ("radius", c.c_float),
    ]


class CNA_VertexElement(c.Structure):
    _fields_ = [
        ("offset", c.c_int32),
        ("format", c.c_uint32),
        ("usage", c.c_uint32),
        ("usage_index", c.c_int32),
    ]


class CNA_BoundingFrustum(c.Structure):
    _fields_ = [
        ("matrix", abi.CNA_Matrix),
    ]


class CNA_VertexPositionColor(c.Structure):
    _fields_ = [
        ("position", abi.CNA_Vector3),
        ("color", abi.CNA_Color),
    ]


# --- constants derived from a generated layout ------------------------------

CNA_POST_PROCESS_CONTEXT_SIZE_V1 = CNA_PostProcessContext.settings.offset

#: Every generated structure, in declaration order, for the ABI audit.
ENGINE_STRUCTURES = (
    CNA_TextureTransformEXT,
    CNA_PostProcessContext,
    CNA_DirectionalLightEXT,
    CNA_PointLightEXT,
    CNA_SpotLightEXT,
    CNA_PunctualLightEXT,
    CNA_ShadowCascadeStateEXT,
    CNA_ClusteredLightEXT,
    CNA_GltfMaterialTexturesEXT,
    CNA_GltfMaterialExtensionTexturesEXT,
    CNA_GltfMaterialSourceEXT,
    CNA_GltfMaterialExtensionSourceEXT,
    CNA_RenderPipelineSettingsEXT,
    CNA_RenderPipelineFrameStatisticsEXT,
    CNA_PassTimingEXT,
    CNA_ImageBasedLightEXT,
    CNA_AreaLightEXT,
    CNA_AreaLightBrdfTerms,
    CNA_ParticleEmitterSettings,
    CNA_Particle,
    CNA_LodLevelEXT,
    CNA_IndirectDrawArguments,
    CNA_IndirectDrawIndexedArguments,
    CNA_BoundingBox,
    CNA_GpuCullableInstance,
    CNA_SamplerState,
    CNA_PbrMaterialEXT,
    CNA_BoundingSphere,
    CNA_VertexElement,
    CNA_BoundingFrustum,
    CNA_VertexPositionColor,
)

#: Every generated constant, for the ABI audit to re-read from C.
ENGINE_CONSTANTS = (
    "CNA_ALPHA_MODE_BLEND_EXT",
    "CNA_ALPHA_MODE_MASK_EXT",
    "CNA_ALPHA_MODE_MAXIMUM_EXT",
    "CNA_ALPHA_MODE_OPAQUE_EXT",
    "CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT",
    "CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE",
    "CNA_AREA_LIGHT_QUAD_CORNER_COUNT",
    "CNA_AREA_LIGHT_SHAPE_DISC_EXT",
    "CNA_AREA_LIGHT_SHAPE_RECTANGLE_EXT",
    "CNA_AREA_LIGHT_SHAPE_TUBE_EXT",
    "CNA_CLUSTERED_ASSIGNMENT_MAX_LIGHTS_EXT",
    "CNA_CLUSTERED_COMPUTE_DEFAULT_STRIDE_EXT",
    "CNA_CLUSTERED_FORWARD_MAX_LIGHTS_PER_FRAGMENT_EXT",
    "CNA_CLUSTERED_LIGHT_SET_MAX_EXT",
    "CNA_CLUSTERED_LIGHT_TYPE_POINT",
    "CNA_CLUSTERED_LIGHT_TYPE_SPOT",
    "CNA_CLUSTERED_SHADOW_DEFAULT_BUDGET_EXT",
    "CNA_CLUSTERED_SHADOW_DEFAULT_HYSTERESIS_EXT",
    "CNA_CLUSTER_GRID_DEFAULT_SLICE_COUNT_EXT",
    "CNA_CLUSTER_GRID_DEFAULT_TILES_X_EXT",
    "CNA_CLUSTER_GRID_DEFAULT_TILES_Y_EXT",
    "CNA_CLUSTER_GRID_MAX_SLICE_COUNT_EXT",
    "CNA_CLUSTER_GRID_MAX_TILES_PER_AXIS_EXT",
    "CNA_COLOR_GRADE_MAX_LUT_SIZE_EXT",
    "CNA_CUBE_LUT_MAX_SIZE_EXT",
    "CNA_CUBE_LUT_MIN_SIZE_EXT",
    "CNA_CUBE_SHADOW_FACE_COUNT_EXT",
    "CNA_DEBUG_DRAW_MAX_SEGMENTS",
    "CNA_DEBUG_DRAW_MIN_SEGMENTS",
    "CNA_DEPTH_ENCODING_AUTOMATIC",
    "CNA_DEPTH_ENCODING_HALF_FLOAT",
    "CNA_DEPTH_ENCODING_PACKED",
    "CNA_DEPTH_OF_FIELD_SENSOR_HEIGHT_MILLIMETRES_EXT",
    "CNA_DISPLAY_COLOR_SPACE_HDR10",
    "CNA_DISPLAY_COLOR_SPACE_SCRGB",
    "CNA_DISPLAY_COLOR_SPACE_SRGB",
    "CNA_ENGINE_LAYER_VERSION",
    "CNA_FRUSTUM_CORNER_COUNT_EXT",
    "CNA_GPU_INSTANCE_BINDING",
    "CNA_GRAPHICS_IMAGE_ACCESS_READ_ONLY",
    "CNA_GRAPHICS_IMAGE_ACCESS_READ_WRITE",
    "CNA_GRAPHICS_IMAGE_ACCESS_WRITE_ONLY",
    "CNA_GRAPHICS_MEMORY_BARRIER_ALL",
    "CNA_GRAPHICS_MEMORY_BARRIER_BUFFER_UPDATE",
    "CNA_GRAPHICS_MEMORY_BARRIER_ELEMENT_ARRAY",
    "CNA_GRAPHICS_MEMORY_BARRIER_FRAMEBUFFER",
    "CNA_GRAPHICS_MEMORY_BARRIER_INDIRECT_COMMAND",
    "CNA_GRAPHICS_MEMORY_BARRIER_NONE",
    "CNA_GRAPHICS_MEMORY_BARRIER_SHADER_IMAGE_ACCESS",
    "CNA_GRAPHICS_MEMORY_BARRIER_SHADER_STORAGE",
    "CNA_GRAPHICS_MEMORY_BARRIER_TEXTURE_FETCH",
    "CNA_GRAPHICS_MEMORY_BARRIER_UNIFORM",
    "CNA_GRAPHICS_MEMORY_BARRIER_VERTEX_ATTRIB_ARRAY",
    "CNA_HDR_DISPLAY_DEFAULT_PAPER_WHITE_NITS_EXT",
    "CNA_HDR_DISPLAY_DEFAULT_PEAK_NITS_EXT",
    "CNA_LENS_FLARE_GHOST_COUNT_EXT",
    "CNA_LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE",
    "CNA_LIGHT_PROBE_BAKER_FACE_COUNT",
    "CNA_LIGHT_PROBE_COEFFICIENT_COUNT_EXT",
    "CNA_LIGHT_PROBE_VISIBILITY_DIRECTIONS_EXT",
    "CNA_LIGHT_PROBE_VOLUME_MAX_PROBES_EXT",
    "CNA_LIGHT_SHAFT_STEP_COUNT_EXT",
    "CNA_LOD_SELECTION_MODE_DISTANCE",
    "CNA_LOD_SELECTION_MODE_SCREEN_SPACE_ERROR",
    "CNA_LUT_INTERPOLATION_TETRAHEDRAL",
    "CNA_LUT_INTERPOLATION_TRILINEAR",
    "CNA_MOTION_BLUR_SAMPLE_COUNT_EXT",
    "CNA_PARTICLE_BINDING",
    "CNA_PARTICLE_SYSTEM_DEFAULT_CAPACITY",
    "CNA_PBR_TEXTURE_BASE_COLOR",
    "CNA_PBR_TEXTURE_EMISSIVE",
    "CNA_PBR_TEXTURE_MAXIMUM",
    "CNA_PBR_TEXTURE_METALLIC_ROUGHNESS",
    "CNA_PBR_TEXTURE_NORMAL",
    "CNA_PBR_TEXTURE_OCCLUSION",
    "CNA_PBR_TEXTURE_SLOT_COUNT",
    "CNA_PBR_TEXTURE_SPECULAR_COLOR_EXT",
    "CNA_PBR_TEXTURE_SPECULAR_EXT",
    "CNA_POST_PROCESS_CONTEXT_SIZE_V1",
    "CNA_POST_PROCESS_CONTEXT_VERSION_2",
    "CNA_PUNCTUAL_LIGHT_KIND_EXT_NONE",
    "CNA_PUNCTUAL_LIGHT_KIND_EXT_POINT",
    "CNA_PUNCTUAL_LIGHT_KIND_EXT_SPOT",
    "CNA_RENDER_PIPELINE_MINIMUM_FXAA_EDGE_THRESHOLD_EXT",
    "CNA_RENDER_PIPELINE_MINIMUM_GAMMA_EXT",
    "CNA_RENDER_QUALITY_HIGH",
    "CNA_RENDER_QUALITY_LOW",
    "CNA_RENDER_QUALITY_MEDIUM",
    "CNA_RENDER_QUALITY_ULTRA",
    "CNA_SHADOW_CASCADE_MAX_EXT",
    "CNA_SHADOW_QUALITY_DISABLED",
    "CNA_SHADOW_QUALITY_HIGH",
    "CNA_SHADOW_QUALITY_LOW",
    "CNA_SHADOW_QUALITY_MEDIUM",
    "CNA_SHADOW_QUALITY_ULTRA",
    "CNA_SSR_PASS_MAX_STEP_COUNT_EXT",
    "CNA_SSR_PASS_MIN_STEP_COUNT_EXT",
    "CNA_TEXTURE_FILTER_ANISOTROPIC",
    "CNA_TEXTURE_FILTER_LINEAR",
    "CNA_TEXTURE_FILTER_LINEAR_MIP_POINT",
    "CNA_TEXTURE_FILTER_MIN_LINEAR_MAG_POINT_MIP_LINEAR",
    "CNA_TEXTURE_FILTER_MIN_LINEAR_MAG_POINT_MIP_POINT",
    "CNA_TEXTURE_FILTER_MIN_POINT_MAG_LINEAR_MIP_LINEAR",
    "CNA_TEXTURE_FILTER_MIN_POINT_MAG_LINEAR_MIP_POINT",
    "CNA_TEXTURE_FILTER_POINT",
    "CNA_TEXTURE_FILTER_POINT_MIP_LINEAR",
    "CNA_TONEMAPPING_MODE_ACES",
    "CNA_TONEMAPPING_MODE_FILMIC",
    "CNA_TONEMAPPING_MODE_NONE",
    "CNA_TONEMAPPING_MODE_REINHARD",
    "CNA_TONEMAPPING_MODE_UNCHARTED2",
    "CNA_TRANSPARENCY_MODE_NONE",
    "CNA_TRANSPARENCY_MODE_ORDER_INDEPENDENT",
    "CNA_TRANSPARENCY_MODE_SORTED",
    "CNA_VERTEX_ELEMENT_FORMAT_BYTE4",
    "CNA_VERTEX_ELEMENT_FORMAT_COLOR",
    "CNA_VERTEX_ELEMENT_FORMAT_HALF_VECTOR2",
    "CNA_VERTEX_ELEMENT_FORMAT_HALF_VECTOR4",
    "CNA_VERTEX_ELEMENT_FORMAT_NORMALIZED_SHORT2",
    "CNA_VERTEX_ELEMENT_FORMAT_NORMALIZED_SHORT4",
    "CNA_VERTEX_ELEMENT_FORMAT_SHORT2",
    "CNA_VERTEX_ELEMENT_FORMAT_SHORT4",
    "CNA_VERTEX_ELEMENT_FORMAT_SINGLE",
    "CNA_VERTEX_ELEMENT_FORMAT_VECTOR2",
    "CNA_VERTEX_ELEMENT_FORMAT_VECTOR3",
    "CNA_VERTEX_ELEMENT_FORMAT_VECTOR4",
    "CNA_VERTEX_ELEMENT_USAGE_BINORMAL",
    "CNA_VERTEX_ELEMENT_USAGE_BLEND_INDICES",
    "CNA_VERTEX_ELEMENT_USAGE_BLEND_WEIGHT",
    "CNA_VERTEX_ELEMENT_USAGE_COLOR",
    "CNA_VERTEX_ELEMENT_USAGE_DEPTH",
    "CNA_VERTEX_ELEMENT_USAGE_FOG",
    "CNA_VERTEX_ELEMENT_USAGE_NORMAL",
    "CNA_VERTEX_ELEMENT_USAGE_POINT_SIZE",
    "CNA_VERTEX_ELEMENT_USAGE_POSITION",
    "CNA_VERTEX_ELEMENT_USAGE_SAMPLE",
    "CNA_VERTEX_ELEMENT_USAGE_TANGENT",
    "CNA_VERTEX_ELEMENT_USAGE_TESSELLATE_FACTOR",
    "CNA_VERTEX_ELEMENT_USAGE_TEXTURE_COORDINATE",
    "CNA_VOLUMETRIC_FOG_SLICE_COUNT_EXT",
    "CNA_VOLUMETRIC_FOG_SLICE_RESOLUTION_EXT",
)
