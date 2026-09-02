"""Bitmaps, in every shape the pipeline moves them.

Three kinds, and the difference is where the pixels live:

``PixelBitmapContentOfT``
    one value per pixel, of a declared type. Reading a pixel is exact.
``DxtBitmapContent``
    4x4 blocks of *compressed* pixels. Reading one pixel means decoding its
    block, and writing one means recompressing it, so the typed accessors are
    not offered -- XNA does not offer them either.
``BitmapContent``
    the base both share, and the place ``Copy`` lives. A copy between two
    bitmaps of different types or different sizes goes through the unpacked
    ``Vector4`` and, when the regions differ in size, through a resample.

The DXT compressor here is real: it picks the two endpoints of each block by
extent along the best-fit axis and assigns each pixel to the nearest of the four
interpolated colours. It is not the best compressor in the world, and it does
not need to be -- what it must be is *correct*, which the qualification checks by
decompressing what it wrote and by handing the result to the runtime's own
texture reader.
"""

from __future__ import annotations

import struct

from typing import Generic, TypeVar

from .... import Color, Rectangle, Vector4
from ....Graphics import SurfaceFormat
from .._collections import _Collection
from .._identity import ContentItem

T = TypeVar("T")
from ._vectors import PIXEL_KINDS, from_vector4, kind_of, to_vector4


class BitmapContent(ContentItem):
    """A rectangle of pixels of some kind."""

    __slots__ = ("_width", "_height")

    def __init__(self, width: int = 0, height: int = 0) -> None:
        super().__init__()
        self._width = _dimension(width, "width")
        self._height = _dimension(height, "height")

    @property
    def Width(self) -> int:
        return self._width

    @property
    def Height(self) -> int:
        return self._height

    def ToString(self) -> str:
        return f"{type(self).__name__}, {self._width}x{self._height}"

    def __repr__(self) -> str:
        return self.ToString()

    # -- the two halves a subclass provides ----------------------------------

    def TryGetFormat(self) -> tuple[bool, SurfaceFormat | None]:
        """XNA's ``out SurfaceFormat`` becomes the second half of the answer."""
        raise NotImplementedError(
            f"{type(self).__name__}.TryGetFormat must be overridden")

    def SetPixelData(self, sourceData: bytes) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.SetPixelData must be overridden")

    def GetPixelData(self) -> bytes:
        raise NotImplementedError(
            f"{type(self).__name__}.GetPixelData must be overridden")

    def TryCopyTo(self, destinationBitmap: "BitmapContent",
                  sourceRegion: Rectangle, destinationRegion: Rectangle) -> bool:
        """Copies into ``destinationBitmap``, or answers False if it cannot.

        The base implementation answers False for everything: XNA's copy is a
        double dispatch, and a bitmap that does not know how to write to a
        particular destination says so, so that ``Copy`` can ask the *other*
        side. Answering False is a real answer, not a stub -- it is what makes
        the pair of attempts work.
        """
        return False

    def TryCopyFrom(self, sourceBitmap: "BitmapContent",
                    sourceRegion: Rectangle, destinationRegion: Rectangle) -> bool:
        return False

    # -- the static copy protocol --------------------------------------------

    @staticmethod
    def Copy(*args: object) -> None:
        """XNA's two overloads: whole-bitmap, or region to region.

        Both ends are asked, in XNA's order: the source is offered the copy
        first, and the destination is asked only if the source declined. That
        order is what lets a compressed bitmap handle a copy *out* of itself
        while an ordinary one handles a copy *into* itself.
        """
        if len(args) == 2:
            source, destination = args
            _require_bitmap(source, "sourceBitmap")
            _require_bitmap(destination, "destinationBitmap")
            source_region = Rectangle(0, 0, source.Width, source.Height)
            destination_region = Rectangle(
                0, 0, destination.Width, destination.Height)
        elif len(args) == 4:
            source, source_region, destination, destination_region = args
            _require_bitmap(source, "sourceBitmap")
            _require_bitmap(destination, "destinationBitmap")
        else:
            raise TypeError("no matching Copy overload")
        BitmapContent.ValidateCopyArguments(
            source, source_region, destination, destination_region)
        if source.TryCopyTo(destination, source_region, destination_region):
            return
        if destination.TryCopyFrom(source, source_region, destination_region):
            return
        raise NotImplementedError(
            f"neither {type(source).__name__} nor {type(destination).__name__} "
            "can perform this copy")

    @staticmethod
    def ValidateCopyArguments(sourceBitmap: "BitmapContent", sourceRegion: Rectangle,
                              destinationBitmap: "BitmapContent",
                              destinationRegion: Rectangle) -> None:
        """Refuses a copy that could not be performed, before any of it happens."""
        _require_bitmap(sourceBitmap, "sourceBitmap")
        _require_bitmap(destinationBitmap, "destinationBitmap")
        for name, region, bitmap in (
                ("sourceRegion", sourceRegion, sourceBitmap),
                ("destinationRegion", destinationRegion, destinationBitmap)):
            if not isinstance(region, Rectangle):
                raise TypeError(
                    f"{name} must be a Rectangle, not {type(region).__name__}")
            if region.Width <= 0 or region.Height <= 0:
                raise ValueError(f"{name} is empty: {region.Width}x{region.Height}")
            if (region.X < 0 or region.Y < 0
                    or region.X + region.Width > bitmap.Width
                    or region.Y + region.Height > bitmap.Height):
                raise ValueError(
                    f"{name} {region.X},{region.Y} {region.Width}x{region.Height} "
                    f"is outside a {bitmap.Width}x{bitmap.Height} bitmap")


