"""Post-processing: pooled targets, shader effects, passes and the chain.

A post-process pass reads one frame's colour -- and, where it needs them, that
frame's depth, normals and velocity -- and writes a destination. A chain runs
several in order, ping-ponging between pooled intermediates it owns. That is the
whole model, and everything else in this module exists to serve it.

Ownership, which CNA is unusually explicit about and which this module keeps
exactly
--------------------------------------------------------------------------

``RenderTargetPool.acquire``
    hands out an **owned view of a pool-owned target**. Disposing the view
    releases the view; the pooled storage stays. The pool refuses ``reset`` and
    ``close`` while any view is out, and that refusal is reported rather than
    worked around.
``ShaderEffectFactory.acquire``
    hands out an **owned view of a factory-owned effect**, as a strict
    ``Effect`` so the caller gets parameters and techniques. Disposing it
    releases the view. The factory refuses ``clear`` and ``close`` while any
    view is out.
``PostProcessChain.add``
    **borrows**: the caller keeps owning the pass, and the chain holds a strong
    reference so it cannot be collected while CNA could still apply it. CNA's
    ownership-transferring ``add_owned_pass`` is deliberately not used; see
    :class:`EffectPass` for the same reasoning.
``PostProcessChain.target_pool``
    is a **counted borrow**: the chain refuses ``close`` while it is out.
``EffectPass``
    borrows its effect, and keeps it alive for as long as the pass could draw.

None of this is inferred from a function's name. Each contract is the one
``engine_layer.h`` states, and the lifecycle tests exercise the refusals.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Microsoft.Xna.Framework import Matrix
from Microsoft.Xna.Framework.Graphics import DepthFormat, RenderTarget2D, SurfaceFormat

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import Effect, GraphicsDevice, Texture

__all__ = [
    "RenderTargetPool",
    "ShaderEffectFactory",
    "RenderTargetScope",
    "bind_render_target",
    "FullscreenPass",
    "PostProcessContext",
    "PostProcessPass",
    "BlitPass",
    "EffectPass",
    "PassTiming",
    "PostProcessChain",
    "POST_PROCESS_CONTEXT_VERSION",
]

#: The ``CNA_PostProcessContext`` version this binding fills, measured from the
#: canonical header. Version 2 is the one that carries the settings pointer;
#: version 1's smaller size is still accepted by CNA, which is what makes the
#: structure growable rather than frozen.
POST_PROCESS_CONTEXT_VERSION = _engine.CNA_POST_PROCESS_CONTEXT_VERSION_2

_NO_HANDLE = 0


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


def _optional_handle(value: object, what: str) -> int:
    """The native handle of an optional strict or engine resource, or none."""
    if value is None:
        return _NO_HANDLE
    if hasattr(value, "_require_handle"):
        return int(value._require_handle())
    handle = getattr(value, "_handle", None)
    if handle is not None and hasattr(handle, "value"):
        return int(handle.value)
    raise TypeError(f"{what} must be a graphics resource or None, "
                    f"not {type(value).__name__}")


def _matrix(value: "Matrix | None") -> _abi.CNA_Matrix:
    if value is None:
        return _abi.CNA_Matrix(*tuple(Matrix.Identity))
    if not isinstance(value, Matrix):
        raise TypeError("expected a Microsoft.Xna.Framework.Matrix")
    return _abi.CNA_Matrix(*tuple(value))


class _EngineObject:
    """Common lifetime for an owned engine handle.

    Public subclasses take the arguments a caller has and never a handle.
    """

    __slots__ = ("_handle",)

    def _attach(self, handle: "_support.NativeHandle") -> None:
        self._handle = handle

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run, or once ownership was handed away."""
        return self._handle.closed

    def close(self) -> None:
        """Releases the native object. Calling it twice is not an error."""
        self._handle.close()

    def __enter__(self):
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()


# --- pooled render targets ---------------------------------------------------


