"""Initial language-local CNA framework types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

from . import _native


@dataclass(frozen=True, slots=True)
class Vector2:
    """A two-dimensional vector implemented entirely in Python."""

    x: float
    y: float

    def __add__(self, other: Vector2) -> Vector2:
        """Return the component-wise sum."""
        if not isinstance(other, Vector2):
            return NotImplemented
        return Vector2(self.x + other.x, self.y + other.y)

    def scale(self, factor: float) -> Vector2:
        """Return this vector multiplied by *factor*."""
        return Vector2(self.x * factor, self.y * factor)

    @property
    def length_squared(self) -> float:
        """Return the squared Euclidean length."""
        return self.x * self.x + self.y * self.y


@dataclass(frozen=True, slots=True)
class Color:
    """A non-premultiplied color with unsigned-byte RGBA channels."""

    red: int
    green: int
    blue: int
    alpha: int = 255

    CORNFLOWER_BLUE: ClassVar[Color]
    WHITE: ClassVar[Color]

    def __post_init__(self) -> None:
        for name in ("red", "green", "blue", "alpha"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer between 0 and 255")


Color.CORNFLOWER_BLUE = Color(100, 149, 237)
Color.WHITE = Color(255, 255, 255)


@dataclass(frozen=True, slots=True)
class GameTime:
    """Timing information supplied to one update or draw callback."""

    total_game_time: timedelta = timedelta()
    elapsed_game_time: timedelta = timedelta()
    running_slowly: bool = False


class Game:
    """Base class for CNA games with a Pythonic lifecycle and context manager."""

    def __init__(self) -> None:
        self._closed = False

    def run(self) -> None:
        """Run CNA's native game loop when the ABI becomes available."""
        self._ensure_open()
        _native.require_available()

    def exit(self) -> None:
        """Request normal game-loop termination."""
        self._ensure_open()

    def initialize(self) -> None:
        """Initialize game-owned state before loading content."""

    def load_content(self) -> None:
        """Load game content."""

    def update(self, game_time: GameTime) -> None:
        """Advance game state."""

    def draw(self, game_time: GameTime) -> None:
        """Draw one frame."""

    def unload_content(self) -> None:
        """Release game-owned content during shutdown."""

    def close(self) -> None:
        """Release the future native game handle; repeated calls are harmless."""
        self._closed = True

    def __enter__(self) -> Game:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("game is already closed")
