#!/usr/bin/env python3
"""Strict runtime-structure verifier for the normative XNA-to-Python mapping."""

from __future__ import annotations

import argparse
import ctypes
from enum import Enum, Flag
import importlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
REFERENCE = ROOT / "tools/api_compat/reference/xna40-windows-runtime-contract.json"
PROFILE = ROOT / "tools/api_compat/profiles/xna40-windows-runtime.json"
RULES = ROOT / "tools/api_compat/mapping-rules.json"
INVENTORY_JSON = ROOT / "docs/generated/missing-type-inventory.json"
INVENTORY_MD = ROOT / "docs/generated/missing-type-inventory.md"

CATEGORIES = (
    "MISSING_TYPE", "MISSING_MEMBER", "UNEXPECTED_TYPE", "UNEXPECTED_MEMBER",
    "TYPE_KIND_MISMATCH", "BASE_MAPPING_MISMATCH", "INTERFACE_MAPPING_MISMATCH",
    "FIELD_MAPPING_MISMATCH", "PROPERTY_MAPPING_MISMATCH",
    "METHOD_SIGNATURE_MAPPING_MISMATCH", "PARAMETER_MAPPING_MISMATCH",
    "RETURN_MAPPING_MISMATCH", "OVERLOAD_MAPPING_MISMATCH", "GENERIC_MAPPING_MISMATCH",
    "ENUM_VALUE_MISMATCH", "FLAGS_MAPPING_MISMATCH", "EVENT_MAPPING_MISMATCH",
    "OPERATOR_MAPPING_MISMATCH", "LANGUAGE_MAPPING_MISMATCH", "INTERNAL_TYPE_LEAK",
    "RAW_HANDLE_LEAK", "PUBLIC_NATIVE_FFI_LEAK", "ALLOWLIST_ENTRIES",
    "UNMEASURED_STRUCTURAL_CATEGORY",
)

PACKAGES = (
    "Microsoft.Xna.Framework",
    "Microsoft.Xna.Framework.Graphics",
    "Microsoft.Xna.Framework.Input",
    "Microsoft.Xna.Framework.Content",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--leak-only", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--inventory", action="store_true")
    return parser.parse_args()


def projected_name(owner: dict[str, Any], member: dict[str, Any], rules: dict[str, Any]) -> str | None:
    if owner["kind"] == "enum" and member["kind"] == "field" and member["name"] == "value__":
        return None
    if member["kind"] == "method" and member["name"] == "Finalize":
        return None
    if member["kind"] == "constructor":
        return rules["constructor"]
    if member["kind"] == "method" and member["name"] in rules["operators"]:
        return rules["operators"][member["name"]]
    if member["kind"] == "property" and member["name"] == "Item":
        return rules["indexer"]
    if member["name"] in rules["keywords"]:
        return member["name"] + rules["keywordSuffix"]
    return member["name"]


def member_signature(member: dict[str, Any]) -> str:
    parameters = member.get("parameters", [])
    return f"{member['name']}({','.join(value['type'] for value in parameters)})"


def expected_arity(member: dict[str, Any]) -> int:
    count = sum(1 for parameter in member.get("parameters", []) if not parameter.get("out"))
    # Python dunders bind the left operand as ``self``.
    if member["kind"] == "method" and member["name"].startswith("op_"):
        count -= 1
    return count


def target_types() -> tuple[dict[str, type], list[dict[str, str]]]:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    result: dict[str, type] = {}
    diagnostics: list[dict[str, str]] = []
    seen_objects: dict[int, str] = {}
    for package_name in PACKAGES:
        package = importlib.import_module(package_name)
        for name in getattr(package, "__all__", ()):
            value = getattr(package, name)
            if not isinstance(value, type):
                continue
            identity = f"{package_name}.{name}"
            previous = seen_objects.get(id(value))
            if previous is not None and previous != identity:
                diagnostics.append({"category": "UNEXPECTED_TYPE", "type": identity,
                                    "detail": f"duplicate public alias of {previous}"})
                continue
            seen_objects[id(value)] = identity
            result[identity] = value
    return result, diagnostics


