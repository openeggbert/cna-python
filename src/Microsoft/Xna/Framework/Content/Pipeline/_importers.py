"""The ten importers: files in, content objects out.

Nine of the ten read their format completely. The tenth, ``FbxImporter``, is a
narrow measured blocker and says so precisely -- FBX is a proprietary format
whose only complete reader is Autodesk's SDK, which is not present and is not
something this package may bundle.

The ``.x`` reader is the interesting one. DirectX's ``.x`` is a *self-describing*
format: the file declares the layout of every template it uses before using it,
so a reader can skip a template it does not know rather than failing on it. That
is what this one does, which is why it reads files written by tools whose extra
templates it has never heard of.
"""

from __future__ import annotations

import os
import re

from ... import Color, Matrix, Vector2, Vector3
from ._attributes import ContentImporterAttribute
from ._components import ContentImporterOfT
from ._context import ContentImporterContext
from ._errors import InvalidContentException
from ._identity import ContentIdentity, ExternalReferenceOfT
from ._images import UnsupportedImage, decode_dds, detect
from ._video import VideoContent
from .Audio import AudioContent, AudioFileType
from .Graphics import (
    BasicMaterialContent, Dxt1BitmapContent, Dxt3BitmapContent,
    Dxt5BitmapContent, EffectContent, FontDescription, FontDescriptionStyle,
    GeometryContent, MeshContent, NodeContent, PixelBitmapContentOfT,
    Texture2DContent, TextureContent, VertexChannelNames,
)


class _ColorBitmapContent(PixelBitmapContentOfT):
    """Every importer's uncompressed working format."""

    __slots__ = ()
    _default_element = Color


@ContentImporterAttribute(".wav", DisplayName="Wav Importer",
                          DefaultProcessor="SoundEffectProcessor")
class WavImporter(ContentImporterOfT[AudioContent]):
    """Reads a RIFF/WAVE file, samples and loop points included."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> AudioContent:
        return AudioContent(filename, AudioFileType.Wav)


@ContentImporterAttribute(".mp3", DisplayName="Mp3 Importer",
                          DefaultProcessor="SongProcessor")
class Mp3Importer(ContentImporterOfT[AudioContent]):
    """Reads an MPEG audio file's format. See :class:`.Audio.AudioContent`."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> AudioContent:
        return AudioContent(filename, AudioFileType.Mp3)


@ContentImporterAttribute(".wma", DisplayName="Wma Importer",
                          DefaultProcessor="SongProcessor")
class WmaImporter(ContentImporterOfT[AudioContent]):
    """Reads a Windows Media audio file's format."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> AudioContent:
        return AudioContent(filename, AudioFileType.Wma)


@ContentImporterAttribute(".wmv", DisplayName="Wmv Importer",
                          DefaultProcessor="VideoProcessor")
class WmvImporter(ContentImporterOfT[VideoContent]):
    """Reads a Windows Media video file's header."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> VideoContent:
        return VideoContent(filename)


@ContentImporterAttribute(".fx", DisplayName="Effect Importer",
                          DefaultProcessor="EffectProcessor")
class EffectImporter(ContentImporterOfT[EffectContent]):
    """Reads effect source, and records every file it includes.

    The includes matter even though nothing here compiles them: an effect that
    includes a shared header has to be rebuilt when that header changes, and the
    only place that dependency can be discovered is here.
    """

    __slots__ = ()

    _INCLUDE = re.compile(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]', re.MULTILINE)

    def Import(self, filename: str, context: ContentImporterContext) -> EffectContent:
        with open(filename, "r", encoding="utf-8-sig") as stream:
            source = stream.read()
        content = EffectContent()
        content.EffectCode = source
        content.Identity = ContentIdentity(filename, "EffectImporter")
        content.Name = os.path.splitext(os.path.basename(filename))[0]
        directory = os.path.dirname(os.path.abspath(filename))
        for match in self._INCLUDE.finditer(source):
            context.AddDependency(os.path.join(directory, match.group(1)))
        return content


@ContentImporterAttribute(".spritefont", DisplayName="Sprite Font Importer",
                          DefaultProcessor="FontDescriptionProcessor")
