"""Deciding what to draw, and drawing many of one thing at once.

Four ideas that share a frame's budget:

* :class:`LodGroup` -- several versions of one mesh, and the rule for choosing
  between them by distance or by how many pixels the object covers.
* :class:`FrustumCuller` -- the six-plane test, over one bound or a whole array.
* :class:`InstancedRenderer` -- one mesh drawn many times in one call, with a
  per-instance transform and an optional per-instance tint, falling back to a
  draw per instance where the renderer has no instancing.
* :class:`GpuInstanceCuller` -- the culling itself moved to the GPU, which then
  writes the draw arguments the GPU reads back: nothing crosses to the CPU at
  all. :func:`draw_primitives_indirect` and its indexed sibling are the draws
  that read them.

Mesh parts, and the one thing this module borrows
-------------------------------------------------

``cna_lod_group_ext_add_level`` and ``cna_instanced_renderer_ext_create`` take a
native mesh-part handle, and strict XNA's ``ModelMeshPart`` is a managed object
with no native handle at all -- CNA's native model runtime is a separate concept
that CNA-Python deliberately does not bind. Exactly two ``models.h`` routes are
therefore imported, ``cna_model_mesh_part_create`` and its destroy, to project a
strict part into the handle those routes demand. That projection is private and
owned by whatever needed it: no native model, mesh or part is ever public here,
and every method takes and returns the caller's own
``Microsoft.Xna.Framework.Graphics.ModelMeshPart``.

What needs a renderer
---------------------

A LOD group and a frustum culler are arithmetic: no device, and they work on
either qualified artifact. The instanced renderer and the GPU culler need a
device, and the GPU culler additionally needs compute shaders, indirect draw, a
storage buffer readable from a vertex shader, and a renderer that actually
executes effect source -- it says which of those is missing rather than only
that something is.
"""

from __future__ import annotations

import ctypes as c
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Iterable, Sequence

from Microsoft.Xna.Framework import BoundingBox, BoundingSphere, Color, Matrix, Vector3

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import _EngineObject, _device_handle, _matrix, _native_matrix, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import (
        Effect, GraphicsDevice, ModelMeshPart, PrimitiveType, VertexElement,
    )

__all__ = [
    "LodSelectionMode",
    "LodLevel",
    "LodGroup",
    "FrustumCuller",
    "InstancedRenderer",
    "GpuCullableInstance",
    "GpuInstanceCuller",
    "IndirectDrawArguments",
    "IndirectDrawIndexedArguments",
    "instance_vertex_elements",
    "instance_vertex_stride",
    "tint_vertex_elements",
    "tint_vertex_stride",
    "instance_lookup_glsl",
    "draw_primitives_indirect",
    "draw_indexed_primitives_indirect",
    "GPU_INSTANCE_STORAGE_BINDING",
]

#: The storage-buffer binding a GPU-culled draw reads its instance list from.
GPU_INSTANCE_STORAGE_BINDING = _engine.CNA_GPU_INSTANCE_BINDING


class LodSelectionMode(IntEnum):
    """What a level's threshold is measured in.

    ``Distance`` compares world units and ``ScreenSpaceError`` compares the
    projected radius in pixels, which needs
    :meth:`LodGroup.set_screen_space_parameters` first. Index zero is the finest
    level in *both*, which is why changing the mode re-sorts the levels.
    """

    Distance = _engine.CNA_LOD_SELECTION_MODE_DISTANCE
    ScreenSpaceError = _engine.CNA_LOD_SELECTION_MODE_SCREEN_SPACE_ERROR


@dataclass(frozen=True)
class LodLevel:
    """One level of detail: its threshold and the mesh part that draws it."""

    max_distance: float
    part: object


