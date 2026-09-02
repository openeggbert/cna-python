"""Reviewed ctypes layouts and frozen constants for CNA's ``cnb.h`` family.

Every structure here is measured against the canonical C declaration by
``tools/audit_cna_abi.py``: size, alignment and every used field offset.  Every
constant is likewise re-read from the header by the C probe rather than trusted
from prose, because a `.cnb` file's wire values outlive any single build.

Nothing in this module is public.  ``cna.extensions.content`` holds the public
projection; a ctypes object never crosses that boundary.
"""

from __future__ import annotations

import ctypes as c

from .abi import CNA_Quaternion, CNA_StringView, CNA_Vector3

# --- container constants ---------------------------------------------------

CNA_CNB_FORMAT_MAGIC_SIZE = 4
CNA_CNB_FORMAT_HEADER_SIZE = 64
CNA_CNB_FORMAT_TOC_ENTRY_SIZE = 48
CNA_CNB_FORMAT_HEADER_CHECKSUM_COVERAGE = 44
CNA_CNB_FORMAT_HEADER_CHECKSUM_OFFSET = 44
CNA_CNB_FORMAT_HEADER_RESERVED_SIZE = 16
CNA_CNB_FORMAT_CONTAINER_MAJOR = 1
CNA_CNB_FORMAT_CONTAINER_MINOR = 0
CNA_CNB_FORMAT_DEFAULT_TOC_OFFSET = 64

#: ``CMET`` -- the asset's canonical type name and its source content name.
CNA_CNB_CONTAINER_CHUNK_METADATA = 0x54454D43
#: ``XREF`` -- the optional external-reference table.
CNA_CNB_CONTAINER_CHUNK_EXTERNAL_REFERENCES = 0x46455258

CNA_CNB_CHUNK_FLAG_NONE = 0
CNA_CNB_CHUNK_FLAG_MANDATORY = 1
CNA_CNB_CHUNK_FLAG_ALL = CNA_CNB_CHUNK_FLAG_MANDATORY

CNA_CNB_CRC32C_SEED = 0

# --- structure versions ----------------------------------------------------

CNA_CNB_READ_LIMITS_STRUCT_VERSION = 1
CNA_CNB_CHUNK_ENTRY_STRUCT_VERSION = 1
CNA_CNB_EXTERNAL_REFERENCE_STRUCT_VERSION = 1
CNA_CNB_METADATA_STRUCT_VERSION = 1
CNA_CNB_TEXTURE_INFO_STRUCT_VERSION = 1
CNA_CNB_MODEL_INFO_STRUCT_VERSION = 1
CNA_CNB_MODEL_BONE_STRUCT_VERSION = 1
CNA_CNB_MODEL_PART_INFO_STRUCT_VERSION = 1
CNA_CNB_MATERIAL_INFO_STRUCT_VERSION = 1
CNA_CNB_MORPH_INFO_STRUCT_VERSION = 1
CNA_CNB_MESH_INFO_STRUCT_VERSION = 1
CNA_CNB_SKELETON_INFO_STRUCT_VERSION = 1
CNA_CNB_MORPH_WEIGHT_KEY_INFO_STRUCT_VERSION = 1
CNA_CNB_SPRITE_FONT_INFO_STRUCT_VERSION = 1
CNA_CNB_SOUND_EFFECT_INFO_STRUCT_VERSION = 1
CNA_CNB_VIDEO_INFO_STRUCT_VERSION = 1
CNA_CNB_IMAGE_IMPORT_OPTIONS_STRUCT_VERSION = 1

# --- compression codecs ----------------------------------------------------

CNA_CNB_COMPRESSION_NONE = 0
CNA_CNB_COMPRESSION_LZ4 = 1
CNA_CNB_COMPRESSION_ZSTD = 2
CNA_CNB_COMPRESSION_DEFLATE = 3
CNA_CNB_COMPRESSION_MAXIMUM = CNA_CNB_COMPRESSION_DEFLATE

# --- asset type identifiers ------------------------------------------------

