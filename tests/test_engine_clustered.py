"""Clustered lighting, against independently computed grids and assignments.

Nothing here compares a CNA getter with itself. Every slice boundary, cluster
index, cluster box, light bound and shadow score is computed a second time in
:mod:`tests.engine_oracles` from the stated algorithm, and the whole
compressed-row assignment is rebuilt there so a transposed grid or an off-by-one
slice cannot pass by having plausible totals.

The numbers are chosen to be awkward on purpose: a near plane of 0.35 and a far
plane of 47.5 with five slices, a 3 by 2 tile grid rather than a square one, and
lights that are not on an axis. A symmetric fixture would let a swapped
``tiles_x``/``tiles_y`` agree with the right answer.

Most of this family is CPU arithmetic, so it runs on any build with an engine
layer; the buffer, the GPU assigner, the BRDF table and the forward effect need
a rasterizing renderer and are separated out.
"""

from __future__ import annotations

import ctypes as c
import math
import unittest

from Microsoft.Xna.Framework import BoundingSphere, Matrix, Vector3

from cna.extensions.engine import (
    AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT, AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE,
    AREA_LIGHT_QUAD_CORNER_COUNT, AreaLight, AreaLightBrdfTable, AreaLightShape,
    CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS, CLUSTERED_COMPUTE_DEFAULT_STRIDE,
    CLUSTERED_LIGHT_SET_MAXIMUM, CLUSTERED_SHADOW_DEFAULT_BUDGET,
    CLUSTERED_SHADOW_DEFAULT_HYSTERESIS, ClusteredForwardEffect, ClusteredLight,
    ClusteredLightAssignment, ClusteredLightBuffer, ClusteredLightCompute,
    ClusteredLightGrid, ClusteredLightKind, ClusteredLightSet, ClusteredShadowPolicy,
    PbrMaterialExtensions, PointLight, SpotLight, area_light_contribution,
    area_light_coverage, area_light_quad, area_light_shading_glsl, brdf_lookup_glsl,
    evaluate_brdf, light_contribution, light_lookup_glsl, lobe_scale_for,
    volume_attenuation,
)
from cna.extensions.engine.errors import (
    EngineArgumentError, EngineDisposedError, EngineError, EngineStateError,
    EngineUnavailableError,
)

from . import engine_oracles as oracle
from .engine_fixtures import (
    ENGINE_PRESENT, in_game, requires_engine, requires_engine_gpu, requires_native,
)

#: A field of view, aspect, near and far that are all awkward numbers, so an
#: expectation that happens to be right for a square 45-degree frustum is not.
FIELD_OF_VIEW = 0.9773843811168246
ASPECT = 1.7777777777777777
NEAR = 0.35
FAR = 47.5
PROJECTION = Matrix.CreatePerspectiveFieldOfView(FIELD_OF_VIEW, ASPECT, NEAR, FAR)

#: Not square, so a swapped pair of tile counts is a different grid.
TILES_X, TILES_Y, SLICES = 3, 2, 5


def _point(position: Vector3, range_: float = 4.0, *, intensity: float = 2.0,
           color: Vector3 | None = None, casts_shadows: bool = False) -> ClusteredLight:
    """A point light built from CNA's defaults, with the fields under test replaced."""
    from dataclasses import replace

    return replace(ClusteredLight.default(), kind=ClusteredLightKind.Point,
                   position=position, range_=range_, intensity=intensity,
                   color=color if color is not None else Vector3(0.25, 0.75, 0.5),
                   casts_shadows=casts_shadows)


def _spot(position: Vector3, direction: Vector3, range_: float = 7.0,
          outer: float = 0.6, inner: float = 0.2, *,
          casts_shadows: bool = False) -> ClusteredLight:
    from dataclasses import replace

    return replace(ClusteredLight.default(), kind=ClusteredLightKind.Spot,
                   position=position, direction=direction, range_=range_,
                   inner_angle=inner, outer_angle=outer, casts_shadows=casts_shadows)


# --- values -------------------------------------------------------------------


@requires_engine
class ClusteredLightValueTests(unittest.TestCase):
    """The light value, its defaults and CNA's own usability rule."""

    def test_the_defaults_come_from_cna_and_are_usable(self) -> None:
        light = ClusteredLight.default()
        self.assertIs(type(light.kind), ClusteredLightKind)
        self.assertGreater(light.range_, 0.0)
        self.assertGreaterEqual(light.intensity, 0.0)
        self.assertTrue(light.is_usable)

    def test_a_light_survives_a_round_trip_through_the_native_structure(self) -> None:
        """Every field, at the width C stores it in.

        The angles are single-precision in the structure, so 0.2 comes back as
        0.20000000298023224; comparing the dataclasses for equality would be a
        test of Python float literals rather than of the conversion.
        """
        light = _spot(Vector3(1.5, 3.25, -6.0), Vector3(0.3, -1.0, 0.2))
        back = ClusteredLight._from_native(light._native())
        self.assertEqual(back.kind, light.kind)
        self.assertEqual(back.casts_shadows, light.casts_shadows)
        for field in ("position", "direction", "color"):
            for axis in ("X", "Y", "Z"):
                self.assertAlmostEqual(getattr(getattr(back, field), axis),
                                       getattr(getattr(light, field), axis),
                                       places=6, msg=f"{field}.{axis}")
        for field in ("intensity", "range_", "inner_angle", "outer_angle"):
            self.assertAlmostEqual(getattr(back, field), getattr(light, field),
                                   places=6, msg=field)

    def test_the_rules_a_set_will_refuse_a_light_for(self) -> None:
        """Each is a separate reason, so each is asserted separately."""
        from dataclasses import replace

        usable = _point(Vector3(0.0, 0.0, -5.0))
        self.assertTrue(usable.is_usable)
        self.assertFalse(replace(usable, range_=0.0).is_usable)
        self.assertFalse(replace(usable, range_=-1.0).is_usable)
        self.assertFalse(replace(usable, intensity=-0.5).is_usable)
        self.assertFalse(replace(usable, range_=math.inf).is_usable)
        self.assertFalse(replace(usable, position=Vector3(math.nan, 0.0, 0.0)).is_usable)
        self.assertFalse(replace(usable, color=Vector3(0.0, math.inf, 0.0)).is_usable)

    def test_a_spot_is_judged_on_its_cone_as_well(self) -> None:
        from dataclasses import replace

        spot = _spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0))
        self.assertTrue(spot.is_usable)
        # A direction of no length has no cone.
        self.assertFalse(replace(spot, direction=Vector3(0.0, 0.0, 0.0)).is_usable)
        # An outer angle wider than a hemisphere is not a cone.
        self.assertFalse(replace(spot, outer_angle=1.6).is_usable)
        # Inner wider than outer inverts the falloff.
        self.assertFalse(replace(spot, inner_angle=0.9, outer_angle=0.6).is_usable)
        self.assertFalse(replace(spot, inner_angle=-0.1).is_usable)

    def test_a_point_light_is_not_judged_on_its_cone(self) -> None:
        """The same angles that refuse a spot are ignored for a point."""
        from dataclasses import replace

        point = replace(_point(Vector3(0.0, 0.0, -5.0)), inner_angle=0.9,
                        outer_angle=1.6, direction=Vector3(0.0, 0.0, 0.0))
        self.assertTrue(point.is_usable)


@requires_engine
class AreaLightValueTests(unittest.TestCase):
    def test_the_defaults_come_from_cna_and_are_valid(self) -> None:
        light = AreaLight.default()
        self.assertIs(type(light.shape), AreaLightShape)
        self.assertTrue(light.is_valid)

    def test_a_light_survives_a_round_trip_through_the_native_structure(self) -> None:
        from dataclasses import replace

        light = replace(AreaLight.default(), shape=AreaLightShape.Tube,
                        two_sided=True, position=Vector3(1.0, 2.0, 3.0),
                        right_axis=Vector3(0.75, 0.0, 0.0),
                        up_axis=Vector3(0.0, 0.25, 0.0))
        # Every value here is exact in single precision, so equality is the
        # right comparison and a widened field would fail it.
        self.assertEqual(AreaLight._from_native(light._native()), light)

    def test_a_degenerate_light_is_not_valid(self) -> None:
        from dataclasses import replace

        light = AreaLight.default()
        self.assertFalse(replace(light, range_=0.0).is_valid)
        self.assertFalse(replace(light, intensity=-1.0).is_valid)
        self.assertFalse(replace(light, right_axis=Vector3(0.0, 0.0, 0.0)).is_valid)


# --- the set ------------------------------------------------------------------


