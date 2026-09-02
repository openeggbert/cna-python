#!/usr/bin/env python3
"""One scoreboard for every counter the six opened scopes have to hold at zero.

The scopes were opened together and they finish together, so the question "is it
done?" should be one command rather than eleven. This reads the reports the
gates produce -- it does not re-measure, because each gate is the authority on
its own numbers and re-deriving them here would be a second opinion nobody
asked for -- and fails if any counter that must be zero is not.

Run the gates first; this says whether what they wrote adds up.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "api_compat"))
GENERATED = ROOT / "docs" / "generated"

#: ``(report, path into its summary, label)`` for every counter that must be
#: zero, grouped by the scope that owns it.
ZERO = {
    "route census": [
        ("cna-route-census.json", "UNREVIEWED", "UNREVIEWED"),
        ("cna-route-census.json", "STATUS_UNREVIEWED", "STATUS_UNREVIEWED"),
        ("cna-route-census.json", "STATUS_ACTIONABLE_LOCAL",
         "STATUS_ACTIONABLE_LOCAL"),
        ("cna-route-census.json", "RULE_CONTRADICTIONS", "RULE_CONTRADICTIONS"),
        ("cna-route-census.json", "RULE_SHADOWING_DIAGNOSTICS",
         "RULE_SHADOWING_DIAGNOSTICS"),
    ],
    "selected families": [
        ("cna-route-census.json", "SELECTED_CNB_CNJ_ACTIONABLE_LOCAL", None),
        ("cna-route-census.json", "SELECTED_ENGINE_ACTIONABLE_LOCAL", None),
        ("cna-route-census.json", "SELECTED_DEVICES_ACTIONABLE_LOCAL", None),
        ("cna-route-census.json", "SELECTED_INPUT_ACTIONABLE_LOCAL", None),
        ("cna-route-census.json", "SELECTED_ONLINE_ACTIONABLE_LOCAL", None),
        ("cna-route-census.json", "CNB_CNJ_UNREVIEWED", None),
        ("cna-route-census.json", "ENGINE_UNREVIEWED", None),
        ("cna-route-census.json", "DEVICES_UNREVIEWED", None),
        ("cna-route-census.json", "INPUT_UNREVIEWED", None),
        ("cna-route-census.json", "ONLINE_UNREVIEWED", None),
    ],
    "content pipeline": [
        ("content-pipeline-coverage.json",
         "CONTENT_PIPELINE_ACTIONABLE_LOCAL", None),
        ("content-pipeline-coverage.json", "UNREVIEWED", None),
        ("content-pipeline-coverage.json", "STALE_DECISIONS", None),
        ("content-pipeline-coverage.json", "DECISIONS_FOR_ABSENT_MEMBERS", None),
    ],
    "platform profiles": [
        ("profile-separation.json", "PLATFORM_LEAKS", None),
        ("profile-separation.json", "WINDOWS_ONLY_REACHABLE_FROM_PLATFORM", None),
        ("profile-separation.json", "UNJUSTIFIED_REMOVALS", None),
        ("profile-separation.json", "DEFAULT_PROFILE_DRIFT", None),
        ("blocked-profiles.json", "UNJUSTIFIED_BLOCK", None),
        ("blocked-profiles.json", "BLOCK_WITHOUT_REASON", None),
        ("blocked-profiles.json", "STALE_BLOCK", None),
        ("blocked-profiles.json", "SEARCH_MISSING", None),
    ],
    "native boundary": [
        ("cna-abi-report.json", "MISSING_SYMBOLS", None),
        ("cna-abi-report.json", "ABI_MISMATCHES", None),
        ("cna-abi-report.json", "PENDING_ROUTES_NOT_IN_HEADERS", None),
        ("cna-abi-report.json", "STALE_PENDING_ROUTES", None),
        ("route-reachability.json", "UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE", None),
        ("route-reachability.json", "STALE_ADMISSIONS", None),
    ],
    "extension surface": [
        ("extension-surface-report.json", "EXTENSION_SURFACE_DIAGNOSTICS", None),
        ("extension-surface-report.json", "XNA_NAMESPACE_CONTAMINATION", None),
    ],
}

#: Counters that must hold an exact value rather than zero: the default Windows
#: surface, which nothing in six scopes was allowed to change.
EXACT = [
    ("profile-separation.json", "DEFAULT_PROFILE_TYPES", 257),
    ("profile-separation.json", "DEFAULT_PROFILE_MEMBERS", 2423),
]

#: The strict profiles, each of which must report zero diagnostics. Read from
#: the profile descriptors so a profile added later is not silently skipped.
PROFILES = ROOT / "tools" / "api_compat" / "profiles"


def _summary(name: str) -> dict:
    path = GENERATED / name
    if not path.exists():
        raise SystemExit(
            f"{name} has not been generated; run the gate that writes it")
    document = json.loads(path.read_text())
    return document.get("summary", document)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()

    rows: list[dict[str, object]] = []
    failures: list[str] = []
    for scope, counters in ZERO.items():
        for report, key, label in counters:
            summary = _summary(report)
            if key not in summary:
                failures.append(f"{report} has no {key}")
                continue
            value = summary[key]
            rows.append({"scope": scope, "counter": label or key,
                         "value": value, "wanted": 0})
            if value:
                failures.append(f"{scope}: {key}={value}, wanted 0")

    for report, key, wanted in EXACT:
        summary = _summary(report)
        value = summary.get(key)
        rows.append({"scope": "default surface", "counter": key,
                     "value": value, "wanted": wanted})
        if value != wanted:
            failures.append(f"default surface: {key}={value}, wanted {wanted}")

    measured, blocked = [], []
    for path in sorted(PROFILES.glob("*.json")):
        profile = json.loads(path.read_text())
        (blocked if profile.get("status") == "BLOCKED_REFERENCE_ASSET"
         else measured).append(profile["id"])

    # The strict profiles are re-measured rather than read: they write no
    # summary file of their own, and this is the counter the whole thing rests
    # on. Every other number here comes from the gate that owns it.
    from verify import Profile, verify  # noqa: E402

    for identifier in measured:
        summary = verify(Profile.load(identifier))["summary"]
        rows.append({"scope": "strict profiles",
                     "counter": f"{identifier} TOTAL_DIAGNOSTICS",
                     "value": summary["TOTAL_DIAGNOSTICS"], "wanted": 0})
        if summary["TOTAL_DIAGNOSTICS"]:
            failures.append(
                f"{identifier}: TOTAL_DIAGNOSTICS="
                f"{summary['TOTAL_DIAGNOSTICS']}, wanted 0")
        rows.append({"scope": "strict profiles",
                     "counter": f"{identifier} types",
                     "value": summary["TARGET_TYPES"],
                     "wanted": summary["EXPECTED_PYTHON_TYPES"]})
        if summary["TARGET_TYPES"] != summary["EXPECTED_PYTHON_TYPES"]:
            failures.append(
                f"{identifier}: {summary['TARGET_TYPES']} types, expected "
                f"{summary['EXPECTED_PYTHON_TYPES']}")

    report = {
        "schemaVersion": 1,
        "summary": {
            "COUNTERS_CHECKED": len(rows),
            "FAILURES": len(failures),
            "MEASURED_PROFILES": len(measured),
            "BLOCKED_PROFILES": len(blocked),
        },
        "measuredProfiles": measured,
        "blockedProfiles": blocked,
        "counters": rows,
        "failures": failures,
    }
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    scope = None
    for row in rows:
        if row["scope"] != scope:
            scope = row["scope"]
            print(f"  {scope}")
        print(f"    {row['counter']:<40s} {row['value']} "
              f"(wanted {row['wanted']})")
    for entry in failures:
        print(f"  ! {entry}")
    print("STOP_CONDITION=" + ("held" if not failures else "not held"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
