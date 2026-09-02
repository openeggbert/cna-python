"""Falsifiability for the Content Pipeline coverage gate.

``tools/verify_content_pipeline.py`` answers a question the strict verifier does
not: whether every member of an exact surface actually *does* something. A gate
like that is only worth having if it fails, so this plants both shapes of the
defect it exists to catch and requires it to report each.

Nothing here needs a CNA library or a content project: the gate reads source and
compares it to a decisions file, and both are data.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_content_pipeline as gate  # noqa: E402


class _Refusing:
    def Blocked(self) -> None:
        raise NotImplementedError("nothing here yet")

    def Working(self) -> int:
        return 1

    @property
    def RefusingProperty(self) -> int:
        raise NotImplementedError("nothing here yet")

    @staticmethod
    def RefusingStatic() -> None:
        raise NotImplementedError("nothing here yet")


class RefusalDetectionTests(unittest.TestCase):
    """What the gate reads to decide whether a member does anything."""

    def test_a_member_that_can_refuse_is_seen(self) -> None:
        self.assertTrue(gate.refuses(_Refusing.__dict__["Blocked"]))

    def test_a_member_that_cannot_refuse_is_not(self) -> None:
        self.assertFalse(gate.refuses(_Refusing.__dict__["Working"]))

    def test_a_refusing_property_is_seen_through_its_getter(self) -> None:
        self.assertTrue(gate.refuses(_Refusing.__dict__["RefusingProperty"]))

    def test_a_refusing_static_method_is_seen_through_its_function(self) -> None:
        self.assertTrue(gate.refuses(_Refusing.__dict__["RefusingStatic"]))


class GateFalsifiabilityTests(unittest.TestCase):
    """The gate, run for real, with the decisions file deliberately wrong."""

    def _run(self, decisions: list[dict]) -> tuple[int, str]:
        original = gate.DECISIONS_PATH.read_text(encoding="utf-8")
        gate.DECISIONS_PATH.write_text(
            json.dumps({"schemaVersion": 1, "decisions": decisions}, indent=1),
            encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "tools/verify_content_pipeline.py"],
                cwd=str(ROOT), capture_output=True, text=True,
                env=_environment())
        finally:
            gate.DECISIONS_PATH.write_text(original, encoding="utf-8")
        return result.returncode, result.stdout + result.stderr

    def _shipped(self) -> list[dict]:
        return json.loads(gate.DECISIONS_PATH.read_text(
            encoding="utf-8"))["decisions"]

    def test_the_decisions_this_repository_ships_pass(self) -> None:
        code, output = self._run(self._shipped())
        self.assertEqual(code, 0, output)
        self.assertIn("CONTENT_PIPELINE_ACTIONABLE_LOCAL=0", output)
        self.assertIn("UNREVIEWED=0", output)

    def test_a_refusing_member_with_no_decision_is_unreviewed(self) -> None:
        """The defect the gate exists for: a member nobody looked at."""
        decisions = [entry for entry in self._shipped()
                     if not entry["member"].endswith("FbxImporter.Import")]
        code, output = self._run(decisions)
        self.assertEqual(code, 1)
        self.assertIn("UNREVIEWED=1", output)
        self.assertIn("FbxImporter.Import", output)

    def test_a_decision_whose_member_no_longer_refuses_is_stale(self) -> None:
        """The other half: a blocker that was fixed and left written down."""
        decisions = self._shipped() + [{
            "member": ("Microsoft.Xna.Framework.Content.Pipeline."
                       "ContentIdentity.SourceFilename"),
            "status": "BLOCKED_UPSTREAM",
            "reason": "planted: this member does not refuse",
        }]
        code, output = self._run(decisions)
        self.assertEqual(code, 1)
        self.assertIn("STALE_DECISIONS=1", output)
        self.assertIn("ContentIdentity.SourceFilename", output)

    def test_a_decision_for_a_member_that_is_not_projected_is_reported(
            self) -> None:
        decisions = self._shipped() + [{
            "member": "Microsoft.Xna.Framework.Content.Pipeline.Ghost.Vanished",
            "status": "BLOCKED_UPSTREAM",
            "reason": "planted: no such member",
        }]
        code, output = self._run(decisions)
        self.assertEqual(code, 1)
        self.assertIn("DECISIONS_FOR_ABSENT_MEMBERS=1", output)

    def test_an_actionable_local_decision_fails_the_gate(self) -> None:
        """The status that means "we could do this and have not"."""
        decisions = [
            dict(entry, status="ACTIONABLE_LOCAL")
            if entry["member"].endswith("FbxImporter.Import") else entry
            for entry in self._shipped()]
        code, output = self._run(decisions)
        self.assertEqual(code, 1)
        self.assertIn("CONTENT_PIPELINE_ACTIONABLE_LOCAL=1", output)


class DecisionContentTests(unittest.TestCase):
    """Every decision says something, and says one of the things it may say."""

    def setUp(self) -> None:
        super().setUp()
        self.decisions = json.loads(
            gate.DECISIONS_PATH.read_text(encoding="utf-8"))["decisions"]

    def test_every_decision_has_a_known_status(self) -> None:
        for entry in self.decisions:
            self.assertIn(entry["status"], gate.STATUSES, entry["member"])

    def test_every_decision_carries_a_written_reason(self) -> None:
        for entry in self.decisions:
            self.assertGreater(len(entry["reason"].strip()), 40,
                               f"{entry['member']} needs a real reason")

    def test_every_blocker_names_what_would_unblock_it(self) -> None:
        for entry in self.decisions:
            if not entry["status"].startswith("BLOCKED"):
                continue
            self.assertIn("Unblocked by", entry["reason"], entry["member"])

    def test_no_member_is_decided_twice(self) -> None:
        names = [entry["member"] for entry in self.decisions]
        self.assertEqual(len(names), len(set(names)))


def _environment() -> dict:
    import os

    return dict(os.environ,
                PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
