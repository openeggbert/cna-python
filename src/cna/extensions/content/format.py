"""The `.cnb` container's own vocabulary: identities, limits, checksums, codecs.

Everything here is independent of any asset schema -- what a byte at a given
offset means, how a chunk is identified, how a checksum is computed, and what a
reader refuses before it allocates anything. It is the layer a custom schema
builds on and the layer a tool inspects a file with.

Every value CNA freezes into the wire format is read from CNA rather than
restated here, and the ABI audit proves each one still matches the header.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Iterable

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

__all__ = [
    "AssetType",
    "ChunkFlags",
    "Compression",
    "ContainerChunk",
    "CnbReadLimits",
    "FORMAT_HEADER_SIZE",
    "FORMAT_MAGIC_SIZE",
    "FORMAT_TOC_ENTRY_SIZE",
    "CONTAINER_MAJOR",
    "CONTAINER_MINOR",
    "CRC32C_SEED",
    "asset_type_id_from_name",
    "asset_type_name",
    "chunk_id",
    "chunk_id_text",
    "compress",
    "compressed_size",
    "compression_name",
    "crc32c",
    "decompress",
    "format_magic",
    "has_magic",
    "is_compression_supported",
    "is_custom_asset_type_id",
    "is_well_formed_chunk_id",
    "is_well_formed_utf8",
    "logical_name_problem",
    "uses_hardware_crc32c",
]

#: Bytes of magic at offset 0 of a `.cnb` file.
FORMAT_MAGIC_SIZE = _abi.CNA_CNB_FORMAT_MAGIC_SIZE
#: Bytes the fixed container header occupies.
FORMAT_HEADER_SIZE = _abi.CNA_CNB_FORMAT_HEADER_SIZE
#: Bytes one table-of-contents entry occupies.
FORMAT_TOC_ENTRY_SIZE = _abi.CNA_CNB_FORMAT_TOC_ENTRY_SIZE
#: Container major version this CNA generation reads and writes.
CONTAINER_MAJOR = _abi.CNA_CNB_FORMAT_CONTAINER_MAJOR
#: Container minor version this CNA generation writes.
CONTAINER_MINOR = _abi.CNA_CNB_FORMAT_CONTAINER_MINOR
#: Starting register for a running CRC-32C.
CRC32C_SEED = _abi.CNA_CNB_CRC32C_SEED


class AssetType(IntEnum):
    """An asset type identifier as a `.cnb` header declares it.

    The numeric values are wire format and frozen. ``Effect`` is reserved with
    no schema by design: CNA has many renderers, so a file carrying one API's
    shader bytecode would be useless on the others.
    """

    Invalid = _abi.CNA_CNB_ASSET_TYPE_INVALID
    Texture2D = _abi.CNA_CNB_ASSET_TYPE_TEXTURE2D
    Texture3D = _abi.CNA_CNB_ASSET_TYPE_TEXTURE3D
    TextureCube = _abi.CNA_CNB_ASSET_TYPE_TEXTURE_CUBE
    SpriteFont = _abi.CNA_CNB_ASSET_TYPE_SPRITE_FONT
    Model = _abi.CNA_CNB_ASSET_TYPE_MODEL
    AnimationClip = _abi.CNA_CNB_ASSET_TYPE_ANIMATION_CLIP
    Curve = _abi.CNA_CNB_ASSET_TYPE_CURVE
    SoundEffect = _abi.CNA_CNB_ASSET_TYPE_SOUND_EFFECT
    Song = _abi.CNA_CNB_ASSET_TYPE_SONG
    Video = _abi.CNA_CNB_ASSET_TYPE_VIDEO
    Effect = _abi.CNA_CNB_ASSET_TYPE_EFFECT

    #: Lowest identifier reserved for future CNA use.
    ReservedRangeFirst = _abi.CNA_CNB_ASSET_TYPE_RESERVED_RANGE_FIRST
    #: Lowest identifier available to game-defined asset types.
    CustomRangeFirst = _abi.CNA_CNB_ASSET_TYPE_CUSTOM_RANGE_FIRST


class Compression(IntEnum):
    """A per-chunk compression codec identity.

    The numeric values are wire format: codec 2 is Zstandard in every `.cnb`
    ever written, whether or not a given build implements it. Whether this build
    can use one is a separate runtime question --
    :func:`is_compression_supported` answers it.
    """

    NoCompression = _abi.CNA_CNB_COMPRESSION_NONE
    Lz4 = _abi.CNA_CNB_COMPRESSION_LZ4
    Zstd = _abi.CNA_CNB_COMPRESSION_ZSTD
    Deflate = _abi.CNA_CNB_COMPRESSION_DEFLATE


class ChunkFlags(IntEnum):
    """Per-chunk flags the container defines.

    ``Mandatory`` means a reader that does not understand the chunk's
    identifier must refuse the whole file rather than skip it.
    """

    NoFlags = _abi.CNA_CNB_CHUNK_FLAG_NONE
    Mandatory = _abi.CNA_CNB_CHUNK_FLAG_MANDATORY


class ContainerChunk(IntEnum):
    """The two chunk identifiers the container itself owns.

    A schema may not add either as an ordinary chunk: the writer emits each at
    most once, and a second copy would break a singleton the reader requires.
    """

    Metadata = _abi.CNA_CNB_CONTAINER_CHUNK_METADATA
    ExternalReferences = _abi.CNA_CNB_CONTAINER_CHUNK_EXTERNAL_REFERENCES


@dataclass(frozen=True)
class CnbReadLimits:
    """Sanity bounds every count-driven `.cnb` read is checked against.

    A correctly bounds-checked reader can still be told by one corrupt count to
    allocate an enormous buffer before further validation rejects the file.
    These bounds make that a fast, named refusal instead. They are generous
    relative to any real asset rather than tuned to a fixture.

    Build one with :meth:`defaults` and narrow it with :meth:`replace`; the
    values come from CNA, so a caller never has to restate them.
    """

    max_file_size: int
    max_chunk_size: int
    max_total_uncompressed_size: int
    max_chunk_count: int
    max_string_bytes: int
    max_array_element_count: int
    max_chunk_alignment: int

    @classmethod
    def defaults(cls) -> "CnbReadLimits":
        """The process-wide default limits, read from CNA."""
        value = _support.out_struct(
            _abi.CNA_CnbReadLimits, _abi.CNA_CNB_READ_LIMITS_STRUCT_VERSION,
            "cna_cnb_read_limits_init")
        return cls._from_native(value)

    def replace(self, **changes: int) -> "CnbReadLimits":
        """A copy with the named bounds changed and every other one kept."""
        return replace(self, **changes)

    @classmethod
    def _from_native(cls, value: _abi.CNA_CnbReadLimits) -> "CnbReadLimits":
        return cls(
            max_file_size=int(value.max_file_size),
            max_chunk_size=int(value.max_chunk_size),
            max_total_uncompressed_size=int(value.max_total_uncompressed_size),
            max_chunk_count=int(value.max_chunk_count),
            max_string_bytes=int(value.max_string_bytes),
            max_array_element_count=int(value.max_array_element_count),
            max_chunk_alignment=int(value.max_chunk_alignment),
        )

    def _to_native(self) -> _abi.CNA_CnbReadLimits:
        value = _abi.CNA_CnbReadLimits()
        value.struct_size = c.sizeof(_abi.CNA_CnbReadLimits)
        value.struct_version = _abi.CNA_CNB_READ_LIMITS_STRUCT_VERSION
        value.max_file_size = _support.checked(
            self.max_file_size, "uint64", "max_file_size")
        value.max_chunk_size = _support.checked(
            self.max_chunk_size, "uint64", "max_chunk_size")
        value.max_total_uncompressed_size = _support.checked(
            self.max_total_uncompressed_size, "uint64", "max_total_uncompressed_size")
        value.max_chunk_count = _support.checked(
            self.max_chunk_count, "uint32", "max_chunk_count")
        value.max_string_bytes = _support.checked(
            self.max_string_bytes, "uint32", "max_string_bytes")
        value.max_array_element_count = _support.checked(
            self.max_array_element_count, "uint32", "max_array_element_count")
        value.max_chunk_alignment = _support.checked(
            self.max_chunk_alignment, "uint32", "max_chunk_alignment")
        return value


def _limits_pointer(limits: "CnbReadLimits | None"):
    """Returns ``(pointer, keepalive)``; a null pointer means CNA's defaults."""
    if limits is None:
        return None, None
    native = limits._to_native()
    return c.byref(native), native


