"""What a sprite font should be built from.

A ``FontDescription`` is the ``.spritefont`` file: a font name, a size, the
extra spacing between characters, and which characters to include. It is the
*input* to a build, not the output -- the output is a texture and a table of
glyph rectangles, and turning one into the other is the font processor's job.
"""

from __future__ import annotations

from enum import IntFlag

from .._identity import ContentItem


class FontDescriptionStyle(IntFlag):
    """The style a font should be rasterized in.

    Flags, as XNA declares it: ``Bold | Italic`` is a style a font description
    may ask for, and the two values really are one and two.
    """

    Regular = 0
    Bold = 1
    Italic = 2


class FontDescription(ContentItem):
    """One font, described.

    ``Characters`` is a set rather than a list: a ``.spritefont`` names
    character *ranges*, the same character can appear in two of them, and a
    glyph built twice would waste texture space and produce a second entry the
    runtime would never reach.
    """

    __slots__ = ("_font_name", "_size", "_spacing", "_use_kerning", "_style",
                 "_default_character", "_characters")

    def __init__(self, fontName: str, size: float, spacing: float,
                 fontStyle: FontDescriptionStyle = FontDescriptionStyle.Regular,
                 useKerning: bool = True) -> None:
        super().__init__()
        self._font_name = ""
        self._size = 0.0
        self._spacing = 0.0
        self._style = FontDescriptionStyle.Regular
        self._use_kerning = True
        self._default_character: str | None = None
        self._characters: set[str] = set()
        self.FontName = fontName
        self.Size = size
        self.Spacing = spacing
        self.Style = fontStyle
        self.UseKerning = useKerning

    @property
    def FontName(self) -> str:
        return self._font_name

    @FontName.setter
    def FontName(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"FontName must be a str, not {type(value).__name__}")
        if not value.strip():
            raise ValueError("FontName must name a font")
        self._font_name = value

    @property
    def Size(self) -> float:
        return self._size

    @Size.setter
    def Size(self, value: float) -> None:
        number = _real(value, "Size")
        if number <= 0.0:
            raise ValueError(f"Size must be positive, got {number}")
        self._size = number

    @property
    def Spacing(self) -> float:
        return self._spacing

    @Spacing.setter
    def Spacing(self, value: float) -> None:
        number = _real(value, "Spacing")
        if number < 0.0:
            raise ValueError(f"Spacing must not be negative, got {number}")
        self._spacing = number

    @property
    def UseKerning(self) -> bool:
        return self._use_kerning

    @UseKerning.setter
    def UseKerning(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("UseKerning must be a bool")
        self._use_kerning = value

    @property
    def Style(self) -> FontDescriptionStyle:
        return self._style

    @Style.setter
    def Style(self, value: FontDescriptionStyle) -> None:
        self._style = FontDescriptionStyle(value)

    @property
    def DefaultCharacter(self) -> str | None:
        return self._default_character

    @DefaultCharacter.setter
    def DefaultCharacter(self, value: str | None) -> None:
        if value is None:
            self._default_character = None
            return
        if not isinstance(value, str) or len(value) != 1:
            raise TypeError("DefaultCharacter must be a single character or None")
        self._default_character = value

    @property
    def Characters(self) -> set[str]:
        return self._characters


FontDescription.__xna_arities__ = {"__init__": {3, 4, 5}}


def _real(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{what} must be a real number, not {type(value).__name__}")
    return float(value)
