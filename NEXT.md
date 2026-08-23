# CNA-Python tactical handoff

Date: 2026-08-23.

`MILESTONE_7_COMPLETE=true`

Foundation Milestone 7 is complete. The entire remaining managed/value layer—
Curve (6), PackedVector (19), and Design (13)—is structurally complete and
behavior-qualified. No Media, Storage, Touch, GamerServices,
FrameworkDispatcher, OcclusionQuery, or RenderTargetCube work was started. CNA
was not modified and the native ABI surface did not grow.

## Strict result

```text
                               M7 START  M7 FINAL
REFERENCE_TYPES                      257       257
REFERENCE_MEMBERS                   2964      2964
EXPECTED_PYTHON_TYPES                257       257
EXPECTED_PYTHON_MEMBERS             2887      2887
TARGET_TYPES                         180       218
TARGET_MEMBERS                      1772      2061
TOTAL_DIAGNOSTICS                     77        39
MISSING_TYPE                          77        39
MISSING_MEMBER                         0         0
COMPLETE_TYPES                       180       218
PARTIAL_TYPES                          0         0
MISSING_TYPES                         77        39
```

All 39 diagnostics are whole future runtime/platform types. Every one of the
38 Milestone 7 types reports `status=complete`, `diagnostics=0`. Normal strict
`--check` is nonzero only because those 39 types remain absent.

```text
UNEXPECTED_TYPE=0
UNEXPECTED_MEMBER=0
TYPE_KIND_MISMATCH=0
BASE_MAPPING_MISMATCH=0
INTERFACE_MAPPING_MISMATCH=0
FIELD_MAPPING_MISMATCH=0
PROPERTY_MAPPING_MISMATCH=0
METHOD_SIGNATURE_MAPPING_MISMATCH=0
PARAMETER_MAPPING_MISMATCH=0
RETURN_MAPPING_MISMATCH=0
OVERLOAD_MAPPING_MISMATCH=0
GENERIC_MAPPING_MISMATCH=0
ENUM_VALUE_MISMATCH=0
FLAGS_MAPPING_MISMATCH=0
EVENT_MAPPING_MISMATCH=0
OPERATOR_MAPPING_MISMATCH=0
LANGUAGE_MAPPING_MISMATCH=0
INTERNAL_TYPE_LEAK=0
RAW_HANDLE_LEAK=0
PUBLIC_NATIVE_FFI_LEAK=0
ALLOWLIST_ENTRIES=0
UNMEASURED_STRUCTURAL_CATEGORY=0
ZERO_DIAGNOSTIC_TYPES=218
```

## Curve

The complete six types are `Curve`, `CurveContinuity`, `CurveKey`,
`CurveKeyCollection`, `CurveLoopType`, and `CurveTangent`.

- CurveKey stores all scalar values as binary32. CompareTo sorts only by
  Position and preserves the reference NaN branch behavior. Equality, hash,
  operators, Clone, shallow copy, and deep copy are implemented.
- CurveKeyCollection is a complete mutable collection. It maintains ascending
  Position order, inserts a new equal-position key after existing equals, and
  permits duplicate/equal objects. Index/replacement, Add, Remove, RemoveAt,
  Clear, Contains, IndexOf, CopyTo, Clone, Count, IsReadOnly, and iteration are
  covered. Collection Clone is independent but shallow in key references,
  matching XNA; Curve.Clone follows the same rule.
- Evaluate covers empty, singleton, exact-key, between-key cubic Hermite, Step,
  duplicate-position, and zero-range behavior. Segment fraction uses the XNA
  double intermediate followed by binary32 narrowing; Hermite terms and
  accumulation preserve binary32 operation order.
- PreLoop/PostLoop implement Constant, Cycle, CycleOffset, Oscillate, and Linear.
  Tests include both sides, exact multiples, negative cycles, parity, duplicate
  positions, and zero total range.
- ComputeTangent/ComputeTangents implement Flat, Linear, and Smooth for first,
  middle, last, singleton, non-uniform, and duplicate-position cases.

Focused tests: 10 methods. `PURE_XNA_DERIVED` corpus observations: 10, with
exact binary32 bit strings. See `docs/curve-evidence.md`.

## PackedVector

The non-generic CLR identity remains public `IPackedVector`. The colliding
`IPackedVector<TPacked>` identity is formally and machine-readably rewritten as
`IPackedVectorOfT[TPacked]`. The two are distinct runtime classes; the generic
TypeVar/base relation is measured, and there is no alias, allowlist, or
synthetic XNA identity.

All seventeen concrete types are complete: `Alpha8`, `Bgr565`, `Bgra4444`,
`Bgra5551`, `Byte4`, `HalfSingle`, `HalfVector2`, `HalfVector4`,
`NormalizedByte2`, `NormalizedByte4`, `NormalizedShort2`, `NormalizedShort4`,
`Rg32`, `Rgba1010102`, `Rgba64`, `Short2`, and `Short4`.

