"""The oracles' own gate: a wrong expectation must not go unnoticed.

:mod:`tests.engine_oracles` is what the engine tests compare CNA against, so an
oracle that is wrong in the same way as CNA would make a whole family of tests
agree on a defect. These cases check each oracle against a value worked out by
hand *here*, from numbers small enough to verify by reading, and against
properties the formula must have whatever the numbers are.

Nothing here needs a native library. That is the point: if these depended on
CNA, they would be checking the oracle against the thing the oracle exists to
check.
"""

from __future__ import annotations

import math
import unittest

from Microsoft.Xna.Framework import Matrix, Vector3

from . import engine_oracles as oracle


class NormalisationTests(unittest.TestCase):
    def test_a_three_four_five_vector_normalises_by_hand(self) -> None:
        unit = oracle.normalized(Vector3(3.0, 4.0, 0.0))
        self.assertAlmostEqual(unit.X, 0.6, places=6)
        self.assertAlmostEqual(unit.Y, 0.8, places=6)
        self.assertAlmostEqual(unit.Z, 0.0, places=6)

    def test_a_zero_vector_does_not_divide_by_zero(self) -> None:
        self.assertEqual(tuple(oracle.normalized(Vector3(0.0, 0.0, 0.0))),
                         (0.0, 0.0, 0.0))


class BoxTests(unittest.TestCase):
    def test_centre_and_radius_of_a_two_by_four_by_four_box(self) -> None:
        minimum, maximum = Vector3(0.0, 0.0, 0.0), Vector3(2.0, 4.0, 4.0)
        centre = oracle.box_centre(minimum, maximum)
        self.assertEqual((centre.X, centre.Y, centre.Z), (1.0, 2.0, 2.0))
        # Half the diagonal: sqrt(4 + 16 + 16) / 2 = 6 / 2 = 3.
        self.assertAlmostEqual(oracle.box_radius(minimum, maximum), 3.0, places=6)

    def test_a_degenerate_box_has_no_radius(self) -> None:
        point = Vector3(5.0, 5.0, 5.0)
        self.assertEqual(oracle.box_radius(point, point), 0.0)


class LightViewTests(unittest.TestCase):
    def test_the_eye_stands_back_along_the_light_by_twice_the_radius(self) -> None:
        """A worked case: a unit box at the origin, lit from -X.

        Radius is half of sqrt(3) ~ 0.866, which is under one, so the distance
        floors at 2. The light travels along -X, so the eye is at +2 on X.
        """
        minimum, maximum = Vector3(-0.5, -0.5, -0.5), Vector3(0.5, 0.5, 0.5)
        view = oracle.shadow_light_view(Vector3(-1.0, 0.0, 0.0), minimum, maximum)
        # The eye is the point that transforms to the view's origin.
        origin = oracle.transform_coordinate((2.0, 0.0, 0.0), view)
        self.assertTrue(oracle.vectors_agree(origin, Vector3(0.0, 0.0, 0.0), 1e-5),
                        f"the eye is not where the formula puts it: {tuple(origin)}")

    def test_a_degenerate_box_still_gives_a_defined_view(self) -> None:
        point = Vector3(1.0, 2.0, 3.0)
        view = oracle.shadow_light_view(Vector3(0.0, -1.0, 0.0), point, point)
        self.assertTrue(all(math.isfinite(value) for value in tuple(view)))

    def test_the_up_vector_switches_only_near_vertical(self) -> None:
        minimum, maximum = Vector3(-1.0, -1.0, -1.0), Vector3(1.0, 1.0, 1.0)
        gentle = oracle.shadow_light_view(Vector3(0.0, -0.98, 0.199), minimum, maximum)
        steep = oracle.shadow_light_view(Vector3(0.0, -1.0, 0.0), minimum, maximum)
        self.assertFalse(oracle.matrices_agree(gentle, steep),
                         "the two up-vector branches produced the same matrix")


class SplitDistanceTests(unittest.TestCase):
    def test_a_pure_uniform_split_is_evenly_spaced(self) -> None:
        splits = oracle.cascade_split_distances(1.0, 101.0, 4, 0.0)
        # near + (far-near) * i/4 for i in 1..4 = 26, 51, 76, 101.
        self.assertEqual([round(value, 6) for value in splits], [26.0, 51.0, 76.0, 101.0])

    def test_a_pure_logarithmic_split_is_a_geometric_series(self) -> None:
        splits = oracle.cascade_split_distances(1.0, 16.0, 4, 1.0)
        # near * (far/near)**(i/4) = 16**(i/4) = 2, 4, 8, 16.
        self.assertEqual([round(value, 6) for value in splits], [2.0, 4.0, 8.0, 16.0])

    def test_the_last_split_is_always_the_far_plane(self) -> None:
        for lambda_ in (0.0, 0.3, 0.7, 1.0):
            with self.subTest(lambda_=lambda_):
                splits = oracle.cascade_split_distances(0.37, 213.7, 3, lambda_)
                self.assertAlmostEqual(splits[-1], 213.7, places=6)

    def test_lambda_is_clamped(self) -> None:
        self.assertEqual(oracle.cascade_split_distances(1.0, 16.0, 4, 2.0),
                         oracle.cascade_split_distances(1.0, 16.0, 4, 1.0))
        self.assertEqual(oracle.cascade_split_distances(1.0, 16.0, 4, -2.0),
                         oracle.cascade_split_distances(1.0, 16.0, 4, 0.0))


