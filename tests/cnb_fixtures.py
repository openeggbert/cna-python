"""Tiny, legal, project-authored source fixtures for the CNB/CNJ tests.

Every fixture here is generated in this file: nothing is downloaded, nothing is
checked in as an opaque blob, and each one is small enough that its expected
decoded contents can be written out in the test that uses it. A fixture whose
contents nobody can state is a fixture that cannot falsify anything.

The DDS layout mirrors CNA's own ``BuildSolidColorCubeDds`` test fixture, so both
sides of the decoder agree about what a valid cube map is rather than each
inventing one.
"""

from __future__ import annotations

import struct
import zlib


def png(width: int, height: int, rgba: bytes) -> bytes:
    """A minimal, valid RGBA8 PNG carrying exactly ``rgba``.

    Colour type 6 (RGBA), bit depth 8, no interlacing, filter 0 on every row --
    so the decoded pixels are the input bytes and nothing else.
    """
    if len(rgba) != width * height * 4:
        raise ValueError("rgba must be exactly width * height * 4 bytes")
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter type 0: None
        raw.extend(rgba[row * width * 4:(row + 1) * width * 4])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def pcm16(frames: int, channels: int = 1) -> bytes:
    """Deterministic signed 16-bit little-endian PCM, one distinct value per sample.

    The values are a fixed arithmetic sequence rather than silence or a tone, so
    a sample the importer misplaced is a different number rather than another
    zero.
    """
    samples = bytearray()
    for index in range(frames * channels):
        value = (index * 61) % 20000 - 10000
        samples.extend(struct.pack("<h", value))
    return bytes(samples)


def wav(samples: bytes, *, sample_rate: int = 22050, channels: int = 1,
        bits_per_sample: int = 16, loop: tuple[int, int] | None = None) -> bytes:
    """A minimal RIFF/WAVE file wrapping ``samples``.

    ``loop`` writes a ``smpl`` chunk whose first loop entry is ``(start, end)``
    in sample frames, which is what CNA's importer turns into the sound's loop
    region.
    """
    block_align = channels * bits_per_sample // 8
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate,
                      sample_rate * block_align, block_align, bits_per_sample)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(samples)) + samples
    if loop is not None:
        start, end = loop
        smpl = struct.pack("<IIIIIIIII", 0, 0, 0, 60, 0, 0, 0, 1, 0)
        smpl += struct.pack("<IIIIII", 0, 0, start, end, 0, 0)
        body += b"smpl" + struct.pack("<I", len(smpl)) + smpl
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _solid_dxt1_block(red: int, green: int, blue: int) -> bytes:
    """One solid DXT1 block whose colour survives the RGB565 round trip exactly.

    ``color0 == color1`` and every 2-bit index is 0, which the decompressor maps
    to ``color0`` in both of DXT1's comparison modes. Each channel must already
    be 0 or 255 so the round trip is exact and a test can assert precise values.
    """
    rgb565 = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
    packed = struct.pack("<HH", rgb565, rgb565)
    return packed + b"\x00\x00\x00\x00"


#: DDS ``caps`` bit marking the file a texture.
DDS_CAPS_TEXTURE = 0x1000
#: DDS ``caps`` bit marking a mip chain present.
DDS_CAPS_MIPMAP = 0x400000
#: DDS ``caps2`` bit marking the file a cube map.
DDS_CAPS2_CUBEMAP = 0x200
#: All six ``DDSCAPS2_CUBEMAP_*`` face bits.
DDS_CAPS2_ALL_FACES = 0xFC00


def cube_dds(size: int, face_colors, *, mip_count: int = 1,
             as_cube_map: bool = True, four_cc: bytes = b"DXT1") -> bytes:
    """A minimal, valid DXT1 DDS cube map, one solid colour per face.

    ``face_colors[0..5]`` map to +X, -X, +Y, -Y, +Z, -Z in that order, matching
    the on-disk DDS face layout. Every mip level of a face repeats that face's
    colour, so a test can assert on any level without a second expectation table.
    Each channel must be 0 or 255.

    ``as_cube_map=False`` and a foreign ``four_cc`` build the deliberately
    invalid variants the negative tests need.
    """
    if size % 4:
        raise ValueError("size must be a multiple of 4 for the block maths to stay exact")
    if len(face_colors) != 6:
        raise ValueError("a cube map needs exactly six face colours")
    data = bytearray(b"DDS ")
    data += struct.pack("<I", 124)
    data += struct.pack("<I", 0x2 | 0x4)          # DDSD_HEIGHT | DDSD_WIDTH
    data += struct.pack("<I", size)               # height
    data += struct.pack("<I", size)               # width
    data += struct.pack("<I", 0)                  # pitchOrLinearSize
    data += struct.pack("<I", 0)                  # depth
    data += struct.pack("<I", mip_count)          # mipMapCount
    data += struct.pack("<I", 0) * 11             # reserved1
    data += struct.pack("<I", 32)                 # pixel format size
    data += struct.pack("<I", 0x4)                # DDPF_FOURCC
    data += four_cc
    data += struct.pack("<I", 0) * 5              # bit count and masks
    data += struct.pack("<I", DDS_CAPS_TEXTURE | (DDS_CAPS_MIPMAP if mip_count > 1 else 0))
    data += struct.pack("<I", (DDS_CAPS2_CUBEMAP | DDS_CAPS2_ALL_FACES) if as_cube_map else 0)
    data += struct.pack("<I", 0) * 3              # caps3, caps4, reserved2
    for red, green, blue in face_colors:
        level_size = size
        for _level in range(mip_count):
            blocks = ((level_size + 3) // 4) ** 2
            data += _solid_dxt1_block(red, green, blue) * blocks
            level_size = level_size // 2 if level_size > 1 else 1
    return bytes(data)


def distinct_rgba(width: int, height: int) -> bytes:
    """Pixels where every channel of every texel is distinguishable from its neighbours.

    A uniform fixture cannot detect a transposed or reversed image; this one can.
    """
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            pixels.extend((
                (x * 37 + 1) & 0xFF,
                (y * 53 + 2) & 0xFF,
                (x * 11 + y * 7 + 3) & 0xFF,
                255,
            ))
    return bytes(pixels)
