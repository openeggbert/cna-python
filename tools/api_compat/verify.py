#!/usr/bin/env python3
"""Strict runtime-structure verifier for the normative XNA-to-Python mapping."""

from __future__ import annotations

import argparse
import ast
import ctypes
from dataclasses import dataclass, field
from enum import Enum, Flag
import importlib
import inspect
import json
from pathlib import Path
import re
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
    "Microsoft.Xna.Framework.Audio",
    "Microsoft.Xna.Framework.Design",
    "Microsoft.Xna.Framework.Graphics",
    "Microsoft.Xna.Framework.Graphics.PackedVector",
    "Microsoft.Xna.Framework.Input",
    "Microsoft.Xna.Framework.Content",
)

STUB_PATHS = {
    package: SRC / Path(*package.split(".")) / "__init__.pyi"
    for package in PACKAGES
}

_RULE_DATA = json.loads(RULES.read_text())
_TYPE_NAMES: dict[str, str] = _RULE_DATA.get("typeNames", {})
_TYPE_MAPPINGS: dict[str, str] = _RULE_DATA.get("typeMappings", {})
_MEMBER_TYPE_MAPPINGS: dict[str, str] = _RULE_DATA.get("memberTypeMappings", {})
_PARAMETER_OMISSIONS: list[dict[str, Any]] = _RULE_DATA.get("parameterOmissions", [])


def projected_type_name(identity: str) -> str:
    return _TYPE_NAMES.get(identity, identity.rsplit(".", 1)[-1].split("`", 1)[0])


def projected_type_identity(package: str, python_name: str) -> str:
    for identity, mapped in _TYPE_NAMES.items():
        if identity.rsplit(".", 1)[0] == package and mapped == python_name:
            return identity
    return f"{package}.{python_name}"


@dataclass(frozen=True)
class StubParameter:
    name: str
    annotation: str
    optional: bool = False


@dataclass(frozen=True)
class StubCallable:
    name: str
    parameters: tuple[StubParameter, ...]
    return_type: str
    shape: str
    overload: bool
    typevars: tuple[str, ...] = ()


@dataclass
class StubAttribute:
    name: str
    annotation: str
    static: bool = False
    readonly: bool = False


@dataclass
class StubProperty:
    name: str
    annotation: str = "Any"
    static: bool = False
    can_get: bool = False
    can_set: bool = False


@dataclass
class StubType:
    name: str
    bases: tuple[str, ...]
    attributes: dict[str, StubAttribute] = field(default_factory=dict)
    properties: dict[str, StubProperty] = field(default_factory=dict)
    callables: dict[str, list[StubCallable]] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpectedParameter:
    name: str
    annotation: str
    optional: bool = False


@dataclass(frozen=True)
class ExpectedCallable:
    parameters: tuple[ExpectedParameter, ...]
    return_type: str
    shape: str
    typevars: tuple[str, ...] = ()


@dataclass(frozen=True)
class TypeVarDeclaration:
    name: str
    bound: str | None
    constraints: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--leak-only", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--inventory", action="store_true")
    return parser.parse_args()


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_decorator_name(node.value)}.{node.attr}"
    return ast.unparse(node)


def _annotation(node: ast.expr | None) -> str:
    if node is None:
        return "Any"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return _annotation(ast.parse(node.value, mode="eval").body)
        except SyntaxError:
            return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        values = sorted({_annotation(node.left), _annotation(node.right)}, key=lambda value: (value == "None", value))
        return " | ".join(values)
    if isinstance(node, ast.Subscript):
        base = _annotation(node.value)
        if isinstance(node.slice, ast.Tuple):
            arguments = tuple(_annotation(value) for value in node.slice.elts)
        else:
            arguments = (_annotation(node.slice),)
        if base == "Optional":
            return " | ".join(sorted({arguments[0], "None"}, key=lambda value: (value == "None", value)))
        aliases = {"List": "list", "Tuple": "tuple", "Sequence": "Sequence",
                   "MutableSequence": "MutableSequence", "ClassVar": "ClassVar", "Final": "Final"}
        return f"{aliases.get(base, base)}[{', '.join(arguments)}]"
    if isinstance(node, ast.Constant) and node.value is None:
        return "None"
    return ast.unparse(node).replace("typing.", "")