class FrustumTests(unittest.TestCase):
    def test_the_identity_unprojects_the_ndc_cube_unchanged(self) -> None:
        """With no transform at all the corners are the NDC corners themselves."""
        corners = oracle.frustum_corners(Matrix.Identity, Matrix.Identity)
        for produced, expected in zip(corners, oracle.NDC_CORNERS):
            self.assertTrue(oracle.vectors_agree(produced, Vector3(*expected), 1e-6),
                            f"{tuple(produced)} vs {expected}")

    def test_depth_runs_zero_to_one_not_minus_one_to_one(self) -> None:
        """The convention half an implementation gets wrong."""
        depths = {corner[2] for corner in oracle.NDC_CORNERS}
        self.assertEqual(depths, {0.0, 1.0})

    def test_a_translated_camera_moves_every_corner_by_the_same_amount(self) -> None:
        projection = Matrix.CreatePerspectiveFieldOfView(0.9, 1.6, 0.4, 90.0)
        first = oracle.frustum_corners(Matrix.Identity, projection)
        shifted = oracle.frustum_corners(
            Matrix.CreateTranslation(Vector3(3.0, 0.0, 0.0)), projection)
        for before, after in zip(first, shifted):
            self.assertAlmostEqual(after.X - before.X, -3.0, places=4)
            self.assertAlmostEqual(after.Y, before.Y, places=4)


class BoundingSphereTests(unittest.TestCase):
    def test_the_unit_cube_centres_on_the_origin_with_the_half_diagonal(self) -> None:
        corners = [Vector3(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0)
                   for z in (-1.0, 1.0)]
        centre, radius = oracle.bounding_sphere(corners)
        self.assertTrue(oracle.vectors_agree(centre, Vector3(0.0, 0.0, 0.0), 1e-9))
        self.assertAlmostEqual(radius, math.sqrt(3.0), places=6)

    def test_a_collapsed_frustum_still_has_a_radius(self) -> None:
        corners = [Vector3(2.0, 2.0, 2.0)] * 8
        _centre, radius = oracle.bounding_sphere(corners)
        self.assertGreater(radius, 0.0)


class SnapTests(unittest.TestCase):
    def test_a_worked_snap(self) -> None:
        """radius 8, size 16 gives one world unit per texel, so it floors."""
        snapped = oracle.snap_to_texel_grid(Vector3(3.7, -2.2, 9.9), 8.0, 16)
        self.assertAlmostEqual(snapped.X, 3.0, places=6)
        self.assertAlmostEqual(snapped.Y, -3.0, places=6)
        self.assertAlmostEqual(snapped.Z, 9.9, places=6)

    def test_a_degenerate_grid_changes_nothing(self) -> None:
        centre = Vector3(1.5, 2.5, 3.5)
        self.assertEqual(tuple(oracle.snap_to_texel_grid(centre, 8.0, 0)), tuple(centre))
        self.assertEqual(tuple(oracle.snap_to_texel_grid(centre, 0.0, 16)), tuple(centre))


class ComparisonTests(unittest.TestCase):
    """The comparators themselves, which every other oracle test relies on."""

    def test_matrices_agree_is_not_vacuous(self) -> None:
        self.assertTrue(oracle.matrices_agree(Matrix.Identity, Matrix.Identity))
        self.assertFalse(oracle.matrices_agree(
            Matrix.Identity, Matrix.CreateTranslation(Vector3(1.0, 0.0, 0.0))))
        # A difference just inside the tolerance passes and one outside fails.
        nudged = Matrix(*[value + 1e-5 for value in tuple(Matrix.Identity)])
        self.assertTrue(oracle.matrices_agree(Matrix.Identity, nudged))
        pushed = Matrix(*[value + 1e-3 for value in tuple(Matrix.Identity)])
        self.assertFalse(oracle.matrices_agree(Matrix.Identity, pushed))

    def test_vectors_agree_is_not_vacuous(self) -> None:
        self.assertTrue(oracle.vectors_agree(Vector3(1.0, 2.0, 3.0),
                                             Vector3(1.0, 2.0, 3.0)))
        self.assertFalse(oracle.vectors_agree(Vector3(1.0, 2.0, 3.0),
                                              Vector3(1.0, 2.0, 3.1)))

    def test_transform_coordinate_divides_by_w(self) -> None:
        """A perspective divide, worked by hand.

        A projection with w = z sends (2, 4, 2) to (1, 2), which is the whole
        reason the divide is there.
        """
        values = list(tuple(Matrix.Identity))
        values[11] = 1.0   # m34: w picks up z
        values[15] = 0.0   # m44: and nothing else
        produced = oracle.transform_coordinate((2.0, 4.0, 2.0), Matrix(*values))
        self.assertAlmostEqual(produced.X, 1.0, places=6)
        self.assertAlmostEqual(produced.Y, 2.0, places=6)


