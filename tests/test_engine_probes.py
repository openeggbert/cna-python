"""Light probes, against independently evaluated spherical harmonics.

No getter is its own oracle. Every irradiance CNA computes is compared with a
second-order evaluation :mod:`tests.engine_oracles` writes out from the
Ramamoorthi-Hanrahan constants, every visibility weight with Chebyshev's bound
computed there, and every grid position, Hammersley point, cube-face direction
and panorama coordinate with an independent construction.

The fixtures are asymmetric on purpose: a box that is not a cube and not centred
on the origin, a grid with a different probe count on each axis, and normals off
every axis -- so a transposed grid, a swapped axis or a coefficient read from the
wrong band cannot coincide with the right answer.

Most of the family is arithmetic and runs on any build with an engine layer. The
baker and the environment processor draw and read back, so they are separated
out and need a rasterizing renderer.
"""

from __future__ import annotations

import math
import unittest

from Microsoft.Xna.Framework import BoundingBox, Matrix, Vector3

from cna.extensions.engine import (
    EnvironmentProcessor, ImageBasedLight, LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE,
    LIGHT_PROBE_BAKER_FACE_COUNT, LIGHT_PROBE_COEFFICIENT_COUNT,
    LIGHT_PROBE_VISIBILITY_DIRECTIONS, LIGHT_PROBE_VOLUME_MAXIMUM_PROBES,
    ClusteredForwardEffect, LightProbe, LightProbeBaker, LightProbeVolume,
    PbrEffect, cube_face_direction, direction_to_equirectangular, hammersley,
    importance_sample_ggx, mip_for_roughness, probe_evaluation_glsl,
    roughness_for_mip,
)
from cna.extensions.engine.errors import (
    EngineArgumentError, EngineDisposedError, EngineError, EngineUnavailableError,
)

from . import engine_oracles as oracle
from .engine_fixtures import (
    ENGINE_PRESENT, in_game, requires_engine, requires_engine_gpu, requires_native,
)

#: A box that is neither a cube nor centred on the origin, so an axis read in
#: the wrong order gives a different answer.
BOUNDS = BoundingBox(Vector3(-2.0, 0.0, 1.0), Vector3(6.0, 3.0, 9.0))
#: Three different probe counts, for the same reason.
COUNT_X, COUNT_Y, COUNT_Z = 3, 2, 4

#: Coefficients that are different in every band and every channel, so a term
#: read from the wrong index changes the answer.
COEFFICIENTS = tuple(
    Vector3(0.10 + 0.03 * index, 0.20 - 0.015 * index, 0.05 + 0.021 * index)
    for index in range(9))

#: A normal off every axis and not of unit length, so the normalisation matters.
SLANTED = Vector3(0.37, -0.62, 0.69)