def format_magic() -> bytes:
    """The four magic bytes every `.cnb` file begins with."""
    required = c.c_uint64()
    _support.size_call("cna_cnb_copy_format_magic", None, c.c_uint64(0), c.byref(required))
    buffer = (c.c_uint8 * int(required.value))()
    written = c.c_uint64()
    _support.call("cna_cnb_copy_format_magic", buffer, required, c.byref(written))
    return bytes(bytearray(buffer)[: written.value])


def has_magic(data: bytes) -> bool:
    """Whether ``data`` begins with the `.cnb` magic.

    A cheap pre-check for a tool that inspects files by content rather than by
    extension. It says nothing about whether the rest of the file is valid.
    """
    pointer, count, _keep = _support.read_only_bytes(data, "data")
    return _support.out_bool("cna_cnb_has_magic", pointer, c.c_uint64(count))


def chunk_id(text: str) -> int:
    """Packs a four-character chunk identifier the way the format stores it.

    Every byte must be printable ASCII. An identifier whose first byte is an
    uppercase ASCII letter is reserved for CNA's own schemas; a game defining
    its own `.cnb` schema uses one starting with a lowercase letter.
    """
    if not isinstance(text, str):
        raise TypeError("chunk identifier must be str")
    raw = text.encode("ascii", errors="strict") if text.isascii() else None
    if raw is None or len(raw) != 4:
        raise ValueError("chunk identifier must be exactly four ASCII characters")
    return _support.out_u32(
        "cna_cnb_make_chunk_id", *(c.c_uint8(byte) for byte in raw))