class ParticleRandomTests(unittest.TestCase):
    """The hash, checked as a hash rather than against itself."""

    def test_the_draw_is_in_range_and_deterministic(self) -> None:
        for seed in (0, 1, 7, 4096, 0xFFFFFFFF):
            with self.subTest(seed=seed):
                value = oracle.particle_random(seed)
                self.assertGreaterEqual(value, 0.0)
                self.assertLess(value, 1.0)
                self.assertEqual(value, oracle.particle_random(seed))

    def test_neighbouring_seeds_decorrelate(self) -> None:
        """The property that makes it usable: consecutive seeds are unrelated.

        A hash that varied smoothly would give a particle emitter a gradient
        rather than a spread, which is the failure this hash exists to avoid.
        """
        values = [oracle.particle_random(seed) for seed in range(64)]
        self.assertEqual(len(set(values)), 64, "two of 64 consecutive seeds collided")
        differences = [abs(b - a) for a, b in zip(values, values[1:])]
        self.assertGreater(sum(differences) / len(differences), 0.2,
                           "consecutive draws move too little to be decorrelated")

    def test_the_hash_stays_inside_thirty_two_bits(self) -> None:
        for seed in (0, 1, 0x7FFFFFFF, 0xFFFFFFFF):
            with self.subTest(seed=seed):
                self.assertLessEqual(oracle.particle_hash(seed), 0xFFFFFFFF)
                self.assertGreaterEqual(oracle.particle_hash(seed), 0)


class DepthPackingTests(unittest.TestCase):
    def test_the_top_channel_is_empty_because_a_float_runs_out_of_bits(self) -> None:
        """The property that makes single precision part of the algorithm.

        ``0.876 * 2**24`` is about 14.7 million, which needs every one of a
        ``float``'s 24 mantissa bits for its integer part, so its fractional
        part is exactly zero. That is not a rounding artefact to be tolerated:
        it is what the first channel actually carries, and an oracle computing
        in doubles would report otherwise.
        """
        self.assertEqual(oracle.pack_depth(0.87654321)[0], 0.0)
        # And the remaining channels do carry the depth.
        self.assertAlmostEqual(oracle.unpack_depth(*oracle.pack_depth(0.87654321)),
                               0.87654321, places=5)

    def test_packing_and_unpacking_are_inverses(self) -> None:
        for depth in (0.0, 0.001, 0.25, 0.5, 0.75, 0.9999):
            with self.subTest(depth=depth):
                red, green, blue, alpha = oracle.pack_depth(depth)
                self.assertAlmostEqual(
                    oracle.unpack_depth(red, green, blue, alpha), depth, places=6)

    def test_one_is_clamped_short_so_it_does_not_wrap_to_zero(self) -> None:
        """The whole reason the clamp exists."""
        packed = oracle.pack_depth(1.0)
        self.assertGreater(oracle.unpack_depth(*packed), 0.99,
                           "a far-plane depth must not read back as the nearest surface")

    def test_every_channel_stays_in_range(self) -> None:
        for depth in (0.0, 0.125, 0.6, 0.99999994):
            with self.subTest(depth=depth):
                for channel in oracle.pack_depth(depth):
                    self.assertGreaterEqual(channel, -1e-6)
                    self.assertLessEqual(channel, 1.0 + 1e-6)


class VelocityTests(unittest.TestCase):
    def test_the_alpha_marker_decides_whether_there_is_a_velocity(self) -> None:
        self.assertTrue(oracle.has_velocity(0))
        self.assertTrue(oracle.has_velocity(127))
        self.assertFalse(oracle.has_velocity(128))
        self.assertFalse(oracle.has_velocity(255))

    def test_an_unmarked_texel_decodes_to_no_velocity_rather_than_a_zero_one(self) -> None:
        self.assertEqual(oracle.decode_velocity(255, 255, 0, 255), (0.0, 0.0))

    def test_the_midpoint_is_zero_and_the_ends_are_plus_and_minus_one(self) -> None:
        self.assertEqual(oracle.decode_velocity(255, 0, 0, 0), (1.0, -1.0))
        middle = oracle.decode_velocity(128, 128, 0, 0)
        self.assertAlmostEqual(middle[0], 0.00392, places=4)


