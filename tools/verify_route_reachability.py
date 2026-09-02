#!/usr/bin/env python3
"""Proves every imported native route is actually called by production code.

A bound route that nothing calls is dead native surface: it passes the ABI audit,
it passes the prototype gate, and it does nothing. This gate closes the last link
in the chain -- canonical declaration, ctypes manifest, real call site, consumer.

Text search is not the authority here. A route named in a comment, a docstring, a
test or its own manifest entry must not count as a caller, and grep cannot tell
those apart from a call. The analysis walks the Python AST of the shipped package
and records only attribute accesses that are genuinely uses of a library route:
``library.cna_x(...)``, ``getattr(library, "cna_x")``, and the operation-name
string a route is invoked through where the codebase builds the name dynamically.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
sys.path.insert(0, str(SOURCE))

from _cna_native.loader import FUNCTION_MANIFEST  # noqa: E402

#: The manifest modules declare the routes. A bare route name in them is data, not
#: a call, so only genuine attribute or getattr uses count there.
DECLARATION_MODULES = {
    SOURCE / "_cna_native/loader.py",
    SOURCE / "_cna_native/media_manifest.py",
    SOURCE / "_cna_native/cnb_manifest.py",
}

#: Underscores a name-template's constant head must contain before it is specific
#: enough to stand as evidence. ``cna_effect_annotation_get_value_`` qualifies;
#: ``cna_`` does not.
MINIMUM_TEMPLATE_SEGMENTS = 3

#: Routes proven to have executed, recorded by CNA_PYTHON_ROUTE_LOG during a real
#: run. This is stronger than any static claim: the route was called.
OBSERVED_PATH = ROOT / "tools/route-reachability-observed.txt"


class _CallSites(ast.NodeVisitor):
    """Collects route names this module genuinely uses."""

    def __init__(self, path: Path, *, literals_count: bool = True) -> None:
        self.path = path
        self.literals_count = literals_count
        self.used: dict[str, list[int]] = {}
        self.templates: dict[str, list[int]] = {}

    def _record(self, name: str, line: int) -> None:
        if name.startswith("cna_"):
            self.used.setdefault(name, []).append(line)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # library.cna_x, self.library.cna_x, get_library().cna_x, raw._cdll.cna_x
        self._record(node.attr, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # getattr(library, "cna_x") and library.check(result, "cna_x")
        if isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                if isinstance(node.args[1].value, str):
                    self._record(node.args[1].value, node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # A route invoked through a name held in a variable is still a call, and the
        # codebase spells that name as a literal at the call site.  Docstrings are
        # excluded so prose cannot satisfy the gate, and in the manifest modules a
        # bare name is the declaration itself rather than a use of it.
        if self.literals_count and isinstance(node.value, str) and node.value.startswith("cna_"):
            self._record(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # A family of routes reached through one f-string, such as
        # f"cna_effect_annotation_get_value_{suffix}".  The constant head is the
        # part the analysis can prove; it is recorded as a template so a route in
        # that family counts as reached and one outside it still does not.
        first = node.values[0] if node.values else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            head = first.value
            # A head of "cna_" alone would match almost every route and prove
            # nothing, so a template must name a real family before it counts.
            if (head.startswith("cna_") and len(node.values) > 1
                    and head.count("_") >= MINIMUM_TEMPLATE_SEGMENTS):
                self.templates.setdefault(head, []).append(node.lineno)
        self.generic_visit(node)


class _TemplateResolver(ast.NodeVisitor):
    """Resolves route names that are built from constants elsewhere in the module.

    Two patterns in this codebase build a route name rather than writing it out,
    and both are fully determined by constants the analysis can follow:

    * a property factory whose body contains ``f"cna_{prefix}_get_{name}"`` and
      whose callers pass ``prefix`` and ``name`` as literals;
    * a class that sets a literal ``_stem`` and whose methods build
      ``f"cna_{self._stem}_get_at"``.

    Substituting them is call-graph analysis, not pattern matching on text: an
    argument that is not a literal resolves nothing.
    """

    def __init__(self) -> None:
        self.resolved: dict[str, int] = {}
        self._functions: dict[str, tuple[list[str], list[ast.JoinedStr]]] = {}
        self._stems: list[str] = []

    @staticmethod
    def _templates(node: ast.AST) -> list[ast.JoinedStr]:
        return [item for item in ast.walk(node)
                if isinstance(item, ast.JoinedStr) and item.values
                and isinstance(item.values[0], ast.Constant)
                and isinstance(item.values[0].value, str)
                and item.values[0].value.startswith("cna_")]

    def collect(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                parameters = [argument.arg for argument in node.args.args]
                templates = self._templates(node)
                if parameters and templates:
                    self._functions[node.name] = (parameters, templates)
            if isinstance(node, ast.For):
                # for _collection, _stem, _item in ((A, "album", ...), ...)
                names = [element.id for element in getattr(node.target, "elts", [])
                         if isinstance(element, ast.Name)]
                if "_stem" in names and isinstance(node.iter, (ast.Tuple, ast.List)):
                    position = names.index("_stem")
                    for row in node.iter.elts:
                        if isinstance(row, (ast.Tuple, ast.List)) and len(row.elts) > position:
                            element = row.elts[position]
                            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                                self._stems.append(element.value)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_stem":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            self._stems.append(node.value.value)
                    if (isinstance(target, ast.Tuple)
                            and isinstance(node.value, ast.Tuple)
                            and len(target.elts) == len(node.value.elts)):
                        for name_node, value_node in zip(target.elts, node.value.elts):
                            if (isinstance(name_node, ast.Name) and name_node.id == "_stem"
                                    and isinstance(value_node, ast.Constant)
                                    and isinstance(value_node.value, str)):
                                self._stems.append(value_node.value)

    @staticmethod
    def _render(template: ast.JoinedStr, bindings: dict[str, str]) -> str | None:
        parts: list[str] = []
        for value in template.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
                bound = bindings.get(value.value.id)
                if bound is None:
                    return None
                parts.append(bound)
            elif (isinstance(value, ast.FormattedValue)
                  and isinstance(value.value, ast.Attribute)
                  and value.value.attr == "_stem"):  # noqa: SIM114
                bound = bindings.get("_stem")
                if bound is None:
                    return None
                parts.append(bound)
            else:
                return None
        return "".join(parts)

    def resolve(self, tree: ast.AST) -> None:
        # Stems apply to every stem-shaped template in the package.
        for _parameters, templates in list(self._functions.values()):
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            entry = self._functions.get(node.func.id)
            if entry is None:
                continue
            parameters, templates = entry
            bindings: dict[str, str] = {}
            for parameter, argument in zip(parameters, node.args):
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    bindings[parameter] = argument.value
            for keyword in node.keywords:
                if (keyword.arg and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)):
                    bindings[keyword.arg] = keyword.value.value
            for template in templates:
                rendered = self._render(template, bindings)
                if rendered:
                    self.resolved[rendered] = node.lineno

    def resolve_stems(self, templates: list[ast.JoinedStr]) -> None:
        for stem in self._stems:
            for template in templates:
                rendered = self._render(template, {"_stem": stem})
                if rendered:
                    self.resolved.setdefault(rendered, 0)


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]


def analyse() -> dict[str, object]:
    bound = [entry[0] for entry in FUNCTION_MANIFEST]
    consumers: dict[str, list[str]] = {}
    templates: dict[str, list[str]] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _strip_docstrings(tree)
        visitor = _CallSites(path, literals_count=path not in DECLARATION_MODULES)
        visitor.visit(tree)
        where = str(path.relative_to(ROOT))
        for name, lines in visitor.used.items():
            consumers.setdefault(name, []).append(f"{where}:{sorted(lines)[0]}")
        for prefix, lines in visitor.templates.items():
            templates.setdefault(prefix, []).append(f"{where}:{sorted(lines)[0]}")

    # Second pass: resolve the names that are built from constants.
    resolver = _TemplateResolver()
    trees: list[tuple[Path, ast.AST]] = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _strip_docstrings(tree)
        trees.append((path, tree))
        resolver.collect(tree)
    stem_templates: list[ast.JoinedStr] = []
    for _path, tree in trees:
        resolver.resolve(tree)
        stem_templates.extend(
            item for item in _TemplateResolver._templates(tree)
            if any(isinstance(value, ast.FormattedValue)
                   and ((isinstance(value.value, ast.Attribute) and value.value.attr == "_stem")
                        or (isinstance(value.value, ast.Name) and value.value.id == "_stem"))
                   for value in item.values))
    resolver.resolve_stems(stem_templates)
    for name in resolver.resolved:
        consumers.setdefault(name, []).append("resolved from constants")

    reached_by_template: dict[str, str] = {}
    for name in bound:
        if name in consumers:
            continue
        for prefix, sites in templates.items():
            if name.startswith(prefix) and len(name) > len(prefix):
                reached_by_template[name] = f"{sites[0]} (family '{prefix}*')"
                break

    observed: set[str] = set()
    if OBSERVED_PATH.is_file():
        observed = {line.strip() for line in OBSERVED_PATH.read_text(encoding="utf-8").splitlines()
                    if line.strip()}
    admitted = json.loads((ROOT / "tools/route-reachability-admitted.json").read_text(
        encoding="utf-8"))["admitted"]
    unreached = [name for name in bound
                 if name not in consumers and name not in observed
                 and name not in reached_by_template and name not in admitted]
    stale = sorted(set(admitted) - set(bound))
    # An admission is stale only when stronger evidence exists: a direct call site
    # or an observed call.  A loose name-template match is weaker than a written
    # reason, so it does not make one redundant.
    unnecessary = sorted(name for name in admitted
                         if name in consumers or name in observed)
    return {
        "schemaVersion": 1,
        "summary": {
            "BOUND_ROUTES": len(bound),
            "DIRECT_CALL_SITE": sum(1 for name in bound if name in consumers),
            "OBSERVED_CALLED_AT_RUNTIME": sum(1 for name in bound if name in observed),
            "REACHED_BY_NAME_TEMPLATE": len(reached_by_template),
            "ADMITTED_WITH_REASON": sum(1 for name in bound if name in admitted),
            "UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE": len(unreached),
            "STALE_ADMISSIONS": len(stale) + len(unnecessary),
        },
        "unreached": unreached,
        "staleAdmissions": stale + unnecessary,
        "reachedByTemplate": reached_by_template,
        "observedAtRuntime": sorted(name for name in bound if name in observed),
        "admitted": admitted,
        "consumers": {name: consumers.get(name, []) for name in bound},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()
    report = analyse()
    if arguments.output:
        Path(arguments.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key, value in report["summary"].items():
        print(f"{key}={value}")
    for name in report["unreached"]:
        print(f"UNREACHED {name}")
    for name in report["staleAdmissions"]:
        print(f"STALE_ADMISSION {name}")
    return 1 if report["unreached"] or report["staleAdmissions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
