"""Compiled ``SpriteFont`` data: the glyph table and the atlas it indexes into.

A compiled font embeds its atlas rather than referencing it: an atlas normally
belongs to exactly one font, so the pixels are stored with exactly the chunks,
strides, alignment and validation a standalone 2D texture would use, in the
font's own file. A model's textures are shared and are referenced through
``XREF`` instead -- the difference is deliberate.

:class:`CnbGlyph` reuses the strict XNA ``Rectangle`` and ``Vector3`` value types
where they are exactly the natural representation. That dependency runs
extension -> strict only; ``Microsoft.Xna.Framework`` learns nothing from this
module existing.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import Sequence

from Microsoft.Xna.Framework import Rectangle, Vector3

from _cna_native import abi as _core_abi
from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .textures import CnbTextureData

__all__ = [
    "MAX_SPRITE_FONT_GLYPHS",
    "SPRITE_FONT_SCHEMA_VERSION",
    "CnbGlyph",
    "CnbSpriteFontData",
    "CnbSpriteFontInfo",
    "SpriteFontChunk",
    "decode_sprite_font",
    "encode_sprite_font",
]

#: Ceiling on the glyphs a file may declare.
MAX_SPRITE_FONT_GLYPHS = _abi.CNA_CNB_MAX_SPRITE_FONT_GLYPHS
#: Highest ``SpriteFont`` schema version this CNA generation understands.
SPRITE_FONT_SCHEMA_VERSION = _abi.CNA_CNB_SPRITE_FONT_SCHEMA_VERSION


class SpriteFontChunk(IntEnum):
    """The five chunk identifiers the sprite font schema writes."""

    Header = _abi.CNA_CNB_SPRITE_FONT_CHUNK_HEADER
    GlyphBounds = _abi.CNA_CNB_SPRITE_FONT_CHUNK_GLYPH_BOUNDS
    Cropping = _abi.CNA_CNB_SPRITE_FONT_CHUNK_CROPPING
    Kerning = _abi.CNA_CNB_SPRITE_FONT_CHUNK_KERNING
    Characters = _abi.CNA_CNB_SPRITE_FONT_CHUNK_CHARACTERS


@dataclass(frozen=True)
class CnbGlyph:
    """One glyph: where it is in the atlas, how it is cropped, and its kerning.

    The canonical `.cnb` schema keeps these as four parallel arrays; this is one
    row of all four, which is how CNA's own glyph type presents them too.
    ``kerning`` is ``(left bearing, width, right bearing)``.
    """

    character: str
    bounds: Rectangle
    cropping: Rectangle
    kerning: Vector3

    def _to_native(self) -> _core_abi.CNA_SpriteFontGlyph:
        if not isinstance(self.character, str) or len(self.character) != 1:
            raise ValueError("character must be exactly one character")
        code_point = ord(self.character)
        if code_point > 0xFFFF:
            raise ValueError(
                "the .cnb character map stores UTF-16 code units, so a character "
                f"outside the basic multilingual plane cannot be a glyph: U+{code_point:X}")
        value = _core_abi.CNA_SpriteFontGlyph()
        value.struct_size = c.sizeof(_core_abi.CNA_SpriteFontGlyph)
        value.struct_version = 1
        value.glyph_bounds.x = int(self.bounds.X)
        value.glyph_bounds.y = int(self.bounds.Y)
        value.glyph_bounds.width = int(self.bounds.Width)
        value.glyph_bounds.height = int(self.bounds.Height)
        value.cropping.x = int(self.cropping.X)
        value.cropping.y = int(self.cropping.Y)
        value.cropping.width = int(self.cropping.Width)
        value.cropping.height = int(self.cropping.Height)
        value.character = code_point
        value.reserved = 0
        value.kerning.x = float(self.kerning.X)
        value.kerning.y = float(self.kerning.Y)
        value.kerning.z = float(self.kerning.Z)
        return value

    @classmethod
    def _from_native(cls, value: _core_abi.CNA_SpriteFontGlyph) -> "CnbGlyph":
        return cls(
            character=chr(int(value.character)),
            bounds=Rectangle(int(value.glyph_bounds.x), int(value.glyph_bounds.y),
                             int(value.glyph_bounds.width), int(value.glyph_bounds.height)),
            cropping=Rectangle(int(value.cropping.x), int(value.cropping.y),
                               int(value.cropping.width), int(value.cropping.height)),
            kerning=Vector3(float(value.kerning.x), float(value.kerning.y),
                            float(value.kerning.z)),
        )


@dataclass(frozen=True)
class CnbSpriteFontInfo:
    """A compiled font's glyph count and its whole-font metrics.

    ``default_character`` is meaningful only when ``has_default_character`` is
    true; a font without one throws on a missing character rather than
    substituting.
    """

    glyph_count: int
    line_spacing: int
    spacing: float
    default_character: str | None

    @property
    def has_default_character(self) -> bool:
        """Whether the font falls back rather than throwing on a missing character."""
        return self.default_character is not None


class CnbSpriteFontData:
    """The decoded contents of a ``SpriteFont`` `.cnb`, atlas included.

    Owns native memory, so it has an explicit :meth:`close` and works as a
    context manager.
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: _support.NativeHandle) -> None:
        self._handle = handle

    @classmethod
    def _adopt(cls, handle: int) -> "CnbSpriteFontData":
        return cls(_support.NativeHandle(
            handle, "cna_cnb_sprite_font_data_destroy", "sprite font data"))

    @classmethod
    def create(cls) -> "CnbSpriteFontData":
        """An empty compiled-font description."""
        return cls._adopt(_support.out_handle("cna_cnb_sprite_font_data_create"))

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the description, its glyph table and its atlas."""
        self._handle.close()

    def __enter__(self) -> "CnbSpriteFontData":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    @property
    def info(self) -> CnbSpriteFontInfo:
        """The font's glyph count and whole-font metrics."""
        value = _support.out_struct(
            _abi.CNA_CnbSpriteFontInfo, _abi.CNA_CNB_SPRITE_FONT_INFO_STRUCT_VERSION,
            "cna_cnb_sprite_font_data_get_info", self._value)
        return CnbSpriteFontInfo(
            glyph_count=int(value.glyph_count),
            line_spacing=int(value.line_spacing),
            spacing=float(value.spacing),
            default_character=(chr(int(value.default_character))
                               if value.has_default_character else None),
        )

    def set_info(self, *, line_spacing: int, spacing: float,
                 default_character: str | None = None) -> None:
        """Sets the whole-font metrics.

        The glyph count is not settable: it follows from the glyphs actually
        added, so accepting one here would let the two disagree.
        """
        value = _abi.CNA_CnbSpriteFontInfo()
        value.struct_size = c.sizeof(_abi.CNA_CnbSpriteFontInfo)
        value.struct_version = _abi.CNA_CNB_SPRITE_FONT_INFO_STRUCT_VERSION
        value.glyph_count = 0
        value.line_spacing = _support.checked(line_spacing, "int32", "line_spacing")
        value.spacing = float(spacing)
        if default_character is None:
            value.default_character = 0
            value.has_default_character = 0
        else:
            if len(default_character) != 1:
                raise ValueError("default_character must be exactly one character")
            value.default_character = _support.checked(
                ord(default_character), "uint16", "default_character")
            value.has_default_character = 1
        _support.call("cna_cnb_sprite_font_data_set_info", self._value, c.byref(value))

    def add_glyph(self, glyph: CnbGlyph) -> int:
        """Appends one glyph and returns its index."""
        native = glyph._to_native()
        return _support.out_u64(
            "cna_cnb_sprite_font_data_add_glyph", self._value, c.byref(native))

    def glyph(self, index: int) -> CnbGlyph:
        """The glyph at ``index``."""
        value = _core_abi.CNA_SpriteFontGlyph()
        value.struct_size = c.sizeof(_core_abi.CNA_SpriteFontGlyph)
        value.struct_version = 1
        _support.call(
            "cna_cnb_sprite_font_data_get_glyph", self._value,
            c.c_uint64(_support.checked(index, "uint64", "index")), c.byref(value))
        return CnbGlyph._from_native(value)

    def set_glyph(self, index: int, glyph: CnbGlyph) -> None:
        """Replaces the glyph at ``index``."""
        native = glyph._to_native()
        _support.call(
            "cna_cnb_sprite_font_data_set_glyph", self._value,
            c.c_uint64(_support.checked(index, "uint64", "index")), c.byref(native))

    @property
    def glyphs(self) -> tuple[CnbGlyph, ...]:
        """Every glyph, in the order the character map stores them."""
        return tuple(self.glyph(index) for index in range(self.info.glyph_count))

    def set_atlas(self, atlas: CnbTextureData) -> None:
        """Sets the glyph atlas, copying it rather than adopting the handle.

        The caller keeps ownership of ``atlas`` and must still close it.
        """
        _support.call("cna_cnb_sprite_font_data_set_atlas", self._value, atlas._value)

    def atlas(self) -> CnbTextureData:
        """A **new, independently owned** copy of the glyph atlas.

        The caller closes what comes back; closing it does not affect the font.
        """
        return CnbTextureData._adopt(
            _support.out_handle("cna_cnb_sprite_font_data_copy_atlas", self._value))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbSpriteFontData closed>"
        return f"<CnbSpriteFontData glyphs {self.info.glyph_count}>"


def encode_sprite_font(font: CnbSpriteFontData, *, content_name: str = "") -> bytes:
    """Encodes a compiled font, atlas included, as a complete `.cnb` byte image."""
    view, keep = _support.string_view(content_name, "content_name")
    result = _support.two_call_bytes("cna_cnb_encode_sprite_font", (font._value, view))
    del keep
    return result


def decode_sprite_font(document) -> CnbSpriteFontData:
    """Decodes a compiled font from a parsed container."""
    return CnbSpriteFontData._adopt(
        _support.out_handle("cna_cnb_decode_sprite_font", document._value))
