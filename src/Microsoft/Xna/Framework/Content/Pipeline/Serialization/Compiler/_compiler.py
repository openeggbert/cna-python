"""The XNB writer: where built content becomes a file a runtime loads.

This is the end of the pipeline and the only part of it whose output is checked
by something other than itself -- the ``ContentManager`` in this same
repository reads what is written here, which is the strongest oracle the project
has for any of it.

The format, exactly:

* ``XNB``, a platform byte, format version 5, a flags byte.
* The file's total size, including the ten bytes above.
* A 7-bit encoded count of *type readers*, then each reader's name and version.
* A 7-bit encoded count of *shared resources*.
* The primary object, then each shared resource, every one prefixed by a 7-bit
  encoded 1-based index into the reader table -- or zero, meaning null.

Two things about that are easy to get wrong and are got right here. The reader
table is built *while writing*, because a writer discovers which readers it
needs only by writing; so the body is written to a buffer first and the header
is assembled once the table is complete. And the size in the header counts the
header itself, which is why it cannot be written until everything else is.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Callable, Generic, TypeVar

from ..... import Color, Matrix, Quaternion, Vector2, Vector3, Vector4
from .....Graphics import GraphicsProfile
from ..._binary_writer import _BinaryWriter
from ..._errors import InvalidContentException, PipelineException
from ..._identity import ExternalReferenceOfT
from ..._target import TargetPlatform

T = TypeVar("T")

#: The platform byte each target writes into the header.
_PLATFORM_BYTES = {
    TargetPlatform.Windows: ord("w"),
    TargetPlatform.Xbox360: ord("x"),
    TargetPlatform.WindowsPhone: ord("m"),
}

#: XNA 4.0's format version. Version 4 is XNA 3.1 and is a different file.
_FORMAT_VERSION = 5

#: Set in the flags byte when the profile is HiDef.
_HIDEF_FLAG = 0x01

#: Set in the flags byte when the body is LZX-compressed.
_COMPRESSED_FLAG = 0x80


class ContentTypeWriter:
    """Knows how to write one type, and which runtime reader reads it back."""

    __slots__ = ("_target_type", "_compiler")

    def __init__(self, targetType: type) -> None:
        if not isinstance(targetType, type):
            raise TypeError(
                f"targetType must be a type, not {type(targetType).__name__}")
        self._target_type = targetType
        self._compiler: "ContentCompiler | None" = None

    def Initialize(self, compiler: "ContentCompiler") -> None:
        """Called once, before anything is written, with the compiler in charge.

        A writer that needs *other* writers -- a list writer needs its element's
        -- looks them up here rather than at construction, because the compiler
        is what knows them and it is not built yet when a writer is.
        """
        self._compiler = compiler

    @property
    def TargetType(self) -> type:
        return self._target_type

    @property
    def TypeVersion(self) -> int:
        """The version the runtime reader must agree with.

        Zero everywhere here, deliberately: a non-zero version is a promise that
        this writer's format has changed since some earlier one, and none of
        them has.
        """
        return 0

    @property
    def CanDeserializeIntoExistingObject(self) -> bool:
        return False

    def Write(self, output: "ContentWriter", value: object) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.Write must be overridden")

    def GetRuntimeType(self, targetPlatform: TargetPlatform) -> str:
        """The CLR name of the type the runtime will build."""
        raise NotImplementedError(
            f"{type(self).__name__}.GetRuntimeType must be overridden")

    def GetRuntimeReader(self, targetPlatform: TargetPlatform) -> str:
        """The CLR name of the reader that builds it."""
        raise NotImplementedError(
            f"{type(self).__name__}.GetRuntimeReader must be overridden")

    def ShouldCompressContent(self, targetPlatform: TargetPlatform,
                              value: object) -> bool:
        """Whether this content is worth compressing.

        True by default and false for content that is already compressed --
        which is what stops a DXT texture or an MP3 from being run through LZX
        for no gain and a slower load.
        """
        return True


class ContentTypeWriterOfT(ContentTypeWriter, Generic[T]):
    """A writer whose target type is its closed generic argument."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(self._closed_target())

    @classmethod
    def _closed_target(cls) -> type:
        for base in getattr(cls, "__orig_bases__", ()):
            arguments = getattr(base, "__args__", ())
            if arguments and isinstance(arguments[0], type):
                return arguments[0]
        raise TypeError(
            f"{cls.__name__} does not close ContentTypeWriterOfT's type "
            "argument, so it has no target type")


class ContentTypeWriterAttribute:
    """Marks a class as a content type writer the compiler should find."""

    __slots__ = ()

    def __call__(self, target: type) -> type:
        setattr(target, "_xna_content_type_writer", True)
        return target


