"""Compiled texture data: the pixels a `.cnb` holds, independent of any GPU.

:class:`CnbTextureData` is **asset data, not a runtime object**. It has no
graphics device, no GPU allocation and no ``Texture2D`` behind it, which is what
lets the whole encode/decode half be exercised with no display and no renderer
at all. Turning one into a real ``Microsoft.Xna.Framework.Graphics.Texture2D``
needs a device and is deliberately not part of this family.

A texture may carry the same image several times over -- once as ``Rgba8``, once
as ``Bc7``, once as something else -- so a runtime can pick whichever its GPU
supports without a second asset. Each of those is a **representation**, and its
levels are ordered face-major then mip: for a cube map that is ``+X`` mip 0,
``+X`` mip 1, ..., then ``-X`` mip 0, and so on.
"""

from __future__ import annotations

import ctypes as c
from enum import IntEnum
from typing import Callable

from Microsoft.Xna.Framework.Graphics import SurfaceFormat

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

__all__ = [
    "CUBE_FACE_COUNT",
    "MAX_TEXTURE_MIP_LEVELS",
    "MAX_TEXTURE_REPRESENTATIONS",
    "TEXTURE_SCHEMA_VERSION",
    "CnbTextureData",
    "CnbTextureInfo",
    "TextureChunk",
    "TextureFormat",
    "decode_texture2d",
    "decode_texture3d",
    "decode_texture_cube",
    "encode_texture2d",
    "encode_texture3d",
    "encode_texture_cube",
    "is_block_compressed",
    "is_known_texture_format",
    "texture_format_from_surface_format",
    "texture_format_name",
    "texture_format_to_surface_format",
    "texture_format_unit_bytes",
    "texture_level_byte_size",
]

#: Faces a cube texture has, in the fixed order +X, -X, +Y, -Y, +Z, -Z.
CUBE_FACE_COUNT = _abi.CNA_CNB_TEXTURE_CUBE_FACE_COUNT
#: Ceiling on the mip levels a file may declare.
MAX_TEXTURE_MIP_LEVELS = _abi.CNA_CNB_MAX_TEXTURE_MIP_LEVELS
#: Ceiling on the representations a file may declare.
MAX_TEXTURE_REPRESENTATIONS = _abi.CNA_CNB_MAX_TEXTURE_REPRESENTATIONS
#: Highest texture schema version this CNA generation understands.
TEXTURE_SCHEMA_VERSION = _abi.CNA_CNB_TEXTURE_SCHEMA_VERSION


class TextureFormat(IntEnum):
    """A pixel format identifier as a `.cnb` texture stores it.

    These exist instead of serializing ``SurfaceFormat``, and the reason
    matters: XNA's ``SurfaceFormat`` enumerators carry no explicit values, so
    inserting one would renumber every enumerator after it and silently change
    the meaning of every `.cnb` already written. These values are frozen the way
    the container's own constants are, and
    :func:`texture_format_to_surface_format` is a deliberate mapping rather than
    a cast that follows along quietly.

    Every ``SurfaceFormat`` CNA defines has an identifier here. That is separate
    from what schema 1 will actually *encode*, which is ``Rgba8`` alone --
    decoding accepts any of them.
    """

    Unknown = _abi.CNA_CNB_TEXTURE_FORMAT_UNKNOWN
    Rgba8 = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA8
    Bgra8 = _abi.CNA_CNB_TEXTURE_FORMAT_BGRA8
    Rgba8Srgb = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA8_SRGB
    Bgr565 = _abi.CNA_CNB_TEXTURE_FORMAT_BGR565
    Bgra5551 = _abi.CNA_CNB_TEXTURE_FORMAT_BGRA5551
    Bgra4444 = _abi.CNA_CNB_TEXTURE_FORMAT_BGRA4444
    Alpha8 = _abi.CNA_CNB_TEXTURE_FORMAT_ALPHA8
    R8 = _abi.CNA_CNB_TEXTURE_FORMAT_R8
    R16 = _abi.CNA_CNB_TEXTURE_FORMAT_R16
    Rg16 = _abi.CNA_CNB_TEXTURE_FORMAT_RG16
    Rgba16 = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA16
    Rg8Snorm = _abi.CNA_CNB_TEXTURE_FORMAT_RG8_SNORM
    Rgba8Snorm = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA8_SNORM
    Rgb10A2 = _abi.CNA_CNB_TEXTURE_FORMAT_RGB10_A2
    R32Float = _abi.CNA_CNB_TEXTURE_FORMAT_R32_FLOAT
    Rg32Float = _abi.CNA_CNB_TEXTURE_FORMAT_RG32_FLOAT
    Rgba32Float = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA32_FLOAT
    R16Float = _abi.CNA_CNB_TEXTURE_FORMAT_R16_FLOAT
    Rg16Float = _abi.CNA_CNB_TEXTURE_FORMAT_RG16_FLOAT
    Rgba16Float = _abi.CNA_CNB_TEXTURE_FORMAT_RGBA16_FLOAT
    HdrBlendable = _abi.CNA_CNB_TEXTURE_FORMAT_HDR_BLENDABLE
    Bc1 = _abi.CNA_CNB_TEXTURE_FORMAT_BC1
    Bc2 = _abi.CNA_CNB_TEXTURE_FORMAT_BC2
    Bc3 = _abi.CNA_CNB_TEXTURE_FORMAT_BC3
    Bc3Srgb = _abi.CNA_CNB_TEXTURE_FORMAT_BC3_SRGB
    Bc7 = _abi.CNA_CNB_TEXTURE_FORMAT_BC7
    Bc7Srgb = _abi.CNA_CNB_TEXTURE_FORMAT_BC7_SRGB


