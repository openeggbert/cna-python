"""Platform surface profiles: XNA as a console or a phone declares it.

Each is an import root of its own, because two profiles cannot both be
``Microsoft.Xna.Framework`` in one interpreter. What they hold is the *surface* a
platform has; the implementation under it is the one this repository ships.

This module holds the one thing they share: how a member that a platform does
**not** have is spelled.
"""

from __future__ import annotations


class _RemovedOnPlatform:
    """A member the platform's assemblies do not declare.

    Reading it raises ``AttributeError``, which is what reading a member that is
    not there does: ``hasattr`` answers False, ``getattr`` with a default
    answers the default, and code that asks before calling behaves the way it
    would on the console. Raising only when *called* would let all three of
    those lie.

    It is a descriptor rather than a deletion because the type it sits on
    inherits from the Windows one -- which is what keeps an ``except`` clause
    written against either of them working -- and inheritance has no way to take
    something back.
    """

    __slots__ = ("_name", "_reason")

    #: Read by the strict verifier, which counts a removed member as absent, and
    #: by the profile-separation gate, which checks every removal against the
    #: two contracts that justify it.
    _xna_removed_on_platform = True

    def __init__(self, name: str, reason: str) -> None:
        self._name = name
        self._reason = reason

    def __get__(self, instance: object, owner: type | None = None):
        raise AttributeError(f"{self._name} is not declared on this platform: "
                             f"{self._reason}")

    def __set__(self, instance: object, value: object) -> None:
        raise AttributeError(f"{self._name} is not declared on this platform: "
                             f"{self._reason}")

    def __repr__(self) -> str:
        return f"<removed on this platform: {self._name}>"
