"""Exceptions ``cna.extensions.input`` raises.

The same four kinds of "no" the device-services family separates, for the same
reason: a build without the extended-input layer, a host without the device, a
call that is wrong for the object's state, and a use after close.
"""

from __future__ import annotations

__all__ = [
    "InputError",
    "InputArgumentError",
    "InputStateError",
    "InputThreadError",
    "InputUnsupportedError",
    "InputDisposedError",
    "InputInternalError",
]


class InputError(Exception):
    """A CNA extended-input route failed."""

    def __init__(self, operation: str, result: int, category: object,
                 message: str | None) -> None:
        self.operation = operation
        self.result = int(result)
        self.category = category
        self.native_message = message
        detail = f": {message}" if message else ""
        super().__init__(f"{operation} failed with CNA result {result}{detail}")


class InputArgumentError(InputError, ValueError):
    """An argument was outside what the route accepts."""


class InputStateError(InputError, RuntimeError):
    """The object is real, and the call is wrong for the state it is in."""


class InputThreadError(InputError, RuntimeError):
    """The call was made from a thread the route does not accept."""


class InputUnsupportedError(InputError, RuntimeError):
    """This host or platform does not have the device or capability."""


class InputDisposedError(InputStateError):
    """The object was closed before this call."""


class InputInternalError(InputError, RuntimeError):
    """CNA reported a failure this package has no more specific name for."""
