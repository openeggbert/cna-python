"""Microsoft.Xna.Framework.Content strict namespace."""

from ._content import (
    ContentLoadException,
    ContentManager,
    ContentReader,
    ContentSerializerAttribute,
    ContentSerializerCollectionItemNameAttribute,
    ContentSerializerIgnoreAttribute,
    ContentSerializerRuntimeTypeAttribute,
    ContentSerializerTypeVersionAttribute,
    ContentTypeReader,
    ContentTypeReaderManager,
    ContentTypeReaderOfT,
    ResourceContentManager,
)

__all__ = [
    "ContentLoadException", "ContentManager", "ContentReader",
    "ContentSerializerAttribute", "ContentSerializerCollectionItemNameAttribute",
    "ContentSerializerIgnoreAttribute", "ContentSerializerRuntimeTypeAttribute",
    "ContentSerializerTypeVersionAttribute", "ContentTypeReader",
    "ContentTypeReaderManager", "ContentTypeReaderOfT", "ResourceContentManager",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
