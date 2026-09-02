"""The reference extractor has to be an authority before any profile trusts it.

Every strict profile in this repository is verified against a checked-in
contract JSON, and from this session on those contracts are *generated* from
locally admitted Microsoft reference assemblies rather than hand-written.  That
only helps if the generator is right, so the proof is: re-deriving the
already-accepted ``xna40-windows-runtime`` contract -- 257 types and 2,964
members that the strict verifier has been green against for the whole project --
must reproduce it exactly.  A generator that cannot re-derive the one contract
whose correctness is already established is not evidence for the ones whose
correctness is not.

These tests do not run the .NET tool when its inputs are absent, and they say
which input was missing rather than passing quietly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/api_compat"
PROFILES = TOOLS / "profiles"

sys.path.insert(0, str(TOOLS))

import compare_contracts  # noqa: E402


def _profiles_with_contracts() -> list[tuple[str, dict]]:
    found = []
    for path in sorted(PROFILES.glob("*.json")):
        profile = json.loads(path.read_text())
        if "contract" in profile:
            found.append((path.stem, profile))
    return found


def _absent_inputs(profile: dict) -> list[str]:
    absent = []
    if shutil.which("dotnet") is None:
        absent.append("dotnet")
    root = Path(os.path.expanduser(profile["assemblyRoot"]))
    for name in profile["referenceAssemblies"]:
        if not (root / name).is_file():
            absent.append(str(root / name))
    for directory in profile.get("resolveDirectories", []):
        if not Path(os.path.expanduser(directory)).is_dir():
            absent.append(directory)
    return absent


class ReferenceContractsAreGenerated(unittest.TestCase):
    def test_every_profile_contract_re_derives_from_its_assemblies(self) -> None:
        profiles = _profiles_with_contracts()
        self.assertTrue(profiles, "no profile declares a contract")
        for identifier, profile in profiles:
            with self.subTest(profile=identifier):
                absent = _absent_inputs(profile)
                if absent:
                    self.skipTest(f"reference input absent: {', '.join(absent)}")
                completed = subprocess.run(
                    [sys.executable, str(TOOLS / "extract_reference.py"),
                     "--check", identifier],
                    capture_output=True, text=True, cwd=ROOT,
                )
                self.assertEqual(
                    completed.returncode, 0,
                    f"{identifier} contract is not what its assemblies say:\n"
                    f"{completed.stdout}{completed.stderr}")
                self.assertIn(f"{identifier} CONTRACT_UP_TO_DATE=yes", completed.stdout)

    def test_every_profile_pins_the_hash_of_every_assembly_it_names(self) -> None:
        for identifier, profile in _profiles_with_contracts():
            with self.subTest(profile=identifier):
                self.assertEqual(
                    sorted(profile["referenceSha256"]),
                    sorted(profile["referenceAssemblies"]),
                    "a profile must pin exactly the assemblies it reads")
                for digest in profile["referenceSha256"].values():
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_profile_counts_agree_with_the_contract_they_point_at(self) -> None:
        for identifier, profile in _profiles_with_contracts():
            with self.subTest(profile=identifier):
                contract = json.loads(
                    (TOOLS / "reference" / profile["contract"]).read_text())
                self.assertEqual(profile["referenceTypes"], len(contract["types"]))
                self.assertEqual(
                    profile["referenceMembers"],
                    sum(len(entry["members"]) for entry in contract["types"]))


class ContractComparerCatchesWhatItMustCatch(unittest.TestCase):
    """The comparer is the oracle; an oracle that cannot fail proves nothing."""

    BASE = {
        "types": [{
            "name": "N.T", "kind": "class", "flags": False, "sealed": False,
            "underlyingType": None, "baseType": "System.Object",
            "interfaces": [], "directInterfaces": [], "genericParameters": [],
            "members": [
                {"kind": "method", "name": "M", "static": False, "access": "public",
                 "returnType": "System.Void", "genericParameters": [],
                 "parameters": [{"name": "a", "type": "System.Int32", "ref": False,
                                 "out": False, "in": False, "optional": False}]},
                {"kind": "field", "name": "F", "type": "System.Int32",
                 "static": True, "constant": True, "value": "3"},
            ],
        }],
    }

    def _mutate(self, mutate) -> list[str]:
        left = json.loads(json.dumps(self.BASE))
        right = json.loads(json.dumps(self.BASE))
        mutate(right)
        return compare_contracts.compare(left, right)

    def test_identical_contracts_differ_nowhere(self) -> None:
        self.assertEqual(self._mutate(lambda c: None), [])

    def test_a_dropped_type_is_caught(self) -> None:
        self.assertTrue(self._mutate(lambda c: c["types"].clear()))

    def test_a_changed_base_type_is_caught(self) -> None:
        self.assertTrue(self._mutate(
            lambda c: c["types"][0].__setitem__("baseType", "System.Attribute")))

    def test_a_changed_parameter_type_is_caught(self) -> None:
        self.assertTrue(self._mutate(
            lambda c: c["types"][0]["members"][0]["parameters"][0]
            .__setitem__("type", "System.Int64")))

    def test_a_changed_constant_value_is_caught(self) -> None:
        self.assertTrue(self._mutate(
            lambda c: c["types"][0]["members"][1].__setitem__("value", "4")))

    def test_a_changed_access_is_caught(self) -> None:
        self.assertTrue(self._mutate(
            lambda c: c["types"][0]["members"][0].__setitem__("access", "protected")))

    def test_a_changed_static_flag_is_caught(self) -> None:
        self.assertTrue(self._mutate(
            lambda c: c["types"][0]["members"][1].__setitem__("static", False)))


if __name__ == "__main__":
    unittest.main()
