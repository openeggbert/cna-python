"""Light probes: the ambient light a point in a scene receives, from every direction.

A probe stores what arrives at one point as nine spherical-harmonic
coefficients -- three bands, three channels. That is enough because irradiance is
the environment convolved with a cosine lobe, and a cosine lobe has almost
nothing above second order: the whole environment collapses into nine numbers
that still reconstruct the diffuse response of any surface orientation. It is
also small enough to interpolate, which is what makes a *grid* of them
affordable.

The pieces
----------

* :class:`LightProbe` -- nine coefficients, a position, and optionally six
  visibility moments.
* :class:`LightProbeVolume` -- a box of probes on a regular grid, sampled by
  trilinear interpolation weighted by visibility, so a lit room does not leak
  into the dark one next door.
* :class:`LightProbeBaker` -- captures a probe by drawing the scene six times,
  once per cube face, through a callback.
* :class:`EnvironmentProcessor` -- turns a panorama into the cube maps a PBR
  effect samples: an irradiance cube, a prefiltered specular cube and a BRDF
  table. Its pure helpers are published beside them.
* :class:`ImageBasedLight` -- those three textures as one value, which a
  :class:`~cna.extensions.engine.PbrEffect` shades with.

Visibility, and what it is for
------------------------------

A probe in a corridor sees a wall a metre away in one direction and open space
in another. Without that, interpolating it into a neighbouring room carries the
corridor's light through the wall. Each probe therefore records the mean and
mean-square distance to geometry along six axes, and a point further away than
the mean is discounted by Chebyshev's inequality -- the same test a variance
shadow map uses, and for the same reason: a flat wall has almost no variance and
cuts off sharply, a cluttered direction has a lot and fades.

What needs a renderer
---------------------

A probe and a volume are arithmetic: they work on either qualified artifact.
The baker and the environment processor draw and read back, so they need a
device with a renderer behind it. :func:`hammersley`,
:func:`importance_sample_ggx`, :func:`mip_for_roughness`,
:func:`roughness_for_mip`, :func:`cube_face_direction` and
:func:`direction_to_equirectangular` are pure functions with no object at all,
published so a caller writing their own filtering can check it against CNA's.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from Microsoft.Xna.Framework import BoundingBox, Matrix, Vector3

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import (_EngineObject, _device_handle, _matrix, _native_vector, _vector)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import (
        Effect, GraphicsDevice, Texture2D, TextureCube,
    )

__all__ = [
    "LightProbe",
    "LightProbeVolume",
    "LightProbeBaker",
    "EnvironmentProcessor",
    "ImageBasedLight",
    "probe_evaluation_glsl",
    "hammersley",
    "importance_sample_ggx",
    "mip_for_roughness",
    "roughness_for_mip",
    "cube_face_direction",
    "direction_to_equirectangular",
    "LIGHT_PROBE_COEFFICIENT_COUNT",
    "LIGHT_PROBE_VISIBILITY_DIRECTIONS",
    "LIGHT_PROBE_VOLUME_MAXIMUM_PROBES",
    "LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE",
    "LIGHT_PROBE_BAKER_FACE_COUNT",
]

#: Nine: three spherical-harmonic bands, which is everything a cosine lobe keeps.
LIGHT_PROBE_COEFFICIENT_COUNT = _engine.CNA_LIGHT_PROBE_COEFFICIENT_COUNT_EXT
#: Six: +X, -X, +Y, -Y, +Z, -Z, in that order.
LIGHT_PROBE_VISIBILITY_DIRECTIONS = _engine.CNA_LIGHT_PROBE_VISIBILITY_DIRECTIONS_EXT
#: How many probes one volume holds. The grid is uploaded as a texture and the
#: bound is what its size is chosen from.
LIGHT_PROBE_VOLUME_MAXIMUM_PROBES = _engine.CNA_LIGHT_PROBE_VOLUME_MAX_PROBES_EXT
#: The cube-face resolution a baker captures at when none is given.
LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE = _engine.CNA_LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE
#: The six faces one capture renders.
LIGHT_PROBE_BAKER_FACE_COUNT = _engine.CNA_LIGHT_PROBE_BAKER_FACE_COUNT


def _box(value: _engine.CNA_BoundingBox) -> BoundingBox:
    return BoundingBox(_vector(value.min), _vector(value.max))


def _native_box(value: BoundingBox) -> _engine.CNA_BoundingBox:
    if not isinstance(value, BoundingBox):
        raise TypeError("expected a Microsoft.Xna.Framework.BoundingBox")
    native = _engine.CNA_BoundingBox()
    native.min = _native_vector(value.Min)
    native.max = _native_vector(value.Max)
    return native


class LightProbe(_EngineObject):
    """The ambient light at one point, as nine spherical-harmonic coefficients.

    A handle rather than a value because a volume hands probes back by filling
    one the caller already owns, and because nine vectors plus six pairs of
    moments is more state than a C structure returns by value.

    Needs no graphics device: a probe is arithmetic, and one can be built,
    filled and evaluated on a build that cannot draw at all.
    """

    __slots__ = ()
    _DESTROY = "cna_light_probe_ext_destroy"

    def __init__(self, position: Vector3 | None = None) -> None:
        if position is None:
            handle = _support.out_handle("cna_light_probe_ext_create")
        else:
            native = _native_vector(position)
            handle = _support.out_handle("cna_light_probe_ext_create_at", c.byref(native))
        self._attach(handle)

    def copy_from(self, source: "LightProbe") -> None:
        """Overwrites this probe with every value of ``source``."""
        if not isinstance(source, LightProbe):
            raise TypeError("source must be a LightProbe")
        _support.call("cna_light_probe_ext_copy_from", self._handle.argument,
                      source._handle.argument)

    @property
    def position(self) -> Vector3:
        """Where the probe was captured."""
        value = _abi.CNA_Vector3()
        _support.call("cna_light_probe_ext_get_position", self._handle.argument,
                      c.byref(value))
        return _vector(value)

    @position.setter
    def position(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call("cna_light_probe_ext_set_position", self._handle.argument,
                      c.byref(native))

    def coefficient(self, index: int) -> Vector3:
        """One coefficient, as a colour rather than a direction."""
        value = _abi.CNA_Vector3()
        _support.call("cna_light_probe_ext_get_coefficient", self._handle.argument,
                      c.c_int32(_support.checked(index, "int32", "index")), c.byref(value))
        return _vector(value)

    def set_coefficient(self, index: int, value: Vector3) -> None:
        """Replaces one coefficient."""
        native = _native_vector(value)
        _support.call("cna_light_probe_ext_set_coefficient", self._handle.argument,
                      c.c_int32(_support.checked(index, "int32", "index")),
                      c.byref(native))

    def coefficients(self) -> tuple[Vector3, ...]:
        """All :data:`LIGHT_PROBE_COEFFICIENT_COUNT` of them, in band order."""
        values, written = _support.copied_values(
            _abi.CNA_Vector3, "cna_light_probe_ext_copy_coefficients",
            (self._handle.argument,))
        return tuple(_vector(values[index]) for index in range(written))

    def irradiance(self, normal: Vector3) -> Vector3:
        """What a surface facing ``normal`` receives.

        Floored at zero per channel: a projection can go slightly negative where
        the environment is dark and the fit overshoots, and negative irradiance
        is light being removed from a surface.
        """
        native = _native_vector(normal)
        value = _abi.CNA_Vector3()
        _support.call("cna_light_probe_ext_irradiance", self._handle.argument,
                      c.byref(native), c.byref(value))
        return _vector(value)

    def set_visibility(self, direction: int, mean_distance: float,
                       mean_squared_distance: float) -> None:
        """Records how far geometry is along one of the six axes.

        Both moments, because the second is what makes the test a distribution
        rather than a threshold. CNA floors the mean at zero and the
        mean-square at the mean squared: no distribution has negative variance,
        and one that appeared to would make the weight fall outside zero to one.
        """
        _support.call("cna_light_probe_ext_set_visibility", self._handle.argument,
                      c.c_int32(_support.checked(direction, "int32", "direction")),
                      c.c_float(_support.real(mean_distance, "mean_distance")),
                      c.c_float(_support.real(mean_squared_distance,
                                              "mean_squared_distance")))

    def visibility_mean(self, direction: int) -> float:
        """The mean distance to geometry along one axis."""
        return _support.out_f32(
            "cna_light_probe_ext_get_visibility_mean", self._handle.argument,
            c.c_int32(_support.checked(direction, "int32", "direction")))

    def visibility_mean_squared(self, direction: int) -> float:
        """The mean *squared* distance along one axis."""
        return _support.out_f32(
            "cna_light_probe_ext_get_visibility_mean_squared", self._handle.argument,
            c.c_int32(_support.checked(direction, "int32", "direction")))

    @property
    def has_visibility(self) -> bool:
        """Whether any direction has been recorded."""
        return _support.out_bool("cna_light_probe_ext_has_visibility",
                                 self._handle.argument)

    def visibility_weight(self, direction: Vector3, distance: float) -> float:
        """How much this probe is trusted to be lighting a point that far along ``direction``.

        One for a probe with nothing recorded and for a point nearer than the
        mean; falling toward zero past it, at a rate the variance sets. Blended
        across the axes the direction actually points along rather than snapped
        to the nearest, so the weight does not jump as a surface turns.
        """
        native = _native_vector(direction)
        return _support.out_f32(
            "cna_light_probe_ext_visibility_weight", self._handle.argument,
            c.byref(native), c.c_float(_support.real(distance, "distance")))

    @property
    def is_zero(self) -> bool:
        """Whether every coefficient is exactly zero -- a probe that stores no light."""
        return _support.out_bool("cna_light_probe_ext_is_zero", self._handle.argument)

    def scale(self, factor: float) -> None:
        """Multiplies every coefficient. A negative factor is ignored, not refused."""
        _support.call("cna_light_probe_ext_scale", self._handle.argument,
                      c.c_float(_support.real(factor, "factor")))

    def matches(self, other: "LightProbe") -> bool:
        """Whether two probes hold the same position and the same coefficients.

        CNA compares, not Python: the comparison is exact rather than
        approximate, and which fields take part is its decision. Visibility does
        not; two probes with the same light and different surroundings are equal.
        """
        if not isinstance(other, LightProbe):
            raise TypeError("other must be a LightProbe")
        return _support.out_bool("cna_light_probe_ext_equals", self._handle.argument,
                                 other._handle.argument)


def probe_evaluation_glsl() -> str:
    """CNA's own GLSL for evaluating a probe, matching :meth:`LightProbe.irradiance`."""
    return _support.copied_text("cna_light_probe_ext_copy_evaluation_glsl",
                                (), "the probe evaluation GLSL")


