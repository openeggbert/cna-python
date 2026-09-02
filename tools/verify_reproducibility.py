#!/usr/bin/env python3
"""Measures what is reproducible about the package, and what is not.

"Reproducible" is two different claims and conflating them is how a project ends
up asserting something it has not measured:

* **Content reproducible** -- two builds of the same tree contain the same files
  with the same bytes. This is the claim that matters to anyone verifying a
  release against its source.
* **Byte reproducible** -- the two archives are identical as files, container
  metadata included.

They can differ, and here they do. The wheel is both. The sdist is content
reproducible but not byte reproducible: setuptools stamps the files it generates
during the build -- ``PKG-INFO``, ``setup.cfg`` -- and every directory entry with
the wall clock, regardless of ``SOURCE_DATE_EPOCH``, and gzip records its own
timestamp in the header. Nothing in this repository causes it and nothing here
can fix it, so it is reported rather than claimed away.

Both builds are isolated, which is what ``python -m build`` does by default.
``--no-isolation`` would be cheaper, but this repository declares its licence in
the PEP 639 form and the interpreter's own setuptools is older than that, so a
non-isolated build fails before it starts. Isolation also means both builds use
the *same* backend version as each other, which is what makes the comparison
about the source rather than about the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

#: A fixed timestamp, so anything that *does* honour it is held still and only
#: what ignores it can vary.
PINNED_EPOCH = "1700000000"


def build(destination: Path) -> tuple[Path, Path]:
    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = PINNED_EPOCH
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir",
         str(destination)],
        cwd=str(ROOT), env=environment, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    wheels = sorted(destination.glob("*.whl"))
    sdists = sorted(destination.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(f"expected one wheel and one sdist in {destination}")
    return wheels[0], sdists[0]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wheel_contents(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {name: hashlib.sha256(archive.read(name)).hexdigest()
                for name in sorted(archive.namelist())}


def sdist_contents(path: Path) -> dict[str, str]:
    contents: dict[str, str] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in sorted(archive.getmembers(), key=lambda item: item.name):
            if not member.isfile():
                contents[member.name] = "<directory>"
                continue
            stream = archive.extractfile(member)
            payload = stream.read() if stream is not None else b""
            contents[member.name] = hashlib.sha256(payload).hexdigest()
    return contents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="cna-python-repro-") as temporary:
        root = Path(temporary)
        first_wheel, first_sdist = build(root / "first")
        second_wheel, second_sdist = build(root / "second")

        wheel_bytes = digest(first_wheel) == digest(second_wheel)
        sdist_bytes = digest(first_sdist) == digest(second_sdist)
        wheel_content = wheel_contents(first_wheel) == wheel_contents(second_wheel)
        sdist_content = sdist_contents(first_sdist) == sdist_contents(second_sdist)
        summary = {
            "WHEEL_BYTE_REPRODUCIBLE": int(wheel_bytes),
            "WHEEL_CONTENT_REPRODUCIBLE": int(wheel_content),
            "SDIST_BYTE_REPRODUCIBLE": int(sdist_bytes),
            "SDIST_CONTENT_REPRODUCIBLE": int(sdist_content),
            "WHEEL_SHA256": digest(first_wheel),
            "WHEEL_FILES": len(wheel_contents(first_wheel)),
            "SDIST_FILES": len(sdist_contents(first_sdist)),
        }

    for key, value in summary.items():
        print(f"{key}={value}")
    if arguments.output:
        import json

        Path(arguments.output).write_text(
            json.dumps({"schemaVersion": 1, "summary": summary,
                        "sourceDateEpoch": PINNED_EPOCH}, indent=2) + "\n",
            encoding="utf-8")
    # Content reproducibility is the gate. Byte reproducibility of the sdist is
    # reported because it is a fact about setuptools, not a defect to fail on.
    return 0 if wheel_content and sdist_content and wheel_bytes else 1


if __name__ == "__main__":
    raise SystemExit(main())
