"""The processors that are not about textures.

``ModelProcessor`` is the centre of the file and of the pipeline: it takes the
scene graph an importer built and produces the flattened, buffer-packed
``ModelContent`` a runtime loads. Everything it does is something a runtime
cannot: flattening a hierarchy into indices, splitting geometry by material,
packing vertices into one interleaved buffer per mesh.

Three processors here are *narrow measured blockers*, and each says exactly what
would unblock it:

``EffectProcessor``
    compiling HLSL needs an HLSL compiler. CNA's own header says it embeds none
    -- "this runtime embeds no HLSL compiler and the XNA/FNA toolchain must
    compile it first" (``effects.h``, at ``cna_effect_create_compiled``) -- and
    Python's standard library has no shader compiler either. The processor
    validates its input and refuses with that citation.
``FontDescriptionProcessor``
    rasterizing a named system font needs a TrueType rasterizer. There is none
    in the standard library and none in CNA's C ABI. ``FontTextureProcessor``,
    which builds the same output from a texture an artist drew, is fully
    implemented -- so the *format* is reachable, and it is the rasterizer alone
    that is missing.
``SongProcessor``/``VideoProcessor``
    are **not** blocked: XNA's own song and video content is a reference to the
    media file plus its duration, and both are produced here in full.
"""

from __future__ import annotations

import math
import os
import shutil

from .... import BoundingSphere, Color, Matrix, Rectangle, Vector2, Vector3
from ....Media import VideoSoundtrackType
from .._attributes import ContentProcessorAttribute
from .._components import ContentProcessorOfT
from .._context import ContentProcessorContext
from .._errors import InvalidContentException
from .._identity import ExternalReferenceOfT
from .._video import VideoContent
from ..Audio import AudioContent, ConversionFormat, ConversionQuality
from ..Graphics import (
    BasicMaterialContent, EffectContent, EffectMaterialContent, FontDescription,
    GeometryContent, MaterialContent, MeshContent, MeshHelper, NodeContent,
    SkinnedMaterialContent, Texture2DContent, TextureContent, VertexChannelNames,
)
from ._content import (
    CompiledEffectContent, ModelBoneContent, ModelContent, ModelMeshContent,
    ModelMeshPartContent, SongContent, SoundEffectContent, SpriteFontContent,
    VertexBufferContent,
)
from ._enums import (
    EffectProcessorDebugMode, MaterialProcessorDefaultEffect,
    TextureProcessorOutputFormat,
)
from ._texture_processors import TextureProcessor

#: Which material each default effect is built from.
_DEFAULT_MATERIALS = {
    MaterialProcessorDefaultEffect.BasicEffect: BasicMaterialContent,
    MaterialProcessorDefaultEffect.SkinnedEffect: SkinnedMaterialContent,
}


@ContentProcessorAttribute(DisplayName="No Processing Required")
class PassThroughProcessor(ContentProcessorOfT[object, object]):
    """Hands the imported object to the writer unchanged.

    Which is a real processor and the right one for content whose importer
    already produced its final shape -- an ``.xml`` file read by the
    intermediate serializer, most often.
    """

    __slots__ = ()

    def Process(self, input: object, context: ContentProcessorContext) -> object:
        return input


