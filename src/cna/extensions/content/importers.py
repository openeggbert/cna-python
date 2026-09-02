"""Turning ordinary source files -- PNG, JPEG, DDS, WAV -- into compiled data.

Every importer here goes through **CNA's own** decoder, which is the point: a
`.cnb` compiled from a PNG holds exactly the pixels the runtime would have loaded
from the same PNG, because there is no second decoder to disagree with the first.

The WAV importer is deliberately narrow rather than a general audio decoder. It
accepts the uncompressed formats that convert to 16-bit PCM *exactly* -- 16-bit
PCM stored as-is and 8-bit unsigned PCM widened exactly -- and refuses everything
else by name instead of resampling or truncating someone's audio silently.
24-bit, 32-bit, IEEE float and ADPCM are each an authoring decision rather than a
compiler's.
"""

from __future__ import annotations

import ctypes as c
import os

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .audio import CnbSoundEffectData
from .textures import CnbTextureData

__all__ = [
    "decode_dds_as_texture_cube",
    "decode_wav_as_sound_effect",
    "import_dds_as_texture_cube",
    "import_image_as_texture2d",
    "import_wav_as_sound_effect",
]


def import_image_as_texture2d(
        path: "str | os.PathLike[str]", *,
        color_key: tuple[int, int, int] | None = None) -> CnbTextureData:
    """Decodes an image file into a single-level ``Rgba8`` 2D description.

    ``color_key`` makes one RGB colour fully transparent -- matching pixels keep
    their RGB and get an alpha of 0, which is what the runtime path does. It is
    applied **only when asked for**: silently rewriting someone's pixels because
    a default said so would be worse than making them say it.
    """
    options = _abi.CNA_CnbImageImportOptions()
    options.struct_size = c.sizeof(_abi.CNA_CnbImageImportOptions)
    options.struct_version = _abi.CNA_CNB_IMAGE_IMPORT_OPTIONS_STRUCT_VERSION
    if color_key is None:
        options.has_color_key = 0
    else:
        if len(color_key) != 3:
            raise ValueError("color_key must be a (red, green, blue) triple")
        for index, channel in enumerate(color_key):
            options.color_key[index] = _support.checked(channel, "uint8", "color_key")
        options.has_color_key = 1
    view, keep = _support.string_view(os.fspath(path), "path")
    handle = _support.out_handle(
        "cna_cnb_import_image_as_texture2d", view, c.byref(options))
    del keep
    return CnbTextureData._adopt(handle)


def import_dds_as_texture_cube(path: "str | os.PathLike[str]") -> CnbTextureData:
    """Decodes a DDS cube map file into a ``TextureCube`` description.

    The result is ``Rgba8``, not the original DXT blocks. That is not a
    shortcut: the runtime DDS path already decompresses on the CPU, and texture
    schema 1's contract is the portable ``Rgba8`` baseline -- storing the blocks
    would produce a file this build could not upload.
    """
    view, keep = _support.string_view(os.fspath(path), "path")
    handle = _support.out_handle("cna_cnb_import_dds_as_texture_cube", view)
    del keep
    return CnbTextureData._adopt(handle)


def decode_dds_as_texture_cube(data: bytes, *, origin: str = "") -> CnbTextureData:
    """Decodes DDS bytes already in memory into a ``TextureCube`` description."""
    pointer, count, keep = _support.read_only_bytes(data, "data")
    view, keep_origin = _support.string_view(origin, "origin")
    handle = _support.out_handle(
        "cna_cnb_decode_dds_as_texture_cube", pointer, c.c_uint64(count), view)
    del keep, keep_origin
    return CnbTextureData._adopt(handle)


def import_wav_as_sound_effect(path: "str | os.PathLike[str]") -> CnbSoundEffectData:
    """Reads and decodes a WAV file as a ``SoundEffect`` description.

    A ``smpl`` chunk's first loop entry becomes the sound's loop region, using
    the runtime's own rules, so a looping WAV compiles to a looping `.cnb`.
    """
    view, keep = _support.string_view(os.fspath(path), "path")
    handle = _support.out_handle("cna_cnb_import_wav_as_sound_effect", view)
    del keep
    return CnbSoundEffectData._adopt(handle)


def decode_wav_as_sound_effect(data: bytes, *, origin: str = "") -> CnbSoundEffectData:
    """Decodes WAV bytes already in memory as a ``SoundEffect`` description."""
    pointer, count, keep = _support.read_only_bytes(data, "data")
    view, keep_origin = _support.string_view(origin, "origin")
    handle = _support.out_handle(
        "cna_cnb_decode_wav_as_sound_effect", pointer, c.c_uint64(count), view)
    del keep, keep_origin
    return CnbSoundEffectData._adopt(handle)