@requires_engine
class ClusteredLightSetTests(unittest.TestCase):
    """A CPU collection, so it needs no renderer -- only a device to be parented to."""

    def _set(self, body):
        def run(game, device, observed):
            with ClusteredLightSet(device) as lights:
                body(lights, observed)

        return in_game(run)

    def test_a_new_set_is_empty(self) -> None:
        observed = self._set(lambda lights, out: out.update(
            count=len(lights), empty=lights.is_empty))
        self.assertEqual(observed["count"], 0)
        self.assertTrue(observed["empty"])

    def test_adding_returns_the_index_it_took_and_reads_back(self) -> None:
        def body(lights, out):
            out["first"] = lights.add(_point(Vector3(1.5, 0.25, -6.0)))
            out["second"] = lights.add(_spot(Vector3(0.0, 3.0, -9.0),
                                             Vector3(0.0, -1.0, 0.0)))
            out["count"] = len(lights)
            out["read"] = lights[0]
            out["kinds"] = [lights[index].kind for index in range(len(lights))]

        observed = self._set(body)
        self.assertEqual((observed["first"], observed["second"]), (0, 1))
        self.assertEqual(observed["count"], 2)
        self.assertEqual(observed["read"].position, Vector3(1.5, 0.25, -6.0))
        self.assertEqual(observed["kinds"],
                         [ClusteredLightKind.Point, ClusteredLightKind.Spot])

    def test_a_point_and_a_spot_light_convert_into_the_set(self) -> None:
        """The two convenience routes, checked against what they should become."""
        from dataclasses import replace

        point = replace(PointLight.default(), position=Vector3(1.0, 2.0, -3.0),
                        range_=5.0, intensity=1.5, casts_shadows=True)
        spot = replace(SpotLight.default(), position=Vector3(-1.0, 4.0, -8.0),
                       direction=Vector3(0.1, -1.0, 0.2), range_=9.0,
                       inner_angle=0.15, outer_angle=0.55)

        def body(lights, out):
            lights.add_point(point)
            lights.add_spot(spot)
            out["values"] = [lights[0], lights[1]]

        converted_point, converted_spot = self._set(body)["values"]
        self.assertEqual(converted_point.kind, ClusteredLightKind.Point)
        self.assertEqual(converted_point.position, point.position)
        self.assertEqual(converted_point.range_, point.range_)
        self.assertEqual(converted_point.casts_shadows, point.casts_shadows)
        self.assertEqual(converted_spot.kind, ClusteredLightKind.Spot)
        self.assertEqual(converted_spot.direction, spot.direction)
        self.assertAlmostEqual(converted_spot.outer_angle, spot.outer_angle, places=6)

    def test_an_unusable_light_is_refused_rather_than_skipped(self) -> None:
        from dataclasses import replace

        def body(lights, out):
            broken = replace(_point(Vector3(0.0, 0.0, -5.0)), range_=0.0)
            try:
                lights.add(broken)
                out["raised"] = None
            except EngineError as error:
                out["raised"] = type(error).__name__
            out["count"] = len(lights)

        observed = self._set(body)
        self.assertIsNotNone(observed["raised"])
        self.assertEqual(observed["count"], 0)

    def test_removing_moves_the_later_lights_down(self) -> None:
        def body(lights, out):
            for x in range(3):
                lights.add(_point(Vector3(float(x), 0.0, -5.0)))
            lights.remove_at(0)
            out["positions"] = [lights[index].position.X for index in range(len(lights))]

        self.assertEqual(self._set(body)["positions"], [1.0, 2.0])

    def test_replacing_keeps_every_other_index(self) -> None:
        def body(lights, out):
            for x in range(3):
                lights.add(_point(Vector3(float(x), 0.0, -5.0)))
            lights.replace_at(1, _point(Vector3(9.0, 0.0, -5.0)))
            out["positions"] = [lights[index].position.X for index in range(len(lights))]

        self.assertEqual(self._set(body)["positions"], [0.0, 9.0, 2.0])

    def test_clearing_empties_it(self) -> None:
        def body(lights, out):
            lights.add(_point(Vector3(0.0, 0.0, -5.0)))
            lights.clear()
            out["count"] = len(lights)
            out["empty"] = lights.is_empty

        observed = self._set(body)
        self.assertEqual(observed["count"], 0)
        self.assertTrue(observed["empty"])

    def test_an_index_outside_the_set_is_refused(self) -> None:
        def body(lights, out):
            lights.add(_point(Vector3(0.0, 0.0, -5.0)))
            for operation in ("get", "remove", "bounds"):
                try:
                    if operation == "get":
                        lights[5]
                    elif operation == "remove":
                        lights.remove_at(-1)
                    else:
                        lights.bounds_at(99)
                    out[operation] = None
                except EngineError as error:
                    out[operation] = type(error).__name__

        observed = self._set(body)
        for operation in ("get", "remove", "bounds"):
            self.assertIsNotNone(observed[operation], operation)

    def test_copying_the_lights_out_gives_the_same_values_in_order(self) -> None:
        def body(lights, out):
            lights.add(_point(Vector3(1.5, 0.25, -6.0)))
            lights.add(_spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0)))
            out["copied"] = lights.lights()
            out["one_by_one"] = tuple(lights[index] for index in range(len(lights)))

        observed = self._set(body)
        self.assertEqual(observed["copied"], observed["one_by_one"])
        self.assertEqual(len(observed["copied"]), 2)

    def test_an_empty_set_copies_nothing_rather_than_failing(self) -> None:
        observed = self._set(lambda lights, out: out.update(
            lights=lights.lights(), bounds=lights.bounds()))
        self.assertEqual(observed["lights"], ())
        self.assertEqual(observed["bounds"], ())

    def test_a_point_lights_bound_is_its_own_sphere(self) -> None:
        def body(lights, out):
            lights.add(_point(Vector3(1.5, 0.25, -6.0), range_=4.0))
            out["bound"] = lights.bounds_at(0)

        bound = self._set(body)["bound"]
        centre, radius = oracle.point_light_bounds(Vector3(1.5, 0.25, -6.0), 4.0)
        self.assertEqual(bound.Center, centre)
        self.assertEqual(bound.Radius, radius)

    def test_a_narrow_spots_bound_is_the_cone_sphere_not_the_light(self) -> None:
        """The case a loose bound would pass and a right one must not."""
        position, direction, range_, outer = (Vector3(0.0, 3.0, -9.0),
                                              Vector3(0.0, -1.0, 0.0), 7.0, 0.6)

        def body(lights, out):
            lights.add(_spot(position, direction, range_=range_, outer=outer))
            out["bound"] = lights.bounds_at(0)

        bound = self._set(body)["bound"]
        centre, radius = oracle.spot_light_bounds(position, direction, range_, outer)
        self.assertAlmostEqual(bound.Radius, radius, places=5)
        self.assertAlmostEqual(bound.Center.Y, centre.Y, places=5)
        # Not centred on the light: that is the whole point of the narrow case.
        self.assertNotAlmostEqual(bound.Center.Y, position.Y, places=3)

    def test_a_wide_spot_uses_the_other_case(self) -> None:
        position, direction, range_, outer = (Vector3(0.0, 3.0, -9.0),
                                              Vector3(0.0, -1.0, 0.0), 7.0, 1.1)

        def body(lights, out):
            lights.add(_spot(position, direction, range_=range_, outer=outer,
                             inner=0.4))
            out["bound"] = lights.bounds_at(0)

        bound = self._set(body)["bound"]
        centre, radius = oracle.spot_light_bounds(position, direction, range_, outer)
        self.assertAlmostEqual(bound.Radius, radius, places=5)
        self.assertAlmostEqual(bound.Center.Y, centre.Y, places=5)

    def test_copying_the_bounds_matches_asking_one_at_a_time(self) -> None:
        def body(lights, out):
            lights.add(_point(Vector3(1.5, 0.25, -6.0)))
            lights.add(_spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0)))
            out["copied"] = lights.bounds()
            out["one_by_one"] = tuple(lights.bounds_at(index)
                                      for index in range(len(lights)))

        observed = self._set(body)
        self.assertEqual([(b.Center, b.Radius) for b in observed["copied"]],
                         [(b.Center, b.Radius) for b in observed["one_by_one"]])

    def test_the_maximum_is_a_measured_constant_and_is_enforced(self) -> None:
        self.assertEqual(CLUSTERED_LIGHT_SET_MAXIMUM, 256)

        def body(lights, out):
            for index in range(CLUSTERED_LIGHT_SET_MAXIMUM):
                lights.add(_point(Vector3(float(index), 0.0, -5.0)))
            out["full"] = len(lights)
            try:
                lights.add(_point(Vector3(0.0, 0.0, -5.0)))
                out["refused"] = False
            except EngineError:
                out["refused"] = True

        observed = self._set(body)
        self.assertEqual(observed["full"], CLUSTERED_LIGHT_SET_MAXIMUM)
        self.assertTrue(observed["refused"])

    def test_using_a_closed_set_is_refused_rather_than_reaching_freed_memory(self) -> None:
        def body(game, device, out):
            lights = ClusteredLightSet(device)
            lights.close()
            out["closed"] = lights.is_closed
            try:
                len(lights)
                out["raised"] = None
            except EngineDisposedError as error:
                out["raised"] = type(error).__name__
            lights.close()  # twice is not an error

        observed = in_game(body)
        self.assertTrue(observed["closed"])
        self.assertEqual(observed["raised"], "EngineDisposedError")

    def test_it_refuses_a_value_of_the_wrong_type(self) -> None:
        def body(game, device, out):
            with ClusteredLightSet(device) as lights:
                for call in (lambda: lights.add(PointLight.default()),
                             lambda: lights.add_point(_point(Vector3(0, 0, -1))),
                             lambda: lights.add_spot(PointLight.default())):
                    try:
                        call()
                        out.setdefault("passed", []).append("no error")
                    except TypeError:
                        out.setdefault("passed", []).append("TypeError")

        self.assertEqual(in_game(body)["passed"], ["TypeError"] * 3)


# --- the grid -----------------------------------------------------------------


