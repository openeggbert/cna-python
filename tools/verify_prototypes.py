#!/usr/bin/env python3
"""Proves every imported ctypes prototype against the canonical C declaration.

Symbol presence and manifest shape are not evidence that a route's signature is
unchanged.  This gate renders each imported route's prototype *from the ctypes
manifest alone* and emits it as a redundant C declaration in a translation unit
that includes the canonical CNA headers.  C requires every declaration of a
function to be compatible, so the compiler rejects a wrong width, a wrong
signedness, a wrong pointer depth, a struct passed by value instead of by
pointer, a wrong callback signature, a swapped parameter, or a wrong arity.

Only the ``const`` qualifier is taken from the canonical declaration: it is not
an ABI property, but C declaration compatibility distinguishes ``const T*`` from
``T*``, so a redundant declaration must carry it.  Every ABI-relevant property is
supplied by ctypes and proven by the compiler.
"""

from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from cna_headers import Declaration, parse_include_directory  # noqa: E402

from _cna_native.loader import FUNCTION_MANIFEST  # noqa: E402


_SCALARS = {
    ctypes.c_uint8: "uint8_t",
    ctypes.c_uint16: "uint16_t",
    ctypes.c_uint32: "uint32_t",
    ctypes.c_uint64: "uint64_t",
    ctypes.c_int8: "int8_t",
    ctypes.c_int16: "int16_t",
    ctypes.c_int32: "int32_t",
    ctypes.c_int64: "int64_t",
    ctypes.c_float: "float",
    ctypes.c_double: "double",
    ctypes.c_char: "char",
}


class PrototypeRenderError(RuntimeError):
    """Raised when a ctypes type has no unambiguous canonical C spelling."""


def render_ctype(value: object) -> str:
    """Renders one ctypes type as the C type spelling it claims to represent."""
    if value is None:
        return "void"
    if value is ctypes.c_void_p:
        return "void*"
    scalar = _SCALARS.get(value)  # type: ignore[arg-type]
    if scalar is not None:
        return scalar
    if isinstance(value, type) and issubclass(value, ctypes._Pointer):  # type: ignore[attr-defined]
        return f"{render_ctype(value._type_)}*"
    if isinstance(value, type) and issubclass(value, ctypes._CFuncPtr):  # type: ignore[attr-defined]
        arguments = ", ".join(render_ctype(item) for item in value._argtypes_) or "void"
        return f"{render_ctype(value._restype_)} (*)({arguments})"
    if isinstance(value, type) and issubclass(value, (ctypes.Structure, ctypes.Union)):
        return value.__name__
    raise PrototypeRenderError(f"no canonical C spelling for ctypes type {value!r}")


def render_prototype(declaration: Declaration, restype: object, argtypes: list[object]) -> str:
    """Renders a redundant C declaration whose types come from ctypes."""
    if declaration.arity != len(argtypes):
        raise PrototypeRenderError(
            f"{declaration.name}: canonical arity {declaration.arity} != ctypes arity {len(argtypes)}"
        )
    if not argtypes:
        return f"{render_ctype(restype)} {declaration.name}(void);"
    rendered: list[str] = []
    for parameter, argtype in zip(declaration.parameters, argtypes):
        text = render_ctype(argtype)
        if parameter.pointee_is_const and text.endswith("*"):
            text = f"const {text}"
        rendered.append(text)
    return f"{render_ctype(restype)} {declaration.name}({', '.join(rendered)});"


def translation_unit(lines: list[str]) -> str:
    return '#include "CNA/C/cna.h"\n\n' + "\n".join(lines) + "\n"


def compile_unit(source: str, include: Path, compiler: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="cna-python-prototypes-") as directory:
        path = Path(directory) / "prototypes.c"
        path.write_text(source, encoding="utf-8")
        return subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Werror",
                "-Wall",
                "-Wextra",
                "-Wno-unused-parameter",
                "-I",
                str(include),
                "-c",
                str(path),
                "-o",
                str(Path(directory) / "prototypes.o"),
            ],
            text=True,
            capture_output=True,
        )


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cna-root", required=True)
    parser.add_argument("--compiler", default="cc")
    parser.add_argument("--output")
    return parser.parse_args()


def verify_manifest(
    manifest: tuple[tuple[str, object, list[object], str], ...],
    canonical: dict[str, Declaration],
    include: Path,
    compiler: str = "cc",
) -> dict[str, object]:
    """Compiles one ctypes manifest against the canonical headers and reports."""
    absent: list[str] = []
    render_failures: list[dict[str, object]] = []
    lines: list[str] = []
    proven: list[str] = []
    for symbol, restype, argtypes, _ownership in manifest:
        declaration = canonical.get(symbol)
        if declaration is None:
            absent.append(symbol)
            continue
        try:
            lines.append(render_prototype(declaration, restype, list(argtypes)))
        except PrototypeRenderError as error:
            render_failures.append({"symbol": symbol, "reason": str(error)})
            continue
        proven.append(symbol)

    conflicts: list[dict[str, object]] = []
    compiled = False
    if lines:
        result = compile_unit(translation_unit(lines), include, compiler)
        compiled = result.returncode == 0
        if not compiled:
            # Localise every conflicting route so the report names it exactly.
            for symbol, line in zip(proven, lines):
                single = compile_unit(translation_unit([line]), include, compiler)
                if single.returncode != 0:
                    conflicts.append(
                        {
                            "symbol": symbol,
                            "ctypesDeclaration": line,
                            "canonicalHeader": canonical[symbol].header,
                            "canonicalReturn": canonical[symbol].return_type,
                            "canonicalParameters": [
                                parameter.type_text for parameter in canonical[symbol].parameters
                            ],
                            "diagnostic": single.stderr.strip().splitlines()[:6],
                        }
                    )

    verified = len(proven) if compiled else len(proven) - len(conflicts)
    return {
        "schemaVersion": 1,
        "summary": {
            "CANONICAL_ROUTES": len(canonical),
            "IMPORTED_ROUTES": len(manifest),
            "PROTOTYPES_COMPILER_VERIFIED": verified,
            "PROTOTYPE_CONFLICTS": len(conflicts),
            "ABSENT_FROM_HEADERS": len(absent),
            "RENDER_FAILURES": len(render_failures),
        },
        "absentFromHeaders": absent,
        "renderFailures": render_failures,
        "conflicts": conflicts,
    }


def main() -> int:
    args = arguments()
    include = Path(args.cna_root).resolve() / "modules/c-api/include"
    canonical = parse_include_directory(include)
    report = verify_manifest(FUNCTION_MANIFEST, canonical, include, args.compiler)
    conflicts = report["conflicts"]
    render_failures = report["renderFailures"]
    absent = report["absentFromHeaders"]
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    for conflict in conflicts:
        print(f"CONFLICT {conflict['symbol']}: {conflict['ctypesDeclaration']}")
        for line in conflict["diagnostic"]:  # type: ignore[index]
            print(f"    {line}")
    for failure in render_failures:
        print(f"RENDER_FAILURE {failure['symbol']}: {failure['reason']}")
    for symbol in absent:
        print(f"ABSENT {symbol}")
    return 1 if conflicts or render_failures or absent else 0


if __name__ == "__main__":
    raise SystemExit(main())
