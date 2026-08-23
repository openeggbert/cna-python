# CNA-Python

CNA-Python is a pre-alpha, measured Python projection of the XNA 4.0 API over
the canonical CNA C ABI. It is a real exact-ABI-0.7 runtime binding, not a
simulated scaffold.

```text
Python game
    -> Microsoft.Xna.Framework.*
    -> private _cna_native ctypes layer
    -> CNA stable C ABI
    -> CNA C++
```

The dependency-complete foundation includes core math/value and geometry,
non-touch input, the Game component/service/window object model, selected 2D
graphics device/state/resources, Texture2D, buffers, render targets,
SpriteBatch, SpriteFont, and a genuine managed Content/XNB object-graph reader.
Content supports exact reader tables and versions, custom readers, existing
instances, deferred shared resources, external references, cache/Unload/
rollback ownership, native Texture2D/SpriteFont/buffer graphs, and persistent
multi-frame LZX decompression. See
[`docs/content-xnb.md`](docs/content-xnb.md).

Foundation Milestone 5 adds the complete Effect/stock-effect/Model dependency
closure: real native reflection identities and typed parameter/annotation
codecs, five native stock effects, Texture3D/TextureCube ABI routes, and legal
uncompressed plus LZX-compressed Model XNB graphs over shared buffers and
BasicEffect. Model.Draw uses the ordinary pass and indexed-draw pipeline. See
[`docs/effect-model-evidence.md`](docs/effect-model-evidence.md).

The maintained sibling starter completes 60- and 600-frame installed-wheel
runs with both a raw PNG and a legal synthetic Texture2D XNB.

This is not a complete XNA binding. The strict verifier exposes 161 of 257
reference types, all locally zero-diagnostic. Its full check intentionally
remains red for 96 wholly missing future types; missing members and partial
types are zero. Every structural mismatch, native leak, allowlist, and
unmeasured-category counter is zero. Audio, media, storage, touch, PackedVector,
Curve, Design, and unrelated Graphics families remain future
dependency-complete milestones. No native library is bundled in the wheel.

## Running

Build or install `cna-python==0.1.0.dev0`, then select an exact CNA ABI 0.7.0
library with an absolute path:

```bash
export CNA_NATIVE_LIBRARY=/absolute/path/to/libcna_c_api.so
python3 -m unittest discover -v
```

`CNA_NATIVE_DIR` may instead name an absolute directory containing the platform
library name. Relative paths and ABI mismatches are rejected before the native
API is imported.

## Measured platform status

| Platform/backend | Evidence |
| --- | --- |
| Linux x86-64, HEADLESS renderer, NULL audio | Native lifecycle, Effect/stock-effect state and Apply, Model XNB/draw command paths, ownership stress, and raw-PNG plus XNB 60/600 frames verified |
| Linux windowed/GPU renderer | Not yet verified |
| Windows | Not yet verified |
| macOS | Not yet verified |
| Android / iOS | Not verified |
| Web / Pyodide | Not supported by the current native-library architecture |

HEADLESS command completion is not visible GPU output. It also cannot prove OS
window transitions, deterministic device loss, or physical input hardware.
Those distinctions are recorded in
[`docs/generated/runtime-capabilities.md`](docs/generated/runtime-capabilities.md).

The normative language mapping is in
[`docs/xna-python-mapping.md`](docs/xna-python-mapping.md), architecture and
ownership in [`docs/architecture.md`](docs/architecture.md), ABI evidence in
[`docs/cna-abi-audit.md`](docs/cna-abi-audit.md), machine-readable capability
source in [`docs/runtime-capabilities.json`](docs/runtime-capabilities.json),
and the tactical handoff in [`NEXT.md`](NEXT.md).

## License

CNA-Python is licensed under the [Microsoft Public License](LICENSE), matching
CNA. See [NOTICE.md](NOTICE.md).
