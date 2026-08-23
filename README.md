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

Foundation Milestone 6 adds the complete 19-type Audio/XACT family: native
SoundEffect and instances, dynamic copied-buffer streaming and owner-thread
callbacks, real microphone enumeration, and the AudioEngine/category/bank/cue
ownership graph. Multi-listener mixing remains an explicit CNA ABI-0.7 blocker;
physical capture is hardware-pending and successful authored XACT playback is
asset-pending. See [`docs/audio-xact-evidence.md`](docs/audio-xact-evidence.md).

Foundation Milestone 7 completes the remaining managed/value layer: all six
Curve types with XNA binary32 Hermite, loop, tangent, ordering, and clone
semantics; both PackedVector interfaces plus all seventeen bit-exact packed
structs; and all thirteen Design converters through a documented Python-native
TypeConverter protocol. This milestone adds no CNA imports. See
[`docs/curve-evidence.md`](docs/curve-evidence.md),
[`docs/packed-vector-evidence.md`](docs/packed-vector-evidence.md), and
[`docs/design-evidence.md`](docs/design-evidence.md).

The maintained sibling starter completes 60- and 600-frame installed-wheel
runs with both a raw PNG and a legal synthetic Texture2D XNB.

This is not a complete XNA binding. The strict verifier exposes 218 of 257
reference types, all locally zero-diagnostic. Its full check intentionally
remains red for 39 wholly missing runtime/platform types; missing members and
partial types are zero. Every structural mismatch, native leak, allowlist, and
unmeasured-category counter is zero. Media, Storage, Touch, GamerServices,
FrameworkDispatcher, OcclusionQuery, and RenderTargetCube remain future
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
| Linux x86-64, HEADLESS renderer, NULL audio | Native lifecycle, Effect/Model paths, SoundEffect/dynamic Audio routes, zero-device microphone enumeration, Audio/XACT ownership stress, and raw-PNG plus XNB 60/600 frames verified |
| Linux windowed/GPU renderer | Not yet verified |
| Windows | Not yet verified |
| macOS | Not yet verified |
| Android / iOS | Not verified |
| Web / Pyodide | Not supported by the current native-library architecture |

HEADLESS command completion is not visible GPU output. NULL audio does not prove
audible playback or physical microphone capture, and no legal authored XACT
bank fixture is available. The qualified host also cannot prove OS window
transitions, deterministic device loss, or physical input hardware.
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
