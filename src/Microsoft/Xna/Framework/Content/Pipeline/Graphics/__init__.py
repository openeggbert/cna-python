"""Microsoft.Xna.Framework.Content.Pipeline.Graphics strict namespace."""

from ._animation import (
    AnimationChannel, AnimationChannelDictionary, AnimationContent,
    AnimationContentDictionary, AnimationKeyframe,
)
from ._bitmap import (
    BitmapContent, Dxt1BitmapContent, Dxt3BitmapContent, Dxt5BitmapContent,
    DxtBitmapContent, MipmapChain, MipmapChainCollection, PixelBitmapContentOfT,
)
from ._font import FontDescription, FontDescriptionStyle
from ._material import (
    AlphaTestMaterialContent, BasicMaterialContent, DualTextureMaterialContent,
    EffectContent, EffectMaterialContent, EnvironmentMapMaterialContent,
    MaterialContent, SkinnedMaterialContent,
)
from ._mesh import MeshBuilder, MeshHelper
from ._node import (
    BoneContent, BoneWeight, BoneWeightCollection, GeometryContent,
    GeometryContentCollection, IndexCollection, MeshContent, NodeContent,
    NodeContentCollection, PositionCollection,
)
from ._texture import (
    Texture2DContent, Texture3DContent, TextureContent, TextureCubeContent,
    TextureReferenceDictionary,
)
from ._vectors import VectorConverter
from ._vertex import (
    IndirectPositionCollection, VertexChannel, VertexChannelCollection,
    VertexChannelNames, VertexChannelOfT, VertexContent,
)

__all__ = [
    "AlphaTestMaterialContent", "AnimationChannel", "AnimationChannelDictionary",
    "AnimationContent", "AnimationContentDictionary", "AnimationKeyframe",
    "BasicMaterialContent", "BitmapContent", "BoneContent", "BoneWeight",
    "BoneWeightCollection", "DualTextureMaterialContent", "Dxt1BitmapContent",
    "Dxt3BitmapContent", "Dxt5BitmapContent", "DxtBitmapContent", "EffectContent",
    "EffectMaterialContent", "EnvironmentMapMaterialContent", "FontDescription",
    "FontDescriptionStyle", "GeometryContent", "GeometryContentCollection",
    "IndexCollection", "IndirectPositionCollection", "MaterialContent",
    "MeshBuilder", "MeshContent", "MeshHelper", "MipmapChain",
    "MipmapChainCollection", "NodeContent", "NodeContentCollection",
    "PixelBitmapContentOfT", "PositionCollection", "SkinnedMaterialContent",
    "Texture2DContent", "Texture3DContent", "TextureContent",
    "TextureCubeContent", "TextureReferenceDictionary", "VectorConverter",
    "VertexChannel", "VertexChannelCollection", "VertexChannelNames",
    "VertexChannelOfT", "VertexContent",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
