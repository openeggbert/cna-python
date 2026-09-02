"""Private plumbing shared by every ``cna.extensions.engine`` slice.

The engine layer differs from every family before it in one way that shapes all
of this: **a CNA build may not contain it at all.** Every route is exported in
every build, and the ones that need a native engine object answer
``CNA_RESULT_NOT_SUPPORTED`` when the layer was configured out. That is a
different fact from "this renderer cannot do that", and collapsing the two would
tell a caller to change GPUs when the answer is to change builds. So the two are
separated here, once, by asking CNA which case applies.

Also here, for the same reason they are in the compiled-content family: the
two-call size/copy protocol, checked width conversion, and deterministic handle
lifetime with no reliance on ``__del__``.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c
from typing import Iterable, Sequence

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
    "int64": (-0x8000000000000000, 0x7FFFFFFFFFFFFFFF),
}

#: ``CNA_RESULT_BUFFER_TOO_SMALL``. A copy route that cannot fit its output
#: still writes the required byte count, which is how the size half of the
#: two-call protocol asks its question.
_BUFFER_TOO_SMALL = 14

#: ``CNA_RESULT_NOT_SUPPORTED``. The one result whose meaning depends on which
#: build is loaded, which is why it is named rather than folded into the table.
_NOT_SUPPORTED = 6

#: CNA result code -> the public exception class that names what it means.
_RESULT_CLASSES = {
    1: "EngineArgumentError",     # INVALID_ARGUMENT
    2: "EngineInternalError",     # INVALID_HANDLE -- this layer never passes one
    3: "EngineStateError",        # INVALID_STATE
    4: "EngineInternalError",     # OUT_OF_MEMORY
    5: "EngineInternalError",     # IO
    6: "EngineUnsupportedError",  # NOT_SUPPORTED -- refined below
    7: "EngineInternalError",     # PLATFORM
    8: "EngineThreadError",       # THREAD
    9: "EngineInternalError",     # CALLBACK
    10: "EngineArgumentError",    # OVERFLOW
    11: "EngineArgumentError",    # ENCODING
    12: "EngineInternalError",    # INTERNAL
    13: "EngineInternalError",    # SHUTTING_DOWN
}


def engine_layer_version() -> int:
    """The engine-layer revision the loaded library was built with; zero for none.

    This is the only route in the family that is meaningful in a build with no
    engine layer, and it is what separates "configured out" from "this renderer
    cannot".
    """
    library = get_library()
    value = c.c_int32()
    library.check(library.cna_engine_layer_get_version(c.byref(value)),
                  "cna_engine_layer_get_version")
    return int(value.value)


def engine_layer_is_present() -> bool:
    return engine_layer_version() != 0


#: Routes whose ``CNA_RESULT_INTERNAL`` is really "the source you gave me does
#: not compile".  CNA reports a shader compiler diagnostic in the internal
#: category; the code is preserved verbatim and the exception class is a
#: subclass of the internal one, so nothing is relabelled -- a caller simply
#: gains the ability to tell a compiler log apart from an allocation failure.
_COMPILE_ROUTES = {
    "cna_compute_shader_create",
}


def _translate(error: NativeError):
    """Maps one CNA failure onto the public engine exception for it.

    Imported at the point of failure rather than at module scope, so the private
    layer keeps not depending on the public one at import time.
    """
    from cna.extensions.engine import errors as public

    name = _RESULT_CLASSES.get(error.result, "EngineInternalError")
    if error.result == _NOT_SUPPORTED:
        # Asked, not assumed. A build with no engine layer answers the same
        # result code as a renderer that lacks a feature, and only one of those
        # is fixed by running somewhere else.
        try:
            present = engine_layer_is_present()
        except NativeError:  # pragma: no cover - the version route itself failed
            present = True
        if not present:
            name = "EngineUnavailableError"
    if error.result == 12 and error.operation in _COMPILE_ROUTES:
        name = "ComputeShaderCompileError"
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


def size_call(operation: str, *arguments: object) -> None:
    """Runs the sizing half of a two-call protocol whose count is not a byte count.

    ``CNA_RESULT_BUFFER_TOO_SMALL`` is the expected answer for a non-empty
    output and success for an empty one; anything else is a real failure. The
    text protocol in :func:`copied_text` handles its own sizing; this is for the
    routes that copy a range of *values* instead.
    """
    library = get_library()
    result = int(getattr(library, operation)(*arguments))
    if result in (0, _BUFFER_TOO_SMALL):
        return
    try:
        library.check(result, operation)
    except NativeError as error:
        raise _translate(error) from None


def call_result(operation: str, *arguments: object) -> int:
    """Invokes one route and returns its raw result without raising.

    Used only where a non-zero result is the answer rather than a failure, and
    the caller turns it into one. The code never reaches a public caller.
    """
    library = get_library()
    return int(getattr(library, operation)(*arguments))


def checked(value: object, width: str, what: str) -> int:
    """Range-checks a Python integer against the native width it is about to take."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an int, not {type(value).__name__}")
    low, high = _WIDTHS[width]
    if not low <= value <= high:
        raise ValueError(f"{what} must be in {low}..{high}, got {value}")
    return int(value)