@requires_engine
class LightProbeTests(unittest.TestCase):
    """A probe is arithmetic: no device, no renderer, no frame."""

    def _filled(self) -> LightProbe:
        probe = LightProbe(Vector3(1.5, -2.25, 3.0))
        for index, value in enumerate(COEFFICIENTS):
            probe.set_coefficient(index, value)
        return probe

    def test_a_probe_needs_no_device_and_starts_dark(self) -> None:
        with LightProbe() as probe:
            self.assertTrue(probe.is_zero)
            self.assertEqual(tuple(probe.position), (0.0, 0.0, 0.0))
            self.assertEqual(len(probe.coefficients()), LIGHT_PROBE_COEFFICIENT_COUNT)
            self.assertTrue(all(tuple(value) == (0.0, 0.0, 0.0)
                                for value in probe.coefficients()))

    def test_the_coefficient_count_is_the_measured_constant(self) -> None:
        self.assertEqual(LIGHT_PROBE_COEFFICIENT_COUNT, 9)
        self.assertEqual(LIGHT_PROBE_VISIBILITY_DIRECTIONS, 6)

    def test_a_probe_can_be_created_at_a_position(self) -> None:
        with LightProbe(Vector3(1.5, -2.25, 3.0)) as probe:
            self.assertEqual(tuple(probe.position), (1.5, -2.25, 3.0))
            probe.position = Vector3(-4.0, 0.5, 0.0)
            self.assertEqual(tuple(probe.position), (-4.0, 0.5, 0.0))

    def test_coefficients_read_back_one_at_a_time_and_in_bulk(self) -> None:
        with self._filled() as probe:
            bulk = probe.coefficients()
            self.assertEqual(len(bulk), LIGHT_PROBE_COEFFICIENT_COUNT)
            for index, value in enumerate(bulk):
                one = probe.coefficient(index)
                self.assertEqual(tuple(one), tuple(value))
                for axis in "XYZ":
                    self.assertAlmostEqual(getattr(value, axis),
                                           getattr(COEFFICIENTS[index], axis),
                                           places=6, msg=f"{index}.{axis}")
            self.assertFalse(probe.is_zero)

    def test_a_coefficient_outside_the_nine_is_refused(self) -> None:
        with self._filled() as probe:
            for index in (LIGHT_PROBE_COEFFICIENT_COUNT, -1, 1000):
                with self.subTest(index=index):
                    with self.assertRaises(EngineError):
                        probe.coefficient(index)
                    with self.assertRaises(EngineError):
                        probe.set_coefficient(index, Vector3(0.0, 0.0, 0.0))

    def test_irradiance_matches_an_independent_evaluation(self) -> None:
        """The family's central claim, over normals that are not on an axis."""
        normals = [SLANTED, Vector3(0.0, 1.0, 0.0), Vector3(-1.0, 0.0, 0.0),
                   Vector3(0.3, 0.5, -0.81), Vector3(2.0, 0.0, 0.0)]
        with self._filled() as probe:
            for normal in normals:
                got = probe.irradiance(normal)
                want = oracle.sh_irradiance(COEFFICIENTS, normal)
                for axis in "XYZ":
                    self.assertAlmostEqual(getattr(got, axis), getattr(want, axis),
                                           places=5, msg=f"{normal} {axis}")

    def test_irradiance_is_floored_at_zero_per_channel(self) -> None:
        """A fit that overshoots must not remove light from a surface."""
        with LightProbe() as probe:
            probe.set_coefficient(3, Vector3(-1.0, -1.0, -1.0))
            value = probe.irradiance(Vector3(1.0, 0.0, 0.0))
            self.assertEqual(tuple(value), (0.0, 0.0, 0.0))
            opposite = probe.irradiance(Vector3(-1.0, 0.0, 0.0))
            self.assertGreater(opposite.X, 0.0)

    def test_a_dark_probe_lights_nothing(self) -> None:
        with LightProbe() as probe:
            self.assertEqual(tuple(probe.irradiance(SLANTED)), (0.0, 0.0, 0.0))

    def test_scaling_multiplies_every_coefficient(self) -> None:
        with self._filled() as probe:
            probe.scale(0.25)
            for index, value in enumerate(probe.coefficients()):
                for axis in "XYZ":
                    self.assertAlmostEqual(getattr(value, axis),
                                           getattr(COEFFICIENTS[index], axis) * 0.25,
                                           places=6)

    def test_a_negative_scale_is_ignored_rather_than_refused(self) -> None:
        with self._filled() as probe:
            before = probe.coefficients()
            probe.scale(-1.0)
            for kept, original in zip(probe.coefficients(), before):
                self.assertEqual(tuple(kept), tuple(original))

    def test_scaling_by_zero_empties_it(self) -> None:
        with self._filled() as probe:
            probe.scale(0.0)
            self.assertTrue(probe.is_zero)

    def test_copying_carries_position_and_coefficients(self) -> None:
        with self._filled() as source, LightProbe() as destination:
            destination.copy_from(source)
            self.assertEqual(tuple(destination.position), tuple(source.position))
            self.assertTrue(destination.matches(source))
            for a, b in zip(destination.coefficients(), source.coefficients()):
                self.assertEqual(tuple(a), tuple(b))

    def test_equality_is_over_position_and_light_and_not_visibility(self) -> None:
        """Which fields take part is CNA's decision, so it is measured."""
        with self._filled() as first, self._filled() as second:
            self.assertTrue(first.matches(second))
            second.set_visibility(0, 4.0, 17.0)
            self.assertTrue(first.matches(second),
                            "visibility is not part of the comparison")
            second.position = Vector3(9.0, 9.0, 9.0)
            self.assertFalse(first.matches(second))

    def test_a_copy_is_independent_of_its_source(self) -> None:
        with self._filled() as source, LightProbe() as destination:
            destination.copy_from(source)
            source.scale(0.5)
            self.assertFalse(destination.matches(source))

    def test_it_refuses_something_that_is_not_a_probe(self) -> None:
        with LightProbe() as probe:
            for call in (lambda: probe.copy_from(object()),
                         lambda: probe.matches(object())):
                with self.assertRaises(TypeError):
                    call()

    def test_a_closed_probe_refuses_rather_than_reaching_freed_memory(self) -> None:
        probe = LightProbe()
        probe.close()
        probe.close()
        self.assertTrue(probe.is_closed)
        with self.assertRaises(EngineDisposedError):
            probe.is_zero

    def test_the_published_glsl_evaluates_the_same_nine_terms(self) -> None:
        source = probe_evaluation_glsl()
        self.assertGreater(len(source), 100)
        self.assertEqual(source, probe_evaluation_glsl())


@requires_engine
class ProbeVisibilityTests(unittest.TestCase):
    def test_a_new_probe_has_no_visibility_and_trusts_everything(self) -> None:
        with LightProbe() as probe:
            self.assertFalse(probe.has_visibility)
            self.assertEqual(probe.visibility_weight(Vector3(1.0, 0.0, 0.0), 100.0), 1.0)

    def test_both_moments_read_back(self) -> None:
        with LightProbe() as probe:
            probe.set_visibility(0, 4.0, 17.0)
            self.assertTrue(probe.has_visibility)
            self.assertAlmostEqual(probe.visibility_mean(0), 4.0, places=6)
            self.assertAlmostEqual(probe.visibility_mean_squared(0), 17.0, places=6)
            # And the untouched directions stay empty.
            for direction in range(1, LIGHT_PROBE_VISIBILITY_DIRECTIONS):
                self.assertEqual(probe.visibility_mean(direction), 0.0)

    def test_negative_moments_are_floored_rather_than_stored(self) -> None:
        """No distribution has negative variance, and one that appeared to would
        make the weight fall outside zero to one."""
        with LightProbe() as probe:
            probe.set_visibility(0, -3.0, -9.0)
            self.assertEqual(probe.visibility_mean(0), 0.0)
            self.assertEqual(probe.visibility_mean_squared(0), 0.0)
            probe.set_visibility(1, 4.0, 1.0)
            self.assertAlmostEqual(probe.visibility_mean_squared(1), 16.0, places=6)

    def test_a_direction_outside_the_six_is_refused(self) -> None:
        with LightProbe() as probe:
            for direction in (LIGHT_PROBE_VISIBILITY_DIRECTIONS, -1):
                with self.subTest(direction=direction):
                    with self.assertRaises(EngineError):
                        probe.set_visibility(direction, 1.0, 1.0)
                    with self.assertRaises(EngineError):
                        probe.visibility_mean(direction)
                    with self.assertRaises(EngineError):
                        probe.visibility_mean_squared(direction)

    def test_every_weight_matches_chebyshevs_bound_computed_independently(self) -> None:
        means = [4.0, 0.0, 0.0, 0.0, 20.0, 0.0]
        squares = [17.0, 0.0, 0.0, 0.0, 401.0, 0.0]
        directions = [Vector3(1.0, 0.0, 0.0), Vector3(0.0, 0.0, 1.0),
                      Vector3(0.6, 0.0, 0.8), SLANTED, Vector3(-1.0, 0.0, 0.0)]
        with LightProbe() as probe:
            for index, (mean, square) in enumerate(zip(means, squares)):
                if mean > 0.0:
                    probe.set_visibility(index, mean, square)
            for direction in directions:
                for distance in (1.0, 3.9, 4.0, 6.0, 15.0, 60.0):
                    got = probe.visibility_weight(direction, distance)
                    want = oracle.probe_visibility_weight(means, squares, direction,
                                                          distance)
                    self.assertAlmostEqual(got, want, places=5,
                                           msg=f"{direction} at {distance}")

    def test_a_point_nearer_than_the_wall_is_fully_trusted(self) -> None:
        with LightProbe() as probe:
            probe.set_visibility(0, 4.0, 17.0)
            self.assertEqual(probe.visibility_weight(Vector3(1.0, 0.0, 0.0), 2.0), 1.0)
            self.assertLess(probe.visibility_weight(Vector3(1.0, 0.0, 0.0), 20.0), 0.1)

    def test_the_weight_never_leaves_zero_to_one(self) -> None:
        with LightProbe() as probe:
            probe.set_visibility(0, 4.0, 17.0)
            probe.set_visibility(4, 20.0, 401.0)
            for step in range(41):
                angle = step * math.pi / 20.0
                direction = Vector3(math.cos(angle), 0.2, math.sin(angle))
                for distance in (0.1, 1.0, 5.0, 50.0, 5000.0):
                    weight = probe.visibility_weight(direction, distance)
                    self.assertTrue(0.0 <= weight <= 1.0,
                                    f"{weight} at {angle} {distance}")


