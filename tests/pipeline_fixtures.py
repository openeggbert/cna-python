"""Fixtures for the content-pipeline tests.

Every fixture is **built here**, in code, from bytes this file writes. No image,
font, model or sound file is checked in and none is downloaded: a PNG is
assembled chunk by chunk, a ``.x`` model is written as text, a WAV is a RIFF
header and a sine wave. That is what makes the fixtures repository-authored, and
it is also what makes them exact -- a test that asserts a decoded pixel knows
what pixel was encoded because it encoded it.

The content pipeline needs no CNA library, so almost everything here runs
anywhere Python does. The exceptions are the cases that hand a built ``.xnb`` to
a *runtime* type -- a ``Texture2D`` needs a graphics device -- and they say so.
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from Microsoft.Xna.Framework import Color

from .device_fixtures import IDENTITY, NATIVE, RENDERS  # noqa: F401

requires_native = unittest.skipUnless(NATIVE, "needs a configured CNA library")
requires_renderer = unittest.skipUnless(
    NATIVE and RENDERS, "needs a rasterizing renderer")


class TemporaryContent(unittest.TestCase):
    """A test case with a scratch directory and a title root pointed at it."""

    def setUp(self) -> None:
        super().setUp()
        self._directory = tempfile.TemporaryDirectory(prefix="cna-pipeline-")
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        (self.root / "content").mkdir()

    def path(self, name: str) -> str:
        return os.fspath(self.root / name)

    def use_as_title_root(self) -> None:
        """Points ``TitleContainer`` at the scratch directory, and back again."""
        from Microsoft.Xna.Framework._title import _set_title_root_for_tests

        _set_title_root_for_tests(self.root)
        self.addCleanup(_set_title_root_for_tests, None)


# -- image fixtures -----------------------------------------------------------


def checkerboard(width: int, height: int) -> list[list[Color]]:
    """A non-symmetric pattern: no row equals another and no channel repeats.

    Deliberately not a checkerboard of two colours -- a decoder that transposed
    the image, swapped two channels or flipped it vertically would still produce
    a checkerboard. Every pixel here is distinct in every channel.
    """
    return [[Color((x * 17 + 3) & 0xFF, (y * 29 + 7) & 0xFF,
                   (x * 5 + y * 11 + 1) & 0xFF,
                   255 if (x + y) % 3 else 128)
             for x in range(width)] for y in range(height)]


def png_bytes(rows: list[list[Color]], *, filter_type: int = 0,
              colour_type: int = 6) -> bytes:
    """An 8-bit PNG carrying ``rows``, written with one filter throughout."""
    height = len(rows)
    width = len(rows[0])
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]

    def sample(pixel: Color) -> bytes:
        if colour_type == 0:
            return bytes((pixel.R,))
        if colour_type == 2:
            return bytes((pixel.R, pixel.G, pixel.B))
        if colour_type == 4:
            return bytes((pixel.R, pixel.A))
        return bytes((pixel.R, pixel.G, pixel.B, pixel.A))

    raw = bytearray()
    previous = bytearray(width * channels)
    for row in rows:
        line = bytearray(b"".join(sample(pixel) for pixel in row))
        encoded = bytearray()
        for index, value in enumerate(line):
            left = line[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                encoded.append(value)
            elif filter_type == 1:
                encoded.append((value - left) & 0xFF)
            elif filter_type == 2:
                encoded.append((value - above) & 0xFF)
            elif filter_type == 3:
                encoded.append((value - ((left + above) >> 1)) & 0xFF)
            else:
                encoded.append((value - _paeth(left, above, upper_left)) & 0xFF)
        raw += bytes((filter_type,)) + encoded
        previous = line
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
                                          colour_type, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw)))
            + _chunk(b"IEND", b""))


def _chunk(kind: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body)))


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (abs(estimate - left), abs(estimate - above),
                 abs(estimate - upper_left))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    return above if distances[1] <= distances[2] else upper_left


def bmp_bytes(rows: list[list[Color]], *, top_down: bool = False) -> bytes:
    """A 32-bit uncompressed BMP, bottom-up unless told otherwise."""
    height = len(rows)
    width = len(rows[0])
    ordered = rows if top_down else list(reversed(rows))
    body = b"".join(bytes((pixel.B, pixel.G, pixel.R, pixel.A))
                    for row in ordered for pixel in row)
    header = struct.pack("<IiiHHIIiiII", 40, width,
                         -height if top_down else height, 1, 32, 0, len(body),
                         2835, 2835, 0, 0)
    return (b"BM" + struct.pack("<IHHI", 14 + len(header) + len(body), 0, 0,
                                14 + len(header)) + header + body)


def tga_bytes(rows: list[list[Color]], *, run_length: bool = False) -> bytes:
    """A 32-bit TGA, stored top-down, optionally run-length encoded."""
    height = len(rows)
    width = len(rows[0])
    header = bytes((0, 0, 10 if run_length else 2, 0, 0, 0, 0, 0, 0, 0, 0, 0)) \
        + struct.pack("<HHBB", width, height, 32, 0x20)
    if not run_length:
        return header + b"".join(
            bytes((pixel.B, pixel.G, pixel.R, pixel.A))
            for row in rows for pixel in row)
    body = bytearray()
    pixels = [pixel for row in rows for pixel in row]
    index = 0
    while index < len(pixels):
        run = 1
        while (run < 128 and index + run < len(pixels)
               and pixels[index + run] == pixels[index]):
            run += 1
        if run > 1:
            body.append(0x80 | (run - 1))
            pixel = pixels[index]
            body += bytes((pixel.B, pixel.G, pixel.R, pixel.A))
            index += run
        else:
            literal = 1
            while (literal < 128 and index + literal < len(pixels)
                   and pixels[index + literal] != pixels[index + literal - 1]):
                literal += 1
            body.append(literal - 1)
            for pixel in pixels[index:index + literal]:
                body += bytes((pixel.B, pixel.G, pixel.R, pixel.A))
            index += literal
    return header + bytes(body)


def dds_bytes(rows: list[list[Color]]) -> bytes:
    """A 32-bit uncompressed DDS with explicit A8R8G8B8 masks."""
    height = len(rows)
    width = len(rows[0])
    header = bytearray(124)
    struct.pack_into("<IIII", header, 0, 124, 0x1007, height, width)
    struct.pack_into("<I", header, 72, 32)          # pixel-format size
    struct.pack_into("<I", header, 76, 0x41)        # RGB | ALPHAPIXELS
    struct.pack_into("<I", header, 84, 32)          # bits per pixel
    struct.pack_into("<IIII", header, 88, 0x00FF0000, 0x0000FF00, 0x000000FF,
                     0xFF000000)
    body = b"".join(bytes((pixel.B, pixel.G, pixel.R, pixel.A))
                    for row in rows for pixel in row)
    return b"DDS " + bytes(header) + body


def dxt_dds_bytes(width: int, height: int, blocks: bytes, code: bytes) -> bytes:
    """A DDS whose surface is already DXT-compressed."""
    header = bytearray(124)
    struct.pack_into("<IIII", header, 0, 124, 0x1007, height, width)
    struct.pack_into("<I", header, 72, 32)
    struct.pack_into("<I", header, 76, 0x4)         # FOURCC
    header[80:84] = code
    return b"DDS " + bytes(header) + blocks


# -- audio fixtures -----------------------------------------------------------


def wav_bytes(*, sample_rate: int = 22050, channels: int = 1,
              frames: int = 512, loop: tuple[int, int] | None = None) -> bytes:
    """A 16-bit PCM WAV of a sine wave, optionally carrying a loop region."""
    samples = bytearray()
    for index in range(frames):
        value = int(16384 * math.sin(index * 2.0 * math.pi / 64.0))
        for _ in range(channels):
            samples += struct.pack("<h", value)
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate,
                      sample_rate * channels * 2, channels * 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if loop is not None:
        start, length = loop
        smpl = struct.pack("<9I", 0, 0, 0, 60, 0, 0, 0, 1, 0)
        smpl += struct.pack("<6I", 0, 0, start, start + length - 1, 0, 0)
        body += b"smpl" + struct.pack("<I", len(smpl)) + smpl
    body += b"data" + struct.pack("<I", len(samples)) + bytes(samples)
    return b"RIFF" + struct.pack("<I", len(body)) + body


# -- model fixtures -----------------------------------------------------------

#: A two-triangle quad with per-face normals, two materials and texture
#: coordinates. Small enough to check by hand and asymmetric enough that a
#: reader which transposed anything would produce different numbers.
X_QUAD = """xof 0303txt 0032