class TransparencyWeightTests(unittest.TestCase):
    def test_near_fragments_weigh_more_than_far_ones(self) -> None:
        near = oracle.transparency_weight(1.0, 1.0, 100.0)
        far = oracle.transparency_weight(90.0, 1.0, 100.0)
        self.assertGreater(near, far,
                           "an order-independent blend has to favour near fragments")

    def test_the_ceiling_binds_and_the_floor_cannot(self) -> None:
        """Depth zero saturates the weight; the lower clamp is unreachable.

        The depth is normalised and clamped to ``0..1`` first, so the falloff
        never falls below ``0.03 / (1e-5 + 1)``, which is three times the 0.01
        floor. The floor is defensive rather than dead code that matters, and
        knowing that is better than assuming it binds somewhere.
        """
        self.assertAlmostEqual(oracle.transparency_weight(0.0, 1.0, 100.0), 3e3,
                               places=1)
        beyond = oracle.transparency_weight(1000.0, 1.0, 100.0)
        self.assertAlmostEqual(beyond, 0.03 / (1e-5 + 1.0), places=6)
        self.assertGreater(beyond, 1e-2)
        # And it really is clamped: twice the far plane weighs the same as the
        # far plane itself.
        self.assertEqual(oracle.transparency_weight(200.0, 1.0, 100.0), beyond)

    def test_alpha_scales_it_linearly(self) -> None:
        full = oracle.transparency_weight(10.0, 1.0, 100.0)
        half = oracle.transparency_weight(10.0, 0.5, 100.0)
        self.assertAlmostEqual(half, full * 0.5, places=5)


class SortKeyTests(unittest.TestCase):
    def test_a_box_containing_the_camera_sorts_at_zero(self) -> None:
        self.assertEqual(oracle.sort_key(Vector3(-1.0, -1.0, -1.0),
                                         Vector3(1.0, 1.0, 1.0),
                                         Vector3(0.5, -0.25, 0.0)), 0.0)

    def test_the_distance_is_to_the_nearest_face_not_the_centre(self) -> None:
        """A 3-4-5 case, worked by hand."""
        key = oracle.sort_key(Vector3(3.0, 4.0, 0.0), Vector3(9.0, 9.0, 0.0),
                              Vector3(0.0, 0.0, 0.0))
        self.assertAlmostEqual(key, 5.0, places=6)

    def test_it_grows_with_distance(self) -> None:
        near = oracle.sort_key(Vector3(1.0, 0.0, 0.0), Vector3(2.0, 1.0, 1.0),
                               Vector3(0.0, 0.0, 0.0))
        far = oracle.sort_key(Vector3(10.0, 0.0, 0.0), Vector3(11.0, 1.0, 1.0),
                              Vector3(0.0, 0.0, 0.0))
        self.assertLess(near, far)


class DecalBoxTests(unittest.TestCase):
    def test_the_box_is_the_unit_cube_and_its_faces_are_inclusive(self) -> None:
        self.assertTrue(oracle.is_inside_decal_box(Vector3(0.0, 0.0, 0.0)))
        self.assertTrue(oracle.is_inside_decal_box(Vector3(0.5, -0.5, 0.5)))
        self.assertFalse(oracle.is_inside_decal_box(Vector3(0.5001, 0.0, 0.0)))
        self.assertFalse(oracle.is_inside_decal_box(Vector3(0.0, 0.0, -0.6)))


class BloomExtractionTests(unittest.TestCase):
    def test_the_knee_is_soft_rather_than_a_cutoff(self) -> None:
        """A value exactly at the threshold contributes a quarter of itself.

        knee = 0.25, so the ramp is (0.5 - 0.5 + 0.25) / 0.5 = 0.5, squared to
        0.25, times the value 0.5 gives 0.125. Worked here rather than taken
        from the routine it checks.
        """
        self.assertAlmostEqual(oracle.bloom_extract_channel(0.5, 0.5), 0.125,
                               places=6)

    def test_well_below_the_knee_contributes_nothing(self) -> None:
        self.assertEqual(oracle.bloom_extract_channel(0.2, 0.5), 0.0)
        self.assertEqual(oracle.bloom_extract_channel(0.0, 1.0), 0.0)

    def test_well_above_the_knee_contributes_everything(self) -> None:
        self.assertAlmostEqual(oracle.bloom_extract_channel(0.9, 0.5), 0.9, places=6)
        self.assertAlmostEqual(oracle.bloom_extract_channel(2.0, 0.0), 2.0, places=6)

    def test_a_zero_threshold_does_not_divide_by_zero(self) -> None:
        self.assertTrue(math.isfinite(oracle.bloom_extract_channel(0.5, 0.0)))

    def test_it_rises_with_the_value(self) -> None:
        values = [oracle.bloom_extract_channel(x / 10.0, 0.5) for x in range(11)]
        self.assertEqual(values, sorted(values))