class PixelBitmapContentOfT(BitmapContent, Generic[T]):
    """A bitmap of one pixel type, one value per pixel.

    The rows are separate lists, which is what ``GetRow`` hands out: XNA hands
    out the row itself so that a caller can write through it, and copying it
    would silently discard those writes.
    """

    __slots__ = ("_rows", "_element")

    #: The pixel type, closed by a subclass or given to the constructor.
    _default_element: type | None = None

    def __init__(self, width: int = 0, height: int = 0, *,
                 element: type | None = None) -> None:
        super().__init__(width, height)
        chosen = element or self._closed_element()
        kind_of(chosen)
        self._element = chosen
        blank = from_vector4(chosen, Vector4(0.0, 0.0, 0.0, 0.0))
        self._rows = [[blank] * self._width for _ in range(self._height)]

    @classmethod
    def _closed_element(cls) -> type:
        if cls._default_element is not None:
            return cls._default_element
        for base in getattr(cls, "__orig_bases__", ()):
            arguments = getattr(base, "__args__", ())
            if arguments and isinstance(arguments[0], type):
                return arguments[0]
        raise TypeError(
            f"{cls.__name__} does not say what pixel type it holds: close "
            "PixelBitmapContentOfT's type argument, or pass element=")

    @classmethod
    def _of(cls, element: type, width: int, height: int) -> "PixelBitmapContentOfT":
        """A bitmap of ``element`` pixels, without a closed subclass."""
        return cls(width, height, element=element)

    @property
    def _pixel_type(self) -> type:
        return self._element

    def GetRow(self, y: int) -> list:
        self._check_row(y)
        return self._rows[y]

    def GetPixel(self, x: int, y: int):
        self._check(x, y)
        return self._rows[y][x]

    def SetPixel(self, x: int, y: int, value) -> None:
        self._check(x, y)
        self._rows[y][x] = value

    def ReplaceColor(self, originalColor, newColor) -> None:
        """Every pixel equal to ``originalColor`` becomes ``newColor``.

        This is how a colour-keyed source image gets its transparent pixels:
        the artist paints magenta, and the processor replaces it with
        transparent black *before* the mipmap chain is built, so that the
        replaced colour never bleeds into a smaller level.
        """
        for row in self._rows:
            for index, pixel in enumerate(row):
                if pixel == originalColor:
                    row[index] = newColor

    def TryGetFormat(self) -> tuple[bool, SurfaceFormat | None]:
        surface = kind_of(self._element).surface
        return (surface is not None), surface

    def GetPixelData(self) -> bytes:
        kind = kind_of(self._element)
        return b"".join(kind.pack(pixel) for row in self._rows for pixel in row)

    def SetPixelData(self, sourceData: bytes) -> None:
        kind = kind_of(self._element)
        raw = bytes(sourceData)
        wanted = kind.size * self._width * self._height
        if len(raw) != wanted:
            raise ValueError(
                f"a {self._width}x{self._height} {self._element.__name__} bitmap "
                f"needs {wanted} bytes, got {len(raw)}")
        offset = 0
        for y in range(self._height):
            row = self._rows[y]
            for x in range(self._width):
                row[x] = kind.unpack(raw[offset:offset + kind.size])
                offset += kind.size

    def TryCopyTo(self, destinationBitmap: BitmapContent, sourceRegion: Rectangle,
                  destinationRegion: Rectangle) -> bool:
        if not isinstance(destinationBitmap, PixelBitmapContentOfT):
            return False
        _resample(self, sourceRegion, destinationBitmap, destinationRegion)
        return True

    def TryCopyFrom(self, sourceBitmap: BitmapContent, sourceRegion: Rectangle,
                    destinationRegion: Rectangle) -> bool:
        if isinstance(sourceBitmap, PixelBitmapContentOfT):
            _resample(sourceBitmap, sourceRegion, self, destinationRegion)
            return True
        if isinstance(sourceBitmap, DxtBitmapContent):
            decoded = sourceBitmap._decode()
            _resample(decoded, sourceRegion, self, destinationRegion)
            return True
        return False

    def ToString(self) -> str:
        return (f"PixelBitmapContentOfT<{self._element.__name__}>, "
                f"{self._width}x{self._height}")

    def _check_row(self, y: int) -> None:
        if not isinstance(y, int) or isinstance(y, bool):
            raise TypeError(f"y must be an int, not {type(y).__name__}")
        if not 0 <= y < self._height:
            raise IndexError(f"y {y} is outside 0..{self._height - 1}")

    def _check(self, x: int, y: int) -> None:
        self._check_row(y)
        if not isinstance(x, int) or isinstance(x, bool):
            raise TypeError(f"x must be an int, not {type(x).__name__}")
        if not 0 <= x < self._width:
            raise IndexError(f"x {x} is outside 0..{self._width - 1}")