def chunk_id_text(identifier: int) -> str:
    """Renders a chunk identifier as its four characters, for diagnostics.

    Any byte outside printable ASCII renders as ``?``, so a corrupt identifier
    cannot inject control characters into a log line.
    """
    value = c.c_uint32(_support.checked(identifier, "uint32", "chunk identifier"))
    return _support.sized_text(
        "cna_cnb_get_chunk_id_string_size", "cna_cnb_copy_chunk_id_string",
        (value,), "chunk identifier text")


def is_well_formed_chunk_id(identifier: int) -> bool:
    """Whether every byte of the identifier is printable ASCII, as required."""
    value = c.c_uint32(_support.checked(identifier, "uint32", "chunk identifier"))
    return _support.out_bool("cna_cnb_is_well_formed_chunk_id", value)


def asset_type_id_from_name(name: str) -> int:
    """Mints the custom asset type identifier for a game-defined type name.

    The identifier is ``FNV-1a-32(name) | 0x80000000``, so it carries 31 usable
    bits and collisions are possible in principle. That is exactly why the
    ``CMET`` chunk carries the type name: a loader can report a mismatch rather
    than decode the wrong asset.
    """
    view, _keep = _support.string_view(name, "name")
    return _support.out_u32("cna_cnb_asset_type_id_from_name", view)


def is_custom_asset_type_id(asset_type_id: int) -> bool:
    """Whether the identifier lies in the game-defined custom range."""
    value = c.c_uint32(_support.checked(asset_type_id, "uint32", "asset type id"))
    return _support.out_bool("cna_cnb_is_custom_asset_type_id", value)


