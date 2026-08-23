"""Strict Microsoft.Xna.Framework public namespace."""

from ._game import DisplayOrientation, Game, GameTime, PlayerIndex
from ._geometry import Color, Point, Rectangle
from ._graphics_manager import GraphicsDeviceManager
from ._math import MathHelper, Matrix, Quaternion, Vector2, Vector3, Vector4

__all__ = [
    "Color", "DisplayOrientation", "Game", "GameTime", "GraphicsDeviceManager",
    "MathHelper", "Matrix", "PlayerIndex", "Point", "Quaternion", "Rectangle",
    "Vector2", "Vector3", "Vector4",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
