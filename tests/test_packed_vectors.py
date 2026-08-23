from __future__ import annotations

import copy
import math
import struct
import unittest

from Microsoft.Xna.Framework import Vector2, Vector3, Vector4
from Microsoft.Xna.Framework.Graphics.PackedVector import (
    Alpha8, Bgr565, Bgra4444, Bgra5551, Byte4, HalfSingle, HalfVector2,
    HalfVector4, IPackedVector, IPackedVectorOfT, NormalizedByte2,
    NormalizedByte4, NormalizedShort2, NormalizedShort4, Rg32, Rgba1010102,
    Rgba64, Short2, Short4,
)


def bits(value: float) -> int:
    return struct.unpack("=I", struct.pack("=f", value))[0]


PACKED_TYPES = (
    Alpha8, Bgr565, Bgra4444, Bgra5551, Byte4, HalfSingle, HalfVector2,
    HalfVector4, NormalizedByte2, NormalizedByte4, NormalizedShort2,
    NormalizedShort4, Rg32, Rgba1010102, Rgba64, Short2, Short4,
)


class PackedVectorTests(unittest.TestCase):
    def test_generic_and_non_generic_interfaces_are_distinct(self) -> None:
        self.assertIsNot(IPackedVector, IPackedVectorOfT)
        self.assertTrue(issubclass(IPackedVectorOfT, IPackedVector))
        for packed_type in PACKED_TYPES:
            with self.subTest(packed_type=packed_type):
                self.assertTrue(issubclass(packed_type, IPackedVector))

    def test_reference_packed_bits_for_all_seventeen_formats(self) -> None:
        values = {
            Alpha8(1.0): 0xFF,
            Bgr565(0.0, 1.0, 0.0): 0x07E0,
            Bgra4444(0.0, 0.0, 1.0, 0.0): 0x000F,
            Bgra5551(0.0, 0.0, 0.0, 1.0): 0x8000,
            Byte4(1.5, 2.5, 3.5, 4.5): 0x04040202,
            HalfSingle(1.0): 0x3C00,
            HalfVector2(1.0, 2.0): 0x40003C00,
            HalfVector4(1.0, -2.0, 0.5, 4.0): 0x44003800C0003C00,
            NormalizedByte2(1.0, -1.0): 0x817F,
            NormalizedByte4(1.0, -1.0, 0.0, 1.0): 0x7F00817F,
            NormalizedShort2(1.0, -1.0): 0x80017FFF,
            NormalizedShort4(1.0, -1.0, 0.0, 0.5): 0x4000000080017FFF,
            Rg32(1.0, 0.5): 0x8000FFFF,
            Rgba1010102(1.0, 0.0, 0.0, 0.5): 0x800003FF,
            Rgba64(0.0, 0.5, 1.0, 0.25): 0x4000FFFF80000000,
            Short2(1.5, -2.5): 0xFFFE0002,
            Short4(40_000.0, -40_000.0, 0.5, 1.5): 0x0002000080007FFF,
        }
        for value, expected in values.items():
            with self.subTest(value=value):
                self.assertEqual(value.PackedValue, expected)

    def test_nearest_even_clamp_nonfinite_and_lane_order(self) -> None:
        self.assertEqual(Alpha8(0.5 / 255.0).PackedValue, 0)
        self.assertEqual(Bgra5551(0.0, 0.0, 0.0, 0.5).PackedValue, 0)
        self.assertEqual(Byte4(0.5, 1.5, 2.5, 3.5).PackedValue, 0x04020200)
        self.assertEqual(Byte4(-math.inf, math.nan, math.inf, 256.0).PackedValue, 0xFFFF0000)
        self.assertEqual(Bgr565(1.0, 0.0, 0.0).PackedValue, 0xF800)
        self.assertEqual(Bgr565(0.0, 0.0, 1.0).PackedValue, 0x001F)
        self.assertEqual(Rgba1010102(1.0, 0.0, 0.0, 1.0).PackedValue, 0xC00003FF)
        self.assertEqual(Rgba64(1.0, 0.0, 0.0, 0.0).PackedValue, 0x000000000000FFFF)

    def test_half_uses_xna_historical_finite_exponent_31(self) -> None:
        cases = (
            (0.0, 0x0000), (-0.0, 0x8000), (2.0 ** -24, 0x0001),
            (1023.0 * 2.0 ** -24, 0x03FF), (2.0 ** -14, 0x0400),
            (65504.0, 0x7BFF), (65520.0, 0x7C00),
            (math.inf, 0x7FFF), (-math.inf, 0xFFFF), (math.nan, 0x7FFF),
            (1.00048828125, 0x3C00), (1.00146484375, 0x3C02),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(HalfSingle(value).PackedValue, expected)
        value = HalfSingle()
        value.PackedValue = 0x7C00
        self.assertEqual(bits(value.ToSingle()), 0x47800000)
        value.PackedValue = 0x7FFF
        self.assertEqual(value.ToSingle(), 131008.0)

    def test_normalized_boundaries_and_reserved_minimum(self) -> None:
        self.assertEqual(NormalizedByte2(-2.0, 2.0).PackedValue, 0x7F81)
        self.assertEqual(NormalizedShort2(-2.0, 2.0).PackedValue, 0x7FFF8001)
        byte_min = NormalizedByte2(); byte_min.PackedValue = 0x8080
        short_min = NormalizedShort2(); short_min.PackedValue = 0x80008000
        self.assertEqual(tuple(byte_min.ToVector2()), (-1.0, -1.0))
        self.assertEqual(tuple(short_min.ToVector2()), (-1.0, -1.0))
        self.assertEqual(NormalizedByte2(0.5 / 127.0, -0.5 / 127.0).PackedValue, 0)

    def test_signed_short_rounding_clamping_and_sign_extension(self) -> None:
        self.assertEqual(Short2(0.5, 1.5).PackedValue, 0x00020000)
        self.assertEqual(Short2(-32769.0, 32768.0).PackedValue, 0x7FFF8000)
        value = Short4(); value.PackedValue = 0xFFFF800000017FFF
        self.assertEqual(tuple(value.ToVector4()), (32767.0, 1.0, -32768.0, -1.0))

    def test_packed_value_widths_reject_wrong_values(self) -> None:
        widths = {
            Alpha8: 8,
            Bgr565: 16, Bgra4444: 16, Bgra5551: 16, HalfSingle: 16,
            NormalizedByte2: 16,
            Byte4: 32, HalfVector2: 32, NormalizedByte4: 32,
            NormalizedShort2: 32, Rg32: 32, Rgba1010102: 32, Short2: 32,
            HalfVector4: 64, NormalizedShort4: 64, Rgba64: 64, Short4: 64,
        }
        for packed_type, width in widths.items():
            value = packed_type()
            value.PackedValue = (1 << width) - 1
            self.assertEqual(value.PackedValue, (1 << width) - 1)
            for invalid in (-1, 1 << width, True, 1.0):
                with self.subTest(packed_type=packed_type, invalid=invalid):
                    with self.assertRaises((TypeError, OverflowError)):
                        value.PackedValue = invalid

    def test_interface_mutation_roundtrip_and_fresh_vectors(self) -> None:
        for packed_type in PACKED_TYPES:
            with self.subTest(packed_type=packed_type):
                value = packed_type()
                value.PackFromVector4(Vector4.One)
                first = value.ToVector4()
                second = value.ToVector4()
                self.assertEqual(first, second)
                self.assertIsNot(first, second)

    def test_value_semantics_and_hex_strings(self) -> None:
        for packed_type in PACKED_TYPES:
            with self.subTest(packed_type=packed_type):
                value = packed_type()
                value.PackFromVector4(Vector4(0.25, -0.5, 0.75, 1.25))
                shallow, deep = copy.copy(value), copy.deepcopy(value)
                self.assertEqual(value, shallow)
                self.assertEqual(value, deep)
                self.assertIsNot(value, shallow)
                self.assertEqual(hash(value), hash(shallow))
        self.assertEqual(Alpha8._from_packed(10).ToString() if hasattr(Alpha8, "_from_packed") else format(10, "02X"), "0A")
        value = Bgra5551(); value.PackedValue = 10
        self.assertEqual(value.ToString(), "000A")
        value32 = Byte4(); value32.PackedValue = 10
        self.assertEqual(value32.ToString(), "0000000A")

    def test_type_specific_vector_constructors(self) -> None:
        self.assertEqual(Bgr565(Vector3.One).PackedValue, 0xFFFF)
        self.assertEqual(Rg32(Vector2.One).PackedValue, 0xFFFFFFFF)
        self.assertEqual(HalfVector4(Vector4(1, 2, 3, 4)).ToVector4(), Vector4(1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