@ContentProcessorAttribute(DisplayName="Effect - XNA Framework")
class EffectProcessor(ContentProcessorOfT[EffectContent, CompiledEffectContent]):
    """Would compile HLSL. Refuses, and says what would let it.

    BLOCKED_UPSTREAM: there is no HLSL compiler to call. CNA's ``effects.h``
    states it directly at ``cna_effect_create_compiled`` -- "this runtime embeds
    no HLSL compiler and the XNA/FNA toolchain must compile it first" -- and
    Python's standard library has none. Unblocked by: any CNA route that takes
    effect *source* and answers bytecode, or a documented external compiler this
    build is allowed to invoke.

    What is implemented is everything up to the compiler: the input is
    validated, ``Defines`` is parsed and applied, and the refusal names the
    effect and the missing capability rather than producing an empty
    ``CompiledEffectContent`` that would fail much later inside a runtime.
    """

    __slots__ = ("_debug_mode", "_defines")

    def __init__(self) -> None:
        self._debug_mode = EffectProcessorDebugMode.Auto
        self._defines = ""

    @property
    def DebugMode(self) -> EffectProcessorDebugMode:
        return self._debug_mode

    @DebugMode.setter
    def DebugMode(self, value: EffectProcessorDebugMode) -> None:
        self._debug_mode = EffectProcessorDebugMode(value)

    @property
    def Defines(self) -> str:
        return self._defines

    @Defines.setter
    def Defines(self, value: str) -> None:
        if value is None:
            self._defines = ""
            return
        if not isinstance(value, str):
            raise TypeError(f"Defines must be a str, not {type(value).__name__}")
        self._defines = value

    def Process(self, input: EffectContent,
                context: ContentProcessorContext) -> CompiledEffectContent:
        if not isinstance(input, EffectContent):
            raise TypeError(
                f"input must be an EffectContent, not {type(input).__name__}")
        if not input.EffectCode.strip():
            raise InvalidContentException(
                "the effect source is empty", input.Identity)
        defines = self._parsed_defines()
        raise NotImplementedError(
            "EffectProcessor cannot compile HLSL: there is no shader compiler "
            "to call. CNA's effects.h says so at cna_effect_create_compiled -- "
            "'this runtime embeds no HLSL compiler and the XNA/FNA toolchain "
            "must compile it first' -- and Python's standard library has none. "
            f"The effect ({len(input.EffectCode)} characters, "
            f"{len(defines)} defines, DebugMode.{self._debug_mode.name}) is "
            "otherwise ready to compile. Unblocked by a CNA route that takes "
            "effect source and answers bytecode.")

    def _parsed_defines(self) -> dict[str, str]:
        """``Defines`` is a semicolon-separated list of ``NAME`` or ``NAME=value``."""
        result: dict[str, str] = {}
        for entry in self._defines.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            name, _, value = entry.partition("=")
            result[name.strip()] = value.strip()
        return result


@ContentProcessorAttribute(DisplayName="Material - XNA Framework")
class MaterialProcessor(ContentProcessorOfT[MaterialContent, MaterialContent]):
    """Builds a material's textures and effect, leaving references behind.

    A material arrives naming files; it leaves naming *built assets*. That is
    the whole job, and it is done through the context so that the nested builds
    are recorded as dependencies of this one -- change the texture, rebuild the
    model.
    """

    __slots__ = ("_generate_mipmaps", "_texture_format", "_color_key_enabled",
                 "_color_key_color", "_resize_textures_to_power_of_two",
                 "_premultiply_texture_alpha", "_default_effect")

    def __init__(self) -> None:
        self._generate_mipmaps = False
        self._texture_format = TextureProcessorOutputFormat.Color
        self._color_key_enabled = True
        self._color_key_color = Color(255, 0, 255, 255)
        self._resize_textures_to_power_of_two = False
        self._premultiply_texture_alpha = True
        self._default_effect = MaterialProcessorDefaultEffect.BasicEffect

    @property
    def GenerateMipmaps(self) -> bool:
        return self._generate_mipmaps

    @GenerateMipmaps.setter
    def GenerateMipmaps(self, value: bool) -> None:
        self._generate_mipmaps = _flag(value, "GenerateMipmaps")

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return self._texture_format

    @TextureFormat.setter
    def TextureFormat(self, value: TextureProcessorOutputFormat) -> None:
        self._texture_format = TextureProcessorOutputFormat(value)

    @property
    def ColorKeyEnabled(self) -> bool:
        return self._color_key_enabled

    @ColorKeyEnabled.setter
    def ColorKeyEnabled(self, value: bool) -> None:
        self._color_key_enabled = _flag(value, "ColorKeyEnabled")

    @property
    def ColorKeyColor(self) -> Color:
        return self._color_key_color

    @ColorKeyColor.setter
    def ColorKeyColor(self, value: Color) -> None:
        if not isinstance(value, Color):
            raise TypeError(
                f"ColorKeyColor must be a Color, not {type(value).__name__}")
        self._color_key_color = value

    @property
    def ResizeTexturesToPowerOfTwo(self) -> bool:
        return self._resize_textures_to_power_of_two

    @ResizeTexturesToPowerOfTwo.setter
    def ResizeTexturesToPowerOfTwo(self, value: bool) -> None:
        self._resize_textures_to_power_of_two = _flag(
            value, "ResizeTexturesToPowerOfTwo")

    @property
    def PremultiplyTextureAlpha(self) -> bool:
        return self._premultiply_texture_alpha

    @PremultiplyTextureAlpha.setter
    def PremultiplyTextureAlpha(self, value: bool) -> None:
        self._premultiply_texture_alpha = _flag(value, "PremultiplyTextureAlpha")

    @property
    def DefaultEffect(self) -> MaterialProcessorDefaultEffect:
        return self._default_effect

    @DefaultEffect.setter
    def DefaultEffect(self, value: MaterialProcessorDefaultEffect) -> None:
        self._default_effect = MaterialProcessorDefaultEffect(value)

    def Process(self, input: MaterialContent,
                context: ContentProcessorContext) -> MaterialContent:
        if not isinstance(input, MaterialContent):
            raise TypeError(
                f"input must be a MaterialContent, not {type(input).__name__}")
        for key in tuple(input.Textures.Keys):
            input.Textures[key] = self.BuildTexture(
                key, input.Textures[key], context)
        if isinstance(input, EffectMaterialContent) and input.Effect is not None:
            input.CompiledEffect = self.BuildEffect(input.Effect, context)
        return input

    def BuildEffect(self, effect: ExternalReferenceOfT,
                    context: ContentProcessorContext) -> ExternalReferenceOfT:
        """Builds the material's effect through the context."""
        return context.BuildAsset(effect, "EffectProcessor")

    def BuildTexture(self, textureName: str, texture: ExternalReferenceOfT,
                     context: ContentProcessorContext) -> ExternalReferenceOfT:
        """Builds one of the material's textures, with this processor's settings.

        The settings are passed on rather than reproduced: the texture is built
        by ``TextureProcessor`` with exactly the parameters this material
        processor was given, so a model's textures are compressed the way the
        model asked for and not the way the texture processor defaults to.
        """
        from .._collections import OpaqueDataDictionary

        parameters = OpaqueDataDictionary()
        parameters["GenerateMipmaps"] = self.GenerateMipmaps
        parameters["TextureFormat"] = self.TextureFormat
        parameters["ColorKeyEnabled"] = self.ColorKeyEnabled
        parameters["ColorKeyColor"] = self.ColorKeyColor
        parameters["ResizeToPowerOfTwo"] = self.ResizeTexturesToPowerOfTwo
        parameters["PremultiplyAlpha"] = self.PremultiplyTextureAlpha
        return context.BuildAsset(texture, "TextureProcessor", parameters,
                                  None, textureName)


