"""A parsed `.cnb` container, and the pieces a schema decoder reads it through.

A :class:`CnbDocument` that exists is a container that is structurally sound.
Parsing applies every container invariant -- magic, versions, reserved-field
zeroing, both structural checksums, every chunk checksum, overflow-safe offset
arithmetic, alignment, table-of-contents ordering, exact non-overlapping
coverage of the file, and zeroed alignment padding -- before any accessor can
hand out a byte. A schema decoder only has to worry about its own contents.

Lifetime is explicit. A document owns its bytes; a reader opened from one
*borrows* them, and CNA refuses to release the document until every such reader
is closed. Both are context managers, and closing in the wrong order raises
rather than corrupting anything.
"""

from __future__ import annotations

import ctypes as c
import os
from dataclasses import dataclass
from typing import Iterator, Sequence

from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .format import (
    AssetType,
    ChunkFlags,
    CnbReadLimits,
    Compression,
    _chunk_ids_array,
    _limits_pointer,
)
from .primitives import CnbReader
from .textures import CnbTextureData

__all__ = ["CnbChunk", "CnbDocument", "CnbExternalReference", "CnbMetadata"]


@dataclass(frozen=True)
class CnbChunk:
    """One parsed table-of-contents entry.

    ``stored_size`` is what the chunk occupies in the file and
    ``uncompressed_size`` what it expands to; they are equal exactly when
    ``compression`` is ``Compression.NoCompression``, which the reader requires.
    """

    index: int
    type: int
    offset: int
    stored_size: int
    uncompressed_size: int
    checksum: int
    compression: Compression
    alignment: int
    flags: int
    is_mandatory: bool

    @property
    def type_text(self) -> str:
        """The chunk's four characters, for diagnostics."""
        from .format import chunk_id_text

        return chunk_id_text(self.type)


@dataclass(frozen=True)
class CnbMetadata:
    """The ``CMET`` chunk: whether it was present, and the two names it carries.

    ``asset_type_name`` is load-bearing for a custom asset type and diagnostic
    for a built-in one: a custom identifier is a 31-bit hash of the name, so a
    numeric match is only a candidate and the name settles it.
    ``content_name`` is provenance only -- nothing reads it to make a decision.
    """

    present: bool
    flags: int
    asset_type_name: str
    content_name: str


@dataclass(frozen=True)
class CnbExternalReference:
    """One entry of the optional ``XREF`` table.

    ``name`` is always relative, always ``/``-separated and never contains a
    ``..`` segment; parsing enforces all three before the name can reach any
    path-resolution code. ``expected_asset_type_id`` is
    ``AssetType.Invalid`` when the referring schema does not constrain it.
    """

    index: int
    name: str
    flags: int
    expected_asset_type_id: int