def target_kind(value: type) -> str:
    if issubclass(value, Enum):
        return "enum"
    return "class"


def accepted_arities(owner: type, name: str, raw: object) -> set[int] | None:
    metadata = getattr(owner, "__xna_arities__", {}).get(name)
    if metadata is not None:
        return set(metadata)
    try:
        if isinstance(raw, staticmethod):
            function, bound_offset = raw.__func__, 0
        elif isinstance(raw, classmethod):
            function, bound_offset = raw.__func__, 1
        elif inspect.isfunction(raw):
            function, bound_offset = raw, 1
        else:
            function, bound_offset = getattr(owner, name), 0
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return None
    minimum = 0
    maximum = 0
    for index, parameter in enumerate(signature.parameters.values()):
        if index < bound_offset:
            continue
        if parameter.kind is parameter.VAR_POSITIONAL:
            return None
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            maximum += 1
            if parameter.default is parameter.empty:
                minimum += 1
    return set(range(minimum, maximum + 1))


def raw_member(owner: type, name: str) -> object | None:
    for base in owner.__mro__:
        if name in base.__dict__:
            return base.__dict__[name]
    return None


def is_property_shape(raw: object, static: bool) -> tuple[bool, bool, bool]:
    if isinstance(raw, property):
        return True, raw.fget is not None, raw.fset is not None
    if static and hasattr(raw, "__get__") and not callable(raw):
        return True, True, False
    return False, False, False


def actual_member_names(owner: type) -> set[str]:
    language = set(json.loads(RULES.read_text())["languageMembers"])
    return {name for name in owner.__dict__
            if (not name.startswith("_") or name in language) and name not in {"None"}}


def add(diagnostics: list[dict[str, str]], category: str, type_name: str, detail: str) -> None:
    diagnostics.append({"category": category, "type": type_name, "detail": detail})


def inspect_leaks(identity: str, value: type, diagnostics: list[dict[str, str]]) -> None:
    for base in value.__bases__:
        if base.__module__.startswith("_cna_native"):
            add(diagnostics, "INTERNAL_TYPE_LEAK", identity,
                f"public base leaks {base.__module__}.{base.__name__}")
    for name, raw in value.__dict__.items():
        if name.startswith("_"):
            continue
        annotation = getattr(raw, "__annotations__", {})
        text = repr(annotation)
        if "_cna_native" in text:
            add(diagnostics, "PUBLIC_NATIVE_FFI_LEAK", identity, f"{name} annotation exposes _cna_native")
        if "ctypes" in text or "c_void_p" in text or "LP_" in text:
            add(diagnostics, "RAW_HANDLE_LEAK", identity, f"{name} annotation exposes ctypes/pointer")
        if isinstance(raw, type) and issubclass(raw, (ctypes.Structure, ctypes._Pointer)):
            add(diagnostics, "PUBLIC_NATIVE_FFI_LEAK", identity, f"{name} exposes a ctypes type")


def diagnose_broken_fixture(fixture: dict[str, Any]) -> set[str]:
    """Small structural-fixture evaluator used to prove category detectors."""
    expected, target = fixture.get("expected", {}), fixture.get("target", {})
    categories: set[str] = set()
    if set(expected.get("members", ())) - set(target.get("members", ())):
        categories.add("MISSING_MEMBER")
    if expected.get("properties") != target.get("properties") and "properties" in expected:
        categories.add("PROPERTY_MAPPING_MISMATCH")
    if expected.get("enum") != target.get("enum") and "enum" in expected:
        categories.add("ENUM_VALUE_MISMATCH")
    if expected.get("arities") != target.get("arities") and "arities" in expected:
        categories.add("OVERLOAD_MAPPING_MISMATCH")
    if set(target.get("types", ())) - set(expected.get("types", ())):
        categories.add("UNEXPECTED_TYPE")
    if str(target.get("baseModule", "")).startswith("_cna_native"):
        categories.add("INTERNAL_TYPE_LEAK")
    annotation = str(target.get("annotation", ""))
    if "ctypes" in annotation or "c_void_p" in annotation:
        categories.add("RAW_HANDLE_LEAK")
    if "name" in expected and expected.get("name") != target.get("name"):
        categories.add("LANGUAGE_MAPPING_MISMATCH")
    return categories


