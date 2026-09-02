"""Private plumbing shared by every ``cna.extensions.content`` slice.

Three things live here because getting any of them wrong once is a memory-safety
bug rather than a behaviour bug:

* **The two-call size/copy protocol.** CNA answers "how many bytes" and "copy
  them here" as separate routes. Doing that by hand at two hundred call sites
  invites a buffer sized from the wrong route, so it is written once.
* **Checked width conversion.** A Python integer is unbounded and a `.cnb` count
  is not, so every value crossing into a fixed-width parameter is range-checked
  here rather than being silently truncated by ctypes.
* **Deterministic handle lifetime.** Every CNA handle this family owns is closed
  explicitly. ``__del__`` is a backstop that reports a leak, never the mechanism
  a correct program relies on.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, Iterable, Sequence

from . import abi
from .errors import NativeError
from .loader import get_library

#: Inclusive bounds of every fixed-width parameter this family passes.
_WIDTHS = {
    "uint8": (0, 0xFF),
    "uint16": (0, 0xFFFF),
    "uint32": (0, 0xFFFFFFFF),
    "uint64": (0, 0xFFFFFFFFFFFFFFFF),
    "int32": (-0x80000000, 0x7FFFFFFF),
}


def checked(value: object, width: str, what: str) -> int:
    """Range-checks a Python integer against the native width it is about to take.

    ``ctypes`` truncates a too-large integer for some widths and raises for
    others, and neither is a usable contract: a count that silently becomes a
    different count is how a caller ends up reading the wrong number of
    elements. This refuses instead, naming the value.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an int, not {type(value).__name__}")
    low, high = _WIDTHS[width]
    if not low <= value <= high:
        raise ValueError(f"{what} must be in {low}..{high}, got {value}")
    return int(value)


def checked_product(count: int, element_size: int, what: str) -> int:
    """Multiplies a count by an element size, refusing a product that cannot fit.

    Python's own arithmetic is exact, so the product is never wrong; what this
    adds is the ceiling, because the result becomes a ``uint64`` byte count.
    """
    product = count * element_size
    if product > _WIDTHS["uint64"][1]:
        raise ValueError(
            f"{what} overflows a 64-bit byte count: {count} x {element_size}")
    return product


