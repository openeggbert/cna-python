#!/usr/bin/env python3
"""Derives the engine layer's ctypes structures and constants from the header.

`engine_layer.h` declares 23 structures and 82 frozen constants. A hand-written
transcription of those can omit a field without anything noticing until the day
CNA reads past what Python allocated, and it can carry a constant that CNA has
since changed. So none of it is hand-written: this reads the canonical header and
emits both halves of the measurement.

Two files come out, and they are checked in so a reviewer sees the diff when CNA
changes:

``src/_cna_native/engine_abi.py``
    The ctypes structures, the scalar identities, and every constant.
``tools/engine_abi_probe.inc``
    A C fragment ``tools/abi_probe.c`` includes, which prints the size and
    alignment of every structure, the offset of every field, and the value of
    every constant, as the C compiler sees them.

The generator is not the authority either: what it emits is compared against the
compiler's own measurement by ``tools/audit_cna_abi.py``, and ``--check`` proves
the checked-in files are what the current header produces. A field the parser
missed would therefore have to be missing from the header as well.
"""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cna_headers import parse_header, strip_comments  # noqa: E402

ABI_PATH = ROOT / "src/_cna_native/engine_abi.py"
PROBE_PATH = ROOT / "tools/engine_abi_probe.inc"

#: C spellings this generator can render, and what they are in ctypes.  A type
#: outside this table stops the generator rather than being guessed: an engine
#: structure with a field nobody can spell must not silently acquire a wrong one.
SCALARS = {
    "uint8_t": "c.c_uint8",
    "uint16_t": "c.c_uint16",
    "uint32_t": "c.c_uint32",
    "uint64_t": "c.c_uint64",
    "int8_t": "c.c_int8",
    "int16_t": "c.c_int16",
    "int32_t": "c.c_int32",
    "int64_t": "c.c_int64",
    "float": "c.c_float",
    "double": "c.c_double",
    "char": "c.c_char",
    "CNA_Handle": "c.c_uint64",
    "CNA_Bool": "c.c_uint8",
    "CNA_Result": "c.c_uint32",
}

#: Structures declared in other canonical headers that engine structures embed.
#: They are already measured by the existing audit, so they are imported rather
#: than re-declared.
IMPORTED = {
    "CNA_Vector2": "abi.CNA_Vector2",
    "CNA_Vector3": "abi.CNA_Vector3",
    "CNA_Vector4": "abi.CNA_Vector4",
    "CNA_Matrix": "abi.CNA_Matrix",
    "CNA_Color": "abi.CNA_Color",
    "CNA_StringView": "abi.CNA_StringView",
    "CNA_Rectangle": "abi.CNA_Rectangle",
}

#: Constant families the engine needs whose names are not derivable from an
#: identity typedef. ``CNA_PBR_TEXTURE_*`` numbers the slots of an array field
#: rather than being an enum of its own, so no typedef points at it; the values
#: still come from the canonical header and are still measured by the C probe.
EXTRA_CONSTANT_PREFIXES = ("CNA_PBR_TEXTURE_",)

_STRUCT = re.compile(r"typedef struct (CNA_[A-Za-z0-9_]+)\s*\{(.*?)\}\s*\1\s*;", re.S)
_SCALAR_TYPEDEF = re.compile(r"^typedef\s+(uint32_t|int32_t|uint64_t|float)\s+(CNA_[A-Za-z0-9_]+)\s*;",
                             re.M)
_HANDLE_TYPEDEF = re.compile(r"^typedef\s+CNA_Handle\s+(CNA_[A-Za-z0-9_]+)\s*;", re.M)
_DEFINE = re.compile(r"^#define\s+(CNA_[A-Za-z0-9_]+)\s+(.+?)\s*$", re.M)
_FIELD = re.compile(r"^(?P<type>[A-Za-z_][A-Za-z0-9_ *]*?)\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
                    r"(?:\[(?P<array>[^\]]+)\])?\s*$")
_DOC_STRUCT = re.compile(
    r"typedef struct (CNA_[A-Za-z0-9_]+)\s*\{(.*?)\}\s*\1\s*;", re.S)
_BRIEF = re.compile(r"@brief\s+(.*?)(?:\*/|\n\s*\*\s*\n)", re.S)
#: One documented field: its comment block and the declaration that follows.
#: Matched as a pair rather than by splitting the body on semicolons, because a
#: ``@brief`` may contain one -- and the fields whose documentation says the most
#: are exactly the ones that do.
_DOCUMENTED_FIELD = re.compile(r"/\*\*(.*?)\*/\s*([^;{}]*?);", re.S)
_CALLBACK = re.compile(
    r"typedef\s+(CNA_Result|void)\s*\(\s*\*\s*(CNA_[A-Za-z0-9_]+)\s*\)\s*\(([^)]*)\)\s*;")
