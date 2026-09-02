#!/usr/bin/env python3
"""Regenerates a strict-profile reference contract from its pinned assemblies.

The contract JSON checked into ``tools/api_compat/reference/`` is a generated
artifact, and this is its generator.  The measurement itself is done by
``tools/reference_extractor`` (a .NET tool reading CLI metadata); this script
selects the profile, runs it, pins the assembly hashes back into the profile,
and reports what was measured.

Nothing here downloads or packages a reference assembly.  A profile names a
local directory; if that directory is missing the profile's dependent rows are
``BLOCKED_REFERENCE_ASSET`` and this script says so rather than guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "tools/api_compat/profiles"
REFERENCE = ROOT / "tools/api_compat/reference"
EXTRACTOR = ROOT / "tools/reference_extractor"
EXTRACTOR_DLL = EXTRACTOR / "bin/Release/net8.0/ReferenceExtractor.dll"


def expand(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def profile_path(identifier: str) -> Path:
    return PROFILES / f"{identifier}.json"


def load_profile(identifier: str) -> dict:
    return json.loads(profile_path(identifier).read_text())


def missing_assemblies(profile: dict) -> list[str]:
    root = expand(profile["assemblyRoot"])
    return [name for name in profile["referenceAssemblies"] if not (root / name).is_file()]


def build_extractor() -> None:
    if EXTRACTOR_DLL.is_file():
        return
    if shutil.which("dotnet") is None:
        raise SystemExit("EXTRACTOR_UNAVAILABLE dotnet is not installed")
    subprocess.run(
        ["dotnet", "build", "-c", "Release", "--nologo"],
        cwd=EXTRACTOR, check=True,
        env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"},
    )


def extract(identifier: str, output: Path) -> dict[str, str]:
    build_extractor()
    completed = subprocess.run(
        ["dotnet", str(EXTRACTOR_DLL),
         "--profile", str(profile_path(identifier)),
         "--output", str(output)],
        check=True, capture_output=True, text=True,
        env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"},
    )
    # The .NET tool writes indented JSON; the checked-in contract is compact so a
    # regeneration that changed nothing produces no diff at all.
    output.write_text(
        json.dumps(json.loads(output.read_text()), separators=(",", ":")) + "\n")
    hashes: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if line.startswith("SHA256 "):
            _, name, digest = line.split()
            hashes[name] = digest
    return hashes


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profiles", nargs="*", help="profile ids; default: every profile")
    parser.add_argument("--check", action="store_true",
                        help="re-derive into a temporary file and diff, changing nothing")
    arguments = parser.parse_args()

    identifiers = arguments.profiles or sorted(
        path.stem for path in PROFILES.glob("*.json"))

    failures = 0
    for identifier in identifiers:
        profile = load_profile(identifier)
        if "contract" not in profile:
            continue
        absent = missing_assemblies(profile)
        if absent:
            print(f"{identifier} BLOCKED_REFERENCE_ASSET {' '.join(absent)}")
            failures += 1
            continue
        target = REFERENCE / profile["contract"]
        scratch = target.with_suffix(".generated.json")
        hashes = extract(identifier, scratch)
        if profile.get("referenceSha256") and profile["referenceSha256"] != hashes:
            print(f"{identifier} REFERENCE_ASSEMBLY_HASH_CHANGED")
            failures += 1
        if arguments.check:
            same = target.is_file() and sha256(target) == sha256(scratch)
            print(f"{identifier} CONTRACT_UP_TO_DATE={'yes' if same else 'no'}")
            if not same and target.is_file():
                subprocess.run(
                    [sys.executable, str(ROOT / "tools/api_compat/compare_contracts.py"),
                     str(target), str(scratch)], check=False)
            failures += 0 if same else 1
            scratch.unlink()
        else:
            scratch.replace(target)
            profile["referenceSha256"] = hashes
            contract = json.loads(target.read_text())
            profile["referenceTypes"] = len(contract["types"])
            profile["referenceMembers"] = sum(
                len(entry["members"]) for entry in contract["types"])
            profile_path(identifier).write_text(json.dumps(profile, indent=2) + "\n")
            print(f"{identifier} TYPES={profile['referenceTypes']} "
                  f"MEMBERS={profile['referenceMembers']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