CNA_CNB_ASSET_TYPE_INVALID = 0x00000000
CNA_CNB_ASSET_TYPE_TEXTURE2D = 0x00000001
CNA_CNB_ASSET_TYPE_TEXTURE3D = 0x00000002
CNA_CNB_ASSET_TYPE_TEXTURE_CUBE = 0x00000003
CNA_CNB_ASSET_TYPE_SPRITE_FONT = 0x00000004
CNA_CNB_ASSET_TYPE_MODEL = 0x00000005
CNA_CNB_ASSET_TYPE_ANIMATION_CLIP = 0x00000006
CNA_CNB_ASSET_TYPE_CURVE = 0x00000007
CNA_CNB_ASSET_TYPE_SOUND_EFFECT = 0x00000008
CNA_CNB_ASSET_TYPE_SONG = 0x00000009
CNA_CNB_ASSET_TYPE_VIDEO = 0x0000000A
CNA_CNB_ASSET_TYPE_EFFECT = 0x0000000B
CNA_CNB_ASSET_TYPE_RESERVED_RANGE_FIRST = 0x40000000
CNA_CNB_ASSET_TYPE_CUSTOM_RANGE_FIRST = 0x80000000

# --- texture formats and schema --------------------------------------------

CNA_CNB_TEXTURE_FORMAT_UNKNOWN = 0
CNA_CNB_TEXTURE_FORMAT_RGBA8 = 1
CNA_CNB_TEXTURE_FORMAT_BGRA8 = 2
CNA_CNB_TEXTURE_FORMAT_RGBA8_SRGB = 3
CNA_CNB_TEXTURE_FORMAT_BGR565 = 4
CNA_CNB_TEXTURE_FORMAT_BGRA5551 = 5
CNA_CNB_TEXTURE_FORMAT_BGRA4444 = 6
CNA_CNB_TEXTURE_FORMAT_ALPHA8 = 7
CNA_CNB_TEXTURE_FORMAT_R8 = 8
CNA_CNB_TEXTURE_FORMAT_R16 = 9
CNA_CNB_TEXTURE_FORMAT_RG16 = 10
CNA_CNB_TEXTURE_FORMAT_RGBA16 = 11
CNA_CNB_TEXTURE_FORMAT_RG8_SNORM = 12
CNA_CNB_TEXTURE_FORMAT_RGBA8_SNORM = 13
CNA_CNB_TEXTURE_FORMAT_RGB10_A2 = 14
CNA_CNB_TEXTURE_FORMAT_R32_FLOAT = 15
CNA_CNB_TEXTURE_FORMAT_RG32_FLOAT = 16
CNA_CNB_TEXTURE_FORMAT_RGBA32_FLOAT = 17
CNA_CNB_TEXTURE_FORMAT_R16_FLOAT = 18
CNA_CNB_TEXTURE_FORMAT_RG16_FLOAT = 19
CNA_CNB_TEXTURE_FORMAT_RGBA16_FLOAT = 20
CNA_CNB_TEXTURE_FORMAT_HDR_BLENDABLE = 21
CNA_CNB_TEXTURE_FORMAT_BC1 = 22
CNA_CNB_TEXTURE_FORMAT_BC2 = 23
CNA_CNB_TEXTURE_FORMAT_BC3 = 24
CNA_CNB_TEXTURE_FORMAT_BC3_SRGB = 25
CNA_CNB_TEXTURE_FORMAT_BC7 = 26
CNA_CNB_TEXTURE_FORMAT_BC7_SRGB = 27
CNA_CNB_TEXTURE_FORMAT_MAXIMUM = CNA_CNB_TEXTURE_FORMAT_BC7_SRGB

CNA_CNB_TEXTURE_CHUNK_HEADER = 0x48584554
CNA_CNB_TEXTURE_CHUNK_REPRESENTATIONS = 0x52584554
CNA_CNB_TEXTURE_CHUNK_PAYLOAD = 0x44584554
CNA_CNB_TEXTURE_SCHEMA_VERSION = 1
CNA_CNB_TEXTURE_HEADER_STRIDE = 24
CNA_CNB_TEXTURE_REPRESENTATION_STRIDE = 24
CNA_CNB_TEXTURE_CUBE_FACE_COUNT = 6
CNA_CNB_MAX_TEXTURE_MIP_LEVELS = 16
CNA_CNB_MAX_TEXTURE_REPRESENTATIONS = 8

