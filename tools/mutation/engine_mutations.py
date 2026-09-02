#!/usr/bin/env python3
"""Plants one defect at a time in the engine slices and reports which test kills it.

A test suite that has never been shown to fail is a suite nobody has measured.
Each mutation below is a plausible mistake in the wrapper or in its oracle -- an
axis swapped, a bound dropped, a view not released, a formula written in double
where CNA writes it in float -- and each one must make a *focused* test fail,
not merely something somewhere.

The oracles are mutated too, and on purpose. An oracle is what the engine tests
compare CNA against, so one that is wrong in the same way as CNA would make a
whole family agree on a defect; planting a wrong oracle and requiring a failure
is how that is ruled out.

Needs ``CNA_NATIVE_LIBRARY`` in the environment, and a rasterizing renderer for
the modules whose tests need one.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

#: (label, file, old, new, the test module the kill is expected in)
MUTATIONS = [
    # --- the cluster grid ----------------------------------------------------
    ("grid: number clusters with y varying fastest",
     "tests/engine_oracles.py",
     "    return (slice_ * tiles_y + y) * tiles_x + x",
     "    return (slice_ * tiles_x + x) * tiles_y + y",
     "tests.test_engine_clustered"),
    ("grid: space the slices linearly instead of logarithmically",
     "tests/engine_oracles.py",
     "    ratio = f32(f32(far_plane) / f32(near_plane))\n"
     "    exponent = f32(f32(slice_) / f32(slice_count))\n"
     "    return f32(f32(near_plane) * f32(math.pow(ratio, exponent)))",
     "    span = f32(f32(far_plane) - f32(near_plane))\n"
     "    return f32(f32(near_plane) + f32(span * f32(f32(slice_) / f32(slice_count))))",
     "tests.test_engine_clustered"),
    ("grid: compute the slice spacing in double rather than float",
     "tests/engine_oracles.py",
     "    return f32(f32(near_plane) * f32(math.pow(ratio, exponent)))",
     "    return near_plane * (far_plane / near_plane) ** (slice_ / slice_count)",
     "tests.test_engine_clustered"),
    ("grid: make the slice lookup a lower bound instead of clamping the far end",
     "tests/engine_oracles.py",
     "    if view_distance >= far_plane:\n        return slice_count - 1",
     "    if view_distance >= far_plane:\n        return slice_count",
     "tests.test_engine_clustered"),
    ("grid: unproject the tile corners at one depth only",
     "tests/engine_oracles.py",
     "            at_far = _unproject(inverse, u, v, 1.0)",
     "            at_far = _unproject(inverse, u, v, 0.0)",
     "tests.test_engine_clustered"),

    # --- light bounds and the assignment -------------------------------------
    ("spot bounds: use the wide case for every cone",
     "tests/engine_oracles.py",
     "    if outer_angle > 0.78539816339:",
     "    if outer_angle > 0.0:",
     "tests.test_engine_clustered"),
    ("assignment: skip the view transform",
     "tests/engine_oracles.py",
     "        view_centre = transform_coordinate((centre.X, centre.Y, centre.Z), view)",
     "        view_centre = centre",
     "tests.test_engine_clustered"),
    ("assignment: compare against the radius rather than its square",
     "tests/engine_oracles.py",
     "                    if squared_distance_to_box(minimum, maximum,\n"
     "                                               view_centre) > radius_squared:",
     "                    if squared_distance_to_box(minimum, maximum,\n"
     "                                               view_centre) > radius:",
     "tests.test_engine_clustered"),
    ("assignment: keep a light with no radius",
     "tests/engine_oracles.py",
     "        if not radius > 0.0:\n            continue",
     "        if False:\n            continue",
     "tests.test_engine_clustered"),

    # --- the shadow budget ---------------------------------------------------
    ("shadow score: weight the channels equally",
     "tests/engine_oracles.py",
     "    return f32(0.2126 * color.X + 0.7152 * color.Y + 0.0722 * color.Z)",
     "    return f32((color.X + color.Y + color.Z) / 3.0)",
     "tests.test_engine_clustered"),
    ("shadow score: drop the one-unit distance floor",
     "tests/engine_oracles.py",
     "               * windowed_falloff(max(distance, 1.0), range_))",
     "               * windowed_falloff(distance, range_))",
     "tests.test_engine_clustered"),
    ("falloff: forget to square the window",
     "tests/engine_oracles.py",
     "    return f32(window * window / max(f32(distance * distance), 1e-4))",
     "    return f32(window / max(f32(distance * distance), 1e-4))",
     "tests.test_engine_clustered"),

    # --- area lights ---------------------------------------------------------
    ("lobe scale: drop the floor a mirror needs",
     "tests/engine_oracles.py",
     "    return f32(max(f32(clamped * clamped), 0.02))",
     "    return f32(clamped * clamped)",
     "tests.test_engine_clustered"),
    ("disc quad: scale by the wrong constant",
     "tests/engine_oracles.py",
     "DISC_AXIS_SCALE = math.sqrt(math.pi) / 2.0",
     "DISC_AXIS_SCALE = math.pi / 4.0",
     "tests.test_engine_clustered"),
    ("volume attenuation: divide the exponent instead of multiplying",
     "tests/engine_oracles.py",
     "    exponent = thickness / attenuation_distance",
     "    exponent = attenuation_distance / thickness",
     "tests.test_engine_clustered"),

    # --- clustered wrappers --------------------------------------------------
    ("light set: read the bounds of the wrong index",
     "src/cna/extensions/engine/clustered.py",
     '            _engine.CNA_BoundingSphere, 0, "cna_clustered_light_set_get_bounds_at",\n'
     '            self._handle.argument, c.c_int32(_support.checked(index, "int32", "index")))',
     '            _engine.CNA_BoundingSphere, 0, "cna_clustered_light_set_get_bounds_at",\n'
     '            self._handle.argument, c.c_int32(0))',
     "tests.test_engine_clustered"),
    ("cluster grid: swap the tile coordinates",
     "src/cna/extensions/engine/clustered.py",
     '            "cna_clustered_light_grid_cluster_index", self._handle.argument,\n'
     '            c.c_int32(_support.checked(x, "int32", "x")),\n'
     '            c.c_int32(_support.checked(y, "int32", "y")),',
     '            "cna_clustered_light_grid_cluster_index", self._handle.argument,\n'
     '            c.c_int32(_support.checked(y, "int32", "y")),\n'
     '            c.c_int32(_support.checked(x, "int32", "x")),',
     "tests.test_engine_clustered"),
    ("forward effect: keep a stale material-extensions view after assigning",
     "src/cna/extensions/engine/clustered.py",
     '        self._drop_view("material_extensions")',
     '        pass',
     "tests.test_engine_clustered"),
    ("forward effect: hand out a new shader view on every read",
     "src/cna/extensions/engine/values.py",
     "        existing = self._views.get(key)\n"
     "        if existing is not None and not (getattr(existing, \"IsDisposed\", False)\n"
     "                                         or getattr(existing, \"is_closed\", False)):\n"
     "            return existing",
     "        existing = None",
     "tests.test_engine_clustered"),

    # --- light probes --------------------------------------------------------
    ("probe: leave negative irradiance unclamped",
     "tests/engine_oracles.py",
     "        channels.append(max(value, 0.0))",
     "        channels.append(value)",
     "tests.test_engine_probes"),
    ("probe: read the first-band terms in the wrong axis order",
     "tests/engine_oracles.py",
     "                 + 2.0 * SH_C2 * (at[1] * unit.Y + at[2] * unit.Z + at[3] * unit.X)",
     "                 + 2.0 * SH_C2 * (at[1] * unit.X + at[2] * unit.Y + at[3] * unit.Z)",
     "tests.test_engine_probes"),
    ("visibility: trust a point beyond the wall as well as one before it",
     "tests/engine_oracles.py",
     "    if distance <= mean:\n        return 1.0",
     "    return 1.0\n    if distance <= mean:\n        return 1.0",
     "tests.test_engine_probes"),
    ("visibility: blend by the component rather than its square",
     "tests/engine_oracles.py",
     "        weight = component * component",
     "        weight = component",
     "tests.test_engine_probes"),
    ("probe grid: space the probes exclusively of the far corner",
     "tests/engine_oracles.py",
     "        return low + (high - low) * step / (count - 1)",
     "        return low + (high - low) * step / count",
     "tests.test_engine_probes"),
    ("hammersley: walk the interval at cell edges rather than centres",
     "tests/engine_oracles.py",
     "    first = (index + 0.5) / count if count > 0 else 0.0",
     "    first = index / count if count > 0 else 0.0",
     "tests.test_engine_probes"),
    ("hammersley: reverse the bits of the wrong index",
     "tests/engine_oracles.py",
     "    bits = index & 0xFFFFFFFF",
     "    bits = (index + 1) & 0xFFFFFFFF",
     "tests.test_engine_probes"),
    ("cube faces: swap the two z faces",
     "tests/engine_oracles.py",
     "        4: Vector3(a, b, 1.0),",
     "        4: Vector3(-a, b, -1.0),",
     "tests.test_engine_probes"),
    ("panorama: put +Z at the centre of the image",
     "tests/engine_oracles.py",
     "    longitude = math.atan2(unit.X, -unit.Z)",
     "    longitude = math.atan2(unit.X, unit.Z)",
     "tests.test_engine_probes"),
    ("probe volume: index the grid with z fastest",
     "tests/engine_oracles.py",
     "    return (z * count_y + y) * count_x + x",
     "    return (x * count_y + y) * count_z + z",
     "tests.test_engine_debug"),
    ("probe wrapper: read a coefficient from the wrong index",
     "src/cna/extensions/engine/probes.py",
     '        _support.call("cna_light_probe_ext_get_coefficient", self._handle.argument,\n'
     '                      c.c_int32(_support.checked(index, "int32", "index")), c.byref(value))',
     '        _support.call("cna_light_probe_ext_get_coefficient", self._handle.argument,\n'
     '                      c.c_int32(0), c.byref(value))',
     "tests.test_engine_probes"),
    ("baker: let a callback exception vanish instead of being re-raised",
     "src/cna/extensions/engine/probes.py",
     "        error, self._error = self._error, None\n        if error is not None:\n            raise error",
     "        self._error = None",
     "tests.test_engine_probes"),
    ("image-based light: keep the three counted views CNA hands out",
     "src/cna/extensions/engine/pbr.py",
     '            if handle:\n                _support.call(destroy, c.c_uint64(handle))',
     '            if False:\n                _support.call(destroy, c.c_uint64(handle))',
     "tests.test_engine_probes"),

    # --- culling and level of detail ------------------------------------------
    ("frustum: take the near plane from the wrong row",
     "tests/engine_oracles.py",
     "        z,                                       # near",
     "        y,                                       # near",
     "tests.test_engine_culling"),
    ("frustum: test the negative vertex of a box instead of the positive one",
     "tests/engine_oracles.py",
     "        x = maximum.X if a >= 0.0 else minimum.X",
     "        x = minimum.X if a >= 0.0 else maximum.X",
     "tests.test_engine_culling"),
    ("frustum: forget to normalise the planes",
     "tests/engine_oracles.py",
     "            planes.append((a / length, b / length, c / length, d / length))",
     "            planes.append((a, b, c, d))",
     "tests.test_engine_culling"),
    ("sphere test: compare against the radius rather than its negation",
     "tests/engine_oracles.py",
     "        if a * centre.X + b * centre.Y + c * centre.Z + d < -radius:",
     "        if a * centre.X + b * centre.Y + c * centre.Z + d < radius:",
     "tests.test_engine_culling"),
    ("lod: make the threshold a lower bound instead of an upper one",
     "tests/engine_oracles.py",
     "        if distance < threshold:\n            return index",
     "        if distance <= threshold:\n            return index",
     "tests.test_engine_culling"),
    ("lod: forget the factor of two in the projected half-extent",
     "tests/engine_oracles.py",
     "    return f32(radius * viewport_height / f32(2.0 * math.tan(vertical_fov * 0.5)\n"
     "                                              * distance))",
     "    return f32(radius * viewport_height / f32(math.tan(vertical_fov * 0.5)\n"
     "                                              * distance))",
     "tests.test_engine_culling"),
    ("lod: make hysteresis sticky across more than one boundary",
     "tests/engine_oracles.py",
     "    if candidate != last + step:\n        return candidate",
     "    if False:\n        return candidate",
     "tests.test_engine_culling"),
    ("lod wrapper: drop the caller's mesh part instead of remembering it",
     "src/cna/extensions/engine/culling.py",
     "        self._parts[handle] = part",
     "        pass",
     "tests.test_engine_culling"),
    ("instancing: report the instance stride as the tint stride",
     "src/cna/extensions/engine/culling.py",
     '    _support.call("cna_instanced_renderer_ext_get_instance_stride", c.byref(value))',
     '    _support.call("cna_instanced_renderer_ext_get_tint_stride", c.byref(value))',
     "tests.test_engine_culling"),
    ("indirect arguments: pack the words in the wrong order",
     "src/cna/extensions/engine/culling.py",
     '            _support.checked(self.vertex_count, "uint32", "vertex_count"),\n'
     '            _support.checked(self.instance_count, "uint32", "instance_count"),',
     '            _support.checked(self.instance_count, "uint32", "instance_count"),\n'
     '            _support.checked(self.vertex_count, "uint32", "vertex_count"),',
     "tests.test_engine_culling"),

    # --- debug drawing --------------------------------------------------------
    ("debug: count a sphere as one ring rather than three",
     "tests/engine_oracles.py",
     "    return 3 * debug_segments(segments)",
     "    return debug_segments(segments)",
     "tests.test_engine_debug"),
    ("debug: forget that a spot light draws two cones",
     "tests/engine_oracles.py",
     "    return 2 * debug_cone_lines(segments)",
     "    return debug_cone_lines(segments)",
     "tests.test_engine_debug"),
    ("debug: clamp the segment count to the wrong bounds",
     "tests/engine_oracles.py",
     "    return min(max(requested, DEBUG_MINIMUM_SEGMENTS), DEBUG_MAXIMUM_SEGMENTS)",
     "    return requested",
     "tests.test_engine_debug"),
    ("debug wrapper: always read the depth-tested list",
     "src/cna/extensions/engine/debug.py",
     "            (self._handle.argument, c.c_uint8(1 if depth_tested else 0)))",
     "            (self._handle.argument, c.c_uint8(1)))",
     "tests.test_engine_debug"),
    ("ascii effect: ignore the destination rectangle",
     "src/cna/extensions/engine/passes.py",
     "                      None if rectangle is None else c.byref(rectangle))",
     "                      None)",
     "tests.test_engine_debug"),
]


def run(module: str) -> tuple[bool, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=str(ROOT), env=environment, capture_output=True, text=True, timeout=1800)
    return completed.returncode == 0, completed.stderr


def main() -> int:
    killed, survived, inapplicable = [], [], []
    for label, relative, old, new, module in MUTATIONS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            inapplicable.append((label, f"anchor appears {original.count(old)} times"))
            continue
        path.write_text(original.replace(old, new), encoding="utf-8")
        try:
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
            passed, stderr = run(module)
        finally:
            path.write_text(original, encoding="utf-8")
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
        if passed:
            survived.append((label, module))
        else:
            names = [line.split(" ")[1] for line in stderr.splitlines()
                     if line.startswith(("FAIL: ", "ERROR: "))]
            killed.append((label, module, names[:3]))

    print(f"PLANTED={len(MUTATIONS)}")
    print(f"KILLED={len(killed)}")
    print(f"SURVIVED={len(survived)}")
    print(f"INAPPLICABLE={len(inapplicable)}")
    for label, module, names in killed:
        print(f"  KILLED  {label}\n            by {module}: {', '.join(names) or '(import)'}")
    for label, module in survived:
        print(f"  SURVIVED {label} (ran {module})")
    for label, reason in inapplicable:
        print(f"  SKIPPED  {label}: {reason}")
    return 1 if survived or inapplicable else 0


if __name__ == "__main__":
    raise SystemExit(main())
