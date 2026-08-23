"""Microsoft.Xna.Framework.Content strict namespace."""

from ._content import ContentLoadException, ContentManager

__all__ = ["ContentLoadException", "ContentManager"]

for _name in __all__:
    globals()[_name].__module__ = __name__
