"""Image decoders, in the four formats a content project actually holds.

Written here rather than reached for, because a content pipeline that needs a
third-party imaging library to open a ``.png`` is a content pipeline that cannot
run where the rest of this package runs. Every decoder is exact: nothing is
resampled, no channel is dropped, and a format this cannot read says so instead
of returning something plausible.

``.dds`` is the interesting one: its surfaces may already be DXT-compressed, and
they are kept that way. Decompressing an artist's DXT file to inspect it and
recompressing it later would lose a generation of quality for nothing, so a
compressed ``.dds`` arrives as the ``DxtBitmapContent`` it already is.

The decoders answer ``(width, height, rows_of_Color)`` or, for a compressed
``.dds``, the compressed blocks and which DXT variant they are.
"""

from __future__ import annotations

import struct
import zlib

from ... import Color

#: What a ``.dds`` says its surface is, by four-character code.
DXT_CODES = {b"DXT1": 1, b"DXT3": 3, b"DXT5": 5}


class UnsupportedImage(ValueError):
    """Raised with the exact reason a file could not be decoded."""


def detect(raw: bytes) -> str:
    """Which of the four formats ``raw`` is, by signature rather than by name."""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:2] == b"BM":
        return "bmp"
    if raw[:4] == b"DDS ":
        return "dds"
    if len(raw) >= 18 and raw[1] in (0, 1) and raw[2] in (1, 2, 3, 9, 10, 11):
        # TGA has no signature; the header's colour-map and image types are the
        # only things that can be checked, and they are checked strictly.
        return "tga"
    raise UnsupportedImage(
        "the file is not a PNG, BMP, TGA or DDS: its first bytes are "
        f"{raw[:8]!r}")


def decode(raw: bytes) -> tuple[int, int, list[list[Color]]]:
    """One image, as rows of ``Color``."""
    kind = detect(raw)
    if kind == "png":
        return _png(raw)
    if kind == "bmp":
        return _bmp(raw)
    if kind == "tga":
        return _tga(raw)
    width, height, rows, compressed = _dds(raw)
    if compressed is not None:
        raise UnsupportedImage(
            "this DDS holds compressed surfaces; read it with decode_dds")
    return width, height, rows


def decode_dds(raw: bytes):
    """A ``.dds``, keeping compressed surfaces compressed.

    Answers ``(width, height, rows, compressed)`` where exactly one of ``rows``
    and ``compressed`` is not ``None``; ``compressed`` is ``(variant, blocks)``.
    """
    return _dds(raw)


# -- PNG ----------------------------------------------------------------------


