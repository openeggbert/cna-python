"""The bounded cursor and the two writers a `.cnb` schema is built from.

These are public because a game defining its own `.cnb` schema needs them: it
has to read and write chunk payloads in exactly the little-endian encoding CNA's
own schemas use, and reimplementing that in Python would be a second format
implementation free to disagree with the first.

* :class:`CnbReader` -- every read is checked against the region's end before a
  byte is touched, and a truncation is a named refusal rather than a silently
  short value.
* :class:`CnbByteWriter` -- the exact counterpart, and deterministic: it reads no
  clock, no random source and no pointer value.
* :class:`CnbWriter` -- assembles a complete, valid container image.

All three are context managers with an explicit ``close``.
"""

from __future__ import annotations

import ctypes as c
import os
from dataclasses import dataclass
from _cna_native import cnb_abi as _abi
from _cna_native import cnb_support as _support

from .format import ChunkFlags, CnbReadLimits, Compression, _limits_pointer
from .textures import CnbTextureData

__all__ = ["CnbByteWriter", "CnbKeyframe", "CnbReader", "CnbWriter"]


@dataclass(frozen=True)
class CnbKeyframe:
    """One bone animation keyframe as the format stores it.

    Translation and scale are ``(x, y, z)``; rotation is a quaternion
    ``(x, y, z, w)``. Times are seconds, which is what the container writes --
    the strict XNA side keeps ticks, and converting here would hide which of the
    two a value came from.
    """

    time_seconds: float
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    scale: tuple[float, float, float]

    @classmethod
    def _from_native(cls, value: _abi.CNA_KeyframeEXT) -> "CnbKeyframe":
        return cls(
            time_seconds=float(value.time_seconds),
            translation=(float(value.translation.x), float(value.translation.y),
                         float(value.translation.z)),
            rotation=(float(value.rotation.x), float(value.rotation.y),
                      float(value.rotation.z), float(value.rotation.w)),
            scale=(float(value.scale.x), float(value.scale.y), float(value.scale.z)),
        )

    def _to_native(self) -> _abi.CNA_KeyframeEXT:
        value = _abi.CNA_KeyframeEXT()
        value.time_seconds = float(self.time_seconds)
        value.translation.x, value.translation.y, value.translation.z = (
            float(item) for item in self.translation)
        (value.rotation.x, value.rotation.y, value.rotation.z,
         value.rotation.w) = (float(item) for item in self.rotation)
        value.scale.x, value.scale.y, value.scale.z = (float(item) for item in self.scale)
        return value