class ClusterIndexTests(unittest.TestCase):
    def test_a_two_by_two_by_two_grid_numbers_x_fastest(self) -> None:
        """Eight clusters, listed in the order the flat index puts them.

        x varies fastest, then y, then depth, so (1, 0, 0) is 1 and (0, 1, 0) is
        2 and (0, 0, 1) is 4. Written out here rather than computed.
        """
        listed = [oracle.cluster_index(2, 2, x, y, s)
                  for s in range(2) for y in range(2) for x in range(2)]
        self.assertEqual(listed, [0, 1, 2, 3, 4, 5, 6, 7])

    def test_the_layout_is_the_one_the_gpu_path_undoes(self) -> None:
        """The shader recovers x, y and slice from the flat index this way."""
        tiles_x, tiles_y, slices = 3, 2, 5
        for slice_ in range(slices):
            for y in range(tiles_y):
                for x in range(tiles_x):
                    flat = oracle.cluster_index(tiles_x, tiles_y, x, y, slice_)
                    self.assertEqual(flat % tiles_x, x)
                    self.assertEqual((flat // tiles_x) % tiles_y, y)
                    self.assertEqual(flat // (tiles_x * tiles_y), slice_)

    def test_every_cluster_gets_its_own_index(self) -> None:
        seen = {oracle.cluster_index(7, 5, x, y, s)
                for s in range(9) for y in range(5) for x in range(7)}
        self.assertEqual(len(seen), 7 * 5 * 9)
        self.assertEqual(max(seen), 7 * 5 * 9 - 1)


class SliceDistanceTests(unittest.TestCase):
    def test_a_ratio_of_sixteen_over_four_slices_doubles_each_time(self) -> None:
        """near 1, far 16, four slices: the ratio is 16, so each step is 16**0.25 = 2.

        1, 2, 4, 8, 16 -- worked here from the exponent, not from the routine.
        """
        distances = [oracle.slice_distance(1.0, 16.0, 4, index) for index in range(5)]
        for expected, actual in zip([1.0, 2.0, 4.0, 8.0, 16.0], distances):
            self.assertAlmostEqual(actual, expected, places=5)

    def test_the_two_ends_are_the_planes_exactly(self) -> None:
        """Not approximately: a boundary that is 47.499996 puts a light in the wrong slice."""
        self.assertEqual(oracle.slice_distance(0.35, 47.5, 5, 0), oracle.f32(0.35))
        self.assertEqual(oracle.slice_distance(0.35, 47.5, 5, 5), oracle.f32(47.5))

    def test_the_slices_grow(self) -> None:
        widths = [oracle.slice_distance(0.35, 47.5, 8, index + 1)
                  - oracle.slice_distance(0.35, 47.5, 8, index) for index in range(8)]
        self.assertEqual(widths, sorted(widths))
        self.assertGreater(widths[0], 0.0)

    def test_one_slice_is_the_whole_range(self) -> None:
        self.assertEqual(oracle.slice_distance(2.0, 30.0, 1, 0), 2.0)
        self.assertEqual(oracle.slice_distance(2.0, 30.0, 1, 1), 30.0)


class SliceForViewDistanceTests(unittest.TestCase):
    def test_it_inverts_the_spacing_at_a_slice_centre(self) -> None:
        """near 1, far 16, four slices: 3 sits between 2 and 4, so it is slice 1."""
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 3.0), 1)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 1.5), 0)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 6.0), 2)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 12.0), 3)

    def test_both_ends_clamp_rather_than_run_off(self) -> None:
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, -5.0), 0)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 1.0), 0)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 16.0), 3)
        self.assertEqual(oracle.slice_for_view_distance(1.0, 16.0, 4, 1e6), 3)

    def test_it_agrees_with_the_boundaries_it_inverts(self) -> None:
        """A point just inside a slice's own range lands in that slice."""
        near, far, count = 0.35, 47.5, 6
        for index in range(count):
            low = oracle.slice_distance(near, far, count, index)
            high = oracle.slice_distance(near, far, count, index + 1)
            middle = math.sqrt(low * high)
            self.assertEqual(
                oracle.slice_for_view_distance(near, far, count, middle), index)


class MatrixInverseTests(unittest.TestCase):
    def test_a_scale_matrix_inverts_to_the_reciprocal_scale(self) -> None:
        scale = Matrix(2.0, 0, 0, 0, 0, 4.0, 0, 0, 0, 0, 8.0, 0, 0, 0, 0, 1.0)
        inverse = oracle.invert_matrix4(scale)
        self.assertAlmostEqual(inverse[0], 0.5, places=9)
        self.assertAlmostEqual(inverse[5], 0.25, places=9)
        self.assertAlmostEqual(inverse[10], 0.125, places=9)
        self.assertAlmostEqual(inverse[15], 1.0, places=9)

    def test_the_product_with_the_original_is_the_identity(self) -> None:
        projection = Matrix.CreatePerspectiveFieldOfView(0.9773843811168246,
                                                         1.7777777777777777, 0.35, 47.5)
        values, inverse = list(projection), oracle.invert_matrix4(projection)
        for row in range(4):
            for column in range(4):
                total = sum(values[row * 4 + k] * inverse[k * 4 + column]
                            for k in range(4))
                self.assertAlmostEqual(total, 1.0 if row == column else 0.0, places=6)

    def test_a_singular_matrix_is_refused_rather_than_dividing_by_zero(self) -> None:
        with self.assertRaises(ValueError):
            oracle.invert_matrix4(Matrix(*([0.0] * 16)))


