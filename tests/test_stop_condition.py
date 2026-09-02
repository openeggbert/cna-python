"""The one command that says whether the six scopes are finished.

Six scopes were opened together and they finish together, so "is it done?"
should be one question rather than eleven. ``tools/verify_stop_condition.py``
reads what every gate wrote -- it re-measures only the strict profiles, which
write no summary of their own -- and fails if any counter that must be zero is
not.

A scoreboard that cannot fail is decoration, so these plant a failure in each
report it reads and require it to be reported.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "generated"

sys.path.insert(0, str(ROOT / "tools"))


def _environment() -> dict:
    import os

    return dict(os.environ,
                PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]))


class ScoreboardTests(unittest.TestCase):
    def _run(self) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, "tools/verify_stop_condition.py"],
            cwd=str(ROOT), capture_output=True, text=True, env=_environment())
        return result.returncode, result.stdout + result.stderr

    def test_the_stop_condition_holds(self) -> None:
        code, output = self._run()
        self.assertEqual(code, 0, output)
        self.assertIn("STOP_CONDITION=held", output)
        self.assertIn("FAILURES=0", output)

    def test_it_checks_every_counter_the_six_scopes_own(self) -> None:
        code, output = self._run()
        self.assertEqual(code, 0, output)
        for counter in ("SELECTED_DEVICES_ACTIONABLE_LOCAL",
                        "SELECTED_INPUT_ACTIONABLE_LOCAL",
                        "SELECTED_ONLINE_ACTIONABLE_LOCAL",
                        "CONTENT_PIPELINE_ACTIONABLE_LOCAL",
                        "PLATFORM_LEAKS", "UNJUSTIFIED_BLOCK",
                        "DEFAULT_PROFILE_TYPES",
                        "xna40-xbox360-runtime TOTAL_DIAGNOSTICS"):
            self.assertIn(counter, output)

    def test_it_measures_four_profiles_and_records_one_as_blocked(self) -> None:
        code, output = self._run()
        self.assertEqual(code, 0, output)
        self.assertIn("MEASURED_PROFILES=4", output)
        self.assertIn("BLOCKED_PROFILES=1", output)

    def _plant(self, report: str, key: str, value: object) -> tuple[int, str]:
        path = GENERATED / report
        original = path.read_text()
        document = json.loads(original)
        document["summary"][key] = value
        path.write_text(json.dumps(document, indent=1) + "\n")
        try:
            return self._run()
        finally:
            path.write_text(original)

    def test_a_family_with_outstanding_work_is_reported(self) -> None:
        code, output = self._plant(
            "cna-route-census.json", "SELECTED_ONLINE_ACTIONABLE_LOCAL", 3)
        self.assertEqual(code, 1)
        self.assertIn("SELECTED_ONLINE_ACTIONABLE_LOCAL=3", output)
        self.assertIn("STOP_CONDITION=not held", output)

    def test_an_unreviewed_pipeline_member_is_reported(self) -> None:
        code, output = self._plant(
            "content-pipeline-coverage.json", "UNREVIEWED", 1)
        self.assertEqual(code, 1)
        self.assertIn("STOP_CONDITION=not held", output)

    def test_a_default_surface_that_changed_is_reported(self) -> None:
        """The number six scopes were not allowed to move."""
        code, output = self._plant(
            "profile-separation.json", "DEFAULT_PROFILE_MEMBERS", 2424)
        self.assertEqual(code, 1)
        self.assertIn("DEFAULT_PROFILE_MEMBERS=2424, wanted 2423", output)

    def test_a_missing_report_is_reported_rather_than_skipped(self) -> None:
        path = GENERATED / "blocked-profiles.json"
        original = path.read_text()
        path.unlink()
        try:
            code, output = self._run()
        finally:
            path.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("blocked-profiles.json", output)

    def test_a_counter_that_disappeared_is_reported(self) -> None:
        """A gate that stopped reporting something is a gate that stopped."""
        path = GENERATED / "route-reachability.json"
        original = path.read_text()
        document = json.loads(original)
        document["summary"].pop("STALE_ADMISSIONS")
        path.write_text(json.dumps(document, indent=1) + "\n")
        try:
            code, output = self._run()
        finally:
            path.write_text(original)
        self.assertEqual(code, 1)
        self.assertIn("has no STALE_ADMISSIONS", output)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
