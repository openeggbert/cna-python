"""Selected Microsoft.Xna.Framework.GamerServices runtime surface."""

from ._component import GamerServicesComponent

__all__ = ["GamerServicesComponent"]

for _name in __all__:
    globals()[_name].__module__ = __name__