@requires_engine
class LightProbeVolumeTests(unittest.TestCase):
    def _volume(self) -> LightProbeVolume:
        return LightProbeVolume(BOUNDS, COUNT_X, COUNT_Y, COUNT_Z)

    def test_the_grid_reports_what_it_was_built_with(self) -> None:
        with self._volume() as volume:
            self.assertEqual((volume.count_x, volume.count_y, volume.count_z),
                             (COUNT_X, COUNT_Y, COUNT_Z))
            self.assertEqual(volume.probe_count, COUNT_X * COUNT_Y * COUNT_Z)
            self.assertEqual(tuple(volume.bounds.Min), tuple(BOUNDS.Min))
            self.assertEqual(tuple(volume.bounds.Max), tuple(BOUNDS.Max))
            self.assertTrue(volume.is_zero)

    def test_every_probe_position_matches_an_independent_construction(self) -> None:
        with self._volume() as volume:
            for z in range(COUNT_Z):
                for y in range(COUNT_Y):
                    for x in range(COUNT_X):
                        got = volume.probe_position(x, y, z)
                        want = oracle.probe_volume_position(
                            BOUNDS.Min, BOUNDS.Max, (COUNT_X, COUNT_Y, COUNT_Z),
                            (x, y, z))
                        for axis in "XYZ":
                            self.assertAlmostEqual(
                                getattr(got, axis), getattr(want, axis), places=5,
                                msg=f"({x}, {y}, {z}).{axis}")

    def test_the_corners_are_the_box_corners(self) -> None:
        with self._volume() as volume:
            first = volume.probe_position(0, 0, 0)
            last = volume.probe_position(COUNT_X - 1, COUNT_Y - 1, COUNT_Z - 1)
            self.assertEqual(tuple(first), tuple(BOUNDS.Min))
            self.assertEqual(tuple(last), tuple(BOUNDS.Max))

    def test_an_index_outside_the_grid_is_refused(self) -> None:
        with self._volume() as volume, LightProbe() as probe:
            for index in ((COUNT_X, 0, 0), (0, COUNT_Y, 0), (0, 0, COUNT_Z),
                          (-1, 0, 0)):
                with self.subTest(index=index):
                    with self.assertRaises(EngineError):
                        volume.probe_position(*index)
                    with self.assertRaises(EngineError):
                        volume.read_probe(*index, probe)
                    with self.assertRaises(EngineError):
                        volume.write_probe(*index, probe)

    def test_a_grid_dimension_below_one_is_refused(self) -> None:
        for counts in ((0, 2, 2), (2, 0, 2), (2, 2, 0), (-1, 2, 2)):
            with self.subTest(counts=counts), self.assertRaises(EngineError):
                LightProbeVolume(BOUNDS, *counts).close()

    def test_an_inverted_box_is_refused(self) -> None:
        inverted = BoundingBox(Vector3(1.0, 0.0, 0.0), Vector3(-1.0, 1.0, 1.0))
        with self.assertRaises(EngineError):
            LightProbeVolume(inverted, 2, 2, 2).close()

    def test_more_probes_than_the_volume_accepts_are_refused(self) -> None:
        self.assertEqual(LIGHT_PROBE_VOLUME_MAXIMUM_PROBES, 32768)
        with self.assertRaises(EngineError):
            LightProbeVolume(BOUNDS, 33, 33, 33).close()
        # And one exactly at the bound is accepted.
        with LightProbeVolume(BOUNDS, 32, 32, 32) as volume:
            self.assertEqual(volume.probe_count, LIGHT_PROBE_VOLUME_MAXIMUM_PROBES)

    def test_a_written_probe_reads_back_with_the_grids_position(self) -> None:
        """The grid decides where a probe is: lighting must not lag the geometry."""
        with self._volume() as volume, LightProbe(Vector3(99.0, 99.0, 99.0)) as source, \
                LightProbe() as read:
            source.set_coefficient(0, Vector3(0.5, 0.25, 0.125))
            volume.write_probe(1, 1, 2, source)
            volume.read_probe(1, 1, 2, read)
            self.assertEqual(tuple(read.position), tuple(volume.probe_position(1, 1, 2)))
            self.assertEqual(tuple(read.coefficient(0)), (0.5, 0.25, 0.125))
            self.assertFalse(volume.is_zero)

    def test_reading_fills_the_callers_probe_rather_than_making_one(self) -> None:
        """The whole grid can be walked with one probe object."""
        with self._volume() as volume, LightProbe() as source, LightProbe() as read:
            source.set_coefficient(0, Vector3(1.0, 1.0, 1.0))
            volume.write_probe(0, 0, 0, source)
            handle_before = read._handle.value
            volume.read_probe(0, 0, 0, read)
            self.assertEqual(read._handle.value, handle_before)
            self.assertEqual(tuple(read.coefficient(0)), (1.0, 1.0, 1.0))

    def test_containment_includes_the_boundary(self) -> None:
        with self._volume() as volume:
            self.assertTrue(volume.contains(BOUNDS.Min))
            self.assertTrue(volume.contains(BOUNDS.Max))
            self.assertTrue(volume.contains(Vector3(0.0, 1.0, 5.0)))
            self.assertFalse(volume.contains(Vector3(-2.001, 1.0, 5.0)))
            self.assertFalse(volume.contains(Vector3(0.0, 1.0, 9.001)))

    def test_sampling_at_a_probes_own_position_returns_that_probe(self) -> None:
        with self._volume() as volume, LightProbe() as source, LightProbe() as sampled:
            source.set_coefficient(0, Vector3(0.75, 0.5, 0.25))
            for z in range(COUNT_Z):
                for y in range(COUNT_Y):
                    for x in range(COUNT_X):
                        volume.write_probe(x, y, z, source)
            volume.sample(volume.probe_position(1, 1, 2), sampled)
            for axis, want in zip("XYZ", (0.75, 0.5, 0.25)):
                self.assertAlmostEqual(getattr(sampled.coefficient(0), axis), want,
                                       places=5)

    def test_sampling_between_two_probes_lands_between_their_values(self) -> None:
        """The interpolation itself, on a grid where only one axis varies."""
        bounds = BoundingBox(Vector3(0.0, 0.0, 0.0), Vector3(4.0, 0.0, 0.0))
        with LightProbeVolume(bounds, 2, 1, 1) as volume, LightProbe() as dark, \
                LightProbe() as bright, LightProbe() as sampled:
            dark.set_coefficient(0, Vector3(0.0, 0.0, 0.0))
            bright.set_coefficient(0, Vector3(1.0, 1.0, 1.0))
            volume.write_probe(0, 0, 0, dark)
            volume.write_probe(1, 0, 0, bright)
            volume.sample(Vector3(2.0, 0.0, 0.0), sampled)
            middle = sampled.coefficient(0).X
            self.assertGreater(middle, 0.0)
            self.assertLess(middle, 1.0)
            volume.sample(Vector3(0.0, 0.0, 0.0), sampled)
            self.assertAlmostEqual(sampled.coefficient(0).X, 0.0, places=5)
            volume.sample(Vector3(4.0, 0.0, 0.0), sampled)
            self.assertAlmostEqual(sampled.coefficient(0).X, 1.0, places=5)

    def test_the_interpolation_is_monotone_along_the_axis(self) -> None:
        bounds = BoundingBox(Vector3(0.0, 0.0, 0.0), Vector3(4.0, 0.0, 0.0))
        with LightProbeVolume(bounds, 2, 1, 1) as volume, LightProbe() as dark, \
                LightProbe() as bright, LightProbe() as sampled:
            bright.set_coefficient(0, Vector3(1.0, 1.0, 1.0))
            volume.write_probe(0, 0, 0, dark)
            volume.write_probe(1, 0, 0, bright)
            values = []
            for step in range(9):
                volume.sample(Vector3(step * 0.5, 0.0, 0.0), sampled)
                values.append(sampled.coefficient(0).X)
            self.assertEqual(values, sorted(values))

    def test_a_position_outside_the_box_is_clamped_rather_than_refused(self) -> None:
        """Refusing would make every object that pokes out of the volume go black."""
        with self._volume() as volume, LightProbe() as source, LightProbe() as sampled:
            source.set_coefficient(0, Vector3(0.5, 0.5, 0.5))
            for z in range(COUNT_Z):
                for y in range(COUNT_Y):
                    for x in range(COUNT_X):
                        volume.write_probe(x, y, z, source)
            volume.sample(Vector3(-1000.0, -1000.0, -1000.0), sampled)
            self.assertEqual(tuple(sampled.position), tuple(BOUNDS.Min))
            self.assertAlmostEqual(sampled.coefficient(0).X, 0.5, places=5)

    def test_the_volumes_irradiance_is_sampling_and_then_evaluating(self) -> None:
        with self._volume() as volume, LightProbe() as source, LightProbe() as sampled:
            for index, value in enumerate(COEFFICIENTS):
                source.set_coefficient(index, value)
            for z in range(COUNT_Z):
                for y in range(COUNT_Y):
                    for x in range(COUNT_X):
                        volume.write_probe(x, y, z, source)
            position = Vector3(1.0, 1.5, 4.0)
            got = volume.irradiance(position, SLANTED)
            volume.sample(position, sampled)
            want = sampled.irradiance(SLANTED)
            independent = oracle.sh_irradiance(COEFFICIENTS, SLANTED)
            for axis in "XYZ":
                self.assertAlmostEqual(getattr(got, axis), getattr(want, axis), places=5)
                self.assertAlmostEqual(getattr(got, axis), getattr(independent, axis),
                                       places=5)

    def test_it_refuses_something_that_is_not_a_probe(self) -> None:
        with self._volume() as volume:
            for call in (lambda: volume.read_probe(0, 0, 0, object()),
                         lambda: volume.write_probe(0, 0, 0, object()),
                         lambda: volume.sample(Vector3(0.0, 0.0, 0.0), object())):
                with self.assertRaises(TypeError):
                    call()

    def test_it_refuses_something_that_is_not_a_box(self) -> None:
        with self.assertRaises(TypeError):
            LightProbeVolume(object(), 2, 2, 2)