class LightProbeVolume(_EngineObject):
    """A box of probes on a regular grid, interpolated at any point inside it.

    Probe positions are the *grid's*, not the probe's: assigning a probe into a
    cell overrides its position with the cell's. A grid that says one thing and
    the probes another makes the interpolation weights describe one arrangement
    and the light describe a different one, which looks like the lighting
    lagging behind the geometry.

    Sampling is trilinear over the eight surrounding probes, with each corner's
    weight multiplied by its own visibility of the point being lit -- so a probe
    that recorded a wall closer than the point cannot light it.
    """

    __slots__ = ()
    _DESTROY = "cna_light_probe_volume_ext_destroy"

    def __init__(self, bounds: BoundingBox, count_x: int, count_y: int,
                 count_z: int) -> None:
        native = _native_box(bounds)
        self._attach(_support.out_handle(
            "cna_light_probe_volume_ext_create", c.byref(native),
            c.c_int32(_support.checked(count_x, "int32", "count_x")),
            c.c_int32(_support.checked(count_y, "int32", "count_y")),
            c.c_int32(_support.checked(count_z, "int32", "count_z"))))

    @property
    def bounds(self) -> BoundingBox:
        """The box the grid spans."""
        value = _engine.CNA_BoundingBox()
        _support.call("cna_light_probe_volume_ext_get_bounds", self._handle.argument,
                      c.byref(value))
        return _box(value)

    @property
    def count_x(self) -> int:
        """How many probes lie along X."""
        return _support.out_i32("cna_light_probe_volume_ext_get_count_x",
                                self._handle.argument)

    @property
    def count_y(self) -> int:
        """How many probes lie along Y."""
        return _support.out_i32("cna_light_probe_volume_ext_get_count_y",
                                self._handle.argument)

    @property
    def count_z(self) -> int:
        """How many probes lie along Z."""
        return _support.out_i32("cna_light_probe_volume_ext_get_count_z",
                                self._handle.argument)

    @property
    def probe_count(self) -> int:
        """How many probes the volume holds in total."""
        return _support.out_i32("cna_light_probe_volume_ext_get_probe_count",
                                self._handle.argument)

    def probe_position(self, x: int, y: int, z: int) -> Vector3:
        """Where one cell of the grid sits.

        Evenly spaced from the box's minimum to its maximum *inclusive*, so an
        axis with one probe puts it at that axis's minimum: there is no interval
        for it to be in the middle of.
        """
        value = _abi.CNA_Vector3()
        _support.call("cna_light_probe_volume_ext_get_probe_position",
                      self._handle.argument, *self._indices(x, y, z), c.byref(value))
        return _vector(value)

    def read_probe(self, x: int, y: int, z: int, into: LightProbe) -> None:
        """Copies one cell's probe into a probe the caller owns.

        Into an existing probe rather than out as a new one, because that is
        what CNA's route does: no handle is created and none is transferred, so
        a caller reading a whole grid allocates one probe and reuses it.
        """
        if not isinstance(into, LightProbe):
            raise TypeError("into must be a LightProbe")
        _support.call("cna_light_probe_volume_ext_get_probe", self._handle.argument,
                      *self._indices(x, y, z), into._handle.argument)

    def write_probe(self, x: int, y: int, z: int, probe: LightProbe) -> None:
        """Copies a probe into one cell, overriding its position with the cell's."""
        if not isinstance(probe, LightProbe):
            raise TypeError("probe must be a LightProbe")
        _support.call("cna_light_probe_volume_ext_set_probe", self._handle.argument,
                      *self._indices(x, y, z), probe._handle.argument)

    def contains(self, position: Vector3) -> bool:
        """Whether a point lies inside the box, boundaries included."""
        native = _native_vector(position)
        return _support.out_bool("cna_light_probe_volume_ext_contains",
                                 self._handle.argument, c.byref(native))

    def sample(self, position: Vector3, into: LightProbe) -> None:
        """Interpolates the eight surrounding probes into a probe the caller owns.

        A position outside the box is clamped into it rather than refused: the
        nearest probes are still the best answer available, and refusing would
        make every object that pokes out of the volume go black.
        """
        if not isinstance(into, LightProbe):
            raise TypeError("into must be a LightProbe")
        native = _native_vector(position)
        _support.call("cna_light_probe_volume_ext_sample_probe", self._handle.argument,
                      c.byref(native), into._handle.argument)

    def irradiance(self, position: Vector3, normal: Vector3) -> Vector3:
        """What a surface at ``position`` facing ``normal`` receives.

        The same as sampling and then evaluating, in one call.
        """
        native_position = _native_vector(position)
        native_normal = _native_vector(normal)
        value = _abi.CNA_Vector3()
        _support.call("cna_light_probe_volume_ext_irradiance", self._handle.argument,
                      c.byref(native_position), c.byref(native_normal), c.byref(value))
        return _vector(value)

    @property
    def is_zero(self) -> bool:
        """Whether every probe in the volume stores no light."""
        return _support.out_bool("cna_light_probe_volume_ext_is_zero",
                                 self._handle.argument)

    @staticmethod
    def _indices(x: int, y: int, z: int):
        return (c.c_int32(_support.checked(x, "int32", "x")),
                c.c_int32(_support.checked(y, "int32", "y")),
                c.c_int32(_support.checked(z, "int32", "z")))


