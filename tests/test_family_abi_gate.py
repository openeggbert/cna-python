"""The generated family ABI modules must be what the canonical headers produce.

Four native families -- the engine layer, sensors and device services, extended
input, and Net/GamerServices/Avatar -- have their ctypes structures, scalar
identities, callbacks and constants *generated* from CNA's headers rather than
transcribed.  Generation only helps if a stale checked-in copy is caught, so this
runs the generator's own ``--check`` and requires it to find nothing.

The falsifiability tests below mutate the generator's inputs rather than its
outputs: a header that gains a field, loses a constant, or changes an integer
width must reach the generated module, or the generator is not measuring.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import generate_family_abi as generator  # noqa: E402


def _cna_root() -> Path | None:
    root = os.environ.get("CNA_SOURCE_ROOT")
    if root is None:
        return None
    include = Path(root) / "modules/c-api/include"
    return Path(root) if (include / "CNA/C/abi.h").is_file() else None


CNA_ROOT = _cna_root()


class GeneratedModulesAreCurrent(unittest.TestCase):
    @unittest.skipIf(CNA_ROOT is None, "CNA_SOURCE_ROOT is not configured")
    def test_every_family_matches_its_headers(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_family_abi.py"),
             "--cna-root", str(CNA_ROOT), "--check"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(completed.returncode, 0,
                         f"generated ABI is stale:\n{completed.stdout}{completed.stderr}")
        self.assertIn("FAMILY_ABI_STALE=0", completed.stdout)

    def test_every_family_module_imports_with_no_native_library(self) -> None:
        for family in generator.FAMILIES:
            with self.subTest(family=family.identifier):
                module = __import__(f"_cna_native.{family.identifier}_abi",
                                    fromlist=["*"])
                prefix = family.prefix
                self.assertTrue(getattr(module, f"{prefix}_STRUCTURES"))
                self.assertTrue(getattr(module, f"{prefix}_CONSTANTS"))

    def test_no_structure_is_measured_by_two_families(self) -> None:
        """One layout, one name, one place.

        A structure two modules both declared would be measured twice, and the
        ABI audit would compare the C compiler against whichever one it happened
        to import.  Families that share a structure import it instead.
        """
        owners: dict[str, str] = {}
        for family in generator.FAMILIES:
            module = __import__(f"_cna_native.{family.identifier}_abi", fromlist=["*"])
            for structure in getattr(module, f"{family.prefix}_STRUCTURES"):
                if structure.__module__ != module.__name__:
                    continue
                previous = owners.get(structure.__name__)
                self.assertIsNone(
                    previous,
                    f"{structure.__name__} is declared by both {previous} and "
                    f"{family.identifier}")
                owners[structure.__name__] = family.identifier

    def test_every_generated_structure_carries_its_headers_field_names(self) -> None:
        for family in generator.FAMILIES:
            module = __import__(f"_cna_native.{family.identifier}_abi", fromlist=["*"])
            for structure in getattr(module, f"{family.prefix}_STRUCTURES"):
                with self.subTest(family=family.identifier, structure=structure.__name__):
                    self.assertTrue(structure._fields_)
                    self.assertTrue(ctypes.sizeof(structure) > 0)


@unittest.skipIf(CNA_ROOT is None, "CNA_SOURCE_ROOT is not configured")
class GeneratorMeasuresRatherThanAsserts(unittest.TestCase):
    """Planted defects in the *header*, which the generator must carry through."""

    def setUp(self) -> None:
        self.include = CNA_ROOT / "modules/c-api/include"

    def _generate(self, family_id: str, mutate) -> str:
        """Regenerates one family from a copy of the headers, mutated."""
        import tempfile

        family = generator.FAMILIES_BY_ID[family_id]
        with tempfile.TemporaryDirectory(prefix="cna-python-abi-mutation-") as directory:
            root = Path(directory) / "CNA/C"
            root.mkdir(parents=True)
            for source in (self.include / "CNA/C").glob("*.h"):
                text = source.read_text(encoding="utf-8")
                if source.name in family.headers:
                    text = mutate(source.name, text)
                (root / source.name).write_text(text, encoding="utf-8")
            module, _probe = generator.generate(family, Path(directory))
        return module

    def test_a_removed_field_disappears_from_the_generated_layout(self) -> None:
        unchanged = self._generate("devices", lambda name, text: text)
        self.assertIn('("magnetic_heading", c.c_double)', unchanged)
        mutated = self._generate(
            "devices",
            lambda name, text: text.replace("    double magnetic_heading;\n", "", 1)
            if name == "sensors.h" else text)
        self.assertNotIn('("magnetic_heading", c.c_double)', mutated)

    def test_a_widened_field_changes_the_generated_type(self) -> None:
        mutated = self._generate(
            "devices",
            lambda name, text: text.replace("    double magnetic_heading;",
                                            "    float magnetic_heading;", 1)
            if name == "sensors.h" else text)
        self.assertIn('("magnetic_heading", c.c_float)', mutated)

    def test_a_changed_constant_changes_the_generated_value(self) -> None:
        unchanged = self._generate("devices", lambda name, text: text)
        self.assertIn("CNA_SENSOR_STATE_DISABLED = 5", unchanged)
        mutated = self._generate(
            "devices",
            lambda name, text: text.replace(
                "#define CNA_SENSOR_STATE_DISABLED UINT32_C(5)",
                "#define CNA_SENSOR_STATE_DISABLED UINT32_C(9)", 1)
            if name == "sensors.h" else text)
        self.assertIn("CNA_SENSOR_STATE_DISABLED = 9", mutated)

    def test_an_unmappable_field_type_stops_the_generator(self) -> None:
        with self.assertRaises((generator.GenerationError, KeyError)):
            self._generate(
                "devices",
                lambda name, text: text.replace("    double magnetic_heading;",
                                                "    struct CNA_NoSuchThing magnetic_heading;", 1)
                if name == "sensors.h" else text)


if __name__ == "__main__":
    unittest.main()