class CnbDocument:
    """A parsed, fully validated `.cnb` container.

    Immutable once parsed. Use it as a context manager, or call :meth:`close`;
    a document is refused release while any reader opened from it is still open,
    which is CNA's rule and is reported rather than worked around.
    """

    __slots__ = ("_handle", "_readers")

    def __init__(self, handle: _support.NativeHandle) -> None:
        # Constructed through the classmethods below; the handle is already owned.
        self._handle = handle
        self._readers: list[CnbReader] = []

    # --- construction ------------------------------------------------------

    @classmethod
    def parse(cls, data: bytes, *, origin: str = "",
              limits: CnbReadLimits | None = None) -> "CnbDocument":
        """Parses and validates a complete `.cnb` byte image.

        The bytes are copied into the document, which then owns them, so the
        caller's buffer need not outlive it. ``origin`` names the file in
        diagnostics and is normally its path.
        """
        pointer, count, keep = _support.read_only_bytes(data, "data")
        view, keep_origin = _support.string_view(origin, "origin")
        limits_pointer, keep_limits = _limits_pointer(limits)
        handle = _support.out_handle(
            "cna_cnb_document_parse", pointer, c.c_uint64(count), view, limits_pointer)
        del keep, keep_origin, keep_limits
        return cls(_support.NativeHandle(handle, "cna_cnb_document_destroy", "document"))

    @classmethod
    def parse_file(cls, path: "str | os.PathLike[str]", *,
                   limits: CnbReadLimits | None = None) -> "CnbDocument":
        """Reads a `.cnb` file from disk and parses it.

        The file's size is checked against ``max_file_size`` before it is read,
        so an oversized file is refused without ever being allocated.
        """
        view, keep = _support.string_view(os.fspath(path), "path")
        limits_pointer, keep_limits = _limits_pointer(limits)
        handle = _support.out_handle("cna_cnb_document_parse_file", view, limits_pointer)
        del keep, keep_limits
        return cls(_support.NativeHandle(handle, "cna_cnb_document_destroy", "document"))

    # --- lifetime ----------------------------------------------------------

    @property
    def closed(self) -> bool:
        """Whether this document has been released."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the document.

        Every reader opened from it must be closed first; CNA refuses otherwise,
        and that refusal is reported rather than swallowed.
        """
        if self._handle.closed:
            return
        for reader in tuple(self._readers):
            if not reader.closed:
                raise ValueError(
                    "close every reader opened from this document before the document")
        self._readers.clear()
        self._handle.close()

    def __enter__(self) -> "CnbDocument":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    # --- container identity ------------------------------------------------

    @property
    def origin(self) -> str:
        """The name this document reports in diagnostics."""
        return _support.sized_text(
            "cna_cnb_document_get_origin_size", "cna_cnb_document_copy_origin",
            (self._value,), "document origin")

    @property
    def container_version(self) -> tuple[int, int]:
        """The container ``(major, minor)`` version the file declares."""
        return (
            _support.out_u16("cna_cnb_document_get_container_major", self._value),
            _support.out_u16("cna_cnb_document_get_container_minor", self._value),
        )

    @property
    def asset_type_id(self) -> int:
        """The asset type identifier the file holds."""
        return _support.out_u32("cna_cnb_document_get_asset_type_id", self._value)

    @property
    def asset_type(self) -> AssetType | None:
        """The asset type as a named identity, or ``None`` for a custom one."""
        try:
            return AssetType(self.asset_type_id)
        except ValueError:
            return None

    @property
    def asset_schema_version(self) -> int:
        """The asset schema version the file was written to."""
        return _support.out_u32("cna_cnb_document_get_asset_schema_version", self._value)

    @property
    def limits(self) -> CnbReadLimits:
        """The limits this document was parsed with."""
        value = _support.out_struct(
            _abi.CNA_CnbReadLimits, _abi.CNA_CNB_READ_LIMITS_STRUCT_VERSION,
            "cna_cnb_document_get_limits", self._value)
        return CnbReadLimits._from_native(value)

    def require_asset(self, asset_type_id: int, max_schema_version: int) -> None:
        """Requires the file's asset type and schema version to be what a decoder expects.

        Raises ``CnbFormatError`` on a mismatch or an out-of-range schema
        version; version 1 is always the lowest accepted.
        """
        _support.call(
            "cna_cnb_document_require_asset", self._value,
            c.c_uint32(_support.checked(int(asset_type_id), "uint32", "asset_type_id")),
            c.c_uint32(_support.checked(max_schema_version, "uint32", "max_schema_version")))

    # --- chunks ------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        """Number of chunks in the table of contents."""
        return _support.out_u64("cna_cnb_document_get_chunk_count", self._value)

    def chunk(self, index: int) -> CnbChunk:
        """The table-of-contents entry at ``index``."""
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        entry = _support.out_struct(
            _abi.CNA_CnbChunkEntry, _abi.CNA_CNB_CHUNK_ENTRY_STRUCT_VERSION,
            "cna_cnb_document_get_chunk", self._value, position)
        mandatory = _support.out_bool("cna_cnb_chunk_entry_is_mandatory", c.byref(entry))
        return CnbChunk(
            index=int(index), type=int(entry.type), offset=int(entry.offset),
            stored_size=int(entry.stored_size),
            uncompressed_size=int(entry.uncompressed_size),
            checksum=int(entry.checksum), compression=Compression(int(entry.compression)),
            alignment=int(entry.alignment), flags=int(entry.flags),
            is_mandatory=mandatory,
        )

    @property
    def chunks(self) -> tuple[CnbChunk, ...]:
        """Every table-of-contents entry, in file order."""
        return tuple(self.chunk(index) for index in range(self.chunk_count))

    def chunk_data(self, index: int) -> bytes:
        """The **logical** bytes of the chunk at ``index``.

        Decompressed when the chunk was stored compressed, and exactly
        ``CnbChunk.uncompressed_size`` bytes long either way.
        """
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        return _support.two_call_bytes(
            "cna_cnb_document_copy_chunk_data", (self._value, position))

    def open_chunk(self, index: int) -> CnbReader:
        """Opens a bounded reader positioned at the start of the chunk at ``index``.

        The reader **borrows** this document's bytes rather than copying them,
        so it keeps the document alive and must be closed before the document
        is.
        """
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        handle = _support.out_handle(
            "cna_cnb_document_open_chunk", self._value, position)
        reader = CnbReader._adopt(handle, parent=self._handle)
        self._readers.append(reader)
        return reader

    def find_all(self, chunk_type: int) -> tuple[int, ...]:
        """Every table-of-contents index whose entry has this type, in file order."""
        value = c.c_uint32(_support.checked(int(chunk_type), "uint32", "chunk_type"))
        return _support.two_call_uint64s(
            "cna_cnb_document_find_all", (self._value, value))

    def find_single(self, chunk_type: int) -> int | None:
        """The index of the single chunk of this type, or ``None`` if there is none.

        Absence is an ordinary answer. More than one is a malformed file and
        raises.
        """
        value = c.c_uint32(_support.checked(int(chunk_type), "uint32", "chunk_type"))
        found = c.c_uint8()
        index = c.c_uint64()
        _support.call("cna_cnb_document_find_single", self._value, value,
                      c.byref(found), c.byref(index))
        return int(index.value) if found.value else None

    def require_single(self, chunk_type: int) -> int:
        """The index of the single chunk of this type, which must be present once."""
        value = c.c_uint32(_support.checked(int(chunk_type), "uint32", "chunk_type"))
        return _support.out_u64("cna_cnb_document_require_single", self._value, value)

    def require_mandatory_chunks_understood(self, known_types: Sequence[int]) -> None:
        """Enforces the mandatory-chunk rule for a schema decoder.

        A chunk carrying the mandatory flag whose identifier is neither
        container-defined nor listed here means the file relies on something
        this build cannot honour, so the whole file is refused. An unknown
        *optional* chunk passes, which is what lets a newer writer add data an
        older reader can safely skip.
        """
        array, count = _chunk_ids_array(known_types)
        _support.call("cna_cnb_document_require_mandatory_chunks_understood",
                      self._value, array, c.c_uint64(count))

    # --- metadata and references -------------------------------------------

    @property
    def metadata(self) -> CnbMetadata:
        """The file's ``CMET`` metadata, with both of its names."""
        value = _support.out_struct(
            _abi.CNA_CnbMetadata, _abi.CNA_CNB_METADATA_STRUCT_VERSION,
            "cna_cnb_document_get_metadata", self._value)
        return CnbMetadata(
            present=bool(value.present),
            flags=int(value.flags),
            asset_type_name=_support.sized_text(
                "cna_cnb_document_get_metadata_asset_type_name_size",
                "cna_cnb_document_copy_metadata_asset_type_name",
                (self._value,), "metadata asset type name"),
            content_name=_support.sized_text(
                "cna_cnb_document_get_metadata_content_name_size",
                "cna_cnb_document_copy_metadata_content_name",
                (self._value,), "metadata content name"),
        )

    @property
    def external_reference_count(self) -> int:
        """Number of entries in the file's ``XREF`` table; zero when there is none."""
        return _support.out_u64(
            "cna_cnb_document_get_external_reference_count", self._value)

    def external_reference(self, index: int, *,
                           what_for_diagnostics: str = "") -> CnbExternalReference:
        """One ``XREF`` entry, with its logical name.

        ``what_for_diagnostics`` is the noun naming what referred to it, used
        only in CNA's own diagnostic if the entry is rejected.
        """
        position = c.c_uint64(_support.checked(index, "uint64", "index"))
        view, keep = _support.string_view(what_for_diagnostics, "what_for_diagnostics")
        value = _support.out_struct(
            _abi.CNA_CnbExternalReference,
            _abi.CNA_CNB_EXTERNAL_REFERENCE_STRUCT_VERSION,
            "cna_cnb_document_get_external_reference", self._value, position, view)
        del keep
        name = _support.sized_text(
            "cna_cnb_document_get_external_reference_name_size",
            "cna_cnb_document_copy_external_reference_name",
            (self._value, position), "external reference name")
        return CnbExternalReference(
            index=int(index), name=name, flags=int(value.flags),
            expected_asset_type_id=int(value.expected_asset_type_id))

    @property
    def external_references(self) -> tuple[CnbExternalReference, ...]:
        """Every ``XREF`` entry, in the order the schema's own indices expect."""
        return tuple(self.external_reference(index)
                     for index in range(self.external_reference_count))

    def read_embedded_texture2d(self, label: str) -> CnbTextureData:
        """Reads back a texture embedded by
        :meth:`CnbWriter.append_embedded_texture2d
        <cna.extensions.content.CnbWriter.append_embedded_texture2d>`.

        ``label`` must be the string the writer was given; it names the owner in
        diagnostics. The caller owns and closes what comes back.
        """
        view, keep = _support.string_view(label, "label")
        handle = _support.out_handle(
            "cna_cnb_document_read_embedded_texture2d", self._value, view)
        del keep
        return CnbTextureData._adopt(handle)

    def __iter__(self) -> Iterator[CnbChunk]:
        return iter(self.chunks)

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbDocument closed>"
        from .format import asset_type_name

        return (f"<CnbDocument {asset_type_name(self.asset_type_id)} "
                f"schema {self.asset_schema_version} chunks {self.chunk_count}>")
