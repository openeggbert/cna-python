#!/usr/bin/env python3
"""Classifies every canonical CNA C route by purpose and by binding status.

Two questions are answered separately, because conflating them is how a census
stops being useful:

* **Purpose** -- why the route exists, from CNA-Python's point of view.  A route
  can be `XNA_BACKING` and still be unbound, and a route can be bound while its
  purpose is only tooling.
* **Binding status** -- why it is or is not imported today.

Classification is rule-driven so it can be re-derived when CNA changes rather
than hand-maintained per route.  Every rule carries a written reason, the first
matching rule wins, and a route that matches no rule is `UNREVIEWED`, which
fails the gate.  Being unreviewed is the one status the census may not ship.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from cna_headers import parse_include_directory  # noqa: E402

from _cna_native.loader import FUNCTION_MANIFEST  # noqa: E402

PURPOSES = (
    "XNA_BACKING",
    "CNA_EXTENSION_CANDIDATE",
    "MANAGED_BY_DESIGN",
    "TOOLING_ONLY",
    "OUT_OF_SELECTED_PROFILE",
    "NOT_USEFUL_FOR_PYTHON",
)

STATUSES = (
    "BOUND",
    "ACTIONABLE_LOCAL",
    "BLOCKED_UPSTREAM",
    "BLOCKED_RENDERER",
    "BLOCKED_PLATFORM",
    "BLOCKED_HARDWARE",
    "BLOCKED_FIXTURE",
    "LANGUAGE_MAPPING_LIMITATION",
    "DELIBERATE_NON_BINDING",
    "UNREVIEWED",
)

RULES_PATH = ROOT / "tools/route-census-rules.json"


#: A selected extension family is reported separately from the global totals,
#: because "zero actionable overall" and "zero actionable inside the family we
#: opened" are different claims and only the second one is what finishing a
#: family means.  The families themselves, their headers and the rules that
#: carry their dependencies out of other headers are declared in the rules file
#: rather than here, so opening one is a data change with a written reason.
def in_family(row: dict, family: dict) -> bool:
    return row["header"] in family["headers"] or row["rule"] in family["ruleIds"]


def _matches(rule: dict, name: str, header: str) -> bool:
    match = rule["match"]
    if "names" in match and name not in match["names"]:
        return False
    if "headers" in match and header not in match["headers"]:
        return False
    if "prefixes" in match and not any(name.startswith(value) for value in match["prefixes"]):
        return False
    if "suffixes" in match and not any(name.endswith(value) for value in match["suffixes"]):
        return False
    if "contains" in match and not any(value in name for value in match["contains"]):
        return False
    return bool(match)


def shadowed_rules(declarations: dict, rules: list[dict]) -> list[dict]:
    """Rules an earlier rule has taken every route away from.

    First-match-wins makes a rule's *position* part of its meaning, and a rule
    that names specific routes is the most specific kind there is -- so it losing
    every one of them to an earlier prefix rule is always a mistake rather than a
    choice. It happened: ``engine-c-lifetime-transfer`` names three ownership
    transfers as deliberate non-bindings, and one of them sat one position behind
    ``engine-post-process-pass``, whose prefix claimed it. The census then
    reported a decision that had already been made as an outstanding task, and
    nothing noticed, because every other check asks about routes rather than
    about rules.

    Two things are reported, because a rule can fail in two ways:

    * a rule that names routes and does not get one of them -- always a defect,
      whatever else the rule still classifies;
    * a rule that classifies nothing at all -- either shadowed entirely or dead.
      A dead rule is worth removing rather than keeping: a broad catch-all left
      at the end of the list quietly converts every future route CNA adds into a
      reviewed decision nobody made, which is exactly what ``UNREVIEWED`` exists
      to prevent.
    """
    claimed: dict[str, str | None] = {}
    for name, declaration in declarations.items():
        for rule in rules:
            if _matches(rule, name, declaration.header):
                claimed[name] = rule.get("id")
                break
    diagnostics = []
    for index, rule in enumerate(rules):
        identifier = rule.get("id", index)
        matched = [name for name, winner in claimed.items() if winner == identifier]
        lost = sorted(name for name in rule["match"].get("names", ())
                      if name in declarations and claimed.get(name) != identifier)
        if lost:
            diagnostics.append({
                "rule": identifier,
                "kind": "NAMED_ROUTE_TAKEN",
                "shadowedBy": sorted({claimed[name] for name in lost}),
                "routes": lost,
            })
        # One rule, one diagnostic: a named rule that lost every route it names
        # has already been reported, and saying it classifies nothing as well
        # would make the count of *rules* to fix disagree with the count of
        # lines printed.
        if matched or lost:
            continue
        would_match = [name for name, declaration in declarations.items()
                       if _matches(rule, name, declaration.header)]
        diagnostics.append({
            "rule": identifier,
            "kind": "SHADOWED" if would_match else "DEAD",
            "shadowedBy": sorted({claimed[name] for name in would_match}),
            "routes": sorted(would_match),
        })
    return diagnostics


def classify(declarations: dict, bound: set[str], rules: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for name, declaration in sorted(declarations.items()):
        selected = None
        for index, rule in enumerate(rules):
            if _matches(rule, name, declaration.header):
                selected = (index, rule)
                break
        if selected is None:
            rows.append({
                "route": name,
                "header": declaration.header,
                "purpose": "UNREVIEWED",
                "status": "UNREVIEWED",
                "reason": "no census rule matches this route",
                "rule": None,
                "bound": name in bound,
            })
            continue
        index, rule = selected
        is_bound = name in bound
        rows.append({
            "route": name,
            "header": declaration.header,
            "purpose": rule["purpose"],
            "status": "BOUND" if is_bound else rule["status"],
            # A rule's reason explains the unbound case; a bound route needs the
            # reason it is imported, not the reason it would not have been.
            "reason": (rule.get("boundReason", "imported: the selected profile reaches this route")
                       if is_bound else rule["reason"]),
            "rule": rule.get("id", index),
            "family": rule.get("family"),
            "familyTitle": rule.get("familyTitle"),
            "bound": is_bound,
        })
    return rows


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cna-root", required=True)
    parser.add_argument("--output")
    parser.add_argument("--markdown")
    parser.add_argument("--show-unreviewed", type=int, default=40)
    return parser.parse_args()


def render_markdown(rows: list[dict], summary: dict, families: list[dict]) -> str:
    lines = ["# CNA route census", ""]
    lines.append("Generated by `tools/route_census.py`. Purpose answers why a route exists;")
    lines.append("binding status answers why it is or is not imported. They are independent.")
    lines.append("")
    lines.append("```text")
    for key, value in summary.items():
        lines.append(f"{key}={value}")
    lines.append("```")
    lines.append("")
    lines.append("## By purpose and status")
    lines.append("")
    lines.append("| Purpose | Status | Routes |")
    lines.append("|---|---|---:|")
    pairs: dict[tuple[str, str], int] = {}
    for row in rows:
        pairs[(row["purpose"], row["status"])] = pairs.get((row["purpose"], row["status"]), 0) + 1
    for (purpose, status), count in sorted(pairs.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {purpose} | {status} | {count} |")
    lines.append("")
    for family in families:
        rows_in = [row for row in rows if in_family(row, family)]
        lines.append(f"## The selected {family['title']} extension family")
        lines.append("")
        lines.append(family["description"])
        lines.append("")
        lines.append("| Status | Routes |")
        lines.append("|---|---:|")
        counts: dict[str, int] = {}
        for row in rows_in:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {status} | {count} |")
        lines.append("")
        by_family = [row for row in rows_in if row.get("family")]
        if by_family:
            lines.append("### By sub-family")
            lines.append("")
            lines.append("| Sub-family | Routes | Bound | Statuses |")
            lines.append("|---|---:|---:|---|")
            grouped: dict[str, list[dict]] = {}
            for row in by_family:
                grouped.setdefault(row["family"], []).append(row)
            for name in sorted(grouped):
                group = grouped[name]
                statuses: dict[str, int] = {}
                for row in group:
                    statuses[row["status"]] = statuses.get(row["status"], 0) + 1
                spelled = ", ".join(f"{key} {value}" for key, value in sorted(statuses.items()))
                title = group[0].get("familyTitle") or name
                lines.append(f"| `{name}` ({title}) | {len(group)} | "
                             f"{sum(1 for row in group if row['bound'])} | {spelled} |")
            lines.append("")
        lines.append("| Route | Header | Status | Reason |")
        lines.append("|---|---|---|---|")
        for row in sorted(rows_in, key=lambda item: item["route"]):
            lines.append(f"| `{row['route']}` | {row['header']} | {row['status']} | "
                         f"{row['reason']} |")
        lines.append("")
    lines.append("## Reasons")
    lines.append("")
    lines.append("| Purpose | Status | Routes | Reason |")
    lines.append("|---|---|---:|---|")
    reasons: dict[tuple[str, str, str], int] = {}
    for row in rows:
        key = (row["purpose"], row["status"], row["reason"])
        reasons[key] = reasons.get(key, 0) + 1
    for (purpose, status, reason), count in sorted(reasons.items(), key=lambda item: (-item[1],)):
        lines.append(f"| {purpose} | {status} | {count} | {reason} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = arguments()
    include = Path(args.cna_root).resolve() / "modules/c-api/include"
    declarations = parse_include_directory(include)
    bound = {entry[0] for entry in FUNCTION_MANIFEST}
    document = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    rules = document["rules"]
    families = document["selectedFamilies"]

    known = {rule.get("id") for rule in rules}
    for family in families:
        for rule_id in family["ruleIds"]:
            if rule_id not in known:
                raise ValueError(f"selected family {family['id']} names unknown rule {rule_id}")

    for rule in rules:
        if rule["purpose"] not in PURPOSES:
            raise ValueError(f"rule {rule.get('id')} has unknown purpose {rule['purpose']}")
        if rule["status"] not in STATUSES:
            raise ValueError(f"rule {rule.get('id')} has unknown status {rule['status']}")
        if not rule.get("reason"):
            raise ValueError(f"rule {rule.get('id')} has no written reason")

    rows = classify(declarations, bound, rules)
    missing = sorted(bound - set(declarations))
    unreviewed = [row for row in rows if row["status"] == "UNREVIEWED"]
    # Only a rule that asserts a route category is never bound can be contradicted.
    # A family default legitimately covers both imported and unimported routes.
    exclusive = {rule.get("id") for rule in rules if rule.get("boundIsError")}
    contradictions = [row["route"] for row in rows if row["bound"] and row["rule"] in exclusive]
    shadowed = shadowed_rules(declarations, rules)

    counts: dict[str, int] = {}
    for row in rows:
        counts[f"PURPOSE_{row['purpose']}"] = counts.get(f"PURPOSE_{row['purpose']}", 0) + 1
        counts[f"STATUS_{row['status']}"] = counts.get(f"STATUS_{row['status']}", 0) + 1

    summary = {
        "CANONICAL_ROUTES": len(declarations),
        "BOUND_ROUTES": len(bound),
        "BOUND_NOT_IN_HEADERS": len(missing),
        "UNREVIEWED": len(unreviewed),
        "RULE_CONTRADICTIONS": len(contradictions),
        "RULE_SHADOWING_DIAGNOSTICS": len(shadowed),
    }
    selected: dict[str, list[dict]] = {}
    for family in families:
        rows_in = [row for row in rows if in_family(row, family)]
        selected[family["id"]] = rows_in
        label = family["label"]
        summary[f"{label}_ROUTES"] = len(rows_in)
        summary[f"{label}_BOUND"] = sum(1 for row in rows_in if row["bound"])
        summary[f"{label}_UNREVIEWED"] = sum(
            1 for row in rows_in if row["status"] == "UNREVIEWED")
        summary[f"SELECTED_{label}_ACTIONABLE_LOCAL"] = sum(
            1 for row in rows_in if row["status"] == "ACTIONABLE_LOCAL")
    summary.update({key: counts.get(key, 0) for key in
                    [f"PURPOSE_{value}" for value in PURPOSES]
                    + [f"STATUS_{value}" for value in STATUSES]})

    report = {
        "schemaVersion": 2,
        "summary": summary,
        "rules": rules,
        "selectedFamilies": families,
        "routes": rows,
        "selectedFamily": selected,
        "boundNotInHeaders": missing,
        "ruleContradictions": contradictions,
        "ruleShadowing": shadowed,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(rows, summary, families), encoding="utf-8")
    for key, value in summary.items():
        print(f"{key}={value}")
    for row in unreviewed[: args.show_unreviewed]:
        print(f"UNREVIEWED {row['header']}: {row['route']}")
    for route in contradictions[:20]:
        print(f"CONTRADICTION {route} is bound but its rule says it is not")
    for entry in shadowed[:20]:
        if entry["kind"] == "NAMED_ROUTE_TAKEN":
            print(f"SHADOWED rule {entry['rule']} names "
                  f"{', '.join(entry['routes'])}, which went to "
                  f"{', '.join(entry['shadowedBy'])}")
        elif entry["kind"] == "SHADOWED":
            print(f"SHADOWED rule {entry['rule']} classifies nothing; its "
                  f"{len(entry['routes'])} route(s) went to "
                  f"{', '.join(entry['shadowedBy'])}")
        else:
            print(f"DEAD rule {entry['rule']} matches no canonical route at all")
    return 1 if unreviewed or missing or contradictions or shadowed else 0


if __name__ == "__main__":
    raise SystemExit(main())
