#!/usr/bin/env python3
"""Compares two strict-profile contracts field by field.

This is how the reference extractor proves itself: re-deriving the
already-accepted `xna40-windows-runtime` contract from the pinned assemblies
must reproduce it exactly, or the extractor is not an authority for any other
profile either.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def key(member: dict) -> tuple:
    kind = member["kind"]
    if kind in ("method", "constructor"):
        return (kind, member["name"],
                tuple((p["name"], p["type"], p["ref"], p["out"], p["in"], p["optional"])
                      for p in member["parameters"]),
                tuple(g["name"] for g in member["genericParameters"]))
    if kind == "property":
        return (kind, member["name"],
                tuple((p["name"], p["type"]) for p in member["parameters"]))
    return (kind, member["name"])


def compare(left: dict, right: dict) -> list[str]:
    problems: list[str] = []
    left_types = {t["name"]: t for t in left["types"]}
    right_types = {t["name"]: t for t in right["types"]}
    for name in sorted(set(left_types) - set(right_types)):
        problems.append(f"ONLY_IN_LEFT_TYPE {name}")
    for name in sorted(set(right_types) - set(left_types)):
        problems.append(f"ONLY_IN_RIGHT_TYPE {name}")
    for name in sorted(set(left_types) & set(right_types)):
        a, b = left_types[name], right_types[name]
        for field in ("kind", "flags", "sealed", "underlyingType", "baseType",
                      "interfaces", "directInterfaces", "genericParameters"):
            if a[field] != b[field]:
                problems.append(f"TYPE_FIELD {name}.{field}: {a[field]!r} != {b[field]!r}")
        a_members = {key(m): m for m in a["members"]}
        b_members = {key(m): m for m in b["members"]}
        if len(a_members) != len(a["members"]) or len(b_members) != len(b["members"]):
            problems.append(f"DUPLICATE_MEMBER_KEY {name}")
        for k in sorted(set(a_members) - set(b_members), key=repr):
            problems.append(f"ONLY_IN_LEFT_MEMBER {name} {k}")
        for k in sorted(set(b_members) - set(a_members), key=repr):
            problems.append(f"ONLY_IN_RIGHT_MEMBER {name} {k}")
        for k in sorted(set(a_members) & set(b_members), key=repr):
            ma, mb = a_members[k], b_members[k]
            if ma != mb:
                for field in sorted(set(ma) | set(mb)):
                    if ma.get(field) != mb.get(field):
                        problems.append(
                            f"MEMBER_FIELD {name} {k} .{field}: "
                            f"{ma.get(field)!r} != {mb.get(field)!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--limit", type=int, default=60)
    arguments = parser.parse_args()
    left = json.loads(arguments.left.read_text())
    right = json.loads(arguments.right.read_text())
    problems = compare(left, right)
    for line in problems[: arguments.limit]:
        print(line)
    print(f"CONTRACT_DIFFERENCES={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