def _mesh_part_handle(part: "ModelMeshPart", what: str) -> int:
    """Projects a strict-XNA mesh part into the native handle CNA asks for.

    Private, and the whole of the ``models.h`` dependency. The native part
    retains the *same* vertex and index buffers the strict part holds, so it
    describes the same geometry rather than a copy of it; the caller keeps
    owning the buffers, and the handle returned here is owned by whatever
    imported it.
    """
    from Microsoft.Xna.Framework.Graphics import ModelMeshPart

    if not isinstance(part, ModelMeshPart):
        raise TypeError(f"{what} must be a Microsoft.Xna.Framework.Graphics.ModelMeshPart")
    vertex_buffer = part.VertexBuffer
    index_buffer = part.IndexBuffer
    return _support.out_handle(
        "cna_model_mesh_part_create",
        c.c_uint64(0 if vertex_buffer is None else int(vertex_buffer._require_handle())),
        c.c_uint64(0 if index_buffer is None else int(index_buffer._require_handle())),
        c.c_int32(_support.checked(int(part.NumVertices), "int32", "NumVertices")),
        c.c_int32(_support.checked(int(part.PrimitiveCount), "int32", "PrimitiveCount")),
        c.c_int32(_support.checked(int(part.StartIndex), "int32", "StartIndex")),
        c.c_int32(_support.checked(int(part.VertexOffset), "int32", "VertexOffset")))


# --- level of detail ----------------------------------------------------------


class LodGroup(_EngineObject):
    """Several versions of one mesh, and the rule for choosing between them.

    Levels are kept sorted with the finest first, whichever mode is in use, so
    the index :meth:`select_index` returns means the same thing in both. Adding
    a level, clearing, or changing the mode re-sorts and forgets the last
    selection.

    A threshold is an *upper* bound: a distance exactly at a level's threshold
    has left that level and belongs to the next one. Past every threshold no
    level covers the object at all, and selection answers ``-1``.
    """

    __slots__ = ("_parts", "_native_parts")
    _DESTROY = "cna_lod_group_ext_destroy"

    def __init__(self) -> None:
        self._attach(_support.out_handle("cna_lod_group_ext_create"))
        #: The caller's own mesh parts, by the native handle CNA knows them as,
        #: so selection answers with the object that was added.
        self._parts: dict[int, object] = {}
        self._native_parts: list[_support.NativeHandle] = []

    def add_level(self, max_distance: float, part: "ModelMeshPart") -> None:
        """Adds one level. The threshold must be positive, and is not a distance
        when the mode is ``ScreenSpaceError`` -- it is a pixel radius."""
        handle = _mesh_part_handle(part, "part")
        owned = _support.NativeHandle(handle, "cna_model_mesh_part_destroy",
                                      "native mesh part")
        try:
            _support.call("cna_lod_group_ext_add_level", self._handle.argument,
                          c.c_float(_support.real(max_distance, "max_distance")),
                          owned.argument)
        except BaseException:
            owned.close()
            raise
        self._native_parts.append(owned)
        self._parts[handle] = part

    def clear(self) -> None:
        """Drops every level and forgets the last selection."""
        _support.call("cna_lod_group_ext_clear", self._handle.argument)
        self._parts.clear()
        for owned in self._native_parts:
            owned.close()
        self._native_parts.clear()

    def levels(self) -> tuple[LodLevel, ...]:
        """Every level, finest first, with the caller's own mesh parts."""
        values, written = _support.copied_values(
            _engine.CNA_LodLevelEXT, "cna_lod_group_ext_copy_levels",
            (self._handle.argument,))
        return tuple(LodLevel(float(values[index].max_distance),
                              self._parts.get(int(values[index].part)))
                     for index in range(written))

    def select_index(self, distance: float) -> int:
        """Which level a distance selects, or ``-1`` when none covers it.

        Not a pure function: the group remembers the choice so that
        :attr:`hysteresis` can hold it next time. A negative distance is treated
        as zero.
        """
        return _support.out_i32(
            "cna_lod_group_ext_select_index", self._handle.argument,
            c.c_float(_support.real(distance, "distance")))

    def select(self, distance: float) -> "ModelMeshPart | None":
        """The mesh part a distance selects, or ``None`` when none covers it.

        The caller's own object, looked up by the handle CNA answers with. The
        group keeps owning the native part, so nothing is released here.
        """
        handle = _support.out_handle("cna_lod_group_ext_select", self._handle.argument,
                                     c.c_float(_support.real(distance, "distance")))
        return self._parts.get(handle)

    @property
    def hysteresis(self) -> float:
        """How far past a boundary a value must move before the level changes.

        Zero disables it. A non-positive margin becomes zero rather than being
        refused, so read it back to see what was kept.
        """
        return _support.out_f32("cna_lod_group_ext_get_hysteresis",
                                self._handle.argument)

    @hysteresis.setter
    def hysteresis(self, value: float) -> None:
        _support.call("cna_lod_group_ext_set_hysteresis", self._handle.argument,
                      c.c_float(_support.real(value, "hysteresis")))

    def reset_hysteresis(self) -> None:
        """Forgets the last selection, so nothing is sticky on the next one."""
        _support.call("cna_lod_group_ext_reset_hysteresis", self._handle.argument)

    @property
    def selection_mode(self) -> LodSelectionMode:
        """Whether thresholds are world distances or projected pixel radii."""
        return LodSelectionMode(_support.out_u32(
            "cna_lod_group_ext_get_selection_mode", self._handle.argument))

    @selection_mode.setter
    def selection_mode(self, value: LodSelectionMode) -> None:
        _support.call("cna_lod_group_ext_set_selection_mode", self._handle.argument,
                      c.c_uint32(int(LodSelectionMode(value))))

    def set_screen_space_parameters(self, radius: float, vertical_fov: float,
                                    viewport_height: float) -> None:
        """The three numbers a projected pixel radius needs.

        All at once, because a projected size computed from a mixture of old and
        new camera state is a number describing no camera. Every one must be
        positive, and the field of view must be less than half a turn.
        """
        _support.call("cna_lod_group_ext_set_screen_space_parameters",
                      self._handle.argument,
                      c.c_float(_support.real(radius, "radius")),
                      c.c_float(_support.real(vertical_fov, "vertical_fov")),
                      c.c_float(_support.real(viewport_height, "viewport_height")))

    def projected_radius_pixels(self, distance: float) -> float:
        """How many pixels the object covers at that distance.

        At or behind the eye the projection is meaningless, and the answer is
        the largest float there is -- which selects the finest level rather than
        none.
        """
        return _support.out_f32(
            "cna_lod_group_ext_projected_radius_pixels", self._handle.argument,
            c.c_float(_support.real(distance, "distance")))

    def close(self) -> None:
        if self._handle.closed:
            return
        super().close()
        self._parts.clear()
        for owned in self._native_parts:
            owned.close()
        self._native_parts.clear()