#: CNA's own surface formats.  The first twenty are XNA 4.0's; the seven ``_EXT``
#: ones above them are CNA capability the strict projection deliberately does not
#: contain, which is why the extension has to name them itself.
CNA_SURFACE_FORMAT_COLOR = 0
CNA_SURFACE_FORMAT_BGR565 = 1
CNA_SURFACE_FORMAT_BGRA5551 = 2
CNA_SURFACE_FORMAT_BGRA4444 = 3
CNA_SURFACE_FORMAT_DXT1 = 4
CNA_SURFACE_FORMAT_DXT3 = 5
CNA_SURFACE_FORMAT_DXT5 = 6
CNA_SURFACE_FORMAT_NORMALIZED_BYTE2 = 7
CNA_SURFACE_FORMAT_NORMALIZED_BYTE4 = 8
CNA_SURFACE_FORMAT_RGBA1010102 = 9
CNA_SURFACE_FORMAT_RG32 = 10
CNA_SURFACE_FORMAT_RGBA64 = 11
CNA_SURFACE_FORMAT_ALPHA8 = 12
CNA_SURFACE_FORMAT_SINGLE = 13
CNA_SURFACE_FORMAT_VECTOR2 = 14
CNA_SURFACE_FORMAT_VECTOR4 = 15
CNA_SURFACE_FORMAT_HALF_SINGLE = 16
CNA_SURFACE_FORMAT_HALF_VECTOR2 = 17
CNA_SURFACE_FORMAT_HALF_VECTOR4 = 18
CNA_SURFACE_FORMAT_HDR_BLENDABLE = 19
CNA_SURFACE_FORMAT_COLOR_BGRA_EXT = 20
CNA_SURFACE_FORMAT_COLOR_SRGB_EXT = 21
CNA_SURFACE_FORMAT_DXT5_SRGB_EXT = 22
CNA_SURFACE_FORMAT_BC7_EXT = 23
CNA_SURFACE_FORMAT_BC7_SRGB_EXT = 24
CNA_SURFACE_FORMAT_BYTE_EXT = 25
CNA_SURFACE_FORMAT_USHORT_EXT = 26

# --- model schema ----------------------------------------------------------

CNA_CNB_EFFECT_KIND_BASIC = 0
CNA_CNB_EFFECT_KIND_SKINNED = 1
CNA_CNB_EFFECT_KIND_DUAL_TEXTURE = 2
CNA_CNB_EFFECT_KIND_PBR = 3
CNA_CNB_EFFECT_KIND_SKINNED_PBR = 4
CNA_CNB_EFFECT_KIND_EXTERNAL = 5
CNA_CNB_EFFECT_KIND_MAXIMUM = CNA_CNB_EFFECT_KIND_EXTERNAL

CNA_CNB_NO_INDEX = 0xFFFFFFFF
CNA_CNB_TEXTURE_SLOT_COUNT = 7

CNA_CNB_MATERIAL_TEXTURE_BASE_COLOR = 0
CNA_CNB_MATERIAL_TEXTURE_SECOND = 1
CNA_CNB_MATERIAL_TEXTURE_NORMAL = 2
CNA_CNB_MATERIAL_TEXTURE_METALLIC_ROUGHNESS = 3
CNA_CNB_MATERIAL_TEXTURE_EMISSIVE = 4
CNA_CNB_MATERIAL_TEXTURE_OCCLUSION = 5
CNA_CNB_MATERIAL_TEXTURE_SPECULAR = 6
CNA_CNB_MATERIAL_TEXTURE_SPECULAR_COLOR = 7
CNA_CNB_MATERIAL_TEXTURE_MAXIMUM = CNA_CNB_MATERIAL_TEXTURE_SPECULAR_COLOR

CNA_CNB_MORPH_DELTA_POSITION = 0
CNA_CNB_MORPH_DELTA_NORMAL = 1
CNA_CNB_MORPH_DELTA_TANGENT = 2
CNA_CNB_MORPH_DELTA_MAXIMUM = CNA_CNB_MORPH_DELTA_TANGENT

CNA_CNB_MORPH_KEY_WEIGHTS = 0
CNA_CNB_MORPH_KEY_IN_TANGENT = 1
CNA_CNB_MORPH_KEY_OUT_TANGENT = 2
CNA_CNB_MORPH_KEY_MAXIMUM = CNA_CNB_MORPH_KEY_OUT_TANGENT

CNA_CNB_SKELETON_MATRIX_BIND_POSE = 0
CNA_CNB_SKELETON_MATRIX_INVERSE_BIND_POSE = 1
CNA_CNB_SKELETON_MATRIX_ROOT_PREFIX = 2
CNA_CNB_SKELETON_MATRIX_MAXIMUM = CNA_CNB_SKELETON_MATRIX_ROOT_PREFIX

