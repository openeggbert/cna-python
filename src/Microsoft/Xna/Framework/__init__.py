"""Microsoft.Xna.Framework compatibility facade backed by CNA."""

from CNA.Framework import Color, Game, GameTime, Vector2

from . import Content, Graphics, Input

__all__ = [
    "Color",
    "Content",
    "Game",
    "GameTime",
    "Graphics",
    "Input",
    "Vector2",
]