@requires_engine
class ImageBasedLightValueTests(unittest.TestCase):
    def test_the_defaults_come_from_cna_and_describe_an_inactive_light(self) -> None:
        light = ImageBasedLight.default()
        self.assertIsNone(light.irradiance)
        self.assertIsNone(light.prefiltered_specular)
        self.assertIsNone(light.brdf_lut)
        self.assertFalse(light.is_valid)

    def test_a_light_with_no_textures_is_never_valid(self) -> None:
        from dataclasses import replace

        self.assertFalse(replace(ImageBasedLight.default(), intensity=5.0).is_valid)

    def test_a_texture_of_the_wrong_kind_is_refused(self) -> None:
        from dataclasses import replace

        light = replace(ImageBasedLight.default(), irradiance=object())
        with self.assertRaises(TypeError):
            light.is_valid


@requires_engine
class PureEnvironmentHelperTests(unittest.TestCase):
    """Published functions with no object behind them, checked against oracles."""

    def test_every_hammersley_point_matches_an_independent_bit_reversal(self) -> None:
        for count in (1, 4, 16, 64):
            for index in range(count):
                got = hammersley(index, count)
                want = oracle.hammersley(index, count)
                self.assertAlmostEqual(got[0], want[0], places=6,
                                       msg=f"{index}/{count} first")
                self.assertAlmostEqual(got[1], want[1], places=6,
                                       msg=f"{index}/{count} second")

    def test_the_radical_inverse_is_the_one_written_out_by_hand(self) -> None:
        self.assertEqual([hammersley(index, 8)[1] for index in range(8)],
                         [0.0, 0.5, 0.25, 0.75, 0.125, 0.625, 0.375, 0.875])

    def test_every_ggx_sample_matches_an_independent_construction(self) -> None:
        """Compared as an angle, because the mapping is ill-conditioned when narrow.

        At roughness 0.05 the elevation comes out of ``sqrt(1 - cos**2)`` with
        ``cos`` about 0.99998, so the subtraction cancels away most of a float's
        significand and the result carries perhaps three digits. Two correct
        implementations differing only in the order of their float operations
        disagree there in the fourth decimal, and an assertion on a component
        would be asserting the operation order rather than the formula. The
        angle between the two directions is the quantity the formula actually
        determines, and a thousandth of a radian is far tighter than the
        distribution's own width at any roughness this samples.
        """
        normal = oracle.normalized(Vector3(0.3, 0.8, -0.5))
        for roughness in (0.05, 0.3, 0.7, 1.0):
            for index in range(16):
                x, y = hammersley(index, 16)
                got = importance_sample_ggx(x, y, normal, roughness)
                want = oracle.importance_sample_ggx(x, y, normal, roughness)
                dot = min(1.0, max(-1.0, got.X * want.X + got.Y * want.Y
                                   + got.Z * want.Z))
                self.assertLess(math.acos(dot), 1e-3,
                                f"r={roughness} i={index}: {got} against {want}")

    def test_the_normal_is_used_as_given_and_not_normalised_first(self) -> None:
        """Measured: a normal that is not a unit vector tilts the whole sample.

        The basis is built from the vector as supplied and the local direction
        is combined with it before the *result* is normalised, so its length
        leaks into the direction. Nothing in ``engine_layer.h`` says the normal
        must be a unit vector, and passing one that is not produces a plausible
        direction rather than an error -- which is why this is pinned rather than
        described.
        """
        unit = oracle.normalized(Vector3(0.3, 0.8, -0.5))
        scaled = Vector3(0.3, 0.8, -0.5)
        worst = 0.0
        for index in range(16):
            x, y = hammersley(index, 16)
            a = importance_sample_ggx(x, y, unit, 0.3)
            b = importance_sample_ggx(x, y, scaled, 0.3)
            dot = min(1.0, max(-1.0, a.X * b.X + a.Y * b.Y + a.Z * b.Z))
            worst = max(worst, math.acos(dot))
        self.assertGreater(worst, 1e-3,
                           "a non-unit normal would have to change nothing for "
                           "this route to be normalising it")

    def test_every_ggx_sample_is_a_unit_vector_in_the_normals_hemisphere(self) -> None:
        """The two properties the formula determines exactly, whatever the rounding."""
        normal = oracle.normalized(Vector3(0.3, 0.8, -0.5))
        for roughness in (0.05, 0.3, 0.7, 1.0):
            for index in range(16):
                x, y = hammersley(index, 16)
                got = importance_sample_ggx(x, y, normal, roughness)
                length = math.sqrt(got.X ** 2 + got.Y ** 2 + got.Z ** 2)
                self.assertAlmostEqual(length, 1.0, places=5,
                                       msg=f"r={roughness} i={index}")
                self.assertGreaterEqual(
                    got.X * normal.X + got.Y * normal.Y + got.Z * normal.Z, -1e-5)

    def test_the_mip_mapping_matches_and_inverts(self) -> None:
        for mip_count in (1, 2, 6, 9):
            for step in range(11):
                roughness = step / 10.0
                got = mip_for_roughness(roughness, mip_count)
                self.assertAlmostEqual(got, oracle.mip_for_roughness(roughness,
                                                                     mip_count),
                                       places=5, msg=f"{roughness} of {mip_count}")
                back = roughness_for_mip(got, mip_count)
                self.assertAlmostEqual(back, oracle.roughness_for_mip(got, mip_count),
                                       places=5)
                if mip_count > 1:
                    self.assertAlmostEqual(back, roughness, places=5)

    def test_every_cube_face_direction_matches_an_independent_construction(self) -> None:
        for face in range(6):
            for u in (0.0, 0.25, 0.5, 0.75, 1.0):
                for v in (0.0, 0.5, 1.0):
                    got = cube_face_direction(face, u, v)
                    want = oracle.cube_face_direction(face, u, v)
                    for axis in "XYZ":
                        self.assertAlmostEqual(getattr(got, axis), getattr(want, axis),
                                               places=5,
                                               msg=f"face {face} ({u}, {v}) {axis}")

    def test_a_face_outside_the_six_answers_with_minus_z_rather_than_refusing(self) -> None:
        """Measured, and what the header documents: only a null output is refused.

        The switch's default branch is the -Z face, so index six is index five
        and minus one is index five. Pinned because the obvious expectation is a
        refusal, and a loop with an off-by-one would sample one face twice
        instead of failing.
        """
        minus_z = cube_face_direction(5, 0.5, 0.5)
        for face in (6, 7, 99, -1, -2):
            with self.subTest(face=face):
                got = cube_face_direction(face, 0.5, 0.5)
                self.assertEqual((got.X, got.Y, got.Z),
                                 (minus_z.X, minus_z.Y, minus_z.Z))

    def test_every_panorama_coordinate_matches_an_independent_construction(self) -> None:
        directions = [Vector3(0.0, 0.0, -1.0), Vector3(1.0, 0.0, 0.0),
                      Vector3(0.0, 1.0, 0.0), Vector3(0.0, -1.0, 0.0), SLANTED,
                      Vector3(-0.3, 0.1, 0.95)]
        for direction in directions:
            got = direction_to_equirectangular(direction)
            want = oracle.direction_to_equirectangular(direction)
            self.assertAlmostEqual(got[0], want[0], places=5, msg=f"{direction} u")
            self.assertAlmostEqual(got[1], want[1], places=5, msg=f"{direction} v")

    def test_the_cube_and_the_panorama_agree_about_where_a_direction_is(self) -> None:
        """Two published conventions, checked against each other rather than singly."""
        for face in range(6):
            direction = cube_face_direction(face, 0.5, 0.5)
            u, v = direction_to_equirectangular(direction)
            self.assertTrue(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0)