def _png(raw: bytes) -> tuple[int, int, list[list[Color]]]:
    position = 8
    header: tuple | None = None
    palette: list[Color] = []
    transparency: bytes = b""
    data = bytearray()
    while position + 8 <= len(raw):
        length, kind = struct.unpack_from(">I4s", raw, position)
        body = raw[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = [Color(body[index], body[index + 1], body[index + 2], 255)
                       for index in range(0, len(body), 3)]
        elif kind == b"tRNS":
            transparency = body
        elif kind == b"IDAT":
            data.extend(body)
        elif kind == b"IEND":
            break
        position += 12 + length
    if header is None:
        raise UnsupportedImage("the PNG has no IHDR chunk")
    width, height, depth, colour, compression, filtering, interlace = header
    if depth != 8:
        raise UnsupportedImage(
            f"{depth}-bit PNG samples are not decoded here; 8-bit are")
    if compression != 0 or filtering != 0:
        raise UnsupportedImage(
            "the PNG uses a compression or filter method the format does not "
            "define")
    if interlace != 0:
        raise UnsupportedImage(
            "interlaced (Adam7) PNG is not decoded here; save it "
            "non-interlaced")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if channels is None:
        raise UnsupportedImage(f"PNG colour type {colour} is not one the format defines")
    if colour == 3 and not palette:
        raise UnsupportedImage("the PNG is palettized and has no PLTE chunk")
    raw_rows = _unfilter(zlib.decompress(bytes(data)), width, height, channels)
    rows: list[list[Color]] = []
    for line in raw_rows:
        row: list[Color] = []
        for x in range(width):
            offset = x * channels
            if colour == 0:
                grey = line[offset]
                row.append(Color(grey, grey, grey, 255))
            elif colour == 2:
                row.append(Color(line[offset], line[offset + 1],
                                 line[offset + 2], 255))
            elif colour == 3:
                index = line[offset]
                entry = palette[index]
                alpha = transparency[index] if index < len(transparency) else 255
                row.append(Color(entry.R, entry.G, entry.B, alpha))
            elif colour == 4:
                grey = line[offset]
                row.append(Color(grey, grey, grey, line[offset + 1]))
            else:
                row.append(Color(line[offset], line[offset + 1],
                                 line[offset + 2], line[offset + 3]))
        rows.append(row)
    return width, height, rows


def _unfilter(data: bytes, width: int, height: int, channels: int) -> list[bytes]:
    """PNG's five per-row filters, undone.

    Each row names its own filter and every filter refers to the row above and
    the pixel to the left, so this has to run in order and cannot be done a row
    at a time in isolation.
    """
    stride = width * channels
    rows: list[bytearray] = []
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        if position >= len(data):
            raise UnsupportedImage("the PNG's pixel data ends early")
        method = data[position]
        line = bytearray(data[position + 1:position + 1 + stride])
        if len(line) != stride:
            raise UnsupportedImage("the PNG's pixel data ends early")
        position += 1 + stride
        if method == 1:
            for index in range(channels, stride):
                line[index] = (line[index] + line[index - channels]) & 0xFF
        elif method == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif method == 3:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif method == 4:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                upper_left = previous[index - channels] if index >= channels else 0
                line[index] = (line[index]
                               + _paeth(left, previous[index], upper_left)) & 0xFF
        elif method != 0:
            raise UnsupportedImage(f"PNG filter {method} is not one of the five")
        rows.append(line)
        previous = line
    return [bytes(row) for row in rows]


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_corner = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_corner:
        return left
    return above if distance_above <= distance_corner else upper_left


# -- BMP ----------------------------------------------------------------------


def _bmp(raw: bytes) -> tuple[int, int, list[list[Color]]]:
    offset = struct.unpack_from("<I", raw, 10)[0]
    header_size = struct.unpack_from("<I", raw, 14)[0]
    if header_size < 40:
        raise UnsupportedImage(
            f"a {header_size}-byte BMP header is older than BITMAPINFOHEADER")
    width, height, planes, bits = struct.unpack_from("<iiHH", raw, 18)
    compression = struct.unpack_from("<I", raw, 30)[0]
    if compression != 0:
        raise UnsupportedImage(
            f"BMP compression {compression} is not decoded here; save it "
            "uncompressed")
    if bits not in (24, 32):
        raise UnsupportedImage(
            f"{bits}-bit BMP is not decoded here; 24- and 32-bit are")
    top_down = height < 0
    height = abs(height)
    stride = ((width * bits // 8) + 3) & ~3
    rows: list[list[Color]] = []
    for y in range(height):
        source = y if top_down else height - 1 - y
        start = offset + source * stride
        row: list[Color] = []
        for x in range(width):
            pixel = start + x * (bits // 8)
            blue, green, red = raw[pixel], raw[pixel + 1], raw[pixel + 2]
            alpha = raw[pixel + 3] if bits == 32 else 255
            row.append(Color(red, green, blue, alpha))
        rows.append(row)
    return width, height, rows


# -- TGA ----------------------------------------------------------------------


def _tga(raw: bytes) -> tuple[int, int, list[list[Color]]]:
    identity_length = raw[0]
    image_type = raw[2]
    width, height, bits, descriptor = struct.unpack_from("<HHBB", raw, 12)
    if image_type not in (2, 10):
        raise UnsupportedImage(
            f"TGA image type {image_type} is not decoded here; true-colour "
            "(2) and RLE true-colour (10) are")
    if bits not in (24, 32):
        raise UnsupportedImage(
            f"{bits}-bit TGA is not decoded here; 24- and 32-bit are")
    position = 18 + identity_length
    depth = bits // 8
    total = width * height
    pixels: list[Color] = []
    if image_type == 2:
        for index in range(total):
            pixels.append(_tga_pixel(raw, position + index * depth, depth))
        position += total * depth
    else:
        while len(pixels) < total:
            packet = raw[position]
            position += 1
            count = (packet & 0x7F) + 1
            if packet & 0x80:
                pixel = _tga_pixel(raw, position, depth)
                position += depth
                pixels.extend([pixel] * count)
            else:
                for index in range(count):
                    pixels.append(_tga_pixel(raw, position + index * depth, depth))
                position += count * depth
    rows = [pixels[y * width:(y + 1) * width] for y in range(height)]
    # Bit 5 of the descriptor is set when the first row stored is the top one.
    if not descriptor & 0x20:
        rows.reverse()
    return width, height, rows


def _tga_pixel(raw: bytes, offset: int, depth: int) -> Color:
    blue, green, red = raw[offset], raw[offset + 1], raw[offset + 2]
    alpha = raw[offset + 3] if depth == 4 else 255
    return Color(red, green, blue, alpha)


# -- DDS ----------------------------------------------------------------------


def _dds(raw: bytes):
    height, width = struct.unpack_from("<II", raw, 12)
    pixel_flags = struct.unpack_from("<I", raw, 80)[0]
    four_cc = raw[84:88]
    offset = 128
    if pixel_flags & 0x4:  # DDPF_FOURCC
        variant = DXT_CODES.get(four_cc)
        if variant is None:
            raise UnsupportedImage(
                f"DDS four-CC {four_cc!r} is not DXT1, DXT3 or DXT5")
        block = 8 if variant == 1 else 16
        blocks = ((width + 3) // 4) * ((height + 3) // 4) * block
        return width, height, None, (variant, raw[offset:offset + blocks])
    bits = struct.unpack_from("<I", raw, 88)[0]
    if bits not in (24, 32):
        raise UnsupportedImage(
            f"{bits}-bit uncompressed DDS is not decoded here; 24- and 32-bit are")
    masks = struct.unpack_from("<IIII", raw, 92)
    depth = bits // 8
    rows: list[list[Color]] = []
    for y in range(height):
        row: list[Color] = []
        for x in range(width):
            start = offset + (y * width + x) * depth
            value = int.from_bytes(raw[start:start + depth], "little")
            row.append(Color(_channel(value, masks[0]), _channel(value, masks[1]),
                             _channel(value, masks[2]),
                             _channel(value, masks[3]) if masks[3] else 255))
        rows.append(row)
    return width, height, rows, None


def _channel(value: int, mask: int) -> int:
    if not mask:
        return 0
    shift = (mask & -mask).bit_length() - 1
    width = bin(mask >> shift).count("1")
    raw_value = (value & mask) >> shift
    if width == 8:
        return raw_value
    # Scale to eight bits by replication rather than by shifting, so that a
    # full-scale value stays full-scale.
    return (raw_value * 255) // ((1 << width) - 1)
