"""Private XNA 4.0 runtime content readers for the implemented public surface."""

from __future__ import annotations

from datetime import timedelta
from pathlib import PurePosixPath
import re
import struct
from typing import Callable

from .._geometry import Color, Point, Rectangle
from .._math import Matrix, Quaternion, Vector2, Vector3, Vector4
from ._content import ContentLoadException, ContentReader, ContentTypeReader


_PREFIX = "Microsoft.Xna.Framework.Content."


class _Reader(ContentTypeReader):
    def __init__(self, target_type: type, read: Callable[[ContentReader], object]) -> None:
        super().__init__(target_type)
        self._read_value = read

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        return self._read_value(input)


class _TimeSpanReader(ContentTypeReader):
    def __init__(self) -> None:
        super().__init__(timedelta)

    def Read(self, input: ContentReader, existingInstance: object) -> timedelta:
        ticks = input.ReadInt64()
        # timedelta has microsecond precision. Reject rather than silently round an XNA
        # TimeSpan that cannot be represented by the formal Python mapping.
        if ticks % 10:
            raise input._failure(
                f"TimeSpan value {ticks} ticks cannot be represented exactly as datetime.timedelta"
            )
        try:
            return timedelta(microseconds=ticks // 10)
        except OverflowError as error:
            raise input._failure(f"TimeSpan value {ticks} ticks is outside datetime.timedelta") from error


class _VideoReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Media import Video
        super().__init__(Video)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Media import Video, VideoSoundtrackType
        if existingInstance is not None:
            raise ValueError("VideoReader cannot deserialize into an existing Video")
        file_name = input.ReadObject()
        duration_milliseconds = input.ReadObject()
        width = input.ReadObject()
        height = input.ReadObject()
        frames_per_second = input.ReadObject()
        soundtrack = input.ReadObject()
        if not isinstance(file_name, str):
            raise input._failure("Video file reference is null or not a String")
        if not all(type(value) is int for value in (duration_milliseconds, width, height, soundtrack)):
            raise input._failure("Video integer metadata has an invalid runtime type")
        if type(frames_per_second) is not float:
            raise input._failure("Video frame rate has an invalid runtime type")
        try:
            soundtrack_type = VideoSoundtrackType(soundtrack)
        except ValueError as error:
            raise input._failure("Video soundtrack identity is undefined") from error
        file_path = PurePosixPath(file_name.replace("\\", "/"))
        if file_path.is_absolute() or ".." in file_path.parts:
            raise input._failure("Video file reference escapes the content root")
        parent = PurePosixPath(input.AssetName.replace("\\", "/")).parent
        relative = parent / file_path if str(parent) != "." else file_path
        root = input.ContentManager.RootDirectory.replace("\\", "/").strip("/")
        resolved = str(PurePosixPath(root) / relative) if root else str(relative)
        # CNA opens the video file itself and resolves a relative path against the
        # process working directory, not the title location, so a title-relative
        # path silently fails to decode wherever the two differ. XNA resolves the
        # reference against the title, so the title-relative path is resolved here
        # -- with the same containment check every other title read uses -- and CNA
        # is handed a path it can open.
        from .._title import _safe_title_path
        try:
            absolute = _safe_title_path(resolved)
        except ValueError as error:
            raise input._failure("Video file reference escapes the content root") from error
        device = input.ContentManager._graphics_device()
        return Video._create(device._require_handle(), str(absolute), duration_milliseconds,
                             width, height, frames_per_second, soundtrack_type)


class _CollectionReader(ContentTypeReader):
    def __init__(self, element_type_identity: str, *, array: bool) -> None:
        super().__init__(tuple if array else list)
        self._element_type_identity = element_type_identity
        self._element_reader: ContentTypeReader | None = None
        self._array = array

    def Initialize(self, manager) -> None:
        identity = _ELEMENT_READERS.get(self._element_type_identity)
        if identity is None:
            raise ContentLoadException(
                f"No built-in element-reader mapping exists for '{self._element_type_identity}'"
            )
        reader = manager._get_identity_reader(identity)
        if reader is None:
            raise ContentLoadException(
                f"The XNB reader table does not contain '{identity}' required by "
                f"'{self._serialized_identity}'"
            )
        self._element_reader = reader

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        count = input.ReadInt32()
        if count < 0 or count > 1_000_000:
            raise input._failure(f"invalid collection element count {count}")
        reader = self._element_reader
        if reader is None:
            raise input._failure("collection reader was not initialized")
        values = [input.ReadObject(reader) for _ in range(count)]
        return tuple(values) if self._array else values


class _NullableReader(ContentTypeReader):
    def __init__(self, element_type_identity: str) -> None:
        super().__init__(object)
        self._element_type_identity = element_type_identity
        self._element_reader: ContentTypeReader | None = None

    def Initialize(self, manager) -> None:
        identity = _ELEMENT_READERS.get(self._element_type_identity)
        if identity is None:
            raise ContentLoadException(
                f"No built-in nullable-reader mapping exists for '{self._element_type_identity}'"
            )
        self._element_reader = manager._get_identity_reader(identity)
        if self._element_reader is None:
            raise ContentLoadException(
                f"The XNB reader table does not contain '{identity}' required by "
                f"'{self._serialized_identity}'"
            )

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        if not input.ReadBoolean():
            return None
        if self._element_reader is None:
            raise input._failure("nullable reader was not initialized")
        return input.ReadObject(self._element_reader)


class _Texture2DReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import Texture2D

        super().__init__(Texture2D)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import SurfaceFormat, Texture2D

        if existingInstance is not None:
            raise ValueError("Texture2DReader cannot deserialize into an existing texture")
        try:
            format_ = SurfaceFormat(input.ReadInt32())
        except ValueError as error:
            raise input._failure("Texture2D contains an unknown SurfaceFormat") from error
        width = input.ReadUInt32()
        height = input.ReadUInt32()
        mip_count = input.ReadUInt32()
        if width == 0 or height == 0 or width > 65536 or height > 65536:
            raise input._failure(f"Texture2D has implausible dimensions {width}x{height}")
        complete_mips = max(width, height).bit_length()
        if mip_count not in (1, complete_mips):
            raise input._failure(
                f"Texture2D has invalid mip count {mip_count} for {width}x{height}"
            )
        if format_ is not SurfaceFormat.Color:
            raise input._failure(
                f"Texture2D SurfaceFormat.{format_.name} cannot be uploaded faithfully through "
                "CNA's currently bound texture transfer route"
            )
        texture = Texture2D(
            input.ContentManager._graphics_device(), width, height, mip_count > 1, format_
        )
        try:
            for level in range(mip_count):
                byte_count = input.ReadUInt32()
                level_width = max(1, width >> level)
                level_height = max(1, height >> level)
                expected = level_width * level_height * 4
                if byte_count != expected:
                    raise input._failure(
                        f"Texture2D mip {level} has {byte_count} bytes; expected exactly {expected}"
                    )
                payload = input.ReadBytes(byte_count)
                colors = [Color(*payload[offset:offset + 4]) for offset in range(0, expected, 4)]
                texture.SetData(level, None, colors, 0, len(colors))
            return texture
        except BaseException:
            texture.Dispose()
            raise


class _SpriteFontReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import SpriteFont

        super().__init__(SpriteFont)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import SpriteFont, Texture2D

        if existingInstance is not None:
            raise ValueError("SpriteFontReader cannot deserialize into an existing SpriteFont")
        texture = input.ReadObject()
        glyph_bounds = input.ReadObject()
        cropping = input.ReadObject()
        characters = input.ReadObject()
        line_spacing = input.ReadInt32()
        spacing = input.ReadSingle()
        kerning = input.ReadObject()
        default_character = input.ReadObject()
        if not isinstance(texture, Texture2D):
            raise input._failure("SpriteFont texture is not a Texture2D")
        if not isinstance(glyph_bounds, (list, tuple)) or not all(
            isinstance(value, Rectangle) for value in glyph_bounds
        ):
            raise input._failure("SpriteFont glyph bounds are not a Rectangle collection")
        if not isinstance(cropping, (list, tuple)) or not all(
            isinstance(value, Rectangle) for value in cropping
        ):
            raise input._failure("SpriteFont cropping values are not a Rectangle collection")
        if not isinstance(characters, (list, tuple)) or not all(
            isinstance(value, str) and len(value) == 1 for value in characters
        ):
            raise input._failure("SpriteFont character map is not a Char collection")
        if not isinstance(kerning, (list, tuple)) or not all(
            isinstance(value, Vector3) for value in kerning
        ):
            raise input._failure("SpriteFont kerning values are not a Vector3 collection")
        if default_character is not None and not (
            isinstance(default_character, str) and len(default_character) == 1
        ):
            raise input._failure("SpriteFont default character is not a nullable Char")
        return SpriteFont._create(
            texture, glyph_bounds, cropping, characters, line_spacing, spacing,
            kerning, default_character,
        )


class _VertexDeclarationReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import VertexDeclaration

        super().__init__(VertexDeclaration)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import (
            VertexDeclaration, VertexElement, VertexElementFormat, VertexElementUsage,
        )

        stride = input.ReadInt32()
        count = input.ReadInt32()
        if stride <= 0 or count <= 0 or count > 1024:
            raise input._failure(
                f"VertexDeclaration has invalid stride/count {stride}/{count}"
            )
        elements = []
        for _ in range(count):
            offset = input.ReadInt32()
            try:
                format_ = VertexElementFormat(input.ReadInt32())
                usage = VertexElementUsage(input.ReadInt32())
            except ValueError as error:
                raise input._failure("VertexDeclaration contains an unknown enum value") from error
            usage_index = input.ReadInt32()
            elements.append(VertexElement(offset, format_, usage, usage_index))
        try:
            return VertexDeclaration(stride, elements)
        except Exception as error:
            raise input._failure(f"invalid VertexDeclaration: {error}") from error


class _VertexBufferReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import VertexBuffer

        super().__init__(VertexBuffer)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import BufferUsage, VertexBuffer

        if existingInstance is not None:
            raise ValueError("VertexBufferReader cannot deserialize into an existing buffer")
        # XNA creates this raw-value reader internally; it need not occupy a slot
        # in the serialized reader table.
        declaration_reader = _VertexDeclarationReader()
        declaration = input.ReadRawObject(declaration_reader)
        vertex_count = input.ReadUInt32()
        if vertex_count == 0 or vertex_count > 100_000_000:
            raise input._failure(f"invalid VertexBuffer vertex count {vertex_count}")
        byte_count = vertex_count * declaration.VertexStride
        if byte_count > 512 * 1024 * 1024:
            raise input._failure(f"implausible VertexBuffer payload size {byte_count}")
        payload = input.ReadBytes(byte_count)
        buffer = VertexBuffer(
            input.ContentManager._graphics_device(), declaration, vertex_count, BufferUsage.None_
        )
        try:
            buffer._set_raw_bytes(payload)
            return buffer
        except BaseException:
            buffer.Dispose()
            raise


class _IndexBufferReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import IndexBuffer

        super().__init__(IndexBuffer)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import BufferUsage, IndexBuffer, IndexElementSize

        if existingInstance is not None:
            raise ValueError("IndexBufferReader cannot deserialize into an existing buffer")
        element_size = (
            IndexElementSize.SixteenBits if input.ReadBoolean()
            else IndexElementSize.ThirtyTwoBits
        )
        byte_count = input.ReadInt32()
        width = 2 if element_size is IndexElementSize.SixteenBits else 4
        if byte_count <= 0 or byte_count > 512 * 1024 * 1024 or byte_count % width:
            raise input._failure(f"invalid IndexBuffer payload size {byte_count}")
        payload = input.ReadBytes(byte_count)
        buffer = IndexBuffer(
            input.ContentManager._graphics_device(), element_size,
            byte_count // width, BufferUsage.None_,
        )
        try:
            buffer._set_raw_bytes(payload)
            return buffer
        except BaseException:
            buffer.Dispose()
            raise


class _BasicEffectReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import BasicEffect
        super().__init__(BasicEffect)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import BasicEffect, Texture2D
        if existingInstance is not None:
            raise ValueError("BasicEffectReader cannot deserialize into an existing Effect")
        effect=BasicEffect(input.ContentManager._graphics_device())
        try:
            texture=input.ReadExternalReference()
            if texture is not None:
                if not isinstance(texture,Texture2D):raise input._failure("BasicEffect external texture is not Texture2D")
                effect.Texture=texture;effect.TextureEnabled=True
            effect.DiffuseColor=input.ReadVector3();effect.EmissiveColor=input.ReadVector3()
            effect.SpecularColor=input.ReadVector3();effect.SpecularPower=input.ReadSingle()
            effect.Alpha=input.ReadSingle();effect.VertexColorEnabled=input.ReadBoolean()
            return effect
        except BaseException:
            effect.Dispose();raise


def _read_bone_reference(input: ContentReader, bone_count: int, context: str) -> int:
    identity=input.ReadByte() if bone_count<255 else input.ReadUInt32()
    if identity==0:return -1
    index=identity-1
    if index<0 or index>=bone_count:raise input._failure(f"{context} bone index {index} is outside {bone_count} bones")
    return index


class _ModelReader(ContentTypeReader):
    def __init__(self) -> None:
        from ..Graphics import Model
        super().__init__(Model)

    def Read(self, input: ContentReader, existingInstance: object) -> object:
        from ..Graphics import (Effect, IndexBuffer, Model, ModelBone, ModelMesh,
                                ModelMeshPart, VertexBuffer)
        from .._intersections import BoundingSphere
        if existingInstance is not None:raise ValueError("ModelReader cannot deserialize into an existing Model")
        bone_count=input.ReadUInt32()
        if bone_count>1_000_000:raise input._failure(f"implausible Model bone count {bone_count}")
        bones=[]
        for index in range(bone_count):
            name=input.ReadObject()
            if not isinstance(name,str):raise input._failure("Model bone name is not a String")
            bones.append(ModelBone(name,index,input.ReadMatrix()))
        encoded_parents=[];children=[];derived_parents=[-1]*bone_count
        for parent_index in range(bone_count):
            encoded_parents.append(_read_bone_reference(input,bone_count,"parent"))
            child_count=input.ReadUInt32()
            if child_count>bone_count:raise input._failure(f"bone {parent_index} has implausible child count {child_count}")
            child_indices=[]
            for _ in range(child_count):
                child_index=_read_bone_reference(input,bone_count,"child")
                if child_index<0:raise input._failure("a Model child reference cannot be null")
                if child_index==parent_index:raise input._failure("a Model bone cannot be its own child")
                if child_index in child_indices:raise input._failure("a Model bone child is duplicated")
                if derived_parents[child_index]>=0:raise input._failure("a Model bone has more than one parent")
                derived_parents[child_index]=parent_index;child_indices.append(child_index)
            children.append(child_indices)
        for index,(encoded,derived) in enumerate(zip(encoded_parents,derived_parents)):
            if encoded!=derived:raise input._failure(f"bone {index} parent and child-list encodings disagree")
        for parent_index,child_indices in enumerate(children):
            for child_index in child_indices:bones[parent_index]._add_child(bones[child_index])
        mesh_count=input.ReadInt32()
        if mesh_count<0 or mesh_count>1_000_000:raise input._failure(f"invalid Model mesh count {mesh_count}")
        meshes=[];device=input.ContentManager._graphics_device()
        for _ in range(mesh_count):
            name=input.ReadObject()
            if not isinstance(name,str):raise input._failure("Model mesh name is not a String")
            parent_index=_read_bone_reference(input,bone_count,"mesh parent")
            center=input.ReadVector3();radius=input.ReadSingle()
            try:sphere=BoundingSphere(center,radius)
            except Exception as error:raise input._failure(f"invalid Model BoundingSphere: {error}") from error
            tag=input.ReadObject();part_count=input.ReadInt32()
            if part_count<0 or part_count>1_000_000:raise input._failure(f"invalid Model mesh-part count {part_count}")
            parts=[]
            for _ in range(part_count):
                part=ModelMeshPart();part._offset=input.ReadInt32();part._num=input.ReadInt32();part._start=input.ReadInt32();part._primitive=input.ReadInt32();part._tag=input.ReadObject()
                if min(part._offset,part._num,part._start,part._primitive)<0:raise input._failure("Model mesh-part ranges cannot be negative")
                input.ReadSharedResource(lambda value,part=part:_assign_model_resource(input,part,"vertex",value,VertexBuffer))
                input.ReadSharedResource(lambda value,part=part:_assign_model_resource(input,part,"index",value,IndexBuffer))
                input.ReadSharedResource(lambda value,part=part:_assign_model_resource(input,part,"effect",value,Effect))
                parts.append(part)
            mesh=ModelMesh(name,None if parent_index<0 else bones[parent_index],parts,sphere=sphere);mesh._tag=tag;meshes.append(mesh)
        root_index=_read_bone_reference(input,bone_count,"root");model_tag=input.ReadObject()
        if bone_count==0:
            if meshes or root_index>=0:raise input._failure("a Model with meshes or Root requires at least one bone")
            root_index=0
        elif root_index<0:raise input._failure("a Model with bones must have a Root")
        return Model(bones,meshes,model_tag,root_index=root_index,graphics_device=device)


def _assign_model_resource(input,part,kind,value,expected):
    if not isinstance(value,expected):raise input._failure(f"Model shared {kind} resource is not {expected.__name__}")
    if kind=="vertex":part._vertex_buffer=value
    elif kind=="index":part._index_buffer=value
    else:part._assign_effect(value,True)


_SIMPLE_READERS: dict[str, tuple[type, Callable[[ContentReader], object]]] = {
    _PREFIX + "BooleanReader": (bool, lambda value: value.ReadBoolean()),
    _PREFIX + "ByteReader": (int, lambda value: value.ReadByte()),
    _PREFIX + "SByteReader": (int, lambda value: value.ReadSByte()),
    _PREFIX + "Int16Reader": (int, lambda value: value.ReadInt16()),
    _PREFIX + "UInt16Reader": (int, lambda value: value.ReadUInt16()),
    _PREFIX + "Int32Reader": (int, lambda value: value.ReadInt32()),
    _PREFIX + "UInt32Reader": (int, lambda value: value.ReadUInt32()),
    _PREFIX + "Int64Reader": (int, lambda value: value.ReadInt64()),
    _PREFIX + "UInt64Reader": (int, lambda value: value.ReadUInt64()),
    _PREFIX + "SingleReader": (float, lambda value: value.ReadSingle()),
    _PREFIX + "DoubleReader": (float, lambda value: value.ReadDouble()),
    _PREFIX + "CharReader": (str, lambda value: value.ReadChar()),
    _PREFIX + "StringReader": (str, lambda value: value.ReadString()),
    _PREFIX + "Vector2Reader": (Vector2, lambda value: value.ReadVector2()),
    _PREFIX + "Vector3Reader": (Vector3, lambda value: value.ReadVector3()),
    _PREFIX + "Vector4Reader": (Vector4, lambda value: value.ReadVector4()),
    _PREFIX + "QuaternionReader": (Quaternion, lambda value: value.ReadQuaternion()),
    _PREFIX + "MatrixReader": (Matrix, lambda value: value.ReadMatrix()),
    _PREFIX + "ColorReader": (Color, lambda value: value.ReadColor()),
    _PREFIX + "PointReader": (
        Point, lambda value: Point(value.ReadInt32(), value.ReadInt32()),
    ),
    _PREFIX + "RectangleReader": (
        Rectangle,
        lambda value: Rectangle(
            value.ReadInt32(), value.ReadInt32(), value.ReadInt32(), value.ReadInt32()
        ),
    ),
}


_SPECIAL_READERS: dict[str, type[ContentTypeReader]] = {
    _PREFIX + "TimeSpanReader": _TimeSpanReader,
    _PREFIX + "Texture2DReader": _Texture2DReader,
    _PREFIX + "SpriteFontReader": _SpriteFontReader,
    _PREFIX + "VertexDeclarationReader": _VertexDeclarationReader,
    _PREFIX + "VertexBufferReader": _VertexBufferReader,
    _PREFIX + "IndexBufferReader": _IndexBufferReader,
    _PREFIX + "BasicEffectReader": _BasicEffectReader,
    _PREFIX + "ModelReader": _ModelReader,
    _PREFIX + "VideoReader": _VideoReader,
}


_ELEMENT_READERS = {
    "System.Boolean": _PREFIX + "BooleanReader",
    "System.Byte": _PREFIX + "ByteReader",
    "System.SByte": _PREFIX + "SByteReader",
    "System.Int16": _PREFIX + "Int16Reader",
    "System.UInt16": _PREFIX + "UInt16Reader",
    "System.Int32": _PREFIX + "Int32Reader",
    "System.UInt32": _PREFIX + "UInt32Reader",
    "System.Int64": _PREFIX + "Int64Reader",
    "System.UInt64": _PREFIX + "UInt64Reader",
    "System.Single": _PREFIX + "SingleReader",
    "System.Double": _PREFIX + "DoubleReader",
    "System.Char": _PREFIX + "CharReader",
    "System.String": _PREFIX + "StringReader",
    "System.TimeSpan": _PREFIX + "TimeSpanReader",
    "Microsoft.Xna.Framework.Vector2": _PREFIX + "Vector2Reader",
    "Microsoft.Xna.Framework.Vector3": _PREFIX + "Vector3Reader",
    "Microsoft.Xna.Framework.Vector4": _PREFIX + "Vector4Reader",
    "Microsoft.Xna.Framework.Quaternion": _PREFIX + "QuaternionReader",
    "Microsoft.Xna.Framework.Matrix": _PREFIX + "MatrixReader",
    "Microsoft.Xna.Framework.Color": _PREFIX + "ColorReader",
    "Microsoft.Xna.Framework.Point": _PREFIX + "PointReader",
    "Microsoft.Xna.Framework.Rectangle": _PREFIX + "RectangleReader",
}


_GENERIC_READER = re.compile(
    r"^Microsoft\.Xna\.Framework\.Content\.(ListReader|ArrayReader|NullableReader)`1\[\[(.+)\]\]$"
)


def _create_builtin_reader(identity: str) -> ContentTypeReader | None:
    simple = _SIMPLE_READERS.get(identity)
    if simple is not None:
        return _Reader(*simple)
    special = _SPECIAL_READERS.get(identity)
    if special is not None:
        return special()
    match = _GENERIC_READER.fullmatch(identity)
    if match is None:
        return None
    kind, element = match.groups()
    if element not in _ELEMENT_READERS:
        return None
    if kind == "NullableReader":
        return _NullableReader(element)
    return _CollectionReader(element, array=kind == "ArrayReader")