@requires_engine
class ClusteredLightGridTests(unittest.TestCase):
    def _grid(self, body, tiles_x=TILES_X, tiles_y=TILES_Y, slices=SLICES,
              projection=True):
        def run(game, device, observed):
            with ClusteredLightGrid(device, tiles_x, tiles_y, slices) as grid:
                if projection:
                    grid.set_projection(PROJECTION, NEAR, FAR)
                body(grid, observed)

        return in_game(run)

    def test_the_dimensions_are_the_ones_it_was_given(self) -> None:
        observed = self._grid(lambda grid, out: out.update(
            x=grid.tiles_x, y=grid.tiles_y, slices=grid.slice_count,
            clusters=grid.cluster_count), projection=False)
        self.assertEqual((observed["x"], observed["y"], observed["slices"]),
                         (TILES_X, TILES_Y, SLICES))
        self.assertEqual(observed["clusters"], TILES_X * TILES_Y * SLICES)

    def test_every_cluster_index_matches_the_stated_layout(self) -> None:
        def body(grid, out):
            out["indices"] = [
                ((x, y, s), grid.cluster_index(x, y, s))
                for s in range(SLICES) for y in range(TILES_Y) for x in range(TILES_X)]

        for (x, y, s), index in self._grid(body)["indices"]:
            self.assertEqual(index, oracle.cluster_index(TILES_X, TILES_Y, x, y, s),
                             f"cluster ({x}, {y}, {s})")

    def test_a_coordinate_outside_the_grid_is_refused(self) -> None:
        def body(grid, out):
            for coordinate in ((TILES_X, 0, 0), (0, TILES_Y, 0), (0, 0, SLICES),
                               (-1, 0, 0)):
                try:
                    grid.cluster_index(*coordinate)
                    out[coordinate] = None
                except EngineError as error:
                    out[coordinate] = type(error).__name__

        observed = self._grid(body)
        for key, value in observed.items():
            self.assertIsNotNone(value, key)

    def test_a_grid_dimension_outside_its_range_is_refused_at_construction(self) -> None:
        def body(game, device, out):
            for dimensions in ((0, 2, 4), (2, 0, 4), (2, 2, 0), (129, 2, 4),
                               (2, 2, 257)):
                try:
                    ClusteredLightGrid(device, *dimensions).close()
                    out[dimensions] = None
                except EngineError as error:
                    out[dimensions] = type(error).__name__

        for key, value in in_game(body).items():
            self.assertIsNotNone(value, key)

    def test_a_grid_has_no_shape_before_a_projection_is_set(self) -> None:
        def body(grid, out):
            out["has"] = grid.has_projection
            out["distance"] = grid.slice_distance(2)
            out["inverse"] = grid.inverse_projection
            try:
                grid.cluster_bounds(0, 0, 0)
                out["bounds"] = None
            except EngineStateError as error:
                out["bounds"] = type(error).__name__

        observed = self._grid(body, projection=False)
        self.assertFalse(observed["has"])
        self.assertEqual(observed["distance"], 0.0)
        self.assertEqual(observed["inverse"], Matrix.Identity)
        self.assertEqual(observed["bounds"], "EngineStateError")

    def test_setting_a_projection_records_both_planes(self) -> None:
        observed = self._grid(lambda grid, out: out.update(
            has=grid.has_projection, near=grid.near_plane, far=grid.far_plane))
        self.assertTrue(observed["has"])
        self.assertAlmostEqual(observed["near"], NEAR, places=6)
        self.assertAlmostEqual(observed["far"], FAR, places=6)

    def test_an_impossible_pair_of_planes_is_refused(self) -> None:
        def body(grid, out):
            for near, far in ((0.0, 10.0), (-1.0, 10.0), (10.0, 10.0), (10.0, 1.0)):
                try:
                    grid.set_projection(PROJECTION, near, far)
                    out[(near, far)] = None
                except EngineError as error:
                    out[(near, far)] = type(error).__name__

        for key, value in self._grid(body, projection=False).items():
            self.assertIsNotNone(value, key)

    def test_a_projection_that_cannot_be_inverted_is_refused(self) -> None:
        def body(grid, out):
            try:
                grid.set_projection(Matrix(*([0.0] * 16)), NEAR, FAR)
                out["raised"] = None
            except EngineError as error:
                out["raised"] = type(error).__name__

        self.assertIsNotNone(self._grid(body, projection=False)["raised"])

    def test_every_slice_boundary_matches_the_logarithmic_spacing(self) -> None:
        def body(grid, out):
            out["distances"] = [grid.slice_distance(index)
                                for index in range(SLICES + 1)]

        distances = self._grid(body)["distances"]
        expected = [oracle.slice_distance(NEAR, FAR, SLICES, index)
                    for index in range(SLICES + 1)]
        for index, (got, want) in enumerate(zip(distances, expected)):
            self.assertAlmostEqual(got, want, places=5, msg=f"slice {index}")
        # The two ends are the planes exactly, not nearly.
        self.assertEqual(distances[0], oracle.f32(NEAR))
        self.assertEqual(distances[-1], oracle.f32(FAR))

    def test_a_slice_past_the_last_boundary_is_refused(self) -> None:
        def body(grid, out):
            for index in (SLICES + 1, -1):
                try:
                    grid.slice_distance(index)
                    out[index] = None
                except EngineArgumentError as error:
                    out[index] = type(error).__name__

        for key, value in self._grid(body).items():
            self.assertEqual(value, "EngineArgumentError", key)

    def test_a_view_distance_lands_in_the_slice_the_spacing_says(self) -> None:
        probes = [0.1, NEAR, 0.36, 1.0, 5.0, 17.3, 47.4, FAR, 90.0]

        def body(grid, out):
            out["slices"] = [grid.slice_for_view_distance(value) for value in probes]

        for value, got in zip(probes, self._grid(body)["slices"]):
            self.assertEqual(got, oracle.slice_for_view_distance(NEAR, FAR, SLICES, value),
                             f"distance {value}")

    def test_a_distance_inside_a_slice_lands_in_that_slice(self) -> None:
        """Round-trip: the geometric middle of a slice belongs to it."""
        def body(grid, out):
            middles = [math.sqrt(grid.slice_distance(index)
                                 * grid.slice_distance(index + 1))
                       for index in range(SLICES)]
            out["pairs"] = [(index, grid.slice_for_view_distance(middles[index]))
                            for index in range(SLICES)]

        for index, landed in self._grid(body)["pairs"]:
            self.assertEqual(landed, index)

    def test_the_inverse_projection_really_inverts_the_projection(self) -> None:
        inverse = self._grid(lambda grid, out: out.update(
            inverse=grid.inverse_projection))["inverse"]
        product = Matrix.Multiply(PROJECTION, inverse)
        for index, value in enumerate(product):
            self.assertAlmostEqual(value, 1.0 if index % 5 == 0 else 0.0, places=4)

    def test_every_cluster_box_matches_one_unprojected_independently(self) -> None:
        """The whole grid, not one cluster: a transposed layout fails only off-centre."""
        def body(grid, out):
            out["boxes"] = [((x, y, s), grid.cluster_bounds(x, y, s))
                            for s in range(SLICES) for y in range(TILES_Y)
                            for x in range(TILES_X)]

        for (x, y, s), box in self._grid(body)["boxes"]:
            minimum, maximum = oracle.cluster_bounds(PROJECTION, TILES_X, TILES_Y,
                                                     SLICES, NEAR, FAR, x, y, s)
            where = f"cluster ({x}, {y}, {s})"
            for axis in ("X", "Y", "Z"):
                self.assertAlmostEqual(getattr(box.Min, axis), getattr(minimum, axis),
                                       places=4, msg=f"{where} min {axis}")
                self.assertAlmostEqual(getattr(box.Max, axis), getattr(maximum, axis),
                                       places=4, msg=f"{where} max {axis}")

    def test_the_slices_meet_exactly_in_depth_and_the_tiles_overlap_across_it(self) -> None:
        """Two different properties, because the box is axis-aligned.

        In depth a cluster runs from one slice boundary to the next, so
        neighbouring boxes meet exactly. Across the screen they do **not**: an
        axis-aligned box around a frustum slab is as wide as that slab's far
        face, which reaches past the near face of its neighbour. The overlap is
        conservative rather than wrong -- a light may be assigned to a cluster it
        only nearly touches, and never missed from one it does -- and asserting a
        clean partition here would be asserting something false.

        The screen axes are checked on a three-tile grid: a tile boundary at the
        centre of the screen sits at zero on both sides whatever the projection,
        so a two-tile row would pass this without measuring anything.
        """
        def body(grid, out):
            out["depth"] = [grid.cluster_bounds(0, 0, s) for s in range(SLICES)]

        def screen(game, device, out):
            with ClusteredLightGrid(device, 3, 3, 1) as grid:
                grid.set_projection(PROJECTION, NEAR, FAR)
                out["row"] = [grid.cluster_bounds(x, 0, 0) for x in range(3)]
                out["column"] = [grid.cluster_bounds(0, y, 0) for y in range(3)]

        depth = self._grid(body)["depth"]
        for near, far in zip(depth, depth[1:]):
            self.assertAlmostEqual(near.Min.Z, far.Max.Z, places=5)
        observed = in_game(screen)
        for left, right in zip(observed["row"], observed["row"][1:]):
            self.assertLess(right.Min.X, left.Max.X)
            self.assertLess(left.Min.X, right.Min.X)
        for low, high in zip(observed["column"], observed["column"][1:]):
            self.assertLess(high.Min.Y, low.Max.Y)
            self.assertLess(low.Min.Y, high.Min.Y)

    def test_the_grid_covers_the_frustum_it_was_given(self) -> None:
        """The union of every box reaches the frustum's own extents."""
        def body(grid, out):
            out["boxes"] = [grid.cluster_bounds(x, y, s)
                            for s in range(SLICES) for y in range(TILES_Y)
                            for x in range(TILES_X)]

        boxes = self._grid(body)["boxes"]
        half_height = FAR * math.tan(FIELD_OF_VIEW / 2.0)
        self.assertAlmostEqual(max(box.Max.Y for box in boxes), half_height, places=3)
        self.assertAlmostEqual(min(box.Min.Y for box in boxes), -half_height, places=3)
        self.assertAlmostEqual(max(box.Max.X for box in boxes),
                               half_height * ASPECT, places=3)
        self.assertAlmostEqual(max(box.Max.Z for box in boxes), -NEAR, places=5)
        self.assertAlmostEqual(min(box.Min.Z for box in boxes), -FAR, places=4)

    def test_a_cluster_box_is_in_front_of_the_camera(self) -> None:
        """View space puts distance on -z, so every box is at negative z."""
        def body(grid, out):
            out["boxes"] = [grid.cluster_bounds(x, y, s)
                            for s in range(SLICES) for y in range(TILES_Y)
                            for x in range(TILES_X)]

        for box in self._grid(body)["boxes"]:
            self.assertLess(box.Max.Z, 0.0)
            self.assertLessEqual(box.Min.Z, box.Max.Z)


# --- the assignment -----------------------------------------------------------


@requires_engine
class ClusteredLightAssignmentTests(unittest.TestCase):
    LIGHTS = (_point(Vector3(1.5, 0.25, -6.0), range_=4.0),
              _spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0)),
              _point(Vector3(-8.0, -2.5, -30.0), range_=12.0))

    def _assign(self, body, lights=None, view=None):
        lights = self.LIGHTS if lights is None else lights
        view = Matrix.Identity if view is None else view

        def run(game, device, observed):
            with ClusteredLightSet(device) as light_set, \
                    ClusteredLightGrid(device, TILES_X, TILES_Y, SLICES) as grid, \
                    ClusteredLightAssignment(device) as assignment:
                grid.set_projection(PROJECTION, NEAR, FAR)
                for light in lights:
                    light_set.add(light)
                observed["spheres"] = light_set.bounds()
                assignment.assign(grid, view, observed["spheres"])
                body(light_set, grid, assignment, observed)

        return in_game(run)

    def test_the_whole_assignment_matches_one_computed_independently(self) -> None:
        """Offsets and indices, entry for entry -- the family's central claim."""
        def body(lights, grid, assignment, out):
            out["offsets"] = assignment.offsets()
            out["indices"] = assignment.indices()

        observed = self._assign(body)
        spheres = [(sphere.Center, sphere.Radius) for sphere in observed["spheres"]]
        offsets, indices = oracle.assign_clusters(
            PROJECTION, TILES_X, TILES_Y, SLICES, NEAR, FAR, Matrix.Identity, spheres)
        self.assertEqual(list(observed["offsets"]), offsets)
        self.assertEqual(list(observed["indices"]), indices)

    def test_it_still_matches_under_a_view_that_is_not_the_identity(self) -> None:
        """An identity view would hide a missing world-to-view transform."""
        view = Matrix.CreateLookAt(Vector3(3.0, 2.0, 7.0), Vector3(0.0, 0.5, -4.0),
                                   Vector3(0.0, 1.0, 0.0))

        def body(lights, grid, assignment, out):
            out["offsets"] = assignment.offsets()
            out["indices"] = assignment.indices()

        observed = self._assign(body, view=view)
        spheres = [(sphere.Center, sphere.Radius) for sphere in observed["spheres"]]
        offsets, indices = oracle.assign_clusters(
            PROJECTION, TILES_X, TILES_Y, SLICES, NEAR, FAR, view, spheres)
        self.assertEqual(list(observed["offsets"]), offsets)
        self.assertEqual(list(observed["indices"]), indices)

    def test_the_counts_describe_the_lists_they_summarise(self) -> None:
        def body(lights, grid, assignment, out):
            out.update(light_count=assignment.light_count,
                       cluster_count=assignment.cluster_count,
                       total=assignment.total_reference_count,
                       busiest=assignment.max_lights_per_cluster,
                       offsets=assignment.offsets(), indices=assignment.indices())

        observed = self._assign(body)
        self.assertEqual(observed["light_count"], len(self.LIGHTS))
        self.assertEqual(observed["cluster_count"], TILES_X * TILES_Y * SLICES)
        self.assertEqual(observed["total"], len(observed["indices"]))
        self.assertEqual(len(observed["offsets"]), observed["cluster_count"] + 1)
        self.assertEqual(observed["offsets"][-1], observed["total"])
        widths = [high - low for low, high in zip(observed["offsets"],
                                                  observed["offsets"][1:])]
        self.assertEqual(observed["busiest"], max(widths))

    def test_one_clusters_lights_are_its_slice_of_the_packed_list(self) -> None:
        def body(lights, grid, assignment, out):
            offsets, indices = assignment.offsets(), assignment.indices()
            out["per_cluster"] = [
                (assignment.lights_in_cluster(cluster),
                 tuple(indices[offsets[cluster]:offsets[cluster + 1]]))
                for cluster in range(assignment.cluster_count)]

        for asked, sliced in self._assign(body)["per_cluster"]:
            self.assertEqual(asked, sliced)

    def test_a_cluster_outside_the_assignment_is_refused(self) -> None:
        def body(lights, grid, assignment, out):
            for cluster in (assignment.cluster_count, -1):
                try:
                    assignment.lights_in_cluster(cluster)
                    out[cluster] = None
                except EngineError as error:
                    out[cluster] = type(error).__name__

        for key, value in self._assign(body).items():
            if isinstance(key, int):
                self.assertIsNotNone(value, key)

    def test_clearing_drops_every_list(self) -> None:
        def body(lights, grid, assignment, out):
            assignment.clear()
            out.update(offsets=assignment.offsets(), indices=assignment.indices(),
                       total=assignment.total_reference_count,
                       clusters=assignment.cluster_count,
                       busiest=assignment.max_lights_per_cluster)

        observed = self._assign(body)
        self.assertEqual(observed["indices"], ())
        self.assertEqual(observed["total"], 0)
        self.assertEqual(observed["clusters"], 0)
        self.assertEqual(observed["busiest"], 0)

    def test_reassigning_replaces_rather_than_appends(self) -> None:
        def body(lights, grid, assignment, out):
            out["first"] = assignment.total_reference_count
            assignment.assign(grid, Matrix.Identity, lights.bounds())
            out["second"] = assignment.total_reference_count

        observed = self._assign(body)
        self.assertEqual(observed["first"], observed["second"])

    def test_a_list_built_elsewhere_can_be_adopted(self) -> None:
        def body(lights, grid, assignment, out):
            offsets, indices = assignment.offsets(), assignment.indices()
            with ClusteredLightAssignment(lights._device) as adopted:
                adopted.adopt(assignment.light_count, offsets, indices)
                out.update(offsets=adopted.offsets(), indices=adopted.indices(),
                           lights=adopted.light_count,
                           clusters=adopted.cluster_count,
                           busiest=adopted.max_lights_per_cluster)
            out["original"] = (offsets, indices, assignment.max_lights_per_cluster)

        observed = self._assign(body)
        offsets, indices, busiest = observed["original"]
        self.assertEqual(observed["offsets"], offsets)
        self.assertEqual(observed["indices"], indices)
        self.assertEqual(observed["clusters"], len(offsets) - 1)
        self.assertEqual(observed["busiest"], busiest)

    def test_a_malformed_adopted_list_is_refused_rather_than_lighting_the_wrong_thing(self) -> None:
        """Each rule CNA states, given its own broken list."""
        broken = {
            "offsets do not start at zero": (2, [1, 2], [0, 1]),
            "offsets go backwards": (2, [0, 2, 1], [0, 1]),
            "the last offset is not the length": (2, [0, 1], [0, 1]),
            "an index names no light": (1, [0, 2], [0, 5]),
            "a negative index": (2, [0, 2], [0, -1]),
            "no clusters at all": (1, [], []),
        }

        def body(game, device, out):
            with ClusteredLightAssignment(device) as assignment:
                for name, (count, offsets, indices) in broken.items():
                    try:
                        assignment.adopt(count, offsets, indices)
                        out[name] = None
                    except EngineError as error:
                        out[name] = type(error).__name__

        for name, value in in_game(body).items():
            self.assertIsNotNone(value, name)

    def test_assigning_against_a_grid_with_no_projection_is_refused(self) -> None:
        def body(game, device, out):
            with ClusteredLightGrid(device, 2, 2, 2) as grid, \
                    ClusteredLightAssignment(device) as assignment:
                try:
                    assignment.assign(grid, Matrix.Identity,
                                      [BoundingSphere(Vector3(0.0, 0.0, -5.0), 1.0)])
                    out["raised"] = None
                except EngineStateError as error:
                    out["raised"] = type(error).__name__

        self.assertEqual(in_game(body)["raised"], "EngineStateError")

    def test_more_lights_than_the_assignment_accepts_are_refused(self) -> None:
        self.assertEqual(CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS, 1024)

        def body(game, device, out):
            with ClusteredLightGrid(device, 1, 1, 1) as grid, \
                    ClusteredLightAssignment(device) as assignment:
                grid.set_projection(PROJECTION, NEAR, FAR)
                spheres = [BoundingSphere(Vector3(0.0, 0.0, -5.0), 1.0)
                           ] * (CLUSTERED_ASSIGNMENT_MAXIMUM_LIGHTS + 1)
                try:
                    assignment.assign(grid, Matrix.Identity, spheres)
                    out["raised"] = None
                except EngineError as error:
                    out["raised"] = type(error).__name__

        self.assertIsNotNone(in_game(body)["raised"])

    def test_no_lights_assigns_nothing_rather_than_failing(self) -> None:
        def body(lights, grid, assignment, out):
            out.update(offsets=assignment.offsets(), indices=assignment.indices())

        observed = self._assign(body, lights=())
        self.assertEqual(observed["indices"], ())
        self.assertEqual(set(observed["offsets"]), {0})

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(game, device, out):
            with ClusteredLightAssignment(device) as assignment:
                try:
                    assignment.assign(object(), Matrix.Identity, [])
                    out["raised"] = None
                except TypeError:
                    out["raised"] = "TypeError"

        self.assertEqual(in_game(body)["raised"], "TypeError")


