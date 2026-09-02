#!/usr/bin/env python3
"""Searches this machine for a profile's reference assemblies, and says so.

A profile that cannot be measured is blocked on a *file*, and a claim that a
file is not there has to be checked rather than remembered. This runs the search
and prints what it did, so that "the assemblies are absent" is a measurement
with a date on it and a reproduction beside it.

It looks for each named assembly by file name, case-insensitively, under every
root it is given; and it looks for the directory layouts the assemblies would
arrive in -- a Windows Phone SDK installation, a Reference Assemblies tree, a
NuGet cache. Finding a file with the right *name* is not the end of it: an
assembly is only the assembly if its SHA-256 matches the one the profile pins,
and a profile with nothing pinned yet says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cli_assembly  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "tools" / "api_compat" / "profiles"

#: Where an assembly could plausibly be, on this machine and on a developer's.
#: Deliberately broad: the point is to be able to say the search was wide, not
#: to guess right on the first directory.
DEFAULT_ROOTS = (
    "~", "/opt", "/usr/share", "/usr/lib", "/srv", "/mnt", "/media",
    "/rv/data/development",
)

#: Directory names that would mean an SDK is installed, even if no assembly
#: matched: an unpacked SDK with the assemblies somewhere unexpected is a very
#: different situation from no SDK at all.
SDK_MARKERS = (
    "Windows Phone", "WindowsPhone", "Microsoft SDKs", "Reference Assemblies",
    "XNA Game Studio",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


#: The ``mscorlib`` a desktop .NET assembly references. A file with the right
#: name that names this one is a *Windows* assembly, whatever directory it is
#: in -- which is the question a name search cannot answer on its own.
DESKTOP_CORE = (4, 0, 0, 0)

#: What a Compact Framework or Silverlight assembly references. Both the Xbox
#: 360 and the Windows Phone builds of XNA do, so this narrows a candidate
#: without settling it.
COMPACT_CORE = (2, 0, 5, 0)


def _identify(path: Path) -> dict[str, str]:
    """What the file's own metadata says it is."""
    try:
        assembly = cli_assembly.read(path)
    except Exception as error:  # noqa: BLE001 - reported, never raised
        return {"identity": "", "core": "",
                "platform": f"unreadable: {error}"}
    core = assembly.core_reference()
    version = core.version if core else None
    if version == DESKTOP_CORE:
        platform = "desktop .NET: not a phone or console assembly"
    elif version == COMPACT_CORE:
        platform = "Compact Framework or Silverlight: a candidate"
    elif version is None:
        platform = "references no mscorlib"
    else:
        platform = f"references mscorlib {'.'.join(str(v) for v in version)}"
    return {
        "identity": str(assembly.identity) if assembly.identity else "",
        "core": str(core) if core else "",
        "platform": platform,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--root", action="append", default=[],
                        help="a directory to search; repeatable")
    parser.add_argument("--output")
    arguments = parser.parse_args()

    path = PROFILES / f"{arguments.profile}.json"
    if not path.is_file():
        raise SystemExit(f"no such profile: {arguments.profile}")
    profile = json.loads(path.read_text())
    wanted = {name.lower(): name for name in profile["referenceAssemblies"]}
    pinned = {name.lower(): value
              for name, value in (profile.get("referenceSha256") or {}).items()}
    # Every hash another profile has already pinned, so that a file with the
    # right *name* can be identified as a different platform's assembly rather
    # than reported as a hit. XNA ships the same file names on every platform,
    # which is exactly how a search like this misleads.
    elsewhere: dict[str, str] = {}
    for other in sorted(PROFILES.glob("*.json")):
        if other.stem == arguments.profile:
            continue
        table = json.loads(other.read_text()).get("referenceSha256") or {}
        for name, value in table.items():
            elsewhere[value] = f"{other.stem}:{name}"

    roots = [Path(value).expanduser() for value in
             (arguments.root or list(DEFAULT_ROOTS))]
    searched, files, markers = [], [], []
    found: list[dict[str, str]] = []
    for root in roots:
        if not root.is_dir():
            searched.append({"root": str(root), "status": "absent"})
            continue
        count = 0
        for directory, subdirectories, names in os.walk(
                root, followlinks=False, onerror=lambda _error: None):
            # Anything that would be a rebuild of this machine's own work is not
            # where a Microsoft SDK lives, and walking it costs minutes.
            subdirectories[:] = [
                value for value in subdirectories
                if value not in {".git", "node_modules", "__pycache__"}
                and not value.startswith("cmake-build")
                and value not in {"build", "build-asan", "build-ubsan", "target"}
            ]
            for marker in SDK_MARKERS:
                if marker.lower() in os.path.basename(directory).lower():
                    markers.append(directory)
            for name in names:
                count += 1
                lowered = name.lower()
                if lowered not in wanted:
                    continue
                candidate = Path(directory) / name
                entry = {"assembly": wanted[lowered], "path": str(candidate)}
                try:
                    entry["sha256"] = digest(candidate)
                except OSError as error:  # pragma: no cover - unreadable file
                    entry["sha256"] = f"unreadable: {error}"
                expected = pinned.get(lowered)
                entry["matchesPin"] = (
                    "no pin recorded" if expected is None
                    else str(entry["sha256"] == expected))
                entry["knownAs"] = elsewhere.get(entry["sha256"], "")
                entry.update(_identify(candidate))
                found.append(entry)
                files.append(str(candidate))
        searched.append({"root": str(root), "status": "searched",
                         "filesExamined": count})

    report = {
        "schemaVersion": 1,
        "profile": arguments.profile,
        "assembliesWanted": sorted(wanted.values()),
        "roots": searched,
        "filesExamined": sum(entry.get("filesExamined", 0) for entry in searched),
        "found": found,
        "sdkMarkers": sorted(set(markers)),
        "summary": {
            "ASSEMBLIES_WANTED": len(wanted),
            "NAME_MATCHES": len(found),
            "PINNED_BY_ANOTHER_PROFILE": sum(
                1 for entry in found if entry["knownAs"]),
            "IDENTIFIED_AS_DESKTOP": sum(
                1 for entry in found
                if entry["platform"].startswith("desktop")),
            "CANDIDATES": sum(
                1 for entry in found if not entry["knownAs"]
                and entry["platform"].startswith("Compact")),
            "UNIDENTIFIED": sum(
                1 for entry in found if not entry["knownAs"]
                and not entry["platform"].startswith(("desktop", "Compact"))),
            "SDK_MARKERS_FOUND": len(set(markers)),
        },
    }
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    print(f"ROOTS_SEARCHED={sum(1 for entry in searched if entry['status'] == 'searched')}")
    print(f"FILES_EXAMINED={report['filesExamined']}")
    for entry in found:
        known = entry["knownAs"] or entry["platform"]
        print(f"  NAME_MATCH {entry['assembly']} at {entry['path']} -> {known}")
    for marker in report["sdkMarkers"]:
        print(f"  SDK_MARKER {marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