class CnbReader:
    """A bounded, little-endian cursor over one region of a `.cnb` file.

    Integers are assembled from individual bytes and floats are produced from an
    explicitly little-endian integer, so a decoded value never depends on the
    host's byte order or floating-point storage order.

    **Where the bytes came from decides the lifetime.** A reader from
    :meth:`CnbDocument.open_chunk <cna.extensions.content.CnbDocument.open_chunk>`
    borrows its document and keeps it alive; a reader built with
    :meth:`over_bytes` copies what it is given, so the caller's buffer need not
    outlive it.
    """

    __slots__ = ("_handle",)

    def __init__(self) -> None:
        raise TypeError(
            "CnbReader is produced by this module's own operations and is not "
            "constructed directly")

    @classmethod
    def _wrap(cls, handle: _support.NativeHandle) -> "CnbReader":
        """Builds the facade around an already-owned handle.

        Private, and it bypasses ``__init__`` deliberately: the public
        signature a caller reads must not name a native type, and there is
        no owned handle a caller could supply anyway.
        """
        self = cls.__new__(cls)
        self._handle = handle
        return self

    @classmethod
    def over_bytes(cls, data: bytes, *, context: str = "",
                   limits: CnbReadLimits | None = None) -> "CnbReader":
        """A cursor over a **copy** of ``data``.

        ``context`` is prefixed to every diagnostic and should name the region,
        for example ``"'walk.cnb' chunk ACLK"``.
        """
        pointer, count, keep = _support.read_only_bytes(data, "data")
        view, keep_context = _support.string_view(context, "context")
        limits_pointer, keep_limits = _limits_pointer(limits)
        handle = _support.out_handle(
            "cna_cnb_reader_create", pointer, c.c_uint64(count), view, limits_pointer)
        del keep, keep_context, keep_limits
        return cls._wrap(_support.NativeHandle(handle, "cna_cnb_reader_destroy", "reader"))

    @classmethod
    def _adopt(cls, handle: int, *, parent: _support.NativeHandle) -> "CnbReader":
        return cls._wrap(_support.NativeHandle(
            handle, "cna_cnb_reader_destroy", "reader", parent=parent))

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the cursor, and with it any borrow it holds on a document."""
        self._handle.close()

    def __enter__(self) -> "CnbReader":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    # --- position ----------------------------------------------------------

    @property
    def remaining(self) -> int:
        """Bytes not yet consumed."""
        return _support.out_u64("cna_cnb_reader_get_remaining", self._value)

    @property
    def position(self) -> int:
        """Current read offset within the region."""
        return _support.out_u64("cna_cnb_reader_get_position", self._value)

    @property
    def size(self) -> int:
        """Total size of the region."""
        return _support.out_u64("cna_cnb_reader_get_size", self._value)

    @property
    def context(self) -> str:
        """The text this cursor prefixes to its diagnostics."""
        return _support.sized_text(
            "cna_cnb_reader_get_context_size", "cna_cnb_reader_copy_context",
            (self._value,), "reader context")

    # --- primitives --------------------------------------------------------

    def read_u8(self) -> int:
        """Reads one unsigned byte."""
        return _support.out_u8("cna_cnb_reader_read_u8", self._value)

    def read_u16(self) -> int:
        """Reads a little-endian unsigned 16-bit integer."""
        return _support.out_u16("cna_cnb_reader_read_u16", self._value)

    def read_u32(self) -> int:
        """Reads a little-endian unsigned 32-bit integer."""
        return _support.out_u32("cna_cnb_reader_read_u32", self._value)

    def read_u64(self) -> int:
        """Reads a little-endian unsigned 64-bit integer."""
        return _support.out_u64("cna_cnb_reader_read_u64", self._value)

    def read_i32(self) -> int:
        """Reads a little-endian two's-complement signed 32-bit integer."""
        return _support.out_i32("cna_cnb_reader_read_i32", self._value)

    def read_f32(self) -> float:
        """Reads a little-endian IEEE-754 binary32 value."""
        return _support.out_f32("cna_cnb_reader_read_f32", self._value)

    def read_f64(self) -> float:
        """Reads a little-endian IEEE-754 binary64 value."""
        return _support.out_f64("cna_cnb_reader_read_f64", self._value)

    def read_string(self) -> str:
        """Reads a length-prefixed UTF-8 string.

        The declared length is checked against ``max_string_bytes`` and against
        the region's remaining size before any allocation, and the bytes are
        validated as well-formed UTF-8 -- a `.cnb` string can end up as a
        filesystem path, so letting malformed UTF-8 through would push the
        problem somewhere far less prepared for it.
        """
        _support.call("cna_cnb_reader_read_string", self._value, c.byref(c.c_uint64()))
        return _support.two_call_text(
            "cna_cnb_reader_copy_string", (self._value,), "reader string")

    def read_count(self, element_size: int = 0, *, what: str = "") -> int:
        """Reads an element count, checked against the limits and against what could fit.

        ``element_size`` is the size of one element that follows; pass 0 when
        the elements are variable-length, which skips the fit check. ``what`` is
        the noun CNA uses in its diagnostic.
        """
        view, keep = _support.string_view(what, "what")
        value = _support.out_u32(
            "cna_cnb_reader_read_count", self._value,
            c.c_uint64(_support.checked(element_size, "uint64", "element_size")), view)
        del keep
        return value

    def read_bytes(self, byte_count: int) -> bytes:
        """Copies the next ``byte_count`` bytes and advances past them."""
        count = _support.checked(byte_count, "uint64", "byte_count")
        if count == 0:
            written = c.c_uint64()
            _support.call("cna_cnb_reader_read_bytes", self._value, c.c_uint64(0),
                          None, c.c_uint64(0), c.byref(written))
            return b""
        buffer = (c.c_uint8 * count)()
        written = c.c_uint64()
        _support.call("cna_cnb_reader_read_bytes", self._value, c.c_uint64(count),
                      buffer, c.c_uint64(count), c.byref(written))
        return bytes(bytearray(buffer)[: written.value])

    def read_seconds(self, what: str = "") -> float:
        """Reads a duration in seconds, refusing a value a ``TimeSpan`` cannot hold."""
        view, keep = _support.string_view(what, "what")
        value = _support.out_f64("cna_cnb_reader_read_seconds", self._value, view)
        del keep
        return value

    def read_keyframe(self) -> CnbKeyframe:
        """Reads one fixed-layout bone animation keyframe."""
        value = _abi.CNA_KeyframeEXT()
        _support.call("cna_cnb_reader_read_keyframe", self._value, c.byref(value))
        return CnbKeyframe._from_native(value)

    def skip(self, byte_count: int) -> None:
        """Advances the cursor without reading."""
        _support.call("cna_cnb_reader_skip", self._value,
                      c.c_uint64(_support.checked(byte_count, "uint64", "byte_count")))

    def require_exhausted(self) -> None:
        """Requires that the region has been consumed exactly.

        Used at the end of every fixed-layout chunk decoder: trailing bytes mean
        the file and the decoder disagree about the layout, which has to be an
        error rather than something silently ignored.
        """
        _support.call("cna_cnb_reader_require_exhausted", self._value)

    def fail(self, detail: str) -> None:
        """Always raises, with a diagnostic built the way this cursor's own are.

        A Python schema decoder's refusals then read exactly like CNA's, naming
        the region and the offset rather than only the caller's message.
        """
        view, keep = _support.string_view(detail, "detail")
        _support.call("cna_cnb_reader_fail", self._value, view)
        del keep
        raise AssertionError("cna_cnb_reader_fail returned success")  # pragma: no cover

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbReader closed>"
        return f"<CnbReader {self.position}/{self.size}>"


