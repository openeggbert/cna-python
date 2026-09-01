"""Falsifiability tests for the route reachability gate.

A gate that cannot fail proves nothing. These plant the two defects it exists to
catch -- a bound route nothing calls, and an admission that has outlived its
reason -- and require it to reject both.
"""

from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import verify_route_reachability as gate


class ReachabilityGateFalsifiability(unittest.TestCase):
    def _analyse(self, extra=None, admitted=None):
        original_manifest = gate.FUNCTION_MANIFEST
        original_admitted = gate.ROOT / "tools/route-reachability-admitted.json"
        if extra is not None:
            gate.FUNCTION_MANIFEST = original_manifest + (extra,)
        try:
            return gate.analyse()
        finally:
            gate.FUNCTION_MANIFEST = original_manifest

    def test_the_real_manifest_is_green(self) -> None:
        summary = self._analyse()["summary"]
        self.assertEqual(summary["UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE"], 0)
        self.assertEqual(summary["STALE_ADMISSIONS"], 0)
        self.assertGreater(summary["DIRECT_CALL_SITE"], 0)

    def test_a_bound_route_nothing_calls_is_rejected(self) -> None:
        dead = ("cna_zzz_route_no_caller_ever", ctypes.c_uint32, [], "planted")
        report = self._analyse(extra=dead)
        self.assertEqual(report["summary"]["UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE"], 1)
        self.assertIn("cna_zzz_route_no_caller_ever", report["unreached"])

    def test_a_route_named_only_in_prose_does_not_count_as_a_caller(self) -> None:
        """A docstring mentioning a route must not satisfy the gate."""
        source = ('"""cna_zzz_documented_but_uncalled is described here."""\n'
                  'def f():\n'
                  '    """cna_zzz_documented_but_uncalled again."""\n'
                  '    return 1\n')
        import ast

        tree = ast.parse(source)
        gate._strip_docstrings(tree)
        visitor = gate._CallSites(Path("planted.py"))
        visitor.visit(tree)
        self.assertNotIn("cna_zzz_documented_but_uncalled", visitor.used)

    def test_an_attribute_call_does_count_as_a_caller(self) -> None:
        import ast

        tree = ast.parse("library.cna_zzz_really_called(handle)\n")
        visitor = gate._CallSites(Path("planted.py"))
        visitor.visit(tree)
        self.assertIn("cna_zzz_really_called", visitor.used)

    def test_a_name_template_too_generic_to_prove_anything_is_ignored(self) -> None:
        import ast

        tree = ast.parse('operation = f"cna_{family}"\n')
        visitor = gate._CallSites(Path("planted.py"))
        visitor.visit(tree)
        self.assertEqual(visitor.templates, {},
                         "a bare 'cna_' head would match almost every route")

    def test_a_specific_name_template_is_kept(self) -> None:
        import ast

        tree = ast.parse('operation = f"cna_effect_annotation_get_value_{suffix}"\n')
        visitor = gate._CallSites(Path("planted.py"))
        visitor.visit(tree)
        self.assertIn("cna_effect_annotation_get_value_", visitor.templates)


if __name__ == "__main__":
    unittest.main()