class ClusterBoundsTests(unittest.TestCase):
    PROJECTION = Matrix.CreatePerspectiveFieldOfView(0.9773843811168246,
                                                     1.7777777777777777, 0.35, 47.5)

    def test_a_cluster_spans_exactly_its_slice_in_depth(self) -> None:
        """View distance is -z, so the box runs from -far_of_slice to -near_of_slice."""
        minimum, maximum = oracle.cluster_bounds(self.PROJECTION, 3, 2, 5, 0.35, 47.5,
                                                 0, 0, 0)
        self.assertAlmostEqual(maximum.Z, -oracle.slice_distance(0.35, 47.5, 5, 0),
                               places=6)
        self.assertAlmostEqual(minimum.Z, -oracle.slice_distance(0.35, 47.5, 5, 1),
                               places=6)

    def test_the_whole_grid_covers_the_frustum_and_no_more(self) -> None:
        """One tile and one slice is the frustum itself, to the two planes."""
        minimum, maximum = oracle.cluster_bounds(self.PROJECTION, 1, 1, 1, 0.35, 47.5,
                                                 0, 0, 0)
        # Half-height at the far plane: far * tan(fov / 2).
        half_height = 47.5 * math.tan(0.9773843811168246 / 2.0)
        self.assertAlmostEqual(maximum.Y, half_height, places=4)
        self.assertAlmostEqual(minimum.Y, -half_height, places=4)
        self.assertAlmostEqual(maximum.X, half_height * 1.7777777777777777, places=4)

    def test_neighbouring_tiles_overlap_because_the_box_is_axis_aligned(self) -> None:
        """A box around a frustum slab is as wide as its far face.

        So it reaches past its neighbour's near face, and the two overlap. The
        first version of this case compared tiles 1 and 2 of a four-tile row --
        which straddle the centre, where both boundaries are zero -- and passed
        without checking anything.
        """
        left = oracle.cluster_bounds(self.PROJECTION, 4, 1, 1, 0.35, 47.5, 0, 0, 0)
        right = oracle.cluster_bounds(self.PROJECTION, 4, 1, 1, 0.35, 47.5, 1, 0, 0)
        self.assertLess(right[0].X, left[1].X)
        self.assertLess(left[0].X, right[0].X)
        self.assertLess(left[1].X, right[1].X)

    def test_the_slices_of_one_tile_meet_exactly_in_depth(self) -> None:
        """Depth is the axis a cluster really does partition."""
        near = oracle.cluster_bounds(self.PROJECTION, 1, 1, 4, 0.35, 47.5, 0, 0, 1)
        far = oracle.cluster_bounds(self.PROJECTION, 1, 1, 4, 0.35, 47.5, 0, 0, 2)
        self.assertAlmostEqual(near[0].Z, far[1].Z, places=6)

    def test_the_tiles_of_one_row_tile_the_row(self) -> None:
        whole = oracle.cluster_bounds(self.PROJECTION, 1, 1, 1, 0.35, 47.5, 0, 0, 0)
        pieces = [oracle.cluster_bounds(self.PROJECTION, 5, 1, 1, 0.35, 47.5, x, 0, 0)
                  for x in range(5)]
        self.assertAlmostEqual(pieces[0][0].X, whole[0].X, places=5)
        self.assertAlmostEqual(pieces[-1][1].X, whole[1].X, places=5)


class LightBoundsTests(unittest.TestCase):
    def test_a_point_light_bounds_itself(self) -> None:
        centre, radius = oracle.point_light_bounds(Vector3(1.0, 2.0, 3.0), 4.0)
        self.assertEqual((centre.X, centre.Y, centre.Z, radius), (1.0, 2.0, 3.0, 4.0))

    def test_a_wide_cone_is_bounded_at_its_base(self) -> None:
        """A 60-degree cone of range 2 along -y: base at y = -2*cos(60) = -1, radius 2*sin(60)."""
        centre, radius = oracle.spot_light_bounds(
            Vector3(0.0, 0.0, 0.0), Vector3(0.0, -1.0, 0.0), 2.0, math.pi / 3.0)
        self.assertAlmostEqual(centre.Y, -1.0, places=5)
        self.assertAlmostEqual(radius, 2.0 * math.sin(math.pi / 3.0), places=5)

    def test_a_narrow_cone_uses_the_sphere_through_the_apex(self) -> None:
        """A 30-degree cone of range 2: radius 2/(2*cos 30) = 1.1547, centred there."""
        centre, radius = oracle.spot_light_bounds(
            Vector3(0.0, 0.0, 0.0), Vector3(0.0, -1.0, 0.0), 2.0, math.pi / 6.0)
        self.assertAlmostEqual(radius, 2.0 / (2.0 * math.cos(math.pi / 6.0)), places=5)
        self.assertAlmostEqual(centre.Y, -radius, places=5)

    def test_the_narrow_sphere_really_contains_the_apex_and_the_rim(self) -> None:
        """The property the two-case split exists for, checked rather than assumed."""
        angle, range_ = math.pi / 6.0, 2.0
        centre, radius = oracle.spot_light_bounds(
            Vector3(0.0, 0.0, 0.0), Vector3(0.0, -1.0, 0.0), range_, angle)
        apex = math.dist((0.0, 0.0, 0.0), (centre.X, centre.Y, centre.Z))
        rim = math.dist((range_ * math.sin(angle), -range_ * math.cos(angle), 0.0),
                        (centre.X, centre.Y, centre.Z))
        self.assertLessEqual(apex, radius + 1e-5)
        self.assertLessEqual(rim, radius + 1e-5)

    def test_the_narrow_case_is_tighter_than_the_wide_one_would_be(self) -> None:
        """Why the split exists: the base-centred sphere is looser for a torch."""
        angle, range_ = math.pi / 12.0, 10.0
        _, narrow = oracle.spot_light_bounds(
            Vector3(0.0, 0.0, 0.0), Vector3(0.0, -1.0, 0.0), range_, angle)
        wide = range_ * math.sin(angle)
        # The base-rim sphere has a smaller radius but does not contain the apex,
        # so it is not a bound at all; the apex is `range_` from its centre.
        self.assertLess(wide, narrow)
        self.assertGreater(range_, wide)


