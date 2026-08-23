from __future__ import annotations

import copy
import math
import unittest

from Microsoft.Xna.Framework import (
    BoundingBox, BoundingFrustum, BoundingSphere, ContainmentType, MathHelper,
    Matrix, Plane, PlaneIntersectionType, Quaternion, Ray, Vector3, Vector4,
)


class PlaneAndRayTests(unittest.TestCase):
    def test_plane_constructors_normalization_dots_and_transforms(self) -> None:
        plane = Plane(Vector3(0, 2, 0), -4)
        normalized = Plane.Normalize(plane)
        self.assertEqual(normalized, Plane(Vector3.Up, -2))
        self.assertEqual(plane.Normal, Vector3(0, 2, 0))
        plane.Normalize()
        self.assertEqual(plane, normalized)
        self.assertEqual(plane.Dot(Vector4(0, 2, 0, 1)), 0)
        self.assertEqual(plane.DotCoordinate(Vector3(0, 3, 0)), 1)
        self.assertEqual(plane.DotNormal(Vector3.Down), -1)
        points = Plane(Vector3.Zero, Vector3.UnitX, Vector3.UnitZ)
        self.assertEqual(abs(points.Normal.Y), 1)
        self.assertEqual(Plane(Vector4(1, 2, 3, 4)), Plane(1, 2, 3, 4))
        rotated = Plane.Transform(Plane(Vector3.UnitX, -1), Quaternion.CreateFromAxisAngle(Vector3.UnitZ, MathHelper.PiOver2))
        self.assertAlmostEqual(rotated.Normal.Y, 1, places=6)
        translated = Plane.Transform(Plane(Vector3.UnitX, 0), Matrix.CreateTranslation(2, 0, 0))
        self.assertEqual(translated.D, -2)

    def test_ray_intersections_cover_inside_parallel_behind_and_tangent(self) -> None:
        box = BoundingBox(Vector3(-1), Vector3(1))
        self.assertEqual(Ray(Vector3(-2, 0, 0), Vector3.UnitX).Intersects(box), 1)
        self.assertEqual(Ray(Vector3.Zero, Vector3.UnitX).Intersects(box), 0)
        self.assertIsNone(Ray(Vector3(2, 0, 0), Vector3.UnitY).Intersects(box))
        sphere = BoundingSphere(Vector3.Zero, 1)
        self.assertEqual(Ray(Vector3(-2, 1, 0), Vector3.UnitX).Intersects(sphere), 2)
        self.assertEqual(Ray(Vector3.Zero, Vector3.UnitX).Intersects(sphere), 0)
        plane = Plane(Vector3.UnitX, -1)
        self.assertEqual(Ray(Vector3.Zero, Vector3.UnitX).Intersects(plane), 1)
        self.assertIsNone(Ray(Vector3.Zero, Vector3.UnitY).Intersects(plane))
        self.assertIsNone(Ray(Vector3(2, 0, 0), Vector3.UnitX).Intersects(plane))


class BoundingVolumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.box = BoundingBox(Vector3(-1), Vector3(1))
        self.sphere = BoundingSphere(Vector3.Zero, 1)

    def test_box_creation_corners_containment_and_copy(self) -> None:
        corners = self.box.GetCorners()
        self.assertEqual(len(corners), BoundingBox.CornerCount)
        destination = [None] * 10
        self.assertIsNone(self.box.GetCorners(destination))
        self.assertEqual(destination[:8], corners)
        with self.assertRaises(ValueError):
            self.box.GetCorners([None] * 7)
        self.assertEqual(BoundingBox.CreateFromPoints(corners), self.box)
        self.assertEqual(BoundingBox.CreateFromSphere(self.sphere), self.box)
        self.assertEqual(BoundingBox.CreateMerged(self.box, BoundingBox(Vector3(1), Vector3(2))), BoundingBox(Vector3(-1), Vector3(2)))
        self.assertEqual(self.box.Contains(Vector3(1, 1, 1)), ContainmentType.Contains)
        self.assertEqual(self.box.Contains(BoundingBox(Vector3(-2), Vector3(0))), ContainmentType.Intersects)
        self.assertTrue(self.box.Intersects(BoundingSphere(Vector3(2, 0, 0), 1)))
        clone = copy.deepcopy(self.box)
        clone.Min = Vector3(-5)
        self.assertEqual(self.box.Min, Vector3(-1))

    def test_sphere_creation_containment_transform_and_tangent_rules(self) -> None:
        created = BoundingSphere.CreateFromBoundingBox(self.box)
        self.assertEqual(created.Center, Vector3.Zero)
        self.assertAlmostEqual(created.Radius, math.sqrt(12) / 2, places=6)
        points = [Vector3(-2, 0, 0), Vector3(2, 0, 0), Vector3.Zero]
        self.assertEqual(BoundingSphere.CreateFromPoints(points), BoundingSphere(Vector3.Zero, 2))
        self.assertEqual(BoundingSphere.CreateMerged(self.sphere, BoundingSphere(Vector3(3, 0, 0), 1)), BoundingSphere(Vector3(1.5, 0, 0), 2.5))
        self.assertEqual(self.sphere.Contains(Vector3(1, 0, 0)), ContainmentType.Disjoint)
        self.assertFalse(self.sphere.Intersects(BoundingSphere(Vector3(2, 0, 0), 1)))
        transformed = self.sphere.Transform(Matrix.CreateScale(2, 3, 4) * Matrix.CreateTranslation(5, 6, 7))
        self.assertEqual(transformed.Center, Vector3(5, 6, 7))
        self.assertEqual(transformed.Radius, 4)
        with self.assertRaises(ValueError):
            BoundingSphere(Vector3.Zero, -1)

    def test_plane_volume_classification(self) -> None:
        front = Plane(Vector3.UnitX, -3)
        through = Plane(Vector3.UnitX, 0)
        back = Plane(Vector3.UnitX, 3)
        self.assertEqual(front.Intersects(self.box), PlaneIntersectionType.Back)
        self.assertEqual(through.Intersects(self.box), PlaneIntersectionType.Intersecting)
        self.assertEqual(back.Intersects(self.box), PlaneIntersectionType.Front)
        self.assertEqual(through.Intersects(self.sphere), PlaneIntersectionType.Intersecting)


class FrustumTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frustum = BoundingFrustum(Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver2, 1, 1, 10))

    def test_planes_corners_matrix_and_copy_boundaries(self) -> None:
        self.assertEqual(self.frustum.Near, Plane(Vector3.Backward, 1))
        self.assertEqual(self.frustum.Far.Normal, Vector3.Forward)
        self.assertAlmostEqual(self.frustum.Far.D, -10, places=5)
        corners = self.frustum.GetCorners()
        self.assertEqual(len(corners), BoundingFrustum.CornerCount)
        destination = [None] * 8
        self.assertIsNone(self.frustum.GetCorners(destination))
        self.assertEqual(destination, corners)
        matrix = self.frustum.Matrix
        matrix.M11 = 999
        self.assertNotEqual(self.frustum.Matrix.M11, 999)
        plane = self.frustum.Near
        plane.D = 99
        self.assertNotEqual(self.frustum.Near.D, 99)

    def test_contains_and_intersects_all_selected_shapes(self) -> None:
        inside = Vector3(0, 0, -2)
        outside = Vector3(100, 0, -2)
        self.assertEqual(self.frustum.Contains(inside), ContainmentType.Contains)
        self.assertEqual(self.frustum.Contains(outside), ContainmentType.Disjoint)
        inside_box = BoundingBox(Vector3(-0.25, -0.25, -2.25), Vector3(0.25, 0.25, -1.75))
        outside_box = BoundingBox(Vector3(100), Vector3(101))
        self.assertEqual(self.frustum.Contains(inside_box), ContainmentType.Contains)
        self.assertTrue(self.frustum.Intersects(inside_box))
        self.assertFalse(self.frustum.Intersects(outside_box))
        self.assertTrue(self.frustum.Intersects(BoundingSphere(inside, 0.25)))
        self.assertFalse(self.frustum.Intersects(BoundingSphere(outside, 0.25)))
        self.assertEqual(self.frustum.Intersects(Ray(Vector3.Zero, Vector3.Forward)), 1)
        self.assertEqual(self.frustum.Intersects(Ray(inside, Vector3.Right)), 0)
        self.assertEqual(self.frustum.Intersects(Plane(Vector3.UnitZ, 2)), PlaneIntersectionType.Intersecting)
        same = BoundingFrustum(self.frustum.Matrix)
        self.assertEqual(self.frustum, same)
        self.assertEqual(self.frustum.Contains(same), ContainmentType.Contains)
        self.assertTrue(self.frustum.Intersects(same))
        self.assertEqual(BoundingSphere.CreateFromFrustum(self.frustum).Contains(self.frustum), ContainmentType.Contains)


if __name__ == "__main__":
    unittest.main()
