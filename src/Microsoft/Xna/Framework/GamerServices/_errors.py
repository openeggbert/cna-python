"""The five exceptions the online profile declares.

Every one is an ordinary Python exception with XNA's constructor overloads. The
two that XNA gives a serialization constructor are projected without it: its
parameters are ``SerializationInfo`` and ``StreamingContext``, both mapped to
``object`` by the language rules, so the overload would be indistinguishable
from ``(message, innerException)`` at run time. That is a
LANGUAGE_MAPPING_LIMITATION and it is recorded as one rather than hidden behind
an overload that could not be dispatched.
"""

from __future__ import annotations

__all__ = [
    "GamerServicesNotAvailableException",
    "GamerPrivilegeException",
    "GuideAlreadyVisibleException",
    "GameUpdateRequiredException",
    "NetworkException",
    "NetworkNotAvailableException",
]


class _XnaException(Exception):
    """XNA's ``(), (message), (message, innerException)`` constructor set."""

    def __init__(self, *args: object) -> None:
        if not args:
            super().__init__()
        elif len(args) == 1 and isinstance(args[0], str):
            super().__init__(args[0])
        elif (len(args) == 2 and isinstance(args[0], str)
              and isinstance(args[1], BaseException)):
            super().__init__(args[0])
            self.__cause__ = args[1]
        else:
            raise TypeError(
                f"{type(self).__name__} expects (), message, or message and "
                "innerException")


_XnaException.__xna_arities__ = {"__init__": {0, 1, 2}}


class GamerServicesNotAvailableException(_XnaException):
    """Gamer services are not available on this platform or in this build."""


class GamerPrivilegeException(_XnaException):
    """The signed-in gamer does not have the privilege the call needed."""


class GuideAlreadyVisibleException(_XnaException):
    """The Guide is already showing something."""


class GameUpdateRequiredException(_XnaException):
    """The title must be updated before it may go online."""


class NetworkException(_XnaException):
    """A network operation failed."""


class NetworkNotAvailableException(NetworkException):
    """There is no network to use."""


GamerServicesNotAvailableException.__xna_arities__ = {"__init__": {0, 1, 2}}


GamerPrivilegeException.__xna_arities__ = {"__init__": {0, 1, 2}}


GuideAlreadyVisibleException.__xna_arities__ = {"__init__": {0, 1, 2}}


GameUpdateRequiredException.__xna_arities__ = {"__init__": {0, 1, 2}}


NetworkException.__xna_arities__ = {"__init__": {0, 1, 2}}


NetworkNotAvailableException.__xna_arities__ = {"__init__": {0, 1, 2}}