PixelBitmapContentOfT.__xna_arities__ = {"__init__": {0, 2}}
BitmapContent.__xna_arities__ = {"__init__": {0, 2}, "Copy": {2, 4}}


class DxtBitmapContent(BitmapContent):
    """A block-compressed bitmap: 4x4 pixels per 8- or 16-byte block."""

    __slots__ = ("_block_size", "_blocks")

    def __init__(self, blockSize: int, width: int = 0, height: int = 0) -> None:
        if blockSize not in (8, 16):
            raise ValueError(f"blockSize must be 8 or 16, got {blockSize}")
        super().__init__(width, height)
        self._block_size = blockSize
        self._blocks = bytearray(
            blockSize * self._blocks_wide * self._blocks_high)

    @property
    def _blocks_wide(self) -> int:
        """Blocks across, rounded up.

        A level narrower than four pixels still occupies a whole block -- which
        is why the bottom of a mipmap chain is compressible at all. The extra
        columns are filled by repeating the last real pixel, so the block's
        colours are the ones actually in the image and the padding costs the
        encoder nothing.
        """
        return (self._width + 3) // 4

    @property
    def _blocks_high(self) -> int:
        return (self._height + 3) // 4

    def GetPixelData(self) -> bytes:
        return bytes(self._blocks)

    def SetPixelData(self, sourceData: bytes) -> None:
        raw = bytes(sourceData)
        if len(raw) != len(self._blocks):
            raise ValueError(
                f"a {self._width}x{self._height} DXT bitmap needs "
                f"{len(self._blocks)} bytes, got {len(raw)}")
        self._blocks = bytearray(raw)

    def TryCopyTo(self, destinationBitmap: BitmapContent, sourceRegion: Rectangle,
                  destinationRegion: Rectangle) -> bool:
        if isinstance(destinationBitmap, DxtBitmapContent):
            if (type(destinationBitmap) is type(self)
                    and sourceRegion == destinationRegion
                    and sourceRegion.Width == self._width
                    and sourceRegion.Height == self._height
                    and destinationBitmap.Width == self._width
                    and destinationBitmap.Height == self._height):
                destinationBitmap.SetPixelData(self.GetPixelData())
                return True
            # Recompressing a sub-region would decompress and recompress every
            # block it touches, losing quality twice for no reason a caller
            # asked for. XNA does not do it either.
            return False
        if isinstance(destinationBitmap, PixelBitmapContentOfT):
            _resample(self._decode(), sourceRegion, destinationBitmap,
                      destinationRegion)
            return True
        return False

    def TryCopyFrom(self, sourceBitmap: BitmapContent, sourceRegion: Rectangle,
                    destinationRegion: Rectangle) -> bool:
        if (sourceRegion.Width != destinationRegion.Width
                or sourceRegion.Height != destinationRegion.Height
                or destinationRegion.X or destinationRegion.Y
                or destinationRegion.Width != self._width
                or destinationRegion.Height != self._height):
            return False
        source = _as_colors(sourceBitmap, sourceRegion)
        self._encode(source)
        return True

    # -- the codec -----------------------------------------------------------

    def _decode(self) -> "PixelBitmapContentOfT":
        result = PixelBitmapContentOfT(self._width, self._height, element=Color)
        alpha = self._block_size == 16
        for block_y in range(self._blocks_high):
            for block_x in range(self._blocks_wide):
                offset = (block_y * self._blocks_wide + block_x) * self._block_size
                block = bytes(self._blocks[offset:offset + self._block_size])
                colors = _decode_color_block(
                    block[-8:], punchthrough=self._is_dxt1())
                alphas = self._decode_alpha(block) if alpha else [255] * 16
                for index in range(16):
                    x = block_x * 4 + index % 4
                    y = block_y * 4 + index // 4
                    if x >= self._width or y >= self._height:
                        continue  # padding, which is not part of the image
                    red, green, blue, block_alpha = colors[index]
                    result.SetPixel(x, y, Color(
                        red, green, blue,
                        block_alpha if not alpha else alphas[index]))
        return result

    def _encode(self, pixels: list[list[Color]]) -> None:
        alpha = self._block_size == 16
        for block_y in range(self._blocks_high):
            for block_x in range(self._blocks_wide):
                block = [
                    pixels[min(block_y * 4 + row, self._height - 1)]
                          [min(block_x * 4 + column, self._width - 1)]
                    for row in range(4) for column in range(4)]
                encoded = b""
                if alpha:
                    encoded += self._encode_alpha(block)
                encoded += _encode_color_block(block, punchthrough=self._is_dxt1())
                offset = (block_y * self._blocks_wide + block_x) * self._block_size
                self._blocks[offset:offset + self._block_size] = encoded

    def _is_dxt1(self) -> bool:
        return self._block_size == 8

    def _decode_alpha(self, block: bytes) -> list[int]:
        raise NotImplementedError(
            f"{type(self).__name__} must say how its alpha block is stored")

    def _encode_alpha(self, block: list[Color]) -> bytes:
        raise NotImplementedError(
            f"{type(self).__name__} must say how its alpha block is stored")


