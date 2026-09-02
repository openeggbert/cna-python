"""Clustered lighting: many small lights, sorted into a grid before shading.

A forward renderer that shades every fragment against every light costs lights
times fragments. Clustered lighting spends a little work up front so it does
not have to: the view frustum is cut into a grid of clusters, each light is
sorted into the clusters its bounding sphere reaches, and a fragment shades
against the handful of lights in its own cluster.

The pieces, in the order a frame builds them
--------------------------------------------

1. :class:`ClusteredLightSet` -- the lights, as values, with the bounding
   sphere each one implies.
2. :class:`ClusteredLightGrid` -- the shape of the cut: tiles across the screen
   and logarithmically spaced slices in depth.
3. :class:`ClusteredLightAssignment` -- which lights landed in which cluster,
   as a compressed-row structure of offsets and indices.
4. :class:`ClusteredLightCompute` -- the same assignment on the GPU, for
   renderers that have compute. It falls back to the CPU rather than failing,
   and both paths are built to produce *identical* lists.
5. :class:`ClusteredLightBuffer` -- all three uploaded as textures a shader can
   walk, plus :func:`light_lookup_glsl` for a caller writing their own.
6. :class:`ClusteredShadowPolicy` -- which of those lights can afford a shadow
   map, inside a fixed budget.
7. :class:`ClusteredForwardEffect` -- CNA's own shader that puts it together.

Area lights are here too, because they are the one light kind the clustered
forward effect shades that the light set does not hold: an area light has an
outline rather than a position, so it is set on the effect directly and paired
with an :class:`AreaLightBrdfTable`.

The device that every constructor takes
---------------------------------------

Four of these constructors are documented in ``engine_layer.h`` as taking "the
owning game". They do not; they take a graphics device, and a real game handle
is refused. See ENGINE-006 in ``docs/engine-upstream-findings.md``. Every class
here takes a ``GraphicsDevice``, like the rest of this package, so the
difference is not visible from Python.

What is pure, and what needs a renderer
---------------------------------------

The set, the grid, the assignment and the shadow policy are CPU objects: they
compute, sort and rank without drawing anything, so they work on either
qualified artifact. :func:`volume_attenuation`, :func:`light_contribution`,
:func:`evaluate_brdf`, :func:`area_light_quad`, :func:`area_light_coverage`,
:func:`area_light_contribution` and :func:`lobe_scale_for` are pure functions
with no object at all -- CNA publishes them beside the GLSL that computes the
same thing on the GPU, so a custom shader can be checked against the CPU rather
than against a screenshot. The buffer, the compute path, the BRDF table and the
forward effect need a device with a renderer behind it.
"""

from __future__ import annotations

import ctypes as c
from typing import TYPE_CHECKING, Iterable, Sequence

from Microsoft.Xna.Framework import BoundingBox, BoundingSphere, Matrix, Vector3

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .pbr import PbrMaterialExtensions
from .values import (AreaLight, ClusteredLight, _EngineObject, _device_handle,
                     _native_matrix, _native_vector, _vector)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import Effect, GraphicsDevice, Texture2D

__all__ = [
    "ClusteredLightSet",
    "ClusteredLightGrid",
    "ClusteredLightAssignment",
    "ClusteredLightCompute",
    "ClusteredLightBuffer",
    "ClusteredShadowPolicy",
    "ClusteredForwardEffect",
    "AreaLightBrdfTable",
    "AreaLightBrdfTerms",
    "light_lookup_glsl",
    "volume_attenuation",
    "light_contribution",
    "lobe_scale_for",
    "area_light_quad",
    "area_light_coverage",
    "area_light_contribution",
    "area_light_shading_glsl",
    "evaluate_brdf",
    "brdf_lookup_glsl",
    "CLUSTERED_LIGHT_SET_MAXIMUM",
    "CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS",
    "CLUSTERED_COMPUTE_DEFAULT_STRIDE",
    "CLUSTERED_FORWARD_MAXIMUM_LIGHTS_PER_FRAGMENT",
    "CLUSTERED_SHADOW_DEFAULT_BUDGET",
    "CLUSTERED_SHADOW_DEFAULT_HYSTERESIS",
    "AREA_LIGHT_QUAD_CORNER_COUNT",
    "AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE",
    "AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT",
]

#: How many lights one clustered light set holds. The uploaded buffer and the
#: shader's index width are sized from this, so the set refuses a 257th light
#: rather than growing.
CLUSTERED_LIGHT_SET_MAXIMUM = _engine.CNA_CLUSTERED_LIGHT_SET_MAX_EXT
#: How many lights one assignment will sort. The index list is sized from it.
CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS = _engine.CNA_CLUSTERED_ASSIGNMENT_MAX_LIGHTS_EXT
#: The per-cluster capacity a GPU assigner uses when none is given.
CLUSTERED_COMPUTE_DEFAULT_STRIDE = _engine.CNA_CLUSTERED_COMPUTE_DEFAULT_STRIDE_EXT
#: How many lights the forward shader will walk for one fragment.
CLUSTERED_FORWARD_MAXIMUM_LIGHTS_PER_FRAGMENT = (
    _engine.CNA_CLUSTERED_FORWARD_MAX_LIGHTS_PER_FRAGMENT_EXT)
#: How many shadow maps a policy grants when none is asked for.
CLUSTERED_SHADOW_DEFAULT_BUDGET = _engine.CNA_CLUSTERED_SHADOW_DEFAULT_BUDGET_EXT
#: How much an incumbent's score is multiplied by, to stop shadows flickering
#: between two lights of nearly equal weight.
CLUSTERED_SHADOW_DEFAULT_HYSTERESIS = _engine.CNA_CLUSTERED_SHADOW_DEFAULT_HYSTERESIS_EXT
#: The four corners an area light is integrated as.
AREA_LIGHT_QUAD_CORNER_COUNT = _engine.CNA_AREA_LIGHT_QUAD_CORNER_COUNT
#: The default edge length of the BRDF lookup table.
AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE = _engine.CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE
#: How many samples each of its texels integrates.
AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT = (
    _engine.CNA_AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT)


def _sphere(value: _engine.CNA_BoundingSphere) -> BoundingSphere:
    return BoundingSphere(_vector(value.center), float(value.radius))


def _native_sphere(value: BoundingSphere) -> _engine.CNA_BoundingSphere:
    if not isinstance(value, BoundingSphere):
        raise TypeError("expected a Microsoft.Xna.Framework.BoundingSphere")
    native = _engine.CNA_BoundingSphere()
    native.center = _native_vector(value.Center)
    native.radius = _support.real(value.Radius, "radius")
    return native


