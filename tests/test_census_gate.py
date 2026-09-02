"""Falsifiability tests for the route census's rule-shadowing gate.

The census classifies by first match, so a rule's *position* is part of its
meaning and a rule can be silently overruled by an earlier one. That happened:
``engine-c-lifetime-transfer`` names three C ownership transfers as deliberate
non-bindings, and one of them sat one position behind a prefix rule that claimed
it, so the census reported a decision already made as an outstanding task. Every
other check the census runs asks about routes rather than about rules, so nothing
noticed.

These plant both shapes of the defect and require the gate to reject each. They
need no native library: the census classifies declarations against rules, and
both are data.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import route_census as census


class _Declaration:
    """The one field the classifier reads, so the cases need no headers."""

    def __init__(self, header: str) -> None:
        self.header = header


DECLARATIONS = {
    "cna_thing_create": _Declaration("engine_layer.h"),
    "cna_thing_create_owning": _Declaration("engine_layer.h"),
    "cna_thing_destroy": _Declaration("engine_layer.h"),
    "cna_other_ext": _Declaration("graphics_ext.h"),
}

PREFIX_RULE = {
    "id": "things",
    "match": {"prefixes": ["cna_thing_"]},
    "purpose": "CNA_EXTENSION_CANDIDATE",
    "status": "ACTIONABLE_LOCAL",
    "reason": "a family default",
}

NAMED_RULE = {
    "id": "ownership-transfer",
    "match": {"names": ["cna_thing_create_owning"]},
    "purpose": "MANAGED_BY_DESIGN",
    "status": "DELIBERATE_NON_BINDING",
    "reason": "C ownership transfer Python does not need",
}

CATCH_ALL = {
    "id": "everything-else",
    "match": {"suffixes": ["_ext"]},
    "purpose": "CNA_EXTENSION_CANDIDATE",
    "status": "DELIBERATE_NON_BINDING",
    "reason": "a broad catch-all",
}


class RuleShadowingFalsifiability(unittest.TestCase):
    def test_a_named_rule_ahead_of_the_prefix_rule_is_clean(self) -> None:
        diagnostics = census.shadowed_rules(
            DECLARATIONS, [NAMED_RULE, PREFIX_RULE, CATCH_ALL])
        self.assertEqual(diagnostics, [])
        rows = census.classify(DECLARATIONS, set(), [NAMED_RULE, PREFIX_RULE, CATCH_ALL])
        owning = next(row for row in rows if row["route"] == "cna_thing_create_owning")
        self.assertEqual(owning["status"], "DELIBERATE_NON_BINDING")

    def test_a_named_rule_behind_the_prefix_rule_is_rejected(self) -> None:
        """The exact defect this gate was written for."""
        diagnostics = census.shadowed_rules(
            DECLARATIONS, [PREFIX_RULE, NAMED_RULE, CATCH_ALL])
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["kind"], "NAMED_ROUTE_TAKEN")
        self.assertEqual(diagnostics[0]["rule"], "ownership-transfer")
        self.assertEqual(diagnostics[0]["routes"], ["cna_thing_create_owning"])
        self.assertEqual(diagnostics[0]["shadowedBy"], ["things"])

    def test_a_rule_that_classifies_nothing_is_rejected(self) -> None:
        """A catch-all every other rule has emptied is dead, not harmless.

        Left in place it turns every route CNA adds later into a reviewed
        decision nobody made, which is what UNREVIEWED exists to prevent.
        """
        broad = dict(CATCH_ALL, match={"prefixes": ["cna_thing_"]})
        diagnostics = census.shadowed_rules(DECLARATIONS, [PREFIX_RULE, broad])
        self.assertEqual([entry["kind"] for entry in diagnostics], ["SHADOWED"])
        self.assertEqual(diagnostics[0]["rule"], "everything-else")
        self.assertEqual(len(diagnostics[0]["routes"]), 3)

    def test_a_rule_that_matches_no_route_at_all_is_rejected(self) -> None:
        absent = {"id": "gone", "match": {"prefixes": ["cna_removed_"]},
                  "purpose": "CNA_EXTENSION_CANDIDATE", "status": "ACTIONABLE_LOCAL",
                  "reason": "a family CNA no longer has"}
        diagnostics = census.shadowed_rules(DECLARATIONS, [PREFIX_RULE, absent])
        self.assertEqual([entry["kind"] for entry in diagnostics], ["DEAD"])
        self.assertEqual(diagnostics[0]["routes"], [])

    def test_a_named_route_that_no_longer_exists_is_not_a_diagnostic(self) -> None:
        """A rule may name a route CNA has yet to add, or has removed.

        Only a route that *exists* and went elsewhere is a shadowing defect;
        naming one that is not in the headers is caught by the rule classifying
        nothing, if that is what it ends up doing.
        """
        forward = dict(NAMED_RULE,
                       match={"names": ["cna_thing_create_owning", "cna_not_yet"]})
        self.assertEqual(census.shadowed_rules(DECLARATIONS, [forward, PREFIX_RULE]), [])


class ShippedRulesTests(unittest.TestCase):
    """The rules this repository actually ships, against the same gate."""

    def test_no_shipped_rule_is_shadowed_or_dead(self) -> None:
        import json

        document = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))
        declarations = self._declarations()
        diagnostics = census.shadowed_rules(declarations, document["rules"])
        self.assertEqual(diagnostics, [], "\n".join(
            f"{entry['kind']} {entry['rule']}" for entry in diagnostics))

    def test_the_three_ownership_transfers_are_all_deliberate_non_bindings(self) -> None:
        """The routes the shadowed rule names, checked as the census classifies them."""
        import json

        document = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))
        declarations = self._declarations()
        rows = {row["route"]: row
                for row in census.classify(declarations, set(), document["rules"])}
        for route in ("cna_post_process_effect_pass_create_owning",
                      "cna_post_process_chain_add_owned_pass",
                      "cna_skybox_set_owned_environment"):
            self.assertIn(route, rows, route)
            self.assertEqual(rows[route]["rule"], "engine-c-lifetime-transfer", route)
            self.assertEqual(rows[route]["purpose"], "MANAGED_BY_DESIGN", route)

    @staticmethod
    def _declarations():
        """The canonical routes, from the census report this repository ships.

        Read from the generated report rather than by parsing CNA's headers, so
        the case runs without a CNA checkout and still uses the real route names.
        """
        import json

        report = json.loads(
            (census.ROOT / "docs/generated/cna-route-census.json").read_text(
                encoding="utf-8"))
        return {row["route"]: _Declaration(row["header"]) for row in report["routes"]}


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class NewRouteFalsifiability(unittest.TestCase):
    """A route CNA adds tomorrow must arrive as a decision nobody has made yet.

    ``UNREVIEWED`` is the one status the census may not ship, and it only means
    anything if a route that nothing has considered actually lands there. These
    check that with routes CNA does not have.
    """

    def _classify(self, name: str, header: str) -> dict:
        import json

        rules = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))["rules"]
        return census.classify({name: _Declaration(header)}, set(), rules)[0]

    def test_a_new_engine_route_is_unreviewed(self) -> None:
        row = self._classify("cna_brand_new_engine_thing_create", "engine_layer.h")
        self.assertEqual(row["status"], "UNREVIEWED")
        self.assertIsNone(row["rule"])

    def test_a_new_route_in_a_header_nothing_claims_is_unreviewed(self) -> None:
        row = self._classify("cna_brand_new_core_thing", "cna.h")
        self.assertEqual(row["status"], "UNREVIEWED")

    def test_a_new_route_in_a_header_with_a_whole_header_decision_inherits_it(self) -> None:
        """The deliberate exception, named so it is a decision and not an oversight.

        ``graphics_ext.h`` is outside the selected XNA 4.0 profile as a *header*,
        with that written down, so a route added to it inherits the same
        decision correctly. That is different in kind from a catch-all matching a
        name *suffix* across twenty families, which is why one is kept and the
        other was removed.
        """
        row = self._classify("cna_brand_new_thing_ext", "graphics_ext.h")
        self.assertEqual(row["status"], "DELIBERATE_NON_BINDING")
        self.assertEqual(row["rule"], "modern-graphics-extensions")

    #: The suffix-only rules this repository has deliberately accepted, and why
    #: each is a decision that really does cover everything it reaches.
    ALLOWED_SUFFIX_RULES = {
        "clr-type-name":
            "two whole route-name tails naming one CLR concept, and an exclusive "
            "claim the contradiction check polices",
        "native-disposed-flag":
            "one whole route-name tail naming one operation every CNA object has, "
            "so a single decision about disposal really does cover all of them",
        "value-struct-initialisers":
            "three whole route-name tails naming one operation -- filling a "
            "caller-owned value structure -- with an exclusive claim, and every "
            "engine family that does import an initialiser claims it first",
    }

    def test_no_new_suffix_only_rule_appears_unnoticed(self) -> None:
        """The shape that quietly reviewed routes nobody had looked at.

        A suffix that is a *marker* rather than a whole operation says nothing
        about which family a route belongs to, so a rule keyed on one classifies
        whatever it happens to reach. Exactly that shipped -- a ``*_ext``
        catch-all spanning twenty families -- and was found only when the
        shadowing gate reported that it had been emptied by more specific rules.

        A suffix rule scoped by a header, prefix or name can only reach what it
        was aimed at, so it needs no argument. An unscoped one needs an argument,
        and that argument lives here: adding one means editing this list, which
        is the point.
        """
        import json

        rules = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))["rules"]
        unscoped = {rule.get("id") for rule in rules
                    if "suffixes" in rule["match"]
                    and not set(rule["match"]) & {"headers", "prefixes", "names"}}
        self.assertEqual(unscoped, set(self.ALLOWED_SUFFIX_RULES),
                         "an unscoped suffix rule appeared or disappeared without "
                         "its reason being written here")

    def test_the_removed_catch_all_has_not_come_back(self) -> None:
        """No rule matches every ``*_ext`` route again.

        The one that did turned every route CNA might add later into a reviewed
        decision nobody had made, which is what UNREVIEWED exists to prevent.
        """
        import json

        rules = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))["rules"]
        for rule in rules:
            match = rule["match"]
            if set(match) & {"headers", "prefixes", "names"}:
                continue
            self.assertNotIn("_ext", match.get("suffixes", ()), rule.get("id"))

    def test_every_shipped_rule_carries_a_written_reason(self) -> None:
        import json

        document = json.loads(census.RULES_PATH.read_text(encoding="utf-8"))
        for rule in document["rules"]:
            self.assertTrue((rule.get("reason") or "").strip(), rule.get("id"))
            self.assertTrue((rule.get("boundReason") or "").strip(), rule.get("id"))
            self.assertIn(rule["purpose"], census.PURPOSES, rule.get("id"))
            self.assertIn(rule["status"], census.STATUSES, rule.get("id"))