class LightProbeBaker(_EngineObject):
    """Captures probes by drawing the scene six times, once per cube face.

    The callback is given the view and projection for one face and should draw
    the scene and nothing else: the baker owns the render target, and binding
    another one inside the callback loses the face being captured.

    **The callback is rooted for the call and no longer.** It is a
    ``TRANSIENT_CALLBACK_VIEW``: CNA holds the trampoline only while the bake
    route runs, so nothing needs to outlive it. A Python exception raised inside
    it is caught, remembered, and re-raised after the native call returns rather
    than unwinding through C.
    """

    __slots__ = ()
    _DESTROY = "cna_light_probe_baker_destroy"

    def __init__(self, device: "GraphicsDevice", face_size: int | None = None) -> None:
        if face_size is None:
            handle = _support.out_handle("cna_light_probe_baker_create",
                                         _device_handle(device))
        else:
            handle = _support.out_handle(
                "cna_light_probe_baker_create_with_face_size", _device_handle(device),
                c.c_int32(_support.checked(face_size, "int32", "face_size")))
        self._attach(handle, device)

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can render to a target and read it back."""
        return _support.out_bool("cna_light_probe_baker_is_supported",
                                 self._handle.argument)

    @property
    def face_size(self) -> int:
        """The cube-face resolution each capture renders at."""
        return _support.out_i32("cna_light_probe_baker_get_face_size",
                                self._handle.argument)

    @property
    def near_plane(self) -> float:
        """The near plane of the capture frustum."""
        return _support.out_f32("cna_light_probe_baker_get_near_plane",
                                self._handle.argument)

    @property
    def far_plane(self) -> float:
        """The far plane of the capture frustum."""
        return _support.out_f32("cna_light_probe_baker_get_far_plane",
                                self._handle.argument)

    def set_planes(self, near_plane: float, far_plane: float) -> None:
        """Sets both planes at once, because only the pair is meaningful."""
        _support.call("cna_light_probe_baker_set_planes", self._handle.argument,
                      c.c_float(_support.real(near_plane, "near_plane")),
                      c.c_float(_support.real(far_plane, "far_plane")))

    def face_view(self, face: int, position: Vector3) -> Matrix:
        """The view matrix one face of a capture uses.

        Published so a caller can reconstruct where a captured texel was looking
        without agreeing with a cube-map layout convention: there is no
        convention to agree with, only the matrix that was used.
        """
        native = _native_vector(position)
        value = _abi.CNA_Matrix()
        _support.call("cna_light_probe_baker_face_view", self._handle.argument,
                      c.c_int32(_support.checked(face, "int32", "face")),
                      c.byref(native), c.byref(value))
        return _matrix(value)

    def bake_probe(self, position: Vector3,
                   draw: Callable[[Matrix, Matrix], None]) -> LightProbe:
        """Captures one probe at ``position`` and returns it."""
        native = _native_vector(position)
        with _SceneDraw(draw) as callback:
            handle = _support.out_handle("cna_light_probe_baker_bake_probe",
                                         self._handle.argument, c.byref(native),
                                         callback.trampoline, None)
        probe = LightProbe.__new__(LightProbe)
        probe._attach(handle)
        return probe

    def bake_light(self, volume: LightProbeVolume,
                   draw: Callable[[Matrix, Matrix], None]) -> None:
        """Captures every probe of a volume, writing the light into each."""
        self._bake_volume("cna_light_probe_baker_bake_light", volume, draw)

    def bake_visibility(self, volume: LightProbeVolume,
                        draw: Callable[[Matrix, Matrix], None]) -> None:
        """Captures every probe's *visibility* -- how far geometry is along six axes.

        A second pass rather than part of the first, because the two want
        different things drawn: light wants the lit scene, and visibility wants
        depth.
        """
        self._bake_volume("cna_light_probe_baker_bake_visibility", volume, draw)

    def _bake_volume(self, route: str, volume: LightProbeVolume, draw) -> None:
        if not isinstance(volume, LightProbeVolume):
            raise TypeError("volume must be a LightProbeVolume")
        with _SceneDraw(draw) as callback:
            _support.call(route, self._handle.argument, volume._handle.argument,
                          callback.trampoline, None)

    @staticmethod
    def face_count() -> int:
        """How many faces a capture renders. Constant, and the same for every baker."""
        value = c.c_int32()
        _support.call("cna_light_probe_baker_face_count", c.byref(value))
        return int(value.value)


class _SceneDraw:
    """One Python callable, rooted for exactly as long as CNA can call it.

    The trampoline is what CNA holds, so the trampoline is what has to stay
    alive; a bare ``CFUNCTYPE(...)(function)`` built at the call site is
    collected the moment the expression ends and CNA is left with a dangling
    pointer. An exception the callable raises is stored and re-raised by
    ``__exit__``, because a Python exception unwinding through a C frame is
    undefined behaviour and CNA has render state to unwind first.
    """

    __slots__ = ("_draw", "trampoline", "_error")

    def __init__(self, draw: Callable[[Matrix, Matrix], None]) -> None:
        if not callable(draw):
            raise TypeError("draw must be callable")
        self._draw = draw
        self._error: BaseException | None = None
        self.trampoline = _engine.CNA_LightProbeSceneDrawCallback(self._invoke)

    def _invoke(self, view, projection, _context) -> None:
        if self._error is not None:
            return
        try:
            self._draw(_matrix(view.contents), _matrix(projection.contents))
        except BaseException as error:  # re-raised outside the native call
            self._error = error

    def __enter__(self) -> "_SceneDraw":
        return self

    def __exit__(self, *_exception: object) -> None:
        error, self._error = self._error, None
        if error is not None:
            raise error


@dataclass(frozen=True)
class ImageBasedLight:
    """The three textures a PBR effect samples for image-based lighting.

    ``irradiance`` answers the diffuse term for any surface normal;
    ``prefiltered_specular`` answers the specular one at a mip level chosen by
    roughness; ``brdf_lut`` holds the split-sum scale and bias. All three are the
    caller's own textures, and the effect borrows them.
    """

    irradiance: object
    prefiltered_specular: object
    brdf_lut: object
    prefiltered_mip_count: int
    intensity: float

    @classmethod
    def default(cls) -> "ImageBasedLight":
        """CNA's own canonical defaults, read rather than transcribed.

        Every texture is absent: the defaults describe an inactive light, which
        is what an effect carries before one is assigned.
        """
        value = _engine.CNA_ImageBasedLightEXT()
        _support.call("cna_image_based_light_ext_init", c.byref(value))
        return cls(None, None, None, int(value.prefiltered_mip_count),
                   float(value.intensity))

    @property
    def is_valid(self) -> bool:
        """Whether CNA would shade with this light rather than ignore it."""
        native = self._native()
        return _support.out_bool("cna_image_based_light_ext_is_valid", c.byref(native))

    def _native(self):
        value = _support.in_struct(_engine.CNA_ImageBasedLightEXT, 1)
        value.irradiance = _texture_handle(self.irradiance, "irradiance")
        value.prefiltered_specular = _texture_handle(self.prefiltered_specular,
                                                     "prefiltered_specular")
        value.brdf_lut = _texture_handle(self.brdf_lut, "brdf_lut")
        value.prefiltered_mip_count = _support.checked(
            self.prefiltered_mip_count, "int32", "prefiltered_mip_count")
        value.intensity = _support.real(self.intensity, "intensity")
        return value


def _texture_handle(value: object, what: str) -> int:
    if value is None:
        return 0
    if not hasattr(value, "_require_handle"):
        raise TypeError(f"{what} must be a graphics texture or None")
    return int(value._require_handle())


class EnvironmentProcessor(_EngineObject):
    """Builds the cube maps and table an :class:`ImageBasedLight` is made of.

    Every texture it produces is **owned by the caller**, not by the processor:
    destroying the processor does not release them, which is what lets a game
    build its lighting once at load and throw the processor away.
    """

    __slots__ = ()
    _DESTROY = "cna_environment_processor_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.out_handle("cna_environment_processor_create",
                                         _device_handle(device)), device)

    def convert_equirectangular(self, panorama: "Texture2D",
                                face_size: int) -> "TextureCube":
        """Turns a latitude-longitude panorama into a cube map."""
        return self._cube("cna_environment_processor_convert_equirectangular",
                          c.c_uint64(_texture_handle(panorama, "panorama")),
                          c.c_int32(_support.checked(face_size, "int32", "face_size")))

    def generate_irradiance(self, environment: "TextureCube", size: int,
                            sample_count: int) -> "TextureCube":
        """Convolves an environment with a cosine lobe: the diffuse term."""
        return self._cube("cna_environment_processor_generate_irradiance",
                          c.c_uint64(_texture_handle(environment, "environment")),
                          c.c_int32(_support.checked(size, "int32", "size")),
                          c.c_int32(_support.checked(sample_count, "int32",
                                                     "sample_count")))

    def generate_prefiltered_specular(self, environment: "TextureCube", base_size: int,
                                      mip_count: int,
                                      sample_count: int) -> "TextureCube":
        """Filters an environment once per mip, each for a different roughness."""
        return self._cube("cna_environment_processor_generate_prefiltered_specular",
                          c.c_uint64(_texture_handle(environment, "environment")),
                          c.c_int32(_support.checked(base_size, "int32", "base_size")),
                          c.c_int32(_support.checked(mip_count, "int32", "mip_count")),
                          c.c_int32(_support.checked(sample_count, "int32",
                                                     "sample_count")))

    def generate_brdf_lut(self, size: int, sample_count: int) -> "Texture2D":
        """The split-sum table, indexed by N-dot-V across and roughness down."""
        from Microsoft.Xna.Framework.Graphics import Texture2D

        handle = _support.out_handle(
            "cna_environment_processor_generate_brdf_lut", self._handle.argument,
            c.c_int32(_support.checked(size, "int32", "size")),
            c.c_int32(_support.checked(sample_count, "int32", "sample_count")))
        return Texture2D._view_of(self._device, handle)

    def generate_probe(self, environment: "TextureCube",
                       position: Vector3) -> LightProbe:
        """Projects an environment cube onto one probe's nine coefficients."""
        native = _native_vector(position)
        handle = _support.out_handle(
            "cna_environment_processor_generate_probe", self._handle.argument,
            c.c_uint64(_texture_handle(environment, "environment")), c.byref(native))
        probe = LightProbe.__new__(LightProbe)
        probe._attach(handle)
        return probe

    def _cube(self, route: str, *arguments) -> "TextureCube":
        from Microsoft.Xna.Framework.Graphics import TextureCube

        handle = _support.out_handle(route, self._handle.argument, *arguments)
        return TextureCube._from_handle(self._device, handle)


