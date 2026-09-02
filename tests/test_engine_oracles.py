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
