"""Microsoft.Xna.Framework.Content.Pipeline.Processors strict namespace."""

from ._content import (
    CompiledEffectContent, ModelBoneContent, ModelBoneContentCollection,
    ModelContent, ModelMeshContent, ModelMeshContentCollection,
    ModelMeshPartContent, ModelMeshPartContentCollection, SongContent,
    SoundEffectContent, SpriteFontContent, VertexBufferContent,
    VertexDeclarationContent,
)
from ._enums import (
    EffectProcessorDebugMode, MaterialProcessorDefaultEffect,
    TextureProcessorOutputFormat,
)
from ._processors import (
    EffectProcessor, FontDescriptionProcessor, FontTextureProcessor,
    MaterialProcessor, ModelProcessor, PassThroughProcessor, SongProcessor,
    SoundEffectProcessor, VideoProcessor,
)
from ._texture_processors import (
    ModelTextureProcessor, SpriteTextureProcessor, TextureProcessor,
)

__all__ = [
    "CompiledEffectContent", "EffectProcessor", "EffectProcessorDebugMode",
    "FontDescriptionProcessor", "FontTextureProcessor", "MaterialProcessor",
    "MaterialProcessorDefaultEffect", "ModelBoneContent",
    "ModelBoneContentCollection", "ModelContent", "ModelMeshContent",
    "ModelMeshContentCollection", "ModelMeshPartContent",
    "ModelMeshPartContentCollection", "ModelProcessor", "ModelTextureProcessor",
    "PassThroughProcessor", "SongContent", "SongProcessor",
    "SoundEffectContent", "SoundEffectProcessor", "SpriteFontContent",
    "SpriteTextureProcessor", "TextureProcessor", "TextureProcessorOutputFormat",
    "VertexBufferContent", "VertexDeclarationContent", "VideoProcessor",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