def _unwrap_annotation(annotation: str) -> tuple[str, bool, bool]:
    for wrapper, static, readonly in (("Final", True, True), ("ClassVar", True, False)):
        prefix = wrapper + "["
        if annotation.startswith(prefix) and annotation.endswith("]"):
            return annotation[len(prefix):-1], static, readonly
    return annotation, False, False


def _function_parameters(node: ast.FunctionDef, shape: str) -> tuple[StubParameter, ...]:
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    offset = 1 if shape in {"instance", "class"} and positional else 0
    result = [
        StubParameter(argument.arg, _annotation(argument.annotation), default is not None)
        for argument, default in zip(positional[offset:], defaults[offset:])
    ]
    if node.args.vararg is not None:
        result.append(StubParameter("*" + node.args.vararg.arg, _annotation(node.args.vararg.annotation)))
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        result.append(StubParameter(argument.arg, _annotation(argument.annotation), default is not None))
    return tuple(result)


def _typevars_in(callable_value: StubCallable, declared: dict[str, TypeVarDeclaration]) -> tuple[str, ...]:
    text = " ".join([callable_value.return_type, *(value.annotation for value in callable_value.parameters)])
    return tuple(name for name in declared if re.search(rf"\b{re.escape(name)}\b", text))


def parse_stubs() -> tuple[dict[str, StubType], dict[str, TypeVarDeclaration]]:
    result: dict[str, StubType] = {}
    typevars: dict[str, TypeVarDeclaration] = {}
    for package, path in STUB_PATHS.items():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
            value = node.value
            if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
                continue
            if _decorator_name(value.func).rsplit(".", 1)[-1] != "TypeVar":
                continue
            positional = tuple(_annotation(argument) for argument in value.args[1:])
            keywords = {keyword.arg: _annotation(keyword.value) for keyword in value.keywords if keyword.arg}
            typevars[target.id] = TypeVarDeclaration(target.id, keywords.get("bound"), positional)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
                continue
            declaration = StubType(node.name, tuple(_annotation(base) for base in node.bases))
            class_typevars: set[str] = set()
            for base in declaration.bases:
                if base.startswith("Generic[") and base.endswith("]"):
                    class_typevars.update(
                        value.strip() for value in base[len("Generic["):-1].split(",")
                    )
            for member in node.body:
                if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                    annotation, static, readonly = _unwrap_annotation(_annotation(member.annotation))
                    declaration.attributes[member.target.id] = StubAttribute(
                        member.target.id, annotation, static, readonly
                    )
                    continue
                if not isinstance(member, ast.FunctionDef):
                    continue
                decorators = tuple(_decorator_name(value) for value in member.decorator_list)
                setter = next((value[:-7] for value in decorators if value.endswith(".setter")), None)
                if "property" in decorators or setter is not None:
                    name = setter or member.name
                    value = declaration.properties.setdefault(name, StubProperty(name))
                    if setter is None:
                        value.can_get = True
                        value.annotation = _annotation(member.returns)
                    else:
                        value.can_set = True
                        parameters = _function_parameters(member, "instance")
                        if parameters:
                            value.annotation = parameters[-1].annotation
                    continue
                shape = "static" if "staticmethod" in decorators else "class" if "classmethod" in decorators else "instance"
                callable_value = StubCallable(
                    member.name,
                    _function_parameters(member, shape),
                    _annotation(member.returns),
                    shape,
                    "overload" in decorators,
                )
                callable_value = StubCallable(
                    callable_value.name, callable_value.parameters, callable_value.return_type,
                    callable_value.shape, callable_value.overload,
                    tuple(
                        value for value in _typevars_in(callable_value, typevars)
                        if value not in class_typevars
                    ),
                )
                declaration.callables.setdefault(member.name, []).append(callable_value)
            result[projected_type_identity(package, node.name)] = declaration
    return result, typevars


_PRIMITIVES = {
    "System.Void": "None", "System.Boolean": "bool", "System.Byte": "int",
    "System.SByte": "int", "System.Int16": "int", "System.UInt16": "int",
    "System.Int32": "int", "System.UInt32": "int", "System.Int64": "int",
    "System.UInt64": "int", "System.Single": "float", "System.Double": "float",
    "System.String": "str", "System.Text.StringBuilder": "str", "System.Char": "str",
    "System.Object": "object", "System.TimeSpan": "timedelta",
    "System.IServiceProvider": "object", "System.Type": "type", "System.EventArgs": "object",
    "System.Exception": "Exception", "System.IO.Stream": "BinaryIO",
}