def _sphere_array(values: Iterable[BoundingSphere]):
    """Copies a sequence of bounding spheres into a C array for one call."""
    spheres = tuple(values)
    if not spheres:
        return None, 0
    array = (_engine.CNA_BoundingSphere * len(spheres))()
    for index, sphere in enumerate(spheres):
        array[index] = _native_sphere(sphere)
    return array, len(spheres)


def _int32_array(values: Iterable[int], what: str):
    numbers = tuple(values)
    if not numbers:
        return None, 0
    array = (c.c_int32 * len(numbers))(
        *(_support.checked(number, "int32", what) for number in numbers))
    return array, len(numbers)


# --- the lights ---------------------------------------------------------------


class ClusteredLightSet(_EngineObject):
    """The lights of one frame, and the bounding sphere each one implies.

    A set holds *values*: nothing it hands back keeps it alive, and nothing it
    lends has to be released. It refuses a light it cannot use rather than
    accepting one and skipping it later -- a light that silently does nothing is
    harder to find than one that refused to be added -- so check
    :attr:`ClusteredLight.is_usable` first if the values came from data.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_light_set_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(
            _support.out_handle("cna_clustered_light_set_create", _device_handle(device)),
            device)

    def add(self, light: ClusteredLight) -> int:
        """Appends one light and returns the index it took."""
        if not isinstance(light, ClusteredLight):
            raise TypeError("light must be a ClusteredLight")
        native = light._native()
        return _support.out_i32("cna_clustered_light_set_add",
                                self._handle.argument, c.byref(native))

    def add_point(self, light) -> int:
        """Appends a :class:`~cna.extensions.engine.PointLight`, converted."""
        from .values import PointLight

        if not isinstance(light, PointLight):
            raise TypeError("light must be a PointLight")
        native = light._native()
        return _support.out_i32("cna_clustered_light_set_add_point",
                                self._handle.argument, c.byref(native))

    def add_spot(self, light) -> int:
        """Appends a :class:`~cna.extensions.engine.SpotLight`, converted."""
        from .values import SpotLight

        if not isinstance(light, SpotLight):
            raise TypeError("light must be a SpotLight")
        native = light._native()
        return _support.out_i32("cna_clustered_light_set_add_spot",
                                self._handle.argument, c.byref(native))

    def replace_at(self, index: int, light: ClusteredLight) -> None:
        """Overwrites the light at ``index``, keeping every other index."""
        if not isinstance(light, ClusteredLight):
            raise TypeError("light must be a ClusteredLight")
        native = light._native()
        _support.call("cna_clustered_light_set_replace_at", self._handle.argument,
                      c.c_int32(_support.checked(index, "int32", "index")), c.byref(native))

    def remove_at(self, index: int) -> None:
        """Removes the light at ``index``; every later light moves down one."""
        _support.call("cna_clustered_light_set_remove_at", self._handle.argument,
                      c.c_int32(_support.checked(index, "int32", "index")))

    def clear(self) -> None:
        """Empties the set."""
        _support.call("cna_clustered_light_set_clear", self._handle.argument)

    def __len__(self) -> int:
        return _support.out_i32("cna_clustered_light_set_get_count", self._handle.argument)

    @property
    def is_empty(self) -> bool:
        """Whether the set holds no lights.

        CNA is asked rather than ``len(self) == 0`` being computed here: the two
        are separate routes and only one of them is the set's own answer.
        """
        return _support.out_bool("cna_clustered_light_set_is_empty", self._handle.argument)

    def __getitem__(self, index: int) -> ClusteredLight:
        value = _support.out_struct(
            _engine.CNA_ClusteredLightEXT, 1, "cna_clustered_light_set_get_at",
            self._handle.argument, c.c_int32(_support.checked(index, "int32", "index")))
        return ClusteredLight._from_native(value)

    def lights(self) -> tuple[ClusteredLight, ...]:
        """Every light, copied out in index order."""
        values, written = _support.copied_values(
            _engine.CNA_ClusteredLightEXT, "cna_clustered_light_set_copy_lights",
            (self._handle.argument,))
        return tuple(ClusteredLight._from_native(values[index]) for index in range(written))

    def bounds_at(self, index: int) -> BoundingSphere:
        """The sphere the light at ``index`` reaches.

        Computed from the light rather than stored: a point light's sphere is
        its position and range, and a spot light's is the bounding sphere of its
        cone, which is not centred on the light at all.
        """
        value = _support.out_struct(
            _engine.CNA_BoundingSphere, 0, "cna_clustered_light_set_get_bounds_at",
            self._handle.argument, c.c_int32(_support.checked(index, "int32", "index")))
        return _sphere(value)

    def bounds(self) -> tuple[BoundingSphere, ...]:
        """Every light's sphere, in index order -- what an assignment sorts."""
        values, written = _support.copied_values(
            _engine.CNA_BoundingSphere, "cna_clustered_light_set_copy_bounds",
            (self._handle.argument,))
        return tuple(_sphere(values[index]) for index in range(written))


# --- the grid -----------------------------------------------------------------


