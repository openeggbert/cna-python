#!/usr/bin/env python3
"""Inspect wheel/sdist contents and reject native, cache, and developer leakage."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tarfile
import zipfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def forbidden(names: list[str]) -> list[str]:
    suffixes = (".pyc", ".pyo", ".so", ".dll", ".dylib")
    return sorted(name for name in names if (
        "/.git/" in f"/{name}/" or "__pycache__" in name or name.endswith(suffixes)
        or "/tests/" in f"/{name}" or "xna-probe" in name or "/tmp/" in name
    ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--sdist", required=True)
    args = parser.parse_args()
    wheel, sdist = Path(args.wheel).resolve(), Path(args.sdist).resolve()
    qualified_temp_path = "".join(("/tmp", "/cna-java-native-working-070")).encode()
    path_needles = (str(Path.cwd().resolve()).encode(), qualified_temp_path)
    content_leaks: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        for name in wheel_names:
            payload = archive.read(name)
            if any(needle in payload for needle in path_needles):
                content_leaks.append(f"wheel:{name}")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
        for member in archive.getmembers():
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            payload = stream.read() if stream is not None else b""
            if any(needle in payload for needle in path_needles):
                content_leaks.append(f"sdist:{member.name}")
    required_checks = {
        "MICROSOFT_XNA_PACKAGES": any(name.startswith("Microsoft/Xna/Framework/") for name in wheel_names),
        "PRIVATE_CNA_NATIVE": any(name.startswith("_cna_native/") for name in wheel_names),
        "TYPE_STUBS": any(name.endswith(".pyi") for name in wheel_names),
        "PY_TYPED": any(name.endswith("/py.typed") for name in wheel_names),
        "LICENSE": any(name.endswith("/licenses/LICENSE") for name in wheel_names),
        "NOTICE": any(name.endswith("/licenses/NOTICE.md") for name in wheel_names),
        "README": any(name.endswith("/share/doc/cna-python/README.md") for name in wheel_names),
    }
    bad_wheel = forbidden(wheel_names)
    # Tests are useful in an sdist, so only apply native/cache/path checks there.
    bad_sdist = sorted(name for name in sdist_names if (
        "/.git/" in f"/{name}/" or "__pycache__" in name
        or name.endswith((".pyc", ".pyo", ".so", ".dll", ".dylib"))
        or "xna-probe" in name or "/tmp/" in name
    ))
    all_names = wheel_names + sdist_names
    bundled_native = sorted(name for name in all_names
                            if name.lower().endswith((".so", ".dll", ".dylib")))
    authored_audio = sorted(name for name in all_names if name.lower().endswith(
        (".xgs", ".xsb", ".xwb", ".wav", ".wma", ".mp3", ".fxb")))
    print(f"WHEEL={wheel.name}")
    print(f"WHEEL_SHA256={sha256(wheel)}")
    print(f"WHEEL_FILES={len(wheel_names)}")
    print(f"WHEEL_ENTRIES={len(wheel_names)}")
    print(f"SDIST={sdist.name}")
    print(f"SDIST_SHA256={sha256(sdist)}")
    print(f"SDIST_FILES={len(sdist_names)}")
    print(f"SDIST_ENTRIES={len(sdist_names)}")
    for name, passed in required_checks.items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    print(f"FORBIDDEN_WHEEL_ENTRIES={len(bad_wheel)}")
    print(f"FORBIDDEN_SDIST_ENTRIES={len(bad_sdist)}")
    print(f"ABSOLUTE_DEVELOPER_PATH_LEAKS={len(content_leaks)}")
    print(f"ABSOLUTE_DEVELOPER_PATHS={len(content_leaks)}")
    print(f"BUNDLED_NATIVE_LIBRARIES={len(bundled_native)}")
    print(f"MICROSOFT_OR_PROPRIETARY_CONTENT={len(authored_audio)}")
    if bad_wheel or bad_sdist:
        for name in bad_wheel + bad_sdist:
            print(f"FORBIDDEN={name}")
    for name in content_leaks:
        print(f"DEVELOPER_PATH_LEAK={name}")
    return 1 if (bad_wheel or bad_sdist or content_leaks or bundled_native
                 or authored_audio or not all(required_checks.values())) else 0


if __name__ == "__main__":
    raise SystemExit(main())
