"""Python-native frontend for the CNA game framework.

This package is an early scaffold. Native execution will be enabled only after
CNA publishes its stable C ABI.
"""

from ._native import NativeUnavailableError
from .framework import Color, Game, GameTime, Vector2

__all__ = [
    "Color",
    "Game",
    "GameTime",
    "NativeUnavailableError",
    "Vector2",
]

__version__ = "0.0.0"