# --- frustum culling ----------------------------------------------------------


class FrustumCuller(_EngineObject):
    """The six-plane visibility test, over one bound or a whole array.

    Conservative, as every frustum test is: a bound that only overlaps the
    corner region outside the frustum still counts as visible. Drawing something
    invisible costs a draw call; skipping something visible is a hole in the
    picture.
    """

    __slots__ = ()
    _DESTROY = "cna_frustum_culler_ext_destroy"

    def __init__(self) -> None:
        self._attach(_support.out_handle("cna_frustum_culler_ext_create"))

    def set_view_projection(self, view_projection: Matrix) -> None:
        """Sets the combined matrix and re-derives the six planes."""
        native = _native_matrix(view_projection)
        _support.call("cna_frustum_culler_ext_set_view_projection",
                      self._handle.argument, c.byref(native))

    def set_camera(self, view: Matrix, projection: Matrix) -> None:
        """The same, from the two matrices a camera already has."""
        native_view = _native_matrix(view)
        native_projection = _native_matrix(projection)
        _support.call("cna_frustum_culler_ext_set_camera", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection))

    @property
    def frustum(self):
        """The frustum as a strict ``BoundingFrustum``.

        The whole XNA surface -- its planes, its corners, its own intersection
        tests -- rather than a second frustum type. What CNA hands back is the
        matrix, which is what a ``BoundingFrustum`` is defined by.
        """
        from Microsoft.Xna.Framework import BoundingFrustum

        value = _engine.CNA_BoundingFrustum()
        _support.call("cna_frustum_culler_ext_get_frustum", self._handle.argument,
                      c.byref(value))
        return BoundingFrustum(_matrix(value.matrix))

    def is_visible(self, bound) -> bool:
        """Whether a box or a sphere is inside the frustum."""
        if isinstance(bound, BoundingBox):
            native = _native_box(bound)
            return _support.out_bool("cna_frustum_culler_ext_is_box_visible",
                                     self._handle.argument, c.byref(native))
        if isinstance(bound, BoundingSphere):
            native = _native_sphere(bound)
            return _support.out_bool("cna_frustum_culler_ext_is_sphere_visible",
                                     self._handle.argument, c.byref(native))
        raise TypeError("bound must be a BoundingBox or a BoundingSphere")

    def cull_boxes(self, bounds: Iterable[BoundingBox]) -> tuple[int, ...]:
        """The indices of the boxes that are visible, in order."""
        array, count = _box_array(bounds)
        values, written = _support.copied_values(
            c.c_uint64, "cna_frustum_culler_ext_cull_boxes",
            (self._handle.argument, array, c.c_uint64(count)))
        return tuple(int(values[index]) for index in range(written))

    def cull_spheres(self, bounds: Iterable[BoundingSphere]) -> tuple[int, ...]:
        """The indices of the spheres that are visible, in order."""
        array, count = _sphere_array(bounds)
        values, written = _support.copied_values(
            c.c_uint64, "cna_frustum_culler_ext_cull_spheres",
            (self._handle.argument, array, c.c_uint64(count)))
        return tuple(int(values[index]) for index in range(written))

    def cull_transforms(self, transforms: Iterable[Matrix],
                        bounds: Iterable[BoundingBox]) -> tuple[Matrix, ...]:
        """The transforms whose bounds are visible, ready to hand to an instanced draw.

        **A transform with no matching bound is kept.** Measured: the two arrays
        are walked together and an index past the end of ``bounds`` is treated
        as visible, so passing fewer bounds than transforms is a way of saying
        "these ones are always drawn" rather than an error.
        """
        transform_array, transform_count = _matrix_array(transforms)
        bound_array, bound_count = _box_array(bounds)
        values, written = _support.copied_values(
            _abi.CNA_Matrix, "cna_frustum_culler_ext_cull_transforms",
            (self._handle.argument, transform_array, c.c_uint64(transform_count),
             bound_array, c.c_uint64(bound_count)))
        return tuple(_matrix(values[index]) for index in range(written))


