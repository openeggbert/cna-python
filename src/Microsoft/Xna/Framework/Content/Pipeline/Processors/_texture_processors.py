"""The processors that turn imported images into textures a runtime can load.

``TextureProcessor`` is the general one and the other two are it with different
defaults: a sprite is not mipmapped and not resized, and a model's texture is.
XNA spells that by overriding the properties and hiding the setters, and so does
this -- a caller who sets ``GenerateMipmaps`` on a ``SpriteTextureProcessor``
has misunderstood something, and the type saying so is better than the setting
being quietly ignored.

The order of operations is the part that matters and it is not arbitrary:

1. **Colour-key** first, while the image is still at its authored resolution.
   Replacing the key colour after a resize would leave a halo of colours that
   are nearly the key and no longer equal to it.
2. **Premultiply alpha**, before anything that averages pixels. Averaging
   straight-alpha pixels pulls the colour of a fully transparent neighbour into
   the result, which is the dark fringe every un-premultiplied sprite sheet
   has around its edges. Both the resize and the mipmaps average, so this comes
   before both of them.
3. **Resize** to a power of two, if asked.
4. **Mipmaps**.
5. **Compress**, last, because every step above needs to read pixels.
"""

from __future__ import annotations

from .... import Color
from .._attributes import ContentProcessorAttribute
from .._components import ContentProcessorOfT
from .._context import ContentProcessorContext
from ..Graphics import (
    BitmapContent, Dxt1BitmapContent, Dxt5BitmapContent, PixelBitmapContentOfT,
    TextureContent,
)
from ..Graphics._vectors import to_vector4
from ._enums import TextureProcessorOutputFormat


class _ColorBitmapContent(PixelBitmapContentOfT):
    """The uncompressed working format every step above reads and writes."""

    __slots__ = ()
    _default_element = Color


@ContentProcessorAttribute(DisplayName="Texture - XNA Framework")
class TextureProcessor(ContentProcessorOfT[TextureContent, TextureContent]):
    """Colour-keys, resizes, premultiplies, mipmaps and compresses a texture."""

    __slots__ = ("_generate_mipmaps", "_texture_format", "_color_key_enabled",
                 "_color_key_color", "_resize_to_power_of_two",
                 "_premultiply_alpha")

    def __init__(self) -> None:
        self._generate_mipmaps = False
        self._texture_format = TextureProcessorOutputFormat.Color
        self._color_key_enabled = True
        #: XNA's default key is full-alpha magenta, which is the colour artists
        #: have used to mean "transparent" since long before XNA.
        self._color_key_color = Color(255, 0, 255, 255)
        self._resize_to_power_of_two = False
        self._premultiply_alpha = True

    @property
    def GenerateMipmaps(self) -> bool:
        return self._generate_mipmaps

    @GenerateMipmaps.setter
    def GenerateMipmaps(self, value: bool) -> None:
        self._generate_mipmaps = _flag(value, "GenerateMipmaps")

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return self._texture_format

    @TextureFormat.setter
    def TextureFormat(self, value: TextureProcessorOutputFormat) -> None:
        self._texture_format = TextureProcessorOutputFormat(value)

    @property
    def ColorKeyEnabled(self) -> bool:
        return self._color_key_enabled

    @ColorKeyEnabled.setter
    def ColorKeyEnabled(self, value: bool) -> None:
        self._color_key_enabled = _flag(value, "ColorKeyEnabled")

    @property
    def ColorKeyColor(self) -> Color:
        return self._color_key_color

    @ColorKeyColor.setter
    def ColorKeyColor(self, value: Color) -> None:
        if not isinstance(value, Color):
            raise TypeError(
                f"ColorKeyColor must be a Color, not {type(value).__name__}")
        self._color_key_color = value

    @property
    def ResizeToPowerOfTwo(self) -> bool:
        return self._resize_to_power_of_two

    @ResizeToPowerOfTwo.setter
    def ResizeToPowerOfTwo(self, value: bool) -> None:
        self._resize_to_power_of_two = _flag(value, "ResizeToPowerOfTwo")

    @property
    def PremultiplyAlpha(self) -> bool:
        return self._premultiply_alpha

    @PremultiplyAlpha.setter
    def PremultiplyAlpha(self, value: bool) -> None:
        self._premultiply_alpha = _flag(value, "PremultiplyAlpha")

    def Process(self, input: TextureContent,
                context: ContentProcessorContext) -> TextureContent:
        if not isinstance(input, TextureContent):
            raise TypeError(
                f"input must be a TextureContent, not {type(input).__name__}")
        input.ConvertBitmapType(_ColorBitmapContent)
        if self.ColorKeyEnabled:
            _replace_key(input, self.ColorKeyColor)
        if self.PremultiplyAlpha:
            _premultiply(input)
        if self.ResizeToPowerOfTwo:
            _resize_to_power_of_two(input)
        if self.GenerateMipmaps:
            input.GenerateMipmaps(False)
        if self.TextureFormat is TextureProcessorOutputFormat.DxtCompressed:
            input.ConvertBitmapType(
                Dxt5BitmapContent if _has_alpha(input) else Dxt1BitmapContent)
        return input


