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
* no public signature *names* a native handle or a ctypes type, which a runtime
  check alone cannot see: an annotation is part of the published contract even
  when the value never crosses at runtime;
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

#: Spellings that must never appear in a public annotation.  A raw CNA handle is
#: a ``uint64`` and a ctypes object is an implementation detail; either one named
#: in a signature is a promise this surface does not intend to keep, whatever the
#: runtime value happens to be.
FORBIDDEN_ANNOTATIONS = (
    "ctypes", "c_uint64", "c_void_p", "c_char_p", "CNA_", "NativeHandle",
    "_cna_native", "CnbDocumentHandle", "CNA_Handle",
)

#: Public attribute names that would hand a caller a raw handle directly.
FORBIDDEN_PUBLIC_ATTRIBUTES = ("handle", "native_handle", "raw_handle", "cdll", "library")
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


def _annotation_leaks(path: Path, tree: ast.AST) -> list[dict[str, object]]:
    """Finds a native spelling inside a public signature or public attribute.

    Only public names are examined: a private helper is allowed to say exactly
    what it takes, and hiding that would make the implementation less honest
    rather than the surface safer.
    """
    leaks: list[dict[str, object]] = []

    #: Methods Python calls through public syntax even though their names begin
    #: with an underscore.  ``StorageBuffer(device, 64)`` publishes
    #: ``__init__``'s annotations exactly as much as a named method publishes
    #: its own, and ``with buffer:`` publishes ``__enter__``'s, so exempting
    #: every dunder left the constructor -- the one signature a caller always
    #: reads -- outside the gate.
    PUBLIC_DUNDERS = frozenset({
        "__init__", "__new__", "__enter__", "__exit__", "__call__", "__iter__",
        "__next__", "__getitem__", "__setitem__", "__contains__", "__len__",
        "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__",
    })

    def public(name: str) -> bool:
        return not name.startswith("_") or name in PUBLIC_DUNDERS

    def check(where: str, node: ast.AST | None, line: int) -> None:
        if node is None:
            return
        text = ast.unparse(node)
        for spelling in FORBIDDEN_ANNOTATIONS:
            if spelling in text:
                leaks.append({"where": where, "annotation": text, "line": line})
                return

    def walk_function(node, owner: str) -> None:
        if not public(node.name):
            return
        arguments = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
        for argument in arguments:
            check(f"{owner}{node.name}({argument.arg})", argument.annotation, node.lineno)
        check(f"{owner}{node.name}() -> ", node.returns, node.lineno)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_function(node, "")
        elif isinstance(node, ast.ClassDef) and public(node.name):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk_function(item, f"{node.name}.")
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if public(item.target.id):
                        check(f"{node.name}.{item.target.id}", item.annotation, item.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if public(node.target.id):
                check(node.target.id, node.annotation, node.lineno)
    return leaks


def _handle_attribute_leaks(module: object, name: str) -> list[dict[str, str]]:
    """Finds a public attribute whose *name* offers a raw handle."""
    leaks: list[dict[str, str]] = []
    for attribute in _public_names(module):
        value = getattr(module, attribute, None)
        if not isinstance(value, type):
            continue
        for member in dir(value):
            if member.startswith("_"):
                continue
            if member.lower() in FORBIDDEN_PUBLIC_ATTRIBUTES:
                leaks.append({"name": f"{name}.{attribute}.{member}", "kind": "raw handle"})
    return leaks


def audit() -> dict[str, object]:
    ctypes_leaks: list[dict[str, str]] = []
    handle_leaks: list[dict[str, str]] = []
    annotation_leaks: list[dict[str, object]] = []
    native_leaks: list[dict[str, str]] = []
    undocumented: list[str] = []
    signatures: dict[str, str] = {}
    modules = _extension_modules()

    for name in modules:
        module = importlib.import_module(name)
        if not (module.__doc__ or "").strip():
            undocumented.append(name)
        handle_leaks.extend(_handle_attribute_leaks(module, name))
        source = getattr(module, "__file__", None)
        if source:
            path = Path(source)
            for leak in _annotation_leaks(path, ast.parse(path.read_text(encoding="utf-8"))):
                annotation_leaks.append({"module": name, **leak})
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
        "PUBLIC_RAW_HANDLE_LEAK": len(handle_leaks),
        "PUBLIC_NATIVE_ANNOTATION_LEAK": len(annotation_leaks),
    }
    summary["EXTENSION_SURFACE_DIAGNOSTICS"] = (
        summary["PUBLIC_CTYPES_LEAK"] + summary["PRIVATE_NATIVE_LEAK"]
        + summary["UNDOCUMENTED_PUBLIC"] + summary["XNA_NAMESPACE_CONTAMINATION"]
        + summary["PUBLIC_RAW_HANDLE_LEAK"] + summary["PUBLIC_NATIVE_ANNOTATION_LEAK"]
    )
    return {
        "schemaVersion": 1,
        "summary": summary,
        "modules": modules,
        "signatures": signatures,
        "ctypesLeaks": ctypes_leaks,
        "rawHandleLeaks": handle_leaks,
        "nativeAnnotationLeaks": annotation_leaks,
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
    for leak in report["rawHandleLeaks"]:
        print(f"RAW_HANDLE_LEAK {leak['name']}")
    for leak in report["nativeAnnotationLeaks"]:
        print(f"NATIVE_ANNOTATION_LEAK {leak['module']}:{leak['line']} "
              f"{leak['where']}: {leak['annotation']}")
    for item in report["xnaContamination"]:
        print(f"XNA_CONTAMINATION {item['file']}:{item.get('line')} imports {item.get('imports')}")
    return 1 if report["summary"]["EXTENSION_SURFACE_DIAGNOSTICS"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