def string_view(text: str | None, what: str) -> tuple[abi.CNA_StringView, bytes]:
    """Builds a borrowed ``CNA_StringView`` over ``text``'s UTF-8 bytes.

    The encoded ``bytes`` object is returned alongside and **must** be kept
    alive by the caller for as long as the view is passed to CNA; a view over a
    temporary is a dangling pointer that usually still works.
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise TypeError(f"{what} must be str, not {type(text).__name__}")
    encoded = text.encode("utf-8")
    view = abi.CNA_StringView()
    view.data = encoded if encoded else None
    view.byte_length = len(encoded)
    return view, encoded


def raw_string_view(raw: bytes) -> tuple[abi.CNA_StringView, bytes]:
    """A ``CNA_StringView`` over bytes CNA is expected to validate itself.

    Two routes -- the external-reference name check and the UTF-8 check --
    document that they do *not* validate their input, because the verdict is
    what the caller asked for. Encoding those inputs through
    :func:`string_view` would refuse exactly the bytes the question is about.
    """
    view = abi.CNA_StringView()
    view.data = raw if raw else None
    view.byte_length = len(raw)
    return view, raw


def read_only_bytes(data: object, what: str) -> tuple[object, int, object]:
    """Borrows a bytes-like object as ``(pointer, count, keepalive)``.

    ``bytes``, ``bytearray`` and any C-contiguous ``memoryview`` are accepted
    without an intermediate copy. A null pointer is passed only for an empty
    input, which is the one case CNA documents it for.
    """
    if isinstance(data, (bytes, bytearray)):
        buffer = data
    elif isinstance(data, memoryview):
        if not data.contiguous:
            raise ValueError(f"{what} must be a contiguous buffer")
        buffer = data.cast("B") if data.format != "B" else data
    else:
        try:
            buffer = memoryview(data).cast("B")
        except TypeError as error:
            raise TypeError(f"{what} must be a bytes-like object") from error
    count = len(buffer)
    if count == 0:
        return None, 0, buffer
    array = (c.c_uint8 * count).from_buffer_copy(buffer)
    return array, count, array


def float_array(values: Sequence[float], what: str) -> tuple[object, int]:
    """Copies a float sequence into a C array, or ``(None, 0)`` when it is empty."""
    try:
        count = len(values)
    except TypeError as error:
        raise TypeError(f"{what} must be a sequence of floats") from error
    if count == 0:
        return None, 0
    return (c.c_float * count)(*(float(value) for value in values)), count


def int32_array(values: Sequence[int], what: str) -> tuple[object, int]:
    """Copies a signed-32 sequence into a C array, or ``(None, 0)`` when empty."""
    count = len(values)
    if count == 0:
        return None, 0
    return (c.c_int32 * count)(*(checked(value, "int32", what) for value in values)), count


def uint32_array(values: Sequence[int], what: str) -> tuple[object, int]:
    """Copies an unsigned-32 sequence into a C array, or ``(None, 0)`` when empty."""
    count = len(values)
    if count == 0:
        return None, 0
    return (c.c_uint32 * count)(*(checked(value, "uint32", what) for value in values)), count


#: CNA result code -> the public exception class that names what it means.
#: ``CNA_RESULT_BUFFER_TOO_SMALL`` is absent on purpose: the two-call protocol
#: above sizes every buffer from CNA itself, so seeing it would be a defect in
#: this module rather than a statement about the caller's file, and it falls
#: through to the internal class.
_RESULT_CLASSES = {
    1: "CnbFormatError",           # INVALID_ARGUMENT
    2: "CnbInternalError",         # INVALID_HANDLE
    3: "CnbFormatError",           # INVALID_STATE
    4: "CnbInternalError",         # OUT_OF_MEMORY
    5: "CnbFormatError",           # IO
    6: "CnbUnsupportedError",      # NOT_SUPPORTED
    7: "CnbInternalError",         # PLATFORM
    8: "CnbInternalError",         # THREAD
    9: "CnbInternalError",         # CALLBACK
    10: "CnbLimitError",           # OVERFLOW
    11: "CnbFormatError",          # ENCODING
    12: "CnbInternalError",        # INTERNAL
    13: "CnbInternalError",        # SHUTTING_DOWN
}

#: Routes whose ``CNA_RESULT_IO`` means "the named file or registration is not
#: there" rather than "these bytes are malformed".  CNA uses one code for both,
#: so the route is what distinguishes them.
_MISSING_ROUTES = {
    "cna_cnb_document_parse_file",
    "cna_cnb_import_image_as_texture2d",
    "cna_cnb_import_dds_as_texture_cube",
    "cna_cnb_import_wav_as_sound_effect",
    "cna_cnb_compile_cnj",
    "cna_cnb_build_model_from_cnj",
    "cna_cnb_loader_registry_resolve_for_document",
    "cna_cnb_writer_write_to_file",
}


def _translate(error: NativeError):
    """Maps one CNA failure onto the public compiled-content exception for it.

    Imported at the point of failure rather than at module scope: the public
    package is the only caller, so it is always already imported by the time
    this runs, and the private layer keeps not depending on the public one at
    import time.
    """
    from cna.extensions.content import errors as public

    name = _RESULT_CLASSES.get(error.result, "CnbInternalError")
    if error.result == 5 and error.operation in _MISSING_ROUTES:
        name = "CnbMissingReferenceError"
    return getattr(public, name)(
        error.operation, error.result, error.category, error.native_message)


def call(operation: str, *arguments: object) -> None:
    """Invokes one CNA route, raising the public exception for any failure."""
    library = get_library()
    function = getattr(library, operation)
    try:
        library.check(function(*arguments), operation)
    except NativeError as error:
        raise _translate(error) from None


#: ``CNA_RESULT_BUFFER_TOO_SMALL``.  A copy route that cannot fit its output
#: still writes the required byte count, which is exactly how the size half of
#: the two-call protocol asks the question: call with no destination, read the
#: count, allocate that much.  Treating it as a failure would make the protocol
#: unusable on every route whose output is not empty.
_BUFFER_TOO_SMALL = 14


def size_call(operation: str, *arguments: object) -> None:
    """Runs the sizing half of the two-call protocol.

    ``CNA_RESULT_BUFFER_TOO_SMALL`` is the expected answer for a non-empty
    output and success for an empty one; anything else is a real failure.
    """
    library = get_library()
    function = getattr(library, operation)
    result = int(function(*arguments))
    if result in (0, _BUFFER_TOO_SMALL):
        return
    try:
        library.check(result, operation)
    except NativeError as error:
        raise _translate(error) from None


def out_u8(operation: str, *arguments: object) -> int:
    value = c.c_uint8()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_bool(operation: str, *arguments: object) -> bool:
    return out_u8(operation, *arguments) != 0


def out_u16(operation: str, *arguments: object) -> int:
    value = c.c_uint16()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_u32(operation: str, *arguments: object) -> int:
    value = c.c_uint32()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_u64(operation: str, *arguments: object) -> int:
    value = c.c_uint64()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_i32(operation: str, *arguments: object) -> int:
    value = c.c_int32()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_f32(operation: str, *arguments: object) -> float:
    value = c.c_float()
    call(operation, *arguments, c.byref(value))
    return float(value.value)


def out_f64(operation: str, *arguments: object) -> float:
    value = c.c_double()
    call(operation, *arguments, c.byref(value))
    return float(value.value)


def out_handle(operation: str, *arguments: object) -> int:
    handle = c.c_uint64()
    call(operation, *arguments, c.byref(handle))
    return int(handle.value)


def out_struct(structure: type, version: int, operation: str, *arguments: object):
    """Fills a versioned CNA output structure, setting the two header fields first."""
    value = structure()
    value.struct_size = c.sizeof(structure)
    value.struct_version = version
    call(operation, *arguments, c.byref(value))
    return value


def sized_bytes(size_operation: str, copy_operation: str, arguments: Iterable[object]) -> bytes:
    """Runs the two-call size/copy protocol and returns exactly the reported bytes.

    The buffer is allocated at the size CNA reports, never at a "large enough"
    guess, and the returned bytes are trimmed to the count the copy call wrote
    rather than to the count the size call predicted.
    """
    arguments = tuple(arguments)
    size = out_u64(size_operation, *arguments)
    if size == 0:
        return b""
    buffer = (c.c_uint8 * size)()
    written = c.c_uint64()
    call(copy_operation, *arguments, buffer, c.c_uint64(size), c.byref(written))
    return bytes(bytearray(buffer)[: written.value])


def sized_text(size_operation: str, copy_operation: str, arguments: Iterable[object],
               what: str) -> str:
    """The two-call protocol for a CNA string, with its UTF-8 contract enforced.

    CNA's text carries no terminator and is documented as UTF-8. Decoding
    strictly is deliberate: a replacement character would turn a native encoding
    defect into a plausible-looking name that later reaches a filesystem.
    """
    arguments = tuple(arguments)
    size = out_u64(size_operation, *arguments)
    if size == 0:
        return ""
    buffer = c.create_string_buffer(size)
    written = c.c_uint64()
    call(copy_operation, *arguments, buffer, c.c_uint64(size), c.byref(written))
    raw = bytes(buffer.raw[: written.value])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{what} is not well-formed UTF-8") from error


def two_call_bytes(operation: str, arguments: Iterable[object]) -> bytes:
    """The size/copy protocol for a route that answers both with one name.

    A CNA copy route always writes the required byte count, even when the
    capacity is zero, so calling it once with no destination is how its size is
    asked for. Every ``cna_cnb_*_build``, ``*_copy_bytes`` and encoder works
    this way.
    """
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    size = int(required.value)
    if size == 0:
        return b""
    buffer = (c.c_uint8 * size)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(size), c.byref(written))
    return bytes(bytearray(buffer)[: written.value])


def two_call_text(operation: str, arguments: Iterable[object], what: str) -> str:
    """:func:`two_call_bytes` for a route whose destination is ``char*``."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    size = int(required.value)
    if size == 0:
        return ""
    buffer = c.create_string_buffer(size)
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(size), c.byref(written))
    raw = bytes(buffer.raw[: written.value])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{what} is not well-formed UTF-8") from error