def verify() -> dict[str, Any]:
    reference = json.loads(REFERENCE.read_text())
    profile = json.loads(PROFILE.read_text())
    rules = json.loads(RULES.read_text())
    targets, diagnostics = target_types()
    reference_by_name = {value["name"]: value for value in reference["types"]}
    expected_names = set(reference_by_name)

    for identity in sorted(set(targets) - expected_names):
        add(diagnostics, "UNEXPECTED_TYPE", identity, "public type is absent from the pinned XNA profile")

    scoreboards: list[dict[str, Any]] = []
    target_member_count = 0
    zero_types: list[str] = []
    for identity in sorted(expected_names):
        expected = reference_by_name[identity]
        target = targets.get(identity)
        before = len(diagnostics)
        if target is None:
            add(diagnostics, "MISSING_TYPE", identity, "type is not exported")
            scoreboards.append({"type": identity, "status": "missing", "diagnostics": 1})
            continue
        inspect_leaks(identity, target, diagnostics)
        expected_kind = expected["kind"]
        actual_kind = target_kind(target)
        if expected_kind != "enum":
            add(diagnostics, "UNMEASURED_STRUCTURAL_CATEGORY", identity,
                "full interface, field-type, parameter-type, return-type, and generic mapping remains unmeasured")
        if expected_kind == "enum" and actual_kind != "enum":
            add(diagnostics, "TYPE_KIND_MISMATCH", identity, f"expected enum, got {actual_kind}")
        elif expected_kind != "enum" and actual_kind == "enum":
            add(diagnostics, "TYPE_KIND_MISMATCH", identity, f"expected {expected_kind}, got enum")
        if expected_kind == "enum" and bool(expected.get("flags")) != issubclass(target, Flag):
            add(diagnostics, "FLAGS_MAPPING_MISMATCH", identity, "IntEnum/IntFlag choice differs")

        base_name = expected.get("baseType")
        if base_name and base_name.startswith("Microsoft.Xna.Framework") and base_name in targets:
            if targets[base_name] not in target.__bases__:
                add(diagnostics, "BASE_MAPPING_MISMATCH", identity, f"expected direct base {base_name}")

        grouped: dict[str, list[dict[str, Any]]] = {}
        expected_public_names: set[str] = set()
        for member in expected["members"]:
            name = projected_name(expected, member, rules)
            if name is None:
                continue
            expected_public_names.add(name)
            grouped.setdefault(name, []).append(member)
        actual_names = actual_member_names(target)
        target_member_count += len(actual_names)
        for name in sorted(actual_names - expected_public_names - set(rules["languageMembers"])):
            add(diagnostics, "UNEXPECTED_MEMBER", identity, name)

        for name, members in sorted(grouped.items()):
            raw = raw_member(target, name)
            if raw is None:
                for member in members:
                    category = "OPERATOR_MAPPING_MISMATCH" if member["name"].startswith("op_") else "MISSING_MEMBER"
                    add(diagnostics, category, identity, member_signature(member))
                continue
            sample = members[0]
            if sample["kind"] == "field" and expected_kind == "enum":
                actual = getattr(target, name, None)
                expected_value = int(sample["value"])
                if not isinstance(actual, target) or int(actual) != expected_value:
                    add(diagnostics, "ENUM_VALUE_MISMATCH", identity,
                        f"{name}: expected {expected_value}, got {actual!r}")
            elif sample["kind"] == "property":
                if name == "__getitem__" and callable(getattr(target, name, None)):
                    shaped, can_get, can_set = True, True, False
                else:
                    shaped, can_get, can_set = is_property_shape(raw, bool(sample.get("static")))
                if not shaped or can_get != bool(sample.get("get")) or can_set != bool(sample.get("set")):
                    add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                        f"{name}: expected get={sample.get('get')} set={sample.get('set')} static={sample.get('static')}")
            elif sample["kind"] in ("method", "constructor"):
                if not callable(getattr(target, name, None)):
                    add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity, f"{name} is not callable")
                expected_arities = {expected_arity(member) for member in members}
                if sample["kind"] == "constructor" and expected_kind == "struct":
                    expected_arities.add(0)
                actual_arities = accepted_arities(target, name, raw)
                if actual_arities is not None and actual_arities != expected_arities:
                    add(diagnostics, "OVERLOAD_MAPPING_MISMATCH", identity,
                        f"{name}: expected arities {sorted(expected_arities)}, got {sorted(actual_arities)}")
            elif sample["kind"] == "event":
                if raw.__class__.__name__ != "Event":
                    add(diagnostics, "EVENT_MAPPING_MISMATCH", identity, f"{name} is not the mapped Event descriptor")

        count = len(diagnostics) - before
        if count == 0:
            zero_types.append(identity)
        scoreboards.append({"type": identity, "status": "complete" if count == 0 else "partial",
                            "diagnostics": count})

    if profile["allowlist"]:
        for value in profile["allowlist"]:
            add(diagnostics, "ALLOWLIST_ENTRIES", "<profile>", str(value))

    diagnostics.sort(key=lambda value: (value["category"], value["type"], value["detail"]))
    counts = {category: 0 for category in CATEGORIES}
    for diagnostic in diagnostics:
        counts[diagnostic["category"]] += 1
    family: dict[str, dict[str, int]] = {}
    for value in scoreboards:
        namespace = ".".join(value["type"].split(".")[:-1])
        bucket = family.setdefault(namespace, {"types": 0, "diagnostics": 0})
        bucket["types"] += 1
        bucket["diagnostics"] += value["diagnostics"]
    summary = {
        "REFERENCE_TYPES": len(reference["types"]),
        "REFERENCE_MEMBERS": sum(len(value["members"]) for value in reference["types"]),
        "EXPECTED_PYTHON_TYPES": profile["expectedPythonTypes"],
        "EXPECTED_PYTHON_MEMBERS": profile["expectedPythonMembers"],
        "TARGET_TYPES": len(targets),
        "TARGET_MEMBERS": target_member_count,
        "TOTAL_DIAGNOSTICS": len(diagnostics),
        **counts,
    }
    return {"schemaVersion": 1, "summary": summary, "diagnostics": diagnostics,
            "zeroDiagnosticTypes": zero_types, "typeScoreboard": scoreboards,
            "familyScoreboard": dict(sorted(family.items()))}


