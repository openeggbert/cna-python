"""The Xbox 360 surface profile, and the gate that keeps the profiles apart.

A **surface** profile: importing from ``cna.profiles.xbox360`` gives exactly the
types and members an Xbox 360 build of XNA has. It is not an Xbox runtime --
there is no console here and CNA does not target one -- so nothing in this file
claims a platform result. Every result here is
``XBOX_SURFACE_VERIFIED_ON_WINDOWS``, and never ``XBOX_HARDWARE_VERIFIED``.

What is measured is the shape: the profile's contents against the Xbox reference
metadata, the generator against the contract it reads, and the separation
between the profiles against both.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "api_compat"))

CONTRACTS = ROOT / "tools" / "api_compat" / "reference"

#: The namespaces the Xbox root holds, and the ones it deliberately does not.
XBOX_NAMESPACES = (
    "Microsoft.Xna.Framework", "Microsoft.Xna.Framework.Audio",
    "Microsoft.Xna.Framework.Content", "Microsoft.Xna.Framework.GamerServices",
    "Microsoft.Xna.Framework.Graphics",
    "Microsoft.Xna.Framework.Graphics.PackedVector",
    "Microsoft.Xna.Framework.Input", "Microsoft.Xna.Framework.Input.Touch",
    "Microsoft.Xna.Framework.Media", "Microsoft.Xna.Framework.Net",
    "Microsoft.Xna.Framework.Storage",
)
WINDOWS_ONLY_NAMESPACES = ("Microsoft.Xna.Framework.Design",
                           "Microsoft.Xna.Framework.Content.Pipeline")


def _contract(name: str) -> dict:
    return json.loads((CONTRACTS / f"{name}-contract.json").read_text())


class SurfaceTests(unittest.TestCase):
    """The profile's contents, against the metadata Microsoft shipped."""

    def setUp(self) -> None:
        super().setUp()
        self.xbox = _contract("xna40-xbox360-runtime")
        self.rules = json.loads(
            (ROOT / "tools/api_compat/mapping-rules.json").read_text())

    def _projected(self, identity: str) -> str:
        return self.rules["typeNames"].get(
            identity, identity.rsplit(".", 1)[-1].split("`", 1)[0])

    def test_every_namespace_holds_exactly_the_contracts_types(self) -> None:
        wanted: dict[str, set[str]] = {}
        for entry in self.xbox["types"]:
            name = self._projected(entry["name"])
            if "." in name:
                continue  # a nested type, reached through its owner
            wanted.setdefault(entry["name"].rsplit(".", 1)[0], set()).add(name)
        self.assertEqual(set(wanted), set(XBOX_NAMESPACES))
        for namespace, names in wanted.items():
            with self.subTest(namespace=namespace):
                module = importlib.import_module(
                    f"cna.profiles.xbox360.{namespace}")
                self.assertEqual(set(module.__all__), names)

    def test_a_namespace_xbox_does_not_have_is_not_importable(self) -> None:
        """Which is the point: a Windows-only name is an ImportError here.

        ``Design`` is thirteen type converters that need
        ``System.ComponentModel``, and the Content Pipeline is design-time. An
        Xbox build of XNA has neither.
        """
        for namespace in WINDOWS_ONLY_NAMESPACES:
            with self.subTest(namespace=namespace):
                with self.assertRaises(ImportError):
                    importlib.import_module(f"cna.profiles.xbox360.{namespace}")

    def test_a_type_is_the_windows_implementation_of_itself(self) -> None:
        """Re-export, not reimplementation: the same class, the same behaviour.

        The profile is about the *surface*. A ``Texture2D`` imported from here
        is the one this repository ships, which is what makes code written
        against the profile runnable on the machine it was written on.
        """
        from Microsoft.Xna.Framework import Vector3 as WindowsVector3
        from Microsoft.Xna.Framework.Graphics import Texture2D as WindowsTexture2D
        from cna.profiles.xbox360.Microsoft.Xna.Framework import Vector3
        from cna.profiles.xbox360.Microsoft.Xna.Framework.Graphics import Texture2D

        self.assertIs(Vector3, WindowsVector3)
        self.assertIs(Texture2D, WindowsTexture2D)

    def test_a_member_xbox_does_not_declare_is_not_there(self) -> None:
        """``hasattr`` answers False, which is what absent means.

        A descriptor that raised only when *called* would let ``hasattr``,
        ``getattr`` with a default and every "ask before calling" idiom lie.
        """
        from cna.profiles.xbox360.Microsoft.Xna.Framework.Net import (
            NetworkSessionJoinException,
        )

        error = NetworkSessionJoinException("no session")
        self.assertFalse(hasattr(error, "GetObjectData"))
        self.assertIsNone(getattr(error, "GetObjectData", None))
        with self.assertRaises(AttributeError) as raised:
            error.GetObjectData
        self.assertIn("Compact Framework", str(raised.exception))

    def test_the_windows_type_still_has_the_member(self) -> None:
        """The removal is the platform's, not this repository's."""
        from Microsoft.Xna.Framework.Net import NetworkSessionJoinException

        self.assertTrue(hasattr(NetworkSessionJoinException("x"), "GetObjectData"))

    def test_a_narrowed_type_is_still_caught_by_the_windows_except_clause(
            self) -> None:
        """Narrowing must not break code that catches the base."""
        from Microsoft.Xna.Framework.GamerServices import NetworkException
        from Microsoft.Xna.Framework.Net import (
            NetworkSessionJoinException as WindowsJoinException,
        )
        from cna.profiles.xbox360.Microsoft.Xna.Framework.Net import (
            NetworkSessionJoinException,
        )

        self.assertTrue(issubclass(NetworkSessionJoinException,
                                   WindowsJoinException))
        self.assertTrue(issubclass(NetworkSessionJoinException, NetworkException))
        try:
            raise NetworkSessionJoinException("no session")
        except NetworkException:
            pass
        else:  # pragma: no cover - the raise above always throws
            self.fail("an Xbox exception must still be a NetworkException")

    def test_the_xbox_surface_is_measured_as_a_subset_of_windows(self) -> None:
        """The measurement the whole profile rests on, asserted rather than assumed."""
        xbox = {entry["name"] for entry in self.xbox["types"]}
        windows = set()
        for name in ("xna40-windows-runtime", "xna40-windows-online"):
            windows.update(entry["name"] for entry in _contract(name)["types"])
        self.assertEqual(xbox - windows, set(),
                         "there is nothing on Xbox that Windows does not have")
        self.assertEqual(len(windows - xbox), 13,
                         "and thirteen Design converters that Windows has alone")