def _native_box(value: BoundingBox) -> _engine.CNA_BoundingBox:
    if not isinstance(value, BoundingBox):
        raise TypeError("expected a Microsoft.Xna.Framework.BoundingBox")
    native = _engine.CNA_BoundingBox()
    native.min = _abi.CNA_Vector3(float(value.Min.X), float(value.Min.Y),
                                  float(value.Min.Z))
    native.max = _abi.CNA_Vector3(float(value.Max.X), float(value.Max.Y),
                                  float(value.Max.Z))
    return native


def _native_sphere(value: BoundingSphere) -> _engine.CNA_BoundingSphere:
    if not isinstance(value, BoundingSphere):
        raise TypeError("expected a Microsoft.Xna.Framework.BoundingSphere")
    native = _engine.CNA_BoundingSphere()
    native.center = _abi.CNA_Vector3(float(value.Center.X), float(value.Center.Y),
                                     float(value.Center.Z))
    native.radius = _support.real(value.Radius, "radius")
    return native


def _box_array(values: Iterable[BoundingBox]):
    boxes = tuple(values)
    if not boxes:
        return None, 0
    array = (_engine.CNA_BoundingBox * len(boxes))()
    for index, box in enumerate(boxes):
        array[index] = _native_box(box)
    return array, len(boxes)


def _sphere_array(values: Iterable[BoundingSphere]):
    spheres = tuple(values)
    if not spheres:
        return None, 0
    array = (_engine.CNA_BoundingSphere * len(spheres))()
    for index, sphere in enumerate(spheres):
        array[index] = _native_sphere(sphere)
    return array, len(spheres)


