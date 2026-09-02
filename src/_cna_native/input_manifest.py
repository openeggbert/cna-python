"""ctypes manifest for CNA's ``input_text.h``, ``input_cursor.h``, ``input_joystick.h``, ``input_haptics.h``, ``input_devices.h`` family.

Do not edit. ``tools/generate_family_manifest.py`` derives every prototype
from the canonical headers, and ``--check`` fails when the checked-in copy is
not what the current headers produce. Every entry is proven against the
canonical C declaration by ``tools/verify_prototypes.py`` -- being generated is
not a reason to trust it.

The fourth column is the ownership contract the Python wrapper has to keep.
"""

from __future__ import annotations

import ctypes as c

from . import abi
from . import devices_abi
from . import input_abi

Entry = tuple[str, object, list[object], str]

#: The host clipboard's read side. ``devices.h`` writes it and
#: ``input_devices.h`` reads it; the two are one clipboard.
INPUT_CLIPBOARD_MANIFEST: tuple[Entry, ...] = (
    ("cna_clipboard_copy_text", c.c_uint32, [c.c_uint64, c.POINTER(c.c_char), c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; two-call size/copy protocol, no partial write"),
    ("cna_clipboard_get_has_text", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint8)],
     "caller output; borrowed handle, nothing is retained"),
    ("cna_clipboard_get_text_size", c.c_uint32, [c.c_uint64, c.POINTER(c.c_uint64)],
     "caller output; the size half of the size/copy protocol"),
    ("cna_clipboard_set_text", c.c_uint32, [c.c_uint64, abi.CNA_StringView],
     "borrowed handle; copies the value, retains nothing"),
)

#: Every group above, in one tuple for :mod:`_cna_native.loader`.
INPUT_FUNCTION_MANIFEST: tuple[Entry, ...] = (
    INPUT_CLIPBOARD_MANIFEST
)