def _split_generic(value: str) -> tuple[str, list[str]] | None:
    marker = value.find("[")
    if marker < 0 or not value.endswith("]"):
        return None
    owner = value[:marker]
    arguments: list[str] = []
    start, depth = marker + 1, 0
    for index in range(start, len(value) - 1):
        character = value[index]
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
        elif character == "," and depth == 0:
            arguments.append(value[start:index])
            start = index + 1
    arguments.append(value[start:-1])
    return owner, arguments


def mapped_type(value: str | None, *, parameter_name: str | None = None,
                return_position: bool = False, typevars: tuple[str, ...] = ()) -> str:
    if value is None:
        return "None"
    if value.endswith("&"):
        value = value[:-1]
    if value.endswith("[]"):
        element = mapped_type(value[:-2], typevars=typevars)
        if return_position:
            return f"list[{element}]"
        if parameter_name in {"destinationArray", "corners", "data"}:
            return f"MutableSequence[{element}]"
        return f"Sequence[{element}]"
    if value.startswith("!!"):
        index = int(value[2:])
        return typevars[index] if index < len(typevars) else f"T{index}"
    if value.startswith("!"):
        index = int(value[1:])
        return typevars[index] if index < len(typevars) else "T" if index == 0 else f"T{index}"
    if value in _TYPE_MAPPINGS:
        return _TYPE_MAPPINGS[value]
    if value in _PRIMITIVES:
        return _PRIMITIVES[value]
    generic = _split_generic(value)
    if generic is not None:
        owner, arguments = generic
        mapped = [mapped_type(argument, typevars=typevars) for argument in arguments]
        if owner.startswith("System.Nullable`1"):
            return f"{mapped[0]} | None"
        if owner.startswith("System.Action`1"):
            return f"Callable[[{mapped[0]}], None]"
        if owner.startswith("System.Collections.Generic.IEnumerable`1"):
            return f"Iterable[{mapped[0]}]"
        if owner.startswith("System.Collections.Generic.IEnumerator`1"):
            return f"Iterator[{mapped[0]}]"
        if owner.startswith("System.Collections.ObjectModel.ReadOnlyCollection`1"):
            return f"tuple[{mapped[0]}, ...]"
        if owner.startswith("System.Collections.Generic.IList`1"):
            return f"MutableSequence[{mapped[0]}]"
        if owner.startswith("System.Collections.Generic.List`1"):
            return f"list[{mapped[0]}]"
        return f"{projected_type_name(owner)}[{', '.join(mapped)}]"
    return projected_type_name(value).replace("+", ".")


def _projected_generic_name(value: dict[str, Any]) -> str:
    constraints = value.get("typeConstraints", ())
    if constraints == ["Microsoft.Xna.Framework.Graphics.IVertexType"]:
        return value["name"] + "Vertex"
    return value["name"]


def expected_callable(member: dict[str, Any], projected: str,
                      owner_identity: str | None = None) -> ExpectedCallable:
    generic_names = tuple(_projected_generic_name(value)
                          for value in member.get("genericParameters", ()))
    parameters = tuple(
        ExpectedParameter(
            parameter["name"] or "value",
            _MEMBER_TYPE_MAPPINGS.get(
                f"{owner_identity}.{member['name']}.{parameter['name'] or 'value'}",
                mapped_type(parameter["type"], parameter_name=parameter["name"] or "value",
                            typevars=generic_names),
            ),
            bool(parameter.get("optional")),
        )
        for parameter in member.get("parameters", ())
        if not parameter.get("out") and not _parameter_is_omitted(
            owner_identity, member["name"], parameter["name"] or "value"
        )
    )
    outputs = [
        mapped_type(parameter["type"], typevars=generic_names)
        for parameter in member.get("parameters", ()) if parameter.get("out")
    ]
    if member["kind"] == "constructor":
        return_type = "None"
        shape = "instance"
    else:
        primary = mapped_type(member.get("returnType"), return_position=True, typevars=generic_names)
        values = ([] if primary == "None" else [primary]) + outputs
        return_type = values[0] if len(values) == 1 else f"tuple[{', '.join(values)}]" if values else "None"
        if member["name"].startswith("op_"):
            # The first CLR operator operand is Python's bound ``self``.
            parameters = parameters[1:]
            shape = "instance"
        else:
            shape = "static" if member.get("static") else "instance"
    return ExpectedCallable(parameters, return_type, shape, generic_names)


