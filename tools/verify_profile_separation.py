#!/usr/bin/env python3
"""Proves the profiles stay separate, and that each is exactly its own contract.

Four profiles now project XNA, and three of them share Python packages or
implementations with a fourth. That is fine and it is deliberate -- XNA really
does put two assemblies' types in one namespace, and Xbox 360 really is the
Windows surface with names taken away -- but it is only fine while the sharing
is *one way*. This gate is what says so:

``PLATFORM_LEAKS``
    a name a platform profile has and the default Windows surface does not,
    reachable from ``Microsoft.Xna.Framework``. A platform's surface must never
    enlarge the default one; that is the whole reason the platforms live under
    an import root of their own.
``WINDOWS_ONLY_REACHABLE_FROM_PLATFORM``
    the other direction: a type the Windows profiles have and the platform
    contract does not, reachable from the platform's import root. This is what
    makes the profile useful -- a Windows-only name has to be an ``ImportError``
    there, or importing from it proves nothing.
``UNJUSTIFIED_REMOVALS``
    a member a platform profile declares removed that the platform contract
    still has, or that the Windows contract never had. Removal is spelled as a
    descriptor the strict verifier treats as absent, so it would otherwise be a
    way to hide a member rather than to record one.
``DEFAULT_PROFILE_DRIFT``
    the default Windows runtime profile's type and member counts, against the
    numbers this repository has held since before any of the other profiles
    existed.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tools" / "api_compat"))

#: The default Windows runtime surface, which nothing may change.
DEFAULT_PROFILE = "xna40-windows-runtime"
DEFAULT_TYPES = 257
DEFAULT_MEMBERS = 2423

#: The profiles that live under an import root of their own.
PLATFORM_PROFILES = ("xna40-xbox360-runtime",)

#: The Windows profiles a platform's surface is drawn from.
WINDOWS_PROFILES = ("xna40-windows-runtime", "xna40-windows-online")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args()

    from verify import Profile, projected_name, target_types, verify  # noqa: E402

    rules = json.loads((ROOT / "tools/api_compat/mapping-rules.json").read_text())
    windows_types: dict[str, dict] = {}
    for identifier in WINDOWS_PROFILES:
        for entry in Profile.load(identifier).contract["types"]:
            windows_types[entry["name"]] = entry

    default = Profile.load(DEFAULT_PROFILE)
    default_targets, _ = target_types(default)

    leaks: list[str] = []
    windows_only_reachable: list[str] = []
    unjustified: list[str] = []
    removals: list[dict[str, str]] = []
    platform_rows: list[dict[str, object]] = []

    for identifier in PLATFORM_PROFILES:
        profile = Profile.load(identifier)
        platform_types = {entry["name"]: entry
                          for entry in profile.contract["types"]}
        targets, _ = target_types(profile)

        # 1. Nothing the platform has may enlarge the default Windows surface.
        for identity in platform_types:
            if identity in windows_types:
                continue
            if identity in default_targets:
                leaks.append(f"{identifier}: {identity}")

        # 2. A Windows-only name must not be reachable from the platform root.
        #    Either the platform has a package for that namespace and does not
        #    export the name, or it has no package for it at all -- and the
        #    second case is checked by *importing* rather than by assuming,
        #    because a package added later would otherwise go unnoticed.
        root = profile.data["pythonPackages"][0].rsplit(
            ".Microsoft", 1)[0] if profile.data.get("packageNamespaces") else None
        # Every name the platform's packages export, wherever it came from: a
        # Windows-only converter re-exported into the platform's root namespace
        # is reachable from it just as surely as one left in its own.
        exported: dict[str, str] = {}
        for package in profile.packages:
            module = importlib.import_module(package)
            for name in getattr(module, "__all__", ()):
                exported.setdefault(name, package)
        for identity in windows_types:
            if identity in platform_types:
                continue
            name = identity.rsplit(".", 1)[-1].split("`", 1)[0]
            namespace = identity.rsplit(".", 1)[0]
            if name in exported:
                windows_only_reachable.append(
                    f"{identifier}: {identity} is exported by "
                    f"{exported[name]}")
                continue
            if root is None:
                continue
            try:
                importlib.import_module(f"{root}.{namespace}")
            except ImportError:
                continue
            windows_only_reachable.append(
                f"{identifier}: {namespace} is importable and holds {name}")

        # 3. Every declared removal is justified by both contracts.
        for identity, target in sorted(targets.items()):
            for member, raw in vars(target).items():
                if not getattr(raw, "_xna_removed_on_platform", False):
                    continue
                entry = {"profile": identifier, "member": f"{identity}.{member}"}
                removals.append(entry)
                platform = platform_types.get(identity)
                reference = windows_types.get(identity)
                if platform is None or reference is None:
                    unjustified.append(
                        f"{entry['member']}: the type is in neither contract")
                    continue
                if any(projected_name(platform, value, rules) == member
                       for value in platform["members"]):
                    unjustified.append(
                        f"{entry['member']}: the platform contract still has it")
                if not any(projected_name(reference, value, rules) == member
                           for value in reference["members"]):
                    unjustified.append(
                        f"{entry['member']}: Windows never had it either")

        platform_rows.append({
            "profile": identifier,
            "types": len(platform_types),
            "sharedWithWindows": sum(
                1 for identity in platform_types if identity in windows_types),
            "platformOnlyTypes": sum(
                1 for identity in platform_types if identity not in windows_types),
            "windowsOnlyTypes": sum(
                1 for identity in windows_types if identity not in platform_types),
        })

    # The default profile's own numbers, from the strict verifier rather than
    # from a package listing: two profiles share packages, so what a package
    # holds is not what a profile owns.
    measured = verify(default)["summary"]
    drift = []
    if measured["TARGET_TYPES"] != DEFAULT_TYPES:
        drift.append(f"types {measured['TARGET_TYPES']} != {DEFAULT_TYPES}")
    if measured["TARGET_MEMBERS"] != DEFAULT_MEMBERS:
        drift.append(f"members {measured['TARGET_MEMBERS']} != {DEFAULT_MEMBERS}")
    if measured["TOTAL_DIAGNOSTICS"]:
        drift.append(
            f"the default profile has {measured['TOTAL_DIAGNOSTICS']} diagnostics")

    report = {
        "schemaVersion": 1,
        "summary": {
            "DEFAULT_PROFILE_TYPES": measured["TARGET_TYPES"],
            "DEFAULT_PROFILE_MEMBERS": measured["TARGET_MEMBERS"],
            "PLATFORM_PROFILES": len(PLATFORM_PROFILES),
            "DECLARED_REMOVALS": len(removals),
            "PLATFORM_LEAKS": len(leaks),
            "WINDOWS_ONLY_REACHABLE_FROM_PLATFORM": len(windows_only_reachable),
            "UNJUSTIFIED_REMOVALS": len(unjustified),
            "DEFAULT_PROFILE_DRIFT": len(drift),
        },
        "platforms": platform_rows,
        "removals": removals,
        "leaks": leaks,
        "windowsOnlyReachable": windows_only_reachable,
        "unjustified": unjustified,
        "drift": drift,
    }
    if arguments.output:
        Path(arguments.output).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    for row in platform_rows:
        print(f"  {row['profile']}: {row['types']} types, "
              f"{row['sharedWithWindows']} shared with Windows, "
              f"{row['platformOnlyTypes']} platform-only, "
              f"{row['windowsOnlyTypes']} Windows-only")
    for entry in leaks + windows_only_reachable + unjustified + drift:
        print(f"  ! {entry}")
    failed = bool(leaks or windows_only_reachable or unjustified or drift)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
