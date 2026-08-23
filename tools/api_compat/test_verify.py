from __future__ import annotations

import json
from pathlib import Path
import unittest

from verify import (
    diagnose_broken_fixture, expected_callable, projected_type_identity,
    projected_type_name,
)


class BrokenFixtureTests(unittest.TestCase):
    def test_packed_vector_generic_collision_has_two_measured_identities(self) -> None:
        generic = "Microsoft.Xna.Framework.Graphics.PackedVector.IPackedVector`1"
        package = "Microsoft.Xna.Framework.Graphics.PackedVector"
        self.assertEqual(projected_type_name(generic), "IPackedVectorOfT")
        self.assertEqual(projected_type_identity(package, "IPackedVectorOfT"), generic)
        self.assertNotEqual(projected_type_name(generic), "IPackedVector")

    def test_design_omits_unobserved_context_and_attribute_parameters(self) -> None:
        callable_value = expected_callable({
            "kind": "method", "name": "GetProperties",
            "returnType": "System.ComponentModel.PropertyDescriptorCollection",
            "genericParameters": [], "parameters": [
                {"name": "context", "type": "System.ComponentModel.ITypeDescriptorContext", "out": False},
                {"name": "value", "type": "System.Object", "out": False},
                {"name": "attributes", "type": "System.Attribute[]", "out": False},
            ],
        }, "GetProperties", "Microsoft.Xna.Framework.Design.MathTypeConverter")
        self.assertEqual(
            [(value.name, value.annotation) for value in callable_value.parameters],
            [("value", "object")],
        )
        self.assertEqual(callable_value.return_type, "Mapping[str, object]")

    def test_audio_contextual_member_mappings_are_machine_measured(self) -> None:
        get_data = expected_callable({
            "kind": "method", "name": "GetData", "returnType": "System.Int32",
            "genericParameters": [], "parameters": [{
                "name": "buffer", "type": "System.Byte[]", "out": False,
            }],
        }, "GetData", "Microsoft.Xna.Framework.Audio.Microphone")
        self.assertEqual(get_data.parameters[0].annotation, "MutableSequence[int]")

    def test_deliberately_broken_fixtures_cover_required_categories(self) -> None:
        fixtures = json.loads((Path(__file__).parent / "fixtures/broken.json").read_text())
        expected = {
            "MISSING_MEMBER", "PROPERTY_MAPPING_MISMATCH", "ENUM_VALUE_MISMATCH",
            "OVERLOAD_MAPPING_MISMATCH", "UNEXPECTED_TYPE", "INTERNAL_TYPE_LEAK",
            "RAW_HANDLE_LEAK", "LANGUAGE_MAPPING_MISMATCH", "FIELD_MAPPING_MISMATCH",
            "PARAMETER_MAPPING_MISMATCH", "RETURN_MAPPING_MISMATCH",
            "INTERFACE_MAPPING_MISMATCH", "GENERIC_MAPPING_MISMATCH",
            "METHOD_SIGNATURE_MAPPING_MISMATCH",
        }
        self.assertEqual({fixture["category"] for fixture in fixtures}, expected)
        self.assertEqual(len(fixtures), 17)
        for fixture in fixtures:
            with self.subTest(fixture=fixture["name"]):
                self.assertIn(fixture["category"], diagnose_broken_fixture(fixture))


if __name__ == "__main__":
    unittest.main()