class RenderTargetPool(_EngineObject):
    """Reusable intermediate render targets, keyed by shape and slot.

    A post-process chain owns one of these and draws through it; a caller
    driving passes by hand can own one directly. Acquiring the same shape and
    slot twice hands back a view of the same pooled target rather than
    allocating a second one, which is the whole point of it.
    """

    __slots__ = ("_borrowed", "_device")

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_render_target_pool_create", _device_handle(device)),
            "cna_render_target_pool_destroy", "render-target pool"))
        self._borrowed = False
        self._device = device

    @classmethod
    def _borrow(cls, handle: int, device: "GraphicsDevice") -> "RenderTargetPool":
        """A counted borrow of a chain's own pool.

        Closing it does not close the chain's pool -- the chain owns that -- but
        the borrow itself must be released, because the chain refuses
        destruction while one is outstanding.
        """
        self = cls.__new__(cls)
        self._attach(_support.NativeHandle(
            handle, "cna_render_target_pool_destroy", "borrowed render-target pool"))
        self._borrowed = True
        self._device = device
        return self

    @property
    def is_borrowed(self) -> bool:
        """True for a pool handed out by a chain rather than created directly."""
        return self._borrowed

    @property
    def target_count(self) -> int:
        """How many distinct targets the pool currently owns."""
        return _support.out_u64("cna_render_target_pool_get_target_count",
                                self._handle.argument)

    @property
    def estimated_bytes(self) -> int:
        """CNA's estimate of the pool's colour storage, in bytes."""
        return _support.out_u64("cna_render_target_pool_get_estimated_bytes",
                                self._handle.argument)

    def acquire(self, width: int, height: int, *,
                surface_format: SurfaceFormat = SurfaceFormat.Color,
                depth_format: DepthFormat = DepthFormat.None_,
                slot: int = 0) -> RenderTarget2D:
        """A view of a pooled target of this shape, creating it on first use.

        What comes back is an ordinary ``RenderTarget2D``, so it binds, draws
        and reads back like any other. **Disposing it releases the view, not the
        pooled target**: the storage stays in the pool for the next caller with
        the same shape, and the pool refuses :meth:`reset` and :meth:`close`
        until every view has been disposed.

        ``slot`` distinguishes two targets that have the same shape and must not
        be the same texture -- a ping-pong pair, for instance.
        """
        handle = _support.out_handle(
            "cna_render_target_pool_acquire", self._handle.argument,
            c.c_int32(_support.checked(width, "int32", "width")),
            c.c_int32(_support.checked(height, "int32", "height")),
            c.c_uint32(_support.checked(int(surface_format), "uint32", "surface_format")),
            c.c_uint32(_support.checked(int(depth_format), "uint32", "depth_format")),
            c.c_int32(_support.checked(slot, "int32", "slot")))
        return RenderTarget2D._view_of(self._device, handle)

    def reset(self) -> None:
        """Releases every pooled target.

        Refused while a view acquired from this pool is still undisposed. That
        is CNA's rule, and it is reported rather than worked around by disposing
        the caller's views for them.
        """
        _support.call("cna_render_target_pool_reset", self._handle.argument)


# --- named shader effects ----------------------------------------------------


