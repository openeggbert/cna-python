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
