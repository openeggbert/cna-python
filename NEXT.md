# CNA-Python tactical handoff

Date: 2026-08-23.

Foundation Milestone 4 is complete. CNA-Python now has a general-purpose XNA
4.0 Content/XNB architecture rather than an asset-name or Texture2D-only path.
All selected public Content types and TitleContainer are structurally complete;
there are no partial types or missing members anywhere in the current target.

## Strict before and after

```text
                                      BEFORE  AFTER
REFERENCE_TYPES                          257    257
REFERENCE_MEMBERS                       2964   2964
EXPECTED_PYTHON_TYPES                    257    257
EXPECTED_PYTHON_MEMBERS                 2887   2887
TARGET_TYPES                             115    126
TARGET_MEMBERS                          1465   1501
TOTAL_DIAGNOSTICS                        144    131
MISSING_TYPE                             142    131
MISSING_MEMBER                             2      0
COMPLETE_TYPES                           114    126
PARTIAL_TYPES                              1      0
MISSING_TYPES                            142    131
```

The predicted target-member count was not forced; 1,501 is the regenerated
authoritative mapping result. Every final mismatch/safety category is zero:

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
```

The normal strict `--check` remains nonzero only for 131 wholly absent future
types. Leak-only, stub/runtime, and verifier self-tests pass.

## Content public types

| Public type | Strict status | Managed status | Native status | Language limitations / blockers |
|---|---|---|---|---|
| `ContentManager` | COMPLETE, 0 diagnostics | VERIFIED: root normalization, cache, graph ownership, rollback, Unload/Dispose | VERIFIED: title route plus native resource graphs | Erased caller `Load[T]` cannot be runtime-enforced; reader-declared root shape is enforced. No implementation blocker. |
| `ContentReader` | COMPLETE, 0 diagnostics | VERIFIED: primitives, values, objects, raw objects, shared/external reads | N/A except resources constructed by readers | No-token `ReadRawObject[T]` cannot recover erased T and raises `NotImplementedError`; explicit-reader and tagged forms work. |
| `ContentSerializerAttribute` | COMPLETE, 0 diagnostics | VERIFIED defaults, setters, Clone independence | N/A | None. |
| `ContentSerializerCollectionItemNameAttribute` | COMPLETE, 0 diagnostics | VERIFIED value behavior | N/A | None. |
| `ContentSerializerIgnoreAttribute` | COMPLETE, 0 diagnostics | VERIFIED construction | N/A | None. |
| `ContentSerializerRuntimeTypeAttribute` | COMPLETE, 0 diagnostics | VERIFIED construction | N/A | None. |
| `ContentSerializerTypeVersionAttribute` | COMPLETE, 0 diagnostics | VERIFIED construction | N/A | None. |
| `ContentTypeReader` | COMPLETE, 0 diagnostics | VERIFIED target/version/initialize/read/existing-instance abstraction | N/A | None. |
| `ContentTypeReader<T>` (`ContentTypeReaderOfT[T]`) | COMPLETE, 0 diagnostics | VERIFIED deterministic concrete Generic-base target recovery | N/A | Subclasses with no recoverable concrete target fail explicitly; no public constructor token was invented. |
| `ContentTypeReaderManager` | COMPLETE, 0 diagnostics | VERIFIED reader identity, table order, initialization | N/A | None. |
| `ResourceContentManager` | COMPLETE, 0 diagnostics | VERIFIED Mapping/GetObject lookup, bytes/stream snapshot, disposal | Native objects still use ordinary readers/routes | CLR ResourceManager maps formally to `object`; no fake System.Resources package. |
| `TitleContainer` | COMPLETE, 0 diagnostics | VERIFIED lexical and resolved-path containment outside Game | VERIFIED CNA title-location/read routes during Game | None on qualified platform. |

`ContentLoadException` remains complete. `System.IO`, `System.Resources`, and
`System.ComponentModel` support packages were not fabricated.

## XNB architecture and behavior

- Header/container: Windows target byte, XNB version 5, supported flags,
  declared file size, compressed output size, truncation, and trailing data are
  validated. Unsupported platforms/versions fail as chained
  `ContentLoadException`.
- Reader table: exact structurally normalized assembly-qualified identities,
  1-based object tags, required identities, reader counts, exact versions,
  table identity, and initialization order are implemented. Fuzzy matching is
  never used.
- Custom readers: the private general registration bridge maps a serialized
  identity to any real `ContentTypeReader` subclass. The fixture proves
  discovery, version, Initialize, Read, existing instances, exceptions,
  shared callbacks, rollback, cache, and Unload without an asset-name branch.
- Existing instances: `CanDeserializeIntoExistingObject`, None/wrong instances,
  mutation, identity-preserving returns, and replacement returns are covered.
- Shared resources: declared count, deferred registration, index validation,
  multiple ordered fixups, null, callback failure, unresolved/truncated data,
  identity, and cleanup are covered.
- External references: resolution is relative to the containing asset and
  constrained beneath the Content root. Nested references, normalization,
  missing/wrong/circular targets, cache identity, rollback, shared resources,
  compressed targets, and Unload are covered.
- Cache/ownership: normalized case-insensitive keys provide repeated-Load,
  shared, and external identity. Disposables are deduplicated by Python
  identity; failures roll back uncommitted resources in reverse order.
- Failure fidelity: malformed headers/compression/tables/tags/fixups, unknown or
  wrong-version readers, wrong object shape, custom-reader errors, partial
  native construction, circular externals, and disposal errors retain useful
  exception chains.

## Built-in readers

Implemented private readers, because their runtime reader classes are not part
of the selected public profile:

- Boolean, Byte/SByte, Int16/UInt16, Int32/UInt32, Int64/UInt64, Single,
  Double, variable-width UTF-8 Char, String, and exactly representable TimeSpan;
- Vector2/3/4, Quaternion, Matrix, Color, Point, and Rectangle;
- List, Array, and Nullable over implemented reader identities;
- Texture2D, SpriteFont, VertexDeclaration, VertexBuffer, and IndexBuffer.

Texture2D parses SurfaceFormat, UInt32 dimensions, full mip graph, and exact
payload lengths. The CNA ABI 0.7 selected upload route is fully qualified for
`SurfaceFormat.Color`; other formats fail explicitly and DXT is never decoded
or relabeled. Multiple Color mip levels are tested.

SpriteFont parses the real atlas/glyph/cropping/character/line-spacing/spacing/
kerning/nullable-default-character graph and uses the existing public factory.
MeasureString, DrawString glyph submissions, missing/default character, cache,
Unload, and reverse atlas ownership all pass.

VertexDeclaration, VertexBuffer, and IndexBuffer use their exact layouts and
ordinary public/native constructors/transfers. Effects and Models were
intentionally not implemented because their complete public object graphs are
still absent; no private substitute objects are returned.

## ContentManager

- `OpenStream`: real normalized RootDirectory + asset + `.xnb` title path;
  fresh owned stream; no CWD fallback or extension guessing.
- `ReadAsset`: real header/decompression/table/object/shared-resource pipeline;
  owned stream closes after the graph is read; failures are chained.
- `Load`: returns the reader-selected root object, validates its declared reader
  shape, and caches normalized asset identity.
- `RootDirectory`: empty/nested behavior, mutation, malformed paths, traversal,
  absolute paths, and mixed separators are tested.
- `Unload`/`Dispose`: reverse-order, identity-deduplicated ownership with state
  cleared before callbacks, reload after unload, idempotence, and exception
  recovery.
- Generic erasure: Python cannot observe caller `T`; this narrow difference is
  recorded as `LANGUAGE_MAPPING_LIMITATION`, not hidden as a perpetual bug.

## LZX compressed XNB

The managed decoder maintains one 64 KiB state across XNA frames and supports
short and extended big-endian frame headers, 32 KiB frames, verbatim/aligned/
uncompressed LZX blocks, repeated offsets, and canonical Huffman tables.

Qualification includes:

```text
single frame=PASS
multi frame with persistent state=PASS
short and extended headers=PASS
truncation/invalid block/size/output/trailing-data negatives=PASS
independent real fixture byte comparisons=2 PASS
compressed primitive/custom/shared graphs=PASS
compressed Texture2D=PASS
compressed SpriteFont=PASS
compressed VertexDeclaration/VertexBuffer/IndexBuffer=PASS
external uncompressed -> compressed=PASS
external compressed -> uncompressed=PASS
external compressed -> compressed=PASS
cache/rollback/Unload after decompression=PASS
```

The XNA runtime does not use the Intel E8 transform for these files; a stream
requesting it is rejected explicitly. No third-party binary dependency or
Microsoft source/content was added.

## Behavior corpus

```text
OBSERVATIONS: 98 -> 108
ASSERTIONS: 413 -> 465
FAILURES: 0
PROVENANCE: pinned XNA metadata plus IL/algorithm analysis; platform-neutral
```

New groups cover serializer defaults/Clone, RootDirectory/disposed behavior,
ContentReader primitive/value decoding, cache identity, reader versions,
shared-fixup order, and external-reference normalization. HEADLESS filesystem
or native errors are not encoded as XNA golden observations.

## ABI evidence

Current CNA HEAD was rechecked read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. Its clean C-API build remains
blocked by the upstream renderer identity assertion `49 == 50`; CNA was not
modified.

Qualified artifact:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
ABI=0.7.0 / 0x00000700 exact
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
BOUND_FUNCTIONS: 186 -> 188
CTYPES_SIGNATURE_MEASUREMENTS: 186 -> 188
C_LAYOUT_MEASUREMENTS=526
CTYPES_LAYOUT_MEASUREMENTS=526
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

Only canonical `cna_title_location_set_path_ext` and
`cna_title_container_read_ext` were added. Content parsing and LZX remain
managed; no unused Content ABI surface, C++ ABI, or other binding is used.

## Ownership stress

Existing native stress remains green, and dedicated Content stress reports:

```text
CONTENT_MANAGER_CYCLES=20
TEXTURE_XNB_CYCLES=20
SPRITEFONT_XNB_CYCLES=20
CUSTOM_READER_CYCLES=20
SHARED_RESOURCE_CYCLES=20
EXTERNAL_REFERENCE_CYCLES=20
COMPRESSED_XNB_CYCLES=20
CRASHES=0
OBSERVED_UAF_OR_DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

