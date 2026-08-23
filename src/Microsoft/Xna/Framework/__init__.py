"""Strict Microsoft.Xna.Framework public namespace."""

from ._game import DisplayOrientation, Game, GameTime, PlayerIndex
from ._geometry import Color, Point, Rectangle
from ._graphics_manager import GraphicsDeviceManager
from ._intersections import (
    BoundingBox, BoundingFrustum, BoundingSphere, ContainmentType, Plane,
    PlaneIntersectionType, Ray,
)
from ._math import MathHelper, Matrix, Quaternion, Vector2, Vector3, Vector4

__all__ = [
    "BoundingBox", "BoundingFrustum", "BoundingSphere", "Color", "ContainmentType",
    "DisplayOrientation", "Game", "GameTime", "GraphicsDeviceManager", "MathHelper",
    "Matrix", "Plane", "PlaneIntersectionType", "PlayerIndex", "Point", "Quaternion",
    "Ray", "Rectangle", "Vector2", "Vector3", "Vector4",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