CNA_CNB_MODEL_CHUNK_HEADER = 0x484C444D
CNA_CNB_MODEL_CHUNK_STRINGS = 0x5254534D
CNA_CNB_MODEL_CHUNK_BONES = 0x4E4F424D
CNA_CNB_MODEL_CHUNK_MESHES = 0x48534D4D
CNA_CNB_MODEL_CHUNK_MATERIALS = 0x54414D4D
CNA_CNB_MODEL_CHUNK_VERTEX_DATA = 0x5854564D
CNA_CNB_MODEL_CHUNK_INDEX_DATA = 0x5844494D
CNA_CNB_MODEL_CHUNK_MORPH_DATA = 0x50524D4D
CNA_CNB_MODEL_CHUNK_SKELETON = 0x4C4B534D
CNA_CNB_MODEL_CHUNK_ANIMATIONS = 0x4D4E414D
CNA_CNB_MODEL_CHUNK_LIGHTS = 0x54494C4D

CNA_CNB_MODEL_SCHEMA_VERSION = 1
CNA_CNB_MODEL_BONE_STRIDE = 72
CNA_CNB_MODEL_MESH_STRIDE = 16
CNA_CNB_MODEL_PART_STRIDE = 56
CNA_CNB_MODEL_MATERIAL_STRIDE = 368

# --- audio, font, media, curve and clip schema -----------------------------

CNA_CNB_AUDIO_FORMAT_UNKNOWN = 0
CNA_CNB_AUDIO_FORMAT_PCM16 = 1
CNA_CNB_AUDIO_FORMAT_PCM8 = 2
CNA_CNB_AUDIO_FORMAT_PCM_FLOAT32 = 3
CNA_CNB_AUDIO_FORMAT_ADPCM = 4
CNA_CNB_AUDIO_FORMAT_VORBIS = 5
CNA_CNB_AUDIO_FORMAT_MAXIMUM = CNA_CNB_AUDIO_FORMAT_VORBIS

CNA_CNB_SPRITE_FONT_CHUNK_HEADER = 0x544E4F46
CNA_CNB_SPRITE_FONT_CHUNK_GLYPH_BOUNDS = 0x50594C47
CNA_CNB_SPRITE_FONT_CHUNK_CROPPING = 0x504F5243
CNA_CNB_SPRITE_FONT_CHUNK_KERNING = 0x4E52454B
CNA_CNB_SPRITE_FONT_CHUNK_CHARACTERS = 0x52414843
CNA_CNB_SPRITE_FONT_SCHEMA_VERSION = 1
CNA_CNB_SPRITE_FONT_HEADER_STRIDE = 24
CNA_CNB_SPRITE_FONT_RECTANGLE_STRIDE = 16
CNA_CNB_SPRITE_FONT_KERNING_STRIDE = 12
CNA_CNB_SPRITE_FONT_CHARACTER_STRIDE = 4
CNA_CNB_MAX_SPRITE_FONT_GLYPHS = 65536

CNA_CNB_SOUND_EFFECT_CHUNK_HEADER = 0x48445541
CNA_CNB_SOUND_EFFECT_CHUNK_DATA = 0x44445541
CNA_CNB_SOUND_EFFECT_SCHEMA_VERSION = 1
CNA_CNB_SOUND_EFFECT_HEADER_STRIDE = 28
CNA_CNB_MAX_AUDIO_SAMPLE_RATE = 384000

CNA_CNB_MEDIA_CHUNK_SONG_HEADER = 0x48474E53
CNA_CNB_MEDIA_CHUNK_VIDEO_HEADER = 0x48444956
CNA_CNB_MEDIA_SCHEMA_VERSION = 1
CNA_CNB_SONG_HEADER_FIXED_STRIDE = 8
CNA_CNB_VIDEO_HEADER_STRIDE = 24
CNA_CNB_MAX_VIDEO_DIMENSION = 65536

CNA_CNB_CURVE_CHUNK_HEADER = 0x48565243
CNA_CNB_CURVE_CHUNK_KEYS = 0x4B565243
CNA_CNB_CURVE_SCHEMA_VERSION = 1
CNA_CNB_CURVE_KEY_STRIDE = 20

CNA_CNB_ANIMATION_CLIP_CHUNK_HEADER = 0x484C4341
CNA_CNB_ANIMATION_CLIP_CHUNK_TRACKS = 0x544C4341
CNA_CNB_ANIMATION_CLIP_CHUNK_KEYS = 0x4B4C4341
CNA_CNB_ANIMATION_CLIP_SCHEMA_VERSION = 1
CNA_CNB_ANIMATION_TRACK_STRIDE = 12
CNA_CNB_ANIMATION_KEY_STRIDE = 48