class StrictVerificationTests(unittest.TestCase):
    """The profile's central claim, run rather than described.

    Every profile is verified in the gate battery, but this repository's tests
    have to be able to say so on their own -- a claim only a shell script checks
    is a claim a change can quietly break.
    """

    def _verify(self, profile: str) -> dict:
        from verify import Profile, verify

        return verify(Profile.load(profile))["summary"]

    def test_the_xbox_profile_matches_its_reference_metadata_exactly(self) -> None:
        summary = self._verify("xna40-xbox360-runtime")
        self.assertEqual(summary["TARGET_TYPES"], 318)
        self.assertEqual(summary["TARGET_MEMBERS"], 2986)
        self.assertEqual(summary["TOTAL_DIAGNOSTICS"], 0,
                         "the Xbox surface is exactly the Xbox contract")

    def test_the_default_windows_profile_is_untouched(self) -> None:
        """The number this whole session may not change."""
        summary = self._verify("xna40-windows-runtime")
        self.assertEqual(summary["TARGET_TYPES"], 257)
        self.assertEqual(summary["TARGET_MEMBERS"], 2423)
        self.assertEqual(summary["TOTAL_DIAGNOSTICS"], 0)


class GeneratorTests(unittest.TestCase):
    """The profile is generated, and regenerating it changes nothing."""

    def test_regenerating_the_profile_is_a_no_op(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/generate_platform_profile.py", "--check"],
            cwd=str(ROOT), capture_output=True, text=True, env=_environment())
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)
        self.assertIn("DIFFERENCES=0", result.stdout)

    def test_the_generator_reports_what_it_produced(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/generate_platform_profile.py", "--check"],
            cwd=str(ROOT), capture_output=True, text=True, env=_environment())
        self.assertIn("EXPORTED_TYPES=316", result.stdout,
                      "318 contract types less the two nested ones")
        self.assertIn("GENERATED_TYPES=9", result.stdout,
                      "nine exception types differ from their Windows form")