class ClusteredLightGrid(_EngineObject):
    """The frustum cut into tiles across the screen and slices in depth.

    Depth is sliced *logarithmically*: cluster boundaries are
    ``near * (far / near) ** (slice / slice_count)``, so a slice near the camera
    is thin and one at the horizon is thick. That matches how perspective
    distributes fragments, and it is why the near plane may not be zero -- the
    spacing is a ratio of the two planes, and zero has no logarithm.

    A grid has no shape until :meth:`set_projection` has been called:
    :meth:`slice_distance` answers zero and :meth:`cluster_bounds` refuses.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_light_grid_destroy"

    def __init__(self, device: "GraphicsDevice", tiles_x: int, tiles_y: int,
                 slice_count: int) -> None:
        self._attach(
            _support.out_handle(
                "cna_clustered_light_grid_create", _device_handle(device),
                c.c_int32(_support.checked(tiles_x, "int32", "tiles_x")),
                c.c_int32(_support.checked(tiles_y, "int32", "tiles_y")),
                c.c_int32(_support.checked(slice_count, "int32", "slice_count"))),
            device)

    @property
    def tiles_x(self) -> int:
        """How many tiles the grid has across the screen."""
        return _support.out_i32("cna_clustered_light_grid_get_tiles_x", self._handle.argument)

    @property
    def tiles_y(self) -> int:
        """How many tiles the grid has down the screen."""
        return _support.out_i32("cna_clustered_light_grid_get_tiles_y", self._handle.argument)

    @property
    def slice_count(self) -> int:
        """How many depth slices the grid has."""
        return _support.out_i32("cna_clustered_light_grid_get_slice_count",
                                self._handle.argument)

    @property
    def cluster_count(self) -> int:
        """How many clusters the grid holds in total."""
        return _support.out_i32("cna_clustered_light_grid_get_cluster_count",
                                self._handle.argument)

    def cluster_index(self, x: int, y: int, slice_: int) -> int:
        """The flat index of one cluster, as the assignment and shader number them."""
        return _support.out_i32(
            "cna_clustered_light_grid_cluster_index", self._handle.argument,
            c.c_int32(_support.checked(x, "int32", "x")),
            c.c_int32(_support.checked(y, "int32", "y")),
            c.c_int32(_support.checked(slice_, "int32", "slice_")))

    def set_projection(self, projection: Matrix, near_plane: float,
                       far_plane: float) -> None:
        """Gives the grid its shape, and inverts the projection once.

        The inverse is the grid's own from here on; every cluster bound and the
        GPU assigner both use it, so the two never differ in their last bits.
        """
        native = _native_matrix(projection)
        _support.call("cna_clustered_light_grid_set_projection", self._handle.argument,
                      c.byref(native),
                      c.c_float(_support.real(near_plane, "near_plane")),
                      c.c_float(_support.real(far_plane, "far_plane")))

    @property
    def has_projection(self) -> bool:
        """Whether :meth:`set_projection` has been called."""
        return _support.out_bool("cna_clustered_light_grid_has_projection",
                                 self._handle.argument)

    @property
    def near_plane(self) -> float:
        """The near distance the slicing starts at."""
        return _support.out_f32("cna_clustered_light_grid_get_near_plane",
                                self._handle.argument)

    @property
    def far_plane(self) -> float:
        """The far distance the slicing ends at."""
        return _support.out_f32("cna_clustered_light_grid_get_far_plane",
                                self._handle.argument)

    @property
    def inverse_projection(self) -> Matrix:
        """The inverted projection, or the identity before one is set."""
        value = _abi.CNA_Matrix()
        _support.call("cna_clustered_light_grid_get_inverse_projection",
                      self._handle.argument, c.byref(value))
        return Matrix(*(getattr(value, f"m{row}{column}")
                        for row in range(1, 5) for column in range(1, 5)))

    def slice_distance(self, slice_: int) -> float:
        """The view distance where a slice begins.

        Takes ``slice_count`` as well as every index below it, because the last
        slice needs both its own boundary and the far plane; that is one more
        value than there are slices.
        """
        return _support.out_f32(
            "cna_clustered_light_grid_slice_distance", self._handle.argument,
            c.c_int32(_support.checked(slice_, "int32", "slice_")))

    def slice_for_view_distance(self, view_distance: float) -> int:
        """Which slice a point at that distance falls in.

        Clamped at both ends: anything at or in front of the near plane is slice
        zero and anything at or beyond the far plane is the last slice, so a
        light that pokes out of the frustum still lands somewhere.
        """
        return _support.out_i32(
            "cna_clustered_light_grid_slice_for_view_distance", self._handle.argument,
            c.c_float(_support.real(view_distance, "view_distance")))

    def cluster_bounds(self, x: int, y: int, slice_: int) -> BoundingBox:
        """The view-space box of one cluster.

        The corners of the tile are unprojected at the near and far planes and
        interpolated to the slice's two distances, which is right for an
        orthographic projection as well as a perspective one.
        """
        value = _engine.CNA_BoundingBox()
        _support.call("cna_clustered_light_grid_cluster_bounds", self._handle.argument,
                      c.c_int32(_support.checked(x, "int32", "x")),
                      c.c_int32(_support.checked(y, "int32", "y")),
                      c.c_int32(_support.checked(slice_, "int32", "slice_")),
                      c.byref(value))
        return BoundingBox(_vector(value.min), _vector(value.max))


# --- the assignment -----------------------------------------------------------


class ClusteredLightAssignment(_EngineObject):
    """Which lights reached which cluster, as offsets and a packed index list.

    A compressed-row structure: :meth:`offsets` is ``cluster_count + 1`` long
    and ``indices()[offsets[i]:offsets[i + 1]]`` is the list for cluster ``i``.
    :meth:`lights_in_cluster` does that slicing through CNA rather than in
    Python, so a caller can ask for one cluster without copying the whole list.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_light_assignment_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(
            _support.out_handle("cna_clustered_light_assignment_create",
                                _device_handle(device)),
            device)

    def assign(self, grid: ClusteredLightGrid, view: Matrix,
               bounds: Iterable[BoundingSphere]) -> None:
        """Sorts the spheres into the grid's clusters, in view space.

        ``bounds`` is what :meth:`ClusteredLightSet.bounds` produced, and the
        index a sphere has here is the index its light has in the set.
        """
        if not isinstance(grid, ClusteredLightGrid):
            raise TypeError("grid must be a ClusteredLightGrid")
        native_view = _native_matrix(view)
        spheres, count = _sphere_array(bounds)
        _support.call("cna_clustered_light_assignment_assign", self._handle.argument,
                      grid._handle.argument, c.byref(native_view), spheres,
                      c.c_uint64(count))

    def clear(self) -> None:
        """Drops every cluster list."""
        _support.call("cna_clustered_light_assignment_clear", self._handle.argument)

    def adopt(self, light_count: int, offsets: Sequence[int],
              indices: Sequence[int]) -> None:
        """Takes a list built elsewhere, after checking it describes a real grid.

        The GPU path is the first caller: it builds the same structure in a
        compute shader and hands it here. CNA validates -- offsets start at zero
        and never go backwards, the last is the length of ``indices``, and no
        index names a light outside the set -- so a wrong list is refused rather
        than lighting the wrong objects.
        """
        offset_array, offset_count = _int32_array(offsets, "offsets")
        index_array, index_count = _int32_array(indices, "indices")
        _support.call("cna_clustered_light_assignment_adopt", self._handle.argument,
                      c.c_int32(_support.checked(light_count, "int32", "light_count")),
                      offset_array, c.c_uint64(offset_count),
                      index_array, c.c_uint64(index_count))

    @property
    def light_count(self) -> int:
        """How many lights the last assignment sorted."""
        return _support.out_i32("cna_clustered_light_assignment_get_light_count",
                                self._handle.argument)

    @property
    def cluster_count(self) -> int:
        """How many clusters it sorted them into."""
        return _support.out_i32("cna_clustered_light_assignment_get_cluster_count",
                                self._handle.argument)

    @property
    def total_reference_count(self) -> int:
        """How many (cluster, light) pairs there are in total."""
        return _support.out_i32(
            "cna_clustered_light_assignment_get_total_reference_count",
            self._handle.argument)

    @property
    def max_lights_per_cluster(self) -> int:
        """The busiest cluster's light count -- what the shader's loop costs."""
        return _support.out_i32(
            "cna_clustered_light_assignment_get_max_lights_per_cluster",
            self._handle.argument)

    def lights_in_cluster(self, cluster_index: int) -> tuple[int, ...]:
        """The light indices in one cluster, in the order they were added."""
        values, written = _support.copied_values(
            c.c_int32, "cna_clustered_light_assignment_copy_lights_in_cluster",
            (self._handle.argument,
             c.c_int32(_support.checked(cluster_index, "int32", "cluster_index"))))
        return tuple(int(values[index]) for index in range(written))

    def indices(self) -> tuple[int, ...]:
        """The packed index list, every cluster's lights end to end."""
        values, written = _support.copied_values(
            c.c_int32, "cna_clustered_light_assignment_copy_indices",
            (self._handle.argument,))
        return tuple(int(values[index]) for index in range(written))

    def offsets(self) -> tuple[int, ...]:
        """Where each cluster's slice of :meth:`indices` begins, and where the last ends."""
        values, written = _support.copied_values(
            c.c_int32, "cna_clustered_light_assignment_copy_offsets",
            (self._handle.argument,))
        return tuple(int(values[index]) for index in range(written))


