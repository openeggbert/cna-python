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

The dependency-complete foundation now includes core math/value and geometry,
non-touch input, the `Game` component/service/window object model, graphics
adapter and presentation types, device states and collections, textures and
PNG/JPEG encoding, explicit vertex codecs and vertex/index buffers, 2D render
targets, native draw/reset/present routes, and SpriteFont metrics/DrawString.
The maintained sibling starter still stays deliberately small and completes
60- and 600-frame installed-wheel runs with a moving 128x128 PNG.

This is not a complete XNA binding. The strict verifier exposes 115 of 257
reference types; 114 are locally zero-diagnostic. Its full check intentionally
remains red for 142 missing types and the two intentionally deferred
`ContentManager` members, `OpenStream` and `ReadAsset`. Every structural
mismatch, native leak, allowlist, and unmeasured-category counter is zero.
Full Content/XNB, effects/models, audio, media, storage, touch, Texture3D/Cube,
and broad 3D content remain future dependency-complete milestones. No native
library is bundled in the wheel.

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
| Linux x86-64, HEADLESS renderer, NULL audio | Native lifecycle, 2D/device/resource command paths, ownership stress, and 60/600 frames verified |
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
