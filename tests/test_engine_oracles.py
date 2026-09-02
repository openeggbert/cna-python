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
