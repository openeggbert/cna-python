"""The Windows Phone profile: blocked on a file, and blocked on nothing else.

This repository derives a profile from Microsoft's own metadata and from nothing
else. That is what makes the other four exact, and it is also why this one does
not exist: the Windows Phone reference assemblies are not on this machine.

"Not on this machine" is a claim, so it is measured. The measurement is in
``docs/generated/windowsphone-assembly-search.json`` -- 1.3 million files
examined across eight roots -- and every file that matched by *name* is
identified by its own CLI metadata rather than by where it sat. What the tests
below check is that the claim is still a claim with evidence behind it, that the
machinery which would build the profile is present and parameterised, and that
the parts of Windows Phone support which do **not** depend on the assemblies are
done rather than excused.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "tools/api_compat/profiles/xna40-windowsphone-runtime.json"
SEARCH = ROOT / "docs/generated/windowsphone-assembly-search.json"

sys.path.insert(0, str(ROOT / "tools"))


class DeclarationTests(unittest.TestCase):
    """What the descriptor says, and what it may not say."""

    def setUp(self) -> None:
        super().setUp()
        self.profile = json.loads(PROFILE.read_text())

    def test_the_profile_is_declared_blocked_on_its_assemblies(self) -> None:
        self.assertEqual(self.profile["status"], "BLOCKED_REFERENCE_ASSET")
        self.assertIsNone(self.profile["contract"],
                          "a profile with a contract is not blocked")

    def test_it_names_the_assemblies_the_reason_and_the_way_out(self) -> None:
        self.assertEqual(len(self.profile["referenceAssemblies"]), 7)
        self.assertIn("MediaLibraryExtensions",
                      " ".join(self.profile["referenceAssemblies"]),
                      "the phone-only assembly is part of what is missing")
        self.assertIn("docs/generated/windowsphone-assembly-search.json",
                      self.profile["blockedReason"])
        self.assertIn("~/deps/xna40-windowsphone-assemblies",
                      self.profile["unblockedBy"])

    def test_no_contract_file_exists_for_it(self) -> None:
        self.assertFalse(
            (ROOT / "tools/api_compat/reference"
             / "xna40-windowsphone-runtime-contract.json").exists(),
            "a contract for a profile whose assemblies are absent could only "
            "have been invented")


class SearchEvidenceTests(unittest.TestCase):
    """The recorded search, read as the evidence it is."""

    def setUp(self) -> None:
        super().setUp()
        self.search = json.loads(SEARCH.read_text())

    def test_the_search_was_run_for_this_profile_and_this_assembly_set(
            self) -> None:
        self.assertEqual(self.search["profile"], "xna40-windowsphone-runtime")
        self.assertEqual(
            sorted(self.search["assembliesWanted"]),
            sorted(json.loads(PROFILE.read_text())["referenceAssemblies"]))

    def test_the_search_was_wide(self) -> None:
        searched = [entry for entry in self.search["roots"]
                    if entry["status"] == "searched"]
        self.assertGreaterEqual(len(searched), 5)
        self.assertGreater(self.search["filesExamined"], 100_000)

    def test_every_file_that_matched_by_name_is_identified(self) -> None:
        """A search that cannot say what it found is not evidence.

        XNA ships the same file names on every platform, so a name match proves
        nothing on its own. Each one here is either an assembly another profile
        already pins, or is identified from its own metadata.
        """
        summary = self.search["summary"]
        self.assertGreater(summary["NAME_MATCHES"], 0,
                           "the search really did find files by name")
        self.assertEqual(summary["UNIDENTIFIED"], 0)
        self.assertEqual(summary["CANDIDATES"], 0,
                         "nothing on this machine is a phone assembly")
        for entry in self.search["found"]:
            self.assertTrue(entry["knownAs"] or entry["platform"],
                            entry["path"])

    def test_the_desktop_assemblies_it_found_are_named_as_such(self) -> None:
        desktop = [entry for entry in self.search["found"]
                   if entry["platform"].startswith("desktop")]
        self.assertGreater(len(desktop), 0)
        for entry in desktop:
            self.assertIn("mscorlib, Version=4.0.0.0", entry["core"])


class MetadataReaderTests(unittest.TestCase):
    """The reader that identifies an assembly, checked on two known ones.

    Whether a file is a phone assembly turns on what it was compiled against,
    and this is what reads that. Checked against the two platforms this
    repository *does* have, where the answer is known independently.
    """

    def test_a_desktop_assembly_names_the_desktop_core_library(self) -> None:
        import cli_assembly

        path = Path.home() / "deps/xna40-windows-assemblies/Microsoft.Xna.Framework.dll"
        if not path.exists():
            self.skipTest("the Windows reference assemblies are not present")
        assembly = cli_assembly.read(path)
        self.assertEqual(assembly.identity.name, "Microsoft.Xna.Framework")
        self.assertEqual(assembly.identity.version, (4, 0, 0, 0))
        self.assertEqual(assembly.core_reference().name, "mscorlib")
        self.assertEqual(assembly.core_reference().version, (4, 0, 0, 0))

    def test_a_console_assembly_names_the_compact_core_library(self) -> None:
        import cli_assembly

        path = Path.home() / "deps/xna40-xbox360-assemblies/Microsoft.Xna.Framework.dll"
        if not path.exists():
            self.skipTest("the Xbox reference assemblies are not present")
        assembly = cli_assembly.read(path)
        core = assembly.core_reference()
        self.assertEqual(core.name, "mscorlib")
        self.assertEqual(core.version, (2, 0, 5, 0),
                         "the Compact Framework, which is what separates a "
                         "console or phone assembly from a desktop one")

    def test_the_core_library_is_found_by_name_and_not_by_position(self) -> None:
        """The reference list is not ordered, and taking the first is wrong.

        This Xbox assembly lists ``System`` before ``mscorlib``, so a reader
        that answered with the first reference would answer with a different
        assembly -- one that happens to carry the same version here, and would
        not on a file where it mattered.
        """
        import cli_assembly

        path = Path.home() / "deps/xna40-xbox360-assemblies/Microsoft.Xna.Framework.dll"
        if not path.exists():
            self.skipTest("the Xbox reference assemblies are not present")
        assembly = cli_assembly.read(path)
        self.assertGreater(len(assembly.references), 1)
        self.assertNotEqual(assembly.references[0].name, "mscorlib",
                            "this file is the one that makes the point")
        self.assertEqual(assembly.core_reference().name, "mscorlib")

    def test_a_desktop_assemblys_core_library_is_also_found_by_name(self) -> None:
        import cli_assembly

        path = (Path.home()
                / "deps/xna40-windows-assemblies/Microsoft.Xna.Framework.Game.dll")
        if not path.exists():
            self.skipTest("the Windows reference assemblies are not present")
        assembly = cli_assembly.read(path)
        self.assertGreater(len(assembly.references), 4,
                           "a Game assembly references most of the framework")
        core = assembly.core_reference()
        self.assertEqual(core.name, "mscorlib")
        self.assertEqual(core.version, (4, 0, 0, 0))

    def test_a_file_that_is_not_managed_says_so(self) -> None:
        import cli_assembly

        with self.assertRaises(cli_assembly.NotManaged):
            cli_assembly.read(ROOT / "README.md")


class GateTests(unittest.TestCase):
    """The blocked-profile gate, run for real and with the block undermined."""

    def _run(self) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "tools/verify_blocked_profiles.py"],
            cwd=str(ROOT), capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr

    def test_the_block_this_repository_declares_is_justified(self) -> None:
        code, output = self._run()
        self.assertEqual(code, 0, output)
        for line in ("BLOCKED_PROFILES=1", "UNJUSTIFIED_BLOCK=0",
                     "BLOCK_WITHOUT_REASON=0", "STALE_BLOCK=0",
                     "SEARCH_MISSING=0"):
            self.assertIn(line, output)

    def test_a_block_on_a_profile_that_has_a_contract_is_rejected(self) -> None:
        original = PROFILE.read_text()
        profile = json.loads(original)
        profile["contract"] = "xna40-windows-runtime-contract.json"
        PROFILE.write_text(json.dumps(profile, indent=2) + "\n")
        try:
            code, output = self._run()
        finally:
            PROFILE.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("UNJUSTIFIED_BLOCK=1", output)

    def test_a_block_with_no_written_reason_is_rejected(self) -> None:
        original = PROFILE.read_text()
        profile = json.loads(original)
        profile["blockedReason"] = "not here"
        PROFILE.write_text(json.dumps(profile, indent=2) + "\n")
        try:
            code, output = self._run()
        finally:
            PROFILE.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("BLOCK_WITHOUT_REASON=1", output)

    def test_a_search_that_found_a_candidate_unblocks_the_profile(self) -> None:
        """The day the assemblies arrive, the descriptor is what is wrong."""
        original = SEARCH.read_text()
        search = json.loads(original)
        search["summary"]["CANDIDATES"] = 1
        SEARCH.write_text(json.dumps(search, indent=1) + "\n")
        try:
            code, output = self._run()
        finally:
            SEARCH.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("STALE_BLOCK=1", output)

    def test_a_search_run_for_a_different_profile_is_not_evidence(self) -> None:
        original = SEARCH.read_text()
        search = json.loads(original)
        search["profile"] = "xna40-xbox360-runtime"
        SEARCH.write_text(json.dumps(search, indent=1) + "\n")
        try:
            code, output = self._run()
        finally:
            SEARCH.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("SEARCH_MISSING=1", output)


class UnblockedWorkTests(unittest.TestCase):
    """What Windows Phone support does *not* need the assemblies for.

    The brief is explicit that a blocked profile does not excuse the work that
    is locally authoritative. These are the pieces, and they are done.
    """

    def test_the_generator_is_parameterised_rather_than_named_after_xbox(
            self) -> None:
        """The machinery is one command away from a phone root."""
        import generate_platform_profile as generator

        self.assertIn("--profile", (ROOT / "tools/generate_platform_profile.py")
                      .read_text())
        self.assertIn("xna40-xbox360-runtime", generator.PLATFORM_ROOTS)
        self.assertNotIn("xna40-windowsphone-runtime", generator.PLATFORM_ROOTS,
                         "a platform with no contract has nothing to generate "
                         "from, and saying otherwise would be the lie")

    def test_the_content_pipeline_builds_for_the_phone(self) -> None:
        """``TargetPlatform.WindowsPhone`` is a real target, not a name.

        It writes its own platform byte, which is what a phone runtime checks
        and what this repository's Windows reader refuses.
        """
        import io

        from Microsoft.Xna.Framework.Content.Pipeline import TargetPlatform
        from Microsoft.Xna.Framework.Content.Pipeline.Serialization.Compiler \
            import ContentCompiler
        from Microsoft.Xna.Framework.Graphics import GraphicsProfile

        stream = io.BytesIO()
        ContentCompiler()._compile(stream, "phone", TargetPlatform.WindowsPhone,
                                   GraphicsProfile.Reach, False, "", "")
        raw = stream.getvalue()
        self.assertEqual(chr(raw[3]), "m", "the Windows Phone platform byte")
        self.assertEqual(raw[4], 5)

    def test_the_reach_profile_limits_are_enforced(self) -> None:
        """Windows Phone is Reach, and Reach's limits are already measured."""
        from Microsoft.Xna.Framework import Color
        from Microsoft.Xna.Framework.Content.Pipeline import InvalidContentException
        from Microsoft.Xna.Framework.Content.Pipeline.Graphics import (
            PixelBitmapContentOfT, Texture2DContent,
        )
        from Microsoft.Xna.Framework.Graphics import GraphicsProfile

        content = Texture2DContent()
        content.Mipmaps = PixelBitmapContentOfT(4096, 16, element=Color)
        with self.assertRaises(InvalidContentException):
            content.Validate(GraphicsProfile.Reach)

    def test_touch_and_the_accelerometer_are_already_projected(self) -> None:
        """The two things a phone adds that this repository already has.

        ``Microsoft.Xna.Framework.Input.Touch`` is in the Windows runtime
        profile because XNA puts it there, and the accelerometer is CNA's, in
        ``cna.extensions.devices``. Neither waits on a reference assembly.
        """
        import Microsoft.Xna.Framework.Input.Touch as touch
        import cna.extensions.devices as devices

        self.assertIn("TouchPanel", touch.__all__)
        self.assertIn("Accelerometer", devices.__all__)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
