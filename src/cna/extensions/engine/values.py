"""The engine layer's own value types: lights, qualities and cascade state.

These are pure values. CNA says so explicitly -- filling one with its canonical
defaults needs no engine-layer object -- so everything in this module works on a
build with no engine layer, and the tests exercise both artifacts.

**No default is written down here.** Each type has a :meth:`default` classmethod
that reads CNA's own canonical values through the matching ``_init`` route, and
the dataclass fields have no Python defaults at all. Transcribing "the default
direction is straight down, the default colour is white" into this file would
create a second source of truth that drifts silently the day CNA changes its
mind. Build from ``default()`` and adjust with :func:`dataclasses.replace`::

    from dataclasses import replace
    sun = replace(DirectionalLight.default(), direction=Vector3(0.3, -1, 0.2))

XNA has no light *value* type at all -- its ``BasicEffect`` carries three fixed
directional lights as effect state -- so these have nowhere to go in
``Microsoft.Xna.Framework``. They use strict ``Vector3`` and ``Matrix``, because
those are the same vectors and matrices.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum

from Microsoft.Xna.Framework import Matrix, Vector3

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

__all__ = [
    "ShadowQuality",
    "RenderQuality",
    "PunctualLightKind",
    "DirectionalLight",
    "PointLight",
    "SpotLight",
    "PunctualLight",
    "ClusteredLightKind",
    "ClusteredLight",
    "AreaLightShape",
    "AreaLight",
    "ShadowCascadeState",
    "SHADOW_CASCADE_MAXIMUM",
    "CUBE_SHADOW_FACE_COUNT",
    "FRUSTUM_CORNER_COUNT",
]

#: How many cascades a cascaded shadow map can have, from the canonical header.
SHADOW_CASCADE_MAXIMUM = _engine.CNA_SHADOW_CASCADE_MAX_EXT
#: The six faces of a cube shadow map.
CUBE_SHADOW_FACE_COUNT = _engine.CNA_CUBE_SHADOW_FACE_COUNT_EXT
#: The eight corners a view frustum has.
FRUSTUM_CORNER_COUNT = _engine.CNA_FRUSTUM_CORNER_COUNT_EXT


class ShadowQuality(IntEnum):
    """A shadow map's size and filter, as one preset.

    ``Disabled`` still produces a real map at the smallest size, so a game
    changing quality at run time does not have to destroy and rebuild the
    object. The exact size and filter radius each preset selects are CNA's and
    are read with :func:`~cna.extensions.engine.shadows.shadow_map_size_for` and
    :func:`~cna.extensions.engine.shadows.shadow_filter_radius_for` rather than
    being written down here.
    """

    Disabled = _engine.CNA_SHADOW_QUALITY_DISABLED
    Low = _engine.CNA_SHADOW_QUALITY_LOW
    Medium = _engine.CNA_SHADOW_QUALITY_MEDIUM
    High = _engine.CNA_SHADOW_QUALITY_HIGH
    Ultra = _engine.CNA_SHADOW_QUALITY_ULTRA


class RenderQuality(IntEnum):
    """The engine's overall quality preset, as the render pipeline reads it."""

    Low = _engine.CNA_RENDER_QUALITY_LOW
    Medium = _engine.CNA_RENDER_QUALITY_MEDIUM
    High = _engine.CNA_RENDER_QUALITY_HIGH
    Ultra = _engine.CNA_RENDER_QUALITY_ULTRA


class PunctualLightKind(IntEnum):
    """Which kind of light a punctual light slot holds; ``Nothing`` is unused."""

    Nothing = _engine.CNA_PUNCTUAL_LIGHT_KIND_EXT_NONE
    Point = _engine.CNA_PUNCTUAL_LIGHT_KIND_EXT_POINT
    Spot = _engine.CNA_PUNCTUAL_LIGHT_KIND_EXT_SPOT


def _vector(value: _abi.CNA_Vector3) -> Vector3:
    return Vector3(float(value.x), float(value.y), float(value.z))


def _native_vector(value: Vector3) -> _abi.CNA_Vector3:
    if not isinstance(value, Vector3):
        raise TypeError("expected a Microsoft.Xna.Framework.Vector3")
    return _abi.CNA_Vector3(float(value.X), float(value.Y), float(value.Z))