_OFFSETOF = re.compile(r"offsetof\s*\(\s*(CNA_[A-Za-z0-9_]+)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _member_prefixes(alias: str) -> tuple[str, ...]:
    """The ``#define`` prefixes an identity's members are spelled with.

    ``CNA_ShadowQuality`` names ``CNA_SHADOW_QUALITY_*`` and
    ``CNA_AlphaModeEXT`` names ``CNA_ALPHA_MODE_*_EXT`` -- the ``EXT`` moves to
    the end of the member -- so both spellings are tried. Deriving them beats
    listing them: an identity CNA adds is picked up without an edit here, and a
    prefix that matches nothing simply contributes nothing.
    """
    body = alias[len("CNA_"):]
    snake = _CAMEL_BOUNDARY.sub("_", body).upper()
    prefixes = {f"CNA_{snake}_"}
    if snake.endswith("_EXT"):
        prefixes.add(f"CNA_{snake[:-len('_EXT')]}_")
    return tuple(sorted(prefixes))


class GenerationError(RuntimeError):
    """The header contains something this generator will not guess at."""


def _defines(text: str) -> dict[str, str]:
    """Every ``#define`` in the header, with line continuations folded in."""
    joined = re.sub(r"\\\n", " ", text)
    values: dict[str, str] = {}
    for name, body in _DEFINE.findall(joined):
        body = body.strip()
        if not body or name.endswith("_H"):
            continue
        values[name] = " ".join(body.split())
    return values


def _evaluate(body: str, known: dict[str, object]) -> object:
    """Evaluates one C constant expression over the constants already known.

    Only the forms this header actually uses are accepted: an integer or float
    literal, a width macro, a shift, an or-fold of other constants, and a
    parenthesised combination of those. Anything else raises rather than
    producing a number nobody measured.
    """
    expression = body
    expression = re.sub(r"\b(?:U?INT(?:8|16|32|64)_C)\s*\(([^)]*)\)", r"(\1)", expression)
    expression = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", expression)
    expression = re.sub(r"\b(\d+\.\d*|\.\d+|\d+)[fF]\b", r"\1", expression)
    if not re.fullmatch(r"[0-9a-fA-FxX_A-Z()\s|&<>+\-*/.]+", expression):
        raise GenerationError(f"unsupported constant expression: {body}")
    names = set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", expression))
    scope = {}
    for name in names:
        if name not in known:
            raise GenerationError(f"constant expression names unknown {name}: {body}")
        scope[name] = known[name]
    try:
        return eval(expression, {"__builtins__": {}}, scope)  # noqa: S307 - closed grammar above
    except Exception as error:  # pragma: no cover - defensive
        raise GenerationError(f"cannot evaluate {body}: {error}") from error


def _fields(body: str) -> list[tuple[str, str, str | None]]:
    """Splits a structure body into ``(c_type, name, array_extent)`` triples."""
    result: list[tuple[str, str, str | None]] = []
    for statement in body.split(";"):
        statement = " ".join(statement.split())
        if not statement:
            continue
        statement = statement.replace("const struct ", "const ").replace("struct ", "")
        match = _FIELD.match(statement)
        if match is None:
            raise GenerationError(f"unparsed structure field: {statement}")
        result.append((" ".join(match.group("type").split()), match.group("name"),
                       match.group("array")))
    return result


def _ctype(c_type: str, aliases: dict[str, str], *, typed_pointers: bool = False) -> str:
    """One C spelling as ctypes.

    ``typed_pointers`` distinguishes the two places a pointer appears. In a
    *structure field* what is stored is the pointer itself and its pointee is
    measured separately, so a bare ``c_void_p`` is both correct and honest. In a
    *callback signature* the pointee type is part of the contract the compiler
    checks, so it is rendered.
    """
    if c_type == "void":
        return "None"
    if c_type.endswith("*"):
        if not typed_pointers:
            return "c.c_void_p"
        pointee = c_type[:-1].strip()
        if pointee.startswith("const "):
            pointee = pointee[len("const "):].strip()
        if pointee == "void":
            return "c.c_void_p"
        return f"c.POINTER({_ctype(pointee, aliases, typed_pointers=True)})"
    if c_type in SCALARS:
        return SCALARS[c_type]
    if c_type in aliases:
        return SCALARS[aliases[c_type]]
    if c_type in IMPORTED:
        return IMPORTED[c_type]
    return c_type


def _dependency_headers(header: Path) -> list[Path]:
    """Every canonical header alongside this one, for resolving referenced types.

    An engine structure embeds types other headers declare -- a bounding box, a
    texture transform, a quality identity. Reading only ``engine_layer.h`` would
    leave those unresolvable and invite a hand-written stand-in, which is the
    transcription this generator exists to remove.
    """
    return sorted(header.parent.glob("*.h"))


def _field_documentation(raw: str) -> dict[str, dict[str, str]]:
    """Each structure field's own ``@brief``, from the un-stripped header.

    A structure with forty-seven fields is one a public projection must
    document, and a hand-written table of forty-seven one-line summaries is
    another transcription that drifts. CNA already writes them; this reads them,
    so a field's documentation and its layout come from the same place.
    """
    documentation: dict[str, dict[str, str]] = {}
    for name, body in _DOC_STRUCT.findall(raw):
        fields: dict[str, str] = {}
        for comment, declaration in _DOCUMENTED_FIELD.findall(body):
            brief = _BRIEF.search(comment + "*/")
            match = _FIELD.match(" ".join(declaration.split()))
            if match is None or brief is None:
                continue
            text = " ".join(brief.group(1).replace("*", " ").split())
            fields[match.group("name")] = text.strip()
        documentation[name] = fields
    return documentation


def generate(header: Path) -> tuple[str, str]:
    raw = header.read_text(encoding="utf-8")
    text = strip_comments(raw)
    aliases: dict[str, str] = {}
    bodies: dict[str, str] = {}
    for other in _dependency_headers(header):
        neighbour = strip_comments(other.read_text(encoding="utf-8"))
        for base, name in _SCALAR_TYPEDEF.findall(neighbour):
            aliases[name] = base
        for name, body in _STRUCT.findall(neighbour):
            bodies.setdefault(name, body)
    own_aliases = {name for _base, name in _SCALAR_TYPEDEF.findall(text)}
    for base, name in _SCALAR_TYPEDEF.findall(text):
        aliases[name] = base
    for name in _HANDLE_TYPEDEF.findall(text):
        aliases[name] = "uint64_t"
    for other in _dependency_headers(header):
        neighbour = strip_comments(other.read_text(encoding="utf-8"))
        for name in _HANDLE_TYPEDEF.findall(neighbour):
            aliases.setdefault(name, "uint64_t")
    handles = _HANDLE_TYPEDEF.findall(text)
    callbacks = [(name, _fields(f"{returns} unused")[0][0] if False else returns,
                  [part.strip() for part in parameters.split(",") if part.strip()])
                 for returns, name, parameters in _CALLBACK.findall(text)]

    #: Every ``#define`` in every canonical header, so an identity declared
    #: elsewhere can contribute its members. Without this the engine's own
    #: header would give the *type* of a shadow quality and none of its values,
    #: and the values would have to be hand-written -- which is exactly the
    #: transcription this generator exists to remove.
    neighbours: dict[str, str] = {}
    for other in _dependency_headers(header):
        if other == header:
            continue
        for name, body in _defines(other.read_text(encoding="utf-8")).items():
            neighbours.setdefault(name, body)

    constants: dict[str, object] = {}
    #: A constant defined as a field offset cannot be evaluated before the
    #: structure exists, and re-deriving it by hand would be exactly the
    #: transcription this generator removes. It is emitted as the offset of the
    #: generated field instead, and C measures the same expression itself.
    derived: dict[str, str] = {}
    for name, body in _defines(raw).items():
        offset = _OFFSETOF.search(body)
        if offset is not None:
            derived[name] = f"{offset.group(1)}.{offset.group(2)}.offset"
            continue
        constants[name] = _evaluate(body, constants)

    structures: list[tuple[str, list[tuple[str, str, str | None]]]] = []
    for name, body in _STRUCT.findall(text):
        structures.append((name, _fields(body)))
    declared = {name for name, _ in structures}

    # A structure an engine *route* takes but no engine structure embeds. The
    # PBR material is the case that matters: every route that applies, extracts
    # or compares one takes it by pointer, and it is declared in graphics_ext.h.
    # Finding it by walking the routes rather than naming it here means the next
    # such type arrives without an edit.
    for declaration in parse_header(header):
        for parameter in declaration.parameters:
            spelling = parameter.type_text
            for prefix in ("const ", "struct "):
                spelling = spelling.replace(prefix, "")
            spelling = spelling.replace("*", "").strip()
            if (spelling.startswith("CNA_") and spelling not in declared
                    and spelling not in IMPORTED and spelling not in aliases
                    and spelling not in SCALARS and spelling in bodies):
                structures.append((spelling, _fields(bodies[spelling])))
                declared.add(spelling)

    # A structure this family embeds but another header declares is generated
    # here too, in dependency order, unless the existing audit already measures
    # it. Nothing is transcribed by hand, and nothing is measured twice.
    pending = True
    while pending:
        pending = False
        for name, fields in list(structures):
            for c_type, _field, _array in fields:
                if c_type.endswith("*") or c_type in SCALARS or c_type in aliases:
                    continue
                if c_type in IMPORTED or c_type in declared:
                    continue
                if c_type not in bodies:
                    raise GenerationError(f"{name} embeds {c_type}, which no canonical "
                                          "header under this include directory declares")
                structures.insert(0, (c_type, _fields(bodies[c_type])))
                declared.add(c_type)
                pending = True

    # A structure must be emitted after everything it embeds, whichever order
    # the headers happened to declare them in.
    by_name = dict(structures)
    ordered: list[tuple[str, list[tuple[str, str, str | None]]]] = []
    placed: set[str] = set()

    def place(name: str) -> None:
        if name in placed:
            return
        placed.add(name)
        for c_type, _field, _array in by_name[name]:
            if c_type in by_name and c_type != name:
                place(c_type)
        ordered.append((name, by_name[name]))

    for name, _fields_of in structures:
        place(name)
    structures = ordered

    lines = [
        '"""Generated ctypes layouts and constants for CNA\'s ``engine_layer.h``.',
        "",
        "Do not edit. ``tools/generate_engine_abi.py`` derives this from the canonical",
        "header, and ``--check`` fails when the checked-in copy is not what the current",
        "header produces. Every size, alignment, field offset and constant here is",
        "re-measured against the C compiler by ``tools/audit_cna_abi.py``.",
        "",
        "Nothing in this module is public. ``cna.extensions.engine`` holds the public",
        "projection; a ctypes object never crosses that boundary.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import ctypes as c",
        "",
        "from . import abi",
        "",
        "# --- scalar identities -----------------------------------------------------",
        "",
        "#: Fixed-width identities the engine layer declares as typedefs of a scalar.",
        "#: They are enums in spirit and integers in the ABI; the public projection",
        "#: turns them into Python enums, and this is only their width.",
    ]
    used = {c_type for _name, fields in structures for c_type, _f, _a in fields}
    emitted = sorted(name for name in aliases
                     if (name in own_aliases or name in used) and not name.endswith("Handle"))
    for name in emitted:
        lines.append(f"{name} = {SCALARS[aliases[name]]}")
    # The members of every identity above, from whichever header declares them,
    # plus the families that have no identity to be derived from.
    wanted = {name: body for prefixes in
              [_member_prefixes(alias) for alias in emitted] + [EXTRA_CONSTANT_PREFIXES]
              for name, body in neighbours.items()
              if name not in constants and name.startswith(prefixes)}
    # One constant may be defined as another -- `CNA_PBR_TEXTURE_MAXIMUM` is the
    # last slot -- and alphabetical order does not respect that, so this repeats
    # until nothing more resolves and then reports whatever is left.
    while wanted:
        progressed = False
        for name in sorted(wanted):
            try:
                constants[name] = _evaluate(wanted[name], constants)
            except GenerationError:
                continue
            del wanted[name]
            progressed = True
        if not progressed:
            raise GenerationError(f"unresolvable constants: {sorted(wanted)}")
    lines.append("")
    lines.append("#: Every opaque engine handle is a ``CNA_Handle``. The names are kept so a")
    lines.append("#: manifest entry can say which object a handle parameter refers to.")
    lines.append(f"ENGINE_HANDLE_TYPES = (")
    for name in sorted(handles):
        lines.append(f'    "{name}",')
    lines.append(")")
    lines.append("")
    if callbacks:
        lines.append("")
        lines.append("#: Function pointers the engine layer hands to CNA. A Python callable")
        lines.append("#: bound to one of these must be rooted for as long as CNA can call it;")
        lines.append("#: the trampoline is what CNA holds, not the Python object.")
        for name, returns, parameters in callbacks:
            rendered = ", ".join(
                _ctype(" ".join(part.split()[:-1]) if len(part.split()) > 1 else part,
                       aliases, typed_pointers=True)
                for part in parameters) or ""
            spelling = _ctype(returns, aliases)
            lines.append(f"{name} = c.CFUNCTYPE({spelling}"
                         + (f", {rendered}" if rendered else "") + ")")
        lines.append("")
        lines.append("#: Every generated callback type, for the ABI audit.")
        lines.append("ENGINE_CALLBACKS = (")
        for name, _returns, _parameters in callbacks:
            lines.append(f"    \"{name}\",")
        lines.append(")")
    lines.append("")
    lines.append("# --- constants -------------------------------------------------------------")
    lines.append("")
    for name in sorted(constants):
        value = constants[name]
        if isinstance(value, float):
            # Emitted at the width C stores it in. ``0.01F`` in a header is
            # 0.009999999776482582, and a Python 0.01 is a *different, larger*
            # number -- so a caller comparing a value CNA produced against this
            # constant would find it one unit in the last place too small.
            rendered = repr(float(ctypes.c_float(value).value))
        else:
            rendered = str(value)
        lines.append(f"{name} = {rendered}")
    lines.append("")
    lines.append("# --- structures ------------------------------------------------------------")
    lines.append("")
    for name, fields in structures:
        lines.append(f"class {name}(c.Structure):")
        lines.append("    _fields_ = [")
        for c_type, field, array in fields:
            rendered = _ctype(c_type, aliases)
            if rendered not in SCALARS.values() and rendered not in IMPORTED.values():
                if rendered != "c.c_void_p" and rendered not in declared:
                    raise GenerationError(f"{name}.{field} has unmappable type {c_type}")
            if array is not None:
                extent = _evaluate(array, constants)
                rendered = f"{rendered} * {int(extent)}"
            lines.append(f'        ("{field}", {rendered}),')
        lines.append("    ]")
        lines.append("")
        lines.append("")
    lines.append("# --- constants derived from a generated layout ------------------------------")
    lines.append("")
    for name in sorted(derived):
        lines.append(f"{name} = {derived[name]}")
    lines.append("")
    lines.append("#: Each structure field's own ``@brief`` from the canonical header, so a")
    lines.append("#: public projection documents a field with CNA's own words rather than a")
    lines.append("#: second summary that can drift from it.")
    lines.append("ENGINE_FIELD_DOCUMENTATION = {")
    documentation = _field_documentation(raw)
    for name, _fields_of in structures:
        fields = documentation.get(name)
        if not fields:
            continue
        lines.append(f'    "{name}": {{')
        for field_name, text in fields.items():
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'        "{field_name}": "{escaped}",')
        lines.append("    },")
    lines.append("}")
    lines.append("")
    lines.append("#: Every generated structure, in declaration order, for the ABI audit.")
    lines.append("ENGINE_STRUCTURES = (")
    for name, _ in structures:
        lines.append(f"    {name},")
    lines.append(")")
    lines.append("")
    lines.append("#: Every generated constant, for the ABI audit to re-read from C.")
    lines.append("ENGINE_CONSTANTS = (")
    for name in sorted(set(constants) | set(derived)):
        lines.append(f'    "{name}",')
    lines.append(")")
    module = "\n".join(lines) + "\n"

    probe = [
        "// Generated by tools/generate_engine_abi.py. Do not edit.",
        "// Included by tools/abi_probe.c so the C compiler measures every engine",
        "// structure and every engine constant rather than this binding asserting them.",
        "#define ENGINE_ABI_PROBE() do { \\",
    ]
    for name, fields in structures:
        probe.append(f"    TYPE({name}); \\")
        for _c_type, field, _array in fields:
            probe.append(f"    FIELD({name}, {field}); \\")
    for name, _returns, _parameters in callbacks:
        probe.append(f'    printf("VALUE {name} %zu\\n", sizeof({name})); \\')
    for name in sorted(derived):
        probe.append(f'    printf("VALUE {name} %lld\\n", (long long)({name})); \\')
    for name in sorted(constants):
        if isinstance(constants[name], float):
            probe.append(f'    printf("FVALUE {name} %.9g\\n", (double)({name})); \\')
        else:
            probe.append(f'    printf("VALUE {name} %lld\\n", (long long)({name})); \\')
    probe.append("} while (0)")
    return module, "\n".join(probe) + "\n"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cna-root", required=True)
    parser.add_argument("--check", action="store_true",
                        help="fail when the checked-in files differ from the header")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    header = Path(args.cna_root).resolve() / "modules/c-api/include/CNA/C/engine_layer.h"
    if not header.is_file():
        raise FileNotFoundError(header)
    module, probe = generate(header)
    written = 0
    for path, content in ((ABI_PATH, module), (PROBE_PATH, probe)):
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == content:
            continue
        if args.check:
            print(f"STALE {path.relative_to(ROOT)} is not what {header.name} produces")
            return 1
        path.write_text(content, encoding="utf-8")
        written += 1
    print(f"ENGINE_ABI_GENERATED={0 if args.check else written}")
    print(f"ENGINE_ABI_UP_TO_DATE={'yes' if args.check else 'regenerated'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