class ShaderEffectFactory(_EngineObject):
    """A named cache of effects compiled from vertex and fragment source.

    XNA's ``Effect`` is loaded from compiled bytecode for one shader model. CNA
    has several renderers, so it compiles source per renderer instead and caches
    the result under a caller-chosen name. Asking twice for the same name
    returns the same effect and does not compile again, which
    :attr:`compile_count` is how a caller can verify rather than assume.
    """

    __slots__ = ("_device",)

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_shader_effect_factory_create", _device_handle(device)),
            "cna_shader_effect_factory_destroy", "shader-effect factory"))
        self._device = device

    def acquire(self, name: str, vertex_source: str, fragment_source: str) -> "Effect":
        """The cached effect for ``name``, compiling the source on first request.

        The result is a strict ``Effect`` view: it carries the whole effect
        surface -- parameters, techniques, ``CurrentTechnique`` -- and disposing
        it releases the **view**, leaving the factory's effect cached. The
        factory refuses :meth:`clear` and :meth:`close` until every view it
        handed out has been disposed.

        On a repeat request the source arguments are not consulted at all: the
        name is the cache key, so two different shaders sharing one name are a
        caller error CNA cannot see.
        """
        from Microsoft.Xna.Framework.Graphics import Effect

        key, keep_key = _support.string_view(name, "name")
        vertex, keep_vertex = _support.string_view(vertex_source, "vertex_source")
        fragment, keep_fragment = _support.string_view(fragment_source, "fragment_source")
        handle = _support.out_handle("cna_shader_effect_factory_acquire",
                                     self._handle.argument, key, vertex, fragment)
        del keep_key, keep_vertex, keep_fragment
        effect = Effect.__new__(Effect)
        effect._initialize_native(self._device, handle)
        return effect

    def contains(self, name: str) -> bool:
        """Whether ``name`` is already in the cache."""
        key, keep = _support.string_view(name, "name")
        try:
            return _support.out_bool("cna_shader_effect_factory_contains",
                                     self._handle.argument, key)
        finally:
            del keep

    @property
    def compile_count(self) -> int:
        """How many distinct shaders the factory has compiled since construction.

        Clearing the cache does not reset it, which is what makes it usable as
        evidence that a second acquire did not recompile.
        """
        return _support.out_u64("cna_shader_effect_factory_get_compile_count",
                                self._handle.argument)

    def clear(self) -> None:
        """Releases every cached effect.

        Refused while a view handed out by :meth:`acquire` is still undisposed.
        """
        _support.call("cna_shader_effect_factory_clear", self._handle.argument)


# --- the render-target save/restore bracket ----------------------------------


class RenderTargetScope(_EngineObject):
    """The active bracket that restores a device's previous render target.

    Scopes on one device may nest and **must** be closed innermost first; an
    out-of-order close is refused by CNA and changes neither the scope stack nor
    the binding. Use :func:`bind_render_target`, which is the ``with`` form.
    """

    __slots__ = ()

    @property
    def has_recorded_previous(self) -> bool:
        """Whether the scope captured a previous binding to restore."""
        return _support.out_bool("cna_scoped_render_target_get_has_recorded_previous",
                                 self._handle.argument)

    def end(self) -> None:
        """Restores the previous binding and releases the scope."""
        self.close()


def bind_render_target(device: "GraphicsDevice",
                       destination: "RenderTarget2D | None") -> RenderTargetScope:
    """Binds ``destination`` until the scope closes, then restores what was bound.

    ``None`` means the back buffer. The context-manager form matches the native
    lifetime exactly -- ``begin`` on entry, ``end`` on exit -- rather than being
    sugar over something else::

        with bind_render_target(device, target):
            ...
    """
    scope = RenderTargetScope.__new__(RenderTargetScope)
    scope._attach(_support.NativeHandle(
        _support.out_handle(
            "cna_scoped_render_target_begin", _device_handle(device),
            c.c_uint64(_optional_handle(destination, "destination"))),
        "cna_scoped_render_target_end", "render-target scope"))
    return scope


# --- full-screen drawing -----------------------------------------------------


class FullscreenPass(_EngineObject):
    """Draws one texture over a whole target, optionally through an effect.

    The primitive every post-process pass is built on, exposed because a caller
    writing their own pass needs it too.
    """

    __slots__ = ()

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_fullscreen_pass_create", _device_handle(device)),
            "cna_fullscreen_pass_destroy", "full-screen pass"))

    def draw(self, source: "Texture | None", destination: "RenderTarget2D | None",
             width: int, height: int, *, effect: "Effect | None" = None,
             sampler: object = None) -> None:
        """Draws ``source`` over ``destination``; ``None`` means the back buffer.

        ``effect`` of ``None`` is a straight copy. Every handle is borrowed for
        the call and nothing is retained.
        """
        _support.call(
            "cna_fullscreen_pass_draw", self._handle.argument,
            c.c_uint64(_optional_handle(source, "source")),
            c.c_uint64(_optional_handle(destination, "destination")),
            c.c_uint64(_optional_handle(effect, "effect")),
            c.c_int32(_support.checked(width, "int32", "width")),
            c.c_int32(_support.checked(height, "int32", "height")),
            _sampler_pointer(sampler))

    def draw_over_current_target(self, source: "Texture | None", width: int, height: int,
                                 *, effect: "Effect | None" = None,
                                 sampler: object = None) -> None:
        """Draws ``source`` over whatever target the device already has bound."""
        _support.call(
            "cna_fullscreen_pass_draw_over_current_target", self._handle.argument,
            c.c_uint64(_optional_handle(source, "source")),
            c.c_uint64(_optional_handle(effect, "effect")),
            c.c_int32(_support.checked(width, "int32", "width")),
            c.c_int32(_support.checked(height, "int32", "height")),
            _sampler_pointer(sampler))