It includes repeated cache hits, Unload/reload, double Dispose, failed and
partial graphs, callback errors, three compressed/external directions, buffers,
and Game shutdown with live Content resources. No allocator-leak claim is made
without sanitizer evidence, and no interpreter finalizer calls CNA.

## Runtime capability inventory

- `ContentManager.OpenStream / TitleContainer.OpenStream`:
  `UNIMPLEMENTED_CNA_PYTHON -> VERIFIED_NATIVE`.
- `ContentManager.ReadAsset/XNB`:
  `UNIMPLEMENTED_CNA_PYTHON -> VERIFIED_NATIVE`.
- `SpriteFont public Content loading`: `FIXTURE_PENDING -> VERIFIED_NATIVE`.
- XNB LZX and ResourceContentManager: new `VERIFIED_MANAGED` entries.
- `Load[T]` caller-type enforcement and no-token `ReadRawObject[T]`: explicit
  `LANGUAGE_MAPPING_LIMITATION` entries.
- Unsupported Texture2D payload formats and missing Effect/Model public graphs
  remain explicit, never fabricated.

## Package

Version remains `0.1.0.dev0`.

```text
wheel=cna_python-0.1.0.dev0-py3-none-any.whl
wheel SHA-256=d75e033dcb7e47d8e30b26c05a1c49a4fd968289687891ff8db6ff2651349a7e
wheel entries=45
sdist=cna_python-0.1.0.dev0.tar.gz
sdist SHA-256=df3fcea75680aab05738b3eb73c7be79e4801f4391e85dfab9fc314bb860cef4
sdist entries=115
forbidden wheel entries=0
forbidden sdist entries=0
absolute developer path leaks=0
private/bundled CNA native library=0
Microsoft/proprietary fixture files=0
```