def _matrix(value: _abi.CNA_Matrix) -> Matrix:
    return Matrix(*(getattr(value, f"m{row}{column}")
                    for row in range(1, 5) for column in range(1, 5)))


def _native_matrix(value: Matrix) -> _abi.CNA_Matrix:
    if not isinstance(value, Matrix):
        raise TypeError("expected a Microsoft.Xna.Framework.Matrix")
    return _abi.CNA_Matrix(*tuple(value))


def _defaults(structure: type, route: str):
    value = structure()
    _support.call(route, c.byref(value))
    return value


@dataclass(frozen=True)
class DirectionalLight:
    """Colour and intensity arriving from one direction, everywhere.

    ``direction`` is the direction the light *travels*, not the direction toward
    the light.
    """

    direction: Vector3
    color: Vector3
    intensity: float
    casts_shadows: bool

    @classmethod
    def default(cls) -> "DirectionalLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_DirectionalLightEXT, "cna_directional_light_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "DirectionalLight":
        return cls(_vector(value.direction), _vector(value.color),
                   float(value.intensity), bool(value.casts_shadows))

    def _native(self):
        value = _support.in_struct(_engine.CNA_DirectionalLightEXT, 1)
        value.direction = _native_vector(self.direction)
        value.color = _native_vector(self.color)
        value.intensity = _support.real(self.intensity, "intensity")
        value.casts_shadows = 1 if self.casts_shadows else 0
        return value


@dataclass(frozen=True)
class PointLight:
    """A light radiating from a position, out to ``range_``.

    ``range_`` carries the trailing underscore because ``range`` is a Python
    builtin; the field is CNA's ``range``.
    """

    position: Vector3
    color: Vector3
    intensity: float
    range_: float
    casts_shadows: bool

    @classmethod
    def default(cls) -> "PointLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_PointLightEXT, "cna_point_light_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "PointLight":
        return cls(_vector(value.position), _vector(value.color),
                   float(value.intensity), float(value.range),
                   bool(value.casts_shadows))

    def _native(self):
        value = _support.in_struct(_engine.CNA_PointLightEXT, 1)
        value.position = _native_vector(self.position)
        value.color = _native_vector(self.color)
        value.intensity = _support.real(self.intensity, "intensity")
        value.range = _support.real(self.range_, "range_")
        value.casts_shadows = 1 if self.casts_shadows else 0
        return value


@dataclass(frozen=True)
class SpotLight:
    """A cone of light: full strength inside ``inner_angle``, gone by ``outer_angle``.

    Both angles are half-angles in radians.
    """

    position: Vector3
    direction: Vector3
    color: Vector3
    intensity: float
    range_: float
    inner_angle: float
    outer_angle: float
    casts_shadows: bool

    @classmethod
    def default(cls) -> "SpotLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_SpotLightEXT, "cna_spot_light_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "SpotLight":
        return cls(_vector(value.position), _vector(value.direction),
                   _vector(value.color), float(value.intensity), float(value.range),
                   float(value.inner_angle), float(value.outer_angle),
                   bool(value.casts_shadows))

    def _native(self):
        value = _support.in_struct(_engine.CNA_SpotLightEXT, 1)
        value.position = _native_vector(self.position)
        value.direction = _native_vector(self.direction)
        value.color = _native_vector(self.color)
        value.intensity = _support.real(self.intensity, "intensity")
        value.range = _support.real(self.range_, "range_")
        value.inner_angle = _support.real(self.inner_angle, "inner_angle")
        value.outer_angle = _support.real(self.outer_angle, "outer_angle")
        value.casts_shadows = 1 if self.casts_shadows else 0
        return value