class TextureChunk(IntEnum):
    """The three chunk identifiers every texture schema writes."""

    Header = _abi.CNA_CNB_TEXTURE_CHUNK_HEADER
    Representations = _abi.CNA_CNB_TEXTURE_CHUNK_REPRESENTATIONS
    Payload = _abi.CNA_CNB_TEXTURE_CHUNK_PAYLOAD


class CnbTextureInfo:
    """A texture's shape: level-0 dimensions and its three counts.

    Immutable; read it from :attr:`CnbTextureData.info`.
    """

    __slots__ = ("width", "height", "depth", "face_count", "mip_count",
                 "representation_count")

    def __init__(self, width: int, height: int, depth: int, face_count: int,
                 mip_count: int, representation_count: int) -> None:
        self.width = width
        self.height = height
        self.depth = depth
        self.face_count = face_count
        self.mip_count = mip_count
        self.representation_count = representation_count

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CnbTextureInfo):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))

    def __repr__(self) -> str:
        return (f"CnbTextureInfo(width={self.width}, height={self.height}, "
                f"depth={self.depth}, face_count={self.face_count}, "
                f"mip_count={self.mip_count}, "
                f"representation_count={self.representation_count})")


def is_known_texture_format(value: int) -> bool:
    """Whether a raw identifier read from a file names a format this build knows."""
    return _support.out_bool(
        "cna_cnb_is_known_texture_format",
        c.c_uint32(_support.checked(int(value), "uint32", "value")))


def texture_format_name(texture_format: TextureFormat | int) -> str:
    """Renders a format identifier for diagnostics.

    A known format gives its name; any other value gives a hexadecimal
    rendering, so a corrupt file's format field still produces a readable line.
    """
    value = c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format"))
    return _support.sized_text(
        "cna_cnb_get_texture_format_name_size", "cna_cnb_copy_texture_format_name",
        (value,), "texture format name")


def is_block_compressed(texture_format: TextureFormat | int) -> bool:
    """Whether the format stores 4x4 texel blocks rather than individual texels."""
    value = c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format"))
    return _support.out_bool("cna_cnb_is_block_compressed_texture_format", value)


def texture_format_unit_bytes(texture_format: TextureFormat | int) -> int:
    """Bytes one texel occupies, or one 4x4 block for a block-compressed format.

    Zero when the format is not known.
    """
    value = c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format"))
    return _support.out_u32("cna_cnb_get_texture_format_unit_bytes", value)


def texture_level_byte_size(texture_format: TextureFormat | int, width: int, height: int,
                            depth: int = 1) -> int:
    """Bytes one mip level of the given dimensions occupies in this format.

    A block-compressed level rounds each dimension up to a whole 4-texel block,
    which is what makes a 1x1 ``Bc7`` level 16 bytes rather than a fraction of
    one.
    """
    return _support.out_u64(
        "cna_cnb_get_texture_level_byte_size",
        c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format")),
        c.c_uint32(_support.checked(width, "uint32", "width")),
        c.c_uint32(_support.checked(height, "uint32", "height")),
        c.c_uint32(_support.checked(depth, "uint32", "depth")))


