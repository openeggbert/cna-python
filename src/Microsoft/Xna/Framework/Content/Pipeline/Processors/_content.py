"""What a processor produces: the shapes a content writer knows how to write.

Everything here is *output*. A ``ModelContent`` is not something an importer
builds -- it is what ``ModelProcessor`` turns a ``NodeContent`` scene into, with
its bones flattened into an indexed list and its geometry packed into vertex and
index buffers. By the time content reaches a writer there is nothing left to
decide, which is why these types are read-only from the outside.

``SoundEffectContent``, ``SongContent`` and ``SpriteFontContent`` have no public
surface at all in XNA, and none here: they carry a payload from the processor
that built them to the writer that writes them, and nothing else may look
inside. Their state is private and the writers reach it through the same private
names, which is exactly the arrangement XNA's ``internal`` gives them.
"""

from __future__ import annotations

import struct
from typing import Iterable

from .... import BoundingSphere, Matrix, Rectangle, Vector3
from ....Graphics import VertexElement, VertexElementFormat, VertexElementUsage
from .._collections import _Collection, _ReadOnlyCollection
from .._errors import InvalidContentException
from .._identity import ContentItem
from ..Graphics._vectors import VERTEX_FORMATS, kind_of


class CompiledEffectContent(ContentItem):
    """Compiled effect bytecode, ready to be written into an XNB."""

    __slots__ = ("_effect_code",)

    def __init__(self, effectCode: bytes) -> None:
        super().__init__()
        self._effect_code = bytes(effectCode)

    def GetEffectCode(self) -> bytes:
        return self._effect_code


class VertexDeclarationContent(ContentItem):
    """The layout of one vertex, element by element."""

    __slots__ = ("_elements", "_stride")

    def __init__(self) -> None:
        super().__init__()
        self._elements = _Collection()
        self._stride: int | None = None

    @property
    def VertexElements(self) -> _Collection:
        return self._elements

    @property
    def VertexStride(self) -> int | None:
        """The declared stride, or ``None`` to let the elements decide.

        ``None`` is not "unknown": it means the stride *is* the end of the last
        element, and saying so is different from pinning a stride that leaves
        padding at the end of every vertex.
        """
        return self._stride

    @VertexStride.setter
    def VertexStride(self, value: int | None) -> None:
        if value is None:
            self._stride = None
            return
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"VertexStride must be an int or None, not {type(value).__name__}")
        if value <= 0:
            raise ValueError(f"VertexStride must be positive, got {value}")
        self._stride = value

    def _effective_stride(self) -> int:
        if self._stride is not None:
            return self._stride
        end = 0
        for element in self._elements:
            end = max(end, element.Offset + _format_size(element.VertexElementFormat))
        return end

    def _build(self, channels) -> None:
        """Position first, then every channel in its own order.

        Position at offset zero is not an arbitrary choice: it is what the
        vertex declarations this repository's effects already use, and a
        declaration that put it elsewhere would be a different layout with the
        same name.
        """
        offset = 0
        self._elements.Clear()
        self._elements.Add(VertexElement(
            0, VertexElementFormat.Vector3, VertexElementUsage.Position, 0))
        offset += _format_size(VertexElementFormat.Vector3)
        from ..Graphics import VertexChannelNames

        for channel in channels:
            element_format = VERTEX_FORMATS.get(channel.ElementType)
            if element_format is None:
                raise InvalidContentException(
                    f"channel {channel.Name!r} holds "
                    f"{channel.ElementType.__name__}, which is not a vertex "
                    "element format")
            found, usage = VertexChannelNames.TryDecodeUsage(channel.Name)
            if not found:
                raise InvalidContentException(
                    f"channel {channel.Name!r} does not encode a vertex element "
                    "usage, so it cannot become a vertex element")
            self._elements.Add(VertexElement(
                offset, element_format, usage,
                VertexChannelNames.DecodeUsageIndex(channel.Name)))
            offset += _format_size(element_format)
        self._stride = None


