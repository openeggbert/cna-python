"""Microsoft.Xna.Framework.Content.Pipeline strict namespace.

XNA's **design-time** surface: the types a content build is written against.
Deliberately a subpackage of ``Microsoft.Xna.Framework.Content`` and deliberately
not imported by it, which is what keeps a game's runtime free of the pipeline.
Importing ``Microsoft.Xna.Framework.Content`` loads a ``ContentManager`` and
nothing from here; importing this loads the pipeline and, through it, the runtime
types it produces content for. The dependency runs one way and a test asserts it.

Nothing here needs a CNA library. A content build is a program that reads files
and writes files, and it runs wherever Python does.
"""

from ._attributes import ContentImporterAttribute, ContentProcessorAttribute
from ._collections import (
    ChildCollectionOfT, NamedValueDictionaryOfT, OpaqueDataDictionary,
)
from ._components import (
    ContentImporterOfT, ContentProcessorOfT, IContentImporter, IContentProcessor,
    PipelineComponentScanner, ProcessorParameter, ProcessorParameterCollection,
)
from ._context import ContentImporterContext, ContentProcessorContext
from ._errors import InvalidContentException, PipelineException
from ._identity import ContentIdentity, ContentItem, ExternalReferenceOfT
from ._importers import (
    EffectImporter, FbxImporter, FontDescriptionImporter, Mp3Importer,
    TextureImporter, WavImporter, WmaImporter, WmvImporter, XImporter,
    XmlImporter,
)
from ._logging import ContentBuildLogger
from ._target import TargetPlatform
from ._video import VideoContent

__all__ = [
    "ChildCollectionOfT", "ContentBuildLogger", "ContentIdentity",
    "ContentImporterAttribute", "ContentImporterContext", "ContentImporterOfT",
    "ContentItem", "ContentProcessorAttribute", "ContentProcessorContext",
    "ContentProcessorOfT", "EffectImporter", "ExternalReferenceOfT",
    "FbxImporter", "FontDescriptionImporter", "IContentImporter",
    "IContentProcessor", "InvalidContentException", "Mp3Importer",
    "NamedValueDictionaryOfT", "OpaqueDataDictionary", "PipelineComponentScanner",
    "PipelineException", "ProcessorParameter", "ProcessorParameterCollection",
    "TargetPlatform", "TextureImporter", "VideoContent", "WavImporter",
    "WmaImporter", "WmvImporter", "XImporter", "XmlImporter",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