def _matrix_array(values: Iterable[Matrix]):
    matrices = tuple(values)
    if not matrices:
        return None, 0
    array = (_abi.CNA_Matrix * len(matrices))()
    for index, matrix in enumerate(matrices):
        array[index] = _native_matrix(matrix)
    return array, len(matrices)


# --- instancing ---------------------------------------------------------------


class InstancedRenderer(_EngineObject):
    """One mesh drawn many times, in one call where the renderer allows it.

    The per-instance transform is bound as a second vertex stream, whose layout
    :func:`instance_vertex_elements` publishes so a caller's own shader can
    declare it. A per-instance tint is a third stream and is off by default.

    **Instancing needs two capabilities, not one**: the transforms are stream
    one, so multi-stream vertex input matters as much as instancing does. Where
    either is missing :attr:`fallback_enabled` decides between a draw per
    instance and a refusal; the fallback needs an effect that carries a world
    matrix, because a per-instance transform has nowhere else to go.
    """

    __slots__ = ("_part", "_native_part")
    _DESTROY = "cna_instanced_renderer_ext_destroy"

    def __init__(self, device: "GraphicsDevice", part: "ModelMeshPart") -> None:
        handle = _mesh_part_handle(part, "part")
        owned = _support.NativeHandle(handle, "cna_model_mesh_part_destroy",
                                      "native mesh part")
        try:
            renderer = _support.out_handle("cna_instanced_renderer_ext_create",
                                           _device_handle(device), owned.argument)
        except BaseException:
            owned.close()
            raise
        self._attach(renderer, device)
        self._part = part
        self._native_part = owned

    @property
    def part(self) -> "ModelMeshPart":
        """The mesh part every instance draws -- the caller's own object."""
        return self._part

    def set_instances(self, transforms: Iterable[Matrix]) -> None:
        """Replaces the whole instance list. The transforms are copied."""
        array, count = _matrix_array(transforms)
        _support.call("cna_instanced_renderer_ext_set_instances", self._handle.argument,
                      array, c.c_uint64(count))

    def set_instance_tints(self, tints: Iterable[Color]) -> None:
        """Replaces the per-instance colours. Shorter than the instance list is
        allowed: the rest are white."""
        colours = tuple(tints)
        array = None
        if colours:
            array = (_abi.CNA_Color * len(colours))()
            for index, colour in enumerate(colours):
                if not isinstance(colour, Color):
                    raise TypeError("tints must be Microsoft.Xna.Framework.Color values")
                array[index] = _abi.CNA_Color(int(colour.R), int(colour.G),
                                              int(colour.B), int(colour.A))
        _support.call("cna_instanced_renderer_ext_set_instance_tints",
                      self._handle.argument, array, c.c_uint64(len(colours)))

    @property
    def tints_enabled(self) -> bool:
        """Whether the tint stream is bound at all."""
        return _support.out_bool("cna_instanced_renderer_ext_is_tints_enabled",
                                 self._handle.argument)

    @tints_enabled.setter
    def tints_enabled(self, value: bool) -> None:
        _support.call("cna_instanced_renderer_ext_set_tints_enabled",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    def draw(self, effect: "Effect") -> None:
        """Draws every instance, in one call or in one call each."""
        if not hasattr(effect, "_require_handle"):
            raise TypeError("effect must be a Microsoft.Xna.Framework.Graphics.Effect")
        _support.call("cna_instanced_renderer_ext_draw", self._handle.argument,
                      c.c_uint64(int(effect._require_handle())))

    @property
    def is_instancing_supported(self) -> bool:
        """Whether the renderer has both instancing and multi-stream input."""
        return _support.out_bool("cna_instanced_renderer_ext_is_instancing_supported",
                                 self._handle.argument)

    @property
    def fallback_enabled(self) -> bool:
        """Whether a renderer without instancing draws one instance at a time."""
        return _support.out_bool("cna_instanced_renderer_ext_is_fallback_enabled",
                                 self._handle.argument)

    @fallback_enabled.setter
    def fallback_enabled(self, value: bool) -> None:
        _support.call("cna_instanced_renderer_ext_set_fallback_enabled",
                      self._handle.argument, c.c_uint8(1 if value else 0))

    @property
    def instance_count(self) -> int:
        """How many instances the last :meth:`set_instances` carried."""
        return _support.out_i32("cna_instanced_renderer_ext_get_instance_count",
                                self._handle.argument)

    @property
    def instance_capacity(self) -> int:
        """How many the buffer can hold without being reallocated."""
        return _support.out_i32("cna_instanced_renderer_ext_get_instance_capacity",
                                self._handle.argument)

    @property
    def last_draw_call_count(self) -> int:
        """How many draw calls the last :meth:`draw` issued.

        One when instancing ran, one per instance when the fallback did, and
        zero when there was nothing to draw. The number that says which path was
        taken, rather than a claim about it.
        """
        return _support.out_i32("cna_instanced_renderer_ext_get_last_draw_call_count",
                                self._handle.argument)

    @property
    def did_last_draw_instance(self) -> bool:
        """Whether the last :meth:`draw` used the instanced path."""
        return _support.out_bool("cna_instanced_renderer_ext_did_last_draw_instance",
                                 self._handle.argument)

    def close(self) -> None:
        if self._handle.closed:
            return
        super().close()
        self._native_part.close()


def _vertex_elements(route: str) -> tuple["VertexElement", ...]:
    from Microsoft.Xna.Framework.Graphics import (
        VertexElement, VertexElementFormat, VertexElementUsage,
    )

    values, written = _support.copied_values(_abi.CNA_VertexElement, route, ())
    return tuple(VertexElement(int(values[index].offset),
                               VertexElementFormat(int(values[index].format)),
                               VertexElementUsage(int(values[index].usage)),
                               int(values[index].usage_index))
                 for index in range(written))


def instance_vertex_elements() -> tuple["VertexElement", ...]:
    """The per-instance transform stream's layout, as strict ``VertexElement`` values.

    Four ``Vector4`` rows at texture-coordinate usages one to four, because a
    vertex attribute is at most four wide and a matrix is four of them.
    """
    return _vertex_elements("cna_instanced_renderer_ext_copy_instance_elements")


def instance_vertex_stride() -> int:
    """How many bytes one instance's transform occupies."""
    value = c.c_int32()
    _support.call("cna_instanced_renderer_ext_get_instance_stride", c.byref(value))
    return int(value.value)


def tint_vertex_elements() -> tuple["VertexElement", ...]:
    """The per-instance tint stream's layout."""
    return _vertex_elements("cna_instanced_renderer_ext_copy_tint_elements")


def tint_vertex_stride() -> int:
    """How many bytes one instance's tint occupies."""
    value = c.c_int32()
    _support.call("cna_instanced_renderer_ext_get_tint_stride", c.byref(value))
    return int(value.value)


# --- GPU culling and indirect draws -------------------------------------------


@dataclass(frozen=True)
class GpuCullableInstance:
    """One instance the GPU may keep or discard: a transform and its bounds."""

    world: Matrix
    bounds: BoundingBox

    @classmethod
    def default(cls) -> "GpuCullableInstance":
        """CNA's own canonical defaults, read rather than transcribed.

        **The world matrix comes back all zero, not identity.**
        ``engine_layer.h`` says "an identity world and an empty box" and
        measurement says otherwise -- see ENGINE-008 in
        ``docs/engine-upstream-findings.md``. It is handed back as CNA gives it,
        because this method exists to report what CNA's defaults *are*; a
        substituted identity would make it a transcription and would hide the
        defect. Set :attr:`world` yourself, or the surviving draw reads back a
        transform that collapses every vertex onto the origin and nothing
        appears.
        """
        value = _engine.CNA_GpuCullableInstance()
        _support.call("cna_gpu_cullable_instance_init", c.byref(value))
        return cls(_matrix(value.world),
                   BoundingBox(_vector(value.bounds.min), _vector(value.bounds.max)))

    def _native(self):
        value = _support.in_struct(_engine.CNA_GpuCullableInstance, 1)
        value.world = _native_matrix(self.world)
        value.bounds = _native_box(self.bounds)
        return value


class GpuInstanceCuller(_EngineObject):
    """Culling on the GPU, writing the draw arguments the GPU then reads.

    Nothing crosses back to the CPU: the compute pass compacts the surviving
    transforms into a storage buffer and fills an indirect-draw command, and
    :meth:`draw` issues a draw that reads that command. The instance count never
    reaches the caller unless it asks -- and asking stalls the pipeline, which is
    why :meth:`read_visible_count` is named for what it does.

    Four capabilities are needed, and :attr:`unsupported_reason` names the first
    one missing rather than only reporting that something is.
    """

    __slots__ = ()
    _DESTROY = "cna_gpu_instance_culler_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.out_handle("cna_gpu_instance_culler_create",
                                         _device_handle(device)), device)

    @property
    def is_supported(self) -> bool:
        """Whether this renderer can cull on the GPU at all."""
        return _support.out_bool("cna_gpu_instance_culler_is_supported",
                                 self._handle.argument)

    @property
    def unsupported_reason(self) -> str:
        """Which capability is missing, or the empty string when none is."""
        return _support.copied_text("cna_gpu_instance_culler_copy_unsupported_reason",
                                    (self._handle.argument,), "the unsupported reason")

    def set_instances(self, instances: Iterable[GpuCullableInstance]) -> None:
        """Uploads the instance list. Refused where the GPU path is unsupported."""
        values = tuple(instances)
        array = None
        if values:
            array = (_engine.CNA_GpuCullableInstance * len(values))()
            for index, instance in enumerate(values):
                if not isinstance(instance, GpuCullableInstance):
                    raise TypeError("instances must be GpuCullableInstance values")
                array[index] = instance._native()
        _support.call("cna_gpu_instance_culler_set_instances", self._handle.argument,
                      array, c.c_uint64(len(values)))

    @property
    def instance_count(self) -> int:
        """How many instances the last :meth:`set_instances` carried."""
        return _support.out_i32("cna_gpu_instance_culler_get_instance_count",
                                self._handle.argument)

    def cull(self, view: Matrix, projection: Matrix, index_count: int,
             first_index: int = 0, base_vertex: int = 0) -> None:
        """Runs the compute pass and writes the indirect-draw command.

        The three index arguments describe the mesh every surviving instance
        draws; they go into the command rather than into a draw call, which is
        the whole point.
        """
        native_view = _native_matrix(view)
        native_projection = _native_matrix(projection)
        _support.call("cna_gpu_instance_culler_cull", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection),
                      c.c_int32(_support.checked(index_count, "int32", "index_count")),
                      c.c_int32(_support.checked(first_index, "int32", "first_index")),
                      c.c_int32(_support.checked(base_vertex, "int32", "base_vertex")))

    def draw(self, primitive_type: "PrimitiveType") -> None:
        """Issues the indirect draw the last :meth:`cull` wrote."""
        _support.call("cna_gpu_instance_culler_draw", self._handle.argument,
                      c.c_uint32(int(primitive_type)))

    def read_visible_count(self) -> int:
        """How many instances survived -- by reading the command buffer back.

        A synchronising read: it waits for the compute pass. Useful for a test
        or a diagnostic overlay, and not something to do every frame.
        """
        return _support.out_i32("cna_gpu_instance_culler_read_visible_count_ext",
                                self._handle.argument)


