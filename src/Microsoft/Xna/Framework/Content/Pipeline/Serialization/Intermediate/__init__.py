"""Microsoft.Xna.Framework.Content.Pipeline.Serialization.Intermediate namespace."""

from ._intermediate import (
    ContentTypeSerializer, ContentTypeSerializerAttribute,
    ContentTypeSerializerChildCallback, ContentTypeSerializerOfT,
    IntermediateReader, IntermediateSerializer, IntermediateWriter,
)

#: XNA nests the delegate inside the serializer; Python has no nested-class
#: identity to preserve, so the type is bound both ways: under its own module
#: name, and as ``ContentTypeSerializer.ChildCallback`` where XNA declares it.
ContentTypeSerializer.ChildCallback = ContentTypeSerializerChildCallback

__all__ = [
    "ContentTypeSerializer", "ContentTypeSerializerAttribute",
    "ContentTypeSerializerOfT", "IntermediateReader", "IntermediateSerializer",
    "IntermediateWriter",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