CNA_CLIP_TARGET_SPACE_JOINT_PALETTE_EXT = 0
CNA_CLIP_TARGET_SPACE_SCENE_NODE_EXT = 1
CNA_CLIP_TARGET_SPACE_MAXIMUM_EXT = CNA_CLIP_TARGET_SPACE_SCENE_NODE_EXT


# --- structures ------------------------------------------------------------


class CNA_CnbReadLimits(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("max_file_size", c.c_uint64), ("max_chunk_size", c.c_uint64),
        ("max_total_uncompressed_size", c.c_uint64),
        ("max_chunk_count", c.c_uint32), ("max_string_bytes", c.c_uint32),
        ("max_array_element_count", c.c_uint32), ("max_chunk_alignment", c.c_uint32),
    ]


class CNA_CnbChunkEntry(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("offset", c.c_uint64), ("stored_size", c.c_uint64),
        ("uncompressed_size", c.c_uint64),
        ("type", c.c_uint32), ("flags", c.c_uint32), ("checksum", c.c_uint32),
        ("compression", c.c_uint32), ("alignment", c.c_uint32), ("reserved", c.c_uint32),
    ]


class CNA_CnbExternalReference(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("flags", c.c_uint32), ("expected_asset_type_id", c.c_uint32),
    ]


class CNA_CnbMetadata(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("present", c.c_uint8), ("reserved", c.c_uint8 * 3), ("flags", c.c_uint32),
    ]


class CNA_CnbTextureInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("width", c.c_uint32), ("height", c.c_uint32), ("depth", c.c_uint32),
        ("face_count", c.c_uint32), ("mip_count", c.c_uint32),
        ("representation_count", c.c_uint32),
    ]


class CNA_CnbTextureTransform(c.Structure):
    _fields_ = [
        ("offset_x", c.c_float), ("offset_y", c.c_float),
        ("scale_x", c.c_float), ("scale_y", c.c_float), ("rotation", c.c_float),
    ]


class CNA_CnbSamplerState(c.Structure):
    _fields_ = [
        ("filter", c.c_uint32), ("address_u", c.c_uint32), ("address_v", c.c_uint32),
        ("declared", c.c_uint8), ("reserved", c.c_uint8 * 3),
    ]


class CNA_CnbModelLight(c.Structure):
    _fields_ = [("direction", c.c_float * 3), ("diffuse_color", c.c_float * 3)]


class CNA_CnbModelInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("bone_count", c.c_uint64), ("part_count", c.c_uint64),
        ("mesh_count", c.c_uint64), ("animation_count", c.c_uint64),
        ("light_count", c.c_uint64),
        ("has_skeleton", c.c_uint8), ("applies_gltf_lighting_policy", c.c_uint8),
        ("has_bone_hierarchy", c.c_uint8), ("reserved", c.c_uint8),
    ]


class CNA_CnbModelBone(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("parent", c.c_int32), ("reserved", c.c_uint32),
        ("transform", c.c_float * 16),
    ]


class CNA_CnbModelPartInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("vertex_stride", c.c_uint32), ("vertex_count", c.c_uint32),
        ("index_count", c.c_uint32), ("index_element_size", c.c_uint32),
        ("primitive_topology", c.c_uint32), ("primitive_count", c.c_uint32),
        ("effect_kind", c.c_uint32),
        ("vertex_color_enabled", c.c_uint8), ("unlit", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
    ]


class CNA_CnbMaterialInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("base_color_factor", c.c_float * 4), ("emissive_factor", c.c_float * 3),
        ("specular_color_factor", c.c_float * 3),
        ("metallic_factor", c.c_float), ("roughness_factor", c.c_float),
        ("ior", c.c_float), ("specular_factor", c.c_float),
        ("normal_scale", c.c_float), ("occlusion_strength", c.c_float),
        ("alpha_cutoff", c.c_float), ("alpha_mode", c.c_uint32),
        ("double_sided", c.c_uint8), ("reserved", c.c_uint8 * 3),
    ]


class CNA_CnbMorphInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("vertex_count", c.c_uint32), ("reserved", c.c_uint32),
        ("target_count", c.c_uint64), ("weight_count", c.c_uint64),
        ("weight_track_key_count", c.c_uint64),
        ("recompute_flat_normals", c.c_uint8),
        ("weight_track_step_interpolation", c.c_uint8),
        ("weight_track_cubic_spline", c.c_uint8), ("reserved2", c.c_uint8 * 5),
    ]