@ContentProcessorAttribute(DisplayName="Sprite - XNA Framework")
class SpriteTextureProcessor(TextureProcessor):
    """A texture for a ``SpriteBatch``: no mipmaps, no resize, exact pixels.

    Every knob a sprite must not have is read-only here, and reads the value a
    sprite requires. XNA does the same, for the same reason: a sprite sheet
    resized to a power of two has every glyph in the wrong place, and one that
    was mipmapped has neighbouring sprites bleeding into each other at distance.
    """

    __slots__ = ()

    @property
    def ColorKeyEnabled(self) -> bool:
        return True

    @property
    def ColorKeyColor(self) -> Color:
        return Color(255, 0, 255, 255)

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return TextureProcessorOutputFormat.Color

    @property
    def GenerateMipmaps(self) -> bool:
        return False

    @property
    def ResizeToPowerOfTwo(self) -> bool:
        return False


@ContentProcessorAttribute(DisplayName="Model Texture - XNA Framework")
class ModelTextureProcessor(TextureProcessor):
    """A texture for a model: mipmapped, resized, compressed."""

    __slots__ = ()

    @property
    def ColorKeyEnabled(self) -> bool:
        return False

    @property
    def ColorKeyColor(self) -> Color:
        return Color(255, 0, 255, 255)

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return TextureProcessorOutputFormat.DxtCompressed

    @property
    def GenerateMipmaps(self) -> bool:
        return True

    @property
    def ResizeToPowerOfTwo(self) -> bool:
        return True


def _flag(value: object, what: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{what} must be a bool")
    return value


def _each_bitmap(texture: TextureContent):
    for chain in texture.Faces:
        for index in range(chain.Count):
            yield chain, index, chain[index]


def _replace_key(texture: TextureContent, key: Color) -> None:
    """Every pixel equal to the key becomes transparent black.

    Transparent *black*, not transparent magenta: a filtered sample that mixes
    a key pixel with its neighbour would otherwise pull magenta into the result
    even at zero alpha, which is the fringe every sprite sheet used to have.
    """
    clear = Color(0, 0, 0, 0)
    for _chain, _index, bitmap in _each_bitmap(texture):
        bitmap.ReplaceColor(key, clear)


def _premultiply(texture: TextureContent) -> None:
    for _chain, _index, bitmap in _each_bitmap(texture):
        for y in range(bitmap.Height):
            row = bitmap.GetRow(y)
            for x, pixel in enumerate(row):
                alpha = pixel.A
                if alpha == 255:
                    continue
                row[x] = Color((pixel.R * alpha + 127) // 255,
                               (pixel.G * alpha + 127) // 255,
                               (pixel.B * alpha + 127) // 255, alpha)


def _has_alpha(texture: TextureContent) -> bool:
    for _chain, _index, bitmap in _each_bitmap(texture):
        for y in range(bitmap.Height):
            if any(pixel.A != 255 for pixel in bitmap.GetRow(y)):
                return True
    return False


def _resize_to_power_of_two(texture: TextureContent) -> None:
    from .... import Rectangle

    for chain, index, bitmap in list(_each_bitmap(texture)):
        width, height = _round_up(bitmap.Width), _round_up(bitmap.Height)
        if (width, height) == (bitmap.Width, bitmap.Height):
            continue
        resized = _ColorBitmapContent(width, height)
        BitmapContent.Copy(bitmap, Rectangle(0, 0, bitmap.Width, bitmap.Height),
                           resized, Rectangle(0, 0, width, height))
        resized.Name = bitmap.Name
        resized.Identity = bitmap.Identity
        chain.SetItem(index, resized)


def _round_up(value: int) -> int:
    result = 1
    while result < value:
        result *= 2
    return result
