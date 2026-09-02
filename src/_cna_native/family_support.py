"""Plumbing every native family's private layer needs, in one place.

Four families now cross the ctypes boundary -- the engine layer, sensors and
device services, extended input, and the online runtime -- and each needs the
same six things: checked width conversion, a borrowed ``CNA_StringView``, the
two-call size/copy protocol, output-parameter helpers, deterministic handle
lifetime with no reliance on ``__del__``, and a rooted callback trampoline.

What differs between them is only *which exception a CNA result becomes*, so
that is the one thing a family supplies. :func:`support_for` binds a family's
translation into a namespace of the helpers above; everything else is shared, so
a fix to the size/copy protocol is a fix everywhere rather than in one of four
copies.

Nothing here is public, and no object defined here reaches a caller.
"""

from __future__ import annotations

import ctypes as c
from typing import Callable, Iterable, Sequence

from . import abi
from .errors import NativeError
from .loader import get_library

#: Inclusive bounds of every fixed-width parameter these families pass.
WIDTHS = {
    "uint8": (0, 0xFF),
    "uint16": (0, 0xFFFF),
    "uint32": (0, 0xFFFFFFFF),
    "uint64": (0, 0xFFFFFFFFFFFFFFFF),
    "int8": (-0x80, 0x7F),
    "int16": (-0x8000, 0x7FFF),
    "int32": (-0x80000000, 0x7FFFFFFF),
    "int64": (-0x8000000000000000, 0x7FFFFFFFFFFFFFFF),
}

#: ``CNA_RESULT_BUFFER_TOO_SMALL``. A copy route that cannot fit its output
#: still writes the required byte count, which is how the size half of the
#: two-call protocol asks its question.
BUFFER_TOO_SMALL = 14

#: ``CNA_RESULT_NOT_SUPPORTED``.
NOT_SUPPORTED = 6


