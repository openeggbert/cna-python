"""Microsoft.Xna.Framework.Graphics strict namespace."""

from ._device import (
    DepthFormat,
    GraphicsDevice,
    GraphicsProfile,
    SpriteEffects,
    SpriteSortMode,
    SurfaceFormat,
    Viewport,
)
from ._resources import GraphicsResource, SpriteBatch, Texture, Texture2D

__all__ = [
    "DepthFormat",
    "GraphicsDevice",
    "GraphicsProfile",
    "GraphicsResource",
    "SpriteBatch",
    "SpriteEffects",
    "SpriteSortMode",
    "SurfaceFormat",
    "Texture2D",
    "Texture",
    "Viewport",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
