#!/usr/bin/env python3
"""Render the human capability table from its machine-readable source."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/runtime-capabilities.json"
OUTPUT = ROOT / "docs/generated/runtime-capabilities.md"


def main() -> int:
    value = json.loads(SOURCE.read_text())
    lines = [
        "# Runtime capability inventory", "",
        f"Qualified boundary: CNA C ABI {value['abi']}; {value['qualifiedBackend']}.", "",
        "| Operation | Status | Evidence | Notes |",
        "|---|---|---|---|",
    ]
    for item in value["operations"]:
        cells = [str(item[name]).replace("|", "\\|")
                 for name in ("operation", "status", "evidence", "notes")]
        lines.append("| " + " | ".join(cells) + " |")
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"CAPABILITIES={len(value['operations'])}")
    print(f"WROTE={OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