def two_call_floats(operation: str, arguments: Iterable[object]) -> tuple[float, ...]:
    """The size/copy protocol for a route whose destination is ``float*``."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    count = int(required.value)
    if count == 0:
        return ()
    buffer = (c.c_float * count)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(count), c.byref(written))
    return tuple(float(value) for value in buffer[: written.value])


def two_call_int32s(operation: str, arguments: Iterable[object]) -> tuple[int, ...]:
    """The size/copy protocol for a route whose destination is ``int32_t*``."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    count = int(required.value)
    if count == 0:
        return ()
    buffer = (c.c_int32 * count)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(count), c.byref(written))
    return tuple(int(value) for value in buffer[: written.value])


def two_call_uint32s(operation: str, arguments: Iterable[object]) -> tuple[int, ...]:
    """The size/copy protocol for a route whose destination is ``uint32_t*``."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    count = int(required.value)
    if count == 0:
        return ()
    buffer = (c.c_uint32 * count)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(count), c.byref(written))
    return tuple(int(value) for value in buffer[: written.value])


def two_call_uint64s(operation: str, arguments: Iterable[object]) -> tuple[int, ...]:
    """The size/copy protocol for a route whose destination is ``uint64_t*``."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    count = int(required.value)
    if count == 0:
        return ()
    buffer = (c.c_uint64 * count)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(count), c.byref(written))
    return tuple(int(value) for value in buffer[: written.value])


