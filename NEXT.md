# CNA-Python tactical handoff

Date: 2026-08-23.

Foundation Milestone 2 is complete. CNA-Python now has a fully measured
stub/runtime structural verifier and a locally zero-diagnostic XNA-faithful
math/value, geometry/intersection, and non-touch input foundation. Do not begin
Content/XNB, effects/3D, audio/media, or touch from this handoff.

## Strict before and after

```text
                                      BEFORE  AFTER
REFERENCE_TYPES                          257    257
REFERENCE_MEMBERS                       2964   2964
EXPECTED_PYTHON_TYPES                    257    257
EXPECTED_PYTHON_MEMBERS                 2887   2887
TARGET_TYPES                              42     51
TARGET_MEMBERS                           796   1003
TOTAL_DIAGNOSTICS                        501    310
MISSING_TYPE                             215    206
MISSING_MEMBER                           223    104
OVERLOAD_MAPPING_MISMATCH                 33      0
UNMEASURED_STRUCTURAL_CATEGORY            30      0
COMPLETE_TYPES                            11     41
PARTIAL_TYPES                             31     10
MISSING_TYPES                            215    206
```

Final values for every other strict category are zero:

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
```

The normal `--check` remains red only for real missing type/member surface.
The `--leak-only` gate is green.

## Structural verifier

`tools/api_compat/verify.py` uses deterministic AST inspection of shipped
`.pyi` files for fields and mapped field types, properties and mutability,
static/instance shape, methods and constructors, overload count, argument
names/order/types/optionality, nullability, mapped return types, ref/out tuple
returns, arrays/sequences, TypeVar identity/order/bounds, indexers, interfaces,
events, enum/flags identity, operators, and Python copy/disposal rules.

Runtime/stub consistency detects missing objects in either direction,
method/static/class/property/event shape, property mutability, and exact runtime
dispatcher arities. `tools/api_compat/generate_stubs.py` regenerates the four
package stubs from pinned metadata. Seventeen deliberately broken fixtures
cover the original regressions plus wrong field/parameter/return/interface,
TypeVar/bound, nullable, ref/out, overload, and runtime/stub cases.

## Complete types

The 41 local-zero types are:

```text
Microsoft.Xna.Framework.BoundingBox
Microsoft.Xna.Framework.BoundingFrustum
Microsoft.Xna.Framework.BoundingSphere
Microsoft.Xna.Framework.Color
Microsoft.Xna.Framework.ContainmentType
Microsoft.Xna.Framework.Content.ContentLoadException
Microsoft.Xna.Framework.DisplayOrientation
Microsoft.Xna.Framework.GameTime
Microsoft.Xna.Framework.Graphics.DepthFormat
Microsoft.Xna.Framework.Graphics.GraphicsProfile
Microsoft.Xna.Framework.Graphics.SpriteEffects
Microsoft.Xna.Framework.Graphics.SpriteSortMode
Microsoft.Xna.Framework.Input.ButtonState
Microsoft.Xna.Framework.Input.Buttons
Microsoft.Xna.Framework.Input.GamePad
Microsoft.Xna.Framework.Input.GamePadButtons
Microsoft.Xna.Framework.Input.GamePadCapabilities
Microsoft.Xna.Framework.Input.GamePadDPad
Microsoft.Xna.Framework.Input.GamePadDeadZone
Microsoft.Xna.Framework.Input.GamePadState
Microsoft.Xna.Framework.Input.GamePadThumbSticks
Microsoft.Xna.Framework.Input.GamePadTriggers
Microsoft.Xna.Framework.Input.GamePadType
Microsoft.Xna.Framework.Input.KeyState
Microsoft.Xna.Framework.Input.Keyboard
Microsoft.Xna.Framework.Input.KeyboardState
Microsoft.Xna.Framework.Input.Keys
Microsoft.Xna.Framework.Input.Mouse
Microsoft.Xna.Framework.Input.MouseState
Microsoft.Xna.Framework.MathHelper
Microsoft.Xna.Framework.Matrix
Microsoft.Xna.Framework.Plane
Microsoft.Xna.Framework.PlaneIntersectionType
Microsoft.Xna.Framework.PlayerIndex
Microsoft.Xna.Framework.Point
Microsoft.Xna.Framework.Quaternion
Microsoft.Xna.Framework.Ray
Microsoft.Xna.Framework.Rectangle
Microsoft.Xna.Framework.Vector2
Microsoft.Xna.Framework.Vector3
Microsoft.Xna.Framework.Vector4
```

Core completion includes exact binary32 intermediate narrowing and evaluation
order, hashes/strings, fresh static values, copy boundaries, complete overloads,
array/range transforms, singular/non-finite Matrix behavior, and all selected
factories. Geometry includes all selected Plane/Ray/box/sphere/frustum
containment and intersection routes, six-plane extraction, exact corner
generation, and convex/GJK interactions.

Non-touch input completion includes KeyboardState filtering/order/hash,
MouseState five-button behavior and real WindowHandle/SetPosition routes,
GamePad value semantics, analog button thresholds, GamePadCapabilities,
GamePadType, dead-zone overloads, capabilities, and vibration. Classification:

```text
API_COMPLETE=YES
NATIVE_ROUTE_VERIFIED=YES
PHYSICAL_HARDWARE_NOT_VERIFIED=YES
TOUCH_STARTED=NO
```

## Remaining exact partial types

Only ten implemented types remain partial:

```text
Microsoft.Xna.Framework.Content.ContentManager=3
Microsoft.Xna.Framework.Game=11
Microsoft.Xna.Framework.Graphics.GraphicsDevice=49
Microsoft.Xna.Framework.Graphics.GraphicsResource=2
Microsoft.Xna.Framework.Graphics.SpriteBatch=6
Microsoft.Xna.Framework.Graphics.SurfaceFormat=19
Microsoft.Xna.Framework.Graphics.Texture=2
Microsoft.Xna.Framework.Graphics.Texture2D=2
Microsoft.Xna.Framework.Graphics.Viewport=2
Microsoft.Xna.Framework.GraphicsDeviceManager=8
```

The generated missing inventory contains the exact 206 absent types. Use it,
not stale prose, for the next family choice.

## Behavior evidence

The `PURE_XNA_DERIVED` corpus moved from 16 observations / 35 assertions to 92
observations / 360 assertions, with zero failures. It covers MathHelper,
Vector2/3/4, Quaternion, Matrix, Color, Point, Rectangle, Plane, Ray,
BoundingBox, BoundingSphere, and BoundingFrustum. Exact-bit cases cover NaN,
infinity, signed zero, scalar-division ordering, spline ULPs, quaternion and
matrix transforms, singular inversion, mirrored decomposition, degenerate
LookAt/shadow/Plane, hashes, tangent/near-parallel intersections, and frustum
planes/corners/GJK. Provenance is pinned XNA metadata plus IL/algorithm and
neutral golden-snapshot analysis; it is not a Windows capture or CNA output.

## CNA and ABI evidence

Current CNA HEAD was rechecked read-only at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. Its C-API build still has the
renderer identity assertion `49 == 50`; CNA was not modified. The qualified
artifact remains:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
ABI=0.7.0 / 0x00000700 exact
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
BOUND_FUNCTIONS=59
CTYPES_SIGNATURE_MEASUREMENTS=59
C_LAYOUT_MEASUREMENTS=210
CTYPES_LAYOUT_MEASUREMENTS=210
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

The four added imports are mouse window get/set, gamepad capabilities, and
gamepad vibration. Canonical C headers and ELF exports are the authority.

## Ownership, callbacks, package, and template

Ownership stress remains:

```text
LIFECYCLE_CYCLES=20
CHILD_RESOURCE_CYCLES=20
EXPLICIT_DOUBLE_DISPOSE_CYCLES=10
PARENT_BEFORE_CHILD_CYCLES=20
CRASHES=0
OBSERVED_UAF_OR_DOUBLE_FREE=0
SANITIZER_STATUS=NOT_RUN
```

Initialize, LoadContent, Update, Draw, and UnloadContent callback tests retain
the original Python exception identity. Input snapshots acquire no native
ownership and no finalizer calls CNA.

Fresh artifacts:

```text
wheel=cna_python-0.1.0.dev0-py3-none-any.whl
wheel SHA-256=ee6a9167e2f8598d1b74635a4eb3fee3910dbeab83721106fa87ac795a0af44b
wheel entries=36
sdist=cna_python-0.1.0.dev0.tar.gz
sdist SHA-256=cd3d6f47f42b328fafd3b5dd64afd9c8f5374bb3b05725f1df9cf121b3bd4310
sdist entries=95
forbidden wheel entries=0
forbidden sdist entries=0
absolute developer path leaks=0
```

The template source was not changed. Maintained 60/600 runs and isolated
installed-wheel generated 60/600 runs all pass. The isolated gate also passes
import/compile and reports zero absolute-path, sibling-source, and PYTHONPATH
source dependencies.

## Reproduction commands

```bash
python3 -m compileall -q src tests tools
python3 -m unittest discover -v
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 -m unittest discover -v
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/generate_stubs.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # expected nonzero
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/audit_cna_abi.py --cna-root ../../cna --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 tools/native_ownership_stress.py --cycles 20
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```

## Next dependency-complete milestone

Use the ten-type partial scoreboard and 206-type generated inventory to choose
one coherent family. The safest pure follow-on is the complete six-type Curve
family; it was not started here and must not be split into shells. If the next
milestone instead chooses native breadth, separately scope the remaining 2D
graphics/device-state dependency set around GraphicsDevice/SpriteBatch/
Texture/Viewport and preserve explicit native-capability errors for absent ABI
routes. Do not start XNB as a one-off Texture loader; future Content requires
the complete reader/manager/shared-resource/external-reference chain. Do not
restore fake effects, buffers, or indexed drawing.