def _sampler_pointer(sampler: object):
    """A pointer to a native sampler state, or null for the pass's own default."""
    if sampler is None:
        return None
    if not hasattr(sampler, "_native_value"):
        raise TypeError("sampler must be a Microsoft.Xna.Framework.Graphics.SamplerState")
    return c.byref(sampler._native_value())


# --- the frame a pass runs over ----------------------------------------------


@dataclass(frozen=True)
class PostProcessContext:
    """One frame's inputs to a pass or a chain.

    An immutable value. The textures are borrowed for the call and nothing here
    keeps them alive, which is why the objects rather than handles are held: the
    caller's references are what they are.

    Only ``source``, ``width`` and ``height`` are needed by every pass; a pass
    that reads depth, normals or velocity says so in its own documentation, and
    a chain refuses a context with no source or a non-positive size because it
    has nowhere to read from and nothing to size its intermediates against.

    The camera matrices default to the identity, and ``has_previous_frame`` is
    what tells a reprojecting pass whether ``previous_view_projection``
    describes a real earlier frame or a placeholder.
    """

    source: object = None
    width: int = 0
    height: int = 0
    destination: object = None
    source_depth: object = None
    source_normals: object = None
    source_velocity: object = None
    elapsed_seconds: float = 0.0
    near_plane: float = 0.0
    far_plane: float = 0.0
    projection: Matrix | None = None
    inverse_projection: Matrix | None = None
    inverse_view: Matrix | None = None
    previous_view_projection: Matrix | None = None
    has_previous_frame: bool = False

    def _native(self) -> _engine.CNA_PostProcessContext:
        """Fills CNA's own defaults first, then only the fields this value sets.

        ``cna_post_process_context_init`` is called rather than zero-filling:
        the structure is growable, so a later revision's added field must get
        CNA's default rather than whatever a zeroed byte happens to mean.
        """
        value = _engine.CNA_PostProcessContext()
        _support.call("cna_post_process_context_init", c.byref(value))
        value.source = _optional_handle(self.source, "source")
        value.source_depth = _optional_handle(self.source_depth, "source_depth")
        value.source_normals = _optional_handle(self.source_normals, "source_normals")
        value.source_velocity = _optional_handle(self.source_velocity, "source_velocity")
        value.destination = _optional_handle(self.destination, "destination")
        value.width = _support.checked(self.width, "int32", "width")
        value.height = _support.checked(self.height, "int32", "height")
        value.elapsed_seconds = _support.real(self.elapsed_seconds, "elapsed_seconds")
        value.near_plane = _support.real(self.near_plane, "near_plane")
        value.far_plane = _support.real(self.far_plane, "far_plane")
        value.has_previous_frame = 1 if self.has_previous_frame else 0
        value.projection = _matrix(self.projection)
        value.inverse_projection = _matrix(self.inverse_projection)
        value.inverse_view = _matrix(self.inverse_view)
        value.previous_view_projection = _matrix(self.previous_view_projection)
        return value


# --- passes ------------------------------------------------------------------


class PostProcessPass(_EngineObject):
    """What every concrete pass can do.

    C cannot derive from CNA's abstract ``PostProcessPass``, so what crosses the
    ABI is the set of operations that contract declares. This class is those
    operations; the concrete constructors are its subclasses.
    """

    __slots__ = ("_effect",)

    @property
    def name(self) -> str:
        """The pass's own name, as CNA reports it in diagnostics."""
        return _support.copied_text("cna_post_process_pass_copy_name",
                                    (self._handle.argument,), "pass name")

    def is_supported(self, device: "GraphicsDevice") -> bool:
        """Whether the pass can do its real work on ``device``.

        A ``False`` does not mean calling is unsafe. This layer's contract is
        that an unsupported pass *degrades*, typically to a copy, rather than
        failing, so this answers which of the two a caller will get.
        """
        return _support.out_bool("cna_post_process_pass_is_supported",
                                 self._handle.argument, _device_handle(device))

    def apply(self, context: PostProcessContext) -> None:
        """Runs the pass over one frame's inputs."""
        if not isinstance(context, PostProcessContext):
            raise TypeError("context must be a PostProcessContext")
        native = context._native()
        _support.call("cna_post_process_pass_apply", self._handle.argument, c.byref(native))