class FontDescriptionImporter(ContentImporterOfT[FontDescription]):
    """Reads a ``.spritefont`` file.

    The format is XNA's own XML: a font name, a size, spacing, a style, an
    optional default character, and a list of character *regions* given as
    start/end pairs. The regions are expanded here, because everything above
    this point wants a set of characters rather than a set of ranges.
    """

    __slots__ = ()

    def Import(self, filename: str,
               context: ContentImporterContext) -> FontDescription:
        from xml.etree import ElementTree

        identity = ContentIdentity(filename, "FontDescriptionImporter")
        tree = ElementTree.parse(filename)
        asset = tree.getroot().find("Asset")
        if asset is None:
            raise InvalidContentException(
                "a .spritefont has an <Asset> element under <XnaContent>",
                identity)
        name = _text(asset, "FontName", identity)
        size = float(_text(asset, "Size", identity))
        spacing = float(_text(asset, "Spacing", identity) or "0")
        style_text = _optional(asset, "Style") or "Regular"
        style = FontDescriptionStyle.Regular
        for word in style_text.replace(",", " ").split():
            style = FontDescriptionStyle(int(style) | int(
                FontDescriptionStyle[word.strip()]))
        description = FontDescription(name, size, spacing, style)
        kerning = _optional(asset, "UseKerning")
        if kerning is not None:
            description.UseKerning = kerning.strip().lower() == "true"
        default = _optional(asset, "DefaultCharacter")
        if default:
            description.DefaultCharacter = default[0]
        regions = asset.find("CharacterRegions")
        for region in (regions if regions is not None else ()):
            start = _character(_raw(region, "Start", identity))
            end = _character(_raw(region, "End", identity))
            if end < start:
                raise InvalidContentException(
                    f"a character region ends ({end}) before it starts ({start})",
                    identity)
            for code in range(start, end + 1):
                description.Characters.add(chr(code))
        description.Identity = identity
        description.Name = os.path.splitext(os.path.basename(filename))[0]
        return description


@ContentImporterAttribute(".bmp", ".dds", ".png", ".tga",
                          DisplayName="Texture Importer",
                          DefaultProcessor="TextureProcessor")