def _parameter_is_omitted(owner: str | None, member: str, parameter: str) -> bool:
    if owner is None:
        return False
    for rule in _PARAMETER_OMISSIONS:
        if rule.get("owner") not in (None, owner):
            continue
        if "ownerPrefix" in rule and not owner.startswith(rule["ownerPrefix"]):
            continue
        if rule.get("member") not in (None, member):
            continue
        if parameter in rule.get("parameters", ()):
            return True
    return False


def expected_callables(owner: dict[str, Any], name: str,
                       members: list[dict[str, Any]]) -> list[ExpectedCallable]:
    result: list[ExpectedCallable] = []
    for member in members:
        value = expected_callable(member, name, owner["name"])
        if value not in result:
            result.append(value)
    if members[0]["kind"] == "constructor" and owner["kind"] == "struct":
        default = ExpectedCallable((), "None", "instance")
        if default not in result:
            result.insert(0, default)
    # Disposable derived types retain the inherited public Dispose() route even
    # when their only newly declared CLR member is the protected bool override.
    if name == "Dispose":
        public_dispose = ExpectedCallable((), "None", "instance")
        if public_dispose not in result:
            result.append(public_dispose)
    return result


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
            identity = projected_type_identity(package_name, name)
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
        elif inspect.isfunction(raw) or inspect.ismethoddescriptor(raw):
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
        return True, True, getattr(raw, "fset", None) is not None
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


def _runtime_shape(raw: object) -> str:
    if isinstance(raw, staticmethod):
        return "static"
    if isinstance(raw, classmethod):
        return "class"
    if isinstance(raw, property):
        return "property"
    if raw.__class__.__name__ in {"classproperty", "staticproperty", "_ColorProperty"}:
        return "static-property"
    if raw.__class__.__name__ == "Event":
        return "event"
    if raw.__class__.__name__ == "_dualmethod":
        return "dual"
    if callable(raw) or inspect.ismethoddescriptor(raw):
        return "instance"
    return "attribute"


def _parameter_detail(values: tuple[ExpectedParameter, ...] | tuple[StubParameter, ...]) -> str:
    return ", ".join(f"{value.name}: {value.annotation}{' = ...' if value.optional else ''}" for value in values)


def _pair_callables(expected: list[ExpectedCallable], actual: list[StubCallable]) -> list[tuple[ExpectedCallable, StubCallable]]:
    remaining = list(actual)
    pairs: list[tuple[ExpectedCallable, StubCallable]] = []
    for wanted in expected:
        candidate = next((value for value in remaining
                          if len(value.parameters) == len(wanted.parameters)
                          and tuple(item.annotation for item in value.parameters)
                          == tuple(item.annotation for item in wanted.parameters)), None)
        if candidate is None:
            candidate = next((value for value in remaining if len(value.parameters) == len(wanted.parameters)), None)
        if candidate is None:
            continue
        remaining.remove(candidate)
        pairs.append((wanted, candidate))
    return pairs


