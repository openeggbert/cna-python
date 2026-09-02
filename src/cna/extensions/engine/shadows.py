"""Shadow maps: directional, cascaded, spot and cube, and the effect state to read one.

**Casting and sampling are two different questions.** A map's ``is_supported``
answers whether its caster shader exists and links, which is the honest answer
because a renderer can advertise custom effects and still fail to compile this
one. Whether anything can *read* the result is
:func:`supports_shadow_sampling`, and a frame needs both: a map that rasters on
a renderer that cannot sample it produces a shadow texture nothing reads, which
looks exactly like a scene with no occluders. Both are exposed, separately, and
neither is inferred from the other.

Pure math, without a device
---------------------------

The matrix helpers -- :func:`compute_light_view`,
:func:`compute_light_projection`, :meth:`CascadedShadowMap.split_distances`,
:meth:`CascadedShadowMap.frustum_corners`, and the rest -- are pure functions of
their arguments. They need no map and no rasterizing renderer, only a build with
an engine layer, so a caller can lay out a shadow frustum before deciding
whether to render one.

Ownership
---------

Every getter on a shadow map hands out a **counted borrow with a fresh handle**:
asking twice gives two handles, and the map refuses destruction until all of
them are released. Measured, not assumed -- see ENGINE-002 in
``docs/engine-upstream-findings.md``, where one such handle is documented as
"do not destroy it" and in fact must be. So this module hands each view out
**once**, caches it, and disposes it when the map closes. A caller reading
:attr:`ShadowMap.shadow_texture` a thousand times leaks nothing and gets the
same object every time.
"""

from __future__ import annotations

import ctypes as c
from typing import TYPE_CHECKING, Sequence

