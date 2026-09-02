"""CNA's own compiled content format, `.cnb`, and its `.cnj` source documents.

This is a **CNA extension**, not part of XNA. ``.cnb`` is CNA's compiled content
container beside ``.xnb``; it has no XNA counterpart at all, which is exactly why
it lives here rather than in ``Microsoft.Xna.Framework.Content``.

**The strict XNA ``ContentManager`` is untouched by this package.** It is still
managed Python, still reads ``.xnb`` and only ``.xnb``, still keeps its own
cache, and never consults a ``.cnb`` file -- there is no "prefer ``.cnb``" rule
and no fallback. Importing ``Microsoft.Xna.Framework`` does not load this
package, which the extension gate asserts in a fresh interpreter rather than
assuming.

CNA's ``cnb.h`` implementation is the authority for the format. Nothing here
re-implements it: there is no second Python parser or encoder that could
disagree with CNA about what a byte means. What Python adds is a typed, safe
projection -- immutable value objects, explicit lifetimes, checked integer
widths, and errors that say which of CNA's categories applied.

What is here
------------

``format``
    The container's own vocabulary: asset types, chunk identifiers, read limits,
    CRC-32C, and the compression codecs.
``document``
    :class:`CnbDocument`, a parsed and fully validated container.
``primitives``
    :class:`CnbReader`, :class:`CnbByteWriter` and :class:`CnbWriter` -- what a
    game's own `.cnb` schema is built from.
``textures``, ``audio``, ``fonts``, ``media``, ``curves``, ``animation``, ``model``
    The typed asset codecs, one module per family. Each produces **asset data**,
    never a runtime GPU or audio object.
``importers``
    PNG, JPEG, DDS and WAV, through CNA's own decoders.
``compiler``
    `.cnj` source documents compiled to `.cnb`.
``loaders``
    Registering a Python loader for a game-defined asset type, and the minimal
    native content manager one needs in order to run.

Ownership
---------

Every object holding a CNA handle has an explicit ``close`` and works as a
context manager. Closing is deterministic and ordered by the caller: a
:class:`CnbDocument` refuses to close while a reader opened from it is still
open, because CNA refuses, and that refusal is reported rather than worked
around. Nothing relies on ``__del__``.

No raw handle, ctypes object or result code is public anywhere in this package.
"""

from __future__ import annotations

from . import (
    animation, audio, compiler, curves, document, errors, fonts, format,
    importers, loaders, media, model, primitives, textures,
)
from .animation import (
    ANIMATION_CLIP_SCHEMA_VERSION, AnimationClipChunk, ClipTargetSpace,
    CnbAnimationClip, CnbAnimationTrack, decode_animation_clip,
    encode_animation_clip,
)
from .audio import (
    MAX_AUDIO_SAMPLE_RATE, SOUND_EFFECT_SCHEMA_VERSION, AudioFormat,
    CnbSoundEffectData, CnbSoundEffectInfo, SoundEffectChunk, audio_format_name,
    audio_frame_bytes, decode_sound_effect, encode_sound_effect,
)
from .compiler import CnjCompilation, compile_cnj
from .curves import CURVE_SCHEMA_VERSION, CurveChunk, decode_curve, encode_curve
from .document import CnbChunk, CnbDocument, CnbExternalReference, CnbMetadata
from .errors import (
    CnbError,
    CnbFormatError,
    CnbInternalError,
    CnbLimitError,
    CnbMissingReferenceError,
    CnbUnsupportedError,
)
from .format import (
    CONTAINER_MAJOR,
    CONTAINER_MINOR,
    CRC32C_SEED,
    FORMAT_HEADER_SIZE,
    FORMAT_MAGIC_SIZE,
    FORMAT_TOC_ENTRY_SIZE,
    AssetType,
    ChunkFlags,
    CnbReadLimits,
    Compression,
    ContainerChunk,
    asset_type_id_from_name,
    asset_type_name,
    chunk_id,
    chunk_id_text,
    compress,
    compressed_size,
    compression_name,
    crc32c,
    decompress,
    format_magic,
    has_magic,
    is_compression_supported,
    is_custom_asset_type_id,
    is_well_formed_chunk_id,
    is_well_formed_utf8,
    logical_name_problem,
    uses_hardware_crc32c,
)
from .fonts import (
    MAX_SPRITE_FONT_GLYPHS, SPRITE_FONT_SCHEMA_VERSION, CnbGlyph,
    CnbSpriteFontData, CnbSpriteFontInfo, SpriteFontChunk, decode_sprite_font,
    encode_sprite_font,
)
from .importers import (
    decode_dds_as_texture_cube, decode_wav_as_sound_effect,
    import_dds_as_texture_cube, import_image_as_texture2d,
    import_wav_as_sound_effect,
)
from .loaders import (
    CnbLoader, LoaderRegistration, NativeContentManager, clear_loader_registry,
    find_loader, is_loader_registered, register_builtin_loaders, register_loader,
    registered_type_name, resolve_loader,
)
from .media import (
    MAX_VIDEO_DIMENSION, MEDIA_SCHEMA_VERSION, CnbSongData, CnbVideoData,
    MediaChunk, decode_song, decode_video, encode_song, encode_video,
)
from .model import (
    MODEL_SCHEMA_VERSION, NO_INDEX, TEXTURE_SLOT_COUNT, CnbBone, CnbMaterial,
    CnbMesh, CnbModelAnimation, CnbModelData, CnbModelFromCnj, CnbModelInfo,
    CnbModelLight, CnbMorphInfo, CnbMorphWeightKey, CnbPart, CnbSamplerState,
    CnbSkeleton, CnbTextureTransform, EffectKind, MaterialTextureSlot, ModelChunk,
    MorphDeltaStream, MorphKeyStream, SkeletonMatrixSet, build_model_from_cnj,
    decode_model, encode_model,
)
from .primitives import CnbByteWriter, CnbKeyframe, CnbReader, CnbWriter
from .textures import (
    CUBE_FACE_COUNT, MAX_TEXTURE_MIP_LEVELS, MAX_TEXTURE_REPRESENTATIONS,
    TEXTURE_SCHEMA_VERSION, CnbTextureData, CnbTextureInfo, TextureChunk,
    TextureFormat, decode_texture2d, decode_texture3d, decode_texture_cube,
    encode_texture2d, encode_texture3d, encode_texture_cube, is_block_compressed,
    is_known_texture_format, texture_format_from_surface_format, texture_format_name,
    texture_format_to_surface_format, texture_format_unit_bytes,
    texture_level_byte_size,
)