class ClusteredLightCompute(_EngineObject):
    """The same assignment, computed on the GPU when the renderer has compute.

    Falls back to the CPU rather than failing: a renderer with no compute
    shaders, or one that refuses this particular program, still gets a correct
    assignment and reports why through :attr:`unsupported_reason`. Read
    :attr:`used_compute` after :meth:`assign` to find out which path ran.

    ``stride`` is the per-cluster capacity the shader writes into. A cluster
    that wants more lights than that keeps the first ``stride`` of them and sets
    :attr:`has_overflowed`; nothing is silently dropped without saying so.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_light_compute_destroy"

    def __init__(self, device: "GraphicsDevice",
                 stride: int = CLUSTERED_COMPUTE_DEFAULT_STRIDE) -> None:
        self._attach(
            _support.out_handle(
                "cna_clustered_light_compute_create", _device_handle(device),
                c.c_int32(_support.checked(stride, "int32", "stride"))),
            device)

    @property
    def is_supported(self) -> bool:
        """Whether the GPU path is available at all."""
        return _support.out_bool("cna_clustered_light_compute_is_supported",
                                 self._handle.argument)

    @property
    def unsupported_reason(self) -> str:
        """Why the GPU path is unavailable, or the empty string when it is not."""
        return _support.copied_text("cna_clustered_light_compute_copy_unsupported_reason",
                                    (self._handle.argument,), "the unsupported reason")

    @property
    def stride(self) -> int:
        """How many lights one cluster may hold on the GPU path."""
        return _support.out_i32("cna_clustered_light_compute_get_stride",
                                self._handle.argument)

    def assign(self, grid: ClusteredLightGrid, view: Matrix,
               bounds: Iterable[BoundingSphere],
               assignment: ClusteredLightAssignment) -> None:
        """Fills ``assignment`` with the same lists :meth:`ClusteredLightAssignment.assign` would.

        Deliberately the same answer, not merely a similar one: the shader
        visits lights in order, no two invocations write to the same place, and
        it is handed the grid's own inverse projection rather than a fresh
        inversion of the same matrix. The two paths can therefore be compared
        for equality, which is how either one is known to be right.
        """
        if not isinstance(grid, ClusteredLightGrid):
            raise TypeError("grid must be a ClusteredLightGrid")
        if not isinstance(assignment, ClusteredLightAssignment):
            raise TypeError("assignment must be a ClusteredLightAssignment")
        native_view = _native_matrix(view)
        spheres, count = _sphere_array(bounds)
        _support.call("cna_clustered_light_compute_assign", self._handle.argument,
                      grid._handle.argument, c.byref(native_view), spheres,
                      c.c_uint64(count), assignment._handle.argument)

    @property
    def used_compute(self) -> bool:
        """Whether the last :meth:`assign` ran on the GPU."""
        return _support.out_bool("cna_clustered_light_compute_used_compute",
                                 self._handle.argument)

    @property
    def has_overflowed(self) -> bool:
        """Whether the last :meth:`assign` had to drop lights from a cluster."""
        return _support.out_bool("cna_clustered_light_compute_has_overflowed",
                                 self._handle.argument)


# --- what the shader reads ----------------------------------------------------


class ClusteredLightBuffer(_EngineObject):
    """The set, the grid and the assignment, uploaded as textures a shader walks.

    :meth:`upload` refuses a mismatched trio -- an assignment whose light count
    is not the set's, or whose cluster count is not the grid's -- because its
    indices are positions in exactly those two, and uploading a mismatch would
    light the wrong objects with the wrong lamps rather than fail.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_light_buffer_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(
            _support.out_handle("cna_clustered_light_buffer_create",
                                _device_handle(device)),
            device)

    def upload(self, lights: ClusteredLightSet, grid: ClusteredLightGrid,
               assignment: ClusteredLightAssignment) -> None:
        """Packs all three into textures. The three must describe each other."""
        if not isinstance(lights, ClusteredLightSet):
            raise TypeError("lights must be a ClusteredLightSet")
        if not isinstance(grid, ClusteredLightGrid):
            raise TypeError("grid must be a ClusteredLightGrid")
        if not isinstance(assignment, ClusteredLightAssignment):
            raise TypeError("assignment must be a ClusteredLightAssignment")
        _support.call("cna_clustered_light_buffer_upload", self._handle.argument,
                      lights._handle.argument, grid._handle.argument,
                      assignment._handle.argument)

    def bind(self, effect: "Effect", first_unit: int) -> None:
        """Binds the three textures and the grid uniforms to a caller's shader.

        Three consecutive texture units from ``first_unit``, named as
        :func:`light_lookup_glsl` declares them. For a shader written against
        that GLSL; :class:`ClusteredForwardEffect` binds its own.

        The effect must be one compiled from **source** -- what
        ``ShaderEffectFactory.acquire`` returns, or
        :attr:`ClusteredForwardEffect.shader`. An ``Effect`` built from XNA
        bytecode has no uniforms to set by name and is refused rather than
        silently binding nothing.
        """
        if not hasattr(effect, "_require_handle"):
            raise TypeError("effect must be a Microsoft.Xna.Framework.Graphics.Effect")
        _support.call("cna_clustered_light_buffer_bind", self._handle.argument,
                      c.c_uint64(int(effect._require_handle())),
                      c.c_int32(_support.checked(first_unit, "int32", "first_unit")))

    @property
    def is_uploaded(self) -> bool:
        """Whether anything has been uploaded yet."""
        return _support.out_bool("cna_clustered_light_buffer_is_uploaded",
                                 self._handle.argument)

    @property
    def light_count(self) -> int:
        """How many lights the last upload carried."""
        return _support.out_i32("cna_clustered_light_buffer_get_light_count",
                                self._handle.argument)

    @property
    def cluster_count(self) -> int:
        """How many clusters the last upload carried."""
        return _support.out_i32("cna_clustered_light_buffer_get_cluster_count",
                                self._handle.argument)

    @property
    def reference_count(self) -> int:
        """How many (cluster, light) pairs the last upload carried."""
        return _support.out_i32("cna_clustered_light_buffer_get_reference_count",
                                self._handle.argument)