class SeparationGateTests(unittest.TestCase):
    """The cross-profile gate, run for real and with defects planted."""

    def _run(self) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "tools/verify_profile_separation.py"],
            cwd=str(ROOT), capture_output=True, text=True, env=_environment())
        return result.returncode, result.stdout + result.stderr

    def test_the_profiles_this_repository_ships_are_separate(self) -> None:
        code, output = self._run()
        self.assertEqual(code, 0, output)
        for line in ("PLATFORM_LEAKS=0",
                     "WINDOWS_ONLY_REACHABLE_FROM_PLATFORM=0",
                     "UNJUSTIFIED_REMOVALS=0", "DEFAULT_PROFILE_DRIFT=0",
                     "DEFAULT_PROFILE_TYPES=257",
                     "DEFAULT_PROFILE_MEMBERS=2423"):
            self.assertIn(line, output)

    def test_a_windows_only_name_reachable_from_the_platform_is_reported(
            self) -> None:
        """Planted by exporting a Design converter from the Xbox root."""
        path = (ROOT / "src/cna/profiles/xbox360/Microsoft/Xna/Framework"
                / "__init__.py")
        original = path.read_text(encoding="utf-8")
        planted = original.replace(
            'from Microsoft.Xna.Framework import (',
            'from Microsoft.Xna.Framework.Design import ColorConverter\n'
            'from Microsoft.Xna.Framework import (')
        planted = planted.replace('__all__ = [', '__all__ = [\n    "ColorConverter",')
        path.write_text(planted, encoding="utf-8")
        try:
            code, output = self._run()
        finally:
            path.write_text(original, encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("WINDOWS_ONLY_REACHABLE_FROM_PLATFORM=1", output)
        self.assertIn("ColorConverter", output)

    def test_a_removal_the_platform_contract_does_not_justify_is_reported(
            self) -> None:
        """A removal is how a member is hidden from the strict verifier.

        So a removal that the platform's own contract contradicts has to be
        reported, or the removal mechanism becomes a way to make any member
        disappear.
        """
        path = (ROOT / "src/cna/profiles/xbox360/Microsoft/Xna/Framework"
                / "Storage/__init__.py")
        original = path.read_text(encoding="utf-8")
        planted = original.replace(
            "from Microsoft.Xna.Framework.Storage import (\n    StorageContainer,",
            "from cna.profiles import _RemovedOnPlatform\n"
            "from Microsoft.Xna.Framework.Storage import (\n"
            "    StorageContainer as _WindowsStorageContainer,")
        planted = planted.replace(
            "__all__ = [",
            "class StorageContainer(_WindowsStorageContainer):\n"
            "    FileExists = _RemovedOnPlatform('StorageContainer.FileExists',\n"
            "                                    'planted')\n"
            "\n"
            "\n__all__ = [")
        path.write_text(planted, encoding="utf-8")
        try:
            code, output = self._run()
        finally:
            path.write_text(original, encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("UNJUSTIFIED_REMOVALS=1", output)
        self.assertIn("the platform contract still has it", output)

    def test_the_default_profiles_counts_are_really_compared(self) -> None:
        """The numbers this whole session may not change.

        Asked for a *different* expected count, the gate has to object -- which
        is the only way to know the comparison runs rather than sitting there.
        """
        source = (
            "import sys\n"
            "sys.path.insert(0, 'tools')\n"
            "sys.path.insert(0, 'tools/api_compat')\n"
            "import verify_profile_separation as gate\n"
            "gate.DEFAULT_TYPES = 999\n"
            "sys.argv = ['gate']\n"
            "raise SystemExit(gate.main())\n"
        )
        result = subprocess.run([sys.executable, "-c", source], cwd=str(ROOT),
                                capture_output=True, text=True,
                                env=_environment())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DEFAULT_PROFILE_DRIFT=1", result.stdout)
        self.assertIn("types 257 != 999", result.stdout)

    def test_a_platform_type_the_default_surface_gained_is_reported(self) -> None:
        """The direction that would matter most, and cannot happen today.

        There is no Xbox-only type, so the leak check has nothing to find -- and
        a check with nothing to find is a check nobody has seen work. Asked
        about a *hypothetical* platform-only type by name, the comparison the
        gate performs answers correctly, which is what makes its zero mean
        something the day CNA or XNA gains one.
        """
        windows = set()
        for name in ("xna40-windows-runtime", "xna40-windows-online"):
            windows.update(entry["name"] for entry in _contract(name)["types"])
        xbox = {entry["name"] for entry in _contract("xna40-xbox360-runtime")["types"]}
        invented = "Microsoft.Xna.Framework.Graphics.XboxOnlyThing"
        self.assertNotIn(invented, windows)
        self.assertNotIn(invented, xbox)
        # The gate's rule, applied to the invented name: a platform type that
        # is not in the Windows contracts and *is* reachable from the default
        # surface would be a leak.
        self.assertTrue(invented not in windows,
                        "the rule's first half: platform-only")
        from verify import Profile, target_types

        default_targets, _ = target_types(Profile.load("xna40-windows-runtime"))
        self.assertNotIn(invented, default_targets,
                         "the rule's second half: reachable from the default")


def _environment() -> dict:
    import os

    return dict(os.environ,
                PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