def checked(value: object, width: str, what: str) -> int:
    """Range-checks a Python integer against the native width it is about to take."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an int, not {type(value).__name__}")
    low, high = WIDTHS[width]
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


def float_array(values: Sequence[float], what: str) -> tuple[object, int]:
    """Copies a real-number sequence into a C array, or ``(None, 0)`` when empty."""
    try:
        count = len(values)
    except TypeError as error:
        raise TypeError(f"{what} must be a sequence of real numbers") from error
    if count == 0:
        return None, 0
    return (c.c_float * count)(*(real(value, what) for value in values)), count


def in_struct(structure: type, version: int):
    """A caller-owned input structure with its two header fields already set."""
    value = structure()
    value.struct_size = c.sizeof(structure)
    value.struct_version = version
    return value


class Support:
    """Every helper that has to know how a family turns a CNA result into an error."""

    __slots__ = ("translate",)

    def __init__(self, translate: Callable[[NativeError], BaseException]) -> None:
        self.translate = translate

    # -- calling ------------------------------------------------------------

    def call(self, operation: str, *arguments: object) -> None:
        """Invokes one CNA route, raising the family's exception for any failure."""
        library = get_library()
        function = getattr(library, operation)
        try:
            library.check(function(*arguments), operation)
        except NativeError as error:
            raise self.translate(error) from None

    def size_call(self, operation: str, *arguments: object) -> None:
        """The sizing half of a two-call protocol whose count is not a byte count.

        ``CNA_RESULT_BUFFER_TOO_SMALL`` is the expected answer for a non-empty
        output and success for an empty one; anything else is a real failure.
        """
        library = get_library()
        result = int(getattr(library, operation)(*arguments))
        if result in (0, BUFFER_TOO_SMALL):
            return
        try:
            library.check(result, operation)
        except NativeError as error:
            raise self.translate(error) from None

    def call_result(self, operation: str, *arguments: object) -> int:
        """Invokes one route and returns its raw result without raising."""
        library = get_library()
        return int(getattr(library, operation)(*arguments))

    # -- output parameters --------------------------------------------------

    def out_u8(self, operation: str, *arguments: object) -> int:
        value = c.c_uint8()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_bool(self, operation: str, *arguments: object) -> bool:
        return self.out_u8(operation, *arguments) != 0

    def out_u16(self, operation: str, *arguments: object) -> int:
        value = c.c_uint16()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_u32(self, operation: str, *arguments: object) -> int:
        value = c.c_uint32()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_u64(self, operation: str, *arguments: object) -> int:
        value = c.c_uint64()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_i32(self, operation: str, *arguments: object) -> int:
        value = c.c_int32()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_i64(self, operation: str, *arguments: object) -> int:
        """A 64-bit output, returned as a Python int.

        Tick counts come back through here, and they are the reason this exists
        rather than a float conversion: a tick count larger than 2**53 does not
        survive a double, and every timestamp in this ABI is larger than that.
        """
        value = c.c_int64()
        self.call(operation, *arguments, c.byref(value))
        return int(value.value)

    def out_f32(self, operation: str, *arguments: object) -> float:
        value = c.c_float()
        self.call(operation, *arguments, c.byref(value))
        return float(value.value)

    def out_f64(self, operation: str, *arguments: object) -> float:
        value = c.c_double()
        self.call(operation, *arguments, c.byref(value))
        return float(value.value)

    def out_handle(self, operation: str, *arguments: object) -> int:
        handle = c.c_uint64()
        self.call(operation, *arguments, c.byref(handle))
        return int(handle.value)

    def out_struct(self, structure: type, version: int, operation: str,
                   *arguments: object):
        """Fills a versioned CNA output structure, setting its header fields first."""
        value = structure()
        value.struct_size = c.sizeof(structure)
        value.struct_version = version
        self.call(operation, *arguments, c.byref(value))
        return value

    # -- the two-call protocols ---------------------------------------------

    def copied_text(self, operation: str, arguments: Iterable[object],
                    what: str) -> str:
        """The two-call size/copy protocol for a route that answers both by one name.

        Every ``*_copy_*`` route writes the required byte count even when the
        capacity is zero, so calling it once with no destination is how its size
        is asked for. The text carries no terminator and is documented as UTF-8;
        decoding strictly keeps a native encoding defect from becoming a
        plausible-looking string.
        """
        arguments = tuple(arguments)
        size = c.c_uint64()
        library = get_library()
        result = int(getattr(library, operation)(
            *arguments, None, c.c_uint64(0), c.byref(size)))
        if result not in (0, BUFFER_TOO_SMALL):
            try:
                library.check(result, operation)
            except NativeError as error:
                raise self.translate(error) from None
        if size.value == 0:
            return ""
        buffer = c.create_string_buffer(size.value)
        written = c.c_uint64()
        self.call(operation, *arguments, buffer, c.c_uint64(size.value),
                  c.byref(written))
        raw = bytes(buffer.raw[: written.value])
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{what} is not well-formed UTF-8") from error

    def sized_text(self, size_operation: str, copy_operation: str,
                   arguments: Iterable[object], what: str) -> str:
        """The two-call protocol where CNA declares a *separate* size route.

        :func:`copied_text` asks the copy route twice, which every copy route
        supports. Where CNA also declares a size route, asking it is the
        protocol as documented -- and it is the only thing that keeps the two
        halves in step when a future CNA changes one of them.
        """
        arguments = tuple(arguments)
        size = c.c_uint64()
        self.call(size_operation, *arguments, c.byref(size))
        if size.value == 0:
            return ""
        buffer = c.create_string_buffer(size.value)
        written = c.c_uint64()
        self.call(copy_operation, *arguments, buffer, c.c_uint64(size.value),
                  c.byref(written))
        raw = bytes(buffer.raw[: written.value])
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{what} is not well-formed UTF-8") from error

    def copied_values(self, element: type, operation: str,
                      arguments: Iterable[object]):
        """The two-call protocol for a route that copies a range of values.

        Sized first because the length is CNA's and not the caller's: asking for
        a guessed number answers ``CNA_RESULT_BUFFER_TOO_SMALL`` rather than
        truncating, which is the right refusal and the reason it is asked at all.
        """
        arguments = tuple(arguments)
        count = c.c_uint64()
        self.size_call(operation, *arguments, None, c.c_uint64(0), c.byref(count))
        if count.value == 0:
            return (element * 0)(), 0
        destination = (element * count.value)()
        written = c.c_uint64()
        self.call(operation, *arguments, destination, c.c_uint64(count.value),
                  c.byref(written))
        return destination, int(written.value)