class ContentWriter(_BinaryWriter):
    """Writes one asset's object graph.

    A caller does not construct one: ``ContentCompiler.Compile`` does, because
    the writer needs the reader table and the shared-resource list that only the
    compiler has.
    """

    __slots__ = ("_compiler", "_target_platform", "_target_profile",
                 "_shared_resources", "_shared_indices")

    def __init__(self, compiler: "ContentCompiler", stream,
                 targetPlatform: TargetPlatform,
                 targetProfile: GraphicsProfile) -> None:
        super().__init__(stream)
        self._compiler = compiler
        self._target_platform = targetPlatform
        self._target_profile = targetProfile
        self._shared_resources: list[object] = []
        self._shared_indices: dict[int, int] = {}

    @property
    def TargetPlatform(self) -> TargetPlatform:
        return self._target_platform

    @property
    def TargetProfile(self) -> GraphicsProfile:
        return self._target_profile

    def Dispose(self, disposing: bool = True) -> None:
        if disposing:
            self.close()

    def WriteObject(self, value: object,
                    typeWriter: ContentTypeWriter | None = None) -> None:
        """Writes ``value`` with its reader index in front of it.

        A ``None`` is written as index zero, which is how the format spells
        null -- and is why a null costs one byte rather than a type name.
        """
        if value is None:
            self.Write7BitEncodedInt(0)
            return
        writer = typeWriter or self._compiler._writer_for(value)
        self.Write7BitEncodedInt(self._compiler._index_of(writer))
        writer.Write(self, value)

    def WriteRawObject(self, value: object,
                       typeWriter: ContentTypeWriter | None = None) -> None:
        """Writes ``value`` with *no* reader index.

        For a field whose type is already known from where it appears -- an
        element of a typed list, say -- which is what makes a list of a thousand
        vectors a thousand vectors rather than a thousand type indices as well.
        """
        if value is None:
            raise InvalidContentException(
                "a raw object may not be null: nothing precedes it that could "
                "say so")
        writer = typeWriter or self._compiler._writer_for(value)
        writer.Write(self, value)

    def WriteSharedResource(self, value: object) -> None:
        """Writes a reference to an object written once at the end of the file.

        Sharing is by identity, not by equality: two references to the same
        object become one resource, and two equal objects stay two. That is what
        preserves the graph -- a model whose meshes share one material must load
        with them still sharing it.
        """
        if value is None:
            self.Write7BitEncodedInt(0)
            return
        key = id(value)
        index = self._shared_indices.get(key)
        if index is None:
            self._shared_resources.append(value)
            index = len(self._shared_resources)
            self._shared_indices[key] = index
        self.Write7BitEncodedInt(index)

    def WriteExternalReference(self, reference: ExternalReferenceOfT | None) -> None:
        """Writes the *built* file name a reference points at, relative to the asset.

        A relative path is the point: the built content is loaded from wherever
        the game installed it, and an absolute path from the build machine would
        be meaningless there.
        """
        if reference is None or not reference.Filename:
            self.WriteString("")
            return
        self.WriteString(self._compiler._relative_output(reference.Filename))

    # -- the typed writes XNA adds to BinaryWriter ---------------------------
    #
    # XNA spells these as six ``Write`` *overloads* rather than six named
    # methods, and the contract says so, which is why the halves below are
    # private: adding ``WriteVector3`` to the public surface would be claiming a
    # member XNA does not have. ``Write`` is the whole public spelling.

    def Write(self, value: object) -> None:
        """``BinaryWriter.Write``, plus XNA's six value types."""
        if isinstance(value, Vector2):
            self.WriteSingle(value.X)
            self.WriteSingle(value.Y)
        elif isinstance(value, Vector3):
            self.WriteSingle(value.X)
            self.WriteSingle(value.Y)
            self.WriteSingle(value.Z)
        elif isinstance(value, (Vector4, Quaternion)):
            self.WriteSingle(value.X)
            self.WriteSingle(value.Y)
            self.WriteSingle(value.Z)
            self.WriteSingle(value.W)
        elif isinstance(value, Matrix):
            for row in range(1, 5):
                for column in range(1, 5):
                    self.WriteSingle(getattr(value, f"M{row}{column}"))
        elif isinstance(value, Color):
            # Four packed bytes in RGBA order, which is what ``ColorReader``
            # reads back.
            self.WriteByte(value.R)
            self.WriteByte(value.G)
            self.WriteByte(value.B)
            self.WriteByte(value.A)
        else:
            super().Write(value)


ContentWriter.__xna_arities__ = {
    "Dispose": {0, 1}, "WriteObject": {1, 2}, "WriteRawObject": {1, 2},
    "WriteSharedResource": {1}, "WriteExternalReference": {1}, "Write": {1},
}
ContentTypeWriter.__xna_arities__ = {"__init__": {1}}
ContentTypeWriterAttribute.__xna_arities__ = {"__init__": {0}}
ContentTypeWriterOfT.__xna_arities__ = {"__init__": {0}, "Write": {2}}