@dataclass(frozen=True)
class PunctualLight:
    """One light slot an effect carries, with its shadow already resolved.

    Where :class:`PointLight` and :class:`SpotLight` describe a light a shadow
    map is *built from*, this is what an effect is *given*: a kind, the light's
    geometry, and the shadow texture and transform to sample. ``shadow_cube``
    and ``shadow_map`` are borrowed textures the caller keeps alive; ``None``
    means the light casts no shadow.
    """

    kind: PunctualLightKind
    position: Vector3
    direction: Vector3
    diffuse_color: Vector3
    range_: float
    inner_angle: float
    outer_angle: float
    shadow_depth_bias: float
    shadow_view_projection: Matrix
    shadow_cube: object = None
    shadow_map: object = None

    @classmethod
    def default(cls) -> "PunctualLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        value = _defaults(_engine.CNA_PunctualLightEXT, "cna_punctual_light_ext_init")
        return cls(PunctualLightKind(int(value.kind)), _vector(value.position),
                   _vector(value.direction), _vector(value.diffuse_color),
                   float(value.range), float(value.inner_angle),
                   float(value.outer_angle), float(value.shadow_depth_bias),
                   _matrix(value.shadow_view_projection), None, None)

    def _native(self):
        value = _support.in_struct(_engine.CNA_PunctualLightEXT, 1)
        value.kind = int(PunctualLightKind(self.kind))
        value.position = _native_vector(self.position)
        value.direction = _native_vector(self.direction)
        value.diffuse_color = _native_vector(self.diffuse_color)
        value.range = _support.real(self.range_, "range_")
        value.inner_angle = _support.real(self.inner_angle, "inner_angle")
        value.outer_angle = _support.real(self.outer_angle, "outer_angle")
        value.shadow_depth_bias = _support.real(self.shadow_depth_bias,
                                                "shadow_depth_bias")
        value.shadow_cube = _texture_handle(self.shadow_cube, "shadow_cube")
        value.shadow_map = _texture_handle(self.shadow_map, "shadow_map")
        value.shadow_view_projection = _native_matrix(self.shadow_view_projection)
        return value

    @classmethod
    def _from_native(cls, value, shadow_cube=None, shadow_map=None) -> "PunctualLight":
        """Rebuilds the value, keeping the caller's texture objects.

        The handles CNA hands back are the ones it was given, and the objects
        that own them are the caller's; handing back a second facade for a
        borrowed texture would create a second owner of one thing.
        """
        return cls(PunctualLightKind(int(value.kind)), _vector(value.position),
                   _vector(value.direction), _vector(value.diffuse_color),
                   float(value.range), float(value.inner_angle),
                   float(value.outer_angle), float(value.shadow_depth_bias),
                   _matrix(value.shadow_view_projection), shadow_cube, shadow_map)


def _texture_handle(value: object, what: str) -> int:
    if value is None:
        return 0
    if not hasattr(value, "_require_handle"):
        raise TypeError(f"{what} must be a graphics texture or None")
    return int(value._require_handle())


@dataclass(frozen=True)
class ShadowCascadeState:
    """The cascade split state an effect samples cascaded shadows with.

    ``world_to_atlas`` and ``split_distance`` are always
    :data:`SHADOW_CASCADE_MAXIMUM` long whatever ``count`` is, because the
    native structure is fixed-size; only the first ``count`` entries mean
    anything. ``count`` of zero disables cascaded shadows.
    """

    count: int
    blend_band: float
    world_to_atlas: tuple[Matrix, ...]
    split_distance: tuple[float, ...]
    camera_view: Matrix
    debug_tint: bool

    @classmethod
    def default(cls) -> "ShadowCascadeState":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_ShadowCascadeStateEXT, "cna_shadow_cascade_state_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "ShadowCascadeState":
        return cls(int(value.count), float(value.blend_band),
                   tuple(_matrix(value.world_to_atlas[index])
                         for index in range(SHADOW_CASCADE_MAXIMUM)),
                   tuple(float(value.split_distance[index])
                         for index in range(SHADOW_CASCADE_MAXIMUM)),
                   _matrix(value.camera_view), bool(value.debug_tint))

    def _native(self):
        value = _support.in_struct(_engine.CNA_ShadowCascadeStateEXT, 1)
        value.count = _support.checked(self.count, "int32", "count")
        value.blend_band = _support.real(self.blend_band, "blend_band")
        if len(self.world_to_atlas) != SHADOW_CASCADE_MAXIMUM:
            raise ValueError(
                f"world_to_atlas must hold {SHADOW_CASCADE_MAXIMUM} matrices, "
                f"got {len(self.world_to_atlas)}")
        if len(self.split_distance) != SHADOW_CASCADE_MAXIMUM:
            raise ValueError(
                f"split_distance must hold {SHADOW_CASCADE_MAXIMUM} distances, "
                f"got {len(self.split_distance)}")
        for index in range(SHADOW_CASCADE_MAXIMUM):
            value.world_to_atlas[index] = _native_matrix(self.world_to_atlas[index])
            value.split_distance[index] = _support.real(
                self.split_distance[index], "split_distance")
        value.camera_view = _native_matrix(self.camera_view)
        value.debug_tint = 1 if self.debug_tint else 0
        return value


