"""Private plumbing for the ``xna40-windows-online`` strict profile.

``Microsoft.Xna.Framework.Net`` and the wider
``Microsoft.Xna.Framework.GamerServices`` are strict XNA surface, not a CNA
extension, so what a route's failure becomes is an *XNA* exception rather than a
family-specific one. That is the only thing this module adds to
:mod:`_cna_native.family_support`.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c

from .errors import NativeError
from .family_support import (  # noqa: F401 - re-exported for the profile's modules
    CallbackRoot, HandleSupport, NativeHandle, checked, float_array, in_struct,
    real, string_view,
)

#: CNA result code -> the XNA exception it is projected as.
#:
#: ``INVALID_STATE`` is ``InvalidOperationException`` in XNA, which Python has no
#: name for, so it is ``RuntimeError`` -- the same choice the rest of this
#: projection already makes. ``NOT_SUPPORTED`` on this family means the platform
#: has no gamer services, which XNA spells
#: ``GamerServicesNotAvailableException``.
_RESULT_CLASSES = {
    1: "ArgumentException",
    2: "InvalidOperationException",
    3: "InvalidOperationException",
    4: "MemoryError",
    5: "IOError",
    6: "GamerServicesNotAvailableException",
    7: "InvalidOperationException",
    8: "InvalidOperationException",
    9: "InvalidOperationException",
    10: "OverflowError",
    11: "ArgumentException",
    12: "InvalidOperationException",
    13: "InvalidOperationException",
}


def _translate(error: NativeError):
    """Maps one CNA failure onto the XNA-shaped Python exception for it."""
    name = _RESULT_CLASSES.get(error.result, "InvalidOperationException")
    message = error.native_message or f"{error.operation} failed with CNA result {error.result}"
    if name == "GamerServicesNotAvailableException":
        from Microsoft.Xna.Framework.GamerServices import (
            GamerServicesNotAvailableException,
        )

        return GamerServicesNotAvailableException(message)
    if name == "ArgumentException":
        return ValueError(message)
    if name == "OverflowError":
        return OverflowError(message)
    if name == "MemoryError":
        return MemoryError(message)
    if name == "IOError":
        return OSError(message)
    return RuntimeError(message)


def _disposed(what: str):
    return RuntimeError(f"{what} has been disposed")


#: The profile's bound helpers.
support = HandleSupport(_translate, _disposed)


def no_callback(factory: type):
    """A null function pointer of ``factory``'s type.

    ``ctypes`` will not accept ``None`` where the prototype declares a
    ``CFUNCTYPE``; an empty instance is the null pointer C expects. Several CNA
    routes take an optional completion callback, and this package passes none
    because every one of them completes during the call.
    """
    return factory()


def handles(values, what: str):
    """A caller-owned C array of handles, or ``(None, 0)`` when empty."""
    values = tuple(values)
    if not values:
        return None, 0
    return (c.c_uint64 * len(values))(*values), len(values)