Exact PackedValue storage:

- UInt8: Alpha8;
- UInt16: Bgr565, Bgra4444, Bgra5551, HalfSingle, NormalizedByte2;
- UInt32: Byte4, HalfVector2, NormalizedByte4, NormalizedShort2, Rg32,
  Rgba1010102, Short2;
- UInt64: HalfVector4, NormalizedShort4, Rgba64, Short4.

Negative, Boolean, and oversized assignments are rejected. Every struct has
the selected constructors/conversions, PackedValue, interface mutation,
fresh-vector unpacking, Equals/hash/hex ToString/operators, and shallow/deep
value-copy behavior.

Packing is exact-bit, not approximate-vector compatibility. Binary32
intermediates, clamping, nearest-even rounding, masks/shifts, BGR/RGBA/alpha
positions, byte/short lane order, signed normalization, reserved signed minima,
and sign extension are verified. NaN follows the XNA zero path; infinities
saturate.

XNA half conversion is explicit and historical, not IEEE binary16:

```text
0x0000 -> +0
0x8000 -> -0
0x0001 -> smallest subnormal
0x7C00 -> 65536
0x7FFF -> 131008
Infinity / NaN input -> signed 0x7FFF saturation
```

Subnormal/normal boundaries, maximum finite, overflow, both infinities, NaN,
signed zero, and tie cases are covered. Python `struct.pack("e")` is not used.

Focused tests: 10 methods. `PURE_XNA_DERIVED` corpus observations: 17, one per
concrete type; each records zero, ordinary, boundary, clamp, round-trip,
PackedValue identity, and equality. HalfSingle adds dedicated subnormal,
non-finite, and exponent-31 assertions. See `docs/packed-vector-evidence.md`.

## Design

All thirteen types are complete: `MathTypeConverter`, `BoundingBoxConverter`,
`BoundingSphereConverter`, `ColorConverter`, `MatrixConverter`, `PlaneConverter`,
`PointConverter`, `QuaternionConverter`, `RayConverter`, `RectangleConverter`,
`Vector2Converter`, `Vector3Converter`, and `Vector4Converter`.

Formal projection:

```text
System.Type                      -> type
CultureInfo                      -> explicit culture-name str; None=invariant
IDictionary                      -> ordered Mapping[str, object]
PropertyDescriptorCollection     -> immutable ordered snapshot Mapping
InstanceDescriptor               -> (callable, immutable argument tuple)
ExpandableObjectConverter        -> private _MathTypeConverterBase flattening
ITypeDescriptorContext           -> omitted: selected XNA IL does not observe it
Attribute[] GetProperties filter -> omitted: fixed descriptor set ignores it
```

No public System.ComponentModel package or support type exists. Context and
attribute omissions are verifier rules. Mapping duplicate keys are
unrepresentable; Python resolves them before the converter sees a mapping.

String parsing support:

| Converter | Parse string | Format string | Descriptor tuple |
| --- | --- | --- | --- |
| MathTypeConverter | capability only; no concrete target | yes | yes |
| Point, Color, Quaternion, Vector2/3/4 | yes | yes | yes |
| BoundingBox/Sphere, Matrix, Plane, Ray, Rectangle | no | yes | yes |

Color uses byte-domain R/G/B/A with no named-color grammar. Unsupported input
converters reject strings, but formatting falls back to the exact XNA value
ToString shape.

Culture is deterministic and thread-safe: invariant/root/en-US use decimal `.`
and list `,`; de-DE uses decimal `,` and list `;`. Legacy seven-significant-
digit Single formatting, exponent thresholds, NaN/infinity tokens, signed zero,
whitespace, overflow, wrong culture, and list/decimal separator interaction are
covered without process-global locale mutation.

Exact property order:

```text
Point/Vector2       X, Y
Vector3             X, Y, Z
Vector4/Quaternion  X, Y, Z, W
Rectangle           X, Y, Width, Height
Color               R, G, B, A
BoundingBox         Min, Max
BoundingSphere      Center, Radius
Plane               Normal, D
Ray                 Position, Direction
Matrix              Translation, M11..M44
```

Nested values are snapshots. CreateInstance uses explicit typed required-key
lookups, rejects missing/None/wrong values, ignores unrelated extras, and copies
nested values. Matrix consumes only the sixteen scalar M fields so Translation
is not applied twice. Every descriptor is executable as `callable(*arguments)`
and reconstructs an XNA-equal value without reflection.

Focused tests: 10 methods. `PURE_XNA_DERIVED` corpus observations: 21. See
`docs/design-evidence.md` and the formal protocol in
`docs/xna-python-mapping.md`.

## Behavior

```text
                         M7 START  M7 FINAL
OBSERVATIONS                   119       167
ASSERTIONS                     538       925
FAILURES                         0         0

CURVE_OBSERVATIONS=10
PACKEDVECTOR_OBSERVATIONS=17
DESIGN_OBSERVATIONS=21
PROVENANCE=PURE_XNA_DERIVED
```

