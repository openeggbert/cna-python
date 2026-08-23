from __future__ import annotations

import copy
from datetime import timedelta
import math
import struct
import unittest

from Microsoft.Xna.Framework import (
    Color, Game, GameTime, MathHelper, Matrix, Point, Quaternion, Rectangle,
    Vector2, Vector3, Vector4,
)


def f32(value: float) -> float:
    return struct.unpack("=f", struct.pack("=f", value))[0]


class Float32Tests(unittest.TestCase):
    def test_public_components_narrow_to_binary32(self) -> None:
        value = Vector2(1 / 3, 16_777_217)
        self.assertEqual(value.X, f32(1 / 3))
        self.assertEqual(value.Y, 16_777_216.0)

    def test_nan_infinity_signed_zero_and_overflow(self) -> None:
        self.assertTrue(math.isnan(Vector2(math.nan, 0).X))
        self.assertEqual(Vector2(math.inf, 0).X, math.inf)
        self.assertEqual(Vector2(1e100, 0).X, math.inf)
        self.assertEqual(math.copysign(1, Vector2(-0.0, 0).X), -1)

    def test_divide_follows_ieee_not_python_zero_division(self) -> None:
        self.assertEqual((Vector2(1, -1) / 0).X, math.inf)
        self.assertEqual((Vector2(1, -1) / 0).Y, -math.inf)
        self.assertTrue(math.isnan((Vector2.Zero / 0).X))


class MathValueTests(unittest.TestCase):
    def test_static_value_properties_are_fresh(self) -> None:
        first, second = Vector2.Zero, Vector2.Zero
        self.assertIsNot(first, second)
        first.X = 99
        self.assertEqual(second, Vector2(0, 0))
        self.assertIsNot(Matrix.Identity, Matrix.Identity)
        self.assertIsNot(Color.White, Color.White)

    def test_vector_operations_and_dual_normalize(self) -> None:
        self.assertEqual(Vector2.Add(Vector2(2, 3), Vector2(4, -1)), Vector2(6, 2))
        self.assertEqual(Vector3.Cross(Vector3.UnitX, Vector3.UnitY), Vector3.UnitZ)
        value = Vector2(3, 4)
        value.Normalize()
        self.assertEqual(value, Vector2(0.6, 0.8))
        self.assertEqual(Vector2.Normalize(Vector2(3, 4)), value)

    def test_copy_is_value_copy(self) -> None:
        original = Vector3(1, 2, 3)
        clone = copy.copy(original)
        clone.X = 9
        self.assertEqual(original.X, 1)
        self.assertEqual(copy.deepcopy(original), original)

    def test_matrix_multiplication_is_real(self) -> None:
        combined = Matrix.CreateScale(2) * Matrix.CreateTranslation(3, 4, 5)
        self.assertEqual(combined.M11, 2)
        self.assertEqual(combined.Translation, Vector3(3, 4, 5))
        rotation = Matrix.CreateRotationX(MathHelper.PiOver2)
        self.assertNotEqual(rotation, Matrix.Identity)

    def test_quaternion_axis_angle(self) -> None:
        value = Quaternion.CreateFromAxisAngle(Vector3.UnitY, MathHelper.Pi)
        self.assertAlmostEqual(value.Y, 1.0, places=6)
        self.assertAlmostEqual(value.W, 0.0, places=6)


class IntegralAndColorTests(unittest.TestCase):
    def test_color_clamps_like_xna_not_old_scaffold_test(self) -> None:
        self.assertEqual(Color(256, -4, 10), Color(255, 0, 10, 255))
        self.assertEqual(Color.CornflowerBlue, Color(100, 149, 237, 255))
        self.assertEqual(Color.Transparent, Color(255, 255, 255, 0))
        self.assertEqual(Color.AliceBlue, Color(240, 248, 255, 255))

    def test_normalized_color_rounds_to_even(self) -> None:
        self.assertEqual(Color(0.5, 0.0, 0.0, 1.0).R, 128)

    def test_point_range_and_rectangle_boundaries(self) -> None:
        with self.assertRaises(OverflowError):
            Point(2**31, 0)
        rectangle = Rectangle(0, 0, 10, 10)
        self.assertTrue(rectangle.Contains(9, 9))
        self.assertFalse(rectangle.Contains(10, 10))
        self.assertEqual(Rectangle.Intersect(rectangle, Rectangle(5, 5, 10, 10)), Rectangle(5, 5, 5, 5))

    def test_game_time_uses_timedelta(self) -> None:
        value = GameTime(timedelta(seconds=2), timedelta(milliseconds=16), True)
        self.assertEqual(value.TotalGameTime, timedelta(seconds=2))
        self.assertEqual(value.ElapsedGameTime, timedelta(milliseconds=16))
        self.assertTrue(value.IsRunningSlowly)

    def test_game_timing_properties_validate_before_native_creation(self) -> None:
        game = Game()
        game.TargetElapsedTime = timedelta(milliseconds=10)
        game.InactiveSleepTime = timedelta()
        game.IsFixedTimeStep = False
        game.IsMouseVisible = True
        self.assertEqual(game.TargetElapsedTime, timedelta(milliseconds=10))
        self.assertEqual(game.InactiveSleepTime, timedelta())
        self.assertFalse(game.IsFixedTimeStep)
        self.assertTrue(game.IsMouseVisible)
        with self.assertRaises(ValueError):
            game.TargetElapsedTime = timedelta()
        with self.assertRaises(ValueError):
            game.InactiveSleepTime = timedelta(microseconds=-1)


if __name__ == "__main__":
    unittest.main()