class BlitPass(PostProcessPass):
    """Copies its source to its destination unchanged.

    The pass whose output can be predicted exactly, which is what makes it the
    one worth checking a chain's plumbing with.
    """

    __slots__ = ()

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_blit_pass_create", _device_handle(device)),
            "cna_post_process_pass_destroy", "blit pass"))
        self._effect = None


class EffectPass(PostProcessPass):
    """Draws its source through an effect.

    The effect is **borrowed**: CNA requires it to outlive the pass, and
    destroying the pass leaves it alive. The pass holds a strong reference to it
    for exactly that reason, so an effect nothing else names cannot be collected
    while the pass could still draw with it.

    CNA also offers an owning constructor, the C form of a ``unique_ptr``
    parameter. This binding deliberately does not use it: in Python the
    reference above already guarantees the lifetime the owning form exists to
    guarantee, and adopting it would *cost* capability -- CNA invalidates the
    handle, so the caller's ``Effect`` facade would have to be torn down and
    could no longer set a parameter. See ``docs/engine-extensions.md``.
    """

    __slots__ = ()

    def __init__(self, device: "GraphicsDevice", effect: "Effect | None",
                 name: str = "") -> None:
        view, keep = _support.string_view(name, "name")
        produced = _support.out_handle(
            "cna_post_process_effect_pass_create", _device_handle(device),
            c.c_uint64(_optional_handle(effect, "effect")), view)
        del keep
        self._effect = effect
        self._attach(_support.NativeHandle(
            produced, "cna_post_process_pass_destroy", "effect pass"))

    @property
    def effect(self) -> "Effect | None":
        """The effect this pass draws through, or ``None`` when it has none.

        CNA is asked, rather than the Python reference being trusted, because a
        pass whose effect was set to ``None`` really has none and only CNA knows
        that. The object handed back is the one the caller supplied; a second
        facade over the same effect would be two owners of one thing.

        **The view CNA answers with is released here, immediately.**
        ``engine_layer.h`` says the returned handle is borrowed from the pass
        and must not be destroyed. Measured on CNA 0.21.0 it is neither: each
        call produces a *distinct* handle, and until every one of them is passed
        to ``cna_effect_destroy`` the owning factory refuses to be destroyed and
        then the game refuses to be destroyed. Following the documentation
        exactly leaks one handle per read. See ENGINE-002 in
        ``docs/engine-upstream-findings.md``.
        """
        handle = _support.out_handle("cna_post_process_effect_pass_get_effect",
                                     self._handle.argument)
        if handle == _NO_HANDLE:
            return None
        _support.call("cna_effect_destroy", c.c_uint64(handle))
        return self._effect

    @effect.setter
    def effect(self, value: "Effect | None") -> None:
        """Replaces the effect, borrowing the new one.

        A pass that owns an effect keeps owning it: CNA's setter does not
        release the old one, and neither does this.
        """
        _support.call("cna_post_process_effect_pass_set_effect", self._handle.argument,
                      c.c_uint64(_optional_handle(value, "effect")))
        self._effect = value


# --- the chain ---------------------------------------------------------------


@dataclass(frozen=True)
class PassTiming:
    """How long one pass took on the GPU, averaged over the samples taken.

    ``sample_count`` of zero means the pass has not been timed -- GPU timing off,
    or a renderer with no timer query -- and is not a duration of zero.
    """

    name: str
    sample_count: int
    milliseconds: float


