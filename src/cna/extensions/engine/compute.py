"""GPU compute: storage buffers, compute programs, memory barriers and timers.

XNA 4.0 has no compute pipeline, no shader-storage buffer and no timer query, so
none of this has anywhere honest to go inside ``Microsoft.Xna.Framework``. It is
CNA engine-layer capability and it lives here.

**Everything here is a renderer capability, and none of it is assumed.** A
storage buffer needs a build with an engine layer; a compute program needs a
renderer that compiles GLSL ES 3.10 compute source; image binding is a further
capability that a renderer with compute may still lack; a timer query is a fourth.
Each is asked for separately -- :attr:`ComputeShader.is_valid`,
:attr:`ComputeShader.supports_image_binding`, :attr:`GpuTimer.is_supported` --
because on a real renderer they do not all answer the same way.

Ownership
---------

Every object here is ``OWNED`` and closed explicitly; each is a context manager
and none relies on ``__del__``. A buffer or texture bound into a
:class:`ComputeShader` is ``BORROWED`` by CNA and must outlive every dispatch
that reads it, so the shader holds a strong reference to whatever is bound to it
(``RETAINED_DEPENDENCY``) and refuses to dispatch once one of them is closed.
That refusal is this binding's, raised before CNA is reached.
"""

from __future__ import annotations

import ctypes as c
from enum import IntEnum, IntFlag
from typing import TYPE_CHECKING

from _cna_native import engine_abi as _abi
from _cna_native import engine_support as _support

from .errors import (
    ComputeShaderCompileError, EngineDisposedError, EngineUnsupportedError,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice, Texture

__all__ = [
    "MemoryBarrier",
    "ImageAccess",
    "StorageBuffer",
    "ComputeShader",
    "GpuTimer",
]


class MemoryBarrier(IntFlag):
    """Which memory accesses a compute barrier orders against later commands.

    A bit mask in CNA and a flag enum here, so ``|`` and ``in`` mean what they
    look like. The values are CNA's own, measured from the canonical header.
    """

    Nothing = _abi.CNA_GRAPHICS_MEMORY_BARRIER_NONE
    VertexAttribArray = _abi.CNA_GRAPHICS_MEMORY_BARRIER_VERTEX_ATTRIB_ARRAY
    ElementArray = _abi.CNA_GRAPHICS_MEMORY_BARRIER_ELEMENT_ARRAY
    Uniform = _abi.CNA_GRAPHICS_MEMORY_BARRIER_UNIFORM
    TextureFetch = _abi.CNA_GRAPHICS_MEMORY_BARRIER_TEXTURE_FETCH
    ShaderImageAccess = _abi.CNA_GRAPHICS_MEMORY_BARRIER_SHADER_IMAGE_ACCESS
    ShaderStorage = _abi.CNA_GRAPHICS_MEMORY_BARRIER_SHADER_STORAGE
    BufferUpdate = _abi.CNA_GRAPHICS_MEMORY_BARRIER_BUFFER_UPDATE
    Framebuffer = _abi.CNA_GRAPHICS_MEMORY_BARRIER_FRAMEBUFFER
    IndirectCommand = _abi.CNA_GRAPHICS_MEMORY_BARRIER_INDIRECT_COMMAND
    All = _abi.CNA_GRAPHICS_MEMORY_BARRIER_ALL


def barrier_contains(mask: MemoryBarrier, bits: MemoryBarrier) -> bool:
    """Reports whether ``mask`` contains every bit of ``bits``, as CNA decides it.

    Python's own ``bits in mask`` computes the same thing, and for a mask this
    binding built the two cannot disagree. It is CNA's answer that is asked for,
    because the containment rule is the engine layer's own and a mask can come
    back from CNA as easily as go into it.
    """
    return _support.out_bool(
        "cna_graphics_memory_barrier_has",
        c.c_uint32(_support.checked(int(mask), "uint32", "mask")),
        c.c_uint32(_support.checked(int(bits), "uint32", "bits")))


class ImageAccess(IntEnum):
    """How a compute shader may access a texture bound as an image."""

    ReadOnly = _abi.CNA_GRAPHICS_IMAGE_ACCESS_READ_ONLY
    WriteOnly = _abi.CNA_GRAPHICS_IMAGE_ACCESS_WRITE_ONLY
    ReadWrite = _abi.CNA_GRAPHICS_IMAGE_ACCESS_READ_WRITE


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    """Borrows the strict XNA device's native handle for the length of one call.

    The dependency runs extension -> strict. ``GraphicsDevice`` is unchanged and
    does not know this package exists.
    """
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


class _EngineObject:
    """Common lifetime for an owned engine handle.

    Public subclasses take the arguments a caller has -- a device, a size, some
    source -- and never a handle: a signature that named one would publish a
    private native type, and there is no owned handle a caller could supply.
    """

    __slots__ = ("_handle",)

    def _attach(self, handle: "_support.NativeHandle") -> None:
        self._handle = handle

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the native object. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self):
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