class TextureImporter(ContentImporterOfT[TextureContent]):
    """Reads an image file into a texture, keeping DXT surfaces compressed."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> TextureContent:
        identity = ContentIdentity(filename, "TextureImporter")
        with open(filename, "rb") as stream:
            raw = stream.read()
        try:
            kind = detect(raw)
            if kind == "dds":
                width, height, rows, compressed = decode_dds(raw)
            else:
                from ._images import decode

                width, height, rows = decode(raw)
                compressed = None
        except UnsupportedImage as error:
            raise InvalidContentException(str(error), identity) from error
        texture = Texture2DContent()
        if compressed is not None:
            variant, blocks = compressed
            bitmap = {1: Dxt1BitmapContent, 3: Dxt3BitmapContent,
                      5: Dxt5BitmapContent}[variant](width, height)
            bitmap.SetPixelData(blocks)
        else:
            bitmap = _ColorBitmapContent(width, height)
            for y, row in enumerate(rows):
                target = bitmap.GetRow(y)
                for x, pixel in enumerate(row):
                    target[x] = pixel
        bitmap.Identity = identity
        texture.Mipmaps = bitmap
        texture.Identity = identity
        texture.Name = os.path.splitext(os.path.basename(filename))[0]
        return texture


@ContentImporterAttribute(".xml", DisplayName="XML Importer",
                          DefaultProcessor="PassThroughProcessor")
class XmlImporter(ContentImporterOfT[object]):
    """Reads an XNA intermediate XML file back into the object it describes."""

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> object:
        from .Serialization.Intermediate import IntermediateSerializer

        with open(filename, "r", encoding="utf-8-sig") as stream:
            return IntermediateSerializer.Deserialize(
                stream, os.path.dirname(os.path.abspath(filename)),
                targetType=object)


@ContentImporterAttribute(".fbx", DisplayName="Fbx Importer",
                          DefaultProcessor="ModelProcessor")
class FbxImporter(ContentImporterOfT[NodeContent]):
    """Would read Autodesk FBX. Refuses, and says what would let it.

    BLOCKED_FIXTURE: FBX is a proprietary format. Its binary form is versioned,
    undocumented outside Autodesk's SDK, and the SDK is neither present here nor
    something this package may redistribute. Writing a partial reader would
    produce a model that silently disagrees with the artist's file, which is
    worse than not reading it.

    Unblocked by: a CNA route that imports FBX, or an explicitly redistributable
    reader this build is allowed to depend on. ``XImporter`` reads DirectX
    ``.x``, which every FBX exporter can also write, so the *model path* through
    this pipeline is reachable today.
    """

    __slots__ = ()

    def Import(self, filename: str, context: ContentImporterContext) -> NodeContent:
        raise NotImplementedError(
            f"FbxImporter cannot read {os.path.basename(filename)}: FBX is a "
            "proprietary format with no public specification, its only complete "
            "reader is Autodesk's SDK, and neither this package nor CNA's C ABI "
            "provides one. Export the model as DirectX .x and use XImporter, "
            "which is fully implemented. Unblocked by a CNA route that imports "
            "FBX.")


@ContentImporterAttribute(".x", DisplayName="X Importer",
                          DefaultProcessor="ModelProcessor")
class XImporter(ContentImporterOfT[NodeContent]):
    """Reads DirectX ``.x`` text files into a scene graph."""

    __slots__ = ("_disposed",)

    def __init__(self) -> None:
        self._disposed = False

    def Import(self, filename: str, context: ContentImporterContext) -> NodeContent:
        identity = ContentIdentity(filename, "XImporter")
        with open(filename, "r", encoding="utf-8-sig") as stream:
            text = stream.read()
        header = text[:16]
        if not header.startswith("xof "):
            raise InvalidContentException(
                f"{filename} is not a DirectX .x file: it does not start with "
                "'xof '", identity)
        if header[8:12] != "txt ":
            raise InvalidContentException(
                f"{filename} is a binary or compressed .x file ({header[8:12]!r}); "
                "this reader reads the text form, which every exporter can "
                "write", identity)
        nodes = _XParser(text[16:], identity).parse()
        root = NodeContent()
        root.Name = os.path.splitext(os.path.basename(filename))[0]
        root.Identity = identity
        for node in nodes:
            root.Children.Add(node)
        return root

    def Dispose(self, disposing: bool = True) -> None:
        self._disposed = True

    def __enter__(self) -> "XImporter":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.Dispose()


XImporter.__xna_arities__ = {"Dispose": {0, 1}}


# -- the .x reader ------------------------------------------------------------


class _XParser:
    """A minimal, complete-enough reader for DirectX ``.x`` text files.

    Complete enough means: it reads every template it understands and *skips*
    every template it does not, by counting braces. A ``.x`` file's grammar
    makes that safe -- a data object is always a name, an optional instance
    name, and a brace-delimited body -- so an unknown template costs nothing.
    """

    _TOKEN = re.compile(r'"[^"]*"|[A-Za-z_][A-Za-z0-9_]*|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|[{};,]')

    def __init__(self, text: str, identity: ContentIdentity) -> None:
        # Comments come in two spellings and both run to end of line.
        text = re.sub(r"(//|#)[^\n]*", " ", text)
        self._tokens = self._TOKEN.findall(text)
        self._position = 0
        self._identity = identity
        self._materials: dict[str, BasicMaterialContent] = {}

    def parse(self) -> list[NodeContent]:
        nodes: list[NodeContent] = []
        while self._position < len(self._tokens):
            token = self._peek()
            if token is None:
                break
            if token == "template":
                self._skip_object()
                continue
            if token in ("Frame", "Mesh"):
                node = self._read_object()
                if node is not None:
                    nodes.append(node)
                continue
            if token == "Material":
                self._read_material()
                continue
            self._skip_object()
        return nodes

    # -- token helpers -------------------------------------------------------

    def _peek(self) -> str | None:
        """The next token that means something, without consuming it.

        Separators are noise in a ``.x`` file -- the format ends a value with
        ``;`` and separates entries with ``,`` and is not consistent about
        which -- so they are skipped. A closing brace is **not** skipped: it is
        what ends the object being read, and swallowing it would make every
        nested object end at the wrong place.
        """
        while self._position < len(self._tokens) and \
                self._tokens[self._position] in (";", ","):
            self._position += 1
        return self._tokens[self._position] if self._position < len(self._tokens) \
            else None

    def _next(self) -> str:
        if self._position >= len(self._tokens):
            raise InvalidContentException(
                "the .x file ends in the middle of a data object",
                self._identity)
        token = self._tokens[self._position]
        self._position += 1
        return token

    def _number(self) -> float:
        while True:
            token = self._next()
            if token in (";", ","):
                continue
            try:
                return float(token)
            except ValueError:
                raise InvalidContentException(
                    f"expected a number in the .x file, found {token!r}",
                    self._identity) from None

    def _integer(self) -> int:
        return int(self._number())

    def _open(self) -> str | None:
        """Consumes an optional instance name and the opening brace."""
        name: str | None = None
        token = self._next()
        if token != "{":
            name = token.strip('"')
            token = self._next()
        if token != "{":
            raise InvalidContentException(
                f"expected '{{' in the .x file, found {token!r}", self._identity)
        return name

    def _skip_object(self) -> None:
        self._next()  # the template or object name
        depth = 0
        while self._position < len(self._tokens):
            token = self._next()
            if token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                if depth <= 0:
                    return

    def _skip_body(self) -> None:
        depth = 1
        while self._position < len(self._tokens) and depth:
            token = self._next()
            if token == "{":
                depth += 1
            elif token == "}":
                depth -= 1

    # -- the templates this reader understands -------------------------------

    def _read_object(self) -> NodeContent | None:
        kind = self._next()
        name = self._open()
        if kind == "Frame":
            return self._read_frame(name)
        if kind == "Mesh":
            return self._read_mesh(name)
        self._skip_body()
        return None

    def _read_frame(self, name: str | None) -> NodeContent:
        node = NodeContent()
        node.Name = name
        node.Identity = self._identity
        while True:
            token = self._peek()
            if token is None:
                break
            if self._tokens[self._position] == "}":
                self._position += 1
                break
            if token == "FrameTransformMatrix":
                self._next()
                self._open()
                node.Transform = self._read_matrix()
                self._expect_close()
            elif token in ("Frame", "Mesh"):
                child = self._read_object()
                if child is not None:
                    node.Children.Add(child)
            else:
                self._skip_object()
        return node

    def _read_matrix(self) -> Matrix:
        values = [self._number() for _ in range(16)]
        return Matrix(*values)

    def _read_mesh(self, name: str | None) -> MeshContent:
        mesh = MeshContent()
        mesh.Name = name
        mesh.Identity = self._identity
        count = self._integer()
        for _ in range(count):
            mesh.Positions.Add(Vector3(self._number(), self._number(),
                                       self._number()))
        face_count = self._integer()
        faces: list[list[int]] = []
        for _ in range(face_count):
            corners = self._integer()
            faces.append([self._integer() for _ in range(corners)])
        normals: list[Vector3] = []
        normal_faces: list[list[int]] = []
        texture_coordinates: list[Vector2] = []
        material_indices: list[int] = []
        materials: list[BasicMaterialContent] = []
        while True:
            token = self._peek()
            if token is None:
                break
            if self._tokens[self._position] == "}":
                self._position += 1
                break
            if token == "MeshNormals":
                self._next()
                self._open()
                normals, normal_faces = self._read_normals()
                self._expect_close()
            elif token == "MeshTextureCoords":
                self._next()
                self._open()
                texture_coordinates = self._read_texture_coordinates()
                self._expect_close()
            elif token == "MeshMaterialList":
                self._next()
                self._open()
                material_indices, materials = self._read_material_list()
                self._expect_close()
            else:
                self._skip_object()
        _build_geometry(mesh, faces, normals, normal_faces, texture_coordinates,
                        material_indices, materials)
        return mesh

    def _read_normals(self) -> tuple[list[Vector3], list[list[int]]]:
        count = self._integer()
        normals = [Vector3(self._number(), self._number(), self._number())
                   for _ in range(count)]
        face_count = self._integer()
        faces = []
        for _ in range(face_count):
            corners = self._integer()
            faces.append([self._integer() for _ in range(corners)])
        return normals, faces

    def _read_texture_coordinates(self) -> list[Vector2]:
        count = self._integer()
        return [Vector2(self._number(), self._number()) for _ in range(count)]

    def _read_material_list(self):
        material_count = self._integer()
        face_count = self._integer()
        indices = [self._integer() for _ in range(face_count)]
        materials: list[BasicMaterialContent] = []
        while len(materials) < material_count:
            token = self._peek()
            if token is None or self._tokens[self._position] == "}":
                break
            if token == "Material":
                materials.append(self._read_material())
            elif token == "{":
                # A reference to a named Material declared elsewhere.
                self._next()
                reference = self._next().strip('"')
                self._next()  # the closing brace of the reference
                materials.append(self._materials.get(
                    reference, BasicMaterialContent()))
            else:
                self._skip_object()
        return indices, materials

    def _read_material(self) -> BasicMaterialContent:
        self._next()  # "Material"
        name = self._open()
        material = BasicMaterialContent()
        material.Name = name
        red, green, blue, alpha = (self._number() for _ in range(4))
        material.DiffuseColor = Vector3(red, green, blue)
        material.Alpha = alpha
        material.SpecularPower = self._number()
        material.SpecularColor = Vector3(self._number(), self._number(),
                                         self._number())
        material.EmissiveColor = Vector3(self._number(), self._number(),
                                         self._number())
        while True:
            token = self._peek()
            if token is None or self._tokens[self._position] == "}":
                self._position += 1
                break
            if token == "TextureFilename":
                self._next()
                self._open()
                path = self._next().strip('"')
                material.Texture = ExternalReferenceOfT(path, self._identity)
                self._expect_close()
            else:
                self._skip_object()
        if name:
            self._materials[name] = material
        return material

    def _expect_close(self) -> None:
        while self._position < len(self._tokens):
            token = self._next()
            if token == "}":
                return
            if token in (";", ","):
                continue
            raise InvalidContentException(
                f"expected '}}' in the .x file, found {token!r}", self._identity)


def _build_geometry(mesh: MeshContent, faces, normals, normal_faces,
                    texture_coordinates, material_indices, materials) -> None:
    """Turns ``.x``'s parallel arrays into geometry, split by material.

    ``.x`` stores normals with their *own* face list, which is what lets a file
    share positions between faces that do not share normals. Honouring that is
    the difference between a faceted cube and a smooth one.
    """
    by_material: dict[int, GeometryContent] = {}
    normal_name = VertexChannelNames.Normal()
    texture_name = VertexChannelNames.TextureCoordinate(0)
    for face_index, corners in enumerate(faces):
        material_index = material_indices[face_index] \
            if face_index < len(material_indices) else 0
        geometry = by_material.get(material_index)
        if geometry is None:
            geometry = GeometryContent()
            if material_index < len(materials):
                geometry.Material = materials[material_index]
            mesh.Geometry.Add(geometry)
            if normals:
                geometry.Vertices.Channels.Add(normal_name, Vector3, ())
            if texture_coordinates:
                geometry.Vertices.Channels.Add(texture_name, Vector2, ())
            by_material[material_index] = geometry
        # A polygon with more than three corners is fanned into triangles from
        # its first corner, which is correct for the convex faces .x holds.
        for offset in range(1, len(corners) - 1):
            for corner in (0, offset, offset + 1):
                position = corners[corner]
                index = geometry.Vertices.Add(position)
                if normals:
                    normal_index = normal_faces[face_index][corner] \
                        if face_index < len(normal_faces) else position
                    geometry.Vertices.Channels.Get(normal_name)[index] = \
                        normals[normal_index]
                if texture_coordinates:
                    geometry.Vertices.Channels.Get(texture_name)[index] = \
                        texture_coordinates[position]
                geometry.Indices.Add(index)


def _text(element, name: str, identity: ContentIdentity) -> str:
    found = element.find(name)
    if found is None or found.text is None:
        raise InvalidContentException(
            f"the font description has no <{name}> element", identity)
    return found.text.strip()


def _raw(element, name: str, identity: ContentIdentity) -> str:
    """A character-region bound, *unstripped*.

    A space is a character a font includes, and ``.spritefont`` files write it
    as ``&#32;``. The XML parser resolves that to a real space, and stripping
    the result would turn the most common region's first character into nothing.
    Indentation is still handled: a bound that is not one character after all is
    stripped and tried again.
    """
    found = element.find(name)
    if found is None or found.text is None:
        raise InvalidContentException(
            f"the font description has no <{name}> element", identity)
    return found.text if len(found.text) == 1 else found.text.strip()


def _optional(element, name: str) -> str | None:
    found = element.find(name)
    return None if found is None or found.text is None else found.text.strip()


def _character(text: str) -> int:
    """A character region bound: a literal character, or ``&#NN;``."""
    if text.startswith("&#") and text.endswith(";"):
        body = text[2:-1]
        return int(body[1:], 16) if body[:1] in ("x", "X") else int(body)
    if len(text) != 1:
        raise ValueError(
            f"a character region bound is one character or an &#NN; escape, "
            f"not {text!r}")
    return ord(text)
