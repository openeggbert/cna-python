from __future__ import annotations

import math
import struct
import unittest

from Microsoft.Xna.Framework import (
    BoundingBox, BoundingSphere, Color, Matrix, Plane, Point, Quaternion, Ray,
    Rectangle, Vector2, Vector3, Vector4,
)
from Microsoft.Xna.Framework.Design import (
    BoundingBoxConverter, BoundingSphereConverter, ColorConverter,
    MathTypeConverter, MatrixConverter, PlaneConverter, PointConverter,
    QuaternionConverter, RayConverter, RectangleConverter, Vector2Converter,
    Vector3Converter, Vector4Converter,
)


def bits(value: float) -> int:
    return struct.unpack("=I", struct.pack("=f", value))[0]


VALUES = (
    (PointConverter, Point(1, 2), ("X", "Y")),
    (RectangleConverter, Rectangle(1, 2, 3, 4), ("X", "Y", "Width", "Height")),
    (Vector2Converter, Vector2(1.0, 2.0), ("X", "Y")),
    (Vector3Converter, Vector3(1.0, 2.0, 3.0), ("X", "Y", "Z")),
    (Vector4Converter, Vector4(1.0, 2.0, 3.0, 4.0), ("X", "Y", "Z", "W")),
    (QuaternionConverter, Quaternion(1.0, 2.0, 3.0, 4.0), ("X", "Y", "Z", "W")),
    (ColorConverter, Color(10, 20, 30, 40), ("R", "G", "B", "A")),
    (MatrixConverter, Matrix.Identity, ("Translation", *Matrix._names)),
    (BoundingBoxConverter, BoundingBox(Vector3(1.0), Vector3(2.0)), ("Min", "Max")),
    (BoundingSphereConverter, BoundingSphere(Vector3(1.0), 2.0), ("Center", "Radius")),
    (PlaneConverter, Plane(Vector3(1.0), 2.0), ("Normal", "D")),
    (RayConverter, Ray(Vector3(1.0), Vector3(2.0)), ("Position", "Direction")),
)


