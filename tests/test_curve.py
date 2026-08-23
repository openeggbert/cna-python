from __future__ import annotations

import copy
import math
import struct
import unittest

from Microsoft.Xna.Framework import (
    Curve, CurveContinuity, CurveKey, CurveKeyCollection, CurveLoopType,
    CurveTangent,
)


def bits(value: float) -> int:
    return struct.unpack("=I", struct.pack("=f", value))[0]


def two_key_curve() -> Curve:
    value = Curve()
    value.Keys.Add(CurveKey(5.0, 0.0))
    value.Keys.Add(CurveKey(7.0, 10.0))
    return value


class CurveTests(unittest.TestCase):
    def test_enum_values_and_defaults(self) -> None:
        self.assertEqual([int(value) for value in CurveContinuity], [0, 1])
        self.assertEqual([int(value) for value in CurveLoopType], [0, 1, 2, 3, 4])
        self.assertEqual([int(value) for value in CurveTangent], [0, 1, 2])
        curve = Curve()
        self.assertEqual(curve.PreLoop, CurveLoopType.Constant)
        self.assertEqual(curve.PostLoop, CurveLoopType.Constant)
        self.assertTrue(curve.IsConstant)
        self.assertEqual(curve.Evaluate(100.0), 0.0)

    def test_curve_key_contract_nan_and_copy(self) -> None:
        value = CurveKey(1.0, 2.0, 3.0, 4.0, CurveContinuity.Step)
        clone = value.Clone()
        shallow, deep = copy.copy(value), copy.deepcopy(value)
        self.assertEqual(value, clone)
        self.assertEqual(value, shallow)
        self.assertEqual(value, deep)
        self.assertIsNot(value, clone)
        clone.Value = 20.0
        self.assertEqual(value.Value, 2.0)
        self.assertEqual(value.CompareTo(CurveKey(2.0, 0.0)), -1)
        self.assertEqual(value.CompareTo(CurveKey(1.0, 99.0)), 0)
        nan_a, nan_b = CurveKey(math.nan, 1.0), CurveKey(math.nan, 1.0)
        self.assertEqual(nan_a.CompareTo(nan_b), 1)
        self.assertFalse(nan_a.Equals(nan_b))
        with self.assertRaises(TypeError):
            value.CompareTo(None)  # type: ignore[arg-type]

    def test_collection_sorts_and_preserves_equal_position_insertion_order(self) -> None:
        keys = CurveKeyCollection()
        middle_a = CurveKey(1.0, 10.0)
        middle_b = CurveKey(1.0, 20.0)
        keys.Add(CurveKey(2.0, 30.0))
        keys.Add(middle_a)
        keys.Add(CurveKey(0.0, 0.0))
        keys.Add(middle_b)
        self.assertEqual([key.Position for key in keys], [0.0, 1.0, 1.0, 2.0])
        self.assertIs(keys[1], middle_a)
        self.assertIs(keys[2], middle_b)
        middle_a.Value = 11.0
        self.assertEqual(keys[1].Value, 11.0)
        self.assertEqual(keys.IndexOf(middle_a), 1)
        self.assertTrue(keys.Contains(CurveKey(1.0, 11.0)))

    def test_collection_index_replacement_removal_copy_and_shallow_clone(self) -> None:
        keys = CurveKeyCollection()
        first, second = CurveKey(0.0, 1.0), CurveKey(2.0, 3.0)
        keys.Add(first); keys.Add(second)
        replacement = CurveKey(1.0, 2.0)
        keys[1] = replacement
        self.assertEqual([key.Position for key in keys], [0.0, 1.0])
        same_position = CurveKey(1.0, 20.0)
        keys[1] = same_position
        self.assertIs(keys[1], same_position)
        destination = [CurveKey(9.0, 9.0) for _ in range(4)]
        keys.CopyTo(destination, 1)
        self.assertIs(destination[1], first)
        self.assertIs(destination[2], same_position)
        clone = keys.Clone()
        self.assertIsNot(clone, keys)
        self.assertIs(clone[0], keys[0])
        clone[0].Value = 42.0
        self.assertEqual(keys[0].Value, 42.0)
        self.assertTrue(keys.Remove(first))
        self.assertFalse(keys.Remove(first))
        keys.RemoveAt(0)
        self.assertEqual(keys.Count, 0)
        self.assertFalse(keys.IsReadOnly)

    def test_basic_hermite_step_and_exact_key_evaluation(self) -> None:
        curve = Curve()
        curve.Keys.Add(CurveKey(0.0, 0.0))
        curve.Keys.Add(CurveKey(1.0, 10.0))
        self.assertEqual(bits(curve.Evaluate(0.25)), 0x3FC80000)
        asymmetric = Curve()
        asymmetric.Keys.Add(CurveKey(0.0, 0.0, 99.0, 4.0))
        asymmetric.Keys.Add(CurveKey(2.0, 10.0, -2.0, 77.0))
        self.assertEqual(bits(asymmetric.Evaluate(1.0)), 0x40B80000)
        step = Curve()
        step.Keys.Add(CurveKey(0.0, 2.0, 0.0, 0.0, CurveContinuity.Step))
        step.Keys.Add(CurveKey(1.0, 9.0))
        self.assertEqual(bits(step.Evaluate(0.999)), 0x40000000)
        self.assertEqual(bits(step.Evaluate(1.0)), 0x41100000)

    def test_every_pre_and_post_loop_mode(self) -> None:
        pre_expected = {
            CurveLoopType.Constant: 0.0,
            CurveLoopType.Cycle: 5.0,
            CurveLoopType.CycleOffset: -5.0,
            CurveLoopType.Oscillate: 5.0,
        }
        post_expected = {
            CurveLoopType.Constant: 10.0,
            CurveLoopType.Cycle: 5.0,
            CurveLoopType.CycleOffset: 15.0,
            CurveLoopType.Oscillate: 5.0,
        }
        for mode, expected in pre_expected.items():
            curve = two_key_curve(); curve.PreLoop = mode
            self.assertEqual(curve.Evaluate(4.0), expected)
        for mode, expected in post_expected.items():
            curve = two_key_curve(); curve.PostLoop = mode
            self.assertEqual(curve.Evaluate(8.0), expected)
        linear = two_key_curve()
        linear.Keys[0].TangentIn = 2.0
        linear.Keys[1].TangentOut = 3.0
        linear.PreLoop = linear.PostLoop = CurveLoopType.Linear
        self.assertEqual(linear.Evaluate(4.0), -2.0)
        self.assertEqual(linear.Evaluate(9.0), 16.0)

    def test_negative_exact_cycles_and_oscillation_parity(self) -> None:
        cycle = two_key_curve(); cycle.PreLoop = CurveLoopType.Cycle
        offset = two_key_curve(); offset.PreLoop = CurveLoopType.CycleOffset
        oscillate = two_key_curve(); oscillate.PreLoop = CurveLoopType.Oscillate
        self.assertEqual(cycle.Evaluate(3.0), 10.0)
        self.assertEqual(offset.Evaluate(3.0), -10.0)
        self.assertEqual(oscillate.Evaluate(3.0), 10.0)
        post = two_key_curve(); post.PostLoop = CurveLoopType.CycleOffset
        self.assertEqual(post.Evaluate(9.0), 20.0)

    def test_flat_linear_and_smooth_tangents(self) -> None:
        curve = Curve()
        curve.Keys.Add(CurveKey(0.0, 0.0))
        curve.Keys.Add(CurveKey(1.0, 10.0))
        curve.Keys.Add(CurveKey(3.0, 30.0))
        curve.ComputeTangent(1, CurveTangent.Flat)
        self.assertEqual((curve.Keys[1].TangentIn, curve.Keys[1].TangentOut), (0.0, 0.0))
        curve.ComputeTangent(1, CurveTangent.Linear)
        self.assertEqual((curve.Keys[1].TangentIn, curve.Keys[1].TangentOut), (10.0, 20.0))
        curve.ComputeTangents(CurveTangent.Smooth)
        self.assertEqual(bits(curve.Keys[1].TangentIn), 0x41200000)
        self.assertEqual(bits(curve.Keys[1].TangentOut), 0x41A00000)
        self.assertEqual(curve.Keys[0].TangentIn, 0.0)
        self.assertEqual(curve.Keys[2].TangentOut, 0.0)

    def test_duplicate_positions_and_zero_range_are_deterministic(self) -> None:
        curve = Curve()
        first, second = CurveKey(1.0, 10.0), CurveKey(1.0, 20.0)
        curve.Keys.Add(first); curve.Keys.Add(second)
        self.assertEqual(curve.Evaluate(1.0), 10.0)
        curve.PreLoop = CurveLoopType.Cycle
        curve.PostLoop = CurveLoopType.Oscillate
        self.assertEqual(curve.Evaluate(0.0), 10.0)
        self.assertEqual(curve.Evaluate(2.0), 20.0)

    def test_curve_clone_has_independent_collection_and_shared_keys(self) -> None:
        curve = two_key_curve()
        clone = curve.Clone()
        self.assertIsNot(clone, curve)
        self.assertIsNot(clone.Keys, curve.Keys)
        self.assertIs(clone.Keys[0], curve.Keys[0])
        clone.Keys[0].Value = 42.0
        self.assertEqual(curve.Keys[0].Value, 42.0)
        clone.Keys.RemoveAt(1)
        self.assertEqual(curve.Keys.Count, 2)
        self.assertEqual(clone.Keys.Count, 1)


if __name__ == "__main__":
    unittest.main()