def mip_for_roughness(roughness: float, mip_count: int) -> float:
    """Which mip of a prefiltered specular cube a roughness reads from."""
    return _support.out_f32(
        "cna_environment_processor_mip_for_roughness",
        c.c_float(_support.real(roughness, "roughness")),
        c.c_int32(_support.checked(mip_count, "int32", "mip_count")))


def roughness_for_mip(mip: float, mip_count: int) -> float:
    """The roughness one mip was filtered for -- the inverse of :func:`mip_for_roughness`."""
    return _support.out_f32(
        "cna_environment_processor_roughness_for_mip",
        c.c_float(_support.real(mip, "mip")),
        c.c_int32(_support.checked(mip_count, "int32", "mip_count")))


def hammersley(index: int, count: int) -> tuple[float, float]:
    """The i-th point of the Hammersley sequence over ``count`` points.

    Published because every importance-sampled integral in this family rests on
    it, and a radical inverse with a wrong bit twiddle produces a sequence that
    still looks random and still converges -- to the wrong number.
    """
    first, second = c.c_float(), c.c_float()
    _support.call("cna_environment_processor_hammersley",
                  c.c_int32(_support.checked(index, "int32", "index")),
                  c.c_int32(_support.checked(count, "int32", "count")),
                  c.byref(first), c.byref(second))
    return float(first.value), float(second.value)