def instance_lookup_glsl() -> str:
    """CNA's own GLSL for reading a GPU-culled instance transform.

    ``cnaInstanceWorld()`` returns the same column-major matrix a custom
    effect's ``World`` uniform arrives in, so a shader can swap one for the
    other without touching anything else.
    """
    return _support.copied_text("cna_gpu_instance_culler_copy_instance_lookup_glsl",
                                (), "the instance lookup GLSL")


@dataclass(frozen=True)
class IndirectDrawArguments:
    """The four words a non-indexed indirect draw reads, in the GPU's own layout.

    No version or size header, unlike every other value in this family: the GPU
    reads these sixteen bytes verbatim, so the layout *is* the contract and
    cannot be versioned or padded.
    """

    vertex_count: int
    instance_count: int
    first_vertex: int
    base_instance: int

    @classmethod
    def default(cls) -> "IndirectDrawArguments":
        """CNA's own canonical defaults: all zero, which draws nothing."""
        value = _engine.CNA_IndirectDrawArguments()
        _support.call("cna_indirect_draw_arguments_init", c.byref(value))
        return cls(int(value.vertex_count), int(value.instance_count),
                   int(value.first_vertex), int(value.base_instance))

    def pack(self) -> bytes:
        """The bytes to write into a storage buffer, in the GPU's layout."""
        value = _engine.CNA_IndirectDrawArguments(
            _support.checked(self.vertex_count, "uint32", "vertex_count"),
            _support.checked(self.instance_count, "uint32", "instance_count"),
            _support.checked(self.first_vertex, "uint32", "first_vertex"),
            _support.checked(self.base_instance, "uint32", "base_instance"))
        return bytes(memoryview(value).cast("B"))