class ClusteredLightKind(IntEnum):
    """Which of the two shapes a clustered light has.

    There is no directional member: a light with no position has no bounding
    sphere, so it cannot be sorted into clusters at all and is a job for the
    effect's own directional term instead.
    """

    Point = _engine.CNA_CLUSTERED_LIGHT_TYPE_POINT
    Spot = _engine.CNA_CLUSTERED_LIGHT_TYPE_SPOT


class AreaLightShape(IntEnum):
    """The outline an area light emits from."""

    Rectangle = _engine.CNA_AREA_LIGHT_SHAPE_RECTANGLE_EXT
    Disc = _engine.CNA_AREA_LIGHT_SHAPE_DISC_EXT
    Tube = _engine.CNA_AREA_LIGHT_SHAPE_TUBE_EXT


@dataclass(frozen=True)
class ClusteredLight:
    """One light a :class:`~cna.extensions.engine.ClusteredLightSet` holds.

    The union of :class:`PointLight` and :class:`SpotLight`: ``direction``,
    ``inner_angle`` and ``outer_angle`` mean nothing when ``kind`` is
    ``Point``, and CNA does not read them then. ``is_usable`` is what decides
    whether a set will take it.
    """

    kind: ClusteredLightKind
    position: Vector3
    direction: Vector3
    color: Vector3
    intensity: float
    range_: float
    inner_angle: float
    outer_angle: float
    casts_shadows: bool

    @classmethod
    def default(cls) -> "ClusteredLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_ClusteredLightEXT, "cna_clustered_light_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "ClusteredLight":
        return cls(ClusteredLightKind(int(value.type)), _vector(value.position),
                   _vector(value.direction), _vector(value.color),
                   float(value.intensity), float(value.range),
                   float(value.inner_angle), float(value.outer_angle),
                   bool(value.casts_shadows))

    def _native(self):
        value = _support.in_struct(_engine.CNA_ClusteredLightEXT, 1)
        value.type = int(ClusteredLightKind(self.kind))
        value.position = _native_vector(self.position)
        value.direction = _native_vector(self.direction)
        value.color = _native_vector(self.color)
        value.intensity = _support.real(self.intensity, "intensity")
        value.range = _support.real(self.range_, "range_")
        value.inner_angle = _support.real(self.inner_angle, "inner_angle")
        value.outer_angle = _support.real(self.outer_angle, "outer_angle")
        value.casts_shadows = 1 if self.casts_shadows else 0
        return value

    @property
    def is_usable(self) -> bool:
        """Whether a clustered light set would accept this light.

        CNA decides, not this module: a set refuses a light rather than
        skipping it later, and asking first is how a caller finds out without
        catching the refusal.

        Unlike :attr:`AreaLight.is_valid`, this needs the engine layer:
        ``engine_layer.h`` documents it as answering ``NOT_SUPPORTED`` without
        one, and it does. The rule belongs to the light *set* rather than to the
        light value, which is where the difference between the two comes from.
        """
        native = self._native()
        return _support.out_bool("cna_clustered_light_set_is_usable", c.byref(native))


