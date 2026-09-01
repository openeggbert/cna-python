#!/usr/bin/env python3
"""Gate for the CNA extension profile.

The strict XNA verifier and this one answer different questions and neither
substitutes for the other. The strict verifier asks whether
``Microsoft.Xna.Framework`` is exactly the selected XNA 4.0 projection. This one
asks whether the CNA-only surface stays where it belongs and keeps its own
promises:

* nothing under ``cna`` leaks a ctypes object, a private native module, or a raw
  CNA handle into public view;
* every public name is documented, because an extension has no reference
  implementation to consult;
* the XNA namespace does not depend on the extension profile, so a program that
  never imports ``cna`` behaves identically.

A leak here is a defect even though the strict verifier would stay green, which
is the entire reason this gate exists separately.
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import importlib
import inspect
import json
from pathlib import Path
import pkgutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
sys.path.insert(0, str(SOURCE))

EXTENSION_ROOT = "cna"
XNA_ROOT = SOURCE / "Microsoft"
PRIVATE_NATIVE = "_cna_native"


def _extension_modules() -> list[str]:
    package = importlib.import_module(EXTENSION_ROOT)
    names = [EXTENSION_ROOT]
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{EXTENSION_ROOT}."):
        names.append(info.name)
    return names


def _is_ctypes(value: object) -> bool:
    if isinstance(value, (ctypes.Structure, ctypes.Union, ctypes._SimpleCData)):
        return True
    if isinstance(value, type) and issubclass(
        value, (ctypes.Structure, ctypes.Union, ctypes._SimpleCData, ctypes._Pointer, ctypes._CFuncPtr)
    ):
        return True
    return False


def _public_names(module: object) -> list[str]:
    declared = getattr(module, "__all__", None)
    if declared is not None:
        return [str(name) for name in declared]
    return [name for name in dir(module) if not name.startswith("_")]


def audit() -> dict[str, object]:
    ctypes_leaks: list[dict[str, str]] = []
    native_leaks: list[dict[str, str]] = []
    undocumented: list[str] = []
    signatures: dict[str, str] = {}
    modules = _extension_modules()

    for name in modules:
        module = importlib.import_module(name)
        if not (module.__doc__ or "").strip():
            undocumented.append(name)
        for attribute in _public_names(module):
            value = getattr(module, attribute, None)
            qualified = f"{name}.{attribute}"
            if _is_ctypes(value):
                ctypes_leaks.append({"name": qualified, "type": type(value).__name__})
                continue
            origin = getattr(value, "__module__", "")
            if isinstance(origin, str) and origin.split(".")[0] == PRIVATE_NATIVE:
                native_leaks.append({"name": qualified, "module": origin})
                continue
            if inspect.ismodule(value):
                continue
            if (inspect.isfunction(value) or inspect.isclass(value)):
                if not (value.__doc__ or "").strip():
                    undocumented.append(qualified)
                try:
                    signatures[qualified] = (
                        str(inspect.signature(value)) if inspect.isfunction(value) else "class"
                    )
                except (TypeError, ValueError):
                    signatures[qualified] = "class"

    # The XNA projection must not depend on the extension profile: a program that
    # never imports `cna` has to behave exactly as it did before this existed.
    contamination: list[dict[str, str]] = []
    for path in sorted(XNA_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:  # pragma: no cover - a syntax error fails elsewhere
            contamination.append({"file": str(path.relative_to(ROOT)), "detail": str(error)})
            continue
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported = [node.module]
            for value in imported:
                if value == EXTENSION_ROOT or value.startswith(f"{EXTENSION_ROOT}."):
                    contamination.append({
                        "file": str(path.relative_to(ROOT)),
                        "line": node.lineno,
                        "imports": value,
                    })

    summary = {
        "EXTENSION_MODULES": len(modules),
        "PUBLIC_EXTENSION_NAMES": len(signatures),
        "PUBLIC_CTYPES_LEAK": len(ctypes_leaks),
        "PRIVATE_NATIVE_LEAK": len(native_leaks),
        "UNDOCUMENTED_PUBLIC": len(undocumented),
        "XNA_NAMESPACE_CONTAMINATION": len(contamination),
    }
    summary["EXTENSION_SURFACE_DIAGNOSTICS"] = (
        summary["PUBLIC_CTYPES_LEAK"] + summary["PRIVATE_NATIVE_LEAK"]
        + summary["UNDOCUMENTED_PUBLIC"] + summary["XNA_NAMESPACE_CONTAMINATION"]
    )
    return {
        "schemaVersion": 1,
        "summary": summary,
        "modules": modules,
        "signatures": signatures,
        "ctypesLeaks": ctypes_leaks,
        "privateNativeLeaks": native_leaks,
        "undocumented": undocumented,
        "xnaContamination": contamination,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()
    report = audit()
    if arguments.output:
        Path(arguments.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key, value in report["summary"].items():
        print(f"{key}={value}")
    for leak in report["ctypesLeaks"]:
        print(f"CTYPES_LEAK {leak['name']} ({leak['type']})")
    for leak in report["privateNativeLeaks"]:
        print(f"PRIVATE_NATIVE_LEAK {leak['name']} from {leak['module']}")
    for name in report["undocumented"]:
        print(f"UNDOCUMENTED {name}")
    for item in report["xnaContamination"]:
        print(f"XNA_CONTAMINATION {item['file']}:{item.get('line')} imports {item.get('imports')}")
    return 1 if report["summary"]["EXTENSION_SURFACE_DIAGNOSTICS"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
