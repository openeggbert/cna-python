#!/usr/bin/env python3
"""Render the human capability table from its machine-readable source.

Schema 2 names the artifacts a measurement came from. A capability can genuinely
differ between them -- a draw that rasterizes on a real renderer and has nowhere
to land on a backend with no pixel storage is one result, not two contradictory
ones -- so a row may carry a per-artifact breakdown and the table shows it.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/runtime-capabilities.json"
OUTPUT = ROOT / "docs/generated/runtime-capabilities.md"


def main() -> int:
    value = json.loads(SOURCE.read_text(encoding="utf-8"))
    artifacts = value["artifacts"]
    lines = [
        "# Runtime capability inventory",
        "",
        f"CNA C ABI {value['abi']}, cnanext `{value['cnaRevision'][:12]}`, "
        f"Sharp Runtime `{value['sharpRuntimeRevision'][:12]}`.",
        "",
        "A status is a claim about a measured artifact, never about CNA in general.",
        "Where a row differs between artifacts the breakdown is shown; where it does not,",
        "the status held on every artifact it was measured on.",
        "",
        "## Qualified artifacts",
        "",
        "| Id | Role | Renderer | Rasterizes | Audio | Video | Platform | SHA-256 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for artifact in artifacts:
        lines.append("| " + " | ".join([
            f"`{artifact['id']}`", artifact["role"], artifact["renderer"],
            "yes" if artifact["rasterizes"] else "no", artifact["audio"],
            artifact["video"], artifact["platform"], f"`{artifact['sha256'][:16]}…`",
        ]) + " |")

    counts: dict[str, int] = {}
    for item in value["operations"]:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    lines += ["", "## Totals", "", "```text", f"CAPABILITIES={len(value['operations'])}"]
    for status in value["statuses"]:
        lines.append(f"{status}={counts.get(status, 0)}")
    lines += ["```", "", "## Operations", "",
              "| Operation | Status | By artifact | Evidence | Notes |",
              "|---|---|---|---|---|"]
    for item in value["operations"]:
        breakdown = item.get("byArtifact")
        rendered = ("; ".join(f"{key}: {name}" for key, name in sorted(breakdown.items()))
                    if breakdown else "same on all")
        cells = [item["operation"], item["status"], rendered, item["evidence"], item["notes"]]
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in cells) + " |")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"CAPABILITIES={len(value['operations'])}")
    for status in value["statuses"]:
        print(f"{status}={counts.get(status, 0)}")
    print(f"ARTIFACTS={len(artifacts)}")
    print(f"WROTE={OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