def asset_type_name(asset_type_id: int) -> str:
    """Renders an asset type identifier as a human-readable name.

    A built-in type gives its name; a custom or unrecognized one gives a
    hexadecimal rendering.
    """
    value = c.c_uint32(_support.checked(asset_type_id, "uint32", "asset type id"))
    return _support.sized_text(
        "cna_cnb_get_asset_type_name_size", "cna_cnb_copy_asset_type_name",
        (value,), "asset type name")


def logical_name_problem(logical_name: str | bytes) -> str | None:
    """Why ``logical_name`` is not a legal external-reference name, or ``None``.

    A name is legal when it is non-empty, well-formed UTF-8, relative, and
    ``/``-separated with no ``..`` segment. The input is deliberately not
    validated as UTF-8 first -- malformed UTF-8 is one of the verdicts this
    reports.
    """
    if isinstance(logical_name, str):
        raw = logical_name.encode("utf-8")
    elif isinstance(logical_name, (bytes, bytearray)):
        raw = bytes(logical_name)
    else:
        raise TypeError("logical_name must be str or bytes")
    view, _keep = _support.raw_string_view(raw)
    size = _support.out_u64("cna_cnb_get_logical_name_problem_size", view)
    if size == 0:
        return None
    buffer = c.create_string_buffer(size)
    written = c.c_uint64()
    _support.call("cna_cnb_copy_logical_name_problem", view, buffer,
                  c.c_uint64(size), c.byref(written))
    return bytes(buffer.raw[: written.value]).decode("utf-8")


def is_well_formed_utf8(text: bytes) -> bool:
    """Whether raw bytes are well-formed UTF-8 by CNA's own check.

    Published so a writer can reject a malformed string before committing it to
    a file, keeping both ends of the format honest.
    """
    if not isinstance(text, (bytes, bytearray, memoryview)):
        raise TypeError("text must be a bytes-like object")
    view, _keep = _support.raw_string_view(bytes(text))
    return _support.out_bool("cna_cnb_is_well_formed_utf8", view)


def crc32c(data: bytes, *, previous: int | None = None, portable: bool = False) -> int:
    """The CRC-32C (Castagnoli) checksum every `.cnb` structure carries.

    Reflected polynomial ``0x82F63B78``, initial register ``0xFFFFFFFF``,
    reflected input and output, final XOR ``0xFFFFFFFF`` -- the iSCSI/SSE4.2
    parameter set, and not the CRC-32 in Python's standard library.

    ``previous`` continues a running checksum over a logically contiguous region
    split across buffers; pass :data:`CRC32C_SEED` to start one explicitly.
    ``portable`` forces the table-driven reference path, which is how a caller
    proves the hardware path agrees with something other than itself.

    This detects **accidental** corruption. It is not a message authentication
    code: anyone who can rewrite a chunk can rewrite its checksum.
    """
    pointer, count, _keep = _support.read_only_bytes(data, "data")
    if previous is not None and portable:
        raise ValueError("the portable path has no continuation route in CNA")
    if previous is not None:
        return _support.out_u32(
            "cna_cnb_crc32c_continue",
            c.c_uint32(_support.checked(previous, "uint32", "previous")),
            pointer, c.c_uint64(count))
    operation = "cna_cnb_crc32c_portable" if portable else "cna_cnb_crc32c"
    return _support.out_u32(operation, pointer, c.c_uint64(count))


def uses_hardware_crc32c() -> bool:
    """Whether this process folds CRC-32C with a hardware instruction.

    Detected once at runtime rather than chosen at build time. The value is
    identical either way, so nothing about correctness depends on this -- but a
    measurement that does not know which path it timed is one that will
    eventually mislead someone.
    """
    return _support.out_bool("cna_cnb_crc32c_uses_hardware")