def texture_format_to_surface_format(texture_format: TextureFormat | int) -> SurfaceFormat:
    """Maps a CNB format identifier onto the runtime ``SurfaceFormat``.

    The dependency runs extension -> strict, which is the allowed direction:
    ``Microsoft.Xna.Framework.Graphics`` gains nothing and learns nothing from
    this package existing.
    """
    value = c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format"))
    return SurfaceFormat(
        _support.out_u32("cna_cnb_texture_format_to_surface_format", value))


def texture_format_from_surface_format(surface_format: SurfaceFormat | int) -> TextureFormat:
    """Maps a runtime ``SurfaceFormat`` onto its CNB format identifier."""
    value = c.c_uint32(_support.checked(int(surface_format), "uint32", "surface_format"))
    return TextureFormat(
        _support.out_u32("cna_cnb_texture_format_from_surface_format", value))


class CnbTextureData:
    """The decoded contents of a texture `.cnb`, independent of any GPU object.

    Build one with :meth:`create` or :meth:`from_rgba8`, or get one back from a
    decoder or importer. It owns native memory, so it has an explicit
    :meth:`close` and works as a context manager.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @classmethod
    def _adopt(cls, handle: int) -> "CnbTextureData":
        return cls(_support.NativeHandle(
            handle, "cna_cnb_texture_data_destroy", "texture data"))

    @classmethod
    def create(cls, width: int, height: int, *, depth: int = 1, face_count: int = 1,
               mip_count: int = 1) -> "CnbTextureData":
        """An empty description with the given shape.

        Add at least one representation with :meth:`add_representation` before
        encoding, and fill every one of its ``face_count * mip_count`` levels.
        """
        handle = _support.out_handle(
            "cna_cnb_texture_data_create",
            c.c_uint32(_support.checked(width, "uint32", "width")),
            c.c_uint32(_support.checked(height, "uint32", "height")),
            c.c_uint32(_support.checked(depth, "uint32", "depth")),
            c.c_uint32(_support.checked(face_count, "uint32", "face_count")),
            c.c_uint32(_support.checked(mip_count, "uint32", "mip_count")))
        return cls._adopt(handle)

    @classmethod
    def from_rgba8(cls, width: int, height: int, rgba: bytes) -> "CnbTextureData":
        """A single-representation, single-mip ``Rgba8`` 2D description.

        ``rgba`` must be exactly ``width * height * 4`` bytes in R, G, B, A
        order -- the common case of a decoded PNG, and what schema 1 encodes.
        """
        pointer, count, keep = _support.read_only_bytes(rgba, "rgba")
        handle = _support.out_handle(
            "cna_cnb_texture_data_create_rgba8",
            c.c_uint32(_support.checked(width, "uint32", "width")),
            c.c_uint32(_support.checked(height, "uint32", "height")),
            pointer, c.c_uint64(count))
        del keep
        return cls._adopt(handle)

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the description and every payload it holds."""
        self._handle.close()

    def __enter__(self) -> "CnbTextureData":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    @property
    def info(self) -> CnbTextureInfo:
        """The texture's shape."""
        value = _support.out_struct(
            _abi.CNA_CnbTextureInfo, _abi.CNA_CNB_TEXTURE_INFO_STRUCT_VERSION,
            "cna_cnb_texture_data_get_info", self._value)
        return CnbTextureInfo(
            width=int(value.width), height=int(value.height), depth=int(value.depth),
            face_count=int(value.face_count), mip_count=int(value.mip_count),
            representation_count=int(value.representation_count))

    def level_dimensions(self, level: int) -> tuple[int, int, int]:
        """The ``(width, height, depth)`` of one mip level, level 0 being full size.

        Each dimension halves per level and never falls below 1, which is the
        standard mip rule and the one every level byte size is computed against.
        """
        width, height, depth = c.c_uint32(), c.c_uint32(), c.c_uint32()
        _support.call(
            "cna_cnb_texture_data_get_level_dimensions", self._value,
            c.c_uint32(_support.checked(level, "uint32", "level")),
            c.byref(width), c.byref(height), c.byref(depth))
        return int(width.value), int(height.value), int(depth.value)

    def add_representation(self, texture_format: TextureFormat | int) -> int:
        """Appends a representation, sized for ``face_count * mip_count`` empty levels.

        Representations are recorded in **preference order**, which is what
        :meth:`select_representation` walks.
        """
        return _support.out_u64(
            "cna_cnb_texture_data_add_representation", self._value,
            c.c_uint32(_support.checked(int(texture_format), "uint32", "texture_format")))

    @property
    def representation_count(self) -> int:
        """Number of representations the texture carries."""
        return _support.out_u64(
            "cna_cnb_texture_data_get_representation_count", self._value)

    def representation_format(self, representation: int) -> TextureFormat:
        """The storage format of one representation."""
        return TextureFormat(_support.out_u32(
            "cna_cnb_texture_data_get_representation_format", self._value,
            c.c_uint64(_support.checked(representation, "uint64", "representation"))))

    def level_count(self, representation: int) -> int:
        """Level payloads one representation holds: ``face_count * mip_count``."""
        return _support.out_u64(
            "cna_cnb_texture_data_get_level_count", self._value,
            c.c_uint64(_support.checked(representation, "uint64", "representation")))

    def set_level(self, representation: int, level: int, payload: bytes) -> None:
        """Sets one level's payload bytes.

        Levels are ordered face-major then mip: index ``face * mip_count + mip``.
        """
        pointer, count, keep = _support.read_only_bytes(payload, "payload")
        _support.call(
            "cna_cnb_texture_data_set_level", self._value,
            c.c_uint64(_support.checked(representation, "uint64", "representation")),
            c.c_uint64(_support.checked(level, "uint64", "level")),
            pointer, c.c_uint64(count))
        del keep

    def level(self, representation: int, level: int) -> bytes:
        """Copies one level's payload bytes."""
        return _support.two_call_bytes(
            "cna_cnb_texture_data_copy_level",
            (self._value,
             c.c_uint64(_support.checked(representation, "uint64", "representation")),
             c.c_uint64(_support.checked(level, "uint64", "level"))))

    def select_representation(
            self, supported: Callable[[TextureFormat], bool]) -> int | None:
        """The representation a caller should upload, or ``None`` if it can use none.

        The writer records representations in preference order, so a runtime
        taking the first format it can upload gets the author's intended choice.
        Absence is an ordinary answer, not a failure.

        ``supported`` is called synchronously, once per representation in order,
        and is never retained past this call. An exception it raises is captured
        and re-raised **after** CNA has returned, because a Python exception
        unwinding through a C frame is undefined behaviour.
        """
        failures: list[BaseException] = []

        def predicate(value: int) -> bool:
            return bool(supported(TextureFormat(value)))

        bridge = _abi.CNA_CnbTextureFormatSupportedFn(
            _support.format_supported_bridge(predicate, failures))
        found = c.c_uint8()
        index = c.c_uint64()
        try:
            _support.call("cna_cnb_texture_data_select_representation", self._value,
                          bridge, None, c.byref(found), c.byref(index))
        finally:
            if failures:
                raise failures[0]
        return int(index.value) if found.value else None

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbTextureData closed>"
        info = self.info
        return (f"<CnbTextureData {info.width}x{info.height}x{info.depth} "
                f"faces {info.face_count} mips {info.mip_count} "
                f"representations {info.representation_count}>")