def compare_callable_contract(identity: str, name: str, expected: list[ExpectedCallable],
                              actual: list[StubCallable], raw: object,
                              typevars: dict[str, TypeVarDeclaration],
                              diagnostics: list[dict[str, str]]) -> None:
    declarations = [value for value in actual if value.overload]
    if not declarations:
        declarations = actual
    if len(declarations) != len(expected):
        add(diagnostics, "OVERLOAD_MAPPING_MISMATCH", identity,
            f"{name}: stub declares {len(declarations)} projected signatures, expected {len(expected)}")
    runtime_shape = _runtime_shape(raw)
    expected_shapes = {value.shape for value in expected}
    actual_shapes = {value.shape for value in declarations}
    if actual_shapes != expected_shapes:
        add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity,
            f"{name}: stub shapes {sorted(actual_shapes)}, expected {sorted(expected_shapes)}")
    if runtime_shape != "dual" and runtime_shape not in actual_shapes:
        add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity,
            f"{name}: runtime shape {runtime_shape} diverges from stub shapes {sorted(actual_shapes)}")
    for wanted, found in _pair_callables(expected, declarations):
        wanted_types = tuple(value.annotation for value in wanted.parameters)
        found_types = tuple(value.annotation for value in found.parameters)
        if wanted_types != found_types:
            add(diagnostics, "PARAMETER_MAPPING_MISMATCH", identity,
                f"{name}({_parameter_detail(found.parameters)}): expected parameter types {wanted_types}")
        # Operator spelling is a Python-language rule; ordinary PascalCase names remain stable.
        if not name.startswith("__"):
            wanted_names = tuple(value.name for value in wanted.parameters)
            found_names = tuple(value.name for value in found.parameters)
            if wanted_names != found_names:
                add(diagnostics, "PARAMETER_MAPPING_MISMATCH", identity,
                    f"{name}: parameter names {found_names}, expected {wanted_names}")
        wanted_optional = tuple(value.optional for value in wanted.parameters)
        found_optional = tuple(value.optional for value in found.parameters)
        if wanted_optional != found_optional:
            add(diagnostics, "PARAMETER_MAPPING_MISMATCH", identity,
                f"{name}: optional parameters {found_optional}, expected {wanted_optional}")
        if wanted.return_type != found.return_type:
            add(diagnostics, "RETURN_MAPPING_MISMATCH", identity,
                f"{name}({_parameter_detail(found.parameters)}): returns {found.return_type}, expected {wanted.return_type}")
        if wanted.typevars != found.typevars:
            add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                f"{name}: TypeVars {found.typevars}, expected {wanted.typevars}")
        for generic in wanted.typevars:
            declaration = typevars.get(generic)
            if declaration is None:
                add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                    f"{name}: TypeVar {generic} is not declared")


def compare_generic_bounds(identity: str, name: str, members: list[dict[str, Any]],
                           typevars: dict[str, TypeVarDeclaration],
                           diagnostics: list[dict[str, str]]) -> None:
    measured: set[tuple[str, str | None]] = set()
    for member in members:
        for parameter in member.get("genericParameters", ()):
            constraints = parameter.get("typeConstraints", ())
            expected_bound = mapped_type(constraints[0]) if len(constraints) == 1 else None
            projected_name = _projected_generic_name(parameter)
            key = (projected_name, expected_bound)
            if key in measured:
                continue
            measured.add(key)
            declaration = typevars.get(projected_name)
            if declaration is not None and declaration.bound != expected_bound:
                add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                    f"{name}: TypeVar {parameter['name']} bound {declaration.bound}, expected {expected_bound}")
            if len(constraints) > 1:
                add(diagnostics, "UNMEASURED_STRUCTURAL_CATEGORY", identity,
                    f"{name}: multiple CLR generic type constraints cannot be projected without a mapping rule")


def compare_language_contract(identity: str, expected: dict[str, Any], target: type,
                              stub: StubType, stubs: dict[str, StubType],
                              diagnostics: list[dict[str, str]]) -> None:
    if expected["kind"] == "struct":
        required = ("__copy__", "__deepcopy__")
        missing_runtime = [name for name in required if raw_member(target, name) is None]
        missing_stub = [name for name in required if not _stub_has_member(stub, name, stubs)]
        if missing_runtime or missing_stub:
            add(diagnostics, "LANGUAGE_MAPPING_MISMATCH", identity,
                f"value-copy protocol: runtime missing {missing_runtime}, stub missing {missing_stub}")


def _stub_has_member(stub: StubType, name: str, stubs: dict[str, StubType], seen: set[str] | None = None) -> bool:
    if name in stub.callables or name in stub.properties or name in stub.attributes:
        return True
    seen = set() if seen is None else seen
    if stub.name in seen:
        return False
    seen.add(stub.name)
    for base in stub.bases:
        inherited = next((value for value in stubs.values() if value.name == base), None)
        if inherited is not None and _stub_has_member(inherited, name, stubs, seen):
            return True
    return False


