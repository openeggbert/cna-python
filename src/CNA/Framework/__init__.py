"""CNA.Framework values and lifecycle types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

from CNA.Interop import NativeUnavailableError, require_available

from . import Content, Graphics, Input


@dataclass(frozen=True, slots=True)
class Vector2:
    """Two-dimensional vector matching the CNA/XNA public member names."""

    X: float
    Y: float

    def Add(self, other: Vector2) -> Vector2:
        """Return the component-wise sum."""
        return Vector2(self.X + other.X, self.Y + other.Y)

    @property
    def LengthSquared(self) -> float:
        """Return the squared Euclidean length."""
        return self.X * self.X + self.Y * self.Y


@dataclass(frozen=True, slots=True)
class Color:
    """Non-premultiplied color with unsigned-byte RGBA channels."""

    R: int
    G: int
    B: int
    A: int = 255

    CornflowerBlue: ClassVar[Color]
    White: ClassVar[Color]

    def __post_init__(self) -> None:
        for name in ("R", "G", "B", "A"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer between 0 and 255")


Color.CornflowerBlue = Color(100, 149, 237)
Color.White = Color(255, 255, 255)


@dataclass(frozen=True, slots=True)
class GameTime:
    """Timing information supplied to Update and Draw."""

    TotalGameTime: timedelta = timedelta()
    ElapsedGameTime: timedelta = timedelta()
    IsRunningSlowly: bool = False


class Game:
    """Base class for games targeting CNA.Framework."""

    def __init__(self) -> None:
        self._closed = False

    def Run(self) -> None:
        """Run the CNA game loop once the canonical ABI is available."""
        self._ensure_open()
        require_available()

    def Exit(self) -> None:
        """Request normal game-loop termination."""
        self._ensure_open()

    def Initialize(self) -> None:
        """Initialize game-owned state."""

    def LoadContent(self) -> None:
        """Load game content."""

    def Update(self, game_time: GameTime) -> None:
        """Advance game state."""

    def Draw(self, game_time: GameTime) -> None:
        """Draw one frame."""

    def UnloadContent(self) -> None:
        """Release game-owned content."""

    def Dispose(self) -> None:
        """Release the future native game handle."""
        self._closed = True

    def __enter__(self) -> Game:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.Dispose()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Game is already disposed")


__all__ = [
    "Color",
    "Content",
    "Game",
    "GameTime",
    "Graphics",
    "Input",
    "NativeUnavailableError",
    "Vector2",
]