class StorageBuffer(_EngineObject):
    """A shader-storage buffer a compute dispatch reads and writes.

    Two shapes, because CNA has two and they behave differently: a plain buffer
    sized in bytes, and a typed one that remembers an element count and an
    element size so an upload of the wrong shape is refused rather than
    reinterpreted.
    """

    __slots__ = ()

    def __init__(self, device: "GraphicsDevice", byte_size: int) -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle(
                "cna_storage_buffer_create", _device_handle(device),
                c.c_uint64(_support.checked(byte_size, "uint64", "byte_size"))),
            "cna_storage_buffer_destroy", "storage buffer"))

    @classmethod
    def of_elements(cls, device: "GraphicsDevice", element_count: int,
                    element_byte_size: int) -> "StorageBuffer":
        """Creates a buffer of ``element_count`` fixed-size elements on ``device``.

        A typed buffer remembers both numbers, which is what lets CNA refuse an
        upload of the wrong shape rather than reinterpret the bytes.
        """
        self = cls.__new__(cls)
        self._attach(_support.NativeHandle(
            _support.out_handle(
                "cna_storage_buffer_create_typed", _device_handle(device),
                c.c_uint64(_support.checked(element_count, "uint64", "element_count")),
                c.c_uint64(_support.checked(element_byte_size, "uint64",
                                            "element_byte_size"))),
            "cna_storage_buffer_destroy", "storage buffer"))
        return self

    @property
    def byte_size(self) -> int:
        """The buffer's size in bytes."""
        return _support.out_u64("cna_storage_buffer_get_byte_size", self._handle.argument)

    @property
    def element_count(self) -> int:
        """How many elements the buffer holds; zero when it was sized in bytes."""
        return _support.out_u64("cna_storage_buffer_get_element_count",
                                self._handle.argument)

    @property
    def element_byte_size(self) -> int:
        """The element size the buffer was created with; zero when sized in bytes."""
        return _support.out_u64("cna_storage_buffer_get_element_byte_size",
                                self._handle.argument)

    def write(self, data: bytes) -> None:
        """Uploads ``data`` from offset zero. It must not exceed the buffer."""
        buffer, count = _bytes_argument(data, "data")
        _support.call("cna_storage_buffer_set_bytes", self._handle.argument,
                      buffer, c.c_uint64(count))

    def read(self, byte_size: int | None = None) -> bytes:
        """Reads ``byte_size`` bytes back, defaulting to the whole buffer."""
        size = self.byte_size if byte_size is None else _support.checked(
            byte_size, "uint64", "byte_size")
        if size == 0:
            return b""
        destination = (c.c_uint8 * size)()
        _support.call("cna_storage_buffer_get_bytes", self._handle.argument,
                      c.cast(destination, c.c_void_p), c.c_uint64(size))
        return bytes(destination)

    def write_elements(self, data: bytes, element_byte_size: int) -> None:
        """Uploads whole elements, refusing more than the buffer holds.

        ``element_byte_size`` must equal the size the buffer was created with;
        CNA treats a disagreement as an argument error rather than silently
        reinterpreting the bytes, and so does this.
        """
        size = _support.checked(element_byte_size, "uint64", "element_byte_size")
        if size == 0:
            raise ValueError("element_byte_size must not be zero")
        buffer, count = _bytes_argument(data, "data")
        if count % size:
            raise ValueError(
                f"data is {count} bytes, which is not a whole number of "
                f"{size}-byte elements")
        _support.call("cna_storage_buffer_set_elements", self._handle.argument,
                      buffer, c.c_uint64(count // size), c.c_uint64(size))

    def read_elements(self) -> bytes:
        """Reads the buffer's whole element range back as bytes."""
        count, size = self.element_count, self.element_byte_size
        total = count * size
        if total == 0:
            return b""
        destination = (c.c_uint8 * total)()
        _support.call("cna_storage_buffer_get_elements", self._handle.argument,
                      c.cast(destination, c.c_void_p), c.c_uint64(count),
                      c.c_uint64(size))
        return bytes(destination)


def _bytes_argument(data: object, what: str) -> tuple[object, int]:
    """Copies a bytes-like object into a C array CNA can read."""
    if isinstance(data, (bytes, bytearray)):
        view = memoryview(data)
    elif isinstance(data, memoryview):
        if not data.contiguous:
            raise ValueError(f"{what} must be a contiguous buffer")
        view = data.cast("B") if data.format != "B" else data
    else:
        try:
            view = memoryview(data).cast("B")
        except TypeError as error:
            raise TypeError(f"{what} must be a bytes-like object") from error
    count = len(view)
    if count == 0:
        return None, 0
    array = (c.c_uint8 * count).from_buffer_copy(view)
    return c.cast(array, c.c_void_p), count


class ComputeShader(_EngineObject):
    """A compute program compiled from GLSL ES 3.10 source.

    **Construction raises when the source does not compile**, with
    :class:`~cna.extensions.engine.errors.ComputeShaderCompileError` carrying
    the compiler's log. That is what the current CNA implementation does, not
    what ``engine_layer.h`` documents: the header says creation succeeds and the
    failure is read back through :attr:`is_valid` and :attr:`compile_error`.
    Measured on CNA 0.21.0, six different bad sources -- empty, a syntax error,
    no ``main``, no ``#version``, an undeclared identifier and a missing
    ``local_size`` -- all fail creation with ``CNA_RESULT_INTERNAL`` and hand
    back no handle. ``docs/engine-upstream-findings.md`` records it. This
    binding reports what happens rather than papering over the difference, and
    the documented path is still handled: a shader CNA does return but calls
    invalid is closed and reported, so neither contract silently produces a
    shader that cannot run.
    """

    __slots__ = ("_bound",)

    def __init__(self, device: "GraphicsDevice", source: str) -> None:
        view, keep = _support.string_view(source, "source")
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_compute_shader_create",
                                _device_handle(device), view),
            "cna_compute_shader_destroy", "compute shader"))
        del keep
        #: Everything CNA borrows from this shader, kept alive for as long as it
        #: could still be dispatched.
        self._bound: dict[tuple[str, int], object] = {}
        if not self.is_valid:
            # The path engine_layer.h documents and this artifact does not take.
            # A shader that cannot run must not be handed out as if it could.
            diagnostic = self.compile_error
            self.close()
            raise ComputeShaderCompileError(
                "cna_compute_shader_create", 0, None,
                "CNA created a compute shader that did not compile: "
                + (diagnostic or "no diagnostic"))

    @property
    def is_valid(self) -> bool:
        """Whether the source compiled."""
        return _support.out_bool("cna_compute_shader_is_valid", self._handle.argument)

    @property
    def compile_error(self) -> str:
        """CNA's compile diagnostic, or the empty string when it compiled."""
        return _support.copied_text("cna_compute_shader_copy_compile_error",
                                    (self._handle.argument,), "compile error")

    @property
    def supports_image_binding(self) -> bool:
        """Whether this renderer can bind a texture as a read/write image.

        A separate capability from compute itself: a renderer that compiles and
        dispatches compute may still answer ``False`` here.
        """
        return _support.out_bool("cna_compute_shader_is_image_binding_supported",
                                 self._handle.argument)

    def _retain(self, kind: str, slot: int, value: object) -> None:
        self._bound[(kind, slot)] = value

    def _require_live_bindings(self, operation: str) -> None:
        for (kind, slot), value in self._bound.items():
            if getattr(value, "is_closed", False) or getattr(value, "IsDisposed", False):
                raise EngineDisposedError(
                    operation, 0, None,
                    f"the {kind} bound at {slot} is closed, and CNA borrows it for the dispatch")

    def set_uniform(self, name: str, value: int | float) -> None:
        """Sets a scalar uniform, choosing the integer or float route by type.

        ``bool`` is refused rather than silently becoming ``0`` or ``1``: GLSL's
        ``bool`` is a distinct type and CNA has no route for it, so accepting
        one would claim a mapping that does not exist.
        """
        view, keep = _support.string_view(name, "name")
        handle = self._handle.argument
        if isinstance(value, bool):
            raise TypeError("value must be an int or a float, not a bool")
        if isinstance(value, int):
            _support.call("cna_compute_shader_set_uniform_int", handle, view,
                          c.c_int32(_support.checked(value, "int32", "value")))
        else:
            _support.call("cna_compute_shader_set_uniform_float", handle, view,
                          c.c_float(_support.real(value, "value")))
        del keep

    def bind_storage_buffer(self, binding: int, buffer: StorageBuffer) -> None:
        """Binds a storage buffer to a numbered binding point.

        CNA borrows the buffer; this object keeps it alive and refuses to
        dispatch after it is closed.
        """
        if not isinstance(buffer, StorageBuffer):
            raise TypeError("buffer must be a StorageBuffer")
        index = _support.checked(binding, "int32", "binding")
        _support.call("cna_compute_shader_bind_storage_buffer", self._handle.argument,
                      c.c_int32(index), buffer._handle.argument)
        self._retain("storage buffer", index, buffer)

    def bind_texture(self, unit: int, sampler_name: str, texture: "Texture") -> None:
        """Binds a texture to a numbered sampler unit."""
        view, keep = _support.string_view(sampler_name, "sampler_name")
        index = _support.checked(unit, "int32", "unit")
        _support.call("cna_compute_shader_bind_texture", self._handle.argument,
                      c.c_int32(index), view, _texture_handle(texture))
        del keep
        self._retain("texture", index, texture)

    def bind_image(self, unit: int, texture: "Texture",
                   access: ImageAccess = ImageAccess.ReadWrite) -> None:
        """Binds a texture as a read/write image.

        Asks :attr:`supports_image_binding` first and raises
        :class:`~cna.extensions.engine.errors.EngineUnsupportedError` naming the
        renderer boundary, rather than letting CNA refuse a call the caller had
        no way to know was unavailable.
        """
        index = _support.checked(unit, "int32", "unit")
        handle = self._handle.argument
        if not self.supports_image_binding:
            raise EngineUnsupportedError(
                "cna_compute_shader_bind_image", 6, None,
                "this renderer has no shader image binding; "
                "bind the texture as a sampler, or write through a storage buffer")
        _support.call("cna_compute_shader_bind_image", handle, c.c_int32(index),
                      _texture_handle(texture),
                      c.c_uint32(int(ImageAccess(access))))
        self._retain("image", index, texture)

    def dispatch(self, groups_x: int, groups_y: int = 1, groups_z: int = 1) -> None:
        """Dispatches the shader over a work-group grid."""
        handle = self._handle.argument
        self._require_live_bindings("cna_compute_shader_dispatch")
        _support.call("cna_compute_shader_dispatch", handle,
                      c.c_int32(_support.checked(groups_x, "int32", "groups_x")),
                      c.c_int32(_support.checked(groups_y, "int32", "groups_y")),
                      c.c_int32(_support.checked(groups_z, "int32", "groups_z")))

    def barrier(self, bits: MemoryBarrier = MemoryBarrier.All) -> None:
        """Orders the given memory accesses against later commands."""
        _support.call("cna_compute_shader_barrier", self._handle.argument,
                      c.c_uint32(_support.checked(int(bits), "uint32", "bits")))

    def close(self) -> None:
        super().close()
        # Nothing native borrows them any more, so the shader stops keeping
        # its dependencies alive when it stops being able to dispatch.
        self._bound.clear()


