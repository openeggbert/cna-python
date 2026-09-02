"""Private plumbing for ``cna.extensions.devices``.

The device-services family shares the whole of :mod:`_cna_native.family_support`
and adds two things of its own: which public exception each CNA result becomes,
and how a strict XNA ``Game`` is turned into the handle every route in
``devices.h`` takes as its first argument.

Like the engine layer, this family can be **absent from a build**. Every route
is exported in every CNA build, and the ones that need the device-services layer
answer ``CNA_RESULT_NOT_SUPPORTED`` when it was configured out. That is not the
same fact as "this host has no battery", and collapsing the two would tell a
caller to buy hardware when the answer is to change builds, so
``cna_devices_ext_is_available`` is asked rather than assumed.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c

from .errors import NativeError
from .family_support import (  # noqa: F401 - re-exported for the family's modules
    CallbackRoot, HandleSupport, NativeHandle, checked, float_array, in_struct,
    real, string_view,
)

#: CNA result code -> the public exception class that names what it means.
_RESULT_CLASSES = {
    1: "DeviceArgumentError",     # INVALID_ARGUMENT
    2: "DeviceInternalError",     # INVALID_HANDLE -- this layer never passes one
    3: "DeviceStateError",        # INVALID_STATE
    4: "DeviceInternalError",     # OUT_OF_MEMORY
    5: "DeviceInternalError",     # IO
    6: "DeviceUnsupportedError",  # NOT_SUPPORTED -- refined below
    7: "DeviceInternalError",     # PLATFORM
    8: "DeviceThreadError",       # THREAD
    9: "DeviceInternalError",     # CALLBACK
    10: "DeviceArgumentError",    # OVERFLOW
    11: "DeviceArgumentError",    # ENCODING
    12: "DeviceInternalError",    # INTERNAL
    13: "DeviceInternalError",    # SHUTTING_DOWN
}

_NOT_SUPPORTED = 6


def device_services_available() -> bool:
    """Whether this CNA build contains the device-services layer at all.

    The one route in the family that answers meaningfully without it, which is
    what separates "configured out" from "this host cannot".
    """
    from .loader import get_library

    library = get_library()
    value = c.c_uint8()
    library.check(library.cna_devices_ext_is_available(c.byref(value)),
                  "cna_devices_ext_is_available")
    return value.value != 0


def _translate(error: NativeError):
    from cna.extensions.devices import errors as public

    name = _RESULT_CLASSES.get(error.result, "DeviceInternalError")
    if error.result == _NOT_SUPPORTED:
        try:
            present = device_services_available()
        except NativeError:  # pragma: no cover - the availability route itself failed
            present = True
        if not present:
            name = "DeviceServicesUnavailableError"
    return getattr(public, name)(
        error.operation, error.result, error.category, error.native_message)


def _disposed(what: str):
    from cna.extensions.devices import errors as public

    return public.DeviceDisposedError("use after close", 0, None, f"{what} is closed")


#: The family's bound helpers.  Every module in ``cna.extensions.devices`` calls
#: through this object rather than touching the library directly.
support = HandleSupport(_translate, _disposed)


def game_handle(game: object, what: str) -> c.c_uint64:
    """The native handle of a strict XNA ``Game``.

    The dependency runs extension -> strict and never the reverse: ``Game`` is
    unchanged and does not know this package exists, so its handle is read
    through the private attribute the runtime already keeps rather than through
    a member added for this family.
    """
    host = getattr(game, "_host", None)
    handle = getattr(host, "handle", 0)
    if not handle:
        raise TypeError(
            f"{what} requires a running Microsoft.Xna.Framework.Game, "
            f"not {type(game).__name__}")
    return c.c_uint64(int(handle))
