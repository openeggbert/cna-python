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
    projected_type_name,
    projected_name,
    raw_member,
    target_types,
)


HEADERS = {
    "Microsoft.Xna.Framework": [
        "from datetime import timedelta",
        "from enum import IntEnum, IntFlag",
        "from typing import Any, BinaryIO, Callable, ClassVar, Final, Iterable, Iterator, MutableSequence, Sequence, TypeVar, overload",
        "from ._language import Event",
        "from .Content import ContentManager",
        "from .Graphics import GraphicsDevice, GraphicsProfile, DepthFormat, SurfaceFormat",
        "",
        "T = TypeVar(\"T\")",
    ],
    "Microsoft.Xna.Framework.Graphics": [
        "from enum import IntEnum, IntFlag",
        "from typing import Any, BinaryIO, Callable, ClassVar, Final, Iterable, Iterator, MutableSequence, Sequence, TypeVar, overload",
        "from .. import Color, Matrix, Rectangle, Vector2, Vector3, Vector4",
        "from .._language import Event",
        "",
        "T = TypeVar(\"T\")",
        "TVertex = TypeVar(\"TVertex\", bound=\"IVertexType\")",
    ],
    "Microsoft.Xna.Framework.Audio": [
        "from datetime import timedelta",
        "from enum import IntEnum",
        "from typing import BinaryIO, ClassVar, Final, MutableSequence, Sequence, overload",
        "from .. import Vector3",
        "from .._language import Event",
    ],
    "Microsoft.Xna.Framework.Input": [
        "from enum import IntEnum, IntFlag",
        "from typing import Any, Final, MutableSequence, Sequence, overload",
        "from .. import PlayerIndex, Vector2",
    ],
    "Microsoft.Xna.Framework.Input.Touch": [
        "from datetime import timedelta",
        "from enum import IntEnum, IntFlag",
        "from typing import Callable, ClassVar, Final, Iterator, MutableSequence, Sequence, overload",
        "from ... import DisplayOrientation, Vector2",
    ],
    "Microsoft.Xna.Framework.GamerServices": [
        "from .. import Game, GameComponent, GameTime",
    ],
    "Microsoft.Xna.Framework.Storage": [
        "from typing import BinaryIO, Callable, Final, overload",
        "from .. import PlayerIndex",
        "from .._language import Event",
    ],
    "Microsoft.Xna.Framework.Content": [
        "from typing import Any, BinaryIO, Callable, Final, Generic, TypeVar, overload",
        "from .._language import Event",
        "",
        "T = TypeVar(\"T\")",
    ],
    "Microsoft.Xna.Framework.Design": [
        "from typing import Mapping",
        "from .. import BoundingBox, BoundingSphere, Color, Matrix, Plane, Point, Quaternion, Ray, Rectangle, Vector2, Vector3, Vector4",
    ],
    "Microsoft.Xna.Framework.Graphics.PackedVector": [
        "from typing import Generic, TypeVar, overload",
        "from ... import Vector2, Vector3, Vector4",
        "",
        "TPacked = TypeVar(\"TPacked\")",
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
                reference_by_name: dict[str, dict], *, name_override: str | None = None) -> list[str]:
    identity = expected["name"]
    target = targets[identity]
    if expected["kind"] == "enum":
        bases = "IntFlag" if expected.get("flags") else "IntEnum"
    elif expected.get("baseType") in targets:
        bases = projected_type_name(expected["baseType"])
    elif (expected.get("baseType") == "System.Exception"
          or rules.get("baseMappings", {}).get(expected.get("baseType")) == "Exception"):
        bases = "Exception"
    else:
        bases = ""
    type_name = name_override or projected_type_name(identity)
    generic_names = tuple(value["name"] for value in expected.get("genericParameters", ()))
    base_items = [bases] if bases else []
    if identity == "Microsoft.Xna.Framework.Graphics.PackedVector.IPackedVector`1":
        base_items.append("IPackedVector")
    typed_packed = next((value for value in expected.get("directInterfaces", ())
                         if identity.startswith("Microsoft.Xna.Framework.Graphics.PackedVector.")
                         and value.startswith("Microsoft.Xna.Framework.Graphics.PackedVector.IPackedVector`1[")), None)
    if typed_packed is not None:
        argument = typed_packed[typed_packed.find("[") + 1:-1]
        base_items.append(f"IPackedVectorOfT[{mapped_type(argument)}]")
    if generic_names:
        base_items.append(f"Generic[{', '.join(generic_names)}]")
    heading = f"class {type_name}" + (f"({', '.join(base_items)})" if base_items else "") + ":"
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
            annotation = rules.get("memberTypeMappings", {}).get(
                f"{identity}.{sample['name']}",
                mapped_type(sample["type"], return_position=True, typevars=generic_names),
            )
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
            elif raw_member(target, name) is not None and members[0]["kind"] == "property":
                sample = members[0]
                annotation = mapped_type(sample["type"], return_position=True)
                lines.extend(("    @property", f"    def {name}(self) -> {annotation}: ..."))
                if sample.get("set"):
                    lines.extend((f"    @{name}.setter", f"    def {name}(self, value: {annotation}) -> None: ..."))
        if interface_name.startswith(("System.Collections.Generic.IEnumerable`1[", "System.Collections.Generic.IEnumerator`1[")) and raw_member(target, "__iter__") is not None:
            argument = interface_name[interface_name.find("[") + 1:-1]
            lines.append(f"    def __iter__(self) -> Iterator[{mapped_type(argument)}]: ...")
    for interface_name in expected.get("directInterfaces", ()):
        if (interface_name.startswith(("System.Collections.Generic.IEnumerable`1[", "System.Collections.Generic.IEnumerator`1["))
                and raw_member(target, "__iter__") is not None
                and not any(line.lstrip().startswith("def __iter__") for line in lines)):
            argument = interface_name[interface_name.find("[") + 1:-1]
            lines.append(f"    def __iter__(self) -> Iterator[{mapped_type(argument)}]: ...")
        if interface_name.startswith("System.Collections.Generic.ICollection`1["):
            argument = interface_name[interface_name.find("[") + 1:-1]
            if raw_member(target, "__iter__") is not None:
                lines.append(f"    def __iter__(self) -> Iterator[{mapped_type(argument)}]: ...")
            if raw_member(target, "__len__") is not None:
                lines.append("    def __len__(self) -> int: ...")
        if interface_name.startswith("System.Collections.Generic.IList`1["):
            argument = interface_name[interface_name.find("[") + 1:-1]
            if raw_member(target, "__setitem__") is not None:
                lines.append(f"    def __setitem__(self, index: int, value: {mapped_type(argument)}) -> None: ...")
            if raw_member(target, "__iter__") is not None:
                lines.append(f"    def __iter__(self) -> Iterator[{mapped_type(argument)}]: ...")
            if raw_member(target, "__len__") is not None:
                lines.append("    def __len__(self) -> int: ...")
    if (identity == "Microsoft.Xna.Framework.Input.Touch.TouchCollection+Enumerator"
            and raw_member(target, "__next__") is not None):
        lines.append("    def __next__(self) -> TouchLocation: ...")
    if "System.IDisposable" in expected.get("directInterfaces", ()):
        if raw_member(target, "__enter__") is not None:
            lines.append(f"    def __enter__(self) -> {type_name}: ...")
        if raw_member(target, "__exit__") is not None:
            lines.append("    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...")
    if expected["kind"] == "struct":
        if raw_member(target, "__copy__") is not None:
            lines.append(f"    def __copy__(self) -> {type_name}: ...")
        if raw_member(target, "__deepcopy__") is not None:
            lines.append(f"    def __deepcopy__(self, memo: object) -> {type_name}: ...")
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
        nested = {value["name"].split("+", 1)[0]: value for value in values
                  if "+" in value["name"] and "." in projected_type_name(value["name"])}
        for expected in values:
            if "+" in expected["name"] and "." in projected_type_name(expected["name"]):
                continue
            rendered = render_type(expected, targets, rules, reference_by_name)
            child = nested.get(expected["name"])
            if child is not None:
                rendered.extend("    " + value for value in render_type(
                    child, targets, rules, reference_by_name,
                    name_override=projected_type_name(child["name"]).rsplit(".", 1)[-1],
                ))
            lines.extend(rendered)
            lines.append("")
        STUB_PATHS[package].write_text("\n".join(lines).rstrip() + "\n")
        print(f"WROTE={STUB_PATHS[package].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