class ClusterAssignmentTests(unittest.TestCase):
    PROJECTION = Matrix.CreatePerspectiveFieldOfView(0.9773843811168246,
                                                     1.7777777777777777, 0.35, 47.5)

    def _assign(self, spheres, tiles_x=2, tiles_y=2, slices=2):
        return oracle.assign_clusters(self.PROJECTION, tiles_x, tiles_y, slices,
                                      0.35, 47.5, Matrix.Identity, spheres)

    def test_no_lights_gives_an_all_zero_offset_table(self) -> None:
        offsets, indices = self._assign([])
        self.assertEqual(offsets, [0] * (2 * 2 * 2 + 1))
        self.assertEqual(indices, [])

    def test_a_light_behind_the_camera_reaches_nothing(self) -> None:
        offsets, indices = self._assign([(Vector3(0.0, 0.0, 10.0), 1.0)])
        self.assertEqual(indices, [])
        self.assertEqual(offsets[-1], 0)

    def test_a_light_with_no_radius_is_skipped(self) -> None:
        self.assertEqual(self._assign([(Vector3(0.0, 0.0, -5.0), 0.0)])[1], [])
        self.assertEqual(self._assign([(Vector3(0.0, 0.0, -5.0), -1.0)])[1], [])

    def test_a_light_enclosing_the_frustum_reaches_every_cluster(self) -> None:
        offsets, indices = self._assign([(Vector3(0.0, 0.0, -20.0), 500.0)])
        self.assertEqual(indices, [0] * 8)
        self.assertEqual(offsets, list(range(9)))

    def test_the_offsets_describe_the_indices(self) -> None:
        """The structural invariant CNA's own adopt() checks for."""
        offsets, indices = self._assign([(Vector3(0.0, 0.0, -5.0), 3.0),
                                         (Vector3(2.0, 1.0, -20.0), 6.0)])
        self.assertEqual(offsets[0], 0)
        self.assertEqual(offsets[-1], len(indices))
        self.assertEqual(offsets, sorted(offsets))
        self.assertTrue(all(0 <= index < 2 for index in indices))

    def test_a_light_in_one_corner_does_not_reach_the_opposite_one(self) -> None:
        """The test that a transposed grid would fail."""
        offsets, indices = self._assign([(Vector3(-3.0, 3.0, -6.0), 1.0)],
                                        tiles_x=2, tiles_y=2, slices=1)
        reached = {cluster for cluster in range(4)
                   if offsets[cluster + 1] > offsets[cluster]}
        self.assertNotEqual(reached, {0, 1, 2, 3})
        self.assertTrue(reached)


class ShadowPolicyScoreTests(unittest.TestCase):
    def test_white_at_one_unit_inside_its_range_scores_the_falloff(self) -> None:
        """A white light of intensity 1, range 2, one unit away.

        luminance 1, falloff (1 - (0.5)**4)**2 / 1 = 0.9375**2 = 0.87890625.
        Worked here from the formula, not from the routine.
        """
        score = oracle.shadow_policy_score(
            Vector3(1.0, 1.0, 1.0), 1.0, 2.0, Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 0.0, 0.0))
        self.assertAlmostEqual(score, 0.87890625, places=6)

    def test_a_light_at_or_beyond_its_range_scores_nothing(self) -> None:
        self.assertEqual(oracle.shadow_policy_score(
            Vector3(1.0, 1.0, 1.0), 1.0, 4.0, Vector3(4.0, 0.0, 0.0),
            Vector3(0.0, 0.0, 0.0)), 0.0)

    def test_green_outweighs_blue_of_the_same_intensity(self) -> None:
        green = oracle.shadow_policy_score(Vector3(0.0, 1.0, 0.0), 1.0, 5.0,
                                           Vector3(2.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0))
        blue = oracle.shadow_policy_score(Vector3(0.0, 0.0, 1.0), 1.0, 5.0,
                                          Vector3(2.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0))
        self.assertGreater(green, blue)
        self.assertAlmostEqual(green / blue, 0.7152 / 0.0722, places=3)

    def test_standing_inside_a_light_is_finite(self) -> None:
        """The distance floors at one unit, so the falloff cannot diverge."""
        at_zero = oracle.shadow_policy_score(
            Vector3(1.0, 1.0, 1.0), 1.0, 10.0, Vector3(0.0, 0.0, 0.0),
            Vector3(0.0, 0.0, 0.0))
        at_one = oracle.shadow_policy_score(
            Vector3(1.0, 1.0, 1.0), 1.0, 10.0, Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 0.0, 0.0))
        self.assertTrue(math.isfinite(at_zero))
        self.assertEqual(at_zero, at_one)

    def test_a_nearer_light_of_equal_colour_outranks_a_further_one(self) -> None:
        scores = [oracle.shadow_policy_score(Vector3(1.0, 1.0, 1.0), 1.0, 20.0,
                                             Vector3(float(d), 0.0, 0.0),
                                             Vector3(0.0, 0.0, 0.0))
                  for d in range(1, 12)]
        self.assertEqual(scores, sorted(scores, reverse=True))