def real(value: object, what: str) -> float:
    """Accepts a real number and refuses a bool, which is an int in Python."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{what} must be a real number, not {type(value).__name__}")
    return float(value)


def string_view(text: str | None, what: str) -> tuple[abi.CNA_StringView, bytes]:
    """Builds a borrowed ``CNA_StringView`` over ``text``'s UTF-8 bytes.

    The encoded ``bytes`` object is returned alongside and **must** be kept alive
    by the caller for as long as the view is passed to CNA.
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


def out_u8(operation: str, *arguments: object) -> int:
    value = c.c_uint8()
    call(operation, *arguments, c.byref(value))
    return int(value.value)


def out_bool(operation: str, *arguments: object) -> bool:
    return out_u8(operation, *arguments) != 0


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


def borrowed_view(operation: str, arguments: Iterable[object], expected: int,
                  release: str) -> bool:
    """Asks CNA for a handle and releases it when it is a fresh counted view.

    Measured across the whole engine layer: a route that answers with a handle
    almost always answers with a **new** one, which must be released or the
    object that owns it -- and then the game -- cannot be destroyed. A few
    answer with the handle they were given, which must *not* be released,
    because destroying it would take the caller's own object with it.

    Comparing against the handle this binding supplied decides which case
    applies without having to guess, and without a table that could go stale
    when CNA changes one route. Returns whether the route reported a handle at
    all, which is the only part of the answer a caller needs -- the object it
    refers to is the one they already hold.
    """
    handle = out_handle(operation, *tuple(arguments))
    if handle == 0:
        return False
    if handle != expected:
        call(release, c.c_uint64(handle))
    return True


def out_struct(structure: type, version: int, operation: str, *arguments: object):
    """Fills a versioned CNA output structure, setting the two header fields first."""
    value = structure()
    value.struct_size = c.sizeof(structure)
    value.struct_version = version
    call(operation, *arguments, c.byref(value))
    return value


def in_struct(structure: type, version: int):
    """A caller-owned input structure with its two header fields already set."""
    value = structure()
    value.struct_size = c.sizeof(structure)
    value.struct_version = version
    return value


def copied_text(operation: str, arguments: Iterable[object], what: str) -> str:
    """The two-call size/copy protocol for a route that answers both by one name.

    Every engine ``*_copy_*`` route writes the required byte count even when the
    capacity is zero, so calling it once with no destination is how its size is
    asked for. The text carries no terminator and is documented as UTF-8;
    decoding strictly keeps a native encoding defect from becoming a
    plausible-looking string.
    """
    arguments = tuple(arguments)
    size = c.c_uint64()
    library = get_library()
    result = int(getattr(library, operation)(*arguments, None, c.c_uint64(0), c.byref(size)))
    if result not in (0, _BUFFER_TOO_SMALL):
        try:
            library.check(result, operation)
        except NativeError as error:
            raise _translate(error) from None
    if size.value == 0:
        return ""
    buffer = c.create_string_buffer(size.value)
    written = c.c_uint64()
    call(operation, *arguments, buffer, c.c_uint64(size.value), c.byref(written))
    raw = bytes(buffer.raw[: written.value])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{what} is not well-formed UTF-8") from error


def float_array(values: Sequence[float], what: str) -> tuple[object, int]:
    """Copies a real-number sequence into a C array, or ``(None, 0)`` when empty."""
    try:
        count = len(values)
    except TypeError as error:
        raise TypeError(f"{what} must be a sequence of real numbers") from error
    if count == 0:
        return None, 0
    return (c.c_float * count)(*(real(value, what) for value in values)), count


class NativeHandle:
    """One owned CNA engine handle with a deterministic, explicit lifetime.

    ``close`` is the mechanism; ``__del__`` is not implemented at all, because
    interpreter shutdown may already have unloaded the library and a finalizer
    that calls into it would be a crash rather than a cleanup. Every public
    engine object is a context manager for the same reason.
    """

    __slots__ = ("_value", "_destroy", "_what", "_closed", "_parent", "_children")

    def __init__(self, value: int, destroy: str | None, what: str,
                 parent: "NativeHandle | None" = None) -> None:
        if value == 0:
            raise ValueError(f"{what}: CNA returned an invalid handle")
        self._value = int(value)
        self._destroy = destroy
        self._what = what
        self._closed = False
        self._parent = parent
        self._children: list["NativeHandle"] = []
        if parent is not None:
            parent._children.append(self)

    @property
    def closed(self) -> bool:
        return self._closed or (self._parent is not None and self._parent.closed)

    @property
    def value(self) -> int:
        if self._closed:
            raise _disposed(self._what)
        if self._parent is not None and self._parent.closed:
            raise _disposed(f"{self._what} (its owner is closed)")
        return self._value

    @property
    def argument(self) -> c.c_uint64:
        return c.c_uint64(self.value)

    def close(self) -> None:
        if self._closed:
            return
        # Children first: CNA refuses to destroy a parent whose views are live,
        # and that refusal is a contract to keep rather than a race to lose.
        for child in list(reversed(self._children)):
            child.close()
        self._children.clear()
        if self._destroy is not None:
            call(self._destroy, c.c_uint64(self._value))
        self._closed = True
        self._value = 0
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)


def _disposed(what: str):
    from cna.extensions.engine import errors as public

    return public.EngineDisposedError(
        "use after close", 0, None, f"{what} is closed")
