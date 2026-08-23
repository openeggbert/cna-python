#!/usr/bin/env python3
"""Reject stub exports/members that do not exist in the runtime projection."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PACKAGES = (
    "Microsoft.Xna.Framework",
    "Microsoft.Xna.Framework.Graphics",
    "Microsoft.Xna.Framework.Input",
    "Microsoft.Xna.Framework.Content",
)


def main() -> int:
    mismatches: list[str] = []
    for package_name in PACKAGES:
        package = importlib.import_module(package_name)
        path = ROOT / "src" / Path(*package_name.split(".")) / "__init__.pyi"
        tree = ast.parse(path.read_text(), filename=str(path))
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for name in package.__all__:
            if isinstance(getattr(package, name), type) and name not in classes:
                mismatches.append(f"{package_name}.{name}: runtime export missing from stub")
        for name, declaration in classes.items():
            runtime = getattr(package, name, None)
            if not isinstance(runtime, type):
                mismatches.append(f"{package_name}.{name}: stub type missing at runtime")
                continue
            for member in declaration.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not hasattr(runtime, member.name):
                    mismatches.append(f"{package_name}.{name}.{member.name}: stub member missing at runtime")
    print(f"STUB_RUNTIME_MISMATCHES={len(mismatches)}")
    for mismatch in mismatches:
        print(mismatch)
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