class HandleSupport(Support):
    """A family's support plus the exception its disposed handles raise."""

    __slots__ = ("disposed",)

    def __init__(self, translate: Callable[[NativeError], BaseException],
                 disposed: Callable[[str], BaseException]) -> None:
        super().__init__(translate)
        self.disposed = disposed

    def handle(self, value: int, destroy: str | None, what: str,
               parent: "NativeHandle | None" = None) -> "NativeHandle":
        return NativeHandle(self, value, destroy, what, parent)


class NativeHandle:
    """One owned CNA handle with a deterministic, explicit lifetime.

    ``close`` is the mechanism; ``__del__`` is not implemented at all, because
    interpreter shutdown may already have unloaded the library and a finalizer
    that called into it would be a crash rather than a cleanup. Every public
    object holding one is a context manager for the same reason.

    A handle may name a parent. Closing the parent closes its children first,
    because CNA refuses to destroy an object whose views are live, and that
    refusal is a contract to keep rather than a race to lose.
    """

    __slots__ = ("_support", "_value", "_destroy", "_what", "_closed",
                 "_parent", "_children")

    def __init__(self, support: HandleSupport, value: int, destroy: str | None,
                 what: str, parent: "NativeHandle | None" = None) -> None:
        if value == 0:
            raise ValueError(f"{what}: CNA returned an invalid handle")
        self._support = support
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
            raise self._support.disposed(self._what)
        if self._parent is not None and self._parent.closed:
            raise self._support.disposed(f"{self._what} (its owner is closed)")
        return self._value

    @property
    def argument(self) -> c.c_uint64:
        return c.c_uint64(self.value)

    def close(self) -> None:
        if self._closed:
            return
        for child in list(reversed(self._children)):
            child.close()
        self._children.clear()
        if self._destroy is not None:
            self._support.call(self._destroy, c.c_uint64(self._value))
        self._closed = True
        self._value = 0
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)


class CallbackRoot:
    """Keeps a callback trampoline alive for exactly as long as CNA can call it.

    ctypes builds a trampoline when a Python callable is converted to a
    ``CFUNCTYPE``, and drops it as soon as nothing references it. CNA holds the
    trampoline, not the Python object, so a bare conversion at the call site is
    a use-after-free waiting for the next dispatch. Everything registered here
    is held until it is explicitly released, and releasing is what
    unsubscription does.

    A Python exception must never unwind through C, so every trampoline built
    here swallows one and records it. :attr:`failures` is what a caller -- and a
    test -- reads to find out that a handler raised.
    """

    __slots__ = ("_entries", "failures")

    def __init__(self) -> None:
        self._entries: dict[object, tuple[object, object]] = {}
        #: ``(handler, exception)`` for every handler that raised, in order.
        self.failures: list[tuple[object, BaseException]] = []

    def root(self, key: object, factory: type, handler: Callable) -> object:
        """Builds and roots a trampoline for ``handler`` under ``key``."""

        def guarded(*arguments: object) -> None:
            try:
                handler(*arguments)
            except BaseException as error:  # noqa: BLE001 - must not unwind into C
                self.failures.append((handler, error))

        trampoline = factory(guarded)
        self._entries[key] = (trampoline, handler)
        return trampoline

    def release(self, key: object) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)
