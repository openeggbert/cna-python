"""Exceptions ``cna.extensions.devices`` raises.

Every one names the CNA route that failed, the result code it answered with, and
CNA's own message. None is raised for a state this package inferred: a sensor
that is not supported says so because CNA said so.

The hierarchy separates four different kinds of "no":

``DeviceServicesUnavailableError``
    This CNA build has no device-services layer. Nothing about the host is
    wrong; a different build answers.
``DeviceUnsupportedError``
    The layer is present and this host or platform does not have the thing.
``DeviceStateError``
    The object is real and the call is wrong for its current state -- reading a
    sensor that was never started.
``DeviceDisposedError``
    The object was closed, and using it after that is a defect in the caller.
"""

from __future__ import annotations

__all__ = [
    "DeviceError",
    "DeviceArgumentError",
    "DeviceStateError",
    "DeviceThreadError",
    "DeviceUnsupportedError",
    "DeviceServicesUnavailableError",
    "DeviceDisposedError",
    "DeviceInternalError",
]


class DeviceError(Exception):
    """A CNA device-services route failed.

    :param operation: the canonical route name.
    :param result: CNA's result code.
    :param category: CNA's error category, when it reported one.
    :param message: CNA's own message, when it reported one.
    """

    def __init__(self, operation: str, result: int, category: object,
                 message: str | None) -> None:
        self.operation = operation
        self.result = int(result)
        self.category = category
        self.native_message = message
        detail = f": {message}" if message else ""
        super().__init__(f"{operation} failed with CNA result {result}{detail}")


class DeviceArgumentError(DeviceError, ValueError):
    """An argument was outside what the route accepts."""


class DeviceStateError(DeviceError, RuntimeError):
    """The object is real, and the call is wrong for the state it is in."""


class DeviceThreadError(DeviceError, RuntimeError):
    """The call was made from a thread the route does not accept."""


class DeviceUnsupportedError(DeviceError, RuntimeError):
    """The device-services layer is present and this host does not have the thing."""


class DeviceServicesUnavailableError(DeviceUnsupportedError):
    """This CNA build was configured without the device-services layer."""


class DeviceDisposedError(DeviceStateError):
    """The object was closed before this call."""


class DeviceInternalError(DeviceError, RuntimeError):
    """CNA reported a failure this package has no more specific name for."""
