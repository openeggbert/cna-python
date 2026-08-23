"""Microsoft.Xna.Framework.Input strict namespace."""

from ._input import (
    ButtonState,
    Buttons,
    GamePad,
    GamePadButtons,
    GamePadDPad,
    GamePadDeadZone,
    GamePadState,
    GamePadThumbSticks,
    GamePadTriggers,
    Keyboard,
    KeyboardState,
    Keys,
    KeyState,
    Mouse,
    MouseState,
)

__all__ = [name for name in globals() if not name.startswith("_")]

for _name in __all__:
    globals()[_name].__module__ = __name__
