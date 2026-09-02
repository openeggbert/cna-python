"""The platforms a content build can target."""

from __future__ import annotations

from enum import IntEnum


class TargetPlatform(IntEnum):
    """Which platform a built asset is for.

    The value matters on the wire: the XNB header's platform byte is derived
    from it, and a runtime refuses a file built for another platform.
    """

    Windows = 0
    Xbox360 = 1
    WindowsPhone = 2