def light_lookup_glsl() -> str:
    """CNA's own GLSL for reading a clustered light buffer.

    Published so a caller writing their own shader walks the same cluster table
    CNA packed, rather than reimplementing the layout from its description.
    """
    return _support.copied_text("cna_clustered_light_buffer_copy_light_lookup_glsl",
                                (), "the clustered light lookup GLSL")


# --- the shadow budget --------------------------------------------------------


class ClusteredShadowPolicy(_EngineObject):
    """Which of many lights can afford a shadow map, inside a fixed budget.

    Ranks by what the picture would notice: Rec. 709 luminance times intensity
    times the same windowed falloff the forward effect shades with, so the
    ranking and the image agree about which light is brightest. A light outside
    the view frustum scores zero rather than being removed, so :meth:`score` can
    still say why it lost.

    :attr:`hysteresis` multiplies an incumbent's score, which is what stops two
    lights of nearly equal weight trading the shadow map every frame. It is
    applied as a bonus rather than as a rule in the comparison, because "unless
    the challenger beats it by X" is not transitive and a sort given an
    intransitive comparison may do anything at all.

    Both setters *ignore* a value outside their range instead of refusing it: a
    negative budget and a hysteresis below one leave the old value in place, so
    read the property back to see what was kept.
    """

    __slots__ = ()
    _DESTROY = "cna_clustered_shadow_policy_destroy"

    def __init__(self, device: "GraphicsDevice",
                 budget: int = CLUSTERED_SHADOW_DEFAULT_BUDGET) -> None:
        self._attach(
            _support.out_handle(
                "cna_clustered_shadow_policy_create", _device_handle(device),
                c.c_int32(_support.checked(budget, "int32", "budget"))),
            device)

    @property
    def budget(self) -> int:
        """How many lights may cast a shadow at once. Zero means none."""
        return _support.out_i32("cna_clustered_shadow_policy_get_budget",
                                self._handle.argument)

    @budget.setter
    def budget(self, value: int) -> None:
        _support.call("cna_clustered_shadow_policy_set_budget", self._handle.argument,
                      c.c_int32(_support.checked(value, "int32", "budget")))

    @property
    def hysteresis(self) -> float:
        """How much an incumbent's score is multiplied by. Never below one."""
        return _support.out_f32("cna_clustered_shadow_policy_get_hysteresis",
                                self._handle.argument)

    @hysteresis.setter
    def hysteresis(self, value: float) -> None:
        _support.call("cna_clustered_shadow_policy_set_hysteresis", self._handle.argument,
                      c.c_float(_support.real(value, "hysteresis")))

    def select(self, lights: ClusteredLightSet, view: Matrix, projection: Matrix,
               camera_position: Vector3) -> None:
        """Scores every shadow-casting light and grants the budget to the best."""
        if not isinstance(lights, ClusteredLightSet):
            raise TypeError("lights must be a ClusteredLightSet")
        native_view = _native_matrix(view)
        native_projection = _native_matrix(projection)
        native_camera = _native_vector(camera_position)
        _support.call("cna_clustered_shadow_policy_select", self._handle.argument,
                      lights._handle.argument, c.byref(native_view),
                      c.byref(native_projection), c.byref(native_camera))

    def selected(self) -> tuple[int, ...]:
        """The light indices that got a shadow map, best first."""
        values, written = _support.copied_values(
            c.c_int32, "cna_clustered_shadow_policy_copy_selected",
            (self._handle.argument,))
        return tuple(int(values[index]) for index in range(written))

    def is_selected(self, light_index: int) -> bool:
        """Whether one light got a shadow map in the last selection."""
        return _support.out_bool(
            "cna_clustered_shadow_policy_is_selected", self._handle.argument,
            c.c_int32(_support.checked(light_index, "int32", "light_index")))

    def score(self, light_index: int) -> float:
        """What one light scored, including the zero a light outside the view gets."""
        return _support.out_f32(
            "cna_clustered_shadow_policy_get_score", self._handle.argument,
            c.c_int32(_support.checked(light_index, "int32", "light_index")))

    @property
    def request_count(self) -> int:
        """How many lights asked for a shadow map in the last selection."""
        return _support.out_i32("cna_clustered_shadow_policy_get_request_count",
                                self._handle.argument)

    @property
    def refused_count(self) -> int:
        """How many of them did not get one."""
        return _support.out_i32("cna_clustered_shadow_policy_get_refused_count",
                                self._handle.argument)

    def reset(self) -> None:
        """Forgets the last selection, so no light is an incumbent."""
        _support.call("cna_clustered_shadow_policy_reset", self._handle.argument)


# --- the forward effect -------------------------------------------------------