__all__ = [
    # modules
    "animation", "audio", "compiler", "curves", "document", "errors", "fonts",
    "format", "importers", "loaders", "media", "model", "primitives", "textures",
    # container vocabulary
    "AssetType", "ChunkFlags", "Compression", "ContainerChunk", "CnbReadLimits",
    "CONTAINER_MAJOR", "CONTAINER_MINOR", "CRC32C_SEED",
    "FORMAT_HEADER_SIZE", "FORMAT_MAGIC_SIZE", "FORMAT_TOC_ENTRY_SIZE",
    "asset_type_id_from_name", "asset_type_name", "chunk_id", "chunk_id_text",
    "compress", "compressed_size", "compression_name", "crc32c", "decompress",
    "format_magic", "has_magic", "is_compression_supported",
    "is_custom_asset_type_id", "is_well_formed_chunk_id", "is_well_formed_utf8",
    "logical_name_problem", "uses_hardware_crc32c",
    # documents
    "CnbChunk", "CnbDocument", "CnbExternalReference", "CnbMetadata",
    # primitives
    "CnbByteWriter", "CnbKeyframe", "CnbReader", "CnbWriter",
    # textures
    "CUBE_FACE_COUNT", "MAX_TEXTURE_MIP_LEVELS", "MAX_TEXTURE_REPRESENTATIONS",
    "TEXTURE_SCHEMA_VERSION", "CnbTextureData", "CnbTextureInfo", "TextureChunk",
    "TextureFormat", "decode_texture2d", "decode_texture3d", "decode_texture_cube",
    "encode_texture2d", "encode_texture3d", "encode_texture_cube",
    "is_block_compressed", "is_known_texture_format",
    "texture_format_from_surface_format", "texture_format_name",
    "texture_format_to_surface_format", "texture_format_unit_bytes",
    "texture_level_byte_size",
    # sound
    "MAX_AUDIO_SAMPLE_RATE", "SOUND_EFFECT_SCHEMA_VERSION", "AudioFormat",
    "CnbSoundEffectData", "CnbSoundEffectInfo", "SoundEffectChunk",
    "audio_format_name", "audio_frame_bytes", "decode_sound_effect",
    "encode_sound_effect",
    # sprite fonts
    "MAX_SPRITE_FONT_GLYPHS", "SPRITE_FONT_SCHEMA_VERSION", "CnbGlyph",
    "CnbSpriteFontData", "CnbSpriteFontInfo", "SpriteFontChunk",
    "decode_sprite_font", "encode_sprite_font",
    # media
    "MAX_VIDEO_DIMENSION", "MEDIA_SCHEMA_VERSION", "CnbSongData", "CnbVideoData",
    "MediaChunk", "decode_song", "decode_video", "encode_song", "encode_video",
    # curves
    "CURVE_SCHEMA_VERSION", "CurveChunk", "decode_curve", "encode_curve",
    # animation
    "ANIMATION_CLIP_SCHEMA_VERSION", "AnimationClipChunk", "ClipTargetSpace",
    "CnbAnimationClip", "CnbAnimationTrack", "decode_animation_clip",
    "encode_animation_clip",
    # models
    "MODEL_SCHEMA_VERSION", "NO_INDEX", "TEXTURE_SLOT_COUNT", "CnbBone",
    "CnbMaterial", "CnbMesh", "CnbModelAnimation", "CnbModelData",
    "CnbModelFromCnj", "CnbModelInfo", "CnbModelLight", "CnbMorphInfo",
    "CnbMorphWeightKey", "CnbPart", "CnbSamplerState", "CnbSkeleton",
    "CnbTextureTransform", "EffectKind", "MaterialTextureSlot", "ModelChunk",
    "MorphDeltaStream", "MorphKeyStream", "SkeletonMatrixSet",
    "build_model_from_cnj", "decode_model", "encode_model",
    # importers
    "decode_dds_as_texture_cube", "decode_wav_as_sound_effect",
    "import_dds_as_texture_cube", "import_image_as_texture2d",
    "import_wav_as_sound_effect",
    # .cnj compilation
    "CnjCompilation", "compile_cnj",
    # loaders
    "CnbLoader", "LoaderRegistration", "NativeContentManager",
    "clear_loader_registry", "find_loader", "is_loader_registered",
    "register_builtin_loaders", "register_loader", "registered_type_name",
    "resolve_loader",
    # errors
    "CnbError", "CnbFormatError", "CnbInternalError", "CnbLimitError",
    "CnbMissingReferenceError", "CnbUnsupportedError",
]
