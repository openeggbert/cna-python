#!/usr/bin/env python3
"""Canonical CNA C header parser shared by the prototype and census tools.

The parser is never the final ABI authority on its own. Every declaration it
produces is re-emitted as a redundant C declaration and compiled against the
canonical headers, so a mis-parse becomes a compiler error rather than a silent
false measurement. See ``tools/verify_prototypes.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Parameter:
    """One canonical C parameter as declared in a CNA public header."""

    type_text: str
    name: str

    @property
    def pointee_is_const(self) -> bool:
        return self.type_text.startswith("const ")

    @property
    def is_pointer(self) -> bool:
        return self.type_text.endswith("*")


@dataclass(frozen=True)
class Declaration:
    """One canonical ``CNA_C_API`` route declaration."""

    name: str
    header: str
    return_type: str
    parameters: tuple[Parameter, ...]
    is_void_parameter_list: bool

    @property
    def arity(self) -> int:
        return 0 if self.is_void_parameter_list else len(self.parameters)


_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE = re.compile(r"//[^\n]*")
_DECLARATION = re.compile(r"^CNA_C_API\b(.*?);", re.S | re.M)
_SIGNATURE = re.compile(r"^(.*?)\b(cna_[A-Za-z0-9_]+)\s*\((.*)\)$", re.S)
_TRAILING_NAME = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)$")


def strip_comments(text: str) -> str:
    return _COMMENT_LINE.sub(" ", _COMMENT_BLOCK.sub(" ", text))


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    for character in text:
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        if character == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += character
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def _parse_parameter(text: str) -> Parameter:
    collapsed = " ".join(text.split())
    match = _TRAILING_NAME.search(collapsed)
    if match is None:
        return Parameter(collapsed, "")
    name = match.group(1)
    type_text = collapsed[: match.start()].strip()
    if not type_text:
        # The whole token is a type such as ``void``; there is no parameter name.
        return Parameter(collapsed, "")
    return Parameter(" ".join(type_text.split()), name)


def parse_header(path: Path) -> list[Declaration]:
    """Parses every ``CNA_C_API`` route declaration in one canonical header."""
    text = strip_comments(path.read_text(encoding="utf-8"))
    declarations: list[Declaration] = []
    for match in _DECLARATION.finditer(text):
        body = " ".join(match.group(1).split())
        signature = _SIGNATURE.match(body)
        if signature is None:
            raise ValueError(f"{path.name}: unparsed CNA_C_API declaration: {body[:160]}")
        return_type = " ".join(signature.group(1).split())
        parameter_text = signature.group(3).strip()
        void_list = parameter_text == "void"
        parameters = (
            ()
            if void_list or not parameter_text
            else tuple(_parse_parameter(part) for part in _split_top_level(parameter_text))
        )
        declarations.append(
            Declaration(signature.group(2), path.name, return_type, parameters, void_list)
        )
    return declarations


def parse_include_directory(include: Path) -> dict[str, Declaration]:
    """Parses every canonical public CNA C header under ``CNA/C``."""
    root = include / "CNA/C"
    if not (root / "abi.h").is_file():
        raise FileNotFoundError(f"canonical CNA C headers are missing under {root}")
    declarations: dict[str, Declaration] = {}
    for header in sorted(root.glob("*.h")):
        for declaration in parse_header(header):
            existing = declarations.get(declaration.name)
            if existing is not None:
                raise ValueError(
                    f"duplicate canonical declaration {declaration.name} in "
                    f"{existing.header} and {declaration.header}"
                )
            declarations[declaration.name] = declaration
    return declarations