def compare_interface_contract(identity: str, expected: dict[str, Any], target: type,
                               stub: StubType, stubs: dict[str, StubType],
                               reference_by_name: dict[str, dict[str, Any]],
                               rules: dict[str, Any], diagnostics: list[dict[str, str]]) -> None:
    for interface in expected.get("directInterfaces", ()):
        base = interface.split("[", 1)[0]
        if base.startswith("System.IEquatable`1"):
            required = ("Equals", "__eq__")
        elif base == "System.IDisposable":
            required = ("Dispose", "__enter__", "__exit__")
        elif base == "System.IServiceProvider":
            required = ("GetService",)
        elif base.startswith("System.Collections.Generic.IEnumerable`1"):
            required = ("GetEnumerator", "__iter__")
        elif base.startswith("System.Collections.Generic.ICollection`1"):
            required = ("Count", "IsReadOnly", "Add", "Clear", "Contains", "CopyTo",
                        "Remove", "GetEnumerator", "__iter__", "__len__")
        elif base.startswith("System.IComparable`1"):
            required = ("CompareTo",)
        elif base.startswith("System.Collections.Generic.IEnumerator`1"):
            required = ("Current", "MoveNext", "Dispose", "__iter__")
        elif base == "Microsoft.Xna.Framework.Graphics.PackedVector.IPackedVector`1":
            required = ("PackedValue",)
            generic = _split_generic(interface)
            if (generic is not None
                    and identity.startswith("Microsoft.Xna.Framework.Graphics.PackedVector.")):
                _, arguments = generic
                wanted_base = f"IPackedVectorOfT[{mapped_type(arguments[0])}]"
                if wanted_base not in stub.bases:
                    add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                        f"typed packed interface stub base {stub.bases}, expected {wanted_base}")
                if not any(value.__name__ == "IPackedVectorOfT" for value in target.__mro__):
                    add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                        "runtime does not implement IPackedVectorOfT")
        elif base == "Microsoft.Xna.Framework.Graphics.IGraphicsResource":
            required = ("GraphicsDevice",)
        elif base == "Microsoft.Xna.Framework.Graphics.IDynamicGraphicsResource":
            required = ("IsContentLost", "ContentLost")
        elif base in reference_by_name:
            required = tuple(dict.fromkeys(
                name for member in reference_by_name[base]["members"]
                if (name := projected_name(reference_by_name[base], member, rules)) is not None
            ))
        else:
            add(diagnostics, "UNMEASURED_STRUCTURAL_CATEGORY", identity,
                f"interface projection is not defined for {interface}")
            continue
        missing_runtime = [name for name in required if raw_member(target, name) is None]
        missing_stub = [name for name in required if not _stub_has_member(stub, name, stubs)]
        if missing_runtime or missing_stub:
            add(diagnostics, "INTERFACE_MAPPING_MISMATCH", identity,
                f"{interface}: runtime missing {missing_runtime}, stub missing {missing_stub}")


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
    if expected.get("fieldTypes") != target.get("fieldTypes") and "fieldTypes" in expected:
        categories.add("FIELD_MAPPING_MISMATCH")
    if expected.get("parameterTypes") != target.get("parameterTypes") and "parameterTypes" in expected:
        categories.add("PARAMETER_MAPPING_MISMATCH")
    if expected.get("returnTypes") != target.get("returnTypes") and "returnTypes" in expected:
        categories.add("RETURN_MAPPING_MISMATCH")
    if expected.get("interfaces") != target.get("interfaces") and "interfaces" in expected:
        categories.add("INTERFACE_MAPPING_MISMATCH")
    if expected.get("typeVars") != target.get("typeVars") and "typeVars" in expected:
        categories.add("GENERIC_MAPPING_MISMATCH")
    if expected.get("genericBounds") != target.get("genericBounds") and "genericBounds" in expected:
        categories.add("GENERIC_MAPPING_MISMATCH")
    if expected.get("nullable") != target.get("nullable") and "nullable" in expected:
        categories.add("PARAMETER_MAPPING_MISMATCH")
    if expected.get("refOut") != target.get("refOut") and "refOut" in expected:
        categories.add("RETURN_MAPPING_MISMATCH")
    if expected.get("runtimeStub") != target.get("runtimeStub") and "runtimeStub" in expected:
        categories.add("METHOD_SIGNATURE_MAPPING_MISMATCH")
    return categories