class PostProcessChain(_EngineObject):
    """Runs passes in order, ping-ponging between pooled intermediates.

    Order is the whole contract: two passes that do not commute produce
    different pixels depending on which is added first, and that is what the
    chain is for.
    """

    __slots__ = ("_passes", "_device")

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.NativeHandle(
            _support.out_handle("cna_post_process_chain_create", _device_handle(device)),
            "cna_post_process_chain_destroy", "post-process chain"))
        #: The passes in the chain. CNA borrows every one of them, so the chain
        #: keeps them alive for as long as it could still apply them.
        self._passes: list[PostProcessPass] = []
        self._device = device

    def add(self, pass_: PostProcessPass) -> None:
        """Appends a pass the caller keeps owning.

        The chain borrows it: it must outlive its membership, and the caller
        closes it afterwards. This object keeps a reference so an unreferenced
        pass cannot be collected out from under CNA.
        """
        if not isinstance(pass_, PostProcessPass):
            raise TypeError("pass_ must be a PostProcessPass")
        _support.call("cna_post_process_chain_add_pass", self._handle.argument,
                      pass_._handle.argument)
        self._passes.append(pass_)

    def clear(self) -> None:
        """Removes every pass. The caller still owns each of them."""
        _support.call("cna_post_process_chain_clear", self._handle.argument)
        self._passes.clear()

    @property
    def pass_count(self) -> int:
        """How many passes the chain holds."""
        return _support.out_i32("cna_post_process_chain_get_pass_count",
                                self._handle.argument)

    def apply(self, context: PostProcessContext) -> None:
        """Runs every pass in order over one frame."""
        if not isinstance(context, PostProcessContext):
            raise TypeError("context must be a PostProcessContext")
        native = context._native()
        _support.call("cna_post_process_chain_apply", self._handle.argument,
                      c.byref(native))

    def reset_targets(self) -> None:
        """Releases the chain's pooled intermediates."""
        _support.call("cna_post_process_chain_reset_targets", self._handle.argument)

    @property
    def target_pool(self) -> RenderTargetPool:
        """The chain's own pool, as a counted borrow.

        The chain refuses to close while the borrow is outstanding, so close the
        pool object first. Asking twice hands out two borrows, and both must be
        released.
        """
        return RenderTargetPool._borrow(
            _support.out_handle("cna_post_process_chain_get_target_pool",
                                self._handle.argument), self._device)

    @property
    def gpu_timing_enabled(self) -> bool:
        """Whether the chain is timing its passes on the GPU."""
        return _support.out_bool("cna_post_process_chain_is_gpu_timing_enabled",
                                 self._handle.argument)

    @gpu_timing_enabled.setter
    def gpu_timing_enabled(self, value: bool) -> None:
        """Asks for GPU timing. A renderer without timers accepts and stays off.

        **Reading the property back straight afterwards is not the answer.**
        ``engine_layer.h`` says to do exactly that, and on a renderer whose GPU
        timer works it still reports ``False`` until the chain has applied once.
        Read it after the first :meth:`apply` instead. See ENGINE-004 in
        ``docs/engine-upstream-findings.md``.
        """
        _support.call("cna_post_process_chain_set_gpu_timing_enabled",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    @property
    def pass_timings(self) -> tuple[PassTiming, ...]:
        """Every timing the chain recorded, in pass order.

        Empty when GPU timing is off or unavailable, which is not a failure. A
        timing with ``sample_count`` zero is a pass whose first query has not
        come back yet -- one frame's delay -- and not a pass that took no time.
        The name is read with a separate route because a C value structure
        cannot own a string.

        The first duration each pass records carries ENGINE-003's unsigned
        32-bit wrap, exactly as :attr:`GpuTimer.last_milliseconds` does.
        """
        count = _support.out_u64("cna_post_process_chain_get_pass_timing_count",
                                 self._handle.argument)
        timings = []
        for index in range(count):
            value = _support.out_struct(
                _engine.CNA_PassTimingEXT, 1, "cna_post_process_chain_get_pass_timing",
                self._handle.argument, c.c_uint64(index))
            name = _support.copied_text(
                "cna_post_process_chain_copy_pass_timing_name",
                (self._handle.argument, c.c_uint64(index)), "pass timing name")
            timings.append(PassTiming(name, int(value.sample_count),
                                      float(value.milliseconds)))
        return tuple(timings)

    def __len__(self) -> int:
        return self.pass_count