class ClusteredForwardEffect(_EngineObject):
    """CNA's own shader for drawing with a clustered light buffer.

    A physically based material -- base colour, metallic, roughness, index of
    refraction, ambient -- shaded against every light in the fragment's own
    cluster, optionally with a :class:`PbrMaterialExtensions` for clearcoat,
    sheen, transmission and the rest, and optionally with one area light.

    **Every setter clamps or ignores rather than refusing**, and the bounds are
    not the same shape in each case, so read a property back to see what was
    kept: ``base_color`` and ``metallic`` clamp to ``0..1``, ``roughness``
    clamps to ``0.04..1`` (a perfectly smooth microfacet distribution divides by
    zero and shows as one blown-out pixel), ``ambient`` floors each channel at
    zero, and ``ior`` *ignores* anything below one, because below one a surface
    refracts the wrong way and the vacuum is the floor of what a material can
    be rather than a value to interpolate through.
    """

    __slots__ = ("_opaque_frame", "_brdf_table")
    _DESTROY = "cna_clustered_forward_effect_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(
            _support.out_handle("cna_clustered_forward_effect_create",
                                _device_handle(device)),
            device)
        #: The caller's own objects, so reading a property back returns what was
        #: set rather than a second facade over a borrowed handle.
        self._opaque_frame: object = None
        self._brdf_table: AreaLightBrdfTable | None = None

    @property
    def is_supported(self) -> bool:
        """Whether the renderer compiled and can execute the shader."""
        return _support.out_bool("cna_clustered_forward_effect_is_supported",
                                 self._handle.argument)

    @property
    def shader(self) -> "Effect | None":
        """The underlying effect, as one counted borrow.

        ``engine_layer.h`` says the handle is borrowed from the effect. Measured
        on CNA 0.21.0 it is a fresh counted view on every call, like every other
        engine getter that answers with a handle (ENGINE-002), so it is taken
        once, cached, and disposed when this object closes. ``None`` when the
        renderer could not build a shader at all.
        """
        return self._effect_view("shader", "cna_clustered_forward_effect_get_effect")

    def begin(self, world: Matrix, view: Matrix, projection: Matrix,
              camera_position: Vector3, lights: ClusteredLightBuffer) -> None:
        """Applies the shader and sets every uniform for one draw.

        Refuses a light buffer that holds nothing: there would be no cluster
        table for the shader to walk.
        """
        if not isinstance(lights, ClusteredLightBuffer):
            raise TypeError("lights must be a ClusteredLightBuffer")
        native_world = _native_matrix(world)
        native_view = _native_matrix(view)
        native_projection = _native_matrix(projection)
        native_camera = _native_vector(camera_position)
        _support.call("cna_clustered_forward_effect_begin", self._handle.argument,
                      c.byref(native_world), c.byref(native_view),
                      c.byref(native_projection), c.byref(native_camera),
                      lights._handle.argument)

    @property
    def base_color(self) -> Vector3:
        """The material's albedo. Clamped to ``0..1`` per channel."""
        value = _abi.CNA_Vector3()
        _support.call("cna_clustered_forward_effect_get_base_color",
                      self._handle.argument, c.byref(value))
        return _vector(value)

    @base_color.setter
    def base_color(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call("cna_clustered_forward_effect_set_base_color",
                      self._handle.argument, c.byref(native))

    @property
    def metallic(self) -> float:
        """How metallic the surface is. Clamped to ``0..1``."""
        return _support.out_f32("cna_clustered_forward_effect_get_metallic",
                                self._handle.argument)

    @metallic.setter
    def metallic(self, value: float) -> None:
        _support.call("cna_clustered_forward_effect_set_metallic", self._handle.argument,
                      c.c_float(_support.real(value, "metallic")))

    @property
    def roughness(self) -> float:
        """How rough the surface is. Clamped to ``0.04..1``, never to zero."""
        return _support.out_f32("cna_clustered_forward_effect_get_roughness",
                                self._handle.argument)

    @roughness.setter
    def roughness(self, value: float) -> None:
        _support.call("cna_clustered_forward_effect_set_roughness", self._handle.argument,
                      c.c_float(_support.real(value, "roughness")))

    @property
    def ior(self) -> float:
        """The index of refraction. A value below one is ignored, not refused."""
        return _support.out_f32("cna_clustered_forward_effect_get_ior",
                                self._handle.argument)

    @ior.setter
    def ior(self, value: float) -> None:
        _support.call("cna_clustered_forward_effect_set_ior", self._handle.argument,
                      c.c_float(_support.real(value, "ior")))

    @property
    def ambient(self) -> Vector3:
        """Light arriving from everywhere. Each channel floors at zero."""
        value = _abi.CNA_Vector3()
        _support.call("cna_clustered_forward_effect_get_ambient",
                      self._handle.argument, c.byref(value))
        return _vector(value)

    @ambient.setter
    def ambient(self, value: Vector3) -> None:
        native = _native_vector(value)
        _support.call("cna_clustered_forward_effect_set_ambient",
                      self._handle.argument, c.byref(native))

    @property
    def opaque_frame(self) -> "Texture2D | None":
        """What a transmissive material refracts against, or ``None``.

        CNA is asked whether one is bound, and the object handed back is the
        caller's own; the view CNA answers with is released immediately, for the
        reason in ENGINE-002.
        """
        expected = (0 if self._opaque_frame is None
                    else int(self._opaque_frame._require_handle()))
        present = _support.borrowed_view("cna_clustered_forward_effect_get_opaque_frame",
                                         (self._handle.argument,), expected,
                                         "cna_texture2d_destroy")
        return self._opaque_frame if present else None

    @opaque_frame.setter
    def opaque_frame(self, value: "Texture2D | None") -> None:
        if value is None:
            handle = 0
        elif hasattr(value, "_require_handle"):
            handle = int(value._require_handle())
        else:
            raise TypeError("opaque_frame must be a Texture2D or None")
        _support.call("cna_clustered_forward_effect_set_opaque_frame",
                      self._handle.argument, c.c_uint64(handle))
        self._opaque_frame = value

    @property
    def material_extensions(self) -> PbrMaterialExtensions:
        """The clearcoat, sheen, transmission and iridescence terms.

        A counted view over the effect's *own* extensions, taken once and
        disposed when this object closes. The effect always has a set: before
        one is assigned it answers with a neutral one rather than with nothing.
        """
        return self._view(
            "material_extensions",
            "cna_clustered_forward_effect_get_material_extensions",
            lambda handle: PbrMaterialExtensions._wrap(_support.NativeHandle(
                handle, "cna_pbr_material_extensions_destroy",
                "PBR material extensions")))

    @material_extensions.setter
    def material_extensions(self, value: PbrMaterialExtensions) -> None:
        if not isinstance(value, PbrMaterialExtensions):
            raise TypeError("material_extensions must be a PbrMaterialExtensions")
        _support.call("cna_clustered_forward_effect_set_material_extensions",
                      self._handle.argument, value._handle.argument)
        # CNA *copies* the caller's values into a new object of its own, so any
        # view already handed out looks at the set that has just been replaced.
        # Dropping it here is what makes reading the property back answer with
        # what was assigned rather than with the old neutral set.
        self._drop_view("material_extensions")

    @property
    def has_area_light(self) -> bool:
        """Whether an area light is set."""
        return _support.out_bool("cna_clustered_forward_effect_has_area_light",
                                 self._handle.argument)

    def set_area_light(self, light: AreaLight, table: "AreaLightBrdfTable") -> None:
        """Gives the effect one area light, shaded through ``table``.

        An invalid light *clears* the area light rather than being refused, so
        check :attr:`AreaLight.is_valid` first if the values came from data, or
        read :attr:`has_area_light` afterwards.
        """
        if not isinstance(light, AreaLight):
            raise TypeError("light must be an AreaLight")
        if not isinstance(table, AreaLightBrdfTable):
            raise TypeError("table must be an AreaLightBrdfTable")
        native = light._native()
        _support.call("cna_clustered_forward_effect_set_area_light", self._handle.argument,
                      c.byref(native), table._handle.argument)
        # CNA keeps a bare pointer to the table, so the effect must keep the
        # Python object alive for as long as it can be shaded with.
        self._brdf_table = table

    def clear_area_light(self) -> None:
        """Drops the area light and the table it was shaded through."""
        _support.call("cna_clustered_forward_effect_clear_area_light",
                      self._handle.argument)
        self._brdf_table = None

    @property
    def has_light_probe(self) -> bool:
        """Whether a light probe or probe volume is set."""
        return _support.out_bool("cna_clustered_forward_effect_has_light_probe",
                                 self._handle.argument)

    def clear_light_probe(self) -> None:
        """Drops the light probe and the probe volume."""
        _support.call("cna_clustered_forward_effect_clear_light_probe",
                      self._handle.argument)

    def close(self) -> None:
        self._brdf_table = None
        self._opaque_frame = None
        super().close()


def volume_attenuation(attenuation_color: Vector3, attenuation_distance: float,
                       thickness: float) -> Vector3:
    """How much light survives ``thickness`` of a coloured medium.

    Beer-Lambert: ``attenuation_color`` is what one ``attenuation_distance`` of
    the medium leaves, so the answer is that colour raised to
    ``thickness / attenuation_distance``. A non-positive distance or thickness
    means no medium at all and gives back white.
    """
    native = _native_vector(attenuation_color)
    result = _abi.CNA_Vector3()
    _support.call("cna_clustered_forward_effect_volume_attenuation", c.byref(native),
                  c.c_float(_support.real(attenuation_distance, "attenuation_distance")),
                  c.c_float(_support.real(thickness, "thickness")), c.byref(result))
    return _vector(result)


def light_contribution(light: ClusteredLight, surface: Vector3, normal: Vector3,
                       camera_position: Vector3, base_color: Vector3,
                       metallic: float, roughness: float, *,
                       extensions: PbrMaterialExtensions | None = None,
                       clearcoat: float = 0.0, clearcoat_roughness: float = 0.0,
                       sheen_color: Vector3 | None = None,
                       sheen_roughness: float = 0.0, iridescence: float = 0.0,
                       iridescence_ior: float = 0.0,
                       iridescence_thickness: float = 0.0,
                       subsurface_color: Vector3 | None = None,
                       subsurface_wrap: float = 0.0) -> Vector3:
    """What one clustered light contributes at one point, on the CPU.

    The same arithmetic the shader runs, exposed so a caller writing their own
    shader can check it against something other than a screenshot.

    Pass ``extensions`` to shade through a :class:`PbrMaterialExtensions`, which
    is CNA's own second route and takes the extended terms from the object
    instead of from the keyword arguments; the two are exclusive, and passing
    both is refused rather than silently preferring one.
    """
    if not isinstance(light, ClusteredLight):
        raise TypeError("light must be a ClusteredLight")
    extended = (clearcoat, clearcoat_roughness, sheen_roughness, iridescence,
                iridescence_ior, iridescence_thickness, subsurface_wrap)
    if extensions is not None and (sheen_color is not None or subsurface_color is not None
                                   or any(value != 0.0 for value in extended)):
        raise TypeError(
            "pass either extensions or the individual extended terms, not both")
    native_light = light._native()
    native_surface = _native_vector(surface)
    native_normal = _native_vector(normal)
    native_camera = _native_vector(camera_position)
    native_base = _native_vector(base_color)
    result = _abi.CNA_Vector3()
    if extensions is not None:
        if not isinstance(extensions, PbrMaterialExtensions):
            raise TypeError("extensions must be a PbrMaterialExtensions")
        _support.call("cna_clustered_forward_effect_contribution_with_extensions",
                      c.byref(native_light), c.byref(native_surface),
                      c.byref(native_normal), c.byref(native_camera),
                      c.byref(native_base),
                      c.c_float(_support.real(metallic, "metallic")),
                      c.c_float(_support.real(roughness, "roughness")),
                      extensions._handle.argument, c.byref(result))
        return _vector(result)
    native_sheen = _native_vector(sheen_color if sheen_color is not None
                                  else Vector3(0.0, 0.0, 0.0))
    native_subsurface = _native_vector(subsurface_color if subsurface_color is not None
                                       else Vector3(0.0, 0.0, 0.0))
    _support.call("cna_clustered_forward_effect_contribution",
                  c.byref(native_light), c.byref(native_surface), c.byref(native_normal),
                  c.byref(native_camera), c.byref(native_base),
                  c.c_float(_support.real(metallic, "metallic")),
                  c.c_float(_support.real(roughness, "roughness")),
                  c.c_float(_support.real(clearcoat, "clearcoat")),
                  c.c_float(_support.real(clearcoat_roughness, "clearcoat_roughness")),
                  c.byref(native_sheen),
                  c.c_float(_support.real(sheen_roughness, "sheen_roughness")),
                  c.c_float(_support.real(iridescence, "iridescence")),
                  c.c_float(_support.real(iridescence_ior, "iridescence_ior")),
                  c.c_float(_support.real(iridescence_thickness, "iridescence_thickness")),
                  c.byref(native_subsurface),
                  c.c_float(_support.real(subsurface_wrap, "subsurface_wrap")),
                  c.byref(result))
    return _vector(result)


# --- area lights --------------------------------------------------------------


class AreaLightBrdfTerms:
    """What the BRDF integrates to for one roughness and one viewing angle.

    ``magnitude`` is the energy the lobe carries and ``fresnel`` the part of it
    that grazing angles add. ``average_tangent`` and ``average_normal`` are the
    two components of the lobe's average reflection direction, in a frame whose
    normal is the surface normal and whose tangent points along the reflection
    side; for an isotropic BRDF the third component is zero, so two numbers say
    where the lobe points.
    """

    __slots__ = ("magnitude", "fresnel", "average_tangent", "average_normal")

    def __init__(self, magnitude: float, fresnel: float, average_tangent: float,
                 average_normal: float) -> None:
        self.magnitude = magnitude
        self.fresnel = fresnel
        self.average_tangent = average_tangent
        self.average_normal = average_normal

    def __repr__(self) -> str:
        return (f"AreaLightBrdfTerms(magnitude={self.magnitude!r}, "
                f"fresnel={self.fresnel!r}, average_tangent={self.average_tangent!r}, "
                f"average_normal={self.average_normal!r})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AreaLightBrdfTerms):
            return NotImplemented
        return (self.magnitude == other.magnitude and self.fresnel == other.fresnel
                and self.average_tangent == other.average_tangent
                and self.average_normal == other.average_normal)


class AreaLightBrdfTable(_EngineObject):
    """A precomputed texture of :func:`evaluate_brdf`, for the GPU to sample.

    Building it integrates ``size * size`` texels of ``sample_count`` samples
    each, which is why :attr:`generation_milliseconds` exists: it is the one
    engine object whose construction cost is worth knowing.
    """

    __slots__ = ()
    _DESTROY = "cna_area_light_brdf_table_destroy"

    def __init__(self, device: "GraphicsDevice", size: int | None = None,
                 sample_count: int | None = None) -> None:
        if (size is None) != (sample_count is None):
            raise TypeError("give both size and sample_count, or neither")
        if size is None:
            handle = _support.out_handle("cna_area_light_brdf_table_create",
                                         _device_handle(device))
        else:
            handle = _support.out_handle(
                "cna_area_light_brdf_table_create_with_size", _device_handle(device),
                c.c_int32(_support.checked(size, "int32", "size")),
                c.c_int32(_support.checked(sample_count, "int32", "sample_count")))
        self._attach(handle, device)

    @property
    def texture(self) -> "Texture2D | None":
        """The table as a texture, as one counted borrow.

        ``engine_layer.h`` says the handle keeps the table alive and that
        releasing it releases only the handle. Measured, it is a fresh view per
        call like every other engine getter (ENGINE-002), so it is taken once,
        cached, and disposed when the table closes. ``None`` when the renderer
        could not build the texture.
        """
        return self._texture_view("texture", "cna_area_light_brdf_table_get_texture")

    def _texture_view(self, key: str, route: str):
        from Microsoft.Xna.Framework.Graphics import Texture2D

        return self._view(key, route,
                          lambda handle: Texture2D._view_of(self._device, handle))

    @property
    def size(self) -> int:
        """The table's edge length in texels."""
        return _support.out_i32("cna_area_light_brdf_table_get_size",
                                self._handle.argument)

    @property
    def sample_count(self) -> int:
        """How many samples each texel integrated."""
        return _support.out_i32("cna_area_light_brdf_table_get_sample_count",
                                self._handle.argument)

    @property
    def generation_milliseconds(self) -> float:
        """How long building the table took."""
        return _support.out_f64("cna_area_light_brdf_table_get_generation_milliseconds",
                                self._handle.argument)


def evaluate_brdf(roughness: float, cos_theta: float,
                  sample_count: int = AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT
                  ) -> AreaLightBrdfTerms:
    """Integrates the GGX BRDF for one roughness and one viewing angle.

    A Monte Carlo integral over ``sample_count`` importance-sampled directions,
    so a larger count is a closer answer rather than a different one. Needs no
    table and no device: :class:`AreaLightBrdfTable` is this function baked into
    a texture, not a different calculation.
    """
    terms = _support.out_struct(
        _engine.CNA_AreaLightBrdfTerms, 1, "cna_area_light_brdf_table_evaluate",
        c.c_float(_support.real(roughness, "roughness")),
        c.c_float(_support.real(cos_theta, "cos_theta")),
        c.c_int32(_support.checked(sample_count, "int32", "sample_count")))
    return AreaLightBrdfTerms(float(terms.magnitude), float(terms.fresnel),
                              float(terms.average_tangent), float(terms.average_normal))


def brdf_lookup_glsl() -> str:
    """CNA's own GLSL for sampling an :class:`AreaLightBrdfTable`."""
    return _support.copied_text("cna_area_light_brdf_table_copy_lookup_glsl",
                                (), "the BRDF lookup GLSL")


def lobe_scale_for(roughness: float) -> float:
    """The width of the specular lobe a roughness implies.

    The GGX alpha, floored so that a mirror still has a lobe with a width rather
    than a line.
    """
    return _support.out_f32("cna_area_light_shading_lobe_scale_for",
                            c.c_float(_support.real(roughness, "roughness")))


def area_light_quad(light: AreaLight,
                    surface: Vector3) -> tuple[Vector3, Vector3, Vector3, Vector3]:
    """The four corners the light is integrated as, counter-clockwise from lower left.

    Shape-dependent, and that is the point: a rectangle uses its axes as they
    are, a disc scales them by ``sqrt(pi) / 2`` so the polygon encloses the
    disc's area rather than the rectangle's, and a tube is *billboarded* --
    turned so its face points at ``surface``, because a cylinder looks like a
    rectangle from wherever it is seen. Only a tube's quad depends on
    ``surface``.
    """
    if not isinstance(light, AreaLight):
        raise TypeError("light must be an AreaLight")
    native_light = light._native()
    native_surface = _native_vector(surface)
    corners = (_abi.CNA_Vector3 * AREA_LIGHT_QUAD_CORNER_COUNT)()
    _support.call("cna_area_light_shading_quad_of", c.byref(native_light),
                  c.byref(native_surface), corners)
    return tuple(_vector(corner) for corner in corners)


def area_light_coverage(quad: Sequence[Vector3], surface: Vector3, lobe_axis: Vector3,
                        lobe_scale: float, two_sided: bool) -> float:
    """How much of a shading lobe the quad covers, from zero to one.

    The quad is taken into the lobe's own frame, widened by the inverse of
    ``lobe_scale`` -- a narrow lobe sees the light as bigger than it is, which
    is the same statement as it being tighter -- clipped to the visible
    hemisphere, and integrated edge by edge. Zero when the quad is behind the
    surface.
    """
    corners = tuple(quad)
    if len(corners) != AREA_LIGHT_QUAD_CORNER_COUNT:
        raise ValueError(
            f"quad must hold {AREA_LIGHT_QUAD_CORNER_COUNT} corners, got {len(corners)}")
    if not isinstance(two_sided, bool):
        raise TypeError("two_sided must be a bool")
    native_quad = (_abi.CNA_Vector3 * AREA_LIGHT_QUAD_CORNER_COUNT)(
        *(_native_vector(corner) for corner in corners))
    native_surface = _native_vector(surface)
    native_axis = _native_vector(lobe_axis)
    return _support.out_f32(
        "cna_area_light_shading_coverage", native_quad, c.byref(native_surface),
        c.byref(native_axis), c.c_float(_support.real(lobe_scale, "lobe_scale")),
        c.c_uint8(1 if two_sided else 0))


def area_light_contribution(light: AreaLight, surface: Vector3, normal: Vector3,
                            camera_position: Vector3, base_color: Vector3,
                            metallic: float, roughness: float) -> Vector3:
    """What one area light contributes at one point, on the CPU.

    Zero for an invalid light, and zero beyond the light's range.
    """
    if not isinstance(light, AreaLight):
        raise TypeError("light must be an AreaLight")
    native_light = light._native()
    native_surface = _native_vector(surface)
    native_normal = _native_vector(normal)
    native_camera = _native_vector(camera_position)
    native_base = _native_vector(base_color)
    result = _abi.CNA_Vector3()
    _support.call("cna_area_light_shading_contribution", c.byref(native_light),
                  c.byref(native_surface), c.byref(native_normal),
                  c.byref(native_camera), c.byref(native_base),
                  c.c_float(_support.real(metallic, "metallic")),
                  c.c_float(_support.real(roughness, "roughness")), c.byref(result))
    return _vector(result)


def area_light_shading_glsl() -> str:
    """CNA's own GLSL for shading an area light, matching :func:`area_light_contribution`."""
    return _support.copied_text("cna_area_light_shading_copy_shading_glsl",
                                (), "the area light shading GLSL")