def _encode(operation: str, texture: CnbTextureData, content_name: str) -> bytes:
    view, keep = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes(operation, (texture._value, view))
    del keep
    return result


def encode_texture2d(texture: CnbTextureData, *, content_name: str = "") -> bytes:
    """Encodes a 2D texture as a complete `.cnb` byte image.

    The description's face count and depth must both be 1.
    """
    return _encode("cna_cnb_encode_texture2d", texture, content_name)


def encode_texture_cube(texture: CnbTextureData, *, content_name: str = "") -> bytes:
    """Encodes a cube texture as a complete `.cnb` byte image.

    The face count must be 6, the depth 1, and the width must equal the height,
    because a cube face is square.
    """
    return _encode("cna_cnb_encode_texture_cube", texture, content_name)


def encode_texture3d(texture: CnbTextureData, *, content_name: str = "") -> bytes:
    """Encodes a 3D texture as a complete `.cnb` byte image.

    The face count must be 1; the depth may be any positive value and halves per
    mip level like the other two dimensions.
    """
    return _encode("cna_cnb_encode_texture3d", texture, content_name)


def _decode(operation: str, document) -> CnbTextureData:
    return CnbTextureData._adopt(_support.out_handle(operation, document._value))


def decode_texture2d(document) -> CnbTextureData:
    """Decodes a 2D texture from a parsed container."""
    return _decode("cna_cnb_decode_texture2d", document)


def decode_texture_cube(document) -> CnbTextureData:
    """Decodes a cube texture from a parsed container, with a face count of 6."""
    return _decode("cna_cnb_decode_texture_cube", document)


def decode_texture3d(document) -> CnbTextureData:
    """Decodes a 3D texture from a parsed container."""
    return _decode("cna_cnb_decode_texture3d", document)
