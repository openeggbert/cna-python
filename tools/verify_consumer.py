#!/usr/bin/env python3
"""Build-independent isolated installed-wheel and generated-template verifier."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--library", required=True)
    args = parser.parse_args()
    wheel = Path(args.wheel).resolve()
    template = Path(args.template).resolve()
    library = Path(args.library).resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise FileNotFoundError(f"wheel is missing: {wheel}")
    if not (template / "tools/generate.py").is_file():
        raise FileNotFoundError(f"template generator is missing: {template}")
    if not library.is_file():
        raise FileNotFoundError(f"native library is missing: {library}")

    with tempfile.TemporaryDirectory(prefix="cna-python-consumer-") as temporary:
        root = Path(temporary)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("CNA_NATIVE_DIR", None)
        environment["CNA_NATIVE_LIBRARY"] = str(library)
        venv = root / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
            cwd=root, env=environment)

        consumer = root / "generated-consumer"
        run([sys.executable, str(template / "tools/generate.py"), str(consumer),
             "--distribution-name", "isolated-cna-consumer",
             "--module-name", "isolated_game", "--game-class", "IsolatedGame"],
            cwd=root, env=environment)

        texts = []
        for path in consumer.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".toml", ".md", ".txt"}:
                texts.append(path.read_text(errors="replace"))
        joined = "\n".join(texts)
        absolute_leaks = int(str(template) in joined or str(wheel.parent.parent) in joined)
        sibling_leaks = int("../cna-python" in joined or "cna-python-template" in joined)
        pythonpath_leaks = int("PYTHONPATH" in joined)

        run([str(python), "-m", "compileall", "-q", "."], cwd=consumer, env=environment)
        import_output = run(
            [str(python), "-c",
             "from Microsoft.Xna.Framework import Game, Vector2; "
             "from Microsoft.Xna.Framework.Graphics import Texture2D, SpriteBatch; "
             "from isolated_game import IsolatedGame; "
             "print('IMPORT_PROBE=PASS')"],
            cwd=consumer, env=environment,
        )
        smoke = run([str(python), "main.py", "--smoke-test"], cwd=consumer, env=environment)
        stability = run([str(python), "main.py", "--stability-test"], cwd=consumer, env=environment)

        print(f"WHEEL={wheel.name}")
        print(f"WHEEL_SHA256={sha256(wheel)}")
        print("IMPORT_PROBE=PASS" if "IMPORT_PROBE=PASS" in import_output else "IMPORT_PROBE=FAIL")
        print("COMPILE_PROBE=PASS")
        smoke_passed = "SUCCESS drew 60 real CNA frames" in smoke
        stability_passed = "SUCCESS drew 600 real CNA frames" in stability
        print("SMOKE_60=PASS" if smoke_passed else "SMOKE_60=FAIL")
        print("STABILITY_600=PASS" if stability_passed else "STABILITY_600=FAIL")
        print(f"ABSOLUTE_DEVELOPER_PATHS={absolute_leaks}")
        print(f"SIBLING_SOURCE_DEPENDENCIES={sibling_leaks}")
        print(f"PYTHONPATH_SOURCE_DEPENDENCIES={pythonpath_leaks}")
        return 1 if (absolute_leaks or sibling_leaks or pythonpath_leaks
                     or not smoke_passed or not stability_passed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
