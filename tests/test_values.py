from __future__ import annotations

import copy
from datetime import timedelta
import math
import struct
import unittest

from Microsoft.Xna.Framework import (
    Color, Game, GameTime, MathHelper, Matrix, Plane, Point, Quaternion,
    Rectangle, Vector2, Vector3, Vector4,
)
from Microsoft.Xna.Framework._math import _cos32, _sin32, _sqrt32
from Microsoft.Xna.Framework._numeric import add32, div32, f32 as narrow32, mul32


def f32(value: float) -> float:
    return struct.unpack("=f", struct.pack("=f", value))[0]


def bits(value: float) -> int:
    return struct.unpack("=I", struct.pack("=f", value))[0]


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

    def test_private_helpers_preserve_binary32_edges_and_order(self) -> None:
        self.assertEqual(math.copysign(1.0, narrow32(0.0)), 1.0)
        self.assertEqual(math.copysign(1.0, narrow32(-0.0)), -1.0)
        self.assertTrue(math.isnan(narrow32(math.nan)))
        self.assertEqual(narrow32(1e100), math.inf)
        self.assertEqual(narrow32(-1e100), -math.inf)
        self.assertEqual(narrow32(2.0**-149), 2.0**-149)
        self.assertEqual(narrow32(2.0**-150), 0.0)
        self.assertEqual(add32(add32(16_777_216.0, 1.0), -16_777_216.0), 0.0)
        self.assertEqual(mul32(1.0000001192092896, 1.0000001192092896), f32(1.0000002384185933))
        self.assertEqual(div32(1.0, 3.0), f32(1.0 / 3.0))
        self.assertEqual(math.copysign(1.0, div32(0.0, -2.0)), -1.0)
        self.assertEqual(_sqrt32(2.0), f32(math.sqrt(2.0)))
        self.assertTrue(math.isnan(_sqrt32(-1.0)))
        self.assertEqual(_sin32(MathHelper.PiOver2), f32(math.sin(f32(MathHelper.PiOver2))))
        self.assertEqual(_cos32(MathHelper.Pi), f32(math.cos(f32(MathHelper.Pi))))

    def test_nan_binary32_payload_survives_a_narrowing_round_trip(self) -> None:
        value = struct.unpack("=f", struct.pack("=I", 0x7FC12345))[0]
        bits = struct.unpack("=I", struct.pack("=f", narrow32(value)))[0]
        self.assertEqual(bits & 0x003FFFFF, 0x00012345)


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

    def test_xna_binary32_golden_edges(self) -> None:
        self.assertEqual(bits(MathHelper.CatmullRom(-10, -10, -10, -7, 0.3)), 0xC1218313)
        self.assertEqual(bits(MathHelper.Hermite(-10, -10, -10, -10, 1.1)), 0xC1351EBA)
        self.assertEqual(bits(MathHelper.WrapAngle(123456.789)), 0xBFC2E06C)
        self.assertTrue(math.isnan(MathHelper.Hermite(1, math.inf, 2, 0, 0)))

        minimum = Vector3.Min(Vector3(math.nan, 1, math.nan), Vector3(7, math.nan, math.nan))
        self.assertEqual(minimum.X, 7.0)
        self.assertTrue(math.isnan(minimum.Y))
        self.assertTrue(math.isnan(minimum.Z))
        self.assertEqual(Vector3(1, 2, 3).GetHashCode(), -1_077_936_128)
        self.assertEqual(Matrix.Identity.GetHashCode(), -33_554_432)

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

    def test_quaternion_matrix_concatenation_and_nonfinite(self) -> None:
        rotation = Matrix.CreateRotationY(0.7)
        value = Quaternion.CreateFromRotationMatrix(rotation)
        self.assertAlmostEqual(Matrix.CreateFromQuaternion(value).M11, rotation.M11, places=6)
        first = Quaternion.CreateFromAxisAngle(Vector3.UnitX, 0.2)
        second = Quaternion.CreateFromAxisAngle(Vector3.UnitY, 0.4)
        self.assertEqual(Quaternion.Concatenate(first, second), second * first)
        self.assertTrue(math.isnan(Quaternion.Normalize(Quaternion.Zero if hasattr(Quaternion, "Zero") else Quaternion()).X))

    def test_matrix_complete_pure_contract(self) -> None:
        value = Matrix.Identity
        value.Right = Vector3(2, 3, 4)
        value.Down = Vector3(5, 6, 7)
        value.Forward = Vector3(8, 9, 10)
        self.assertEqual(value.Right, Vector3(2, 3, 4))
        self.assertEqual(value.Up, Vector3(-5, -6, -7))
        self.assertEqual(value.Backward, Vector3(-8, -9, -10))

        composed = Matrix.CreateScale(2, 3, 4) * Matrix.CreateRotationY(0.25) * Matrix.CreateTranslation(5, 6, 7)
        inverse = Matrix.Invert(composed)
        identity = composed * inverse
        for actual, expected in zip(identity, Matrix.Identity):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertTrue(all(math.isnan(component) for component in Matrix.Invert(Matrix())))
        succeeded, scale, rotation, translation = composed.Decompose()
        self.assertTrue(succeeded)
        self.assertEqual(scale, Vector3(2, 3, 4))
        self.assertEqual(translation, Vector3(5, 6, 7))
        self.assertEqual(Matrix.Transform(Matrix.Identity, rotation), Matrix.CreateFromQuaternion(rotation))
        self.assertEqual(Matrix.Lerp(Matrix.Identity, Matrix.CreateScale(3), 0.5).M11, 2.0)
        self.assertAlmostEqual(Matrix.CreateFromAxisAngle(Vector3.UnitY, 0.25).M11, Matrix.CreateRotationY(0.25).M11)
        self.assertEqual(Matrix.CreateFromYawPitchRoll(0.25, 0, 0), Matrix.CreateRotationY(0.25))

        infinite = Matrix.CreatePerspective(4, 3, 0.1, math.inf)
        self.assertTrue(math.isnan(infinite.M33))
        self.assertTrue(math.isnan(infinite.M43))
        with self.assertRaises(ValueError):
            Matrix.CreatePerspectiveFieldOfView(0, 1, 0.1, 100)
        with self.assertRaises(ValueError):
            Matrix.CreatePerspective(4, 3, 10, 5)

        plane = Plane(Vector3.UnitY, -2)
        reflected = Vector3.Transform(Vector3(1, 3, 4), Matrix.CreateReflection(plane))
        self.assertEqual(reflected, Vector3(1, 1, 4))
        shadow = Matrix.CreateShadow(Vector3.Down, Plane(Vector3.Up, 0))
        self.assertEqual(Vector3.Transform(Vector3(2, 3, 4), shadow).Y, 0.0)

    def test_transform_range_matches_xna_negative_edge_rules(self) -> None:
        source = [Vector3.Zero]
        destination = [Vector3.One]
        self.assertIsNone(Vector3.Transform(source, 0, Matrix.Identity, destination, 0, -1))
        self.assertEqual(destination, [Vector3.One])
        with self.assertRaises(IndexError):
            Vector3.Transform(source, -1, Matrix.Identity, destination, 0, 1)


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