Frame Root {
  FrameTransformMatrix {
    1.0,0.0,0.0,0.0,
    0.0,1.0,0.0,0.0,
    0.0,0.0,1.0,0.0,
    3.0,4.0,5.0,1.0;;
  }
  Mesh Quad {
    4;
    -1.0;0.0;0.0;,
     1.0;0.0;0.0;,
     1.0;2.0;0.0;,
    -1.0;2.0;0.0;;
    2;
    3;0,1,2;,
    3;0,2,3;;
    MeshNormals {
      2;
      0.0;0.0;1.0;,
      0.0;0.0;-1.0;;
      2;
      3;0,0,0;,
      3;1,1,1;;
    }
    MeshTextureCoords {
      4;
      0.0;1.0;,
      1.0;1.0;,
      1.0;0.0;,
      0.0;0.0;;
    }
    MeshMaterialList {
      2;
      2;
      0,
      1;
      Material Red {
        1.0;0.0;0.0;1.0;;
        32.0;
        0.5;0.5;0.5;;
        0.1;0.0;0.0;;
      }
      Material Blue {
        0.0;0.0;1.0;0.75;;
        8.0;
        0.0;0.0;0.0;;
        0.0;0.0;0.2;;
      }
    }
  }
}
"""


class _Services:
    """The smallest service provider a ``ContentManager`` accepts."""

    def GetService(self, serviceType: type) -> object:
        return None


def content_manager(root: str = "content"):
    from Microsoft.Xna.Framework.Content import ContentManager

    return ContentManager(_Services(), root)


def png_palette_bytes(rows: list[list[Color]], palette: list[Color],
                      transparency: list[int]) -> bytes:
    """A palettized PNG with a ``tRNS`` chunk, so alpha comes from the palette."""
    height, width = len(rows), len(rows[0])
    index_of = {(entry.R, entry.G, entry.B): index
                for index, entry in enumerate(palette)}
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for pixel in row:
            raw.append(index_of[(pixel.R, pixel.G, pixel.B)])
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0))
            + _chunk(b"PLTE", b"".join(bytes((entry.R, entry.G, entry.B))
                                       for entry in palette))
            + _chunk(b"tRNS", bytes(transparency))
            + _chunk(b"IDAT", zlib.compress(bytes(raw)))
            + _chunk(b"IEND", b""))


def wav_with_odd_chunk(*, sample_rate: int = 22050) -> bytes:
    """A WAV with an odd-sized chunk before ``data``.

    RIFF pads an odd chunk to an even boundary and does *not* count the pad in
    the chunk's size. A reader that forgets is one byte out for everything that
    follows, which is exactly what this fixture makes visible.
    """
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16)
    samples = b"".join(struct.pack("<h", index * 100) for index in range(16))
    odd = b"odd"  # three bytes, so the chunk needs one byte of padding
    body = (b"WAVE"
            + b"fmt " + struct.pack("<I", len(fmt)) + fmt
            + b"LIST" + struct.pack("<I", len(odd)) + odd + b"\x00"
            + b"data" + struct.pack("<I", len(samples)) + samples)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def mp3_with_decoy_tag() -> bytes:
    """An MP3 whose ID3 tag contains bytes that look like a frame header.

    A reader that searches from the start of the file rather than from the end
    of the tag finds the decoy, and answers a sample rate that is not the one
    the audio is in.
    """
    # 0xFF 0xF3 0x10 0x40 inside the tag: MPEG-**2** Layer III at 22.05 kHz --
    # a valid-looking header, and a different sample rate from the real one.
    decoy = bytes((0xFF, 0xF3, 0x10, 0x40)) + bytes(12)
    tag = b"ID3" + bytes((3, 0, 0, 0, 0, 0, len(decoy))) + decoy
    real = bytes((0xFF, 0xFB, 0x90, 0x40)) + bytes(64)
    return tag + real


def tga_bottom_up(rows: list[list[Color]]) -> bytes:
    """A 32-bit TGA stored bottom-up, which is TGA's default order."""
    height, width = len(rows), len(rows[0])
    header = bytes((0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0)) \
        + struct.pack("<HHBB", width, height, 32, 0x00)
    return header + b"".join(bytes((pixel.B, pixel.G, pixel.R, pixel.A))
                             for row in reversed(rows) for pixel in row)
