#!/usr/bin/env python3
"""Generate the Milestone-3 Game/Graphics dependency matrix from its baseline report."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tools/api_compat/reference/xna40-windows-runtime-contract.json"
JSON_OUTPUT = ROOT / "docs/generated/milestone3-dependency-matrix.json"
MD_OUTPUT = ROOT / "docs/generated/milestone3-dependency-matrix.md"


def route(owner: str, name: str) -> tuple[str, str, str, str, str, str]:
    """route, available, ownership, callback, implementable, blockers"""
    if owner.endswith("SurfaceFormat") or owner.endswith("Viewport"):
        return "PURE_XNA_DERIVED", "not needed", "value", "none", "yes", "none"
    if owner.endswith("Game"):
        if name in {"Activated", "Deactivated"}:
            return "cna_game_subscribe", "yes", "game-owned registration", "observer", "yes", "BACKEND_BLOCKED"
        if name in {"ResetElapsedTime", "SuppressDraw"}:
            return f"cna_game_{'reset_elapsed_time' if name == 'ResetElapsedTime' else 'suppress_draw'}", "yes", "borrowed Game", "none", "yes", "none"
        return "managed Game facade plus runtime_window/runtime launch routes", "yes", "Game-owned", "managed/native observer", "yes", "none"
    if owner.endswith("GraphicsResource"):
        return "graphics_resource.h", "yes", "owned resource/registration", "disposing observer", "yes", "none"
    if owner.endswith("Texture2D"):
        return "cna_texture2d_*encoded*", "yes", "owned texture", "none", "yes", "none"
    if owner.endswith("Texture"):
        return "cna_texture2d_get_info", "yes", "owned texture", "none", "yes", "none"
    if owner.endswith("SpriteBatch"):
        return "sprite_font.h + cna_sprite_batch_submit_scaled_many", "yes", "owned atlas/font/batch", "none", "yes", "FIXTURE_PENDING public Content loading"
    if owner.endswith("GraphicsDeviceManager"):
        return "runtime_graphics_manager.h", "yes", "owned manager/registrations", "native observer/mutator", "yes", "none"
    if owner.endswith("GraphicsDevice"):
        if name in {"ResourceCreated", "ResourceDestroyed"}:
            return "identityless graphics-device resource callbacks", "partial", "device-owned registration", "observer", "public member only", "UPSTREAM_CNA_BLOCKED stable identity"
        if name == "DeviceLost":
            return "cna_graphics_device_subscribe_event", "yes", "device-owned registration", "observer", "yes", "BACKEND_BLOCKED"
        if name == "Present":
            return "cna_graphics_device_present (default only)", "partial", "borrowed device", "none", "yes", "UPSTREAM_CNA_BLOCKED non-default overload"
        if name.startswith("Draw"):
            blocker = "HARDWARE_PENDING" if name == "DrawInstancedPrimitives" else "BACKEND_BLOCKED"
            return "graphics_device.h draw route", "yes", "borrowed bindings/user bytes", "none", "yes", blocker
        if "RenderTarget" in name:
            return "render_target.h", "yes", "owned target; borrowed binding", "none", "yes", "HARDWARE_PENDING visible output"
        if name in {"Indices", "GetVertexBuffers", "SetVertexBuffer", "SetVertexBuffers"}:
            return "vertex_resources.h/index_resources.h device binding", "yes", "owned buffer; borrowed binding", "none", "yes", "none"
        if name == "GetBackBufferData":
            return "cna_graphics_device_get_backbuffer_data_window", "yes", "caller output", "none", "yes", "BACKEND_BLOCKED on HEADLESS"
        if name in {"DeviceReset", "DeviceResetting", "Disposing"}:
            return "cna_graphics_device_subscribe_event", "yes", "device-owned registration", "observer", "yes", "none"
        return "display.h/graphics_state.h/graphics_device.h", "yes", "borrowed device/copied descriptor", "none", "yes", "none"
    return "managed dependency", "not needed", "managed", "none", "yes", "none"


def main() -> int:
    baseline = json.loads(subprocess.run(
        ["git", "show", "HEAD:docs/generated/api-compat-report.json"],
        cwd=ROOT, text=True, capture_output=True, check=True).stdout)
    reference = json.loads(REFERENCE.read_text())
    by_name = {value["name"]: value for value in reference["types"]}
    rows = []
    for diagnostic in baseline["diagnostics"]:
        owner = diagnostic["type"]
        if diagnostic["category"] != "MISSING_MEMBER": continue
        if not (owner == "Microsoft.Xna.Framework.Game" or
                owner == "Microsoft.Xna.Framework.GraphicsDeviceManager" or
                owner.startswith("Microsoft.Xna.Framework.Graphics.")):
            continue
        name = diagnostic["detail"].split("(", 1)[0]
        members = [value for value in by_name[owner]["members"] if value["name"] == name]
        dependencies = set()
        for member in members:
            for value in [member.get("type"), member.get("returnType"),
                          *(parameter["type"] for parameter in member.get("parameters", ()) )]:
                if value and value.startswith("Microsoft.Xna.Framework") and value != owner:
                    dependencies.add(value.replace("&", ""))
        route_value, available, ownership, callback, implementable, blockers = route(owner, name)
        rows.append({
            "XNA_MEMBER": f"{owner}.{diagnostic['detail']}",
            "REQUIRED_XNA_TYPE": ", ".join(sorted(dependencies)) or "none",
            "CNA_C_API_ROUTE": route_value,
            "ABI_0_7_AVAILABLE": available,
            "NATIVE_OWNERSHIP": ownership,
            "CALLBACK_MODEL": callback,
            "IMPLEMENTABLE": implementable,
            "CNA_BLOCKED": "yes" if "UPSTREAM_CNA_BLOCKED" in blockers else "no",
            "BACKEND_BLOCKED": "yes" if any(value in blockers for value in ("BACKEND_BLOCKED", "HARDWARE_PENDING")) else "no",
            "QUALIFICATION": blockers,
        })
    JSON_OUTPUT.write_text(json.dumps({"schemaVersion": 1, "baselineRows": len(rows), "rows": rows}, indent=2) + "\n")
    headers = list(rows[0])
    lines = ["# Foundation Milestone 3 dependency matrix", "",
             "Generated from the pre-milestone missing-member diagnostics.", "",
             "| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[key]).replace("|", "\\|") for key in headers) + " |")
    MD_OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"DEPENDENCY_ROWS={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
