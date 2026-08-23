#!/usr/bin/env python3
"""Mechanically render runtime-consistent stubs from the pinned XNA contract."""

from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

from verify import (  # noqa: E402
    PACKAGES,
    REFERENCE,
    STUB_PATHS,
    expected_callables,
    mapped_type,
    projected_name,
    raw_member,
    target_types,
)


HEADERS = {
    "Microsoft.Xna.Framework": [
        "from datetime import timedelta",
        "from enum import IntEnum, IntFlag",
        "from typing import Any, BinaryIO, Callable, ClassVar, Final, Iterable, MutableSequence, Sequence, TypeVar, overload",
        "from ._language import Event",
        "from .Content import ContentManager",
        "from .Graphics import GraphicsDevice, GraphicsProfile, DepthFormat, SurfaceFormat",
        "",
        "T = TypeVar(\"T\")",
    ],
    "Microsoft.Xna.Framework.Graphics": [
        "from enum import IntEnum, IntFlag",
        "from typing import Any, BinaryIO, Callable, ClassVar, Final, Iterable, MutableSequence, Sequence, TypeVar, overload",
        "from .. import Color, Matrix, Rectangle, Vector2, Vector3, Vector4",
        "from .._language import Event",
        "",
        "T = TypeVar(\"T\")",
    ],
    "Microsoft.Xna.Framework.Input": [
        "from enum import IntEnum, IntFlag",
        "from typing import Any, Final, MutableSequence, Sequence, overload",
        "from .. import PlayerIndex, Vector2",
    ],
    "Microsoft.Xna.Framework.Content": [
        "from typing import Any, Final, TypeVar, overload",
        "from .._language import Event",
        "",
        "T = TypeVar(\"T\")",
    ],
}


def parameter_text(parameters) -> str:
    result = []
    for parameter in parameters:
        name = (parameter.name or "value") + ("_" if parameter.name == "None" else "")
        result.append(f"{name}: {parameter.annotation}" + (" = ..." if parameter.optional else ""))
    return ", ".join(result)


def render_callable(name: str, signatures) -> list[str]:
    lines: list[str] = []
    multiple = len(signatures) > 1
    for signature in signatures:
        if multiple:
            lines.append("    @overload")
        if signature.shape == "static":
            lines.append("    @staticmethod")
        prefix = "" if signature.shape == "static" else "self" if not signature.parameters else "self, "
        lines.append(
            f"    def {name}({prefix}{parameter_text(signature.parameters)}) -> {signature.return_type}: ..."
        )
    return lines


def render_type(expected: dict, targets: dict[str, type], rules: dict,
                reference_by_name: dict[str, dict]) -> list[str]:
    identity = expected["name"]
    target = targets[identity]
    if expected["kind"] == "enum":
        bases = "IntFlag" if expected.get("flags") else "IntEnum"
    elif expected.get("baseType") in targets:
        bases = expected["baseType"].rsplit(".", 1)[-1]
    elif expected.get("baseType") == "System.Exception":
        bases = "Exception"
    else:
        bases = ""
    heading = f"class {identity.rsplit('.', 1)[-1]}" + (f"({bases})" if bases else "") + ":"
    lines = [heading]
    grouped: dict[str, list[dict]] = {}
    for member in expected["members"]:
        name = projected_name(expected, member, rules)
        if name is not None:
            grouped.setdefault(name, []).append(member)
    emitted = False
    for name, members in grouped.items():
        if raw_member(target, name) is None:
            continue
        sample = members[0]
        if sample["kind"] == "field":
            annotation = "int" if expected["kind"] == "enum" else mapped_type(sample["type"])
            if sample.get("static") and expected["kind"] != "enum":
                annotation = f"Final[{annotation}]" if sample.get("constant") else f"ClassVar[{annotation}]"
            lines.append(f"    {name}: {annotation}")
        elif sample["kind"] == "property" and name == "__getitem__":
            signature = expected_callables(expected, name, [{
                "kind": "method", "name": "Item", "static": False,
                "returnType": sample["type"], "parameters": sample.get("parameters", ()),
                "genericParameters": [],
            }])
            lines.extend(render_callable(name, signature))
        elif sample["kind"] == "property":
            annotation = mapped_type(sample["type"], return_position=True)
            if sample.get("static"):
                wrapper = "ClassVar" if sample.get("set") else "Final"
                lines.append(f"    {name}: {wrapper}[{annotation}]")
            else:
                lines.extend(("    @property", f"    def {name}(self) -> {annotation}: ..."))
                if sample.get("set"):
                    lines.extend((f"    @{name}.setter", f"    def {name}(self, value: {annotation}) -> None: ..."))
        elif sample["kind"] in {"constructor", "method"}:
            lines.extend(render_callable(name, expected_callables(expected, name, members)))
        elif sample["kind"] == "event":
            lines.append(f"    {name}: Final[Event]")
        emitted = True
    for interface_name in expected.get("directInterfaces", ()):
        interface = reference_by_name.get(interface_name.split("[", 1)[0])
        if interface is None:
            continue
        interface_groups: dict[str, list[dict]] = {}
        for member in interface["members"]:
            name = projected_name(interface, member, rules)
            if name is not None and name not in grouped:
                interface_groups.setdefault(name, []).append(member)
        for name, members in interface_groups.items():
            if raw_member(target, name) is not None and members[0]["kind"] in {"constructor", "method"}:
                lines.extend(render_callable(name, expected_callables(interface, name, members)))
    if "System.IDisposable" in expected.get("directInterfaces", ()):
        if raw_member(target, "__enter__") is not None:
            lines.append(f"    def __enter__(self) -> {identity.rsplit('.', 1)[-1]}: ...")
        if raw_member(target, "__exit__") is not None:
            lines.append("    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...")
    if expected["kind"] == "struct":
        if raw_member(target, "__copy__") is not None:
            lines.append(f"    def __copy__(self) -> {identity.rsplit('.', 1)[-1]}: ...")
        if raw_member(target, "__deepcopy__") is not None:
            lines.append(f"    def __deepcopy__(self, memo: object) -> {identity.rsplit('.', 1)[-1]}: ...")
    if len(lines) == 1 and not emitted:
        lines.append("    ...")
    return lines


def main() -> int:
    reference = json.loads(REFERENCE.read_text())
    reference_by_name = {value["name"]: value for value in reference["types"]}
    rules = json.loads((HERE / "mapping-rules.json").read_text())
    targets, _ = target_types()
    by_package: dict[str, list[dict]] = {package: [] for package in PACKAGES}
    for expected in reference["types"]:
        identity = expected["name"]
        if identity not in targets:
            continue
        package = identity.rsplit(".", 1)[0]
        if package in by_package:
            by_package[package].append(expected)
    for package, values in by_package.items():
        lines = [*HEADERS[package], ""]
        for expected in values:
            lines.extend(render_type(expected, targets, rules, reference_by_name))
            lines.append("")
        STUB_PATHS[package].write_text("\n".join(lines).rstrip() + "\n")
        print(f"WROTE={STUB_PATHS[package].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
