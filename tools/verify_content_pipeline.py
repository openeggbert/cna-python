#!/usr/bin/env python3
"""Coverage gate for the XNA Content Pipeline projection.

The strict verifier answers "is every member *there*, with the right shape?".
This answers the other question: "does every member *do* something?" -- because a
surface that is structurally exact and made of methods that refuse is not a
projection of anything.

How it decides, without being told:

* Every projected member's implementation is read. One that cannot raise
  ``NotImplementedError`` is **IMPLEMENTED**, and nothing more is asked of it.
* One that can raise it has to appear in ``tools/content-pipeline-decisions.json``
  with a status and a written reason. A member that refuses and is *not*
  declared is **UNREVIEWED**, which is the one status this gate may not ship.
* A declared member that no longer refuses is **STALE**: the decision outlived
  the reason for it, and saying so is how a blocker gets removed when it is
  fixed rather than lingering as a comment.

``ACTIONABLE_LOCAL`` is work this repository could do and has not. It must be
zero. Everything else is a decision with a reason attached to it.
"""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tools" / "api_compat"))

DECISIONS_PATH = ROOT / "tools" / "content-pipeline-decisions.json"
PROFILE = "xna40-windows-content-pipeline"

#: What a decision may say. ``ACTIONABLE_LOCAL`` is the one that fails the gate.
STATUSES = (
    #: XNA declares the member abstract, and so does this projection. The
    #: concrete implementations are named in the decision's reason.
    "ABSTRACT_BY_DESIGN",
    #: The member is implemented; the ``NotImplementedError`` inside it is an
    #: error path for arguments it cannot serve.
    "IMPLEMENTED_ERROR_PATH",
    "BLOCKED_UPSTREAM",
    "BLOCKED_FIXTURE",
    "LANGUAGE_MAPPING_LIMITATION",
    #: Work this repository could do and has not. Must be zero.
    "ACTIONABLE_LOCAL",
)


def projected_members(profile) -> dict[str, dict[str, object]]:
    """Every ``Type.Member`` the strict profile projects, with its implementation."""
    from verify import Profile, projected_name, target_types  # noqa: E402

    rules = json.loads((ROOT / "tools/api_compat/mapping-rules.json").read_text())
    targets, _diagnostics = target_types(profile)
    result: dict[str, dict[str, object]] = {}
    for expected in profile.contract["types"]:
        identity = expected["name"]
        target = targets.get(identity)
        if target is None:
            continue
        for member in expected["members"]:
            name = projected_name(expected, member, rules)
            if name is None:
                continue
            raw = _raw_member(target, name)
            if raw is None:
                continue
            key = f"{identity}.{name}"
            if key in result:
                continue
            result[key] = {"target": target, "name": name, "raw": raw}
    return result


def _raw_member(owner: type, name: str):
    for base in owner.__mro__:
        if name in base.__dict__:
            return base.__dict__[name]
    return None


def refuses(raw: object) -> bool:
    """Whether a member's own code can raise ``NotImplementedError``.

    Read from the source rather than by calling it: a member that refuses only
    for some arguments still refuses, and calling every member of a content
    pipeline to find out would need a content project to call them with.
    """
    for function in _functions(raw):
        try:
            source = inspect.getsource(function)
        except (OSError, TypeError):
            continue
        if "NotImplementedError" in source:
            return True
    return False


def _functions(raw: object):
    if isinstance(raw, property):
        return [value for value in (raw.fget, raw.fset) if value is not None]
    if isinstance(raw, (staticmethod, classmethod)):
        return [raw.__func__]
    if inspect.isfunction(raw):
        return [raw]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()

    from verify import Profile  # noqa: E402

    profile = Profile.load(PROFILE)
    members = projected_members(profile)
    document = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    decisions = {entry["member"]: entry for entry in document["decisions"]}

    rows: list[dict[str, object]] = []
    counts = {status: 0 for status in STATUSES}
    unreviewed: list[str] = []
    stale: list[str] = []
    absent: list[str] = []

    for key in sorted(members):
        entry = members[key]
        declared = decisions.get(key)
        if refuses(entry["raw"]):
            if declared is None:
                unreviewed.append(key)
                rows.append({"member": key, "status": "UNREVIEWED"})
                continue
            counts[declared["status"]] += 1
            rows.append({"member": key, "status": declared["status"],
                         "reason": declared["reason"]})
        else:
            if declared is not None:
                stale.append(key)
            rows.append({"member": key, "status": "IMPLEMENTED"})

    for key in sorted(decisions):
        if key not in members:
            absent.append(key)

    implemented = sum(1 for row in rows if row["status"] == "IMPLEMENTED")
    report = {
        "schemaVersion": 1,
        "profile": PROFILE,
        "summary": {
            "PROJECTED_MEMBERS": len(members),
            "IMPLEMENTED": implemented,
            "UNREVIEWED": len(unreviewed),
            "STALE_DECISIONS": len(stale),
            "DECISIONS_FOR_ABSENT_MEMBERS": len(absent),
            **{f"STATUS_{status}": counts[status] for status in STATUSES},
            "CONTENT_PIPELINE_ACTIONABLE_LOCAL": counts["ACTIONABLE_LOCAL"],
        },
        "unreviewed": unreviewed,
        "stale": stale,
        "absent": absent,
        "members": rows,
    }
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    for key in unreviewed:
        print(f"  UNREVIEWED {key}")
    for key in stale:
        print(f"  STALE {key}")
    for key in absent:
        print(f"  ABSENT {key}")
    failed = bool(unreviewed or stale or absent
                  or counts["ACTIONABLE_LOCAL"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
