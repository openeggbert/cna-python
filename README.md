# CNA-Python

CNA-Python is a pre-alpha, measured Python projection of the XNA 4.0 API over
the canonical CNA C ABI. It is no longer a simulated scaffold: the implemented
game, graphics, texture, SpriteBatch, and input paths call a real exact ABI
0.7.0 native runtime.

```text
Python game
    -> Microsoft.Xna.Framework.*
    -> private _cna_native ctypes layer
    -> CNA stable C ABI
    -> CNA C++
```

The current dependency-complete foundation provides locally complete,
binary32-aware core math/value, geometry/intersection, and non-touch input
families; deterministic events and disposal; a real `Game` lifecycle;
`GraphicsDevice.Clear`, PNG/JPEG `Texture2D.FromStream`, Color texture transfer,
scaled/rotated `SpriteBatch.Draw`, viewport access, and CNA-backed keyboard,
mouse, and gamepad polling. The maintained sibling starter completes 60- and
600-frame installed-wheel runs with a moving 128×128 PNG.

This is not a complete XNA binding. The strict verifier currently exposes 51 of
257 reference types; 41 are locally zero-diagnostic. Its full check
intentionally remains red for 206 missing and 10 partial types. Stub-backed
measurement now covers fields, properties, overloads, mapped parameter and
return types, nullability, ref/out transformations, generics, interfaces,
runtime/stub consistency, events, operators, and Python language rules. Every
structural mismatch category and the unmeasured-category counter are zero.
`ContentManager.Load` explicitly rejects XNB loads rather than fabricating an
asset. Effects, 3D buffers/drawing, audio, media, storage, touch, and many other
families remain future dependency-complete milestones. No native library is
bundled in the wheel.

## Running

Build or install `cna-python==0.1.0.dev0`, then select an exact CNA ABI 0.7.0
library with an absolute path:

```bash
export CNA_NATIVE_LIBRARY=/absolute/path/to/libcna_c_api.so
python3 -m unittest discover -v
```

`CNA_NATIVE_DIR` may instead name an absolute directory containing the
platform library name. Relative paths and ABI mismatches are rejected before
the native API is imported.

## Measured platform status

| Platform/backend | Evidence |
| --- | --- |
| Linux x86-64, HEADLESS renderer, NULL audio | Runtime verified for the selected 2D/input slice, ownership stress, and 60/600 frames |
| Linux windowed/GPU renderer | Not yet verified |
| Windows | Not yet verified |
| macOS | Not yet verified |
| Android / iOS | Not verified |
| Web / Pyodide | Not supported by the current native-library architecture |

HEADLESS input calls prove the CNA routes and state conversion, not the
presence of physical devices. NULL audio is only an artifact qualification;
this Python milestone binds no audio API.

The normative language mapping is in
[`docs/xna-python-mapping.md`](docs/xna-python-mapping.md), architecture and
ownership in [`docs/architecture.md`](docs/architecture.md), ABI evidence in
[`docs/cna-abi-audit.md`](docs/cna-abi-audit.md), pure/input evidence in
[`docs/core-value-evidence.md`](docs/core-value-evidence.md) and
[`docs/input-evidence.md`](docs/input-evidence.md), and the tactical handoff in
[`NEXT.md`](NEXT.md).

## License

CNA-Python is licensed under the [Microsoft Public License](LICENSE), matching
CNA. See [NOTICE.md](NOTICE.md).