class CnbByteWriter:
    """Emits `.cnb` primitives in their canonical little-endian encoding.

    Deterministic by construction: nothing here consults the clock, a random
    source or a pointer value, which is what makes a built `.cnb`
    byte-deterministic.
    """

    __slots__ = ("_handle",)

    def __init__(self, initial: bytes | None = None) -> None:
        """Creates a writer, optionally appending to a **copy** of ``initial``."""
        if initial is None:
            handle = _support.out_handle("cna_cnb_byte_writer_create")
        else:
            pointer, count, keep = _support.read_only_bytes(initial, "initial")
            handle = _support.out_handle(
                "cna_cnb_byte_writer_create_from_bytes", pointer, c.c_uint64(count))
            del keep
        self._handle = _support.NativeHandle(
            handle, "cna_cnb_byte_writer_destroy", "byte writer")

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the writer and everything it has buffered."""
        self._handle.close()

    def __enter__(self) -> "CnbByteWriter":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    def write_u8(self, value: int) -> None:
        """Appends one byte."""
        _support.call("cna_cnb_byte_writer_write_u8", self._value,
                      c.c_uint8(_support.checked(value, "uint8", "value")))

    def write_u16(self, value: int) -> None:
        """Appends a little-endian unsigned 16-bit integer."""
        _support.call("cna_cnb_byte_writer_write_u16", self._value,
                      c.c_uint16(_support.checked(value, "uint16", "value")))

    def write_u32(self, value: int) -> None:
        """Appends a little-endian unsigned 32-bit integer."""
        _support.call("cna_cnb_byte_writer_write_u32", self._value,
                      c.c_uint32(_support.checked(value, "uint32", "value")))

    def write_u64(self, value: int) -> None:
        """Appends a little-endian unsigned 64-bit integer."""
        _support.call("cna_cnb_byte_writer_write_u64", self._value,
                      c.c_uint64(_support.checked(value, "uint64", "value")))

    def write_i32(self, value: int) -> None:
        """Appends a little-endian two's-complement signed 32-bit integer."""
        _support.call("cna_cnb_byte_writer_write_i32", self._value,
                      c.c_int32(_support.checked(value, "int32", "value")))

    def write_f32(self, value: float) -> None:
        """Appends a little-endian IEEE-754 binary32 value."""
        _support.call("cna_cnb_byte_writer_write_f32", self._value, c.c_float(float(value)))

    def write_f64(self, value: float) -> None:
        """Appends a little-endian IEEE-754 binary64 value."""
        _support.call("cna_cnb_byte_writer_write_f64", self._value, c.c_double(float(value)))

    def write_string(self, value: str) -> None:
        """Appends a byte length followed by the string's UTF-8 bytes."""
        view, keep = _support.string_view(value, "value")
        _support.call("cna_cnb_byte_writer_write_string", self._value, view)
        del keep

    def write_bytes(self, data: bytes) -> None:
        """Appends raw bytes verbatim."""
        pointer, count, keep = _support.read_only_bytes(data, "data")
        _support.call("cna_cnb_byte_writer_write_bytes", self._value,
                      pointer, c.c_uint64(count))
        del keep

    def write_zeros(self, byte_count: int) -> None:
        """Appends ``byte_count`` zero bytes."""
        _support.call("cna_cnb_byte_writer_write_zeros", self._value,
                      c.c_uint64(_support.checked(byte_count, "uint64", "byte_count")))

    def write_keyframe(self, keyframe: CnbKeyframe) -> None:
        """Appends one fixed-layout bone animation keyframe."""
        value = keyframe._to_native()
        _support.call("cna_cnb_byte_writer_write_keyframe", self._value, c.byref(value))

    @property
    def size(self) -> int:
        """Bytes written so far."""
        return _support.out_u64("cna_cnb_byte_writer_get_size", self._value)

    def copy_bytes(self) -> bytes:
        """Everything written so far, leaving the writer unchanged."""
        return _support.two_call_bytes("cna_cnb_byte_writer_copy_bytes", (self._value,))

    def take_bytes(self) -> bytes:
        """Everything written so far, leaving the writer **empty**.

        The transfer is what distinguishes this from :meth:`copy_bytes`: after
        it, :attr:`size` is zero and the bytes are the caller's alone. A refused
        call takes nothing, so a failure leaves the buffer intact.
        """
        return _support.two_call_bytes("cna_cnb_byte_writer_take", (self._value,))

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbByteWriter closed>"
        return f"<CnbByteWriter {self.size} bytes>"


