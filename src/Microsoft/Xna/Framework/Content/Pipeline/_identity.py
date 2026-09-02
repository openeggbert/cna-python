"""What a piece of content is, where it came from, and how to point at it.

Three types carry the pipeline's whole notion of provenance. They matter more
than their size suggests: a build error has to name the *source* file and the
line inside it, not the intermediate object that happened to be in hand, and
that is only possible because every content item drags its identity along.
"""

from __future__ import annotations

import ntpath
import os
import posixpath
from typing import Generic, TypeVar

from ._collections import OpaqueDataDictionary

T = TypeVar("T")


class ContentIdentity:
    """Where a piece of content came from.

    ``FragmentIdentifier`` is the part inside the file -- a line number, an XPath
    expression, a mesh name -- and it is a free-form string because the tool
    that produced it decides what it means.
    """

    __slots__ = ("_source_filename", "_source_tool", "_fragment_identifier")

    def __init__(self, sourceFilename: str | None = None,
                 sourceTool: str | None = None,
                 fragmentIdentifier: str | None = None) -> None:
        self._source_filename = _text(sourceFilename, "sourceFilename")
        self._source_tool = _text(sourceTool, "sourceTool")
        self._fragment_identifier = _text(fragmentIdentifier, "fragmentIdentifier")

    @property
    def SourceFilename(self) -> str | None:
        return self._source_filename

    @SourceFilename.setter
    def SourceFilename(self, value: str | None) -> None:
        self._source_filename = _text(value, "SourceFilename")

    @property
    def SourceTool(self) -> str | None:
        return self._source_tool

    @SourceTool.setter
    def SourceTool(self, value: str | None) -> None:
        self._source_tool = _text(value, "SourceTool")

    @property
    def FragmentIdentifier(self) -> str | None:
        return self._fragment_identifier

    @FragmentIdentifier.setter
    def FragmentIdentifier(self, value: str | None) -> None:
        self._fragment_identifier = _text(value, "FragmentIdentifier")

    def __repr__(self) -> str:
        return (f"ContentIdentity({self._source_filename!r}, "
                f"{self._source_tool!r}, {self._fragment_identifier!r})")


class ContentItem:
    """Anything the pipeline can carry from an importer to a writer.

    ``OpaqueData`` is created eagerly and never replaced, because a processor
    reads and writes it through the object it was handed: swapping the
    dictionary out from under one is not something XNA lets a caller do.
    """

    __slots__ = ("_name", "_identity", "_opaque_data")

    def __init__(self) -> None:
        self._name: str | None = None
        self._identity: ContentIdentity | None = None
        self._opaque_data = OpaqueDataDictionary()

    @property
    def Name(self) -> str | None:
        return self._name

    @Name.setter
    def Name(self, value: str | None) -> None:
        self._name = _text(value, "Name")

    @property
    def Identity(self) -> ContentIdentity | None:
        return self._identity

    @Identity.setter
    def Identity(self, value: ContentIdentity | None) -> None:
        if value is not None and not isinstance(value, ContentIdentity):
            raise TypeError(
                f"Identity must be a ContentIdentity, not {type(value).__name__}")
        self._identity = value

    @property
    def OpaqueData(self) -> OpaqueDataDictionary:
        return self._opaque_data

    # XNA marks ``OpaqueData`` with ``[ContentSerializerIgnore]``, and so does
    # this: a material's typed properties *are* windows onto it, so writing both
    # would put every value in the file twice and let the two disagree.
    OpaqueData.fget._xna_content_serializer_ignored = True

    def __repr__(self) -> str:
        return f"{type(self).__name__}(Name={self._name!r})"


class ExternalReferenceOfT(ContentItem, Generic[T]):
    """A pointer to content built separately, by file name.

    The two-argument constructor is the interesting one: the file name is
    resolved *relative to the content that refers to it*, which is what lets a
    model name its textures the way the artist did rather than the way the build
    directory happens to be laid out. XNA stores the result as an absolute path,
    and so does this -- a relative one would mean something different depending
    on who read it back.
    """

    __slots__ = ("_filename",)

    def __init__(self, filename: str | None = None,
                 relativeToContent: ContentIdentity | None = None) -> None:
        super().__init__()
        if filename is None:
            if relativeToContent is not None:
                raise TypeError(
                    "an external reference resolved against content needs a filename")
            self._filename = ""
            return
        if not isinstance(filename, str):
            raise TypeError(f"filename must be a str, not {type(filename).__name__}")
        if relativeToContent is None:
            self._filename = _absolute(filename)
            return
        if not isinstance(relativeToContent, ContentIdentity):
            raise TypeError("relativeToContent must be a ContentIdentity, not "
                            f"{type(relativeToContent).__name__}")
        source = relativeToContent.SourceFilename
        if not source:
            raise ValueError(
                "relativeToContent has no SourceFilename to resolve against")
        self._filename = _absolute(_join(_directory(source), filename))

    @property
    def Filename(self) -> str:
        return self._filename

    @Filename.setter
    def Filename(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Filename must be a str, not {type(value).__name__}")
        self._filename = value

    def __repr__(self) -> str:
        return f"ExternalReferenceOfT({self._filename!r})"


def _text(value: object, what: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a str, not {type(value).__name__}")
    return value


def _directory(path: str) -> str:
    """The directory part of ``path``, whichever separator it was written with.

    A content project is authored on Windows and may be built anywhere, so a
    path that arrives with backslashes has to keep meaning what it meant. Asking
    both separators is the only answer that is right on both hosts.
    """
    head = posixpath.dirname(path)
    windows_head = ntpath.dirname(path)
    return windows_head if len(windows_head) > len(head) else head


def _join(directory: str, filename: str) -> str:
    if not directory:
        return filename
    return os.path.join(directory.replace("\\", os.sep), filename.replace("\\", os.sep))


def _absolute(path: str) -> str:
    return os.path.abspath(path.replace("\\", os.sep))
