"""Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler namespace."""

from ._compiler import (
    ContentCompiler, ContentTypeWriter, ContentTypeWriterAttribute,
    ContentTypeWriterOfT, ContentWriter,
)

__all__ = [
    "ContentCompiler", "ContentTypeWriter", "ContentTypeWriterAttribute",
    "ContentTypeWriterOfT", "ContentWriter",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