from Microsoft.Xna.Framework import Matrix, Vector3
from Microsoft.Xna.Framework.Graphics import CubeMapFace, RenderTarget2D

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import (
    CUBE_SHADOW_FACE_COUNT, DirectionalLight, PointLight, PunctualLight,
    ShadowCascadeState, ShadowQuality, SpotLight, _matrix, _native_matrix,
    _native_vector, _vector,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework import BoundingBox
    from Microsoft.Xna.Framework.Graphics import Effect, GraphicsDevice

__all__ = [
    "supports_shadow_sampling",
    "shadow_map_size_for",
    "shadow_filter_radius_for",
    "cube_shadow_map_size_for",
    "compute_light_view",
    "compute_light_projection",
    "ShadowMap",
    "CascadedShadowMap",
    "SpotShadowMap",
    "CubeShadowMap",
    "ShadowReceiver",
]


def _device_handle(device: "GraphicsDevice") -> c.c_uint64:
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(device._require_handle())


def _bounds(value: "BoundingBox") -> _engine.CNA_BoundingBox:
    if not hasattr(value, "Min") or not hasattr(value, "Max"):
        raise TypeError("scene_bounds must be a Microsoft.Xna.Framework.BoundingBox")
    native = _engine.CNA_BoundingBox()
    native.min = _native_vector(value.Min)
    native.max = _native_vector(value.Max)
    return native


def supports_shadow_sampling(device: "GraphicsDevice") -> bool:
    """Whether the renderer can sample a shadow map in a shader.

    Ask this **as well as** a map's own ``is_supported``, never instead of it:
    one says whether the shadow can be drawn, the other whether anything can
    read it.
    """
    return _support.out_bool("cna_graphics_device_supports_shadow_sampling_ext",
                             _device_handle(device))


def shadow_map_size_for(quality: ShadowQuality) -> int:
    """The texture size in texels a quality preset selects, from CNA."""
    return _support.out_i32("cna_shadow_map_size_for_quality",
                            c.c_uint32(int(ShadowQuality(quality))))


def shadow_filter_radius_for(quality: ShadowQuality) -> int:
    """The percentage-closer filter radius in texels a quality preset selects."""
    return _support.out_i32("cna_shadow_map_filter_radius_for_quality",
                            c.c_uint32(int(ShadowQuality(quality))))


def cube_shadow_map_size_for(quality: ShadowQuality) -> int:
    """The cube face size a quality preset selects.

    A separate route from :func:`shadow_map_size_for` because six faces cost six
    times one, and CNA does not have to choose the same number for both.
    """
    return _support.out_i32("cna_cube_shadow_map_size_for_quality",
                            c.c_uint32(int(ShadowQuality(quality))))


def compute_light_view(light: DirectionalLight, scene_bounds: "BoundingBox") -> Matrix:
    """A directional light's view transform for a scene, without a map.

    Pure: no handle, no device, no rasterizer.
    """
    native = light._native()
    box = _bounds(scene_bounds)
    value = _abi.CNA_Matrix()
    _support.call("cna_shadow_map_compute_light_view", c.byref(native), c.byref(box),
                  c.byref(value))
    return _matrix(value)


def compute_light_projection(light_view: Matrix, scene_bounds: "BoundingBox") -> Matrix:
    """The orthographic projection that fits a scene in a light's view. Pure."""
    view = _native_matrix(light_view)
    box = _bounds(scene_bounds)
    value = _abi.CNA_Matrix()
    _support.call("cna_shadow_map_compute_light_projection", c.byref(view), c.byref(box),
                  c.byref(value))
    return _matrix(value)


class _CastScope:
    """The ``begin``/``end`` bracket of one shadow pass."""

    __slots__ = ("_map", "_arguments")

    def __init__(self, shadow_map: "_ShadowMapBase", arguments: tuple) -> None:
        self._map = shadow_map
        self._arguments = arguments

    def __enter__(self):
        self._map._begin(*self._arguments)
        return self._map

    def __exit__(self, *_exception: object) -> None:
        self._map._end()


class _ShadowMapBase:
    """Shared lifetime, views and pass bracket for every shadow map kind."""

    __slots__ = ("_handle", "_device", "_views")

    #: Every route the shared operations use, spelled out in full by each kind.
    #: Building these names with an f-string would work and would be shorter, and
    #: it would also make the reachability gate unable to see that the route is
    #: called at all -- a route reached only through a name nobody wrote is
    #: exactly what that gate exists to catch. So they are written.
    _ROUTES: dict[str, str] = {}

    def _attach(self, handle: int, device: "GraphicsDevice") -> None:
        self._handle = _support.NativeHandle(
            handle, self._ROUTES["destroy"], type(self).__name__)
        self._device = device
        #: Counted views handed out once and disposed with the map.
        self._views: dict[str, object] = {}

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Disposes every view this map handed out, then releases the map.

        In that order, and not the other way round: CNA refuses to destroy a map
        while one of its counted borrows is outstanding, and a caller should not
        have to know which properties they happened to read.
        """
        if self._handle.closed:
            return
        for view in reversed(list(self._views.values())):
            dispose = getattr(view, "Dispose", None)
            if dispose is not None and not getattr(view, "IsDisposed", False):
                dispose()
        self._views.clear()
        self._handle.close()

    def __enter__(self):
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    # --- shared queries ----------------------------------------------------

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can compile and link the caster shader.

        Not whether the result can be sampled -- that is
        :func:`supports_shadow_sampling`, and a frame needs both.
        """
        return _support.out_bool(self._ROUTES["is_supported"], self._handle.argument)

    @property
    def quality(self) -> ShadowQuality:
        """The preset the map was created with."""
        return ShadowQuality(_support.out_u32(self._ROUTES["get_quality"],
                                              self._handle.argument))

    @property
    def depth_bias(self) -> float:
        """The bias applied when comparing against the stored depth."""
        return _support.out_f32(self._ROUTES["get_depth_bias"], self._handle.argument)

    @depth_bias.setter
    def depth_bias(self, value: float) -> None:
        _support.call(self._ROUTES["set_depth_bias"], self._handle.argument,
                      c.c_float(_support.real(value, "depth_bias")))

    def _view(self, key: str, route: str, factory) -> object:
        """One counted borrow, taken once and kept for the map's lifetime."""
        existing = self._views.get(key)
        if existing is not None and not getattr(existing, "IsDisposed", False):
            return existing
        handle = _support.out_handle(route, self._handle.argument)
        if handle == 0:
            return None
        view = factory(handle)
        self._views[key] = view
        return view

    @property
    def shadow_texture(self) -> "RenderTarget2D | None":
        """The depth the map rendered, as a render target that reads back.

        A counted borrow of the map's own target: disposing it releases the
        view, not the storage, and the map disposes it for you on
        :meth:`close`. ``None`` on a renderer that cannot cast at all.
        """
        return self._view("shadow_texture", self._ROUTES["get_shadow_texture"],
                          lambda handle: RenderTarget2D._view_of(self._device, handle))

    @property
    def caster_effect(self) -> "Effect | None":
        """The effect the map draws occluders with, as a borrowed view.

        Set its ``World`` and draw geometry between :meth:`cast` entry and exit
        to put an occluder in the map. ``None`` when the caster shader did not
        link.
        """
        return self._view("caster_effect", self._ROUTES["get_caster_effect"],
                          self._make_effect)

    def _make_effect(self, handle: int):
        from Microsoft.Xna.Framework.Graphics import Effect

        effect = Effect.__new__(Effect)
        effect._initialize_native(self._device, handle)
        return effect

    def _begin(self, *arguments) -> None:
        raise NotImplementedError

    def _end(self) -> None:
        _support.call(self._ROUTES["end"], self._handle.argument)


class ShadowMap(_ShadowMapBase):
    """A single-frustum shadow map for one directional light.

    Rendering one is a bracket::

        with shadow_map.cast(sun, scene_bounds):
            shadow_map.apply_caster()
            device.DrawUserPrimitives(...)

    Entering binds the map's target and clears it to white -- "nothing here, and
    it is infinitely far away" -- so an unwritten texel is not an occluder at
    zero distance.
    """

    __slots__ = ()
    _ROUTES = {
        "destroy": "cna_shadow_map_destroy",
        "is_supported": "cna_shadow_map_is_supported",
        "get_quality": "cna_shadow_map_get_quality",
        "get_depth_bias": "cna_shadow_map_get_depth_bias",
        "set_depth_bias": "cna_shadow_map_set_depth_bias",
        "get_shadow_texture": "cna_shadow_map_get_shadow_texture",
        "get_caster_effect": "cna_shadow_map_get_caster_effect",
        "end": "cna_shadow_map_end",
    }

    def __init__(self, device: "GraphicsDevice",
                 quality: ShadowQuality = ShadowQuality.Medium) -> None:
        self._attach(_support.out_handle(
            "cna_shadow_map_create", _device_handle(device),
            c.c_uint32(int(ShadowQuality(quality)))), device)

    @property
    def size(self) -> int:
        """The map's edge length in texels."""
        return _support.out_i32("cna_shadow_map_get_size", self._handle.argument)

    @property
    def filter_radius(self) -> int:
        """The filter radius in texels the map's quality selects."""
        return _support.out_i32("cna_shadow_map_get_filter_radius", self._handle.argument)

    @property
    def light_view_projection(self) -> Matrix:
        """The world-to-shadow transform the last :meth:`cast` computed."""
        value = _abi.CNA_Matrix()
        _support.call("cna_shadow_map_get_light_view_projection",
                      self._handle.argument, c.byref(value))
        return _matrix(value)

    @property
    def skinned_caster_effect(self) -> "Effect | None":
        """The caster effect for skinned geometry, as a borrowed view."""
        return self._view("skinned_caster_effect",
                          "cna_shadow_map_get_skinned_caster_effect", self._make_effect)

    def cast(self, light: DirectionalLight, scene_bounds: "BoundingBox") -> _CastScope:
        """The bracket that renders occluders into the map."""
        return _CastScope(self, (light, scene_bounds))

    def _begin(self, light: DirectionalLight, scene_bounds: "BoundingBox") -> None:
        native = light._native()
        box = _bounds(scene_bounds)
        _support.call("cna_shadow_map_begin", self._handle.argument, c.byref(native),
                      c.byref(box))

    def apply_caster(self) -> None:
        """Applies the caster effect for rigid geometry. Only inside :meth:`cast`."""
        _support.call("cna_shadow_map_apply_caster", self._handle.argument)

    def apply_skinned_caster(self, bone_transforms: Sequence[Matrix],
                             weights_per_vertex: int) -> None:
        """Applies the caster effect for skinned geometry. Only inside :meth:`cast`."""
        count = len(bone_transforms)
        array = (_abi.CNA_Matrix * count)(*(_native_matrix(value)
                                            for value in bone_transforms)) if count else None
        _support.call("cna_shadow_map_apply_skinned_caster", self._handle.argument,
                      array, c.c_uint64(count),
                      c.c_int32(_support.checked(weights_per_vertex, "int32",
                                                 "weights_per_vertex")))


class CascadedShadowMap(_ShadowMapBase):
    """Several shadow frusta covering successive depth ranges of one camera.

    The near cascade covers a small volume at high resolution and the far one a
    large volume at low resolution, which is what makes a directional shadow
    usable across a whole view. :meth:`update` recomputes the splits for a
    camera; each cascade is then rendered with its own bracket.
    """

    __slots__ = ()
    _ROUTES = {
        "destroy": "cna_cascaded_shadow_map_destroy",
        "is_supported": "cna_cascaded_shadow_map_is_supported",
        "get_quality": "cna_cascaded_shadow_map_get_quality",
        "get_depth_bias": "cna_cascaded_shadow_map_get_depth_bias",
        "set_depth_bias": "cna_cascaded_shadow_map_set_depth_bias",
        "get_shadow_texture": "cna_cascaded_shadow_map_get_shadow_texture",
        "get_caster_effect": "cna_cascaded_shadow_map_get_caster_effect",
        "end": "cna_cascaded_shadow_map_end",
    }

    def __init__(self, device: "GraphicsDevice",
                 quality: ShadowQuality = ShadowQuality.Medium,
                 cascade_count: int = 3) -> None:
        self._attach(_support.out_handle(
            "cna_cascaded_shadow_map_create", _device_handle(device),
            c.c_uint32(int(ShadowQuality(quality))),
            c.c_int32(_support.checked(cascade_count, "int32", "cascade_count"))), device)

    @property
    def cascade_count(self) -> int:
        """How many cascades the map holds."""
        return _support.out_i32("cna_cascaded_shadow_map_get_cascade_count",
                                self._handle.argument)

    @property
    def cascade_size(self) -> int:
        """The edge length in texels of one cascade."""
        return _support.out_i32("cna_cascaded_shadow_map_get_cascade_size",
                                self._handle.argument)

    @property
    def blend_band(self) -> float:
        """The world-space width over which neighbouring cascades cross-fade."""
        return _support.out_f32("cna_cascaded_shadow_map_get_blend_band",
                                self._handle.argument)

    @blend_band.setter
    def blend_band(self, value: float) -> None:
        _support.call("cna_cascaded_shadow_map_set_blend_band", self._handle.argument,
                      c.c_float(_support.real(value, "blend_band")))

    @property
    def split_lambda(self) -> float:
        """How far the splits lean logarithmic (1) rather than uniform (0)."""
        return _support.out_f32("cna_cascaded_shadow_map_get_split_lambda",
                                self._handle.argument)

    @split_lambda.setter
    def split_lambda(self, value: float) -> None:
        _support.call("cna_cascaded_shadow_map_set_split_lambda", self._handle.argument,
                      c.c_float(_support.real(value, "split_lambda")))

    @property
    def debug_tint_enabled(self) -> bool:
        """Whether each cascade is tinted differently, for diagnosing splits."""
        return _support.out_bool("cna_cascaded_shadow_map_is_debug_tint_enabled",
                                 self._handle.argument)

    @debug_tint_enabled.setter
    def debug_tint_enabled(self, value: bool) -> None:
        _support.call("cna_cascaded_shadow_map_set_debug_tint_enabled",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    def update(self, light: DirectionalLight, camera_view: Matrix,
               camera_projection: Matrix) -> None:
        """Recomputes every cascade's split and transform for one camera."""
        native = light._native()
        view, projection = _native_matrix(camera_view), _native_matrix(camera_projection)
        _support.call("cna_cascaded_shadow_map_update", self._handle.argument,
                      c.byref(native), c.byref(view), c.byref(projection))

    def cascade_matrix(self, index: int) -> Matrix:
        """One cascade's world-to-shadow transform."""
        value = _abi.CNA_Matrix()
        _support.call("cna_cascaded_shadow_map_get_cascade_matrix", self._handle.argument,
                      c.c_int32(_support.checked(index, "int32", "index")), c.byref(value))
        return _matrix(value)

    def split_distance(self, index: int) -> float:
        """The view-space distance at which one cascade ends."""
        return _support.out_f32("cna_cascaded_shadow_map_get_split_distance",
                                self._handle.argument,
                                c.c_int32(_support.checked(index, "int32", "index")))

    def select_cascade(self, view_depth: float) -> int:
        """Which cascade covers a view-space depth."""
        return _support.out_i32("cna_cascaded_shadow_map_select_cascade",
                                self._handle.argument,
                                c.c_float(_support.real(view_depth, "view_depth")))

    def apply_to(self, receiver: "ShadowReceiver | Effect") -> None:
        """Moves the whole cascade state onto a receiving effect in one call.

        The atlas, every cascade transform, the splits and the blend band cross
        together, so a caller cannot set half of them and get a shadow that is
        subtly in the wrong place. That is the reason the receiver contract is
        bound at all; setting the pieces individually through
        :class:`ShadowReceiver` is for the cases this does not cover.
        """
        effect = getattr(receiver, "effect", receiver)
        if not hasattr(effect, "_require_handle"):
            raise TypeError("receiver must be a ShadowReceiver or an Effect")
        _support.call("cna_cascaded_shadow_map_apply_to_receiver", self._handle.argument,
                      c.c_uint64(effect._require_handle()))

    def cast(self, cascade_index: int) -> _CastScope:
        """The bracket that renders occluders into one cascade."""
        return _CastScope(self, (cascade_index,))

    def _begin(self, cascade_index: int) -> None:
        _support.call("cna_cascaded_shadow_map_begin", self._handle.argument,
                      c.c_int32(_support.checked(cascade_index, "int32", "cascade_index")))

    # --- pure math ---------------------------------------------------------

    @staticmethod
    def split_distances(near_plane: float, far_plane: float, cascade_count: int,
                        split_lambda: float) -> tuple[float, ...]:
        """Where the cascades end, blending a logarithmic and a uniform split.

        Pure. ``split_lambda`` is clamped to ``0..1`` by CNA, and the last
        distance is the far plane by definition.
        """
        capacity = _support.checked(cascade_count, "int32", "cascade_count")
        destination = (c.c_float * max(capacity, 1))()
        written = c.c_uint64()
        _support.call("cna_cascaded_shadow_map_compute_split_distances",
                      c.c_float(_support.real(near_plane, "near_plane")),
                      c.c_float(_support.real(far_plane, "far_plane")),
                      c.c_int32(capacity),
                      c.c_float(_support.real(split_lambda, "split_lambda")),
                      destination, c.c_uint64(max(capacity, 1)), c.byref(written))
        return tuple(float(destination[index]) for index in range(int(written.value)))

    @staticmethod
    def frustum_corners(view: Matrix, projection: Matrix) -> tuple[Vector3, ...]:
        """The eight world-space corners of a camera frustum. Pure.

        CNA takes depth as ``0..1``, the Direct3D convention XNA's projection
        matrices produce, so the near corners land on the near plane rather than
        half way to the camera.
        """
        native_view, native_projection = _native_matrix(view), _native_matrix(projection)
        corners = (_abi.CNA_Vector3 * 8)()
        _support.call("cna_cascaded_shadow_map_compute_frustum_corners",
                      c.byref(native_view), c.byref(native_projection), corners)
        return tuple(_vector(corners[index]) for index in range(8))

    @staticmethod
    def bounding_sphere(corners: Sequence[Vector3]) -> tuple[Vector3, float]:
        """The centre and radius of a sphere around eight corners. Pure."""
        if len(corners) != 8:
            raise ValueError(f"corners must hold 8 points, got {len(corners)}")
        native = (_abi.CNA_Vector3 * 8)(*(_native_vector(value) for value in corners))
        centre, radius = _abi.CNA_Vector3(), c.c_float()
        _support.call("cna_cascaded_shadow_map_compute_bounding_sphere", native,
                      c.byref(centre), c.byref(radius))
        return _vector(centre), float(radius.value)

    @staticmethod
    def snap_to_texel_grid(centre: Vector3, radius: float, cascade_size: int) -> Vector3:
        """Quantizes a cascade centre to its own texel grid. Pure.

        Without this a cascade's texels move as the camera does and every edge
        crawls. Only X and Y are snapped: depth is not sampled on a texel grid,
        so quantizing it would add a camera-dependent bias for nothing.
        """
        native = _native_vector(centre)
        value = _abi.CNA_Vector3()
        _support.call("cna_cascaded_shadow_map_snap_to_texel_grid", c.byref(native),
                      c.c_float(_support.real(radius, "radius")),
                      c.c_int32(_support.checked(cascade_size, "int32", "cascade_size")),
                      c.byref(value))
        return _vector(value)


class SpotShadowMap(_ShadowMapBase):
    """A single perspective shadow frustum for one spot light."""

    __slots__ = ()
    _ROUTES = {
        "destroy": "cna_spot_shadow_map_destroy",
        "is_supported": "cna_spot_shadow_map_is_supported",
        "get_quality": "cna_spot_shadow_map_get_quality",
        "get_depth_bias": "cna_spot_shadow_map_get_depth_bias",
        "set_depth_bias": "cna_spot_shadow_map_set_depth_bias",
        "get_shadow_texture": "cna_spot_shadow_map_get_shadow_texture",
        "get_caster_effect": "cna_spot_shadow_map_get_caster_effect",
        "end": "cna_spot_shadow_map_end",
    }

    def __init__(self, device: "GraphicsDevice",
                 quality: ShadowQuality = ShadowQuality.Medium) -> None:
        self._attach(_support.out_handle(
            "cna_spot_shadow_map_create", _device_handle(device),
            c.c_uint32(int(ShadowQuality(quality)))), device)

    @property
    def size(self) -> int:
        """The map's edge length in texels."""
        return _support.out_i32("cna_spot_shadow_map_get_size", self._handle.argument)

    @property
    def light_view_projection(self) -> Matrix:
        """The world-to-shadow transform the last :meth:`cast` computed."""
        value = _abi.CNA_Matrix()
        _support.call("cna_spot_shadow_map_get_light_view_projection",
                      self._handle.argument, c.byref(value))
        return _matrix(value)

    @property
    def light_position(self) -> Vector3:
        """Where the light was when the map was last rendered."""
        value = _abi.CNA_Vector3()
        _support.call("cna_spot_shadow_map_get_light_position", self._handle.argument,
                      c.byref(value))
        return _vector(value)

    @property
    def light_range(self) -> float:
        """The light's range when the map was last rendered."""
        return _support.out_f32("cna_spot_shadow_map_get_light_range",
                                self._handle.argument)

    def cast(self, light: SpotLight) -> _CastScope:
        """The bracket that renders occluders into the map."""
        return _CastScope(self, (light,))

    def _begin(self, light: SpotLight) -> None:
        native = light._native()
        _support.call("cna_spot_shadow_map_begin", self._handle.argument, c.byref(native))

    @staticmethod
    def compute_light_view(light: SpotLight) -> Matrix:
        """The spot light's view transform. Pure."""
        native = light._native()
        value = _abi.CNA_Matrix()
        _support.call("cna_spot_shadow_map_compute_light_view", c.byref(native),
                      c.byref(value))
        return _matrix(value)

    @staticmethod
    def compute_light_projection(light: SpotLight) -> Matrix:
        """The perspective projection matching the light's cone. Pure."""
        native = light._native()
        value = _abi.CNA_Matrix()
        _support.call("cna_spot_shadow_map_compute_light_projection", c.byref(native),
                      c.byref(value))
        return _matrix(value)


class CubeShadowMap(_ShadowMapBase):
    """Six shadow frusta covering every direction from one point light."""

    __slots__ = ()
    _ROUTES = {
        "destroy": "cna_cube_shadow_map_destroy",
        "is_supported": "cna_cube_shadow_map_is_supported",
        "get_quality": "cna_cube_shadow_map_get_quality",
        "get_depth_bias": "cna_cube_shadow_map_get_depth_bias",
        "set_depth_bias": "cna_cube_shadow_map_set_depth_bias",
        "get_shadow_texture": "cna_cube_shadow_map_get_shadow_texture",
        "get_caster_effect": "cna_cube_shadow_map_get_caster_effect",
        "end": "cna_cube_shadow_map_end",
    }

    def __init__(self, device: "GraphicsDevice",
                 quality: ShadowQuality = ShadowQuality.Medium) -> None:
        self._attach(_support.out_handle(
            "cna_cube_shadow_map_create", _device_handle(device),
            c.c_uint32(int(ShadowQuality(quality)))), device)

    @property
    def size(self) -> int:
        """One face's edge length in texels."""
        return _support.out_i32("cna_cube_shadow_map_get_size", self._handle.argument)

    @property
    def light_position(self) -> Vector3:
        """Where the light was at the last :meth:`update`."""
        value = _abi.CNA_Vector3()
        _support.call("cna_cube_shadow_map_get_light_position", self._handle.argument,
                      c.byref(value))
        return _vector(value)

    @property
    def light_range(self) -> float:
        """The light's range at the last :meth:`update`."""
        return _support.out_f32("cna_cube_shadow_map_get_light_range",
                                self._handle.argument)

    def update(self, light: PointLight) -> None:
        """Records the light every face is rendered from. Call before casting."""
        native = light._native()
        _support.call("cna_cube_shadow_map_update", self._handle.argument, c.byref(native))

    def cast(self, face: CubeMapFace) -> _CastScope:
        """The bracket that renders occluders into one of the six faces."""
        return _CastScope(self, (face,))

    def _begin(self, face: CubeMapFace) -> None:
        _support.call("cna_cube_shadow_map_begin", self._handle.argument,
                      c.c_int32(int(CubeMapFace(face))))

    @property
    def shadow_texture(self):
        """The cube the map rendered, as a borrowed ``TextureCube`` view.

        Genuinely a cube and not a render target: measured on CNA 0.21.0 the
        handle answers ``cna_texturecube_get_info`` and is released with
        ``cna_texturecube_destroy``, while the other three maps hand out render
        targets. The map disposes the view on :meth:`close` like every other
        counted borrow.
        """
        from Microsoft.Xna.Framework.Graphics import TextureCube

        return self._view("shadow_texture", "cna_cube_shadow_map_get_shadow_texture",
                          lambda handle: TextureCube._from_handle(self._device, handle))

    @staticmethod
    def compute_face_view(face: CubeMapFace, position: Vector3) -> Matrix:
        """One cube face's view transform from a light position. Pure."""
        native = _native_vector(position)
        value = _abi.CNA_Matrix()
        _support.call("cna_cube_shadow_map_compute_face_view",
                      c.c_uint32(int(CubeMapFace(face))), c.byref(native), c.byref(value))
        return _matrix(value)

    @staticmethod
    def compute_face_projection(light_range: float) -> Matrix:
        """The 90-degree projection every cube face shares. Pure."""
        value = _abi.CNA_Matrix()
        _support.call("cna_cube_shadow_map_compute_face_projection",
                      c.c_float(_support.real(light_range, "light_range")), c.byref(value))
        return _matrix(value)


class ShadowReceiver:
    """The engine state a stock effect carries so it can sample a shadow.

    ``IShadowReceiverEXT`` is an interface a CNA effect implements, not an
    object anyone holds, and C cannot implement an interface. What crosses the
    ABI is the set of operations it declares, and this is those operations,
    bound to one effect.

    It is deliberately not a set of methods on ``Effect``: adding them there
    would put CNA-only state on a strict XNA type, which is the one thing this
    package does not do. Wrap the effect instead::

        receiver = ShadowReceiver(effect)
        receiver.shadow_map = shadow.shadow_texture
        receiver.light_view_projection = shadow.light_view_projection
        receiver.enabled = True

    Every value is written straight through to the effect; nothing is cached
    here, so two receivers over one effect cannot disagree.
    """

    __slots__ = ("_effect", "_shadow_texture")

    def __init__(self, effect: "Effect") -> None:
        if not hasattr(effect, "_require_handle"):
            raise TypeError("effect must be a Microsoft.Xna.Framework.Graphics.Effect")
        self._effect = effect
        #: The texture object last assigned, kept alive because CNA borrows it.
        self._shadow_texture: object = None

    @property
    def _handle(self) -> c.c_uint64:
        return c.c_uint64(self._effect._require_handle())

    @property
    def effect(self) -> "Effect":
        """The effect this receiver writes to."""
        return self._effect

    @property
    def shadow_map(self):
        """The shadow texture the effect samples, or ``None``.

        The object handed back is the one that was assigned; a second facade
        over a borrowed texture would be a second owner of one thing.

        **The handle CNA answers with is released here.** Measured on CNA
        0.21.0: every call produces a *new* handle, whichever kind of texture
        was assigned, and one that is never released stops the game being
        destroyed. ``cna_render_target_destroy`` releases it in both cases.
        This is the same pattern as ENGINE-002 in
        ``docs/engine-upstream-findings.md``.
        """
        handle = _support.out_handle("cna_effect_get_shadow_map_ext", self._handle)
        if not handle:
            return None
        _support.call("cna_render_target_destroy", c.c_uint64(handle))
        return self._shadow_texture

    @shadow_map.setter
    def shadow_map(self, value) -> None:
        handle = 0 if value is None else int(value._require_handle())
        _support.call("cna_effect_set_shadow_map_ext", self._handle, c.c_uint64(handle))
        self._shadow_texture = value

    @property
    def light_view_projection(self) -> Matrix:
        """The world-to-shadow transform the effect samples with."""
        value = _abi.CNA_Matrix()
        _support.call("cna_effect_get_light_view_projection_ext", self._handle,
                      c.byref(value))
        return _matrix(value)

    @light_view_projection.setter
    def light_view_projection(self, value: Matrix) -> None:
        native = _native_matrix(value)
        _support.call("cna_effect_set_light_view_projection_ext", self._handle,
                      c.byref(native))

    @property
    def enabled(self) -> bool:
        """Whether the effect samples its shadow map at all."""
        return _support.out_bool("cna_effect_is_shadows_enabled_ext", self._handle)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        _support.call("cna_effect_set_shadows_enabled_ext", self._handle,
                      c.c_uint8(1 if value else 0))

    @property
    def depth_bias(self) -> float:
        """The bias the effect compares depths with."""
        return _support.out_f32("cna_effect_get_shadow_depth_bias_ext", self._handle)

    @depth_bias.setter
    def depth_bias(self, value: float) -> None:
        _support.call("cna_effect_set_shadow_depth_bias_ext", self._handle,
                      c.c_float(_support.real(value, "depth_bias")))

    @property
    def filter_radius(self) -> int:
        """The percentage-closer filter radius the effect uses, in texels."""
        return _support.out_i32("cna_effect_get_shadow_filter_radius_ext", self._handle)

    @filter_radius.setter
    def filter_radius(self, value: int) -> None:
        _support.call("cna_effect_set_shadow_filter_radius_ext", self._handle,
                      c.c_int32(_support.checked(value, "int32", "filter_radius")))

    @property
    def cascades(self) -> ShadowCascadeState:
        """The cascade splits and transforms the effect samples with."""
        value = _support.out_struct(_engine.CNA_ShadowCascadeStateEXT, 1,
                                    "cna_effect_get_shadow_cascades_ext", self._handle)
        return ShadowCascadeState._from_native(value)

    @cascades.setter
    def cascades(self, value: ShadowCascadeState) -> None:
        if not isinstance(value, ShadowCascadeState):
            raise TypeError("cascades must be a ShadowCascadeState")
        native = value._native()
        _support.call("cna_effect_set_shadow_cascades_ext", self._handle, c.byref(native))

    @property
    def punctual_light(self) -> PunctualLight:
        """The single punctual light the effect shades with."""
        value = _support.out_struct(_engine.CNA_PunctualLightEXT, 1,
                                    "cna_effect_get_punctual_light_ext", self._handle)
        return PunctualLight._from_native(value, shadow_map=self._shadow_texture)

    @punctual_light.setter
    def punctual_light(self, value: PunctualLight) -> None:
        if not isinstance(value, PunctualLight):
            raise TypeError("punctual_light must be a PunctualLight")
        native = value._native()
        _support.call("cna_effect_set_punctual_light_ext", self._handle, c.byref(native))