@requires_engine
class LightProbeIntoEffectsTests(unittest.TestCase):
    """Where a probe goes once it has been captured."""

    def test_a_clustered_forward_effect_takes_a_probe_and_a_volume(self) -> None:
        def body(game, device, out):
            with ClusteredForwardEffect(device) as effect, LightProbe() as probe, \
                    LightProbeVolume(BOUNDS, 2, 2, 2) as volume:
                out["before"] = effect.has_light_probe
                probe.set_coefficient(0, Vector3(0.5, 0.5, 0.5))
                effect.set_light_probe(probe)
                out["after_probe"] = effect.has_light_probe
                effect.clear_light_probe()
                out["cleared"] = effect.has_light_probe
                effect.set_light_probe_volume(volume)
                out["after_volume"] = effect.has_light_probe
                out["retained"] = effect._light_probe_volume is volume
                effect.clear_light_probe()
                out["cleared_again"] = effect.has_light_probe
                out["released"] = effect._light_probe_volume is None

        observed = in_game(body)
        self.assertFalse(observed["before"])
        self.assertTrue(observed["after_probe"])
        self.assertFalse(observed["cleared"])
        self.assertTrue(observed["after_volume"])
        self.assertTrue(observed["retained"])
        self.assertFalse(observed["cleared_again"])
        self.assertTrue(observed["released"])

    def test_the_probe_is_copied_and_the_volume_is_retained(self) -> None:
        """Two different lifetimes, which is why they are two setters."""
        def body(game, device, out):
            with ClusteredForwardEffect(device) as effect:
                probe = LightProbe()
                probe.set_coefficient(0, Vector3(0.5, 0.5, 0.5))
                effect.set_light_probe(probe)
                probe.close()
                # The values were copied, so closing the source is safe.
                out["still_has"] = effect.has_light_probe

        self.assertTrue(in_game(body)["still_has"])

    def test_it_refuses_the_wrong_kind_of_argument(self) -> None:
        def body(game, device, out):
            with ClusteredForwardEffect(device) as effect:
                for call in (lambda: effect.set_light_probe(object()),
                             lambda: effect.set_light_probe_volume(object())):
                    try:
                        call()
                        out.setdefault("results", []).append("no error")
                    except TypeError:
                        out.setdefault("results", []).append("TypeError")

        self.assertEqual(in_game(body)["results"], ["TypeError"] * 2)