class VolumeAttenuationTests(unittest.TestCase):
    def test_one_attenuation_distance_leaves_the_colour_itself(self) -> None:
        result = oracle.volume_attenuation(Vector3(0.5, 0.25, 1.0), 2.0, 2.0)
        self.assertAlmostEqual(result.X, 0.5, places=6)
        self.assertAlmostEqual(result.Y, 0.25, places=6)
        self.assertAlmostEqual(result.Z, 1.0, places=6)

    def test_half_the_distance_is_the_square_root(self) -> None:
        result = oracle.volume_attenuation(Vector3(0.25, 1.0, 0.0625), 2.0, 1.0)
        self.assertAlmostEqual(result.X, 0.5, places=6)
        self.assertAlmostEqual(result.Y, 1.0, places=6)
        self.assertAlmostEqual(result.Z, 0.25, places=6)

    def test_no_medium_leaves_everything(self) -> None:
        for distance, thickness in ((0.0, 1.0), (2.0, 0.0), (-1.0, 1.0), (2.0, -1.0)):
            result = oracle.volume_attenuation(Vector3(0.5, 0.5, 0.5), distance,
                                               thickness)
            self.assertEqual((result.X, result.Y, result.Z), (1.0, 1.0, 1.0))

    def test_a_black_channel_does_not_take_a_logarithm_of_zero(self) -> None:
        result = oracle.volume_attenuation(Vector3(0.0, 0.0, 0.0), 1.0, 1.0)
        self.assertTrue(all(math.isfinite(value)
                            for value in (result.X, result.Y, result.Z)))
        self.assertAlmostEqual(result.X, 1e-4, places=8)


class LobeScaleTests(unittest.TestCase):
    def test_it_is_roughness_squared_above_the_floor(self) -> None:
        self.assertAlmostEqual(oracle.lobe_scale_for(0.5), 0.25, places=6)
        self.assertAlmostEqual(oracle.lobe_scale_for(1.0), 1.0, places=6)
        self.assertAlmostEqual(oracle.lobe_scale_for(0.25), 0.0625, places=6)

    def test_a_mirror_keeps_a_width(self) -> None:
        self.assertAlmostEqual(oracle.lobe_scale_for(0.0), 0.02, places=6)
        self.assertAlmostEqual(oracle.lobe_scale_for(0.1), 0.02, places=6)

    def test_it_clamps_outside_zero_to_one(self) -> None:
        self.assertAlmostEqual(oracle.lobe_scale_for(-1.0), 0.02, places=6)
        self.assertAlmostEqual(oracle.lobe_scale_for(5.0), 1.0, places=6)


class AreaLightQuadTests(unittest.TestCase):
    def test_a_unit_rectangle_has_the_corners_its_axes_describe(self) -> None:
        corners = oracle.area_light_quad(0, Vector3(0.0, 0.0, 0.0),
                                         Vector3(0.5, 0.0, 0.0), Vector3(0.0, 0.5, 0.0))
        self.assertEqual([(c.X, c.Y, c.Z) for c in corners],
                         [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0),
                          (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)])

    def test_a_disc_encloses_the_area_a_disc_encloses(self) -> None:
        """The scale exists so pi*a*b equals 4*(a*s)*(b*s); check that identity."""
        a, b = 0.5, 0.25
        corners = oracle.area_light_quad(1, Vector3(0.0, 0.0, 0.0),
                                         Vector3(a, 0.0, 0.0), Vector3(0.0, b, 0.0))
        width = corners[1].X - corners[0].X
        height = corners[2].Y - corners[1].Y
        self.assertAlmostEqual(width * height, math.pi * a * b, places=6)

    def test_the_corners_go_counter_clockwise_about_the_axes(self) -> None:
        corners = oracle.area_light_quad(0, Vector3(1.0, 2.0, 3.0),
                                         Vector3(2.0, 0.0, 0.0), Vector3(0.0, 3.0, 0.0))
        self.assertLess(corners[0].X, corners[1].X)
        self.assertLess(corners[1].Y, corners[2].Y)
        self.assertGreater(corners[2].X, corners[3].X)