class CnbWriter:
    """Builds a complete, valid `.cnb` byte image for one asset.

    Deterministic by construction: it emits chunks in the order they were added,
    lays the table of contents out in that same order, and zero-fills every
    alignment gap. Given identical inputs it produces byte-identical output.

    The container-level ``CMET`` and ``XREF`` chunks are always emitted first,
    ahead of the schema's own chunks, regardless of when they were set. A schema
    must therefore address chunks by ordinal within a chunk type -- see
    :meth:`CnbDocument.find_all <cna.extensions.content.CnbDocument.find_all>`
    -- never by table-of-contents index.
    """

    __slots__ = ("_handle",)

    def __init__(self, asset_type_id: int, asset_schema_version: int = 1) -> None:
        """Starts a new image; the asset type must not be ``AssetType.Invalid``."""
        handle = _support.out_handle(
            "cna_cnb_writer_create",
            c.c_uint32(_support.checked(int(asset_type_id), "uint32", "asset_type_id")),
            c.c_uint32(_support.checked(asset_schema_version, "uint32",
                                        "asset_schema_version")))
        self._handle = _support.NativeHandle(
            handle, "cna_cnb_writer_destroy", "container writer")

    @property
    def closed(self) -> bool:
        return self._handle.closed

    def close(self) -> None:
        """Releases the writer and every chunk it has buffered."""
        self._handle.close()

    def __enter__(self) -> "CnbWriter":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def _value(self) -> c.c_uint64:
        return c.c_uint64(self._handle.value)

    def set_metadata(self, asset_type_name: str, content_name: str = "") -> None:
        """Sets the ``CMET`` chunk.

        Diagnostic for a built-in asset type. **Not optional for a custom one**:
        a custom identifier is a 31-bit hash of the type name, so the load path
        proves identity by comparing this name against the one the loader was
        registered under, and :meth:`build` refuses a custom-typed file without
        it.
        """
        type_view, keep_type = _support.string_view(asset_type_name, "asset_type_name")
        name_view, keep_name = _support.string_view(content_name, "content_name")
        _support.call("cna_cnb_writer_set_metadata", self._value, type_view, name_view)
        del keep_type, keep_name

    def add_external_reference(self, logical_name: str, *,
                               expected_asset_type_id: int = 0, flags: int = 0) -> None:
        """Appends one entry to the optional ``XREF`` table.

        Call order is the order the schema's own indices expect. Each name is
        validated against the container's own rule -- the same function the
        reader applies -- so the writer has no path to a file its own reader
        would refuse.
        """
        reference = _abi.CNA_CnbExternalReference()
        reference.struct_size = c.sizeof(_abi.CNA_CnbExternalReference)
        reference.struct_version = _abi.CNA_CNB_EXTERNAL_REFERENCE_STRUCT_VERSION
        reference.flags = _support.checked(flags, "uint32", "flags")
        reference.expected_asset_type_id = _support.checked(
            int(expected_asset_type_id), "uint32", "expected_asset_type_id")
        view, keep = _support.string_view(logical_name, "logical_name")
        _support.call("cna_cnb_writer_add_external_reference", self._value,
                      c.byref(reference), view)
        del keep

    def clear_external_references(self) -> None:
        """Empties the ``XREF`` table; with :meth:`add_external_reference` this is
        the whole-table setter: clear, then append in order."""
        _support.call("cna_cnb_writer_clear_external_references", self._value)

    def add_chunk(self, chunk_type: int, data: bytes, *,
                  flags: int | ChunkFlags = ChunkFlags.NoFlags,
                  alignment: int = 1) -> None:
        """Appends one schema chunk.

        The container-defined identifiers ``CMET`` and ``XREF`` are refused
        here: the writer emits each at most once, and a schema adding one as an
        ordinary chunk would produce a file carrying two of a singleton.
        """
        pointer, count, keep = _support.read_only_bytes(data, "data")
        _support.call(
            "cna_cnb_writer_add_chunk", self._value,
            c.c_uint32(_support.checked(int(chunk_type), "uint32", "chunk_type")),
            pointer, c.c_uint64(count),
            c.c_uint32(_support.checked(int(flags), "uint32", "flags")),
            c.c_uint32(_support.checked(alignment, "uint32", "alignment")))
        del keep

    @property
    def schema_chunk_count(self) -> int:
        """Schema chunks added so far, excluding the container-level ones."""
        return _support.out_u64("cna_cnb_writer_get_schema_chunk_count", self._value)

    def set_compression(self, codec: Compression | int, *, level: int = 3) -> None:
        """Compresses this document's schema chunks with ``codec``.

        Off by default. A chunk is emitted compressed only when compression
        actually made it smaller, decided per chunk; container-level chunks are
        always stored. Enabling this raises the file's minimum runtime -- a
        build without the codec cannot open the file at all, not even to read
        its identity.
        """
        _support.call(
            "cna_cnb_writer_set_compression", self._value,
            c.c_uint32(_support.checked(int(codec), "uint32", "codec")),
            c.c_int32(_support.checked(level, "int32", "level")))

    @property
    def limits(self) -> CnbReadLimits:
        """The limits the build will enforce."""
        value = _support.out_struct(
            _abi.CNA_CnbReadLimits, _abi.CNA_CNB_READ_LIMITS_STRUCT_VERSION,
            "cna_cnb_writer_get_limits", self._value)
        return CnbReadLimits._from_native(value)

    def set_limits(self, limits: CnbReadLimits) -> None:
        """Bounds the file so it cannot exceed what a reader with these limits opens.

        It matters because compression breaks the intuition that a file a writer
        built is a file a reader can open: a highly compressible document
        serializes to very little and expands to a great deal. The producer is
        the right place to find that out.
        """
        native = limits._to_native()
        _support.call("cna_cnb_writer_set_limits", self._value, c.byref(native))

    def append_embedded_texture2d(self, texture: CnbTextureData, label: str) -> None:
        """Embeds a 2D texture's chunks in a document of a *different* asset type.

        This is what lets a schema carry an image without a second copy of the
        texture layout: the pixels are stored with exactly the chunks, strides,
        alignment and validation a standalone 2D texture would use, inside this
        file. CNA's own ``SpriteFont`` schema is built on it, and a game's own
        schema can be.

        Embedding is the right default only when the image belongs to exactly one
        asset. A shared texture should be an external reference instead --
        :meth:`add_external_reference` -- so a content manager loads it once.

        ``label`` names the owner in diagnostics, for example ``"SpriteFont"``,
        and must be the same string
        :meth:`CnbDocument.read_embedded_texture2d
        <cna.extensions.content.CnbDocument.read_embedded_texture2d>` is given.
        """
        view, keep = _support.string_view(label, "label")
        _support.call("cna_cnb_writer_append_embedded_texture2d", self._value,
                      texture._value, view)
        del keep

    def build(self) -> bytes:
        """Assembles the finished `.cnb` image.

        Every file this produces is loadable by
        :meth:`CnbDocument.parse <cna.extensions.content.CnbDocument.parse>`.
        Assembling is non-destructive, so calling it twice builds twice rather
        than returning something stale.
        """
        return _support.two_call_bytes("cna_cnb_writer_build", (self._value,))

    def write_to_file(self, path: "str | os.PathLike[str]") -> None:
        """Assembles the image and writes it to ``path``, creating or overwriting."""
        view, keep = _support.string_view(os.fspath(path), "path")
        _support.call("cna_cnb_writer_write_to_file", self._value, view)
        del keep

    def __repr__(self) -> str:
        if self.closed:
            return "<CnbWriter closed>"
        return f"<CnbWriter {self.schema_chunk_count} schema chunks>"
