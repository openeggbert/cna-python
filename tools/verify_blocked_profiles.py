#!/usr/bin/env python3
"""Checks that a profile declared blocked is still blocked, and blocked on that.

A profile this repository cannot measure is a claim like any other, and a claim
that has stopped being true is worse than one that was never made. So a
descriptor that says ``BLOCKED_REFERENCE_ASSET`` has to keep earning it:

``UNJUSTIFIED_BLOCK``
    the profile names a contract, or a contract file for it exists. A profile
    that can be measured is not blocked on being able to measure it.
``BLOCK_WITHOUT_REASON``
    no written reason, or no unblock condition, or no assemblies named. "It is
    not here" is not a finding; "these seven files are not here, and here is
    where I looked" is.
``STALE_BLOCK``
    the recorded search found the assemblies after all. Then the profile is
    unblocked and the descriptor is out of date.
``SEARCH_MISSING``
    there is no recorded search, or it was run for a different profile, or it
    left a candidate it could not identify. A search that cannot say what it
    found is not evidence.

The search itself is ``tools/find_reference_assemblies.py`` and is *not* re-run
here: it walks a million files and takes minutes. What this checks is that the
recorded one exists, was run for this profile, is complete, and says what the
descriptor says it says.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "tools" / "api_compat" / "profiles"
CONTRACTS = ROOT / "tools" / "api_compat" / "reference"
SEARCHES = ROOT / "docs" / "generated"

BLOCKED = "BLOCKED_REFERENCE_ASSET"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()

    rows: list[dict[str, object]] = []
    unjustified: list[str] = []
    unreasoned: list[str] = []
    stale: list[str] = []
    missing: list[str] = []

    for path in sorted(PROFILES.glob("*.json")):
        profile = json.loads(path.read_text())
        if profile.get("status") != BLOCKED:
            continue
        identifier = profile["id"]

        if profile.get("contract"):
            unjustified.append(f"{identifier}: names a contract")
        elif (CONTRACTS / f"{identifier}-contract.json").exists():
            unjustified.append(f"{identifier}: a contract file exists for it")

        for field in ("blockedReason", "unblockedBy"):
            if len((profile.get(field) or "").strip()) < 80:
                unreasoned.append(f"{identifier}: {field} says too little")
        if not profile.get("referenceAssemblies"):
            unreasoned.append(f"{identifier}: names no assemblies")

        search_path = SEARCHES / f"{identifier.split('-')[1]}-assembly-search.json"
        if not search_path.exists():
            missing.append(f"{identifier}: no recorded search at {search_path.name}")
            rows.append({"profile": identifier, "search": None})
            continue
        search = json.loads(search_path.read_text())
        if search.get("profile") != identifier:
            missing.append(
                f"{identifier}: the recorded search was run for "
                f"{search.get('profile')!r}")
        summary = search.get("summary", {})
        if sorted(search.get("assembliesWanted", ())) != \
                sorted(profile["referenceAssemblies"]):
            missing.append(
                f"{identifier}: the search looked for a different assembly set")
        if summary.get("UNIDENTIFIED"):
            missing.append(
                f"{identifier}: the search left "
                f"{summary['UNIDENTIFIED']} files it could not identify")
        if summary.get("CANDIDATES"):
            stale.append(
                f"{identifier}: the search found {summary['CANDIDATES']} "
                "candidate assemblies for this platform")
        rows.append({
            "profile": identifier,
            "assemblies": len(profile["referenceAssemblies"]),
            "filesExamined": search.get("filesExamined"),
            "rootsSearched": sum(1 for entry in search.get("roots", ())
                                 if entry.get("status") == "searched"),
            "nameMatches": summary.get("NAME_MATCHES"),
            "candidates": summary.get("CANDIDATES"),
            "unidentified": summary.get("UNIDENTIFIED"),
        })

    report = {
        "schemaVersion": 1,
        "summary": {
            "BLOCKED_PROFILES": len(rows),
            "UNJUSTIFIED_BLOCK": len(unjustified),
            "BLOCK_WITHOUT_REASON": len(unreasoned),
            "STALE_BLOCK": len(stale),
            "SEARCH_MISSING": len(missing),
        },
        "profiles": rows,
        "unjustified": unjustified,
        "unreasoned": unreasoned,
        "stale": stale,
        "missing": missing,
    }
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    for row in rows:
        print(f"  {row['profile']}: {row.get('assemblies')} assemblies wanted, "
              f"{row.get('filesExamined')} files examined across "
              f"{row.get('rootsSearched')} roots, "
              f"{row.get('candidates')} candidates")
    for entry in unjustified + unreasoned + stale + missing:
        print(f"  ! {entry}")
    return 1 if (unjustified or unreasoned or stale or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
