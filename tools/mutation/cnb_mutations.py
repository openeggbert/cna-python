#!/usr/bin/env python3
"""Plants one defect at a time in the CNB slices and reports which test kills it.

A test suite that has never been shown to fail is a suite nobody has measured.
Each mutation below is a plausible mistake in the wrapper -- an index swapped, a
field read from the wrong place, a length off by one -- and each one must make a
*focused* test fail, not merely something somewhere.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

#: The repository this tool lives in, derived from its own location rather
#: than written down: an absolute developer path in a shipped file is both a
#: leak and a file that only works on one machine.
ROOT = Path(__file__).resolve().parents[2]

#: (label, file, old, new, the test module the kill is expected in)
MUTATIONS = [
    # --- document / container ---
    ("document: report the chunk count as one too many",
     "src/cna/extensions/content/document.py",
     'return _support.out_u64("cna_cnb_document_get_chunk_count", self._value)',
     'return _support.out_u64("cna_cnb_document_get_chunk_count", self._value) + 1',
     "tests.test_cnb_format"),
    ("document: read the asset type from the schema version",
     "src/cna/extensions/content/document.py",
     'return _support.out_u32("cna_cnb_document_get_asset_type_id", self._value)',
     'return _support.out_u32("cna_cnb_document_get_asset_schema_version", self._value)',
     "tests.test_cnb_format"),
    ("document: skip the mandatory-chunk check",
     "src/cna/extensions/content/document.py",
     '        _support.call("cna_cnb_document_require_mandatory_chunks_understood",\n'
     '                      self._value, array, c.c_uint64(count))',
     '        return',
     "tests.test_cnb_format"),
    ("document: swap the two metadata names",
     "src/cna/extensions/content/document.py",
     '            asset_type_name=_support.sized_text(\n'
     '                "cna_cnb_document_get_metadata_asset_type_name_size",\n'
     '                "cna_cnb_document_copy_metadata_asset_type_name",',
     '            asset_type_name=_support.sized_text(\n'
     '                "cna_cnb_document_get_metadata_content_name_size",\n'
     '                "cna_cnb_document_copy_metadata_content_name",',
     "tests.test_cnb_format"),
    # --- buffers ---
    ("buffer: size a two-call output one byte short",
     "src/_cna_native/cnb_support.py",
     '    buffer = (c.c_uint8 * size)()\n'
     '    written = c.c_uint64()\n'
     '    call(operation, *arguments, buffer, c.c_uint64(size), c.byref(written))\n'
     '    return bytes(bytearray(buffer)[: written.value])\n'
     '\n'
     '\n'
     'def two_call_text',
     '    buffer = (c.c_uint8 * size)()\n'
     '    written = c.c_uint64()\n'
     '    call(operation, *arguments, buffer, c.c_uint64(size - 1), c.byref(written))\n'
     '    return bytes(bytearray(buffer)[: written.value])\n'
     '\n'
     '\n'
     'def two_call_text',
     "tests.test_cnb_format"),
    ("buffer: trim the returned text by one byte",
     "src/_cna_native/cnb_support.py",
     '    raw = bytes(buffer.raw[: written.value])\n'
     '    try:\n'
     '        return raw.decode("utf-8")\n'
     '    except UnicodeDecodeError as error:\n'
     '        raise ValueError(f"{what} is not well-formed UTF-8") from error\n'
     '\n'
     '\n'
     'def two_call_bytes',
     '    raw = bytes(buffer.raw[: max(written.value - 1, 0)])\n'
     '    try:\n'
     '        return raw.decode("utf-8")\n'
     '    except UnicodeDecodeError as error:\n'
     '        raise ValueError(f"{what} is not well-formed UTF-8") from error\n'
     '\n'
     '\n'
     'def two_call_bytes',
     "tests.test_cnb_format"),
    ("integers: let a too-wide value through instead of refusing",
     "src/_cna_native/cnb_support.py",
     '    if not low <= value <= high:\n'
     '        raise ValueError(f"{what} must be in {low}..{high}, got {value}")\n'
     '    return int(value)',
     '    if not low <= value <= high:\n'
     '        return int(value) & high if low == 0 else int(value)\n'
     '    return int(value)',
     "tests.test_cnb_format"),
    # --- textures ---
    ("texture: read a level from the wrong representation",
     "src/cna/extensions/content/textures.py",
     '            (self._value,\n'
     '             c.c_uint64(_support.checked(representation, "uint64", "representation")),\n'
     '             c.c_uint64(_support.checked(level, "uint64", "level"))))',
     '            (self._value,\n'
     '             c.c_uint64(0),\n'
     '             c.c_uint64(_support.checked(level, "uint64", "level"))))',
     "tests.test_cnb_codecs"),
    ("texture: swap width and height when building from RGBA",
     "src/cna/extensions/content/textures.py",
     '            c.c_uint32(_support.checked(width, "uint32", "width")),\n'
     '            c.c_uint32(_support.checked(height, "uint32", "height")),\n'
     '            pointer, c.c_uint64(count))',
     '            c.c_uint32(_support.checked(height, "uint32", "height")),\n'
     '            c.c_uint32(_support.checked(width, "uint32", "width")),\n'
     '            pointer, c.c_uint64(count))',
     "tests.test_cnb_codecs"),
    ("texture: always select the first representation",
     "src/cna/extensions/content/textures.py",
     '        return int(index.value) if found.value else None',
     '        return 0',
     "tests.test_cnb_codecs"),
    # --- sound ---
    ("sound: swap the sample rate and the channel count",
     "src/cna/extensions/content/audio.py",
     '        return cls(int(value.format), int(value.sample_rate), int(value.channels),',
     '        return cls(int(value.format), int(value.channels), int(value.sample_rate),',
     "tests.test_cnb_codecs"),
    ("sound: report the frame count as the byte count",
     "src/cna/extensions/content/audio.py",
     '        value.frame_count = _support.checked(self.frame_count, "uint32", "frame_count")',
     '        value.frame_count = _support.checked(self.frame_count * 2, "uint32", "frame_count")',
     "tests.test_cnb_codecs"),
    # --- sprite font ---
    ("font: swap two kerning fields",
     "src/cna/extensions/content/fonts.py",
     '        value.kerning.x = float(self.kerning.X)\n'
     '        value.kerning.y = float(self.kerning.Y)',
     '        value.kerning.x = float(self.kerning.Y)\n'
     '        value.kerning.y = float(self.kerning.X)',
     "tests.test_cnb_codecs"),
    ("font: read the cropping rectangle as the glyph bounds",
     "src/cna/extensions/content/fonts.py",
     '            bounds=Rectangle(int(value.glyph_bounds.x), int(value.glyph_bounds.y),\n'
     '                             int(value.glyph_bounds.width), int(value.glyph_bounds.height)),',
     '            bounds=Rectangle(int(value.cropping.x), int(value.cropping.y),\n'
     '                             int(value.cropping.width), int(value.cropping.height)),',
     "tests.test_cnb_codecs"),
    # --- media ---
    ("video: swap the frame width and height",
     "src/cna/extensions/content/media.py",
     '    info.width = _support.checked(video.width, "uint32", "width")\n'
     '    info.height = _support.checked(video.height, "uint32", "height")',
     '    info.width = _support.checked(video.height, "uint32", "height")\n'
     '    info.height = _support.checked(video.width, "uint32", "width")',
     "tests.test_cnb_codecs"),
    ("song: read the display name as the stream reference",
     "src/cna/extensions/content/media.py",
     '        stream_reference=_support.sized_text(\n'
     '            "cna_cnb_decode_song_stream_reference_size",\n'
     '            "cna_cnb_decode_song_stream_reference", (handle,), "song stream reference"),',
     '        stream_reference=_support.sized_text(\n'
     '            "cna_cnb_decode_song_name_size",\n'
     '            "cna_cnb_decode_song_name", (handle,), "song stream reference"),',
     "tests.test_cnb_codecs"),
    # --- curve ---
    ("curve: swap the pre-loop and post-loop behaviours",
     "src/cna/extensions/content/curves.py",
     '        _support.call("cna_curve_set_pre_loop", self.value,\n'
     '                      c.c_uint32(int(curve.PreLoop)))\n'
     '        _support.call("cna_curve_set_post_loop", self.value,\n'
     '                      c.c_uint32(int(curve.PostLoop)))',
     '        _support.call("cna_curve_set_pre_loop", self.value,\n'
     '                      c.c_uint32(int(curve.PostLoop)))\n'
     '        _support.call("cna_curve_set_post_loop", self.value,\n'
     '                      c.c_uint32(int(curve.PreLoop)))',
     "tests.test_cnb_codecs"),
    ("curve: swap a key's two tangents",
     "src/cna/extensions/content/curves.py",
     '                native.tangent_in = float(key.TangentIn)\n'
     '                native.tangent_out = float(key.TangentOut)',
     '                native.tangent_in = float(key.TangentOut)\n'
     '                native.tangent_out = float(key.TangentIn)',
     "tests.test_cnb_codecs"),
    # --- animation ---
    ("clip: swap a keyframe's translation and scale",
     "src/cna/extensions/content/primitives.py",
     '            translation=(float(value.translation.x), float(value.translation.y),\n'
     '                         float(value.translation.z)),',
     '            translation=(float(value.scale.x), float(value.scale.y),\n'
     '                         float(value.scale.z)),',
     "tests.test_cnb_codecs"),
    ("clip: drop every track after the first",
     "src/cna/extensions/content/animation.py",
     '        return tuple(self.track(index) for index in range(self.track_count))',
     '        return tuple(self.track(index) for index in range(min(self.track_count, 1)))',
     "tests.test_cnb_codecs"),
    # --- model ---
    ("model: report every bone's parent as the root",
     "src/cna/extensions/content/model.py",
     '        return CnbBone(index=int(index), name=name, parent=int(value.parent),',
     '        return CnbBone(index=int(index), name=name, parent=-1,',
     "tests.test_cnb_model"),
    ("model: sort a mesh's part indices instead of keeping draw order",
     "src/cna/extensions/content/model.py",
     '            part_indices=_support.two_call_uint32s(\n'
     '                "cna_cnb_model_copy_mesh_part_indices", (self._value, position)))',
     '            part_indices=tuple(sorted(_support.two_call_uint32s(\n'
     '                "cna_cnb_model_copy_mesh_part_indices", (self._value, position)))))',
     "tests.test_cnb_model"),
    ("model: truncate a morph delta stream by three values",
     "src/cna/extensions/content/model.py",
     '        return _support.two_call_floats(\n'
     '            "cna_cnb_model_copy_morph_target_deltas",\n'
     '            (self._value, c.c_uint64(_support.checked(part, "uint64", "part")),\n'
     '             c.c_uint64(_support.checked(target, "uint64", "target")),\n'
     '             c.c_uint32(_support.checked(int(stream), "uint32", "stream"))))',
     '        return _support.two_call_floats(\n'
     '            "cna_cnb_model_copy_morph_target_deltas",\n'
     '            (self._value, c.c_uint64(_support.checked(part, "uint64", "part")),\n'
     '             c.c_uint64(_support.checked(target, "uint64", "target")),\n'
     '             c.c_uint32(_support.checked(int(stream), "uint32", "stream"))))[:-3]',
     "tests.test_cnb_model"),
    ("model: read every morph delta stream as positions",
     "src/cna/extensions/content/model.py",
     '             c.c_uint32(_support.checked(int(stream), "uint32", "stream"))))\n'
     '\n'
     '    def set_morph_weights',
     '             c.c_uint32(0)))\n'
     '\n'
     '    def set_morph_weights',
     "tests.test_cnb_model"),
    ("model: read the inverse bind pose as the bind pose",
     "src/cna/extensions/content/model.py",
     '            bind_pose=matrices(SkeletonMatrixSet.BindPose),',
     '            bind_pose=matrices(SkeletonMatrixSet.InverseBindPose),',
     "tests.test_cnb_model"),
    ("model: report a part's index bytes as its vertex bytes",
     "src/cna/extensions/content/model.py",
     '            vertex_bytes=self.part_vertex_bytes(index),',
     '            vertex_bytes=self.part_index_bytes(index),',
     "tests.test_cnb_model"),
    ("model: transpose every bone transform",
     "src/cna/extensions/content/model.py",
     '    return tuple(float(getattr(matrix, f"M{row}{column}"))\n'
     '                 for row in range(1, 5) for column in range(1, 5))',
     '    return tuple(float(getattr(matrix, f"M{column}{row}"))\n'
     '                 for row in range(1, 5) for column in range(1, 5))',
     "tests.test_cnb_model"),
    # --- importers and the compiler ---
    ("importer: apply a colour key even when none was asked for",
     "src/cna/extensions/content/importers.py",
     '    if color_key is None:\n'
     '        options.has_color_key = 0',
     '    if color_key is None:\n'
     '        options.has_color_key = 1',
     "tests.test_cnb_pipeline"),
    ("compiler: drop the last absorbed file",
     "src/cna/extensions/content/compiler.py",
     '        count = _support.out_u64(\n'
     '            "cna_cnb_cnj_result_get_absorbed_file_count", self._value)\n'
     '        return tuple(',
     '        count = max(_support.out_u64(\n'
     '            "cna_cnb_cnj_result_get_absorbed_file_count", self._value) - 1, 0)\n'
     '        return tuple(',
     "tests.test_cnb_pipeline"),
    ("compiler: report external references in reverse order",
     "src/cna/extensions/content/compiler.py",
     '        count = _support.out_u64(\n'
     '            "cna_cnb_cnj_result_get_external_reference_count", self._value)\n'
     '        return tuple(',
     '        count = _support.out_u64(\n'
     '            "cna_cnb_cnj_result_get_external_reference_count", self._value)\n'
     '        return tuple(reversed(tuple(',
     "tests.test_cnb_model"),
    ("compiler: pass the content root as the document path",
     "src/cna/extensions/content/compiler.py",
     '    root_view, keep_root = _support.string_view(\n'
     '        "" if content_root is None else os.fspath(content_root), "content_root")',
     '    root_view, keep_root = _support.string_view("", "content_root")',
     "tests.test_cnb_pipeline"),
    # --- loaders ---
    ("loader: resolve by number, skipping the type-name check",
     "src/cna/extensions/content/loaders.py",
     '        _support.out_handle(\n'
     '            "cna_cnb_loader_registry_resolve_for_document", document._value),',
     '        _support.out_handle(\n'
     '            "cna_cnb_loader_registry_find", c.c_uint32(0), None),',
     "tests.test_cnb_pipeline"),
    ("loader: let an exception escape the callback as a success",
     "src/cna/extensions/content/loaders.py",
     '            _FAILURES.append(error)\n'
     '            return 5',
     '            _FAILURES.append(error)\n'
     '            return 0',
     "tests.test_cnb_loaders"),
    ("loader: hold the Python callable weakly",
     "src/cna/extensions/content/loaders.py",
     '        self._loader = loader\n'
     '        self._closed = False',
     '        import weakref\n'
     '        self._loader_ref = weakref.ref(loader)\n'
     '        self._loader = property(lambda self: self._loader_ref())\n'
     '        self._closed = False',
     "tests.test_cnb_loaders"),
    ("registry: report every asset type as registered",
     "src/cna/extensions/content/loaders.py",
     '    return _support.out_bool(\n'
     '        "cna_cnb_loader_registry_is_registered",\n'
     '        c.c_uint32(_support.checked(int(asset_type_id), "uint32", "asset_type_id")))',
     '    return True',
     "tests.test_cnb_pipeline"),
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
            for cache in (ROOT / "src").rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
            passed, stderr = run(module)
        finally:
            path.write_text(original, encoding="utf-8")
            for cache in (ROOT / "src").rglob("__pycache__"):
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