@dataclass(frozen=True)
class IndirectDrawIndexedArguments:
    """The five words an indexed indirect draw reads.

    ``base_vertex`` is signed, as the graphics API is; ``base_instance`` must be
    zero on GL ES.
    """

    index_count: int
    instance_count: int
    first_index: int
    base_vertex: int
    base_instance: int

    @classmethod
    def default(cls) -> "IndirectDrawIndexedArguments":
        """CNA's own canonical defaults: all zero, which draws nothing."""
        value = _engine.CNA_IndirectDrawIndexedArguments()
        _support.call("cna_indirect_draw_indexed_arguments_init", c.byref(value))
        return cls(int(value.index_count), int(value.instance_count),
                   int(value.first_index), int(value.base_vertex),
                   int(value.base_instance))

    def pack(self) -> bytes:
        """The bytes to write into a storage buffer, in the GPU's layout."""
        value = _engine.CNA_IndirectDrawIndexedArguments(
            _support.checked(self.index_count, "uint32", "index_count"),
            _support.checked(self.instance_count, "uint32", "instance_count"),
            _support.checked(self.first_index, "uint32", "first_index"),
            _support.checked(self.base_vertex, "int32", "base_vertex"),
            _support.checked(self.base_instance, "uint32", "base_instance"))
        return bytes(memoryview(value).cast("B"))


