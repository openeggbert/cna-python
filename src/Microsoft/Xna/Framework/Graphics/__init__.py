"""Microsoft.Xna.Framework.Graphics strict namespace."""

from ._device import (
    Blend, BlendFunction, BufferUsage, ClearOptions, ColorWriteChannels,
    CompareFunction, CubeMapFace, CullMode,
    DepthFormat,
    FillMode,
    GraphicsDevice, IGraphicsDeviceService,
    GraphicsDeviceStatus,
    GraphicsProfile,
    IndexElementSize, PresentInterval, PrimitiveType, RenderTargetUsage,
    SetDataOptions,
    SpriteEffects,
    SpriteSortMode,
    StencilOperation,
    SurfaceFormat,
    TextureAddressMode, TextureFilter, VertexElementFormat, VertexElementUsage,
    Viewport,
)
from ._resources import (
    GraphicsResource, ResourceCreatedEventArgs, ResourceDestroyedEventArgs,
    SpriteBatch, SpriteFont, Texture, Texture2D,
)
from ._display import (
    DeviceLostException, DeviceNotResetException, DisplayMode, DisplayModeCollection,
    GraphicsAdapter, NoSuitableGraphicsDeviceException, PresentationParameters,
)
from ._states import (
    BlendState, DepthStencilState, RasterizerState, SamplerState,
    SamplerStateCollection, TextureCollection,
)
from ._vertices import (
    DynamicIndexBuffer, DynamicVertexBuffer, IndexBuffer, IVertexType,
    VertexBuffer, VertexBufferBinding, VertexDeclaration, VertexElement,
    VertexPositionColor, VertexPositionColorTexture, VertexPositionNormalTexture,
    VertexPositionTexture,
)
from ._render_targets import RenderTarget2D, RenderTargetBinding, RenderTargetCube
from ._queries import OcclusionQuery
from ._effects import (AlphaTestEffect, BasicEffect, DirectionalLight, DualTextureEffect,
    Effect, EffectAnnotation, EffectAnnotationCollection, EffectMaterial, EffectParameter,
    EffectParameterClass, EffectParameterCollection, EffectParameterType, EffectPass,
    EffectPassCollection, EffectTechnique, EffectTechniqueCollection, EnvironmentMapEffect,
    IEffectFog, IEffectLights, IEffectMatrices, SkinnedEffect)
from ._model import (Model, ModelBone, ModelBoneCollection, ModelEffectCollection, ModelMesh,
    ModelMeshCollection, ModelMeshPart, ModelMeshPartCollection, ModelBoneCollectionEnumerator,
    ModelEffectCollectionEnumerator, ModelMeshCollectionEnumerator, ModelMeshPartCollectionEnumerator)
from ._texture_volume import Texture3D, TextureCube

__all__ = [
    "Blend", "BlendFunction", "BlendState", "BufferUsage", "ClearOptions", "ColorWriteChannels",
    "CompareFunction", "CubeMapFace", "CullMode", "DepthFormat", "DepthStencilState", "FillMode",
    "DeviceLostException", "DeviceNotResetException", "DisplayMode", "DisplayModeCollection",
    "GraphicsAdapter", "GraphicsDevice", "IGraphicsDeviceService",
    "GraphicsProfile",
    "GraphicsDeviceStatus", "IndexElementSize", "PresentInterval", "PrimitiveType",
    "DynamicIndexBuffer", "DynamicVertexBuffer", "IndexBuffer", "IVertexType",
    "OcclusionQuery", "RasterizerState", "RenderTarget2D", "RenderTargetBinding", "RenderTargetCube", "RenderTargetUsage",
    "SamplerState", "SamplerStateCollection",
    "SetDataOptions", "StencilOperation",
    "GraphicsResource", "NoSuitableGraphicsDeviceException", "PresentationParameters",
    "ResourceCreatedEventArgs", "ResourceDestroyedEventArgs",
    "SpriteBatch", "SpriteFont",
    "SpriteEffects",
    "SpriteSortMode",
    "SurfaceFormat",
    "TextureAddressMode", "TextureCollection", "TextureFilter", "VertexElementFormat", "VertexElementUsage",
    "VertexBuffer", "VertexBufferBinding", "VertexDeclaration", "VertexElement",
    "VertexPositionColor", "VertexPositionColorTexture", "VertexPositionNormalTexture",
    "VertexPositionTexture",
    "Texture2D",
    "Texture3D", "TextureCube", "Effect", "EffectAnnotation", "EffectAnnotationCollection",
    "EffectMaterial", "EffectParameter", "EffectParameterClass", "EffectParameterCollection",
    "EffectParameterType", "EffectPass", "EffectPassCollection", "EffectTechnique",
    "EffectTechniqueCollection", "AlphaTestEffect", "BasicEffect", "DirectionalLight",
    "DualTextureEffect", "EnvironmentMapEffect", "SkinnedEffect", "IEffectFog", "IEffectLights",
    "IEffectMatrices", "Model", "ModelBone", "ModelBoneCollection", "ModelEffectCollection",
    "ModelMesh", "ModelMeshCollection", "ModelMeshPart", "ModelMeshPartCollection",
    "ModelBoneCollectionEnumerator", "ModelEffectCollectionEnumerator", "ModelMeshCollectionEnumerator",
    "ModelMeshPartCollectionEnumerator",
    "Texture",
    "Viewport",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