The expected results come from pinned XNA metadata plus IL/reference algorithm
analysis, not CNA output. The generated report is
`docs/generated/behavior-corpus-report.json`.

## ABI and native regression

Milestone 7 adds no native function or layout:

```text
BOUND_FUNCTIONS=471
CTYPES_SIGNATURE_MEASUREMENTS=471
C_LAYOUT_MEASUREMENTS=708
CTYPES_LAYOUT_MEASUREMENTS=708
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
ABI=0.7.0 / 0x00000700
```

Qualified artifact:

```text
CNA artifact source revision=a09196a6477f69a7a57c8364f990658d31531a5b
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
```

Current CNA HEAD was inspected read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`; it was not changed. The full
native, Content, Effect/Model, and Audio ownership stress suites pass at 20
cycles (dynamic Audio callbacks: 50) with zero crashes, observed UAF, or
double-free. Sanitizers were not run.

## Tests and package

```text
COMPILEALL=PASS
UNITTESTS=128 total, 126 pass, 2 optional-fixture skips
VERIFIER_SELF_TESTS=4 PASS
FOCUSED_M7_TEST_METHODS=30 PASS
STRICT_REPORT=PASS
LEAK_ONLY=PASS
STRICT_CHECK=EXPECTED_NONZERO_ONLY_FOR_39_MISSING_TYPES
```

Version remains `0.1.0.dev0`. Final artifacts:

```text
WHEEL_FILENAME=cna_python-0.1.0.dev0-py3-none-any.whl
WHEEL_SHA256=2c7fea1c11dd402e67464e1f52adc83e7c866a3069723263019aa38683217439
WHEEL_ENTRIES=62
SDIST_FILENAME=cna_python-0.1.0.dev0.tar.gz
SDIST_SHA256=0c59da88d41a2150de4bd1a6d76495be79e63027802fdbc3c59abceafa8c33a2
SDIST_ENTRIES=148
FORBIDDEN_WHEEL_ENTRIES=0
FORBIDDEN_SDIST_ENTRIES=0
ABSOLUTE_DEVELOPER_PATHS=0
BUNDLED_NATIVE_LIBRARIES=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0
```

The wheel contains `_curve.py`, both Design modules and stub, and both
PackedVector modules and stub. It contains no native library.

The exact final wheel above was installed with `--no-index --no-deps` into
fresh venvs with no editable install, source import, sibling runtime dependency,
or PYTHONPATH:

```text
ISOLATED_IMPORT_PROBE=PASS
ISOLATED_COMPILE_PROBE=PASS
GENERATED_SMOKE_60=PASS
GENERATED_STABILITY_600=PASS
MAINTAINED_SMOKE_60=PASS
MAINTAINED_STABILITY_600=PASS
ABSOLUTE_DEVELOPER_PATHS=0
SIBLING_SOURCE_DEPENDENCIES=0
PYTHONPATH_SOURCE_DEPENDENCIES=0
TEMPLATE_SOURCE_CHANGED=NO
```

The maintained template remains the raw PNG plus Texture2D XNB 2D lifecycle
canary. No Curve, PackedVector, or Design demo was added.

## Remaining exact inventory

The regenerated 39 whole missing runtime/platform types are:

- Framework (1): `FrameworkDispatcher`;
- GamerServices (1): `GamerServicesComponent`;
- Graphics (2): `OcclusionQuery`, `RenderTargetCube`;
- Touch (8): `GestureSample`, `GestureType`, `TouchCollection`,
  `TouchCollection.Enumerator`, `TouchLocation`, `TouchLocationState`,
  `TouchPanel`, `TouchPanelCapabilities`;
- Storage (3): `StorageContainer`, `StorageDevice`,
  `StorageDeviceNotConnectedException`;
- Media (24): `Album`, `AlbumCollection`, `Artist`, `ArtistCollection`, `Genre`,
  `GenreCollection`, `MediaLibrary`, `MediaPlayer`, `MediaQueue`, `MediaSource`,
  `MediaSourceType`, `MediaState`, `Picture`, `PictureAlbum`,
  `PictureAlbumCollection`, `PictureCollection`, `Playlist`,
  `PlaylistCollection`, `Song`, `SongCollection`, `Video`, `VideoPlayer`,
  `VideoSoundtrackType`, `VisualizationData`.

The authoritative inventory is in
`docs/generated/missing-type-inventory.json` and `.md`. Milestone 7 stops here;
no next runtime family has been started.

## Reproduction

```bash
python3 -m compileall -q src tests tools
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # nonzero only for 39 absent types
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/generate_runtime_capabilities.py
python3 tools/audit_cna_abi.py --cna-root /qualified/cna/source --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/native_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/content_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/effect_model_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/audio_ownership_stress.py --cycles 20 --callback-cycles 50
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```