class VertexBufferContent(ContentItem):
    """Interleaved vertex bytes, with the declaration that describes them."""

    __slots__ = ("_data", "_declaration")

    def __init__(self, size: int = 0) -> None:
        super().__init__()
        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError(f"size must be an int, not {type(size).__name__}")
        if size < 0:
            raise ValueError(f"size must not be negative, got {size}")
        self._data = bytearray(size)
        self._declaration = VertexDeclarationContent()

    @property
    def VertexDeclaration(self) -> VertexDeclarationContent:
        return self._declaration

    @VertexDeclaration.setter
    def VertexDeclaration(self, value: VertexDeclarationContent) -> None:
        if not isinstance(value, VertexDeclarationContent):
            raise TypeError(
                "VertexDeclaration must be a VertexDeclarationContent, not "
                f"{type(value).__name__}")
        self._declaration = value

    @property
    def VertexData(self) -> bytes:
        return bytes(self._data)

    def Write(self, offset: int, stride: int, *rest: object) -> None:
        """XNA's two overloads: with an element type, or inferred from the data.

        ``stride`` is the distance between one value and the next, which is how
        one call fills one channel of an interleaved buffer: the first vertex's
        normal at offset 12, the second at 12 + stride, and so on.
        """
        if len(rest) == 1:
            values = list(rest[0])
            if not values:
                return
            data_type = type(values[0])
        elif len(rest) == 2:
            data_type, data = rest
            if not isinstance(data_type, type):
                raise TypeError(
                    f"dataType must be a type, not {type(data_type).__name__}")
            values = list(data)
        else:
            raise TypeError("no matching Write overload")
        kind = kind_of(data_type)
        if offset < 0:
            raise ValueError(f"offset must not be negative, got {offset}")
        if stride < kind.size:
            raise ValueError(
                f"stride {stride} is smaller than one "
                f"{data_type.__name__} ({kind.size} bytes)")
        needed = offset + stride * (len(values) - 1) + kind.size
        if needed > len(self._data):
            self._data.extend(bytes(needed - len(self._data)))
        for index, value in enumerate(values):
            start = offset + index * stride
            self._data[start:start + kind.size] = kind.pack(value)

    @staticmethod
    def SizeOf(type_: type) -> int:
        """How many bytes one value of ``type_`` takes in a vertex buffer."""
        return kind_of(type_).size

    def _write(self, positions: Iterable[Vector3], channels) -> None:
        """Packs positions and channels into the declaration's layout."""
        positions = list(positions)
        stride = self._declaration._effective_stride()
        self._data = bytearray(stride * len(positions))
        elements = list(self._declaration.VertexElements)
        self.Write(elements[0].Offset, stride, Vector3, positions)
        for element, channel in zip(elements[1:], channels):
            self.Write(element.Offset, stride, channel.ElementType, list(channel))


VertexBufferContent.__xna_arities__ = {"__init__": {0, 1}, "Write": {3, 4}}


class ModelBoneContent:
    """One bone of a built model, with its index into the flattened list."""

    __slots__ = ("_name", "_index", "_transform", "_parent", "_children")

    def __init__(self, name: str | None, index: int, transform: Matrix,
                 parent: "ModelBoneContent | None") -> None:
        self._name = name
        self._index = index
        self._transform = transform
        self._parent = parent
        self._children = ModelBoneContentCollection([])

    @property
    def Name(self) -> str | None:
        return self._name

    @property
    def Index(self) -> int:
        return self._index

    @property
    def Transform(self) -> Matrix:
        return self._transform

    @Transform.setter
    def Transform(self, value: Matrix) -> None:
        if not isinstance(value, Matrix):
            raise TypeError(f"Transform must be a Matrix, not {type(value).__name__}")
        self._transform = value

    @property
    def Parent(self) -> "ModelBoneContent | None":
        return self._parent

    @property
    def Children(self) -> "ModelBoneContentCollection":
        return self._children

    def __repr__(self) -> str:
        return f"ModelBoneContent({self._name!r}, index={self._index})"


class ModelBoneContentCollection(_ReadOnlyCollection[ModelBoneContent]):
    """A model's bones, in the order their indices name."""

    __slots__ = ()


class ModelMeshPartContent:
    """One material's worth of one mesh: a slice of a vertex and index buffer."""

    __slots__ = ("_vertex_offset", "_num_vertices", "_start_index",
                 "_primitive_count", "_material", "_vertex_buffer",
                 "_index_buffer", "_tag")

    def __init__(self, vertexBuffer: VertexBufferContent, indexBuffer,
                 vertexOffset: int, numVertices: int, startIndex: int,
                 primitiveCount: int) -> None:
        self._vertex_buffer = vertexBuffer
        self._index_buffer = indexBuffer
        self._vertex_offset = vertexOffset
        self._num_vertices = numVertices
        self._start_index = startIndex
        self._primitive_count = primitiveCount
        self._material = None
        self._tag = None

    @property
    def VertexOffset(self) -> int:
        return self._vertex_offset

    @property
    def NumVertices(self) -> int:
        return self._num_vertices

    @property
    def StartIndex(self) -> int:
        return self._start_index

    @property
    def PrimitiveCount(self) -> int:
        return self._primitive_count

    @property
    def Material(self):
        return self._material

    @Material.setter
    def Material(self, value) -> None:
        self._material = value

    @property
    def VertexBuffer(self) -> VertexBufferContent:
        return self._vertex_buffer

    @property
    def IndexBuffer(self):
        return self._index_buffer

    @property
    def Tag(self) -> object:
        return self._tag

    @Tag.setter
    def Tag(self, value: object) -> None:
        self._tag = value


