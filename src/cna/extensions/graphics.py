"""Renderer identity, capability reporting and selection.

XNA has no notion of a renderer: it targets one Direct3D generation, so
``Microsoft.Xna.Framework.Graphics`` has nowhere honest to put "which backend am
I running on". CNA compiles a chosen set of renderers into a build and picks one
at startup, and that choice decides what a program can actually do -- whether
draws produce pixels, whether compiled effects exist, whether a device can be
lost. This module reports it.

**Selection is process-wide and latches.** CNA fixes the choice when the first
graphics device is created; before that the preference and fallback chain can be
set, and afterwards they are refused rather than silently ignored. That is why
:func:`is_selection_latched` exists: it is how a caller knows which of the two
states it is in without guessing.

All values here are plain Python. No CNA handle and no ctypes object is public.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

from _cna_native import abi
from _cna_native.loader import get_library

__all__ = [
    "Renderer",
    "FallbackReason",
    "FallbackRecord",
    "available_renderers",
    "is_renderer_available",
    "selected_renderer",
    "active_renderer",
    "current_renderer",
    "current_renderer_name",
    "is_selection_latched",
    "parse_renderer_name",
    "prefer_renderer",
    "set_fallback_chain",
    "automatic_fallback",
    "set_automatic_fallback",
    "fallback_history",
]


class Renderer(IntEnum):
    """A CNA graphics renderer identity.

    The numeric values are CNA's own and are stable: an identity CNA retires
    keeps its number rather than having it reused, so a value read from an older
    build never silently means a different renderer in a newer one.
    """

    Unknown = 0
    SdlRenderer = 1
    OpenGLES2 = 2
    OpenGLES3 = 3
    OpenGL33 = 4
    WebGL1 = 5
    WebGL2 = 6
    Bgfx = 7
    Vulkan = 8
    WebGpu = 9
    Headless = 11
    Software = 12
    Stub = 13
    DirectX11 = 14
    DirectX12 = 15
    Direct2D = 16
    Canvas = 17
    HtmlDom = 18
    FreeDirect = 21
    DirectX9 = 22
    DirectX1 = 23
    DirectX2 = 24
    DirectX3 = 25
    DirectX5 = 26
    DirectX6 = 27
    DirectX7 = 28
    DirectX8 = 29
    DirectX10 = 30
    SdlGpu = 31
    OpenGLES1 = 32
    OpenGL4 = 33
    OpenGL1 = 34
    OpenGL2 = 35
    Glide = 39
    Gdi = 40
    Metal = 42
    Fna3D = 43
    SvgDom = 44
    PortableGL = 46
    PixiJS = 49


#: Identities that execute no real graphics pipeline. A result measured on one of
#: these describes a command path, not rendering.
NON_RENDERING = frozenset({Renderer.Unknown, Renderer.Headless, Renderer.Stub})


class FallbackReason(IntEnum):
    """Why a renderer that was tried got passed over."""

    NotCompiledIn = 0
    ProbeUnavailable = 1
    InitializationFailed = 2
    WindowKindConflict = 3


@dataclass(frozen=True)
class FallbackRecord:
    """One renderer that was tried and passed over, with CNA's diagnostic."""

    renderer: Renderer
    reason: FallbackReason
    reason_name: str
    message: str


def _renderer(value: int) -> Renderer:
    try:
        return Renderer(int(value))
    except ValueError:
        # A build newer than this module can report an identity it does not name.
        # Reporting the number honestly beats pretending the renderer is Unknown.
        return int(value)  # type: ignore[return-value]