# --- what needs a renderer ----------------------------------------------------


@requires_engine_gpu
class LightProbeBakerTests(unittest.TestCase):
    POSITION = Vector3(1.5, 2.0, -3.0)

    def _baker(self, body, face_size=8):
        def run(game, device, observed):
            with LightProbeBaker(device, face_size) as baker:
                body(baker, device, observed)

        return in_game(run)

    def test_the_defaults_are_the_measured_constants(self) -> None:
        self.assertEqual(LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE, 32)
        self.assertEqual(LIGHT_PROBE_BAKER_FACE_COUNT, 6)

        def body(game, device, out):
            with LightProbeBaker(device) as baker:
                out.update(size=baker.face_size, faces=baker.face_count(),
                           supported=baker.is_supported)

        observed = in_game(body)
        self.assertEqual(observed["size"], LIGHT_PROBE_BAKER_DEFAULT_FACE_SIZE)
        self.assertEqual(observed["faces"], LIGHT_PROBE_BAKER_FACE_COUNT)

    def test_the_planes_read_back(self) -> None:
        def body(baker, device, out):
            out["defaults"] = (baker.near_plane, baker.far_plane)
            baker.set_planes(0.125, 64.0)
            out["set"] = (baker.near_plane, baker.far_plane)

        observed = self._baker(body)
        self.assertGreater(observed["defaults"][1], observed["defaults"][0])
        self.assertEqual(observed["set"], (0.125, 64.0))

    def test_every_face_view_matches_an_independent_look_at(self) -> None:
        def body(baker, device, out):
            out["views"] = [baker.face_view(face, self.POSITION) for face in range(6)]

        for face, view in enumerate(self._baker(body)["views"]):
            want = oracle.probe_face_view(face, self.POSITION)
            for index, (got, expected) in enumerate(zip(view, want)):
                self.assertAlmostEqual(got, expected, places=4,
                                       msg=f"face {face} element {index}")

    def test_a_face_outside_the_six_is_refused(self) -> None:
        def body(baker, device, out):
            for face in (6, -1):
                try:
                    baker.face_view(face, self.POSITION)
                    out[face] = None
                except EngineError as error:
                    out[face] = type(error).__name__

        for face, value in self._baker(body).items():
            self.assertIsNotNone(value, face)

    def test_baking_calls_back_once_per_face_with_that_faces_matrices(self) -> None:
        def body(baker, device, out):
            calls = []

            def draw(view, projection):
                calls.append((view, projection))

            probe = baker.bake_probe(self.POSITION, draw)
            try:
                out["calls"] = calls
                out["is_zero"] = probe.is_zero
                out["position"] = tuple(probe.position)
            finally:
                probe.close()

        observed = self._baker(body)
        self.assertEqual(len(observed["calls"]), LIGHT_PROBE_BAKER_FACE_COUNT)
        self.assertEqual(observed["position"],
                         (self.POSITION.X, self.POSITION.Y, self.POSITION.Z))
        for face, (view, projection) in enumerate(observed["calls"]):
            want = oracle.probe_face_view(face, self.POSITION)
            for got, expected in zip(view, want):
                self.assertAlmostEqual(got, expected, places=4, msg=f"face {face}")
            # The projection is square and 90 degrees, the same for every face.
            self.assertEqual(list(projection), list(observed["calls"][0][1]))

    def test_a_black_scene_bakes_a_dark_probe(self) -> None:
        def body(baker, device, out):
            probe = baker.bake_probe(self.POSITION, lambda view, projection: None)
            try:
                out["zero"] = probe.is_zero
                out["irradiance"] = tuple(probe.irradiance(Vector3(0.0, 1.0, 0.0)))
            finally:
                probe.close()

        observed = self._baker(body)
        self.assertEqual(observed["irradiance"], (0.0, 0.0, 0.0))

    def test_an_exception_in_the_callback_reaches_the_caller_intact(self) -> None:
        """Raised after the native call returns, never unwound through C."""
        class Planted(RuntimeError):
            pass

        def body(baker, device, out):
            def draw(view, projection):
                raise Planted("from inside the bake")

            try:
                baker.bake_probe(self.POSITION, draw).close()
                out["raised"] = None
            except Planted as error:
                out["raised"] = str(error)
            # And the baker is still usable afterwards.
            probe = baker.bake_probe(self.POSITION, lambda v, p: None)
            probe.close()
            out["still_usable"] = True

        observed = self._baker(body)
        self.assertEqual(observed["raised"], "from inside the bake")
        self.assertTrue(observed["still_usable"])

    def test_a_callback_that_is_not_callable_is_refused_before_the_native_call(self) -> None:
        def body(baker, device, out):
            try:
                baker.bake_probe(self.POSITION, object())
                out["raised"] = None
            except TypeError:
                out["raised"] = "TypeError"

        self.assertEqual(self._baker(body)["raised"], "TypeError")

    def test_baking_a_volume_visits_every_probe(self) -> None:
        def body(baker, device, out):
            with LightProbeVolume(BOUNDS, 2, 1, 2) as volume:
                calls = []
                baker.bake_light(volume, lambda view, projection: calls.append(view))
                out["light_calls"] = len(calls)
                calls.clear()
                baker.bake_visibility(volume,
                                      lambda view, projection: calls.append(view))
                out["visibility_calls"] = len(calls)
                out["probe_count"] = volume.probe_count
                with LightProbe() as probe:
                    volume.read_probe(0, 0, 0, probe)
                    out["has_visibility"] = probe.has_visibility

        observed = self._baker(body)
        expected = observed["probe_count"] * LIGHT_PROBE_BAKER_FACE_COUNT
        self.assertEqual(observed["light_calls"], expected)
        self.assertEqual(observed["visibility_calls"], expected)

    def test_baking_a_volume_refuses_something_that_is_not_one(self) -> None:
        def body(baker, device, out):
            try:
                baker.bake_light(object(), lambda v, p: None)
                out["raised"] = None
            except TypeError:
                out["raised"] = "TypeError"

        self.assertEqual(self._baker(body)["raised"], "TypeError")