class DesignConverterTests(unittest.TestCase):
    def test_base_capabilities_and_no_support_framework_types(self) -> None:
        converter = MathTypeConverter()
        self.assertTrue(converter.CanConvertFrom(str))
        self.assertFalse(converter.CanConvertFrom(int))
        self.assertTrue(converter.CanConvertTo(str))
        self.assertTrue(converter.CanConvertTo(tuple))
        self.assertTrue(converter.GetCreateInstanceSupported())
        self.assertTrue(converter.GetPropertiesSupported())
        self.assertEqual(dict(converter.GetProperties(object())), {})
        self.assertEqual(converter.ConvertTo(None, Point.Zero, str), "{X:0 Y:0}")

        class DerivedVector3Converter(Vector3Converter):
            pass

        derived = DerivedVector3Converter()
        value = derived.ConvertFrom(None, "1, 2, 3")
        self.assertEqual(derived.ConvertTo(None, value, str), "1, 2, 3")
        self.assertEqual(derived.CreateInstance(dict(derived.GetProperties(value))), value)

    def test_exact_property_order_and_immutable_snapshots(self) -> None:
        for converter_type, value, names in VALUES:
            with self.subTest(converter_type=converter_type):
                converter = converter_type()
                self.assertEqual(tuple(converter.propertyDescriptions), names)
                properties = converter.GetProperties(value)
                self.assertEqual(tuple(properties), names)
                with self.assertRaises(TypeError):
                    properties[names[0]] = object()  # type: ignore[index]
        sphere = BoundingSphere(Vector3(1, 2, 3), 4)
        properties = BoundingSphereConverter().GetProperties(sphere)
        center = properties["Center"]
        center.X = 99  # type: ignore[union-attr]
        self.assertEqual(sphere.Center.X, 1.0)

    def test_support_matrix(self) -> None:
        supported = {PointConverter, Vector2Converter, Vector3Converter,
                     Vector4Converter, QuaternionConverter, ColorConverter}
        for converter_type, _, _ in VALUES:
            converter = converter_type()
            with self.subTest(converter_type=converter_type):
                self.assertEqual(converter.CanConvertFrom(str), converter_type in supported)
                self.assertFalse(converter.CanConvertFrom(int))
                self.assertTrue(converter.CanConvertTo(str))
                self.assertTrue(converter.CanConvertTo(tuple))

    def test_invariant_en_us_and_german_formatting(self) -> None:
        vector = Vector3(1.25, -2.5, 3.75)
        converter = Vector3Converter()
        self.assertEqual(converter.ConvertTo(None, vector, str), "1.25, -2.5, 3.75")
        self.assertEqual(converter.ConvertTo("invariant", vector, str), "1.25, -2.5, 3.75")
        self.assertEqual(converter.ConvertTo("en-US", vector, str), "1.25, -2.5, 3.75")
        self.assertEqual(converter.ConvertTo("de-DE", vector, str), "1,25; -2,5; 3,75")
        special = Vector4(math.nan, math.inf, -math.inf, -0.0)
        self.assertEqual(Vector4Converter().ConvertTo(None, special, str), "NaN, Infinity, -Infinity, 0")
        self.assertEqual(Vector4Converter().ConvertTo("de-DE", special, str), "NaN; +unendlich; -unendlich; 0")
        extremes = Vector2(1e-30, 3.40282347e38)
        self.assertEqual(Vector2Converter().ConvertTo(None, extremes, str), "1E-30, 3.402823E+38")

    def test_string_parsing_preserves_binary32_and_culture(self) -> None:
        point = PointConverter().ConvertFrom(None, "2147483647, -2147483648")
        self.assertEqual(point, Point(2_147_483_647, -2_147_483_648))
        value = Vector3Converter().ConvertFrom(None, "-0, 1e-30, 3.40282347E+38")
        self.assertEqual([bits(component) for component in value], [0x80000000, 0x0DA24260, 0x7F7FFFFF])
        german = Vector3Converter().ConvertFrom("de-DE", "1,5; -2,25; 3,75")
        self.assertEqual([bits(component) for component in german], [0x3FC00000, 0xC0100000, 0x40700000])
        special = Vector3Converter().ConvertFrom("de-DE", "NaN; +unendlich; -unendlich")
        self.assertTrue(math.isnan(special.X))
        self.assertEqual((special.Y, special.Z), (math.inf, -math.inf))
        self.assertEqual(ColorConverter().ConvertFrom(None, "0,255,10,40"), Color(0, 255, 10, 40))

    def test_unsupported_string_input_and_fallback_output(self) -> None:
        unsupported = (
            (RectangleConverter(), Rectangle(1, 2, 3, 4)),
            (MatrixConverter(), Matrix.Identity),
            (BoundingBoxConverter(), BoundingBox(Vector3.Zero, Vector3.One)),
            (BoundingSphereConverter(), BoundingSphere(Vector3.Zero, 1.0)),
            (PlaneConverter(), Plane(Vector3.Up, 2.0)),
            (RayConverter(), Ray(Vector3.Zero, Vector3.One)),
        )
        for converter, value in unsupported:
            with self.subTest(converter=type(converter)):
                with self.assertRaises(TypeError):
                    converter.ConvertFrom(None, "1,2")
                self.assertEqual(converter.ConvertTo("de-DE", value, str), value.ToString())

    def test_create_instance_for_every_shape_and_extra_values(self) -> None:
        for converter_type, value, _ in VALUES:
            with self.subTest(converter_type=converter_type):
                converter = converter_type()
                properties = dict(converter.GetProperties(value))
                properties["Unrelated"] = object()
                self.assertEqual(converter.CreateInstance(properties), value)
        matrix_values = {name: float(index) for index, name in enumerate(Matrix._names, 1)}
        matrix_values["Translation"] = Vector3(100, 200, 300)
        matrix = MatrixConverter().CreateInstance(matrix_values)
        self.assertEqual((matrix.M11, matrix.M24, matrix.M41, matrix.M44), (1.0, 8.0, 13.0, 16.0))

    def test_executable_instance_descriptors_for_every_shape(self) -> None:
        for converter_type, value, _ in VALUES:
            with self.subTest(converter_type=converter_type):
                constructor, arguments = converter_type().ConvertTo(None, value, tuple)
                self.assertIsInstance(arguments, tuple)
                self.assertEqual(constructor(*arguments), value)

    def test_color_is_byte_domain_without_named_colors(self) -> None:
        converter = ColorConverter()
        self.assertEqual(converter.ConvertTo(None, Color(0, 255, 10, 40), str), "0, 255, 10, 40")
        for invalid in ("Red", "-1,0,0,0", "256,0,0,0", "0.5,0,0,0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises((TypeError, ValueError)):
                    converter.ConvertFrom(None, invalid)

    def test_invalid_strings_cultures_and_property_maps(self) -> None:
        converter = Vector3Converter()
        for invalid in ("", "1,2", "1,2,3,4", "1,,3", "3.5e38,0,0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises((TypeError, ValueError)):
                    converter.ConvertFrom(None, invalid)
        with self.assertRaises(ValueError):
            converter.ConvertFrom("de-DE", "1.5; -2.25; 3.75")
        with self.assertRaises(ValueError):
            converter.ConvertFrom("fr-FR", "1;2;3")
        with self.assertRaises(TypeError):
            converter.CreateInstance(None)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            converter.CreateInstance({"X": 1.0, "Y": 2.0})
        with self.assertRaises(TypeError):
            converter.CreateInstance({"X": 1, "Y": 2.0, "Z": 3.0})
        with self.assertRaises(ValueError):
            converter.CreateInstance({"X": 1.0, "Y": None, "Z": 3.0})


if __name__ == "__main__":
    unittest.main()