def is_compression_supported(codec: Compression | int) -> bool:
    """Whether this build can compress and decompress ``codec`` both ways.

    ``Compression.NoCompression`` is always supported. Zstandard depends on a
    build option that is quietly off when the system library is missing, so ask
    rather than assume. An identity outside the named set answers ``False``,
    which is exactly true of a codec that does not exist.
    """
    value = c.c_uint32(_support.checked(int(codec), "uint32", "codec"))
    return _support.out_bool("cna_cnb_is_compression_supported", value)


def compression_name(codec: Compression | int) -> str:
    """Renders a codec identity for diagnostics.

    A named codec gives its name; any other value gives ``unknown codec N``, so
    a corrupt table-of-contents entry still produces a readable line.
    """
    value = c.c_uint32(_support.checked(int(codec), "uint32", "codec"))
    return _support.sized_text(
        "cna_cnb_get_compression_name_size", "cna_cnb_copy_compression_name",
        (value,), "compression name")


def compressed_size(data: bytes, codec: Compression | int, *, level: int = 3) -> int:
    """How many bytes :func:`compress` would produce for the same input.

    Compression is performed to answer this, exactly as encoding an image is to
    answer its own byte count, so this is a way to decide whether compression
    pays -- not a cheap way to size a buffer before compressing.
    """
    pointer, count, _keep = _support.read_only_bytes(data, "data")
    return _support.out_u64(
        "cna_cnb_get_compressed_byte_count", pointer, c.c_uint64(count),
        c.c_uint32(_support.checked(int(codec), "uint32", "codec")),
        c.c_int32(_support.checked(level, "int32", "level")))


def compress(data: bytes, codec: Compression | int, *, level: int = 3) -> bytes:
    """Compresses a chunk payload with one of the container's codecs.

    ``Compression.NoCompression`` copies the input unchanged. ``level`` is
    codec-specific effort -- for Zstandard 1..19, with 3 the measured sweet spot
    -- and a value outside the codec's range is clamped rather than refused,
    matching CNA.
    """
    pointer, count, keep = _support.read_only_bytes(data, "data")
    arguments = (pointer, c.c_uint64(count),
                 c.c_uint32(_support.checked(int(codec), "uint32", "codec")),
                 c.c_int32(_support.checked(level, "int32", "level")))
    result = _support.two_call_bytes("cna_cnb_copy_compressed", arguments)
    del keep
    return result


def decompress(stored: bytes, codec: Compression | int, uncompressed_size: int, *,
               max_uncompressed_size: int | None = None) -> bytes:
    """Expands a stored chunk payload to exactly ``uncompressed_size`` bytes.

    The exact-size requirement is the safety story. ``uncompressed_size`` comes
    from a file's table of contents, so it is attacker-controlled: it is checked
    against ``max_uncompressed_size`` **before anything is allocated**, and the
    codec must then produce exactly that many bytes, so a stream that expands to
    a different size is a corrupt file rather than a short read.

    ``max_uncompressed_size`` defaults to the default limits'
    ``max_chunk_size``, which is the ceiling CNA's own reader applies.
    """
    if max_uncompressed_size is None:
        max_uncompressed_size = CnbReadLimits.defaults().max_chunk_size
    pointer, count, keep = _support.read_only_bytes(stored, "stored")
    arguments = (pointer, c.c_uint64(count),
                 c.c_uint32(_support.checked(int(codec), "uint32", "codec")),
                 c.c_uint64(_support.checked(uncompressed_size, "uint64",
                                             "uncompressed_size")),
                 c.c_uint64(_support.checked(max_uncompressed_size, "uint64",
                                             "max_uncompressed_size")))
    result = _support.two_call_bytes("cna_cnb_copy_decompressed", arguments)
    del keep
    return result


def _chunk_ids_array(values: Iterable[int]):
    """Copies chunk identifiers into a C array, or ``(None, 0)`` when empty."""
    items = [_support.checked(int(value), "uint32", "chunk identifier") for value in values]
    if not items:
        return None, 0
    return (c.c_uint32 * len(items))(*items), len(items)