# --- the shadow budget --------------------------------------------------------


@requires_engine
class ClusteredShadowPolicyTests(unittest.TestCase):
    #: Three shadow casters at increasing distance, plus one that asks for nothing.
    #: In range of the camera, so the falloff is non-zero and the ranking is real.
    CASTERS = (_point(Vector3(1.0, 0.0, -2.0), range_=30.0, intensity=1.0,
                      color=Vector3(1.0, 1.0, 1.0), casts_shadows=True),
               _point(Vector3(4.0, 0.0, -4.0), range_=30.0, intensity=1.0,
                      color=Vector3(1.0, 1.0, 1.0), casts_shadows=True),
               _point(Vector3(9.0, 0.0, -9.0), range_=30.0, intensity=1.0,
                      color=Vector3(1.0, 1.0, 1.0), casts_shadows=True),
               _point(Vector3(2.0, 0.0, -3.0), range_=30.0, intensity=5.0,
                      color=Vector3(1.0, 1.0, 1.0), casts_shadows=False))
    CAMERA = Vector3(0.0, 0.0, 0.0)

    def _policy(self, body, budget=CLUSTERED_SHADOW_DEFAULT_BUDGET, lights=None):
        lights = self.CASTERS if lights is None else lights

        def run(game, device, observed):
            with ClusteredLightSet(device) as light_set, \
                    ClusteredShadowPolicy(device, budget) as policy:
                for light in lights:
                    light_set.add(light)
                body(light_set, policy, observed)

        return in_game(run)

    def test_the_defaults_are_measured_constants(self) -> None:
        self.assertEqual(CLUSTERED_SHADOW_DEFAULT_BUDGET, 4)
        self.assertAlmostEqual(CLUSTERED_SHADOW_DEFAULT_HYSTERESIS, 1.25, places=6)
        observed = self._policy(lambda lights, policy, out: out.update(
            budget=policy.budget, hysteresis=policy.hysteresis))
        self.assertEqual(observed["budget"], CLUSTERED_SHADOW_DEFAULT_BUDGET)
        self.assertAlmostEqual(observed["hysteresis"],
                               CLUSTERED_SHADOW_DEFAULT_HYSTERESIS, places=6)

    def test_every_score_matches_one_computed_independently(self) -> None:
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["scores"] = [policy.score(index) for index in range(len(lights))]

        scores = self._policy(body)["scores"]
        for index, light in enumerate(self.CASTERS):
            expected = (0.0 if not light.casts_shadows else
                        oracle.shadow_policy_score(light.color, light.intensity,
                                                   light.range_, light.position,
                                                   self.CAMERA))
            self.assertAlmostEqual(scores[index], expected, places=5, msg=f"light {index}")

    def test_a_light_that_asks_for_no_shadow_is_not_a_request(self) -> None:
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out.update(requests=policy.request_count, selected=policy.selected(),
                       refused=policy.refused_count)

        observed = self._policy(body)
        self.assertEqual(observed["requests"], 3)
        self.assertEqual(observed["refused"],
                         max(0, observed["requests"] - len(observed["selected"])))
        self.assertNotIn(3, observed["selected"])

    def test_the_budget_is_what_is_granted_and_the_rest_are_refused(self) -> None:
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out.update(selected=policy.selected(), refused=policy.refused_count,
                       flags=[policy.is_selected(index) for index in range(len(lights))])

        observed = self._policy(body, budget=1)
        self.assertEqual(len(observed["selected"]), 1)
        self.assertEqual(observed["refused"], 2)
        self.assertEqual([index for index, flag in enumerate(observed["flags"]) if flag],
                         list(observed["selected"]))

    def test_the_nearest_bright_light_wins_the_only_slot(self) -> None:
        """Ranked by score, which the oracle also ranks -- so the winner is checked."""
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["selected"] = policy.selected()

        expected = max(
            (index for index, light in enumerate(self.CASTERS) if light.casts_shadows),
            key=lambda index: oracle.shadow_policy_score(
                self.CASTERS[index].color, self.CASTERS[index].intensity,
                self.CASTERS[index].range_, self.CASTERS[index].position, self.CAMERA))
        self.assertEqual(self._policy(body, budget=1)["selected"], (expected,))

    def test_a_budget_of_zero_grants_nothing_and_refuses_everything(self) -> None:
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out.update(selected=policy.selected(), refused=policy.refused_count)

        observed = self._policy(body, budget=0)
        self.assertEqual(observed["selected"], ())
        self.assertEqual(observed["refused"], 3)

    def test_a_light_outside_the_view_scores_zero_and_still_has_a_score(self) -> None:
        """Dropped by scoring nothing rather than by disappearing, so score() explains it."""
        behind = _point(Vector3(0.0, 0.0, 40.0), range_=30.0, intensity=1.0,
                        color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)

        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out.update(score=policy.score(0), selected=policy.selected(),
                       requests=policy.request_count)

        observed = self._policy(body, lights=(behind,))
        self.assertEqual(observed["score"], 0.0)
        self.assertEqual(observed["selected"], ())
        self.assertEqual(observed["requests"], 1)

    def test_a_light_beyond_its_own_range_of_the_camera_scores_zero(self) -> None:
        far_away = _point(Vector3(0.0, 0.0, -20.0), range_=3.0, intensity=1.0,
                          color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)

        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["score"] = policy.score(0)

        self.assertEqual(self._policy(body, lights=(far_away,))["score"], 0.0)
        self.assertEqual(
            oracle.shadow_policy_score(far_away.color, far_away.intensity,
                                       far_away.range_, far_away.position, self.CAMERA),
            0.0)

    def test_hysteresis_keeps_an_incumbent_that_a_challenger_barely_beats(self) -> None:
        """The reason the bonus exists: a shadow map that changes hands every frame."""
        near = _point(Vector3(1.0, 0.0, -2.0), range_=30.0, intensity=1.0,
                      color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)
        rival = _point(Vector3(1.02, 0.0, -2.0), range_=30.0, intensity=1.02,
                       color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)

        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["first"] = policy.selected()
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["second"] = policy.selected()
            out["scores"] = (policy.score(0), policy.score(1))
            policy.reset()
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            out["after_reset"] = policy.selected()

        observed = self._policy(body, budget=1, lights=(near, rival))
        # Light 1 scores higher, so with no incumbent it wins.
        self.assertGreater(observed["scores"][1], observed["scores"][0])
        self.assertEqual(observed["first"], (1,))
        # And with hysteresis it keeps the slot rather than trading it.
        self.assertEqual(observed["second"], (1,))
        self.assertEqual(observed["after_reset"], (1,))

    def test_hysteresis_holds_a_weaker_incumbent_against_a_close_challenger(self) -> None:
        """The behaviour the multiplier buys, isolated."""
        weaker = _point(Vector3(1.0, 0.0, -2.0), range_=30.0, intensity=1.0,
                        color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)
        stronger = _point(Vector3(1.0, 0.0, -2.0), range_=30.0, intensity=1.1,
                          color=Vector3(1.0, 1.0, 1.0), casts_shadows=True)

        def body(game, device, out):
            with ClusteredLightSet(device) as lights, \
                    ClusteredShadowPolicy(device, 1) as policy:
                lights.add(weaker)
                policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
                out["alone"] = policy.selected()
                lights.add(stronger)
                policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
                out["with_rival"] = policy.selected()
                out["scores"] = (policy.score(0), policy.score(1))

        observed = in_game(body)
        self.assertEqual(observed["alone"], (0,))
        # 1.1 is closer than the 1.25 bonus, so the incumbent holds the slot.
        self.assertLess(observed["scores"][0] * 1.25 < observed["scores"][1], True)
        self.assertEqual(observed["with_rival"], (0,))

    def test_a_budget_below_zero_is_ignored_rather_than_refused(self) -> None:
        def body(lights, policy, out):
            out["before"] = policy.budget
            policy.budget = -1
            out["after"] = policy.budget
            policy.budget = 7
            out["accepted"] = policy.budget

        observed = self._policy(body, budget=2)
        self.assertEqual(observed["before"], 2)
        self.assertEqual(observed["after"], 2)
        self.assertEqual(observed["accepted"], 7)

    def test_a_hysteresis_below_one_is_ignored_rather_than_refused(self) -> None:
        def body(lights, policy, out):
            policy.hysteresis = 0.5
            out["ignored"] = policy.hysteresis
            policy.hysteresis = 2.5
            out["accepted"] = policy.hysteresis

        observed = self._policy(body)
        self.assertAlmostEqual(observed["ignored"],
                               CLUSTERED_SHADOW_DEFAULT_HYSTERESIS, places=6)
        self.assertAlmostEqual(observed["accepted"], 2.5, places=6)

    def test_a_negative_budget_at_construction_is_refused(self) -> None:
        def body(game, device, out):
            try:
                ClusteredShadowPolicy(device, -1).close()
                out["raised"] = None
            except EngineError as error:
                out["raised"] = type(error).__name__

        self.assertIsNotNone(in_game(body)["raised"])

    def test_a_score_for_a_light_that_was_not_selected_from_is_refused(self) -> None:
        def body(lights, policy, out):
            policy.select(lights, Matrix.Identity, PROJECTION, self.CAMERA)
            for index in (len(lights), -1):
                try:
                    policy.score(index)
                    out[index] = None
                except EngineError as error:
                    out[index] = type(error).__name__

        for key, value in self._policy(body).items():
            if isinstance(key, int):
                self.assertIsNotNone(value, key)


