"""Microsoft.Xna.Framework.Input.Touch value and runtime surface."""

from ._touch import (
    GestureSample, GestureType, TouchCollection, TouchLocation,
    TouchLocationState, TouchPanel, TouchPanelCapabilities,
)

__all__ = [
    "GestureSample", "GestureType", "TouchCollection", "TouchLocation",
    "TouchLocationState", "TouchPanel", "TouchPanelCapabilities",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
TouchCollection.Enumerator.__module__ = __name__
