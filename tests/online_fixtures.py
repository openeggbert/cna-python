"""Shared harness for the ``xna40-windows-online`` strict profile's tests.

Everything here runs against **CNA's own synthetic platform**. A signed-in gamer
is published through :mod:`cna.extensions.online`, which is the route a platform
layer would call; a session's remote roster is filled explicitly; a packet is
delivered as if a transport had received it.

The label is therefore ``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED``, and never
``REAL_PLATFORM_SIGN_IN_VERIFIED``. Nobody signed in to anything, no second
machine was involved, and no test here claims otherwise. What is measured is the
object graph, the roster arithmetic, the packet protocol, the event contract and
this binding's own conversions.
"""

from __future__ import annotations

import unittest

from Microsoft.Xna.Framework import PlayerIndex

from .device_fixtures import IDENTITY, NATIVE, RENDERS, in_game  # noqa: F401


def _online_available() -> bool:
    if not NATIVE:
        return False
    from _cna_native.loader import get_library

    try:
        library = get_library()
        return hasattr(library, "cna_signed_in_gamer_create_ext")
    except Exception:  # pragma: no cover - defensive
        return False


ONLINE_PRESENT = _online_available()

requires_online = unittest.skipUnless(
    ONLINE_PRESENT, "the loaded CNA build has no gamer-services layer")
requires_online_renderer = unittest.skipUnless(
    ONLINE_PRESENT and RENDERS,
    "needs a gamer-services build on a rasterizing renderer")

#: The two gamertags every case uses. Different lengths and different bytes, so a
#: facade that answered with the wrong gamer produces a different string.
FIRST_GAMERTAG = "PlayerOne"
SECOND_GAMERTAG = "SecondPlayerWithALongerTag"


class _Platform:
    """Publishes synthetic signed-in gamers and takes them away again."""

    def __init__(self, *tags: str) -> None:
        self.tags = tags or (FIRST_GAMERTAG,)
        self.gamers: list = []

    def __enter__(self):
        from cna.extensions.online import create_signed_in_gamer, publish_signed_in_gamers

        indices = list(PlayerIndex)
        self.gamers = [
            create_signed_in_gamer(tag, is_signed_in_to_live=True,
                                   player_index=indices[index])
            for index, tag in enumerate(self.tags)
        ]
        publish_signed_in_gamers(self.gamers)
        return self.gamers

    def __exit__(self, *_exception: object) -> None:
        from cna.extensions.online import publish_signed_in_gamers

        publish_signed_in_gamers([])


def platform(*tags: str) -> _Platform:
    """A context manager that publishes ``tags`` as signed-in gamers."""
    return _Platform(*tags)
