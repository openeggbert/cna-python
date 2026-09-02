"""CNA's extended input: devices and capabilities XNA 4.0 never had.

This is a **CNA extension**, not part of XNA. Text input and IME composition,
mouse cursors, raw joysticks, haptics, input-device enumeration and hotplug, and
the sensors a gamepad carries have no ``Microsoft.Xna.Framework`` counterpart,
which is why they live here rather than there.

**The strict XNA projection is untouched by this package.** The dependency runs
one way, and the extension gate asserts in a fresh interpreter that importing
the XNA namespace loads no ``cna`` module.

Ownership is the same contract as everywhere in ``cna.extensions``: an explicit
``close``, a context manager, no ``__del__``, and no raw handle, ctypes object or
result code anywhere in the public surface.
"""

from __future__ import annotations

from . import clipboard, errors
from .clipboard import (
    clipboard_has_text, clipboard_text, clipboard_text_byte_length,
    set_clipboard_text,
)
from .errors import (
    InputArgumentError, InputDisposedError, InputError, InputInternalError,
    InputStateError, InputThreadError, InputUnsupportedError,
)

__all__ = [
    "clipboard", "errors",
    "clipboard_has_text", "clipboard_text", "clipboard_text_byte_length",
    "set_clipboard_text",
    "InputArgumentError", "InputDisposedError", "InputError",
    "InputInternalError", "InputStateError", "InputThreadError",
    "InputUnsupportedError",
]
