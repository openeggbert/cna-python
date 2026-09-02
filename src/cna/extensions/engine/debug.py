"""Seeing what a frame decided, as world-space lines.

A light's reach, a cluster grid's depth slices, a cascade's frustum and a probe
volume's lattice are all numbers that are hard to check and easy to see. This
family draws them: :class:`DebugDraw` collects line segments between
:meth:`~DebugDraw.begin` and :meth:`~DebugDraw.end`, and the gizmo methods build
a whole picture out of one engine object.

Two lists, and why
------------------

Lines go into a *depth-tested* list or an *overlay* list, chosen by
:attr:`DebugDraw.depth_tested` when the line is added rather than when it is
drawn. The overlay pass runs second, so an overlay line crossing a depth-tested
one wins -- which is the point of asking for an overlay at all.

Countable, which is what makes it testable
------------------------------------------

Every shape's line count is exact and determined by its arguments: a box is
twelve, a cross is three, a sphere is three rings of its clamped segment count.
:attr:`DebugDraw.line_count` and :meth:`DebugDraw.vertices` therefore let a
caller -- and a test -- check what was built without rendering anything, which is
why both are here rather than only a draw.
"""

from __future__ import annotations

import ctypes as c
from typing import TYPE_CHECKING, Iterable

from Microsoft.Xna.Framework import (
    BoundingBox, BoundingFrustum, BoundingSphere, Color, Matrix, Vector3,
)

from _cna_native import abi as _abi
from _cna_native import engine_abi as _engine
from _cna_native import engine_support as _support

from .values import _EngineObject, _device_handle, _native_matrix, _native_vector, _vector

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from Microsoft.Xna.Framework.Graphics import GraphicsDevice

__all__ = [
    "DebugDraw",
    "DebugLineVertex",
    "DEBUG_DRAW_MINIMUM_SEGMENTS",
    "DEBUG_DRAW_MAXIMUM_SEGMENTS",
    "DEBUG_DRAW_DEFAULT_SEGMENTS",
    "DEBUG_DRAW_BOX_EDGE_COUNT",
]

#: The fewest segments a ring is drawn with; fewer would not read as a circle.
DEBUG_DRAW_MINIMUM_SEGMENTS = 4
#: The most; more is a filled disc on screen and shows nothing extra.
DEBUG_DRAW_MAXIMUM_SEGMENTS = 128
#: What a sphere uses when a gizmo does not choose.
DEBUG_DRAW_DEFAULT_SEGMENTS = 24
#: A box and a frustum have the same twelve edges, because XNA numbers their
#: corners the same way.
DEBUG_DRAW_BOX_EDGE_COUNT = 12


class DebugLineVertex:
    """One endpoint of a debug line: where it is and what colour it is."""

    __slots__ = ("position", "color")

    def __init__(self, position: Vector3, color: Color) -> None:
        self.position = position
        self.color = color

    def __repr__(self) -> str:
        return f"DebugLineVertex(position={self.position!r}, color={self.color!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DebugLineVertex):
            return NotImplemented
        return self.position == other.position and self.color == other.color


def _native_color(value: Color) -> _abi.CNA_Color:
    if not isinstance(value, Color):
        raise TypeError("colour must be a Microsoft.Xna.Framework.Color")
    return _abi.CNA_Color(int(value.R), int(value.G), int(value.B), int(value.A))