class CNA_CnbMeshInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("parent_bone", c.c_int32), ("reserved", c.c_uint32),
        ("part_index_count", c.c_uint64),
    ]


class CNA_CnbSkeletonInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("joint_count", c.c_uint64),
        ("has_root_prefix", c.c_uint8), ("reserved", c.c_uint8 * 7),
    ]


class CNA_CnbMorphWeightKeyInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("time_seconds", c.c_double), ("weight_count", c.c_uint64),
        ("in_tangent_count", c.c_uint64), ("out_tangent_count", c.c_uint64),
    ]


class CNA_CnbSpriteFontInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("glyph_count", c.c_uint64), ("line_spacing", c.c_int32),
        ("spacing", c.c_float), ("default_character", c.c_uint16),
        ("has_default_character", c.c_uint8), ("reserved", c.c_uint8 * 5),
    ]


class CNA_CnbSoundEffectInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("format", c.c_uint32), ("sample_rate", c.c_uint32),
        ("channels", c.c_uint32), ("frame_count", c.c_uint32),
        ("loop_start", c.c_uint32), ("loop_length", c.c_uint32),
    ]


class CNA_CnbVideoInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("duration_milliseconds", c.c_uint32), ("width", c.c_uint32),
        ("height", c.c_uint32), ("frames_per_second", c.c_float),
        ("soundtrack_type", c.c_uint32), ("reserved", c.c_uint32),
    ]


class CNA_CnbImageImportOptions(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("color_key", c.c_uint8 * 3), ("has_color_key", c.c_uint8),
    ]


class CNA_KeyframeEXT(c.Structure):
    """One fixed-layout bone animation keyframe, from ``models.h``."""

    _fields_ = [
        ("time_seconds", c.c_double), ("translation", CNA_Vector3),
        ("rotation", CNA_Quaternion), ("scale", CNA_Vector3),
    ]


class CNA_BoneTrackEXTDescriptor(c.Structure):
    """One borrowed keyframe array driving one skeleton bone, from ``models.h``."""

    _fields_ = [
        ("bone_index", c.c_int32), ("reserved", c.c_uint32),
        ("keyframes", c.POINTER(CNA_KeyframeEXT)), ("keyframe_count", c.c_uint64),
    ]


class CNA_AnimationClipEXTDescriptor(c.Structure):
    """A borrowed bone-track array and clip duration, from ``models.h``."""

    _fields_ = [
        ("duration_seconds", c.c_double),
        ("tracks", c.POINTER(CNA_BoneTrackEXTDescriptor)), ("track_count", c.c_uint64),
    ]


class CNA_CurveKey(c.Structure):
    """One fixed-layout XNA curve key, from ``curve.h``.

    Needed because the `.cnb` curve codec speaks in native ``Curve`` handles;
    see :mod:`cna.extensions.content.codecs`.
    """

    _fields_ = [
        ("position", c.c_float), ("value", c.c_float),
        ("tangent_in", c.c_float), ("tangent_out", c.c_float),
        ("continuity", c.c_uint32),
    ]


#: ``content.h`` declares no named constant for this structure's version, so
#: the value is the ABI's own v1.  The layout itself is measured.
CNA_CONTENT_MANAGER_CREATE_INFO_STRUCT_VERSION = 1


class CNA_ContentManagerCreateInfo(c.Structure):
    """Creation configuration for the native content manager, from ``content.h``.

    Imported only because ``cna_cnb_loader_invoke`` requires a manager; see
    ``NATIVE_CONTENT_MANAGER_FUNCTION_MANIFEST``.
    """

    _fields_ = [
        ("struct_size", c.c_uint32), ("struct_version", c.c_uint32),
        ("root_directory", CNA_StringView), ("reserved", c.c_uint64),
    ]


#: Predicate a caller supplies to say which texture formats it can upload.
#: Called synchronously, once per representation, and never retained.
CNA_CnbTextureFormatSupportedFn = c.CFUNCTYPE(c.c_uint8, c.c_uint32, c.c_void_p)

#: Turns one validated ``.cnb`` container into a caller-owned object.  The
#: document and content-manager handles are callback-scoped borrows.
CNA_CnbLoaderCallback = c.CFUNCTYPE(
    c.c_uint32, c.c_void_p, c.c_uint64, c.c_uint64, CNA_StringView, c.POINTER(c.c_void_p)
)
