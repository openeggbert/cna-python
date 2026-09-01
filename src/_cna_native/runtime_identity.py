"""Identity of the CNA runtime that actually executed a measurement.

Runtime capability evidence is only meaningful when it names the backend that
produced it.  A result measured on a non-windowed control artifact is not a
statement about a real renderer, and the reverse is equally untrue, so every
capability claim is attributed to the artifact and renderer that produced it.

These are CNA-only identities and are deliberately private.  Nothing here is
part of the XNA projection; ``Microsoft.Xna.Framework.*`` never exposes a CNA
renderer identity.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass

from .loader import format_abi, get_library

#: Canonical ``CNA_GRAPHICS_RENDERER_*`` identities used by this binding.
RENDERER_UNKNOWN = 0
RENDERER_HEADLESS = 11
RENDERER_STUB = 13

#: Identities that execute no real graphics pipeline.  A capability measured on
#: one of these is a command-path result, never a rendering result.
NON_RENDERING_IDENTITIES = frozenset({RENDERER_UNKNOWN, RENDERER_HEADLESS, RENDERER_STUB})


@dataclass(frozen=True)
class RuntimeIdentity:
    """What actually ran: the library, its ABI, and its renderer."""

    library_path: str
    abi_version: int
    selected_renderer: int
    active_renderer: int | None
    renderer_latched: bool
    renderer_name: str

    @property
    def abi_text(self) -> str:
        return format_abi(self.abi_version)

    @property
    def renders(self) -> bool:
        """True when the active renderer executes a real graphics pipeline."""
        identity = self.active_renderer if self.active_renderer is not None else self.selected_renderer
        return identity not in NON_RENDERING_IDENTITIES

    def describe(self) -> str:
        state = "active" if self.active_renderer is not None else "selected"
        return f"{self.renderer_name} ({state}), CNA ABI {self.abi_text}"


def _copy_renderer_name(library: object) -> str:
    size = c.c_uint64()
    if library.cna_graphics_renderer_get_current_name_size(c.byref(size)) != 0:
        return ""
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    if library.cna_graphics_renderer_copy_current_name(buffer, size.value, c.byref(written)) != 0:
        return ""
    return bytes(buffer.raw[: written.value]).decode("utf-8", errors="replace")


def runtime_identity() -> RuntimeIdentity:
    """Reads the loaded runtime's identity without requiring a live Game."""
    library = get_library()
    selected = c.c_uint32()
    library.check(
        library.cna_graphics_renderer_get_selected_ext(c.byref(selected)),
        "cna_graphics_renderer_get_selected_ext")
    latched = c.c_uint8()
    library.check(
        library.cna_graphics_renderer_get_is_latched_ext(c.byref(latched)),
        "cna_graphics_renderer_get_is_latched_ext")
    active: int | None = None
    if latched.value:
        # Asking before the selection latches is refused rather than guessed, so the
        # unlatched answer stays absent instead of being filled in with the selection.
        value = c.c_uint32()
        if library.cna_graphics_renderer_get_active_ext(c.byref(value)) == 0:
            active = int(value.value)
    return RuntimeIdentity(
        library_path=str(library.path),
        abi_version=int(library.abi_version),
        selected_renderer=int(selected.value),
        active_renderer=active,
        renderer_latched=bool(latched.value),
        renderer_name=_copy_renderer_name(library),
    )
