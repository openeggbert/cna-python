"""Private plumbing for ``cna.extensions.input``.

Shares the whole of :mod:`_cna_native.family_support`; what it adds is which
public exception each CNA result becomes and how a strict XNA ``Game`` becomes
the handle these routes take.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c

from .devices_support import game_handle  # noqa: F401 - one Game, one handle
from .errors import NativeError
from .family_support import (  # noqa: F401 - re-exported for the family's modules
    CallbackRoot, HandleSupport, NativeHandle, checked, float_array, in_struct,
    real, string_view,
)

_RESULT_CLASSES = {
    1: "InputArgumentError",
    2: "InputInternalError",
    3: "InputStateError",
    4: "InputInternalError",
    5: "InputInternalError",
    6: "InputUnsupportedError",
    7: "InputInternalError",
    8: "InputThreadError",
    9: "InputInternalError",
    10: "InputArgumentError",
    11: "InputArgumentError",
    12: "InputInternalError",
    13: "InputInternalError",
}


def _translate(error: NativeError):
    from cna.extensions.input import errors as public

    return getattr(public, _RESULT_CLASSES.get(error.result, "InputInternalError"))(
        error.operation, error.result, error.category, error.native_message)


def _disposed(what: str):
    from cna.extensions.input import errors as public

    return public.InputDisposedError("use after close", 0, None, f"{what} is closed")


#: The family's bound helpers.
support = HandleSupport(_translate, _disposed)