def available_renderers() -> tuple[Renderer, ...]:
    """Every renderer identity compiled into this build, in CNA's order.

    Being enumerated is not a support claim about the host; it says the build can
    produce that renderer, not that this machine can run it.
    """
    library = get_library()
    count = c.c_uint64()
    library.check(library.cna_graphics_renderer_get_available_count_ext(c.byref(count)),
                  "cna_graphics_renderer_get_available_count_ext")
    if count.value == 0:
        return ()
    values = (c.c_uint32 * count.value)()
    written = c.c_uint64()
    library.check(library.cna_graphics_renderer_copy_available_ext(
        values, count.value, c.byref(written)), "cna_graphics_renderer_copy_available_ext")
    return tuple(_renderer(values[index]) for index in range(written.value))


def is_renderer_available(renderer: Renderer | int) -> bool:
    """Reports whether one identity is compiled into this build."""
    library = get_library()
    answer = c.c_uint8()
    library.check(library.cna_graphics_renderer_get_is_available_ext(int(renderer), c.byref(answer)),
                  "cna_graphics_renderer_get_is_available_ext")
    return bool(answer.value)


def selected_renderer() -> Renderer:
    """The renderer CNA will attempt first."""
    library = get_library()
    value = c.c_uint32()
    library.check(library.cna_graphics_renderer_get_selected_ext(c.byref(value)),
                  "cna_graphics_renderer_get_selected_ext")
    return _renderer(value.value)


def active_renderer() -> Renderer | None:
    """The renderer that was actually created, or ``None`` before one exists.

    It equals :func:`selected_renderer` unless a fallback chain substituted
    another. Asking before the selection latches has no honest answer, so this
    reports ``None`` rather than filling in the preference.
    """
    if not is_selection_latched():
        return None
    library = get_library()
    value = c.c_uint32()
    library.check(library.cna_graphics_renderer_get_active_ext(c.byref(value)),
                  "cna_graphics_renderer_get_active_ext")
    return _renderer(value.value)


def current_renderer() -> Renderer:
    """This build's compiled-in renderer identity."""
    library = get_library()
    value = c.c_uint32()
    library.check(library.cna_graphics_renderer_get_current_type(c.byref(value)),
                  "cna_graphics_renderer_get_current_type")
    return _renderer(value.value)


def current_renderer_name() -> str:
    """This build's compiled-in renderer name, such as ``"OPENGLES3"``."""
    library = get_library()
    size = c.c_uint64()
    library.check(library.cna_graphics_renderer_get_current_name_size(c.byref(size)),
                  "cna_graphics_renderer_get_current_name_size")
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    library.check(library.cna_graphics_renderer_copy_current_name(
        buffer, size.value, c.byref(written)), "cna_graphics_renderer_copy_current_name")
    return bytes(buffer.raw[: written.value]).decode("utf-8", errors="strict")


def is_selection_latched() -> bool:
    """Reports whether a renderer has been created and the choice is now fixed."""
    library = get_library()
    value = c.c_uint8()
    library.check(library.cna_graphics_renderer_get_is_latched_ext(c.byref(value)),
                  "cna_graphics_renderer_get_is_latched_ext")
    return bool(value.value)


def parse_renderer_name(name: str) -> Renderer | None:
    """Parses a renderer name case-insensitively, or ``None`` if unrecognized.

    An unrecognized name is an answer rather than an error, which is what makes
    this usable directly on configuration a user typed.
    """
    if not isinstance(name, str):
        raise TypeError("name must be str")
    encoded = name.encode("utf-8", errors="strict")
    library = get_library()
    value, recognized = c.c_uint32(), c.c_uint8()
    library.check(library.cna_graphics_renderer_try_parse_name_ext(
        abi.CNA_StringView(encoded, len(encoded)), c.byref(value), c.byref(recognized)),
        "cna_graphics_renderer_try_parse_name_ext")
    return _renderer(value.value) if recognized.value else None