The audited wheel contains all four Content implementation modules and
TitleContainer. A fresh isolated venv passed import and compile probes. The
generated final-wheel consumer passed exact 60/600 runs with zero absolute
developer paths, sibling-source dependencies, or PYTHONPATH dependencies.

## Template canary

Template source changed: **yes**, only for the approved Content canary.

- Existing raw `Content/logo.png -> Texture2D.FromStream` canary: PASS.
- Legal deterministic 126-byte `Content/logo.xnb -> ContentManager.Load ->
  Texture2DReader -> CNA Texture2D -> SpriteBatch` canary: PASS.
- XNB SHA-256:
  `2557e9f7f7deebcf381f4ec433efb97636592c27a755fe5b9b7b291ae5083503`.
- Maintained source 60/600: PASS/PASS.
- Maintained final-wheel 60/600: PASS/PASS.
- Generated final-wheel consumer 60/600: PASS/PASS.
- No SpriteFont demo, Effect, Model, 3D, audio, or video was added.

## Remaining exact families

The regenerated inventory contains 131 types:

- Framework: Curve family and FrameworkDispatcher;
- Audio;
- Design converters;
- GamerServicesComponent;
- Graphics: Effect/stock-effect/Model graph, OcclusionQuery,
  RenderTargetCube, Texture3D, and TextureCube;
- Graphics.PackedVector;
- Input.Touch;
- Media;
- Storage.

The next dependency-complete architectural milestone is the Effect + Model
asset/runtime graph: implement its complete public resource graph and native
dependencies, then add exact private XNB readers through the now-stable Content
resolver. This is selected by dependency architecture, not smallest type count.
No follow-on family was started in this run.

## Reproduction commands

```bash
python3 -m compileall -q src tests tools
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # expected nonzero only for 131 missing types
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/generate_runtime_capabilities.py
python3 tools/audit_cna_abi.py --cna-root ../../cna --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/native_ownership_stress.py --cycles 20
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so PYTHONPATH=src python3 tools/content_ownership_stress.py --cycles 20
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```