class ContentCompiler:
    """Finds the writer for a type, and turns an object into an XNB file."""

    __slots__ = ("_writers", "_by_type", "_output_directory")

    def __init__(self) -> None:
        from ._writers import builtin_writers

        self._writers: list[ContentTypeWriter] = []
        self._by_type: dict[object, ContentTypeWriter] = {}
        self._output_directory = ""
        for writer in builtin_writers():
            writer.Initialize(self)
            self._by_type[writer.TargetType] = writer

    def GetTypeWriter(self, type_: type) -> ContentTypeWriter:
        """The writer for ``type_``, or the nearest one its bases provide.

        Walking the bases is what lets one writer serve a whole hierarchy --
        every ``PixelBitmapContent`` variant writes the same way -- while an
        exact match still wins where one exists.
        """
        writer = self._by_type.get(type_)
        if writer is not None:
            return writer
        if type_ is list:
            raise PipelineException(
                "a list's writer depends on what is in it, so it is resolved "
                "from the value rather than the type; ContentWriter.WriteObject "
                "does that")
        for base in getattr(type_, "__mro__", ())[1:]:
            candidate = self._by_type.get(base)
            if candidate is not None:
                self._by_type[type_] = candidate
                return candidate
        raise PipelineException(
            f"no ContentTypeWriter is registered for {type_.__name__}; the "
            "content pipeline cannot write it")

    def _compile(self, stream, value: object, targetPlatform: TargetPlatform,
                 targetProfile: GraphicsProfile, compressContent: bool,
                 rootDirectory: str, referenceRelocationPath: str) -> None:
        """Writes ``value`` to ``stream`` as a complete XNB file.

        Private, because XNA's ``ContentCompiler.Compile`` is ``internal``: a
        content project drives the compiler through ``Tasks.BuildContent``, and
        ``GetTypeWriter`` is the only thing the type publishes. Making it public
        here would be claiming a member XNA does not have.
        """
        platform = TargetPlatform(targetPlatform)
        profile = GraphicsProfile(targetProfile)
        self._output_directory = referenceRelocationPath or rootDirectory or ""
        self._writers = []
        body = BytesIO()
        writer = ContentWriter(self, body, platform, profile)
        writer.WriteObject(value)
        index = 0
        # Writing a shared resource can discover another one, so the list is
        # walked by index rather than iterated: appending while iterating is
        # exactly the case a for-loop would miss.
        while index < len(writer._shared_resources):
            writer.WriteObject(writer._shared_resources[index])
            index += 1
        payload = self._header_payload(writer) + body.getvalue()
        compress = compressContent and self._should_compress(value, platform)
        if compress:
            raise NotImplementedError(
                "compressed XNB output is not implemented: writing one needs an "
                "LZX *compressor*, and this repository has the decompressor "
                "only (Content/_lzx.py). Uncompressed XNB is a complete, valid "
                "XNA 4.0 file that this repository's own ContentManager loads, "
                "so nothing is unreachable -- the files are larger. Unblocked "
                "by an LZX compressor.")
        flags = _HIDEF_FLAG if profile is GraphicsProfile.HiDef else 0
        header = bytes((ord("X"), ord("N"), ord("B"),
                        _PLATFORM_BYTES[platform], _FORMAT_VERSION, flags))
        total = len(header) + 4 + len(payload)
        stream.write(header)
        stream.write(total.to_bytes(4, "little"))
        stream.write(payload)

    def _header_payload(self, writer: ContentWriter) -> bytes:
        """The reader table and the shared-resource count, as bytes.

        Written after the body because the table is discovered by writing it.
        """
        buffer = BytesIO()
        header = _BinaryWriter(buffer)
        header.Write7BitEncodedInt(len(self._writers))
        for entry in self._writers:
            header.WriteString(entry.GetRuntimeReader(writer.TargetPlatform))
            header.WriteInt32(entry.TypeVersion)
        header.Write7BitEncodedInt(len(writer._shared_resources))
        return buffer.getvalue()

    def _index_of(self, writer: ContentTypeWriter) -> int:
        """This writer's 1-based index in the file's reader table."""
        for index, entry in enumerate(self._writers):
            if entry is writer:
                return index + 1
        self._writers.append(writer)
        return len(self._writers)

    def _should_compress(self, value: object, platform: TargetPlatform) -> bool:
        try:
            writer = self.GetTypeWriter(type(value))
        except PipelineException:
            return False
        return writer.ShouldCompressContent(platform, value)

    def _relative_output(self, filename: str) -> str:
        import os

        if not self._output_directory:
            return filename
        try:
            relative = os.path.relpath(filename, self._output_directory)
        except ValueError:
            return filename
        return relative.replace(os.sep, "\\")

    def _writer_for(self, value: object) -> ContentTypeWriter:
        """The writer for a *value*, which is what a list needs.

        ``List<T>`` has one reader per element type, so the writer cannot be
        found from ``list`` alone. The element type comes from the first entry,
        and every other entry is checked against it when the list is written --
        a heterogeneous list is a content error, not something to write twice.
        """
        if not isinstance(value, list):
            return self.GetTypeWriter(type(value))
        if not value:
            raise InvalidContentException(
                "an empty list cannot be written: its element type is what "
                "names the runtime reader, and an empty list has none")
        from ._writers import list_writer

        element = type(value[0])
        writer = self._by_type.get(("list", element))
        if writer is None:
            writer = list_writer(element)
            writer.Initialize(self)
            self._by_type[("list", element)] = writer
        return writer

    def _register(self, writer: ContentTypeWriter) -> None:
        """Adds a writer of a caller's own, ahead of the built-in for its type."""
        writer.Initialize(self)
        self._by_type[writer.TargetType] = writer