def _texture_handle(texture: object) -> c.c_uint64:
    if not hasattr(texture, "_require_handle"):
        raise TypeError("texture must be a Microsoft.Xna.Framework.Graphics texture")
    return c.c_uint64(texture._require_handle())


class GpuTimer(_EngineObject):
    """A non-blocking GPU-side elapsed-time query.

    **Construction succeeds where the renderer has no timer query**, exactly as
    CNA specifies, so :attr:`is_supported` and :attr:`unsupported_reason` are how
    a caller finds out.

    A result is not available when :meth:`end` returns: the query is
    asynchronous, so :meth:`poll` is called until it collects one. Nothing here
    blocks, and nothing here fabricates a duration.
    """

    __slots__ = ()

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_gpu_timer_create", _device_handle(device)),
            "cna_gpu_timer_destroy", "GPU timer"))

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can answer a timer query at all."""
        return _support.out_bool("cna_gpu_timer_is_supported", self._handle.argument)

    @property
    def unsupported_reason(self) -> str:
        """CNA's reason, or the empty string when the timer is supported."""
        return _support.copied_text("cna_gpu_timer_copy_unsupported_reason",
                                    (self._handle.argument,), "unsupported reason")

    @property
    def is_open(self) -> bool:
        """Whether a measurement has begun and not yet ended."""
        return _support.out_bool("cna_gpu_timer_is_open", self._handle.argument)

    @property
    def is_result_available(self) -> bool:
        """Whether the GPU has finished the outstanding query."""
        return _support.out_bool("cna_gpu_timer_is_result_available",
                                 self._handle.argument)

    @property
    def sample_count(self) -> int:
        """How many measurements this timer has collected."""
        return _support.out_i32("cna_gpu_timer_get_sample_count", self._handle.argument)

    @property
    def last_milliseconds(self) -> float:
        """The most recently collected duration, in milliseconds.

        **The first sample a timer collects is not a duration.** On CNA 0.21.0
        it is exactly ``4294.967295`` -- ``(2**32 - 1)`` nanoseconds, an
        unsigned underflow -- and every sample after it is plausible. The value
        is returned unchanged: dropping it here would hide the defect and would
        disagree with :attr:`sample_count`, which counts it. See ENGINE-003 in
        ``docs/engine-upstream-findings.md``, and take the first measurement as
        a warm-up.
        """
        return _support.out_f64("cna_gpu_timer_get_last_milliseconds",
                                self._handle.argument)

    def begin(self) -> None:
        """Opens a measurement."""
        _support.call("cna_gpu_timer_begin", self._handle.argument)

    def end(self) -> None:
        """Closes a measurement. The result is not available yet."""
        _support.call("cna_gpu_timer_end", self._handle.argument)

    def poll(self) -> bool:
        """Collects a finished result if one is ready; ``True`` when it did."""
        return _support.out_bool("cna_gpu_timer_poll", self._handle.argument)

    def measure(self) -> "_Measurement":
        """A context manager that brackets one measurement.

        ``with timer.measure():`` is exactly ``begin()`` then ``end()``, which is
        the native lifetime rather than sugar over it. The result still arrives
        later, through :meth:`poll`.
        """
        return _Measurement(self)


class _Measurement:
    """The ``begin``/``end`` bracket of one GPU timer measurement."""

    __slots__ = ("_timer",)

    def __init__(self, timer: GpuTimer) -> None:
        self._timer = timer

    def __enter__(self) -> GpuTimer:
        self._timer.begin()
        return self._timer

    def __exit__(self, *_exception: object) -> None:
        self._timer.end()