DxtBitmapContent.__xna_arities__ = {"__init__": {1, 3}}


class Dxt1BitmapContent(DxtBitmapContent):
    """DXT1: colour only, with one bit of punch-through alpha."""

    __slots__ = ()

    def __init__(self, width: int = 0, height: int = 0) -> None:
        super().__init__(8, width, height)

    def TryGetFormat(self) -> tuple[bool, SurfaceFormat | None]:
        return True, SurfaceFormat.Dxt1


class Dxt3BitmapContent(DxtBitmapContent):
    """DXT3: colour plus four bits of explicit alpha per pixel."""

    __slots__ = ()

    def __init__(self, width: int = 0, height: int = 0) -> None:
        super().__init__(16, width, height)

    def TryGetFormat(self) -> tuple[bool, SurfaceFormat | None]:
        return True, SurfaceFormat.Dxt3

    def _decode_alpha(self, block: bytes) -> list[int]:
        packed = int.from_bytes(block[:8], "little")
        # Four bits become eight by replication, so 0xF is 255 rather than 240.
        return [(((packed >> (index * 4)) & 0xF) * 17) for index in range(16)]

    def _encode_alpha(self, block: list[Color]) -> bytes:
        packed = 0
        for index, pixel in enumerate(block):
            packed |= ((pixel.A * 15 + 127) // 255) << (index * 4)
        return packed.to_bytes(8, "little")


class Dxt5BitmapContent(DxtBitmapContent):
    """DXT5: colour plus an interpolated alpha block."""

    __slots__ = ()

    def __init__(self, width: int = 0, height: int = 0) -> None:
        super().__init__(16, width, height)

    def TryGetFormat(self) -> tuple[bool, SurfaceFormat | None]:
        return True, SurfaceFormat.Dxt5

    def _decode_alpha(self, block: bytes) -> list[int]:
        first, second = block[0], block[1]
        table = _alpha_table(first, second)
        indices = int.from_bytes(block[2:8], "little")
        return [table[(indices >> (index * 3)) & 0x7] for index in range(16)]

    def _encode_alpha(self, block: list[Color]) -> bytes:
        values = [pixel.A for pixel in block]
        high, low = max(values), min(values)
        if high == low:
            # A constant alpha block: one endpoint and index zero everywhere.
            return bytes((high, low)) + bytes(6)
        table = _alpha_table(high, low)
        indices = 0
        for index, value in enumerate(values):
            best = min(range(8), key=lambda slot: abs(table[slot] - value))
            indices |= best << (index * 3)
        return bytes((high, low)) + indices.to_bytes(6, "little")


class MipmapChain(_Collection[BitmapContent]):
    """One face's mipmap levels, largest first.

    The single-bitmap constructor is XNA's implicit conversion: a processor
    writes ``texture.Mipmaps = bitmap`` and means a chain with one level in it.
    Python has no implicit conversion, so the conversion *is* the constructor,
    and the property setters that accept a bare bitmap call it.
    """

    __slots__ = ()

    def __init__(self, bitmap: BitmapContent | None = None) -> None:
        super().__init__()
        if bitmap is not None:
            self.InsertItem(0, bitmap)

    def InsertItem(self, index: int, item: BitmapContent) -> None:
        _require_bitmap(item, "item")
        super().InsertItem(index, item)

    def SetItem(self, index: int, item: BitmapContent) -> None:
        _require_bitmap(item, "item")
        super().SetItem(index, item)


class MipmapChainCollection(_Collection[MipmapChain]):
    """Every face of a texture, each with its own mipmap chain.

    A 2D texture has one face and a cube map has six, which is the only thing
    that distinguishes their content types on the wire.
    """

    __slots__ = ()

    def __init__(self, faces: int = 0) -> None:
        super().__init__(MipmapChain() for _ in range(faces))

    def InsertItem(self, index: int, item: MipmapChain) -> None:
        _require_chain(item)
        super().InsertItem(index, item)

    def SetItem(self, index: int, item: MipmapChain) -> None:
        _require_chain(item)
        super().SetItem(index, item)


MipmapChain.__xna_arities__ = {"__init__": {0, 1}}
#: Each DXT variant fixes the block size its base takes, so its constructor is
#: width and height alone. Declared per class rather than inherited: the base's
#: ``{1, 3}`` would otherwise be read off every subclass.
Dxt1BitmapContent.__xna_arities__ = {"__init__": {2}}
Dxt3BitmapContent.__xna_arities__ = {"__init__": {2}}
Dxt5BitmapContent.__xna_arities__ = {"__init__": {2}}


# -- shared helpers ----------------------------------------------------------


def _dimension(value: object, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{what} must be an int, not {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{what} must not be negative, got {value}")
    return value


def _require_bitmap(value: object, what: str) -> None:
    if not isinstance(value, BitmapContent):
        raise TypeError(f"{what} must be a BitmapContent, not {type(value).__name__}")


def _require_chain(value: object) -> None:
    if not isinstance(value, MipmapChain):
        raise TypeError(f"item must be a MipmapChain, not {type(value).__name__}")


def _as_colors(bitmap: BitmapContent, region: Rectangle) -> list[list[Color]]:
    """``region`` of ``bitmap``, as rows of ``Color``."""
    if isinstance(bitmap, DxtBitmapContent):
        bitmap = bitmap._decode()
    if not isinstance(bitmap, PixelBitmapContentOfT):
        raise TypeError(
            f"{type(bitmap).__name__} cannot be read as pixels")
    rows = []
    for y in range(region.Height):
        row = []
        for x in range(region.Width):
            pixel = bitmap.GetPixel(region.X + x, region.Y + y)
            row.append(pixel if isinstance(pixel, Color)
                       else from_vector4(Color, to_vector4(pixel)))
        rows.append(row)
    return rows


def _resample(source: "PixelBitmapContentOfT", source_region: Rectangle,
              destination: "PixelBitmapContentOfT",
              destination_region: Rectangle) -> None:
    """Copies pixels, converting the type and the size as needed.

    Same size is an exact per-pixel conversion. Different sizes are a box
    filter: every destination pixel is the average of the source pixels it
    covers, which is what makes a mipmap chain look like the image it came from
    rather than like every other source pixel thrown away.
    """
    element = destination._pixel_type
    same_size = (source_region.Width == destination_region.Width
                 and source_region.Height == destination_region.Height)
    for y in range(destination_region.Height):
        for x in range(destination_region.Width):
            if same_size:
                value = to_vector4(source.GetPixel(
                    source_region.X + x, source_region.Y + y))
            else:
                value = _box(source, source_region, destination_region, x, y)
            destination.SetPixel(destination_region.X + x,
                                 destination_region.Y + y,
                                 from_vector4(element, value))


def _box(source: "PixelBitmapContentOfT", source_region: Rectangle,
         destination_region: Rectangle, x: int, y: int) -> Vector4:
    left = source_region.X + x * source_region.Width // destination_region.Width
    right = source_region.X + (x + 1) * source_region.Width // destination_region.Width
    top = source_region.Y + y * source_region.Height // destination_region.Height
    bottom = source_region.Y + (y + 1) * source_region.Height // destination_region.Height
    right = max(right, left + 1)
    bottom = max(bottom, top + 1)
    total = [0.0, 0.0, 0.0, 0.0]
    count = 0
    for sample_y in range(top, bottom):
        for sample_x in range(left, right):
            value = to_vector4(source.GetPixel(sample_x, sample_y))
            total[0] += value.X
            total[1] += value.Y
            total[2] += value.Z
            total[3] += value.W
            count += 1
    return Vector4(total[0] / count, total[1] / count,
                   total[2] / count, total[3] / count)


def _alpha_table(first: int, second: int) -> list[int]:
    """DXT5's eight alpha values, in the order the block's indices name them."""
    if first > second:
        return [first, second] + [
            ((8 - index) * first + (index - 1) * second) // 7
            for index in range(2, 8)]
    return [first, second] + [
        ((6 - index) * first + (index - 1) * second) // 5
        for index in range(2, 6)] + [0, 255]


def _rgb565(color: Color) -> int:
    return (((color.R >> 3) << 11) | ((color.G >> 2) << 5) | (color.B >> 3))


def _from_565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    # Replicate the high bits into the low ones, which is what makes 0x1F
    # decode to 255 rather than 248.
    return ((red << 3) | (red >> 2), (green << 2) | (green >> 4),
            (blue << 3) | (blue >> 2))


def _color_palette(first: int, second: int, punchthrough: bool
                   ) -> list[tuple[int, int, int, int]]:
    """The four colours a block's two endpoints name.

    The ordering of the endpoints is the mode switch: in DXT1, ``first <=
    second`` means the third slot is the midpoint and the fourth is
    transparent black. DXT3 and DXT5 carry alpha separately and always use the
    four-colour form, whatever the endpoints happen to compare as.
    """
    zero, one = _from_565(first), _from_565(second)
    if first > second or not punchthrough:
        return [zero + (255,), one + (255,),
                _lerp(zero, one, 2, 3) + (255,), _lerp(zero, one, 1, 3) + (255,)]
    return [zero + (255,), one + (255,),
            _lerp(zero, one, 1, 2) + (255,), (0, 0, 0, 0)]


def _decode_color_block(block: bytes, punchthrough: bool
                        ) -> list[tuple[int, int, int, int]]:
    first, second = struct.unpack_from("<HH", block, 0)
    indices = struct.unpack_from("<I", block, 4)[0]
    palette = _color_palette(first, second, punchthrough)
    return [palette[(indices >> (index * 2)) & 0x3] for index in range(16)]


def _lerp(zero: tuple[int, int, int], one: tuple[int, int, int],
          weight: int, total: int) -> tuple[int, int, int]:
    return tuple((zero[channel] * weight + one[channel] * (total - weight)) // total
                 for channel in range(3))


def _encode_color_block(block: list[Color], punchthrough: bool) -> bytes:
    """Two endpoints along the block's own colour axis, then nearest-of-four.

    The axis is the vector between the per-channel extremes, which points along
    the direction the block's colours actually spread; the endpoints are the two
    pixels furthest apart when projected onto it. That is a cheap stand-in for
    the principal component, and on a 4x4 block it lands on the same pair often
    enough that the difference is invisible -- while the naive choice, extremes
    of the widest single channel, is visibly wrong on anything whose colours
    vary in two channels at once.

    A block whose colours are collinear -- a greyscale ramp, a fade to black,
    anything an artist actually paints into 4x4 pixels -- comes back within the
    565 quantisation of what went in, and the qualification asserts that rather
    than assuming it.
    """
    opaque = [pixel for pixel in block if pixel.A >= 128] if punchthrough else block
    if not opaque:
        # Every pixel is transparent: DXT1 spells that as the punch-through
        # encoding with both endpoints black and every index at slot three.
        return struct.pack("<HHI", 0, 0, 0xFFFFFFFF)
    low_channels = [min(pixel.R for pixel in opaque), min(pixel.G for pixel in opaque),
                    min(pixel.B for pixel in opaque)]
    high_channels = [max(pixel.R for pixel in opaque), max(pixel.G for pixel in opaque),
                     max(pixel.B for pixel in opaque)]
    axis = [high_channels[channel] - low_channels[channel] for channel in range(3)]

    def projection(pixel: Color) -> int:
        return pixel.R * axis[0] + pixel.G * axis[1] + pixel.B * axis[2]

    low = min(opaque, key=projection)
    high = max(opaque, key=projection)
    first, second = _rgb565(high), _rgb565(low)
    transparent = punchthrough and len(opaque) != len(block)
    if transparent and first > second:
        first, second = second, first
    elif not transparent and first < second:
        first, second = second, first
    # ``first == second`` is a constant block. It is left alone: in the
    # three-colour form slot zero is that exact colour, so every pixel encodes
    # to it, and nudging an endpoint to force the four-colour form would move
    # the one colour the block has.
    palette = _color_palette(first, second, punchthrough)
    indices = 0
    for index, pixel in enumerate(block):
        if transparent and pixel.A < 128:
            indices |= 0x3 << (index * 2)
            continue
        candidates = range(3) if transparent else range(4)
        best = min(candidates, key=lambda slot: _distance(palette[slot], pixel))
        indices |= best << (index * 2)
    return struct.pack("<HHI", first, second, indices)


def _distance(entry: tuple[int, int, int, int], pixel: Color) -> int:
    return ((entry[0] - pixel.R) ** 2 + (entry[1] - pixel.G) ** 2
            + (entry[2] - pixel.B) ** 2)