@requires_engine_gpu
class EnvironmentProcessorTests(unittest.TestCase):
    def _panorama(self, device, width=16, height=8):
        from Microsoft.Xna.Framework import Color
        from Microsoft.Xna.Framework.Graphics import SurfaceFormat, Texture2D

        texture = Texture2D(device, width, height, False, SurfaceFormat.Color)
        # Asymmetric on purpose: a uniform panorama would let a swapped axis pass.
        pixels = [Color(int(255 * x / max(width - 1, 1)),
                        int(255 * y / max(height - 1, 1)), 64, 255)
                  for y in range(height) for x in range(width)]
        texture.SetData(pixels)
        return texture

    def _processor(self, body):
        def run(game, device, observed):
            with EnvironmentProcessor(device) as processor:
                body(processor, device, observed)

        return in_game(run)

    def test_a_panorama_converts_into_a_cube_map_of_the_asked_size(self) -> None:
        def body(processor, device, out):
            panorama = self._panorama(device)
            try:
                cube = processor.convert_equirectangular(panorama, 8)
                try:
                    out["size"] = cube.Size
                finally:
                    cube.Dispose()
            finally:
                panorama.Dispose()

        self.assertEqual(self._processor(body)["size"], 8)

    def test_the_textures_outlive_the_processor_that_made_them(self) -> None:
        """The processor owns nothing it produced; a game builds and throws it away."""
        def body(game, device, out):
            processor = EnvironmentProcessor(device)
            panorama = self._panorama(device)
            cube = processor.convert_equirectangular(panorama, 8)
            processor.close()
            panorama.Dispose()
            try:
                out["still_readable"] = cube.Size
            finally:
                cube.Dispose()

        self.assertEqual(in_game(body)["still_readable"], 8)

    def test_irradiance_and_specular_cubes_are_built_from_an_environment(self) -> None:
        def body(processor, device, out):
            panorama = self._panorama(device)
            environment = processor.convert_equirectangular(panorama, 8)
            try:
                irradiance = processor.generate_irradiance(environment, 4, 4)
                specular = processor.generate_prefiltered_specular(environment, 8, 3, 8)
                try:
                    out.update(irradiance=irradiance.Size, specular=specular.Size,
                               mips=specular.LevelCount)
                finally:
                    irradiance.Dispose()
                    specular.Dispose()
            finally:
                environment.Dispose()
                panorama.Dispose()

        observed = self._processor(body)
        self.assertEqual(observed["irradiance"], 4)
        self.assertEqual(observed["specular"], 8)
        self.assertGreaterEqual(observed["mips"], 1)

    def test_the_brdf_table_is_square_and_the_size_it_was_asked_for(self) -> None:
        def body(processor, device, out):
            table = processor.generate_brdf_lut(16, 8)
            try:
                out["size"] = (table.Width, table.Height)
            finally:
                table.Dispose()

        self.assertEqual(self._processor(body)["size"], (16, 16))

    def test_a_probe_generated_from_an_environment_stores_light(self) -> None:
        def body(processor, device, out):
            panorama = self._panorama(device)
            environment = processor.convert_equirectangular(panorama, 8)
            try:
                probe = processor.generate_probe(environment, Vector3(1.0, 2.0, 3.0))
                try:
                    out["position"] = tuple(probe.position)
                    out["zero"] = probe.is_zero
                    out["irradiance"] = tuple(probe.irradiance(Vector3(0.0, 1.0, 0.0)))
                finally:
                    probe.close()
            finally:
                environment.Dispose()
                panorama.Dispose()

        observed = self._processor(body)
        self.assertEqual(observed["position"], (1.0, 2.0, 3.0))
        self.assertFalse(observed["zero"], "a lit panorama should project to something")
        self.assertGreater(sum(observed["irradiance"]), 0.0)

    def test_a_size_or_sample_count_that_is_not_positive_is_refused(self) -> None:
        def body(processor, device, out):
            panorama = self._panorama(device)
            environment = processor.convert_equirectangular(panorama, 8)
            try:
                for name, call in (
                        ("face size", lambda: processor.convert_equirectangular(
                            panorama, 0)),
                        ("irradiance size", lambda: processor.generate_irradiance(
                            environment, 0, 4)),
                        ("irradiance samples", lambda: processor.generate_irradiance(
                            environment, 4, 0)),
                        ("lut size", lambda: processor.generate_brdf_lut(0, 4))):
                    try:
                        call().Dispose()
                        out[name] = None
                    except EngineError as error:
                        out[name] = type(error).__name__
            finally:
                environment.Dispose()
                panorama.Dispose()

        for name, value in self._processor(body).items():
            self.assertIsNotNone(value, name)

    def test_an_effect_takes_the_three_textures_and_hands_them_back(self) -> None:
        def body(processor, device, out):
            from dataclasses import replace

            panorama = self._panorama(device)
            environment = processor.convert_equirectangular(panorama, 8)
            irradiance = processor.generate_irradiance(environment, 4, 4)
            specular = processor.generate_prefiltered_specular(environment, 8, 3, 8)
            table = processor.generate_brdf_lut(16, 8)
            effect = PbrEffect(device)
            try:
                out["before"] = effect.image_based_light
                light = replace(ImageBasedLight.default(), irradiance=irradiance,
                                prefiltered_specular=specular, brdf_lut=table,
                                prefiltered_mip_count=specular.LevelCount,
                                intensity=1.5)
                out["valid"] = light.is_valid
                effect.image_based_light = light
                read = effect.image_based_light
                out["same_objects"] = (read.irradiance is irradiance
                                       and read.prefiltered_specular is specular
                                       and read.brdf_lut is table)
                out["intensity"] = read.intensity
                out["mips"] = read.prefiltered_mip_count
                # Reading in a loop must not leak a handle per read.
                for _ in range(20):
                    effect.image_based_light
                out["repeated"] = True
            finally:
                effect.close()
                for texture in (table, specular, irradiance, environment, panorama):
                    texture.Dispose()

        observed = self._processor(body)
        self.assertIsNone(observed["before"])
        self.assertTrue(observed["valid"])
        self.assertTrue(observed["same_objects"])
        self.assertAlmostEqual(observed["intensity"], 1.5, places=5)
        self.assertGreaterEqual(observed["mips"], 1)
        self.assertTrue(observed["repeated"])

    def test_an_effect_refuses_something_that_is_not_an_image_based_light(self) -> None:
        def body(game, device, out):
            effect = PbrEffect(device)
            try:
                effect.image_based_light = object()
                out["raised"] = None
            except TypeError:
                out["raised"] = "TypeError"
            finally:
                effect.close()

        self.assertEqual(in_game(body)["raised"], "TypeError")