def prefer_renderer(renderer: Renderer | int | str) -> None:
    """Requests the renderer CNA should attempt first.

    Process-wide, and only before the first graphics device exists; afterwards
    the runtime refuses rather than silently ignoring the request.
    """
    library = get_library()
    if isinstance(renderer, str):
        encoded = renderer.encode("utf-8", errors="strict")
        library.check(library.cna_graphics_renderer_set_preferred_by_name_ext(
            abi.CNA_StringView(encoded, len(encoded))),
            "cna_graphics_renderer_set_preferred_by_name_ext")
        return
    library.check(library.cna_graphics_renderer_set_preferred_ext(int(renderer)),
                  "cna_graphics_renderer_set_preferred_ext")


def set_fallback_chain(renderers: Iterable[Renderer | int]) -> None:
    """Sets the order CNA tries renderers in when the preferred one cannot be used."""
    values = [int(value) for value in renderers]
    library = get_library()
    array = (c.c_uint32 * len(values))(*values) if values else None
    library.check(library.cna_graphics_renderer_set_fallback_chain_ext(array, len(values)),
                  "cna_graphics_renderer_set_fallback_chain_ext")


def automatic_fallback() -> bool:
    """Reports whether CNA may try the fallback chain."""
    library = get_library()
    value = c.c_uint8()
    library.check(library.cna_graphics_renderer_get_automatic_fallback_ext(c.byref(value)),
                  "cna_graphics_renderer_get_automatic_fallback_ext")
    return bool(value.value)


def set_automatic_fallback(enabled: bool) -> None:
    """Lets CNA try the fallback chain, or makes it fail instead."""
    if type(enabled) is not bool:
        raise TypeError("enabled must be bool")
    library = get_library()
    library.check(library.cna_graphics_renderer_set_automatic_fallback_ext(int(enabled)),
                  "cna_graphics_renderer_set_automatic_fallback_ext")


def _fallback_message(index: int) -> str:
    library = get_library()
    size = c.c_uint64()
    library.check(library.cna_graphics_renderer_fallback_get_message_size_ext(index, c.byref(size)),
                  "cna_graphics_renderer_fallback_get_message_size_ext")
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    library.check(library.cna_graphics_renderer_fallback_copy_message_ext(
        index, buffer, size.value, c.byref(written)),
        "cna_graphics_renderer_fallback_copy_message_ext")
    return bytes(buffer.raw[: written.value]).decode("utf-8", errors="replace")


def _fallback_reason_name(reason: int) -> str:
    library = get_library()
    size = c.c_uint64()
    library.check(library.cna_graphics_renderer_fallback_reason_get_name_size_ext(
        reason, c.byref(size)), "cna_graphics_renderer_fallback_reason_get_name_size_ext")
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    library.check(library.cna_graphics_renderer_fallback_reason_copy_name_ext(
        reason, buffer, size.value, c.byref(written)),
        "cna_graphics_renderer_fallback_reason_copy_name_ext")
    return bytes(buffer.raw[: written.value]).decode("utf-8", errors="replace")


def fallback_history() -> tuple[FallbackRecord, ...]:
    """Every renderer that was tried and passed over, in attempt order.

    Empty on a build whose first choice worked, which is the ordinary case. When
    it is not empty it is the only place that says why the program is running on
    a renderer it did not ask for.
    """
    library = get_library()
    count = c.c_uint64()
    library.check(library.cna_graphics_renderer_get_fallback_count_ext(c.byref(count)),
                  "cna_graphics_renderer_get_fallback_count_ext")
    records: list[FallbackRecord] = []
    for index in range(count.value):
        record = abi.CNA_GraphicsRendererFallbackRecord()
        record.struct_size, record.struct_version = c.sizeof(record), 1
        library.check(library.cna_graphics_renderer_get_fallback_at_ext(index, c.byref(record)),
                      "cna_graphics_renderer_get_fallback_at_ext")
        try:
            reason = FallbackReason(int(record.reason))
        except ValueError:
            reason = int(record.reason)  # type: ignore[assignment]
        records.append(FallbackRecord(
            renderer=_renderer(record.type),
            reason=reason,
            reason_name=_fallback_reason_name(int(record.reason)),
            message=_fallback_message(index),
        ))
    return tuple(records)