def verify() -> dict[str, Any]:
    reference = json.loads(REFERENCE.read_text())
    profile = json.loads(PROFILE.read_text())
    rules = json.loads(RULES.read_text())
    targets, diagnostics = target_types()
    stubs, typevars = parse_stubs()
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
        stub = stubs.get(identity)
        if stub is None:
            add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity,
                "runtime type is absent from its package stub")
            stub = StubType(identity.rsplit(".", 1)[-1], ())
        expected_kind = expected["kind"]
        actual_kind = target_kind(target)
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
            stub_base = projected_type_name(base_name)
            if stub_base not in stub.bases:
                add(diagnostics, "BASE_MAPPING_MISMATCH", identity,
                    f"stub bases {stub.bases}, expected mapped base {stub_base}")
        elif base_name in rules.get("baseMappings", {}):
            base_mapping = rules["baseMappings"][base_name]
            if base_mapping.startswith("composition:"):
                implementation_base = base_mapping.split(":", 1)[1]
                if not any(value.__name__ == implementation_base for value in target.__bases__):
                    add(diagnostics, "BASE_MAPPING_MISMATCH", identity,
                        f"{base_name} must use the measured {base_mapping} relation")
                if implementation_base in stub.bases:
                    add(diagnostics, "INTERNAL_TYPE_LEAK", identity,
                        f"stub exposes composition base {implementation_base}")
            elif base_mapping == "object":
                if object not in target.__bases__ or stub.bases:
                    add(diagnostics, "BASE_MAPPING_MISMATCH", identity,
                        f"{base_name} must map to an implicit Python object base")
            elif base_mapping == "Exception":
                if not issubclass(target, Exception) or "Exception" not in stub.bases:
                    add(diagnostics, "BASE_MAPPING_MISMATCH", identity,
                        f"{base_name} must map to Python Exception")
            else:
                add(diagnostics, "UNMEASURED_STRUCTURAL_CATEGORY", identity,
                    f"unknown formal base mapping {base_name} -> {base_mapping}")

        generic_parameters = tuple(
            _projected_generic_name(value) for value in expected.get("genericParameters", ())
        )
        if generic_parameters:
            wanted_generic = f"Generic[{', '.join(generic_parameters)}]"
            runtime_generic = tuple(
                getattr(value, "__name__", str(value))
                for value in getattr(target, "__parameters__", ())
            )
            if runtime_generic != generic_parameters or wanted_generic not in stub.bases:
                add(diagnostics, "GENERIC_MAPPING_MISMATCH", identity,
                    f"class generics runtime={runtime_generic}, stub bases={stub.bases}, "
                    f"expected {generic_parameters}")

        grouped: dict[str, list[dict[str, Any]]] = {}
        expected_public_names: set[str] = set()
        for member in expected["members"]:
            name = projected_name(expected, member, rules)
            if name is None:
                continue
            expected_public_names.add(name)
            grouped.setdefault(name, []).append(member)
        for interface_name in expected.get("directInterfaces", ()):
            interface = reference_by_name.get(interface_name.split("[", 1)[0])
            if interface is None:
                continue
            for member in interface["members"]:
                name = projected_name(interface, member, rules)
                if name is not None:
                    expected_public_names.add(name)
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
                declaration = stub.attributes.get(name)
                if declaration is None:
                    add(diagnostics, "FIELD_MAPPING_MISMATCH", identity,
                        f"{name}: runtime enum value is missing from stub")
                elif declaration.annotation != "int":
                    add(diagnostics, "FIELD_MAPPING_MISMATCH", identity,
                        f"{name}: stub type {declaration.annotation}, expected int")
            elif sample["kind"] == "field":
                declaration = stub.attributes.get(name)
                expected_type = mapped_type(sample["type"])
                if declaration is None:
                    add(diagnostics, "FIELD_MAPPING_MISMATCH", identity,
                        f"{name}: runtime field is missing from stub")
                elif declaration.annotation != expected_type:
                    add(diagnostics, "FIELD_MAPPING_MISMATCH", identity,
                        f"{name}: stub type {declaration.annotation}, expected {expected_type}")
                elif bool(sample.get("static")) != declaration.static:
                    add(diagnostics, "FIELD_MAPPING_MISMATCH", identity,
                        f"{name}: stub static={declaration.static}, expected static={sample.get('static')}")
            elif sample["kind"] == "property":
                if name == "__getitem__" and callable(getattr(target, name, None)):
                    shaped, can_get, can_set = True, True, raw_member(target, "__setitem__") is not None
                else:
                    shaped, can_get, can_set = is_property_shape(raw, bool(sample.get("static")))
                if not shaped or can_get != bool(sample.get("get")) or can_set != bool(sample.get("set")):
                    add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                        f"{name}: expected get={sample.get('get')} set={sample.get('set')} static={sample.get('static')}")
                expected_type = _MEMBER_TYPE_MAPPINGS.get(
                    f"{identity}.{sample['name']}",
                    mapped_type(sample["type"], return_position=True,
                                typevars=generic_parameters),
                )
                if name == "__getitem__":
                    expected_indexers = [expected_callable({
                        "kind": "method", "name": "Item", "static": False,
                        "returnType": sample["type"], "parameters": sample.get("parameters", ()),
                        "genericParameters": [],
                    }, name, identity)]
                    declarations = stub.callables.get(name, [])
                    if not declarations:
                        add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                            "indexer getter is absent from stub")
                    else:
                        compare_callable_contract(identity, name, expected_indexers, declarations,
                                                  raw, typevars, diagnostics)
                    if sample.get("set") and raw_member(target, "__setitem__") is None:
                        add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                            "writable indexer has no runtime __setitem__")
                elif sample.get("static"):
                    declaration = stub.attributes.get(name)
                    expected_readonly = not bool(sample.get("set"))
                    if declaration is None or not declaration.static or declaration.readonly != expected_readonly:
                        add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                            f"{name}: static property readonly={getattr(declaration, 'readonly', None)}, expected {expected_readonly}")
                    elif declaration.annotation != expected_type:
                        add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                            f"{name}: stub type {declaration.annotation}, expected {expected_type}")
                else:
                    declaration = stub.properties.get(name)
                    if declaration is None:
                        add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                            f"{name}: instance property is absent from stub")
                    else:
                        if (declaration.can_get, declaration.can_set) != (bool(sample.get("get")), bool(sample.get("set"))):
                            add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                                f"{name}: stub get/set={(declaration.can_get, declaration.can_set)}, expected {(sample.get('get'), sample.get('set'))}")
                        if declaration.annotation != expected_type:
                            add(diagnostics, "PROPERTY_MAPPING_MISMATCH", identity,
                                f"{name}: stub type {declaration.annotation}, expected {expected_type}")
            elif sample["kind"] in ("method", "constructor"):
                if not callable(getattr(target, name, None)):
                    add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity, f"{name} is not callable")
                projected = expected_callables(expected, name, members)
                declarations = stub.callables.get(name, [])
                if not declarations:
                    add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity,
                        f"{name}: runtime callable is absent from stub")
                else:
                    compare_callable_contract(identity, name, projected, declarations,
                                              raw, typevars, diagnostics)
                    compare_generic_bounds(identity, name, members, typevars, diagnostics)
                expected_arities = {len(value.parameters) for value in projected}
                actual_arities = accepted_arities(target, name, raw)
                if actual_arities is None:
                    add(diagnostics, "OVERLOAD_MAPPING_MISMATCH", identity,
                        f"{name}: runtime dispatcher has no exact __xna_arities__ metadata")
                elif actual_arities != expected_arities:
                    add(diagnostics, "OVERLOAD_MAPPING_MISMATCH", identity,
                        f"{name}: expected arities {sorted(expected_arities)}, got {sorted(actual_arities)}")
            elif sample["kind"] == "event":
                if raw.__class__.__name__ != "Event":
                    add(diagnostics, "EVENT_MAPPING_MISMATCH", identity, f"{name} is not the mapped Event descriptor")
                declaration = stub.attributes.get(name)
                if declaration is None or declaration.annotation != "Event":
                    add(diagnostics, "EVENT_MAPPING_MISMATCH", identity,
                        f"{name}: runtime event is not declared as Event in stub")

        compare_interface_contract(identity, expected, target, stub, stubs,
                                   reference_by_name, rules, diagnostics)
        compare_language_contract(identity, expected, target, stub, stubs, diagnostics)

        declared_names = set(stub.attributes) | set(stub.properties) | set(stub.callables)
        for name in sorted(declared_names):
            if name.startswith("_"):
                continue
            if raw_member(target, name) is None:
                add(diagnostics, "METHOD_SIGNATURE_MAPPING_MISMATCH", identity,
                    f"stub declares {name}, but runtime lacks it")

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