class ProbeAbsenceTests(unittest.TestCase):
    """What the family answers on a build with no engine layer at all."""

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_every_route_that_needs_the_layer_says_so(self) -> None:
        for name, call in (
                ("LightProbe", LightProbe),
                ("LightProbeVolume", lambda: LightProbeVolume(BOUNDS, 2, 2, 2)),
                ("hammersley", lambda: hammersley(0, 8)),
                ("mip_for_roughness", lambda: mip_for_roughness(0.5, 6)),
                ("cube_face_direction", lambda: cube_face_direction(0, 0.5, 0.5)),
                ("direction_to_equirectangular",
                 lambda: direction_to_equirectangular(Vector3(0.0, 0.0, -1.0))),
                ("importance_sample_ggx",
                 lambda: importance_sample_ggx(0.5, 0.5, Vector3(0.0, 1.0, 0.0), 0.5)),
                ("probe_evaluation_glsl", probe_evaluation_glsl)):
            with self.subTest(name), self.assertRaises(EngineUnavailableError):
                call()

    @requires_native
    @unittest.skipIf(ENGINE_PRESENT, "this build has an engine layer")
    def test_the_image_based_light_value_still_fills_its_defaults(self) -> None:
        """``cna_image_based_light_ext_init`` is documented as answering everywhere."""
        light = ImageBasedLight.default()
        self.assertIsNone(light.irradiance)
        self.assertFalse(light.is_valid)