@dataclass(frozen=True)
class AreaLight:
    """A light that emits from a surface rather than from a point.

    ``right_axis`` and ``up_axis`` are half-extents, not directions: their
    lengths are half the light's width and half its height. A ``Disc`` uses
    them as half-axes of an ellipse, and a ``Tube`` uses ``right_axis`` as its
    axis and the *length* of ``up_axis`` as its radius.
    """

    shape: AreaLightShape
    two_sided: bool
    position: Vector3
    right_axis: Vector3
    up_axis: Vector3
    color: Vector3
    intensity: float
    range_: float

    @classmethod
    def default(cls) -> "AreaLight":
        """CNA's own canonical defaults, read rather than transcribed."""
        return cls._from_native(
            _defaults(_engine.CNA_AreaLightEXT, "cna_area_light_ext_init"))

    @classmethod
    def _from_native(cls, value) -> "AreaLight":
        return cls(AreaLightShape(int(value.shape)), bool(value.two_sided),
                   _vector(value.position), _vector(value.right_axis),
                   _vector(value.up_axis), _vector(value.color),
                   float(value.intensity), float(value.range))

    def _native(self):
        value = _support.in_struct(_engine.CNA_AreaLightEXT, 1)
        value.shape = int(AreaLightShape(self.shape))
        value.two_sided = 1 if self.two_sided else 0
        value.position = _native_vector(self.position)
        value.right_axis = _native_vector(self.right_axis)
        value.up_axis = _native_vector(self.up_axis)
        value.color = _native_vector(self.color)
        value.intensity = _support.real(self.intensity, "intensity")
        value.range = _support.real(self.range_, "range_")
        return value

    @property
    def is_valid(self) -> bool:
        """Whether CNA would shade with this light rather than ignore it.

        Answers on a build with no engine layer, which ``engine_layer.h``
        documents as "SUCCESS in every build" and measurement confirms: the rule
        belongs to the value itself. :attr:`ClusteredLight.is_usable` is the
        deliberate opposite.
        """
        native = self._native()
        return _support.out_bool("cna_area_light_ext_is_valid", c.byref(native))


def _device_handle(device: object) -> c.c_uint64:
    """The native handle of a strict-XNA graphics device, refusing anything else."""
    if not hasattr(device, "_require_handle"):
        raise TypeError("device must be a Microsoft.Xna.Framework.Graphics.GraphicsDevice")
    return c.c_uint64(int(device._require_handle()))


class _EngineObject:
    """Common lifetime for an owned engine handle and the counted views it lends.

    Public subclasses take the arguments a caller has -- a device, a size, some
    source -- and never a handle: a signature naming one would publish a private
    native type, and there is no owned handle a caller could supply.

    Every engine getter that answers with a handle answers with a *fresh* counted
    view, whatever its documentation says (ENGINE-002). A view is therefore built
    once per key, cached, and disposed when the owner closes -- so reading a
    property in a loop cannot leak, and the owning game can still be destroyed.
    """

    __slots__ = ("_handle", "_device", "_views", "_retained")

    _DESTROY: str = ""

    def _attach(self, handle: int, device: object = None) -> None:
        self._handle = _support.NativeHandle(handle, self._DESTROY, type(self).__name__)
        self._device = device
        self._views: dict[str, object] = {}
        self._retained: list[object] = []

    @property
    def is_closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._handle.closed

    def close(self) -> None:
        """Disposes every view handed out, then releases the object.

        A view is either a strict-XNA resource, which is released by ``Dispose``,
        or another object in this package, which is released by ``close``. Both
        are asked for, because a view left alive keeps the owning game alive and
        the failure shows up as an unrelated game refusing to be destroyed.
        """
        if self._handle.closed:
            return
        for view in reversed(list(self._views.values())):
            self._release_view(view)
        self._views.clear()
        self._handle.close()
        self._retained.clear()

    @staticmethod
    def _release_view(view: object) -> None:
        dispose = getattr(view, "Dispose", None)
        if dispose is not None:
            if not getattr(view, "IsDisposed", False):
                dispose()
            return
        close = getattr(view, "close", None)
        if close is not None and not getattr(view, "is_closed", False):
            close()

    def __enter__(self):
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def _drop_view(self, key: str) -> None:
        """Releases one cached view, because what it looked at has been replaced."""
        view = self._views.pop(key, None)
        if view is not None:
            self._release_view(view)

    def _view(self, key: str, route: str, factory):
        existing = self._views.get(key)
        if existing is not None and not (getattr(existing, "IsDisposed", False)
                                         or getattr(existing, "is_closed", False)):
            return existing
        handle = _support.out_handle(route, self._handle.argument)
        if handle == 0:
            return None
        view = factory(handle)
        self._views[key] = view
        return view

    def _render_target_view(self, key: str, route: str):
        from Microsoft.Xna.Framework.Graphics import RenderTarget2D

        return self._view(key, route,
                          lambda handle: RenderTarget2D._view_of(self._device, handle))

    def _effect_view(self, key: str, route: str):
        from Microsoft.Xna.Framework.Graphics import Effect

        def build(handle: int):
            effect = Effect.__new__(Effect)
            effect._initialize_native(self._device, handle)
            return effect

        return self._view(key, route, build)