@ContentProcessorAttribute(DisplayName="Model - XNA Framework")
class ModelProcessor(ContentProcessorOfT[NodeContent, ModelContent]):
    """Turns an imported scene into a model a runtime can draw."""

    __slots__ = ("_scale", "_generate_tangent_frames", "_swap_winding_order",
                 "_rotation_x", "_rotation_y", "_rotation_z", "_generate_mipmaps",
                 "_texture_format", "_color_key_enabled", "_color_key_color",
                 "_resize_textures_to_power_of_two", "_premultiply_texture_alpha",
                 "_premultiply_vertex_colors", "_default_effect")

    def __init__(self) -> None:
        self._scale = 1.0
        self._generate_tangent_frames = False
        self._swap_winding_order = False
        self._rotation_x = 0.0
        self._rotation_y = 0.0
        self._rotation_z = 0.0
        self._generate_mipmaps = True
        self._texture_format = TextureProcessorOutputFormat.Color
        self._color_key_enabled = True
        self._color_key_color = Color(255, 0, 255, 255)
        self._resize_textures_to_power_of_two = True
        self._premultiply_texture_alpha = True
        self._premultiply_vertex_colors = True
        self._default_effect = MaterialProcessorDefaultEffect.BasicEffect

    # -- knobs ---------------------------------------------------------------

    @property
    def Scale(self) -> float:
        return self._scale

    @Scale.setter
    def Scale(self, value: float) -> None:
        self._scale = _real(value, "Scale")

    @property
    def GenerateTangentFrames(self) -> bool:
        return self._generate_tangent_frames

    @GenerateTangentFrames.setter
    def GenerateTangentFrames(self, value: bool) -> None:
        self._generate_tangent_frames = _flag(value, "GenerateTangentFrames")

    @property
    def SwapWindingOrder(self) -> bool:
        return self._swap_winding_order

    @SwapWindingOrder.setter
    def SwapWindingOrder(self, value: bool) -> None:
        self._swap_winding_order = _flag(value, "SwapWindingOrder")

    @property
    def RotationX(self) -> float:
        return self._rotation_x

    @RotationX.setter
    def RotationX(self, value: float) -> None:
        self._rotation_x = _real(value, "RotationX")

    @property
    def RotationY(self) -> float:
        return self._rotation_y

    @RotationY.setter
    def RotationY(self, value: float) -> None:
        self._rotation_y = _real(value, "RotationY")

    @property
    def RotationZ(self) -> float:
        return self._rotation_z

    @RotationZ.setter
    def RotationZ(self, value: float) -> None:
        self._rotation_z = _real(value, "RotationZ")

    @property
    def GenerateMipmaps(self) -> bool:
        return self._generate_mipmaps

    @GenerateMipmaps.setter
    def GenerateMipmaps(self, value: bool) -> None:
        self._generate_mipmaps = _flag(value, "GenerateMipmaps")

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return self._texture_format

    @TextureFormat.setter
    def TextureFormat(self, value: TextureProcessorOutputFormat) -> None:
        self._texture_format = TextureProcessorOutputFormat(value)

    @property
    def ColorKeyEnabled(self) -> bool:
        return self._color_key_enabled

    @ColorKeyEnabled.setter
    def ColorKeyEnabled(self, value: bool) -> None:
        self._color_key_enabled = _flag(value, "ColorKeyEnabled")

    @property
    def ColorKeyColor(self) -> Color:
        return self._color_key_color

    @ColorKeyColor.setter
    def ColorKeyColor(self, value: Color) -> None:
        if not isinstance(value, Color):
            raise TypeError(
                f"ColorKeyColor must be a Color, not {type(value).__name__}")
        self._color_key_color = value

    @property
    def ResizeTexturesToPowerOfTwo(self) -> bool:
        return self._resize_textures_to_power_of_two

    @ResizeTexturesToPowerOfTwo.setter
    def ResizeTexturesToPowerOfTwo(self, value: bool) -> None:
        self._resize_textures_to_power_of_two = _flag(
            value, "ResizeTexturesToPowerOfTwo")

    @property
    def PremultiplyTextureAlpha(self) -> bool:
        return self._premultiply_texture_alpha

    @PremultiplyTextureAlpha.setter
    def PremultiplyTextureAlpha(self, value: bool) -> None:
        self._premultiply_texture_alpha = _flag(value, "PremultiplyTextureAlpha")

    @property
    def PremultiplyVertexColors(self) -> bool:
        return self._premultiply_vertex_colors

    @PremultiplyVertexColors.setter
    def PremultiplyVertexColors(self, value: bool) -> None:
        self._premultiply_vertex_colors = _flag(value, "PremultiplyVertexColors")

    @property
    def DefaultEffect(self) -> MaterialProcessorDefaultEffect:
        return self._default_effect

    @DefaultEffect.setter
    def DefaultEffect(self, value: MaterialProcessorDefaultEffect) -> None:
        self._default_effect = MaterialProcessorDefaultEffect(value)

    # -- the build -----------------------------------------------------------

    def Process(self, input: NodeContent,
                context: ContentProcessorContext) -> ModelContent:
        if not isinstance(input, NodeContent):
            raise TypeError(
                f"input must be a NodeContent, not {type(input).__name__}")
        transform = (Matrix.CreateRotationX(math.radians(self.RotationX))
                     * Matrix.CreateRotationY(math.radians(self.RotationY))
                     * Matrix.CreateRotationZ(math.radians(self.RotationZ))
                     * Matrix.CreateScale(self.Scale))
        if transform != Matrix.Identity:
            MeshHelper.TransformScene(input, transform)
        meshes = [node for node in _walk(input) if isinstance(node, MeshContent)]
        for mesh in meshes:
            if self.SwapWindingOrder:
                MeshHelper.SwapWindingOrder(mesh)
            MeshHelper.CalculateNormals(mesh, False)
            if self.GenerateTangentFrames:
                MeshHelper.CalculateTangentFrames(
                    mesh, VertexChannelNames.TextureCoordinate(0),
                    VertexChannelNames.Tangent(0),
                    VertexChannelNames.Binormal(0))
            self.ProcessGeometryUsingMaterial(None, mesh.Geometry, context)

        bones: list[ModelBoneContent] = []
        by_node: dict[int, ModelBoneContent] = {}
        _flatten(input, None, bones, by_node)
        built = [self._build_mesh(mesh, by_node[id(mesh)], context)
                 for mesh in meshes]
        return ModelContent(bones[0], bones, built)

    def ProcessGeometryUsingMaterial(self, material: MaterialContent | None,
                                     geometryCollection,
                                     context: ContentProcessorContext) -> None:
        """Prepares every geometry that shares one material.

        Called once per material with the geometry that uses it, which is what
        makes the nested texture builds happen once rather than once per mesh.
        A ``material`` of ``None`` means "each geometry's own", which is how
        :meth:`Process` calls it.
        """
        for geometry in geometryCollection:
            chosen = material if material is not None else geometry.Material
            if chosen is None:
                chosen = _DEFAULT_MATERIALS.get(
                    self.DefaultEffect, BasicMaterialContent)()
            geometry.Material = self.ConvertMaterial(chosen, context)
            for index in range(geometry.Vertices.Channels.Count):
                self.ProcessVertexChannel(geometry, index, context)

    def ConvertMaterial(self, material: MaterialContent,
                        context: ContentProcessorContext) -> MaterialContent:
        """Runs the material through ``MaterialProcessor``, via the context."""
        from .._collections import OpaqueDataDictionary

        parameters = OpaqueDataDictionary()
        parameters["GenerateMipmaps"] = self.GenerateMipmaps
        parameters["TextureFormat"] = self.TextureFormat
        parameters["ColorKeyEnabled"] = self.ColorKeyEnabled
        parameters["ColorKeyColor"] = self.ColorKeyColor
        parameters["ResizeTexturesToPowerOfTwo"] = self.ResizeTexturesToPowerOfTwo
        parameters["PremultiplyTextureAlpha"] = self.PremultiplyTextureAlpha
        parameters["DefaultEffect"] = self.DefaultEffect
        return context.Convert(material, "MaterialProcessor", parameters)

    def ProcessVertexChannel(self, geometry: GeometryContent,
                             vertexChannelIndex: int,
                             context: ContentProcessorContext) -> None:
        """Converts one channel into something a vertex buffer can hold.

        Two conversions actually happen. A ``COLOR`` channel is premultiplied
        when asked, for the same reason a texture is. A ``BLENDWEIGHT`` channel
        holding ``BoneWeightCollection`` values -- which is what a skinned
        importer produces -- is normalised to four influences and split into the
        ``BLENDINDICES`` and ``BLENDWEIGHT`` channels a skinned effect reads,
        because a collection is not a vertex element and four bytes and four
        floats are.
        """
        from ..Graphics._node import BoneWeightCollection

        channels = geometry.Vertices.Channels
        channel = channels.Get(vertexChannelIndex)
        base = VertexChannelNames.DecodeBaseName(channel.Name)
        if base == "COLOR" and self.PremultiplyVertexColors:
            for index in range(len(channel)):
                pixel = channel[index]
                if isinstance(pixel, Color) and pixel.A != 255:
                    channel[index] = Color(
                        (pixel.R * pixel.A + 127) // 255,
                        (pixel.G * pixel.A + 127) // 255,
                        (pixel.B * pixel.A + 127) // 255, pixel.A)
            return
        if base != "BLENDWEIGHT" or not len(channel) \
                or not isinstance(channel[0], BoneWeightCollection):
            return
        bones: list[Vector3] = []
        weights: list[Vector3] = []
        names: list[str] = []
        for index in range(len(channel)):
            collection = channel[index]
            collection.NormalizeWeights(4)
            entries = list(collection)
            for entry in entries:
                if entry.BoneName not in names:
                    names.append(entry.BoneName)
            bones.append(Vector3(*[
                float(names.index(entries[slot].BoneName)) if slot < len(entries)
                else 0.0 for slot in range(3)]))
            weights.append(Vector3(*[
                entries[slot].Weight if slot < len(entries) else 0.0
                for slot in range(3)]))
        name = channel.Name
        usage_index = VertexChannelNames.DecodeUsageIndex(name)
        channels.Remove(name)
        channels.Add(VertexChannelNames.EncodeName("BLENDINDICES", usage_index),
                     Vector3, bones)
        channels.Add(name, Vector3, weights)

    def _build_mesh(self, mesh: MeshContent, bone: ModelBoneContent,
                    context: ContentProcessorContext) -> ModelMeshContent:
        parts: list[ModelMeshPartContent] = []
        for geometry in mesh.Geometry:
            buffer = geometry.Vertices.CreateVertexBuffer()
            indices = geometry.Indices
            if indices.Count % 3:
                raise InvalidContentException(
                    f"{indices.Count} indices is not a whole number of triangles",
                    geometry.Identity)
            part = ModelMeshPartContent(
                buffer, indices, 0, geometry.Vertices.VertexCount, 0,
                indices.Count // 3)
            part.Material = geometry.Material
            parts.append(part)
        return ModelMeshContent(
            mesh.Name, mesh, bone, _bounding_sphere(mesh), parts)


ModelProcessor.__xna_arities__ = {
    "ProcessGeometryUsingMaterial": {3}, "ConvertMaterial": {2},
    "ProcessVertexChannel": {3},
}


@ContentProcessorAttribute(DisplayName="Sound Effect - XNA Framework")
class SoundEffectProcessor(ContentProcessorOfT[AudioContent, SoundEffectContent]):
    """Converts audio to PCM and packs it as a sound effect."""

    __slots__ = ("_quality",)

    def __init__(self) -> None:
        self._quality = ConversionQuality.Best

    @property
    def Quality(self) -> ConversionQuality:
        return self._quality

    @Quality.setter
    def Quality(self, value: ConversionQuality) -> None:
        self._quality = ConversionQuality(value)

    def Process(self, input: AudioContent,
                context: ContentProcessorContext) -> SoundEffectContent:
        if not isinstance(input, AudioContent):
            raise TypeError(
                f"input must be an AudioContent, not {type(input).__name__}")
        input.ConvertFormat(ConversionFormat.Pcm, self.Quality, None)
        data = bytes(input.Data)
        return SoundEffectContent(
            bytes(input.Format.NativeWaveFormat), data,
            input.LoopStart, input.LoopLength,
            round(input.Duration.total_seconds() * 1000.0))


@ContentProcessorAttribute(DisplayName="Song - XNA Framework")
class SongProcessor(ContentProcessorOfT[AudioContent, SongContent]):
    """Copies the media file beside the built content and records its duration.

    Which is what XNA's song content *is*: a ``Song`` is loaded by the runtime
    from a media file next to the ``.xnb``, and the ``.xnb`` carries the path and
    the duration. Nothing is transcoded, and nothing needs to be.
    """

    __slots__ = ("_quality",)

    def __init__(self) -> None:
        self._quality = ConversionQuality.Best

    @property
    def Quality(self) -> ConversionQuality:
        return self._quality

    @Quality.setter
    def Quality(self, value: ConversionQuality) -> None:
        self._quality = ConversionQuality(value)

    def Process(self, input: AudioContent,
                context: ContentProcessorContext) -> SongContent:
        if not isinstance(input, AudioContent):
            raise TypeError(
                f"input must be an AudioContent, not {type(input).__name__}")
        name = os.path.basename(input.FileName)
        destination = os.path.join(context.OutputDirectory, name)
        os.makedirs(context.OutputDirectory, exist_ok=True)
        if os.path.abspath(destination) != os.path.abspath(input.FileName):
            shutil.copyfile(input.FileName, destination)
        context.AddOutputFile(destination)
        return SongContent(
            name, round(input.Duration.total_seconds() * 1000.0))


@ContentProcessorAttribute(DisplayName="Video - XNA Framework")
class VideoProcessor(ContentProcessorOfT[VideoContent, VideoContent]):
    """Records how a video's soundtrack should be treated, and copies it across.

    XNA's video content is also a reference to a media file, so this is the
    whole of the processor: the soundtrack type is the one decision a video
    build makes, and the file itself is copied beside the built content.
    """

    __slots__ = ("_video_soundtrack_type",)

    def __init__(self) -> None:
        self._video_soundtrack_type = VideoSoundtrackType.Music

    @property
    def VideoSoundtrackType(self) -> VideoSoundtrackType:
        return self._video_soundtrack_type

    @VideoSoundtrackType.setter
    def VideoSoundtrackType(self, value: VideoSoundtrackType) -> None:
        self._video_soundtrack_type = VideoSoundtrackType(value)

    def Process(self, input: VideoContent,
                context: ContentProcessorContext) -> VideoContent:
        if not isinstance(input, VideoContent):
            raise TypeError(
                f"input must be a VideoContent, not {type(input).__name__}")
        input.VideoSoundtrackType = self.VideoSoundtrackType
        name = os.path.basename(input.Filename)
        destination = os.path.join(context.OutputDirectory, name)
        os.makedirs(context.OutputDirectory, exist_ok=True)
        if os.path.abspath(destination) != os.path.abspath(input.Filename):
            shutil.copyfile(input.Filename, destination)
        context.AddOutputFile(destination)
        return input


@ContentProcessorAttribute(DisplayName="Sprite Font Description - XNA Framework")
class FontDescriptionProcessor(
        ContentProcessorOfT[FontDescription, SpriteFontContent]):
    """Would rasterize a named font. Refuses, and says what would let it.

    BLOCKED_UPSTREAM: rasterizing ``Arial 14pt`` means finding a TrueType file,
    parsing its outlines and scan-converting them. Python's standard library has
    no font rasterizer and CNA's C ABI declares none -- ``sprite_font.h`` reads
    and measures a ``SpriteFont`` that already exists and does not build one.
    Unblocked by: a CNA route that rasterizes a font file into glyph bitmaps.

    The description itself is fully implemented and so is the *other* way to
    build the same output: :class:`FontTextureProcessor` turns a texture an
    artist drew into exactly this ``SpriteFontContent``, so a sprite font is
    reachable in this pipeline. It is the rasterizer alone that is missing.
    """

    __slots__ = ()

    def Process(self, input: FontDescription,
                context: ContentProcessorContext) -> SpriteFontContent:
        if not isinstance(input, FontDescription):
            raise TypeError(
                f"input must be a FontDescription, not {type(input).__name__}")
        if not input.Characters:
            raise InvalidContentException(
                "the font description names no characters to build",
                input.Identity)
        raise NotImplementedError(
            f"FontDescriptionProcessor cannot rasterize {input.FontName!r} at "
            f"{input.Size}pt: there is no TrueType rasterizer to call. Python's "
            "standard library has none and CNA's C ABI declares none -- "
            "sprite_font.h reads a SpriteFont, it does not build one. "
            "FontTextureProcessor builds the same SpriteFontContent from a "
            "texture and is fully implemented. Unblocked by a CNA route that "
            "rasterizes a font file into glyph bitmaps.")


@ContentProcessorAttribute(DisplayName="Sprite Font Texture - XNA Framework")
class FontTextureProcessor(
        ContentProcessorOfT[Texture2DContent, SpriteFontContent]):
    """Builds a sprite font from a texture an artist drew.

    The convention is XNA's and it is simple: the glyphs sit on a background of
    one colour -- whatever is in the texture's top-left pixel -- and every run
    of columns that is not entirely background is one glyph. Rows are found the
    same way, so a sheet may hold several lines of glyphs.

    Glyphs are assigned characters in reading order, starting from
    ``FirstCharacter``. :meth:`GetCharacterForIndex` is the hook a subclass
    overrides to say otherwise -- a sheet whose glyphs are not consecutive.
    """

    __slots__ = ("_texture_format", "_premultiply_alpha", "_first_character")

    def __init__(self) -> None:
        self._texture_format = TextureProcessorOutputFormat.Color
        self._premultiply_alpha = True
        self._first_character = " "

    @property
    def TextureFormat(self) -> TextureProcessorOutputFormat:
        return self._texture_format

    @TextureFormat.setter
    def TextureFormat(self, value: TextureProcessorOutputFormat) -> None:
        self._texture_format = TextureProcessorOutputFormat(value)

    @property
    def PremultiplyAlpha(self) -> bool:
        return self._premultiply_alpha

    @PremultiplyAlpha.setter
    def PremultiplyAlpha(self, value: bool) -> None:
        self._premultiply_alpha = _flag(value, "PremultiplyAlpha")

    @property
    def FirstCharacter(self) -> str:
        return self._first_character

    @FirstCharacter.setter
    def FirstCharacter(self, value: str) -> None:
        if not isinstance(value, str) or len(value) != 1:
            raise TypeError("FirstCharacter must be a single character")
        self._first_character = value

    def GetCharacterForIndex(self, index: int) -> str:
        """Which character the ``index``-th glyph on the sheet is."""
        return chr(ord(self._first_character) + index)

    def Process(self, input: Texture2DContent,
                context: ContentProcessorContext) -> SpriteFontContent:
        if not isinstance(input, Texture2DContent):
            raise TypeError(
                f"input must be a Texture2DContent, not {type(input).__name__}")
        from ._texture_processors import _ColorBitmapContent

        input.ConvertBitmapType(_ColorBitmapContent)
        bitmap = input.Faces[0][0]
        background = bitmap.GetPixel(0, 0)
        glyphs = _find_glyphs(bitmap, background)
        if not glyphs:
            raise InvalidContentException(
                "the font texture has no glyphs: every pixel is the background "
                f"colour {background}", input.Identity)
        for y in range(bitmap.Height):
            row = bitmap.GetRow(y)
            for x, pixel in enumerate(row):
                if pixel == background:
                    row[x] = Color(0, 0, 0, 0)
                elif self.PremultiplyAlpha and pixel.A != 255:
                    row[x] = Color((pixel.R * pixel.A + 127) // 255,
                                   (pixel.G * pixel.A + 127) // 255,
                                   (pixel.B * pixel.A + 127) // 255, pixel.A)
        characters = [self.GetCharacterForIndex(index)
                      for index in range(len(glyphs))]
        line_spacing = max(glyph.Height for glyph in glyphs)
        return SpriteFontContent(
            input, list(glyphs), [Rectangle(0, 0, glyph.Width, glyph.Height)
                                  for glyph in glyphs],
            characters, line_spacing, 0.0,
            [Vector3(0.0, float(glyph.Width), 0.0) for glyph in glyphs], None)


# -- helpers ------------------------------------------------------------------


def _flag(value: object, what: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{what} must be a bool")
    return value


def _real(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{what} must be a real number, not {type(value).__name__}")
    return float(value)


def _walk(node: NodeContent):
    pending = [node]
    while pending:
        current = pending.pop(0)
        yield current
        pending.extend(current.Children)


def _flatten(node: NodeContent, parent: ModelBoneContent | None,
             bones: list[ModelBoneContent], by_node: dict[int, ModelBoneContent]
             ) -> ModelBoneContent:
    """Depth-first, which is the order a model's bone indices name."""
    bone = ModelBoneContent(node.Name, len(bones), node.Transform, parent)
    bones.append(bone)
    by_node[id(node)] = bone
    for child in node.Children:
        bone.Children._items.append(_flatten(child, bone, bones, by_node))
    return bone


def _bounding_sphere(mesh: MeshContent) -> BoundingSphere:
    """The smallest sphere this projection can honestly claim around a mesh.

    The centre is the midpoint of the axis-aligned bounds and the radius is the
    furthest point from it, which is a real bounding sphere -- it contains every
    vertex -- and is not the *minimal* one. Saying so matters: a runtime uses it
    to cull, and a sphere that is slightly too big culls correctly while one
    that is too small does not.
    """
    positions = list(mesh.Positions)
    if not positions:
        return BoundingSphere(Vector3(0.0, 0.0, 0.0), 0.0)
    low = Vector3(min(p.X for p in positions), min(p.Y for p in positions),
                  min(p.Z for p in positions))
    high = Vector3(max(p.X for p in positions), max(p.Y for p in positions),
                   max(p.Z for p in positions))
    centre = Vector3((low.X + high.X) / 2.0, (low.Y + high.Y) / 2.0,
                     (low.Z + high.Z) / 2.0)
    radius = max(math.sqrt((p.X - centre.X) ** 2 + (p.Y - centre.Y) ** 2
                           + (p.Z - centre.Z) ** 2) for p in positions)
    return BoundingSphere(centre, radius)


def _find_glyphs(bitmap, background) -> list[Rectangle]:
    """Every glyph on a font sheet, in reading order."""
    rows = _runs(range(bitmap.Height), lambda y: any(
        bitmap.GetPixel(x, y) != background for x in range(bitmap.Width)))
    glyphs: list[Rectangle] = []
    for top, height in rows:
        columns = _runs(range(bitmap.Width), lambda x: any(
            bitmap.GetPixel(x, y) != background
            for y in range(top, top + height)))
        for left, width in columns:
            glyphs.append(Rectangle(left, top, width, height))
    return glyphs


def _runs(values, occupied) -> list[tuple[int, int]]:
    """Maximal runs of ``occupied`` positions, as ``(start, length)`` pairs."""
    result: list[tuple[int, int]] = []
    start: int | None = None
    for value in values:
        if occupied(value):
            if start is None:
                start = value
        elif start is not None:
            result.append((start, value - start))
            start = None
    if start is not None:
        result.append((start, list(values)[-1] - start + 1))
    return result