def draw_primitives_indirect(device: "GraphicsDevice", primitive_type: "PrimitiveType",
                             argument_buffer, argument_byte_offset: int = 0) -> None:
    """Draws primitives whose counts the GPU reads out of a storage buffer.

    The same state an ordinary draw needs: a vertex buffer must be bound and an
    effect pass applied first. Measured, CNA refuses either omission by name --
    *"no vertex buffer is bound"*, *"no effect has been applied"* -- rather than
    drawing nothing.
    """
    _support.call("cna_graphics_device_draw_primitives_indirect_ext",
                  _device_handle(device), c.c_uint32(int(primitive_type)),
                  c.c_uint64(_storage_handle(argument_buffer)),
                  c.c_int32(_support.checked(argument_byte_offset, "int32",
                                             "argument_byte_offset")))


def draw_indexed_primitives_indirect(device: "GraphicsDevice",
                                     primitive_type: "PrimitiveType", argument_buffer,
                                     argument_byte_offset: int = 0) -> None:
    """Draws indexed primitives whose counts the GPU reads out of a storage buffer.

    Needs an index buffer bound as well as a vertex buffer and an applied
    effect.
    """
    _support.call("cna_graphics_device_draw_indexed_primitives_indirect_ext",
                  _device_handle(device), c.c_uint32(int(primitive_type)),
                  c.c_uint64(_storage_handle(argument_buffer)),
                  c.c_int32(_support.checked(argument_byte_offset, "int32",
                                             "argument_byte_offset")))


def _storage_handle(buffer: object) -> int:
    from .compute import StorageBuffer

    if not isinstance(buffer, StorageBuffer):
        raise TypeError("argument_buffer must be a cna.extensions.engine.StorageBuffer")
    return int(buffer._handle.value)