def importance_sample_ggx(x: float, y: float, normal: Vector3,
                          roughness: float) -> Vector3:
    """A half-vector drawn from the GGX distribution around ``normal``.

    **Give it a unit normal.** Measured on CNA 0.21.0, the vector is used as
    supplied: the tangent frame is built from it and the local direction is
    combined with it before the *result* is normalised, so a length other than
    one tilts the sample. Nothing in ``engine_layer.h`` says so, and a normal of
    length 0.99 produces a plausible direction rather than an error, which is
    the kind of mistake that shows up as a slightly wrong reflection and never
    as a failure.
    """
    native = _native_vector(normal)
    value = _abi.CNA_Vector3()
    _support.call("cna_environment_processor_importance_sample_ggx",
                  c.c_float(_support.real(x, "x")), c.c_float(_support.real(y, "y")),
                  c.byref(native), c.c_float(_support.real(roughness, "roughness")),
                  c.byref(value))
    return _vector(value)


def cube_face_direction(face: int, u: float, v: float) -> Vector3:
    """The world direction one texel of a cube face looks along.

    ``v`` runs *down* the face, which is the cube-map convention and the
    opposite of what a texture coordinate usually means. Published so a
    converter and a test agree by construction rather than by both being written
    from the same diagram.

    **A face outside zero to five is not refused.** Measured on CNA 0.21.0, and
    consistent with what ``engine_layer.h`` documents -- it names
    ``CNA_RESULT_INVALID_ARGUMENT`` only for a null output -- any other index
    answers with the -Z face, because the switch's default branch is what -Z
    reaches. Six is therefore five, and minus one is five. Stated here because
    the obvious expectation is a refusal, and a loop written with an off-by-one
    would silently sample one face twice rather than fail.
    """
    value = _abi.CNA_Vector3()
    _support.call("cna_environment_processor_face_direction",
                  c.c_int32(_support.checked(face, "int32", "face")),
                  c.c_float(_support.real(u, "u")), c.c_float(_support.real(v, "v")),
                  c.byref(value))
    return _vector(value)


def direction_to_equirectangular(direction: Vector3) -> tuple[float, float]:
    """Where a direction lands in a panorama, as texture coordinates."""
    native = _native_vector(direction)
    u, v = c.c_float(), c.c_float()
    _support.call("cna_environment_processor_direction_to_equirectangular",
                  c.byref(native), c.byref(u), c.byref(v))
    return float(u.value), float(v.value)