# --- the pure shading functions -----------------------------------------------


@requires_engine
class VolumeAttenuationTests(unittest.TestCase):
    """Beer-Lambert, checked against the closed form rather than the same three calls."""

    def test_it_matches_the_closed_form(self) -> None:
        for color, distance, thickness in (
                (Vector3(0.5, 0.25, 1.0), 2.0, 1.0),
                (Vector3(0.9, 0.1, 0.45), 3.5, 7.25),
                (Vector3(1.0, 1.0, 1.0), 1.0, 100.0)):
            got = volume_attenuation(color, distance, thickness)
            want = oracle.volume_attenuation(color, distance, thickness)
            for axis in ("X", "Y", "Z"):
                self.assertAlmostEqual(getattr(got, axis), getattr(want, axis),
                                       places=5, msg=f"{color} {distance} {thickness}")

    def test_no_medium_leaves_everything(self) -> None:
        for distance, thickness in ((0.0, 1.0), (2.0, 0.0), (-1.0, 1.0)):
            got = volume_attenuation(Vector3(0.5, 0.5, 0.5), distance, thickness)
            self.assertEqual((got.X, got.Y, got.Z), (1.0, 1.0, 1.0))

    def test_a_thicker_medium_transmits_less(self) -> None:
        values = [volume_attenuation(Vector3(0.5, 0.5, 0.5), 2.0, t / 4.0).X
                  for t in range(1, 12)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_a_black_channel_is_finite_rather_than_a_logarithm_of_zero(self) -> None:
        got = volume_attenuation(Vector3(0.0, 0.0, 0.0), 1.0, 1.0)
        self.assertTrue(all(math.isfinite(value) for value in (got.X, got.Y, got.Z)))


@requires_engine
class LightContributionTests(unittest.TestCase):
    SURFACE = Vector3(0.0, 0.0, 0.0)
    NORMAL = Vector3(0.0, 1.0, 0.0)
    CAMERA = Vector3(0.0, 2.0, 3.0)
    BASE = Vector3(0.8, 0.6, 0.4)

    def _contribution(self, light, **keywords) -> Vector3:
        return light_contribution(light, self.SURFACE, self.NORMAL, self.CAMERA,
                                  self.BASE, 0.0, 0.5, **keywords)

    def test_a_light_above_the_surface_contributes_something(self) -> None:
        value = self._contribution(_point(Vector3(0.0, 3.0, 0.0), range_=10.0))
        self.assertGreater(value.X + value.Y + value.Z, 0.0)

    def test_a_light_beyond_its_range_contributes_nothing(self) -> None:
        value = self._contribution(_point(Vector3(0.0, 30.0, 0.0), range_=10.0))
        self.assertEqual((value.X, value.Y, value.Z), (0.0, 0.0, 0.0))

    def test_a_light_below_the_surface_contributes_nothing(self) -> None:
        """The normal points up, so a light under the floor is behind it."""
        value = self._contribution(_point(Vector3(0.0, -3.0, 0.0), range_=10.0))
        self.assertEqual((value.X, value.Y, value.Z), (0.0, 0.0, 0.0))

    def test_it_falls_off_with_distance(self) -> None:
        values = [self._contribution(_point(Vector3(0.0, float(y), 0.0),
                                            range_=30.0)).Y
                  for y in range(1, 12)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_the_light_colour_reaches_the_answer(self) -> None:
        """A green light on a white-ish surface leaves more green than blue."""
        green = self._contribution(
            _point(Vector3(0.0, 3.0, 0.0), range_=10.0, color=Vector3(0.0, 1.0, 0.0)))
        self.assertGreater(green.Y, green.X)
        self.assertGreater(green.Y, green.Z)

    def test_a_spot_outside_its_cone_contributes_less_than_inside_it(self) -> None:
        inside = self._contribution(
            _spot(Vector3(0.0, 3.0, 0.0), Vector3(0.0, -1.0, 0.0), range_=10.0,
                  outer=0.6, inner=0.2))
        outside = self._contribution(
            _spot(Vector3(0.0, 3.0, 0.0), Vector3(1.0, 0.0, 0.0), range_=10.0,
                  outer=0.6, inner=0.2))
        self.assertGreater(inside.X + inside.Y + inside.Z,
                           outside.X + outside.Y + outside.Z)

    def test_the_extended_terms_change_the_answer(self) -> None:
        """A clearcoat is a second specular lobe, so it cannot leave the value alone."""
        plain = self._contribution(_point(Vector3(0.0, 3.0, 0.0), range_=10.0))
        coated = self._contribution(_point(Vector3(0.0, 3.0, 0.0), range_=10.0),
                                    clearcoat=1.0, clearcoat_roughness=0.1)
        self.assertNotEqual((plain.X, plain.Y, plain.Z),
                            (coated.X, coated.Y, coated.Z))

    def test_an_extensions_object_is_the_second_route_and_agrees_with_the_first(self) -> None:
        light = _point(Vector3(0.0, 3.0, 0.0), range_=10.0)
        with PbrMaterialExtensions() as extensions:
            extensions.clearcoat_factor = 1.0
            extensions.clearcoat_roughness = 0.1
            through_object = self._contribution(light, extensions=extensions)
        through_terms = self._contribution(light, clearcoat=1.0,
                                           clearcoat_roughness=0.1)
        for axis in ("X", "Y", "Z"):
            self.assertAlmostEqual(getattr(through_object, axis),
                                   getattr(through_terms, axis), places=5)

    def test_giving_both_an_extensions_object_and_terms_is_refused(self) -> None:
        light = _point(Vector3(0.0, 3.0, 0.0), range_=10.0)
        with PbrMaterialExtensions() as extensions:
            with self.assertRaises(TypeError):
                self._contribution(light, extensions=extensions, clearcoat=1.0)

    def test_it_refuses_the_wrong_kind_of_light(self) -> None:
        with self.assertRaises(TypeError):
            self._contribution(PointLight.default())


@requires_engine
class AreaLightShadingTests(unittest.TestCase):
    def test_the_lobe_scale_is_the_ggx_alpha_with_a_floor(self) -> None:
        for roughness in (-1.0, 0.0, 0.1, 0.1414, 0.25, 0.5, 0.75, 1.0, 2.0):
            self.assertAlmostEqual(lobe_scale_for(roughness),
                                   oracle.lobe_scale_for(roughness), places=6,
                                   msg=f"roughness {roughness}")

    def test_a_rectangle_quad_is_the_corners_its_axes_describe(self) -> None:
        from dataclasses import replace

        light = replace(AreaLight.default(), shape=AreaLightShape.Rectangle,
                        position=Vector3(1.0, 2.0, 3.0),
                        right_axis=Vector3(0.75, 0.0, 0.0),
                        up_axis=Vector3(0.0, 0.25, 0.0))
        corners = area_light_quad(light, Vector3(0.0, 0.0, 0.0))
        expected = oracle.area_light_quad(int(AreaLightShape.Rectangle), light.position,
                                          light.right_axis, light.up_axis)
        self.assertEqual(len(corners), AREA_LIGHT_QUAD_CORNER_COUNT)
        for got, want in zip(corners, expected):
            for axis in ("X", "Y", "Z"):
                self.assertAlmostEqual(getattr(got, axis), getattr(want, axis), places=6)

    def test_a_disc_quad_encloses_the_area_a_disc_encloses(self) -> None:
        from dataclasses import replace

        light = replace(AreaLight.default(), shape=AreaLightShape.Disc,
                        position=Vector3(0.0, 0.0, 0.0),
                        right_axis=Vector3(0.5, 0.0, 0.0),
                        up_axis=Vector3(0.0, 0.25, 0.0))
        corners = area_light_quad(light, Vector3(0.0, 0.0, 0.0))
        width = corners[1].X - corners[0].X
        height = corners[2].Y - corners[1].Y
        self.assertAlmostEqual(width * height, math.pi * 0.5 * 0.25, places=5)

    def test_a_rectangle_quad_does_not_depend_on_the_surface(self) -> None:
        light = AreaLight.default()
        here = area_light_quad(light, Vector3(0.0, -1.0, 0.0))
        there = area_light_quad(light, Vector3(4.0, -9.0, 7.0))
        self.assertEqual([(p.X, p.Y, p.Z) for p in here],
                         [(p.X, p.Y, p.Z) for p in there])

    def test_a_tube_quad_turns_to_face_the_surface(self) -> None:
        """Billboarded, which is the whole reason one quad serves three shapes."""
        from dataclasses import replace

        light = replace(AreaLight.default(), shape=AreaLightShape.Tube,
                        position=Vector3(0.0, 0.0, 0.0),
                        right_axis=Vector3(1.0, 0.0, 0.0),
                        up_axis=Vector3(0.0, 0.25, 0.0))
        below = area_light_quad(light, Vector3(0.0, -3.0, 0.0))
        aside = area_light_quad(light, Vector3(0.0, 0.0, -3.0))
        self.assertNotEqual([(p.X, p.Y, p.Z) for p in below],
                            [(p.X, p.Y, p.Z) for p in aside])
        # Its axis is unchanged; only the facing half-extent turns.
        self.assertAlmostEqual(below[1].X - below[0].X, 2.0, places=5)
        self.assertAlmostEqual(aside[1].X - aside[0].X, 2.0, places=5)

    def test_a_one_sided_light_emits_from_the_face_its_winding_names(self) -> None:
        """The default light lies in the z = 0 plane and emits toward +z.

        Which face that is, is a fact about the corner order rather than
        something the values say, so it is measured: a surface on the +z side
        sees it one-sided, and one on the -z side sees nothing until the light
        is two-sided.
        """
        light = AreaLight.default()
        in_front = Vector3(0.0, 0.0, 2.0)
        behind = Vector3(0.0, 0.0, -2.0)
        self.assertGreater(
            area_light_coverage(area_light_quad(light, in_front), in_front,
                                Vector3(0.0, 0.0, -1.0), 1.0, False), 0.0)
        self.assertEqual(
            area_light_coverage(area_light_quad(light, behind), behind,
                                Vector3(0.0, 0.0, 1.0), 1.0, False), 0.0)

    def test_coverage_is_a_fraction_and_is_zero_facing_away(self) -> None:
        light = AreaLight.default()
        surface = Vector3(0.0, 0.0, 2.0)
        quad = area_light_quad(light, surface)
        facing = area_light_coverage(quad, surface, Vector3(0.0, 0.0, -1.0), 1.0, False)
        away = area_light_coverage(quad, surface, Vector3(0.0, 0.0, 1.0), 1.0, False)
        self.assertGreater(facing, 0.0)
        self.assertLessEqual(facing, 1.0)
        self.assertEqual(away, 0.0)

    def test_a_surface_in_the_lights_own_plane_sees_it_edge_on(self) -> None:
        """A quad seen edge-on subtends nothing, whichever side it emits from."""
        light = AreaLight.default()
        surface = Vector3(0.0, -2.0, 0.0)
        quad = area_light_quad(light, surface)
        for two_sided in (False, True):
            self.assertEqual(
                area_light_coverage(quad, surface, Vector3(0.0, 1.0, 0.0), 1.0,
                                    two_sided), 0.0)

    def test_a_two_sided_light_covers_from_behind_as_well(self) -> None:
        light = AreaLight.default()
        surface = Vector3(0.0, 0.0, -2.0)
        quad = area_light_quad(light, surface)
        one_sided = area_light_coverage(quad, surface, Vector3(0.0, 0.0, 1.0), 1.0,
                                        False)
        two_sided = area_light_coverage(quad, surface, Vector3(0.0, 0.0, 1.0), 1.0,
                                        True)
        self.assertEqual(one_sided, 0.0)
        self.assertGreater(two_sided, 0.0)
        # And from the emitting side the two agree, because there is only one face.
        front = Vector3(0.0, 0.0, 2.0)
        front_quad = area_light_quad(light, front)
        self.assertEqual(
            area_light_coverage(front_quad, front, Vector3(0.0, 0.0, -1.0), 1.0, False),
            area_light_coverage(front_quad, front, Vector3(0.0, 0.0, -1.0), 1.0, True))

    def test_coverage_falls_as_the_surface_moves_away(self) -> None:
        light = AreaLight.default()
        values = []
        for distance in range(1, 10):
            surface = Vector3(0.0, 0.0, float(distance))
            quad = area_light_quad(light, surface)
            values.append(area_light_coverage(quad, surface, Vector3(0.0, 0.0, -1.0),
                                              1.0, False))
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertGreater(values[0], 0.0)

    def test_a_narrow_lobe_sees_more_of_the_light_than_a_wide_one(self) -> None:
        """The lobe scale widens the quad by its inverse; that is what tighter means."""
        light = AreaLight.default()
        surface = Vector3(0.0, 0.0, 2.0)
        quad = area_light_quad(light, surface)
        values = [area_light_coverage(quad, surface, Vector3(0.0, 0.0, -1.0), scale,
                                      False)
                  for scale in (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0)]
        self.assertEqual(values, sorted(values, reverse=True))
        # A lobe narrow enough sees the light as filling almost the whole
        # hemisphere, and the fraction is still capped at one.
        self.assertGreater(values[0], 0.9)
        self.assertLessEqual(values[0], 1.0)

    def test_a_quad_of_the_wrong_length_is_refused_here_rather_than_read_past(self) -> None:
        with self.assertRaises(ValueError):
            area_light_coverage([Vector3(0.0, 0.0, 0.0)] * 3, Vector3(0.0, 0.0, 0.0),
                                Vector3(0.0, 1.0, 0.0), 1.0, False)

    def test_two_sided_must_be_a_real_bool(self) -> None:
        """CNA refuses a non-canonical byte; this refuses before it gets there."""
        quad = area_light_quad(AreaLight.default(), Vector3(0.0, 0.0, 0.0))
        with self.assertRaises(TypeError):
            area_light_coverage(quad, Vector3(0.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0),
                                1.0, 1)

    def test_a_valid_light_in_front_of_a_surface_contributes_something(self) -> None:
        """The default light emits toward +z, so the surface faces it from there."""
        value = area_light_contribution(AreaLight.default(), Vector3(0.0, 0.0, 2.0),
                                        Vector3(0.0, 0.0, -1.0), Vector3(0.0, 0.0, 4.0),
                                        Vector3(0.8, 0.8, 0.8), 0.0, 0.5)
        self.assertGreater(value.X + value.Y + value.Z, 0.0)

    def test_an_invalid_light_contributes_nothing(self) -> None:
        from dataclasses import replace

        light = replace(AreaLight.default(), range_=0.0)
        self.assertFalse(light.is_valid)
        value = area_light_contribution(light, Vector3(0.0, 0.0, 2.0),
                                        Vector3(0.0, 0.0, -1.0), Vector3(0.0, 0.0, 4.0),
                                        Vector3(0.8, 0.8, 0.8), 0.0, 0.5)
        self.assertEqual((value.X, value.Y, value.Z), (0.0, 0.0, 0.0))

    def test_a_light_beyond_its_range_contributes_nothing(self) -> None:
        from dataclasses import replace

        light = replace(AreaLight.default(), position=Vector3(0.0, 0.0, 100.0),
                        range_=5.0)
        value = area_light_contribution(light, Vector3(0.0, 0.0, 2.0),
                                        Vector3(0.0, 0.0, -1.0), Vector3(0.0, 0.0, 4.0),
                                        Vector3(0.8, 0.8, 0.8), 0.0, 0.5)
        self.assertEqual((value.X, value.Y, value.Z), (0.0, 0.0, 0.0))

    def test_it_refuses_the_wrong_kind_of_light(self) -> None:
        with self.assertRaises(TypeError):
            area_light_quad(PointLight.default(), Vector3(0.0, 0.0, 0.0))


@requires_engine
class BrdfEvaluationTests(unittest.TestCase):
    """A Monte Carlo integral: checked against its properties, not a transcription.

    Reimplementing importance-sampled GGX here would copy CNA's arithmetic rather
    than independently derive it, and an oracle that is the same code is no
    oracle. What *can* be checked independently is what the integral must be: a
    fraction of incoming energy, a unit direction, monotone in the right
    variables, and convergent in the sample count.
    """

    def test_every_term_is_in_the_range_it_has_to_be(self) -> None:
        for roughness in (0.02, 0.25, 0.5, 0.75, 1.0):
            for cosine in (0.05, 0.3, 0.6, 1.0):
                terms = evaluate_brdf(roughness, cosine)
                self.assertGreaterEqual(terms.magnitude, 0.0)
                self.assertLessEqual(terms.magnitude, 1.0)
                self.assertGreaterEqual(terms.fresnel, 0.0)
                self.assertLessEqual(terms.fresnel, 1.0)

    def test_the_average_direction_is_a_unit_vector_in_its_plane(self) -> None:
        """Two components describe it, so they must square to one."""
        for roughness in (0.1, 0.4, 0.8):
            for cosine in (0.2, 0.5, 0.95):
                terms = evaluate_brdf(roughness, cosine)
                length = math.hypot(terms.average_tangent, terms.average_normal)
                self.assertAlmostEqual(length, 1.0, places=4,
                                       msg=f"roughness {roughness} cos {cosine}")

    def test_a_mirror_seen_head_on_reflects_almost_everything(self) -> None:
        terms = evaluate_brdf(0.02, 1.0)
        self.assertGreater(terms.magnitude, 0.99)
        # Straight back along the normal, so nothing leans to the side.
        self.assertAlmostEqual(terms.average_tangent, 0.0, places=4)
        self.assertAlmostEqual(terms.average_normal, 1.0, places=4)

    def test_a_rougher_surface_carries_less_of_the_lobe(self) -> None:
        values = [evaluate_brdf(r / 10.0, 0.8).magnitude for r in range(1, 11)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_it_is_deterministic(self) -> None:
        """A Monte Carlo integral over a fixed low-discrepancy sequence, not a random one."""
        self.assertEqual(evaluate_brdf(0.37, 0.61), evaluate_brdf(0.37, 0.61))

    def test_more_samples_converge_rather_than_wander(self) -> None:
        reference = evaluate_brdf(0.5, 0.5, 4096).magnitude
        errors = [abs(evaluate_brdf(0.5, 0.5, count).magnitude - reference)
                  for count in (16, 64, 256, 1024)]
        self.assertLess(errors[-1], errors[0])

    def test_a_sample_count_that_is_not_positive_is_refused(self) -> None:
        for count in (0, -1):
            with self.assertRaises(EngineArgumentError):
                evaluate_brdf(0.5, 0.5, count)

    def test_the_default_sample_count_is_the_measured_constant(self) -> None:
        self.assertEqual(AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT, 64)
        self.assertEqual(evaluate_brdf(0.4, 0.7),
                         evaluate_brdf(0.4, 0.7,
                                       AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT))

    def test_the_terms_repr_names_its_own_values(self) -> None:
        terms = evaluate_brdf(0.5, 0.5)
        text = repr(terms)
        self.assertIn("AreaLightBrdfTerms", text)
        self.assertIn(repr(terms.magnitude), text)


@requires_engine
class PublishedGlslTests(unittest.TestCase):
    """The GLSL CNA publishes beside each CPU function, so the two can be compared."""

    def test_each_source_is_non_empty_glsl_naming_what_it_declares(self) -> None:
        for name, source, expected in (
                ("light lookup", light_lookup_glsl(), "uCnaClusterTable"),
                ("BRDF lookup", brdf_lookup_glsl(), "vec"),
                ("area shading", area_light_shading_glsl(), "vec")):
            self.assertGreater(len(source), 100, name)
            self.assertIn(expected, source, name)

    def test_the_light_lookup_declares_the_uniforms_bind_sets(self) -> None:
        """The two halves of one contract: bind sets exactly these names."""
        source = light_lookup_glsl()
        for uniform in ("uCnaLightData", "uCnaClusterTable", "uCnaLightIndices",
                        "uCnaTilesX", "uCnaTilesY", "uCnaSliceCount",
                        "uCnaLightCount", "uCnaGridNear", "uCnaGridFar"):
            self.assertIn(uniform, source, uniform)

    def test_asking_twice_gives_the_same_source(self) -> None:
        self.assertEqual(light_lookup_glsl(), light_lookup_glsl())


# --- what needs a renderer ----------------------------------------------------


@requires_engine_gpu
class ClusteredLightBufferTests(unittest.TestCase):
    LIGHTS = (_point(Vector3(1.5, 0.25, -6.0), range_=4.0),
              _spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0)))

    def _uploaded(self, body):
        def run(game, device, observed):
            with ClusteredLightSet(device) as lights, \
                    ClusteredLightGrid(device, TILES_X, TILES_Y, SLICES) as grid, \
                    ClusteredLightAssignment(device) as assignment, \
                    ClusteredLightBuffer(device) as buffer:
                grid.set_projection(PROJECTION, NEAR, FAR)
                for light in self.LIGHTS:
                    lights.add(light)
                assignment.assign(grid, Matrix.Identity, lights.bounds())
                body(lights, grid, assignment, buffer, observed)

        return in_game(run)

    def test_a_new_buffer_holds_nothing(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            out.update(uploaded=buffer.is_uploaded, lights=buffer.light_count,
                       clusters=buffer.cluster_count,
                       references=buffer.reference_count)

        observed = self._uploaded(body)
        self.assertFalse(observed["uploaded"])
        self.assertEqual((observed["lights"], observed["clusters"],
                          observed["references"]), (0, 0, 0))

    def test_uploading_carries_the_counts_of_what_it_was_given(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            buffer.upload(lights, grid, assignment)
            out.update(uploaded=buffer.is_uploaded, lights=buffer.light_count,
                       clusters=buffer.cluster_count,
                       references=buffer.reference_count,
                       expected=(len(lights), grid.cluster_count,
                                 assignment.total_reference_count))

        observed = self._uploaded(body)
        self.assertTrue(observed["uploaded"])
        self.assertEqual((observed["lights"], observed["clusters"],
                          observed["references"]), observed["expected"])

    def test_a_mismatched_trio_is_refused_rather_than_lighting_the_wrong_thing(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            # An assignment built for a different grid.
            with ClusteredLightGrid(lights._device, 1, 1, 1) as other, \
                    ClusteredLightAssignment(lights._device) as mismatched:
                other.set_projection(PROJECTION, NEAR, FAR)
                mismatched.assign(other, Matrix.Identity, lights.bounds())
                try:
                    buffer.upload(lights, grid, mismatched)
                    out["wrong_grid"] = None
                except EngineError as error:
                    out["wrong_grid"] = type(error).__name__
            # An assignment built for a different set of lights.
            with ClusteredLightAssignment(lights._device) as fewer:
                fewer.assign(grid, Matrix.Identity, lights.bounds()[:1])
                try:
                    buffer.upload(lights, grid, fewer)
                    out["wrong_lights"] = None
                except EngineError as error:
                    out["wrong_lights"] = type(error).__name__
            out["still_empty"] = buffer.is_uploaded

        observed = self._uploaded(body)
        self.assertIsNotNone(observed["wrong_grid"])
        self.assertIsNotNone(observed["wrong_lights"])
        self.assertFalse(observed["still_empty"])

    def test_binding_before_uploading_is_refused(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            with ClusteredForwardEffect(lights._device) as shader_effect:
                try:
                    buffer.bind(shader_effect.shader, 0)
                    out["raised"] = None
                except EngineError as error:
                    out["raised"] = type(error).__name__

        self.assertIsNotNone(self._uploaded(body)["raised"])

    def test_binding_after_uploading_reaches_a_real_source_compiled_effect(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            buffer.upload(lights, grid, assignment)
            with ClusteredForwardEffect(lights._device) as shader_effect:
                buffer.bind(shader_effect.shader, 0)
                out["bound"] = True

        self.assertTrue(self._uploaded(body)["bound"])

    def test_an_effect_that_was_not_compiled_from_source_is_refused(self) -> None:
        """Measured: the buffer sets uniforms by name, which bytecode has none of."""
        def body(lights, grid, assignment, buffer, out):
            from Microsoft.Xna.Framework.Graphics import Effect

            buffer.upload(lights, grid, assignment)
            effect = Effect(lights._device)
            try:
                buffer.bind(effect, 0)
                out["raised"] = None
            except EngineArgumentError as error:
                out["raised"] = type(error).__name__
            finally:
                effect.Dispose()

        self.assertEqual(self._uploaded(body)["raised"], "EngineArgumentError")

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(lights, grid, assignment, buffer, out):
            for call in (lambda: buffer.upload(object(), grid, assignment),
                         lambda: buffer.upload(lights, object(), assignment),
                         lambda: buffer.upload(lights, grid, object()),
                         lambda: buffer.bind(object(), 0)):
                try:
                    call()
                    out.setdefault("results", []).append("no error")
                except TypeError:
                    out.setdefault("results", []).append("TypeError")

        self.assertEqual(self._uploaded(body)["results"], ["TypeError"] * 4)


@requires_engine_gpu
class ClusteredLightComputeTests(unittest.TestCase):
    LIGHTS = (_point(Vector3(1.5, 0.25, -6.0), range_=4.0),
              _spot(Vector3(0.0, 3.0, -9.0), Vector3(0.0, -1.0, 0.0)),
              _point(Vector3(-8.0, -2.5, -30.0), range_=12.0))

    def _both_paths(self, body, stride=CLUSTERED_COMPUTE_DEFAULT_STRIDE):
        def run(game, device, observed):
            with ClusteredLightSet(device) as lights, \
                    ClusteredLightGrid(device, TILES_X, TILES_Y, SLICES) as grid, \
                    ClusteredLightAssignment(device) as cpu, \
                    ClusteredLightAssignment(device) as gpu, \
                    ClusteredLightCompute(device, stride) as compute:
                grid.set_projection(PROJECTION, NEAR, FAR)
                for light in self.LIGHTS:
                    lights.add(light)
                spheres = lights.bounds()
                cpu.assign(grid, Matrix.Identity, spheres)
                compute.assign(grid, Matrix.Identity, spheres, gpu)
                body(compute, cpu, gpu, observed)

        return in_game(run)

    def test_the_two_paths_agree_exactly(self) -> None:
        """Not plausibly: the same lists, entry for entry. That is the design claim."""
        def body(compute, cpu, gpu, out):
            out.update(supported=compute.is_supported, used=compute.used_compute,
                       cpu_offsets=cpu.offsets(), gpu_offsets=gpu.offsets(),
                       cpu_indices=cpu.indices(), gpu_indices=gpu.indices(),
                       overflowed=compute.has_overflowed)

        observed = self._both_paths(body)
        self.assertEqual(observed["cpu_offsets"], observed["gpu_offsets"])
        self.assertEqual(observed["cpu_indices"], observed["gpu_indices"])
        self.assertFalse(observed["overflowed"])
        # And both agree with the independent oracle, so neither is checking itself.
        self.assertEqual(observed["used"], observed["supported"])

    def test_the_gpu_result_matches_the_independent_oracle_too(self) -> None:
        def body(compute, cpu, gpu, out):
            out.update(offsets=gpu.offsets(), indices=gpu.indices())

        observed = self._both_paths(body)
        spheres = []
        for light in self.LIGHTS:
            if light.kind is ClusteredLightKind.Point:
                spheres.append(oracle.point_light_bounds(light.position, light.range_))
            else:
                spheres.append(oracle.spot_light_bounds(
                    light.position, light.direction, light.range_, light.outer_angle))
        offsets, indices = oracle.assign_clusters(
            PROJECTION, TILES_X, TILES_Y, SLICES, NEAR, FAR, Matrix.Identity, spheres)
        self.assertEqual(list(observed["offsets"]), offsets)
        self.assertEqual(list(observed["indices"]), indices)

    def test_it_reports_which_path_ran_and_why(self) -> None:
        def body(compute, cpu, gpu, out):
            out.update(supported=compute.is_supported, used=compute.used_compute,
                       reason=compute.unsupported_reason, stride=compute.stride)

        observed = self._both_paths(body)
        self.assertEqual(observed["stride"], CLUSTERED_COMPUTE_DEFAULT_STRIDE)
        if observed["supported"]:
            self.assertTrue(observed["used"])
            self.assertEqual(observed["reason"], "")
        else:
            self.assertFalse(observed["used"])
            self.assertTrue(observed["reason"])

    def test_a_stride_of_one_overflows_and_says_so(self) -> None:
        """Nothing is dropped silently: the flag is the whole point of the stride."""
        def body(compute, cpu, gpu, out):
            out.update(supported=compute.is_supported,
                       overflowed=compute.has_overflowed,
                       busiest=gpu.max_lights_per_cluster,
                       cpu_busiest=cpu.max_lights_per_cluster)

        observed = self._both_paths(body, stride=1)
        if observed["supported"] and observed["cpu_busiest"] > 1:
            self.assertTrue(observed["overflowed"])
            self.assertLessEqual(observed["busiest"], 1)

    def test_a_stride_that_is_not_positive_is_refused(self) -> None:
        def body(game, device, out):
            for stride in (0, -4):
                try:
                    ClusteredLightCompute(device, stride).close()
                    out[stride] = None
                except EngineError as error:
                    out[stride] = type(error).__name__

        for key, value in in_game(body).items():
            self.assertIsNotNone(value, key)

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(game, device, out):
            with ClusteredLightCompute(device) as compute, \
                    ClusteredLightAssignment(device) as assignment, \
                    ClusteredLightGrid(device, 2, 2, 2) as grid:
                for call in (lambda: compute.assign(object(), Matrix.Identity, [],
                                                    assignment),
                             lambda: compute.assign(grid, Matrix.Identity, [],
                                                    object())):
                    try:
                        call()
                        out.setdefault("results", []).append("no error")
                    except TypeError:
                        out.setdefault("results", []).append("TypeError")

        self.assertEqual(in_game(body)["results"], ["TypeError"] * 2)


@requires_engine_gpu
class AreaLightBrdfTableTests(unittest.TestCase):
    def _table(self, body, size=None, sample_count=None):
        def run(game, device, observed):
            with AreaLightBrdfTable(device, size, sample_count) as table:
                body(table, observed)

        return in_game(run)

    def test_the_defaults_are_the_measured_constants(self) -> None:
        self.assertEqual(AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE, 32)
        observed = self._table(lambda table, out: out.update(
            size=table.size, samples=table.sample_count))
        self.assertEqual(observed["size"], AREA_LIGHT_BRDF_TABLE_DEFAULT_SIZE)
        self.assertEqual(observed["samples"],
                         AREA_LIGHT_BRDF_TABLE_DEFAULT_SAMPLE_COUNT)

    def test_a_table_can_be_built_at_another_size(self) -> None:
        observed = self._table(lambda table, out: out.update(
            size=table.size, samples=table.sample_count), size=8, sample_count=16)
        self.assertEqual((observed["size"], observed["samples"]), (8, 16))

    def test_the_texture_is_the_size_the_table_says(self) -> None:
        def body(table, out):
            texture = table.texture
            out["present"] = texture is not None
            if texture is not None:
                out.update(width=texture.Width, height=texture.Height,
                           size=table.size)

        observed = self._table(body, size=8, sample_count=16)
        if observed["present"]:
            self.assertEqual((observed["width"], observed["height"]),
                             (observed["size"], observed["size"]))

    def test_the_texture_is_one_view_however_often_it_is_read(self) -> None:
        """Reading in a loop must not leak a handle per read -- see ENGINE-002."""
        def body(table, out):
            first = table.texture
            out["same"] = all(table.texture is first for _ in range(20))

        self.assertTrue(self._table(body, size=8, sample_count=16)["same"])

    def test_closing_the_table_disposes_the_view_it_handed_out(self) -> None:
        def body(game, device, out):
            table = AreaLightBrdfTable(device, 8, 16)
            texture = table.texture
            table.close()
            out["disposed"] = texture is None or bool(texture.IsDisposed)

        self.assertTrue(in_game(body)["disposed"])

    def test_building_it_takes_a_measurable_and_finite_time(self) -> None:
        observed = self._table(lambda table, out: out.update(
            ms=table.generation_milliseconds), size=8, sample_count=16)
        self.assertGreaterEqual(observed["ms"], 0.0)
        self.assertTrue(math.isfinite(observed["ms"]))

    def test_giving_only_one_of_size_and_sample_count_is_refused(self) -> None:
        def body(game, device, out):
            for arguments in ((8, None), (None, 16)):
                try:
                    AreaLightBrdfTable(device, *arguments).close()
                    out[arguments] = None
                except TypeError:
                    out[arguments] = "TypeError"

        for key, value in in_game(body).items():
            self.assertEqual(value, "TypeError", key)


@requires_engine_gpu
class ClusteredForwardEffectTests(unittest.TestCase):
    def _effect(self, body):
        def run(game, device, observed):
            with ClusteredForwardEffect(device) as effect:
                body(effect, device, observed)

        return in_game(run)

    def test_it_reports_whether_the_renderer_can_run_it(self) -> None:
        observed = self._effect(lambda effect, device, out: out.update(
            supported=effect.is_supported, shader=effect.shader is not None))
        self.assertIs(type(observed["supported"]), bool)
        if observed["supported"]:
            self.assertTrue(observed["shader"])

    def test_the_shader_is_one_view_however_often_it_is_read(self) -> None:
        def body(effect, device, out):
            first = effect.shader
            out["same"] = all(effect.shader is first for _ in range(20))

        self.assertTrue(self._effect(body)["same"])

    def test_closing_the_effect_disposes_the_shader_it_handed_out(self) -> None:
        def body(game, device, out):
            effect = ClusteredForwardEffect(device)
            shader = effect.shader
            effect.close()
            out["disposed"] = shader is None or bool(shader.IsDisposed)

        self.assertTrue(in_game(body)["disposed"])

    def test_the_material_scalars_clamp_where_cna_clamps_them(self) -> None:
        """Each bound is a different shape, so each is checked with its own values."""
        def body(effect, device, out):
            out["metallic"] = [(value, setattr(effect, "metallic", value)
                                or effect.metallic)
                               for value in (-0.5, 0.0, 0.375, 1.0, 2.0)]
            out["roughness"] = [(value, setattr(effect, "roughness", value)
                                 or effect.roughness)
                                for value in (0.0, 0.02, 0.04, 0.5, 1.0, 3.0)]
            out["ior"] = [(value, setattr(effect, "ior", value) or effect.ior)
                          for value in (0.375, 1.0, 1.5, 2.0)]

        observed = self._effect(body)
        self.assertEqual(observed["metallic"],
                         [(-0.5, 0.0), (0.0, 0.0), (0.375, 0.375), (1.0, 1.0),
                          (2.0, 1.0)])
        # 0.04 is not representable in single precision; the floor is the float
        # CNA actually holds, not the decimal it is written as.
        self.assertEqual([kept for _, kept in observed["roughness"]],
                         [oracle.f32(0.04), oracle.f32(0.04), oracle.f32(0.04),
                          0.5, 1.0, 1.0])
        # ior ignores a value below one rather than clamping it, so the previous
        # value survives: 0.375 leaves the default in place.
        self.assertEqual([kept for _, kept in observed["ior"]][1:], [1.0, 1.5, 2.0])
        self.assertGreaterEqual(observed["ior"][0][1], 1.0)

    def test_the_base_colour_clamps_and_the_ambient_only_floors(self) -> None:
        """Two different rules, which is why they are two assertions."""
        def body(effect, device, out):
            effect.base_color = Vector3(-1.0, 0.5, 2.0)
            out["base"] = effect.base_color
            effect.ambient = Vector3(-1.0, 0.5, 2.0)
            out["ambient"] = effect.ambient

        observed = self._effect(body)
        self.assertEqual((observed["base"].X, observed["base"].Y, observed["base"].Z),
                         (0.0, 0.5, 1.0))
        self.assertEqual((observed["ambient"].X, observed["ambient"].Y,
                          observed["ambient"].Z), (0.0, 0.5, 2.0))

    def test_the_opaque_frame_is_the_callers_own_object(self) -> None:
        def body(effect, device, out):
            from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

            out["before"] = effect.opaque_frame
            texture = Texture2D(device, 4, 4, False, SurfaceFormat.Color)
            try:
                effect.opaque_frame = texture
                out["same_object"] = effect.opaque_frame is texture
                effect.opaque_frame = None
                out["after"] = effect.opaque_frame
            finally:
                texture.Dispose()

        observed = self._effect(body)
        self.assertIsNone(observed["before"])
        self.assertTrue(observed["same_object"])
        self.assertIsNone(observed["after"])

    def test_the_material_extensions_are_one_view_and_are_the_effects_own(self) -> None:
        def body(effect, device, out):
            first = effect.material_extensions
            out["same"] = all(effect.material_extensions is first for _ in range(10))
            with PbrMaterialExtensions() as given:
                given.clearcoat_factor = 0.625
                effect.material_extensions = given
            out["kept"] = effect.material_extensions.clearcoat_factor

        observed = self._effect(body)
        self.assertTrue(observed["same"])
        # The setter copies out of the caller's object, so the value survives the
        # caller's object being closed.
        self.assertAlmostEqual(observed["kept"], 0.625, places=6)

    def test_closing_the_effect_disposes_the_extensions_view(self) -> None:
        def body(game, device, out):
            effect = ClusteredForwardEffect(device)
            extensions = effect.material_extensions
            effect.close()
            out["closed"] = extensions.is_closed

        self.assertTrue(in_game(body)["closed"])

    def test_an_area_light_can_be_set_cleared_and_asked_about(self) -> None:
        def body(effect, device, out):
            with AreaLightBrdfTable(device, 8, 16) as table:
                out["before"] = effect.has_area_light
                effect.set_area_light(AreaLight.default(), table)
                out["after"] = effect.has_area_light
                effect.clear_area_light()
                out["cleared"] = effect.has_area_light

        observed = self._effect(body)
        self.assertFalse(observed["before"])
        self.assertTrue(observed["after"])
        self.assertFalse(observed["cleared"])

    def test_an_invalid_area_light_clears_rather_than_being_refused(self) -> None:
        """A measured behaviour that reads as a no-op unless it is stated."""
        from dataclasses import replace

        def body(effect, device, out):
            with AreaLightBrdfTable(device, 8, 16) as table:
                effect.set_area_light(AreaLight.default(), table)
                out["set"] = effect.has_area_light
                effect.set_area_light(replace(AreaLight.default(), range_=0.0), table)
                out["after_invalid"] = effect.has_area_light

        observed = self._effect(body)
        self.assertTrue(observed["set"])
        self.assertFalse(observed["after_invalid"])

    def test_a_light_probe_can_be_asked_about_and_cleared(self) -> None:
        """Setting one arrives with the light-probe family; clearing is here."""
        def body(effect, device, out):
            out["before"] = effect.has_light_probe
            effect.clear_light_probe()
            out["after"] = effect.has_light_probe

        observed = self._effect(body)
        self.assertFalse(observed["before"])
        self.assertFalse(observed["after"])

    def test_beginning_with_an_empty_light_buffer_is_refused(self) -> None:
        def body(effect, device, out):
            with ClusteredLightBuffer(device) as buffer:
                try:
                    effect.begin(Matrix.Identity, Matrix.Identity, PROJECTION,
                                 Vector3(0.0, 0.0, 0.0), buffer)
                    out["raised"] = None
                except EngineError as error:
                    out["raised"] = type(error).__name__

        self.assertIsNotNone(self._effect(body)["raised"])

    def test_beginning_with_a_filled_buffer_sets_the_frames_uniforms(self) -> None:
        def body(effect, device, out):
            with ClusteredLightSet(device) as lights, \
                    ClusteredLightGrid(device, TILES_X, TILES_Y, SLICES) as grid, \
                    ClusteredLightAssignment(device) as assignment, \
                    ClusteredLightBuffer(device) as buffer:
                grid.set_projection(PROJECTION, NEAR, FAR)
                lights.add(_point(Vector3(1.5, 0.25, -6.0)))
                assignment.assign(grid, Matrix.Identity, lights.bounds())
                buffer.upload(lights, grid, assignment)
                effect.begin(Matrix.Identity, Matrix.Identity, PROJECTION,
                             Vector3(0.0, 1.0, 3.0), buffer)
                out["began"] = True

        self.assertTrue(self._effect(body)["began"])

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(effect, device, out):
            for call in (lambda: effect.begin(Matrix.Identity, Matrix.Identity,
                                              PROJECTION, Vector3(0.0, 0.0, 0.0),
                                              object()),
                         lambda: setattr(effect, "material_extensions", object()),
                         lambda: setattr(effect, "opaque_frame", object()),
                         lambda: effect.set_area_light(object(), object())):
                try:
                    call()
                    out.setdefault("results", []).append("no error")
                except TypeError:
                    out.setdefault("results", []).append("TypeError")

        self.assertEqual(self._effect(body)["results"], ["TypeError"] * 4)


# --- the boundaries the whole family shares -----------------------------------


@requires_engine
class ClusteredConstructorTests(unittest.TestCase):
    def test_the_owning_game_parameter_takes_a_device_and_refuses_a_game(self) -> None:
        """ENGINE-006, pinned so it fails the day CNA changes either side.

        ``engine_layer.h`` documents the first parameter of four constructors as
        "the owning game". The C layer resolves it as a graphics device, and a
        real game handle is refused with ``CNA_RESULT_INVALID_HANDLE``.
        """
        from _cna_native.loader import get_library

        def body(game, device, out):
            library = get_library()
            handle = c.c_uint64()
            create = library.cna_clustered_light_set_create
            out["with_game"] = int(create(c.c_uint64(game._host.handle),
                                          c.byref(handle)))
            out["game_handle_returned"] = int(handle.value)
            out["with_device"] = int(create(c.c_uint64(device._require_handle()),
                                            c.byref(handle)))
            if handle.value:
                library.cna_clustered_light_set_destroy(handle)

        observed = in_game(body)
        self.assertEqual(observed["with_game"], 2, "expected CNA_RESULT_INVALID_HANDLE")
        self.assertEqual(observed["game_handle_returned"], 0)
        self.assertEqual(observed["with_device"], 0)

    def test_every_constructor_refuses_something_that_is_not_a_device(self) -> None:
        for build in (lambda d: ClusteredLightSet(d),
                      lambda d: ClusteredLightGrid(d, 2, 2, 2),
                      lambda d: ClusteredLightAssignment(d),
                      lambda d: ClusteredShadowPolicy(d),
                      lambda d: ClusteredLightBuffer(d),
                      lambda d: ClusteredLightCompute(d),
                      lambda d: ClusteredForwardEffect(d),
                      lambda d: AreaLightBrdfTable(d)):
            with self.assertRaises(TypeError):
                build(object())

    def test_every_owned_object_closes_once_twice_and_then_refuses(self) -> None:
        def body(game, device, out):
            builders = {
                "set": lambda: ClusteredLightSet(device),
                "grid": lambda: ClusteredLightGrid(device, 2, 2, 2),
                "assignment": lambda: ClusteredLightAssignment(device),
                "policy": lambda: ClusteredShadowPolicy(device),
            }
            for name, build in builders.items():
                thing = build()
                thing.close()
                thing.close()
                try:
                    thing._handle.value
                    out[name] = None
                except EngineDisposedError as error:
                    out[name] = type(error).__name__

        for name, value in in_game(body).items():
            self.assertEqual(value, "EngineDisposedError", name)


class ClusteredAbsenceTests(unittest.TestCase):
    """What the family answers on a build with no engine layer at all.

    ``UNSUPPORTED`` and ``UNAVAILABLE`` are different facts and the control
    artifact is what proves the API tells them apart.
    """

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_every_route_that_needs_the_layer_says_so_rather_than_answering(self) -> None:
        for name, call in (
                ("is_usable", lambda: ClusteredLight.default().is_usable),
                ("lobe_scale_for", lambda: lobe_scale_for(0.5)),
                ("volume_attenuation",
                 lambda: volume_attenuation(Vector3(0.5, 0.5, 0.5), 1.0, 1.0)),
                ("evaluate_brdf", lambda: evaluate_brdf(0.5, 0.5)),
                ("light_lookup_glsl", light_lookup_glsl),
                ("brdf_lookup_glsl", brdf_lookup_glsl),
                ("area_light_shading_glsl", area_light_shading_glsl),
                ("area_light_quad",
                 lambda: area_light_quad(AreaLight.default(), Vector3(0.0, 0.0, 2.0))),
                ("area_light_contribution",
                 lambda: area_light_contribution(
                     AreaLight.default(), Vector3(0.0, 0.0, 2.0),
                     Vector3(0.0, 0.0, -1.0), Vector3(0.0, 0.0, 4.0),
                     Vector3(0.8, 0.8, 0.8), 0.0, 0.5))):
            with self.subTest(name), self.assertRaises(EngineUnavailableError):
                call()

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_the_two_routes_that_answer_without_the_layer_still_answer(self) -> None:
        """Measured, and what ``engine_layer.h`` documents for each.

        Filling a value with its canonical defaults is a fact about the
        structure, so both ``_init`` routes answer everywhere; so does
        ``AreaLight.is_valid``, documented as "SUCCESS in every build".
        ``ClusteredLight.is_usable`` is the deliberate opposite, because that
        rule belongs to the light *set* -- and it is checked above.
        """
        self.assertIsInstance(ClusteredLight.default(), ClusteredLight)
        self.assertIsInstance(AreaLight.default(), AreaLight)
        self.assertTrue(AreaLight.default().is_valid)

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_a_constructor_reports_the_layer_as_absent(self) -> None:
        def body(game, device, out):
            try:
                ClusteredLightSet(device).close()
                out["raised"] = None
            except EngineUnavailableError as error:
                out["raised"] = type(error).__name__

        self.assertEqual(in_game(body)["raised"], "EngineUnavailableError")