def write_inventory(report: dict[str, Any]) -> None:
    missing = [value["type"] for value in report["diagnostics"] if value["category"] == "MISSING_TYPE"]
    payload = {"profile": "XNA 4.0 Windows runtime", "missingTypeCount": len(missing), "types": missing}
    INVENTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    families: dict[str, list[str]] = {}
    for name in missing:
        namespace, short = name.rsplit(".", 1)
        families.setdefault(namespace, []).append(short)
    lines = ["# Missing XNA type inventory", "", f"Missing types: **{len(missing)}**.", ""]
    for namespace, names in sorted(families.items()):
        lines.extend((f"## {namespace}", "", *[f"- `{name}`" for name in sorted(names)], ""))
    INVENTORY_MD.write_text("\n".join(lines))


def print_summary(report: dict[str, Any]) -> None:
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    print("ZERO_DIAGNOSTIC_TYPES=" + str(len(report["zeroDiagnosticTypes"])))


def main() -> int:
    args = parse_args()
    report = verify()
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    if args.inventory:
        write_inventory(report)
    print_summary(report)
    if args.leak_only:
        gate = ("UNEXPECTED_TYPE", "UNEXPECTED_MEMBER", "INTERNAL_TYPE_LEAK", "RAW_HANDLE_LEAK",
                "PUBLIC_NATIVE_FFI_LEAK", "ALLOWLIST_ENTRIES")
        return 1 if any(report["summary"][name] for name in gate) else 0
    if args.check:
        return 1 if report["summary"]["TOTAL_DIAGNOSTICS"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