class DebugDraw(_EngineObject):
    """Collects world-space lines and draws them as one batch.

    :meth:`begin` clears both lists, sets the camera and turns depth testing back
    on; :meth:`end` draws and clears. A drawer that was never begun draws
    nothing on :meth:`end` rather than drawing with a stale camera.
    """

    __slots__ = ()
    _DESTROY = "cna_debug_draw_destroy"

    def __init__(self, device: "GraphicsDevice") -> None:
        self._attach(_support.out_handle("cna_debug_draw_create",
                                         _device_handle(device)), device)

    def begin(self, view: Matrix, projection: Matrix) -> None:
        """Starts a batch: clears both lists and sets the camera.

        Also turns :attr:`depth_tested` back on, so a batch always starts in the
        same state whatever the last one ended in.
        """
        native_view = _native_matrix(view)
        native_projection = _native_matrix(projection)
        _support.call("cna_debug_draw_begin", self._handle.argument,
                      c.byref(native_view), c.byref(native_projection))

    def end(self) -> None:
        """Draws the depth-tested lines, then the overlay ones, then clears both.

        In that order, so an overlay line crossing a depth-tested one wins. The
        device's depth-stencil state is restored afterwards.
        """
        _support.call("cna_debug_draw_end", self._handle.argument)

    def clear(self) -> None:
        """Drops every line without drawing any of them."""
        _support.call("cna_debug_draw_clear", self._handle.argument)

    def __enter__(self) -> "DebugDraw":
        self._handle.value
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    @property
    def depth_tested(self) -> bool:
        """Which list the *next* line joins, not how the batch is drawn."""
        return _support.out_bool("cna_debug_draw_is_depth_tested",
                                 self._handle.argument)

    @depth_tested.setter
    def depth_tested(self, value: bool) -> None:
        _support.call("cna_debug_draw_set_depth_tested", self._handle.argument,
                      c.c_uint8(1 if value else 0))

    @property
    def line_count(self) -> int:
        """How many lines both lists hold together."""
        return _support.out_i32("cna_debug_draw_get_line_count", self._handle.argument)

    def vertices(self, depth_tested: bool = True) -> tuple[DebugLineVertex, ...]:
        """One of the two lists, as endpoint pairs.

        Two vertices per line, in the order they were added. Exposed because it
        is how a caller can check what a gizmo built without drawing it -- and
        the only way to see the two lists apart, since :attr:`line_count` adds
        them together.
        """
        if not isinstance(depth_tested, bool):
            raise TypeError("depth_tested must be a bool")
        values, written = _support.copied_values(
            _abi.CNA_VertexPositionColor, "cna_debug_draw_copy_vertices",
            (self._handle.argument, c.c_uint8(1 if depth_tested else 0)))
        return tuple(DebugLineVertex(_vector(values[index].position),
                                     _color(values[index].color))
                     for index in range(written))

    # -- shapes ---------------------------------------------------------------

    def add_line(self, start: Vector3, end: Vector3, color: Color) -> None:
        """One segment."""
        native_start = _native_vector(start)
        native_end = _native_vector(end)
        _support.call("cna_debug_draw_add_line", self._handle.argument,
                      c.byref(native_start), c.byref(native_end),
                      _native_color(color))

    def add_box(self, bounds: BoundingBox, color: Color) -> None:
        """The twelve edges of an axis-aligned box."""
        native = _native_box(bounds)
        _support.call("cna_debug_draw_add_box", self._handle.argument, c.byref(native),
                      _native_color(color))

    def add_frustum(self, frustum: BoundingFrustum, color: Color) -> None:
        """The twelve edges of a frustum, from its own eight corners."""
        if not isinstance(frustum, BoundingFrustum):
            raise TypeError("frustum must be a Microsoft.Xna.Framework.BoundingFrustum")
        native = _engine.CNA_BoundingFrustum()
        native.matrix = _native_matrix(frustum.Matrix)
        _support.call("cna_debug_draw_add_frustum", self._handle.argument, native,
                      _native_color(color))

    def add_sphere(self, centre: Vector3, radius: float, color: Color,
                   segments: int = DEBUG_DRAW_DEFAULT_SEGMENTS) -> None:
        """Three rings around a point, one per axis pair.

        ``segments`` is clamped into
        ``DEBUG_DRAW_MINIMUM_SEGMENTS..DEBUG_DRAW_MAXIMUM_SEGMENTS`` rather than
        refused, so read :attr:`line_count` to see what was built.
        """
        native = _native_vector(centre)
        _support.call("cna_debug_draw_add_sphere", self._handle.argument,
                      c.byref(native), c.c_float(_support.real(radius, "radius")),
                      _native_color(color),
                      c.c_int32(_support.checked(segments, "int32", "segments")))

    def add_bounding_sphere(self, sphere: BoundingSphere, color: Color,
                            segments: int = DEBUG_DRAW_DEFAULT_SEGMENTS) -> None:
        """The same three rings, from a bounding sphere."""
        native = _native_sphere(sphere)
        _support.call("cna_debug_draw_add_bounding_sphere", self._handle.argument,
                      c.byref(native), _native_color(color),
                      c.c_int32(_support.checked(segments, "int32", "segments")))

    def add_cross(self, position: Vector3, size: float, color: Color) -> None:
        """Three axis-aligned segments through a point."""
        native = _native_vector(position)
        _support.call("cna_debug_draw_add_cross", self._handle.argument,
                      c.byref(native), c.c_float(_support.real(size, "size")),
                      _native_color(color))

    # -- gizmos ---------------------------------------------------------------

    def add_point_light_gizmo(self, light, color: Color) -> None:
        """A sphere at the light's reach and a small cross at its position."""
        from .values import PointLight

        if not isinstance(light, PointLight):
            raise TypeError("light must be a PointLight")
        native = light._native()
        _support.call("cna_debug_draw_add_point_light_gizmo", self._handle.argument,
                      c.byref(native), _native_color(color))

    def add_spot_light_gizmo(self, light, color: Color,
                             segments: int = DEBUG_DRAW_DEFAULT_SEGMENTS) -> None:
        """The cone the light lights: a ring at its base and four ribs.

        Four ribs and no more, whatever the segment count: a cone drawn with one
        rib per ring segment is a filled triangle on screen and shows nothing.
        """
        from .values import SpotLight

        if not isinstance(light, SpotLight):
            raise TypeError("light must be a SpotLight")
        native = light._native()
        _support.call("cna_debug_draw_add_spot_light_gizmo", self._handle.argument,
                      c.byref(native), _native_color(color),
                      c.c_int32(_support.checked(segments, "int32", "segments")))

    def add_directional_light_gizmo(self, light, at: Vector3, length: float,
                                    color: Color) -> None:
        """An arrow through ``at``, pointing the way the light travels."""
        from .values import DirectionalLight

        if not isinstance(light, DirectionalLight):
            raise TypeError("light must be a DirectionalLight")
        native = light._native()
        native_at = _native_vector(at)
        _support.call("cna_debug_draw_add_directional_light_gizmo",
                      self._handle.argument, c.byref(native), c.byref(native_at),
                      c.c_float(_support.real(length, "length")),
                      _native_color(color))

    def add_probe_volume_gizmo(self, volume, color: Color,
                               cross_size: float = 0.1) -> None:
        """The volume's box, and a small cross at every probe in the lattice."""
        from .probes import LightProbeVolume

        if not isinstance(volume, LightProbeVolume):
            raise TypeError("volume must be a LightProbeVolume")
        _support.call("cna_debug_draw_add_probe_volume_gizmo", self._handle.argument,
                      volume._handle.argument, _native_color(color),
                      c.c_float(_support.real(cross_size, "cross_size")))

    def add_cluster_slice_gizmo(self, grid, inverse_view: Matrix,
                                color: Color) -> None:
        """One box per depth slice, spanning the whole grid at that depth.

        The grid's clusters are in view space, so ``inverse_view`` brings them
        back to world. One box per slice rather than one per cluster: the full
        grid would be tiles times tiles times slices boxes, which is a thicket
        rather than a picture. A grid with no projection draws nothing.
        """
        from .clustered import ClusteredLightGrid

        if not isinstance(grid, ClusteredLightGrid):
            raise TypeError("grid must be a ClusteredLightGrid")
        native = _native_matrix(inverse_view)
        _support.call("cna_debug_draw_add_cluster_slice_gizmo", self._handle.argument,
                      grid._handle.argument, c.byref(native), _native_color(color))

    def add_cascade_gizmo(self, cascades, color: Color) -> None:
        """One frustum per cascade, so their overlap can be seen."""
        from .shadows import CascadedShadowMap

        if not isinstance(cascades, CascadedShadowMap):
            raise TypeError("cascades must be a CascadedShadowMap")
        _support.call("cna_debug_draw_add_cascade_gizmo", self._handle.argument,
                      cascades._handle.argument, _native_color(color))


def _color(value: _abi.CNA_Color) -> Color:
    return Color(int(value.r), int(value.g), int(value.b), int(value.a))


def _native_box(value: BoundingBox) -> _engine.CNA_BoundingBox:
    if not isinstance(value, BoundingBox):
        raise TypeError("bounds must be a Microsoft.Xna.Framework.BoundingBox")
    native = _engine.CNA_BoundingBox()
    native.min = _native_vector(value.Min)
    native.max = _native_vector(value.Max)
    return native


def _native_sphere(value: BoundingSphere) -> _engine.CNA_BoundingSphere:
    if not isinstance(value, BoundingSphere):
        raise TypeError("sphere must be a Microsoft.Xna.Framework.BoundingSphere")
    native = _engine.CNA_BoundingSphere()
    native.center = _native_vector(value.Center)
    native.radius = _support.real(value.Radius, "radius")
    return native
