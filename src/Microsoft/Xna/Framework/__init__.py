"""Strict Microsoft.Xna.Framework public namespace."""

from ._game import DisplayOrientation, Game, GameTime, PlayerIndex
from ._game_objects import (
    DrawableGameComponent, GameComponent, GameComponentCollection,
    GameComponentCollectionEventArgs, GameServiceContainer, GameWindow,
    IDrawable, IGameComponent, IUpdateable, LaunchParameters,
)
from ._geometry import Color, Point, Rectangle
from ._curve import Curve, CurveContinuity, CurveKey, CurveKeyCollection, CurveLoopType, CurveTangent
from ._graphics_manager import (
    GraphicsDeviceInformation, GraphicsDeviceManager, IGraphicsDeviceManager,
    PreparingDeviceSettingsEventArgs,
)
from ._intersections import (
    BoundingBox, BoundingFrustum, BoundingSphere, ContainmentType, Plane,
    PlaneIntersectionType, Ray,
)
from ._math import MathHelper, Matrix, Quaternion, Vector2, Vector3, Vector4
from ._title import TitleContainer

__all__ = [
    "BoundingBox", "BoundingFrustum", "BoundingSphere", "Color", "ContainmentType",
    "Curve", "CurveContinuity", "CurveKey", "CurveKeyCollection", "CurveLoopType", "CurveTangent",
    "DisplayOrientation", "DrawableGameComponent", "Game", "GameComponent",
    "GameComponentCollection", "GameComponentCollectionEventArgs", "GameServiceContainer",
    "GameTime", "GameWindow", "GraphicsDeviceInformation", "GraphicsDeviceManager",
    "IDrawable", "IGameComponent", "IGraphicsDeviceManager",
    "IUpdateable", "LaunchParameters", "MathHelper",
    "Matrix", "Plane", "PlaneIntersectionType", "PlayerIndex", "Point",
    "PreparingDeviceSettingsEventArgs", "Quaternion",
    "Ray", "Rectangle", "TitleContainer", "Vector2", "Vector3", "Vector4",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
