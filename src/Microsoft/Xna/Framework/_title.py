"""Deterministic title-relative content access for the XNA TitleContainer facade."""

from __future__ import annotations

import ctypes as c
from io import BytesIO
import os
from pathlib import Path
import re
import sys
from threading import RLock
from typing import BinaryIO

from _cna_native import abi
from _cna_native.errors import NativeError
from _cna_native.loader import get_library
from _cna_native.runtime_context import try_current_game


_root_lock = RLock()
_title_root: Path | None = None


def _default_title_root() -> Path:
    configured = os.environ.get("CNA_TITLE_ROOT")
    if configured is not None:
        root = Path(configured)
        if not root.is_absolute():
            raise ValueError("CNA_TITLE_ROOT must name an absolute directory")
        return root.resolve(strict=False)

    main = sys.modules.get("__main__")
    main_file = getattr(main, "__file__", None)
    if isinstance(main_file, str) and main_file and not main_file.startswith("<"):
        return Path(main_file).resolve(strict=False).parent

    argument = sys.argv[0] if sys.argv else ""
    if argument and argument not in {"-c", "-m"} and not argument.startswith("<"):
        candidate = Path(argument)
        if candidate.is_absolute():
            return candidate.resolve(strict=False).parent

    # Interactive/embedded Python has no application module.  The executable directory is a
    # deterministic title location and, unlike an empty Path, never changes with process CWD.
    return Path(sys.executable).resolve(strict=False).parent


def _get_title_root() -> Path:
    global _title_root
    with _root_lock:
        if _title_root is None:
            _title_root = _default_title_root()
        return _title_root


def _set_title_root_for_tests(value: Path | None) -> None:
    """Private deterministic override used by repository tests only."""
    global _title_root
    with _root_lock:
        _title_root = None if value is None else value.resolve(strict=False)


def _normalize_title_name(name: str) -> str:
    if name is None:
        raise TypeError("name cannot be None")
    if not isinstance(name, str):
        raise TypeError("name must be str")
    if not name:
        raise ValueError("name must not be empty")
    if "\0" in name:
        raise ValueError("name cannot contain NUL")

    portable = name.replace("\\", "/")
    if portable.startswith("/") or re.match(r"^[A-Za-z]:", portable):
        raise ValueError("name must be relative to title storage")
    segments: list[str] = []
    for segment in portable.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if not segments:
                raise ValueError("name escapes title storage")
            segments.pop()
            continue
        segments.append(segment)
    if not segments:
        raise ValueError("name must identify a title file")
    return "/".join(segments)


def _native_title_bytes(game: object, name: str) -> bytes:
    host = getattr(game, "_host", None)
    if host is None or not getattr(host, "handle", 0):
        raise RuntimeError("the active Game has no CNA title-storage handle")
    encoded = name.encode("utf-8", errors="strict")
    view = abi.CNA_StringView(encoded, len(encoded))
    required = c.c_uint64()
    library = host.library
    operation = "cna_title_container_read_ext"
    result = int(library.cna_title_container_read_ext(
        host.handle, view, None, 0, c.byref(required)
    ))
    if result not in (0, 14):
        try:
            library.check(result, operation, context=name)
        except NativeError as error:
            if error.result == 5:
                raise FileNotFoundError(name) from error
            raise
    if required.value == 0:
        return b""
    destination = (c.c_uint8 * required.value)()
    copied = c.c_uint64()
    result = int(library.cna_title_container_read_ext(
        host.handle, view, destination, required.value, c.byref(copied)
    ))
    try:
        library.check(result, operation, context=name)
    except NativeError as error:
        if error.result == 5:
            raise FileNotFoundError(name) from error
        raise
    if copied.value != required.value:
        raise OSError(f"short CNA title read: {copied.value} of {required.value} bytes")
    return bytes(destination)


def _safe_title_path(name: str) -> Path:
    root = _get_title_root().resolve(strict=False)
    path = root.joinpath(*name.split("/")).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("name resolves outside title storage") from error
    return path


def _configure_native_title_root(host: object) -> None:
    root = os.fspath(_get_title_root())
    encoded = root.encode("utf-8", errors="strict")
    view = abi.CNA_StringView(encoded, len(encoded))
    host.library.check(
        host.library.cna_title_location_set_path_ext(host.handle, view),
        "cna_title_location_set_path_ext",
        context=root,
    )


class TitleContainer:
    """XNA title-relative, caller-owned readable stream entry point."""

    @staticmethod
    def OpenStream(name: str) -> BinaryIO:
        normalized = _normalize_title_name(name)
        path = _safe_title_path(normalized)
        game = try_current_game()
        if game is not None:
            return BytesIO(_native_title_bytes(game, normalized))

        try:
            # Read eagerly to keep the managed and CNA whole-file routes observationally aligned.
            return BytesIO(path.read_bytes())
        except (FileNotFoundError, NotADirectoryError) as error:
            raise FileNotFoundError(name) from error


TitleContainer.__xna_arities__ = {"OpenStream": {1}}
