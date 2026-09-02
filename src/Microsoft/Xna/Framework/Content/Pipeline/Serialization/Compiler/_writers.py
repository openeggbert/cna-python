"""The built-in content type writers.

One per runtime reader, and the set is not arbitrary: it is exactly the set of
readers ``Microsoft.Xna.Framework.Content`` in this repository can *read*. That
correspondence is the point -- everything written here is loadable by the
``ContentManager`` beside it, and the qualification proves it by doing so rather
than by comparing bytes to a specification.

The reader names are CLR names, because that is what the format carries and what
a real XNA runtime would look up. They are written in the short form -- no
assembly, no version -- which is what XNA's own compiler writes and what this
repository's reader normalises to.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable

from ..... import Color, Matrix, Point, Quaternion, Rectangle, Vector2, Vector3, Vector4
from .....Graphics import SurfaceFormat
from ..._errors import InvalidContentException
from ..._target import TargetPlatform
from ._compiler import ContentTypeWriter

_PREFIX = "Microsoft.Xna.Framework.Content."

#: 100-nanosecond ticks per second, which is what a ``TimeSpan`` counts.
_TICKS_PER_SECOND = 10_000_000


class _SimpleWriter(ContentTypeWriter):
    """A writer described entirely by a reader name and one write call."""

    __slots__ = ("_reader", "_runtime", "_write", "_compressible")

    def __init__(self, targetType: type, reader: str, runtime: str,
                 write: Callable[[object, object], None],
                 compressible: bool = True) -> None:
        super().__init__(targetType)
        self._reader = reader
        self._runtime = runtime
        self._write = write
        self._compressible = compressible

    def Write(self, output, value: object) -> None:
        self._write(output, value)

    def GetRuntimeType(self, targetPlatform: TargetPlatform) -> str:
        return self._runtime

    def GetRuntimeReader(self, targetPlatform: TargetPlatform) -> str:
        return self._reader

    def ShouldCompressContent(self, targetPlatform: TargetPlatform,
                              value: object) -> bool:
        return self._compressible


class _ListWriter(ContentTypeWriter):
    """``List<T>``: a count, then every element raw.

    Raw because the element type is already named in the reader's own identity,
    so writing a type index per element would be a byte per element for nothing.

    The identity names the element's **CLR type**, not the reader that reads it:
    ``ListReader`1[[System.Int32]]``. That is what XNA writes and what a runtime
    parses -- naming the reader instead produces an identity nothing resolves,
    which is exactly what the round-trip through this repository's own
    ``ContentManager`` caught.
    """

    __slots__ = ("_element",)

    def __init__(self, element: type) -> None:
        super().__init__(list)
        self._element = element

    def Write(self, output, value: object) -> None:
        values = list(value)
        output.WriteUInt32(len(values))
        writer = self._compiler.GetTypeWriter(self._element)
        # A list reader resolves its element reader *by name* out of the file's
        # own reader table, so the element writer has to be in that table even
        # though no type index is written for the elements themselves. Asking
        # for its index is what puts it there.
        self._compiler._index_of(writer)
        for entry in values:
            if not isinstance(entry, self._element):
                raise InvalidContentException(
                    f"a List<{self._element.__name__}> holds "
                    f"{type(entry).__name__}")
            output.WriteRawObject(entry, writer)

    def GetRuntimeType(self, targetPlatform: TargetPlatform) -> str:
        return (f"System.Collections.Generic.List`1[["
                f"{_runtime_name(self._element)}]]")

    def GetRuntimeReader(self, targetPlatform: TargetPlatform) -> str:
        return f"{_PREFIX}ListReader`1[[{_runtime_name(self._element)}]]"


def _runtime_name(element: type) -> str:
    return _RUNTIME_NAMES[element]


def _write_timespan(output, value: timedelta) -> None:
    """A ``TimeSpan`` is 64 bits of 100-nanosecond ticks.

    The arithmetic is integer throughout: a ``timedelta`` holds days, seconds
    and microseconds as integers, and multiplying them out keeps every tick a
    long duration has. Going through ``total_seconds()`` would put a float in
    the middle and lose the low digits of anything over a few hours.
    """
    ticks = ((value.days * 86_400 + value.seconds) * _TICKS_PER_SECOND
             + value.microseconds * 10)
    output.WriteInt64(ticks)


def _write_texture2d(output, value) -> None:
    """A ``Texture2DContent``, as ``Texture2DReader`` reads it.

    Format, width, height, level count, then each level's byte count and bytes.
    """
    from ...Graphics import BitmapContent

    bitmap = value.Faces[0][0]
    found, surface = bitmap.TryGetFormat()
    if not found:
        raise InvalidContentException(
            f"{type(bitmap).__name__} has no SurfaceFormat, so it cannot be "
            "written as a Texture2D", value.Identity)
    output.WriteInt32(int(surface))
    output.WriteUInt32(bitmap.Width)
    output.WriteUInt32(bitmap.Height)
    levels = list(value.Faces[0])
    output.WriteUInt32(len(levels))
    for level in levels:
        data = level.GetPixelData()
        output.WriteUInt32(len(data))
        output.WriteBytes(data)


def _write_sprite_font(output, value) -> None:
    """A ``SpriteFontContent``, as ``SpriteFontReader`` reads it."""
    output.WriteObject(value._texture)
    output.WriteObject(value._glyphs)
    output.WriteObject(value._cropping)
    output.WriteObject(value._character_map)
    output.WriteInt32(value._line_spacing)
    output.WriteSingle(value._spacing)
    output.WriteObject(value._kerning)
    if value._default_character is None:
        output.WriteBoolean(False)
    else:
        output.WriteBoolean(True)
        output.WriteChar(value._default_character)


def _write_sound_effect(output, value) -> None:
    """A ``SoundEffectContent``, as XNA's ``SoundEffectReader`` reads it."""
    output.WriteUInt32(len(value._format))
    output.WriteBytes(value._format)
    output.WriteUInt32(len(value._data))
    output.WriteBytes(value._data)
    output.WriteInt32(value._loop_start)
    output.WriteInt32(value._loop_length)
    output.WriteInt32(value._duration)


def _write_song(output, value) -> None:
    output.WriteString(value._filename)
    output.WriteInt32(value._duration)


def _write_video(output, value) -> None:
    """A ``VideoContent``, as ``VideoReader`` reads it."""
    import os

    output.WriteString(os.path.basename(value.Filename))
    output.WriteInt32(round(value.Duration.total_seconds() * 1000.0))
    output.WriteInt32(value.Width)
    output.WriteInt32(value.Height)
    output.WriteSingle(value.FramesPerSecond)
    output.WriteInt32(int(value.VideoSoundtrackType))


def _write_vertex_declaration(output, value) -> None:
    """A ``VertexDeclarationContent``, as ``VertexDeclarationReader`` reads it."""
    elements = list(value.VertexElements)
    output.WriteUInt32(value._effective_stride())
    output.WriteUInt32(len(elements))
    for element in elements:
        output.WriteUInt32(element.Offset)
        output.WriteInt32(int(element.VertexElementFormat))
        output.WriteInt32(int(element.VertexElementUsage))
        output.WriteUInt32(element.UsageIndex)


def _write_vertex_buffer(output, value) -> None:
    """A ``VertexBufferContent``, as ``VertexBufferReader`` reads it.

    The declaration is written *raw*, with no type index: a vertex buffer always
    carries one, so the reader builds its declaration reader itself and the
    index would be a byte nothing reads.
    """
    output.WriteRawObject(value.VertexDeclaration)
    stride = value.VertexDeclaration._effective_stride()
    data = value.VertexData
    if stride <= 0:
        raise InvalidContentException(
            "a vertex buffer with a zero stride has no vertices to count",
            value.Identity)
    output.WriteUInt32(len(data) // stride)
    output.WriteBytes(data)


def _write_index_buffer(output, value) -> None:
    """An ``IndexCollection``, as ``IndexBufferReader`` reads it.

    Sixteen-bit indices whenever every index fits, which halves the buffer for
    the overwhelming majority of meshes and is what XNA does. The flag in the
    file says which was written, so nothing has to guess.
    """
    indices = list(value)
    sixteen = all(0 <= index <= 0xFFFF for index in indices)
    output.WriteBoolean(sixteen)
    width = 2 if sixteen else 4
    output.WriteUInt32(len(indices) * width)
    for index in indices:
        if sixteen:
            output.WriteUInt16(index)
        else:
            output.WriteUInt32(index)


def _write_model(output, value) -> None:
    """A ``ModelContent``, as ``ModelReader`` reads it."""
    bones = list(value.Bones)
    output.WriteUInt32(len(bones))
    for bone in bones:
        output.WriteObject(bone.Name)
        output.Write(bone.Transform)
    for bone in bones:
        # Parent first, then the child count and the children: the reader checks
        # that the two encodings of the hierarchy agree, so writing them the
        # other way round produces a file it rejects rather than misreads.
        _write_bone_reference(output, len(bones), bone.Parent)
        output.WriteUInt32(len(bone.Children))
        for child in bone.Children:
            _write_bone_reference(output, len(bones), child)
    meshes = list(value.Meshes)
    output.WriteUInt32(len(meshes))
    for mesh in meshes:
        output.WriteObject(mesh.Name)
        _write_bone_reference(output, len(bones), mesh.ParentBone)
        output.Write(mesh.BoundingSphere.Center)
        output.WriteSingle(mesh.BoundingSphere.Radius)
        output.WriteObject(mesh.Tag)
        parts = list(mesh.MeshParts)
        output.WriteUInt32(len(parts))
        for part in parts:
            output.WriteUInt32(part.VertexOffset)
            output.WriteUInt32(part.NumVertices)
            output.WriteUInt32(part.StartIndex)
            output.WriteUInt32(part.PrimitiveCount)
            output.WriteObject(part.Tag)
            output.WriteSharedResource(part.VertexBuffer)
            output.WriteSharedResource(part.IndexBuffer)
            output.WriteSharedResource(part.Material)
    _write_bone_reference(output, len(bones), value.Root)
    output.WriteObject(value.Tag)


def _write_bone_reference(output, count: int, bone) -> None:
    """A bone index, one byte where it fits and four where it does not.

    The width is decided by the *bone count*, not by the value: a reader that
    knows how many bones there are knows how wide every reference is, which is
    what lets the references be written with no marker of their own.
    """
    index = 0 if bone is None else bone.Index + 1
    if count < 255:
        output.WriteByte(index)
    else:
        output.WriteUInt32(index)


def _write_basic_effect(output, value) -> None:
    """A ``BasicMaterialContent``, as ``BasicEffectReader`` reads it."""
    output.WriteExternalReference(value.Texture)
    output.Write(value.DiffuseColor or Vector3(1.0, 1.0, 1.0))
    output.Write(value.EmissiveColor or Vector3(0.0, 0.0, 0.0))
    output.Write(value.SpecularColor or Vector3(1.0, 1.0, 1.0))
    output.WriteSingle(16.0 if value.SpecularPower is None
                       else value.SpecularPower)
    output.WriteSingle(1.0 if value.Alpha is None else value.Alpha)
    output.WriteBoolean(bool(value.VertexColorEnabled))


#: Every CLR type name a list writer may name as its element.
_RUNTIME_NAMES: dict[type, str] = {}


def builtin_writers() -> list[ContentTypeWriter]:
    """Every writer this pipeline ships, in one list.

    Built fresh for each compiler rather than shared: a writer holds the
    compiler that initialised it, and two compilers with different target
    platforms must not share one.
    """
    from ...Graphics import IndexCollection, Texture2DContent
    from ...Graphics._material import BasicMaterialContent
    from ...Processors import (
        SongContent, SoundEffectContent, SpriteFontContent, VertexBufferContent,
        VertexDeclarationContent,
    )
    from ..._video import VideoContent

    writers: list[ContentTypeWriter] = [
        _SimpleWriter(bool, f"{_PREFIX}BooleanReader", "System.Boolean",
                      lambda output, value: output.WriteBoolean(value)),
        _SimpleWriter(int, f"{_PREFIX}Int32Reader", "System.Int32",
                      lambda output, value: output.WriteInt32(value)),
        _SimpleWriter(float, f"{_PREFIX}SingleReader", "System.Single",
                      lambda output, value: output.WriteSingle(value)),
        _SimpleWriter(str, f"{_PREFIX}StringReader", "System.String",
                      lambda output, value: output.WriteString(value)),
        _SimpleWriter(timedelta, f"{_PREFIX}TimeSpanReader", "System.TimeSpan",
                      _write_timespan),
        _SimpleWriter(Vector2, f"{_PREFIX}Vector2Reader",
                      "Microsoft.Xna.Framework.Vector2",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Vector3, f"{_PREFIX}Vector3Reader",
                      "Microsoft.Xna.Framework.Vector3",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Vector4, f"{_PREFIX}Vector4Reader",
                      "Microsoft.Xna.Framework.Vector4",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Quaternion, f"{_PREFIX}QuaternionReader",
                      "Microsoft.Xna.Framework.Quaternion",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Matrix, f"{_PREFIX}MatrixReader",
                      "Microsoft.Xna.Framework.Matrix",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Color, f"{_PREFIX}ColorReader",
                      "Microsoft.Xna.Framework.Color",
                      lambda output, value: output.Write(value)),
        _SimpleWriter(Point, f"{_PREFIX}PointReader",
                      "Microsoft.Xna.Framework.Point",
                      lambda output, value: (output.WriteInt32(value.X),
                                             output.WriteInt32(value.Y))),
        _SimpleWriter(Rectangle, f"{_PREFIX}RectangleReader",
                      "Microsoft.Xna.Framework.Rectangle",
                      lambda output, value: (output.WriteInt32(value.X),
                                             output.WriteInt32(value.Y),
                                             output.WriteInt32(value.Width),
                                             output.WriteInt32(value.Height))),
        _SimpleWriter(Texture2DContent, f"{_PREFIX}Texture2DReader",
                      "Microsoft.Xna.Framework.Graphics.Texture2D",
                      _write_texture2d, compressible=False),
        _SimpleWriter(SpriteFontContent, f"{_PREFIX}SpriteFontReader",
                      "Microsoft.Xna.Framework.Graphics.SpriteFont",
                      _write_sprite_font),
        _SimpleWriter(SoundEffectContent, f"{_PREFIX}SoundEffectReader",
                      "Microsoft.Xna.Framework.Audio.SoundEffect",
                      _write_sound_effect, compressible=False),
        _SimpleWriter(SongContent, f"{_PREFIX}SongReader",
                      "Microsoft.Xna.Framework.Media.Song", _write_song),
        _SimpleWriter(VideoContent, f"{_PREFIX}VideoReader",
                      "Microsoft.Xna.Framework.Media.Video", _write_video),
        _SimpleWriter(VertexDeclarationContent,
                      f"{_PREFIX}VertexDeclarationReader",
                      "Microsoft.Xna.Framework.Graphics.VertexDeclaration",
                      _write_vertex_declaration),
        _SimpleWriter(VertexBufferContent, f"{_PREFIX}VertexBufferReader",
                      "Microsoft.Xna.Framework.Graphics.VertexBuffer",
                      _write_vertex_buffer, compressible=False),
        _SimpleWriter(IndexCollection, f"{_PREFIX}IndexBufferReader",
                      "Microsoft.Xna.Framework.Graphics.IndexBuffer",
                      _write_index_buffer),
        _SimpleWriter(BasicMaterialContent, f"{_PREFIX}BasicEffectReader",
                      "Microsoft.Xna.Framework.Graphics.BasicEffect",
                      _write_basic_effect),
    ]
    from ...Processors._content import ModelContent

    writers.append(_SimpleWriter(
        ModelContent, f"{_PREFIX}ModelReader",
        "Microsoft.Xna.Framework.Graphics.Model", _write_model))
    return writers


def list_writer(element: type) -> ContentTypeWriter:
    """The writer for ``List<element>``.

    Built on demand rather than enumerated: the element types a list may hold
    are exactly the ones with a CLR name a runtime can resolve, and that table
    is :data:`_RUNTIME_NAMES` -- written once.
    """
    if element not in _RUNTIME_NAMES:
        raise InvalidContentException(
            f"a list of {getattr(element, '__name__', element)} has no runtime "
            "element type name; the element types with one are "
            + ", ".join(sorted(kind.__name__ for kind in _RUNTIME_NAMES)))
    return _ListWriter(element)


_RUNTIME_NAMES.update({
    bool: "System.Boolean", int: "System.Int32", float: "System.Single",
    str: "System.String", timedelta: "System.TimeSpan",
    Vector2: "Microsoft.Xna.Framework.Vector2",
    Vector3: "Microsoft.Xna.Framework.Vector3",
    Vector4: "Microsoft.Xna.Framework.Vector4",
    Quaternion: "Microsoft.Xna.Framework.Quaternion",
    Matrix: "Microsoft.Xna.Framework.Matrix",
    Color: "Microsoft.Xna.Framework.Color",
    Point: "Microsoft.Xna.Framework.Point",
    Rectangle: "Microsoft.Xna.Framework.Rectangle",
})