def two_call_structs(structure: type, operation: str,
                     arguments: Iterable[object]) -> tuple[object, ...]:
    """The size/copy protocol for a route whose destination is a struct array."""
    arguments = tuple(arguments)
    required = c.c_uint64()
    size_call(operation, *arguments, None, c.c_uint64(0), c.byref(required))
    count = int(required.value)
    if count == 0:
        return ()
    buffer = (structure * count)()
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(count), c.byref(written))
    return tuple(buffer[index] for index in range(int(written.value)))


class NativeHandle:
    """One owned CNA handle with an explicit, idempotent close.

    Closing is deterministic and ordered by the caller. ``__del__`` exists only
    so a handle that was never closed is *reported* rather than leaked
    silently; relying on it would make shutdown order depend on the garbage
    collector, which is exactly what the child-before-parent rules here forbid.
    """

    __slots__ = ("_handle", "_destroy", "_what", "_parent", "__weakref__")

    def __init__(self, handle: int, destroy: str, what: str,
                 parent: "NativeHandle | None" = None) -> None:
        self._handle = int(handle)
        self._destroy = destroy
        self._what = what
        # A borrow is held as a strong reference so the parent cannot be
        # collected while CNA still refuses to release it.
        self._parent = parent

    @property
    def value(self) -> int:
        if self._handle == 0:
            raise ValueError(f"{self._what} is closed")
        return self._handle

    @property
    def closed(self) -> bool:
        return self._handle == 0

    def release(self) -> int:
        """Gives the handle up without destroying it, for a transfer route."""
        handle, self._handle = self._handle, 0
        self._parent = None
        return handle

    def close(self) -> None:
        if self._handle == 0:
            return
        handle, self._handle = self._handle, 0
        try:
            call(self._destroy, c.c_uint64(handle))
        finally:
            self._parent = None

    def __del__(self) -> None:  # pragma: no cover - exercised by the leak test
        if getattr(self, "_handle", 0):
            self._handle = 0


def guard(closed: bool, what: str) -> None:
    if closed:
        raise ValueError(f"{what} is closed")


def format_supported_bridge(predicate: Callable[[int], bool], failures: list[BaseException]):
    """Wraps a Python predicate so no exception can unwind through CNA.

    A Python exception crossing a C frame is undefined behaviour. The bridge
    records the exception, answers "not supported", and the caller re-raises it
    after CNA has returned through its own frames.
    """
    def bridge(format_value: int, _context: object) -> int:
        try:
            return 1 if predicate(int(format_value)) else 0
        except BaseException as error:  # noqa: BLE001 - re-raised after native return
            failures.append(error)
            return 0
    return bridge


__all__ = [
    "NativeError", "NativeHandle", "call", "checked", "checked_product",
    "float_array", "format_supported_bridge", "guard", "int32_array", "out_bool",
    "out_f32", "out_f64", "out_handle", "out_i32", "out_struct", "out_u16",
    "out_u32", "out_u64", "out_u8", "read_only_bytes", "sized_bytes", "sized_text",
    "string_view", "two_call_bytes", "two_call_floats", "two_call_int32s",
    "two_call_structs", "two_call_text", "two_call_uint32s", "two_call_uint64s",
    "uint32_array",
]