class ModelMeshPartContentCollection(_ReadOnlyCollection[ModelMeshPartContent]):
    """Every part of one mesh."""

    __slots__ = ()


class ModelMeshContent:
    """One mesh of a built model, attached to one bone."""

    __slots__ = ("_name", "_parent_bone", "_bounding_sphere", "_tag",
                 "_mesh_parts", "_source_mesh")

    def __init__(self, name: str | None, sourceMesh, parentBone: ModelBoneContent,
                 boundingSphere: BoundingSphere,
                 meshParts: list[ModelMeshPartContent]) -> None:
        self._name = name
        self._source_mesh = sourceMesh
        self._parent_bone = parentBone
        self._bounding_sphere = boundingSphere
        self._mesh_parts = ModelMeshPartContentCollection(meshParts)
        self._tag = None

    @property
    def Name(self) -> str | None:
        return self._name

    @property
    def ParentBone(self) -> ModelBoneContent:
        return self._parent_bone

    @property
    def BoundingSphere(self) -> BoundingSphere:
        return self._bounding_sphere

    @property
    def Tag(self) -> object:
        return self._tag

    @Tag.setter
    def Tag(self, value: object) -> None:
        self._tag = value

    @property
    def MeshParts(self) -> ModelMeshPartContentCollection:
        return self._mesh_parts

    @property
    def SourceMesh(self):
        return self._source_mesh


class ModelMeshContentCollection(_ReadOnlyCollection[ModelMeshContent]):
    """Every mesh of one model."""

    __slots__ = ()


class ModelContent:
    """A built model: a bone hierarchy, and meshes hanging off it."""

    __slots__ = ("_root", "_bones", "_meshes", "_tag")

    def __init__(self, root: ModelBoneContent, bones: list[ModelBoneContent],
                 meshes: list[ModelMeshContent]) -> None:
        self._root = root
        self._bones = ModelBoneContentCollection(bones)
        self._meshes = ModelMeshContentCollection(meshes)
        self._tag = None

    @property
    def Root(self) -> ModelBoneContent:
        return self._root

    @property
    def Bones(self) -> ModelBoneContentCollection:
        return self._bones

    @property
    def Meshes(self) -> ModelMeshContentCollection:
        return self._meshes

    @property
    def Tag(self) -> object:
        return self._tag

    @Tag.setter
    def Tag(self, value: object) -> None:
        self._tag = value


class SoundEffectContent:
    """A built sound effect: format, samples and loop points.

    No public surface, by XNA's design and by this projection's. What is inside
    is exactly what ``SoundEffectWriter`` writes, and the only thing that reads
    it is that writer.
    """

    __slots__ = ("_format", "_data", "_loop_start", "_loop_length", "_duration")

    def __init__(self, format_bytes: bytes, data: bytes, loopStart: int,
                 loopLength: int, durationMilliseconds: int) -> None:
        self._format = bytes(format_bytes)
        self._data = bytes(data)
        self._loop_start = loopStart
        self._loop_length = loopLength
        self._duration = durationMilliseconds


class SongContent:
    """A built song: a path to the media file and how long it plays."""

    __slots__ = ("_filename", "_duration")

    def __init__(self, filename: str, durationMilliseconds: int) -> None:
        self._filename = filename
        self._duration = durationMilliseconds


class SpriteFontContent:
    """A built sprite font: a texture, and where every glyph is inside it."""

    __slots__ = ("_texture", "_glyphs", "_cropping", "_character_map",
                 "_line_spacing", "_spacing", "_kerning", "_default_character")

    def __init__(self, texture, glyphs: list[Rectangle],
                 cropping: list[Rectangle], characterMap: list[str],
                 lineSpacing: int, spacing: float, kerning: list[Vector3],
                 defaultCharacter: str | None) -> None:
        self._texture = texture
        self._glyphs = glyphs
        self._cropping = cropping
        self._character_map = characterMap
        self._line_spacing = lineSpacing
        self._spacing = spacing
        self._kerning = kerning
        self._default_character = defaultCharacter


_FORMAT_SIZES = {
    VertexElementFormat.Single: 4, VertexElementFormat.Vector2: 8,
    VertexElementFormat.Vector3: 12, VertexElementFormat.Vector4: 16,
    VertexElementFormat.Color: 4, VertexElementFormat.Byte4: 4,
    VertexElementFormat.Short2: 4, VertexElementFormat.Short4: 8,
    VertexElementFormat.NormalizedShort2: 4,
    VertexElementFormat.NormalizedShort4: 8,
    VertexElementFormat.HalfVector2: 4, VertexElementFormat.HalfVector4: 8,
}


def _format_size(value: VertexElementFormat) -> int:
    return _FORMAT_SIZES[VertexElementFormat(value)]
