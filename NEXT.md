# CNA-Python tactical handoff

Date: 2026-08-23.

## Baseline and scope

The session started from clean CNA-Python commit
`79f66ce90a15dbdc9239cff9e47071166a14950f` and clean template commit
`060520d8f6ae9fb62de695146d645084f6b90048`. Production contained 7 Python
files / 192 lines and the five scaffold tests failed at import when run from a
source checkout. The fake paths removed were no-op Game/Exit/Clear/SpriteBatch/
SetData, fabricated empty input, synthetic ContentManager texture loads,
identity matrix operations, BasicEffect.Apply, DrawRect, method-shaped static
values, and the template's fake renderer/3D/Web/Android/mobile claims.

The resulting production tree contains 22 Python files / 3,372 lines. The public surface is split from private
implementation modules and the sibling starter is desktop-only.

## Authoritative profile and strict report

The neutral reference contract was extracted from the same seven pinned XNA
4.0 Windows runtime assemblies used by mature bindings. The contract file
`tools/api_compat/reference/xna40-windows-runtime-contract.json` has SHA-256
`7207908eb7926cc90a156d0370c907add4dda465421cea1cbec51afba2f97fdc`.

Latest strict report:

```text
REFERENCE_TYPES=257
REFERENCE_MEMBERS=2964
EXPECTED_PYTHON_TYPES=257
EXPECTED_PYTHON_MEMBERS=2887
TARGET_TYPES=42
TARGET_MEMBERS=796
TOTAL_DIAGNOSTICS=501
MISSING_TYPE=215
MISSING_MEMBER=223
OVERLOAD_MAPPING_MISMATCH=33
UNMEASURED_STRUCTURAL_CATEGORY=30
all other mismatch categories=0
UNEXPECTED_TYPE=0
UNEXPECTED_MEMBER=0
INTERNAL_TYPE_LEAK=0
RAW_HANDLE_LEAK=0
PUBLIC_NATIVE_FFI_LEAK=0
ALLOWLIST_ENTRIES=0
ZERO_DIAGNOSTIC_TYPES=11
```

`--check` is deliberately red. `--leak-only` must remain green. Full interface,
field-type, parameter/return-type, and generic checks are explicitly counted as
unmeasured rather than silently treated as compatible.

## CNA and native evidence

Current CNA HEAD was inspected once, read-only, at
`1bb2145d99ed572dd4eb15009c34e2e5f410fcf0`. Its C-API build currently stops at
`modules/c-api/src/CnaCApiCoreExt.cpp:250`, where a compile-time assertion sees
49 C renderer identities against 50 canonical renderer entries. CNA was not
modified.

The qualified local verification artifact was used from
`/tmp/cna-java-native-working-070/modules/c-api/libcna_c_api.so` solely through
`CNA_NATIVE_LIBRARY`; no committed runtime path or native binary enters the
runtime resolver, wheel, or template; the path appears here only because this is
the requested evidence log. Evidence:

```text
CNA source revision=a09196a6477f69a7a57c8364f990658d31531a5b
ABI=0.7.0 / 0x00000700 exact
library SHA-256=42e099146bf3b470f82fd963a516f8bdd7ff0406da8c37dd53747699117db086
platform=Linux x86-64
renderer=HEADLESS
audio=NULL
BOUND_FUNCTIONS=55
CTYPES_SIGNATURE_MEASUREMENTS=55
C_LAYOUT_MEASUREMENTS=169
CTYPES_LAYOUT_MEASUREMENTS=169
MISSING_SYMBOLS=0
ABI_MISMATCHES=0
```

The loader sets `argtypes` and `restype` on every selected symbol. It rejects a
relative/missing explicit path, wrong ABI, and missing symbol. Native callback
exceptions in Initialize, LoadContent, Update, Draw, and UnloadContent retain
their Python identity; no exception escapes through C.

## Behavior, ownership, template, package

Pure corpus: 16 observations / 35 assertions / 0 failures, derived from pinned
XNA metadata and IL/algorithm analysis, not labelled as a Windows capture.

Native unit suite: 30 tests pass with the artifact. The ownership stress gate
passes 20 game lifetimes, 20 child-resource cycles, 10 explicit double-dispose
cycles, and 20 parent-before-live-child cycles with zero crash or observed
use-after-free/double-free. No sanitizer run was available.

The raw template PNG is 128×128, 2,325 bytes, SHA-256
`66643910d4ca53075ebd096a41671118df7f1ff15016d8bbbc9f8f38d055f989`.
`Texture2D.FromStream` decodes those dimensions natively. The maintained and
generated starters Clear Cornflower Blue, poll real CNA keyboard/mouse/gamepad
routes, and submit moving/rotating/scaling SpriteBatch commands. Both exact 60-
and 600-draw runs pass.

Final artifacts:

```text
wheel=cna_python-0.1.0.dev0-py3-none-any.whl
wheel SHA-256=f5ef185b99644788ec2fb6a1475e7acc33a4906335b5182f94eb6c199997e979
wheel entries=35, forbidden entries=0
sdist=cna_python-0.1.0.dev0.tar.gz
sdist SHA-256=743d89da3c44f6be6f09054b42c0744cba32a015173fdb159508e8720cb43136
sdist entries=89, forbidden entries=0
```

The isolated consumer gate creates a new venv,
installs the exact local wheel without dependencies or an editable/source path,
generates a fresh game, compiles/imports it, and runs 60/600 frames. Its required
leak counters are all zero.

## Reproduction commands

From CNA-Python, with the qualified library available:

```bash
python3 -m compileall -q src tests tools
python3 -m unittest discover -v
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 -m unittest discover -v
python3 tools/run_behavior_corpus.py --output docs/generated/behavior-corpus-report.json
python3 tools/api_compat/test_verify.py
python3 tools/api_compat/verify.py --report --output docs/generated/api-compat-report.json --inventory
python3 tools/api_compat/verify.py --leak-only
python3 tools/api_compat/verify.py --check  # expected nonzero
python3 tools/audit_cna_abi.py --cna-root ../../cna --library /absolute/path/libcna_c_api.so --output docs/generated/cna-abi-report.json
CNA_NATIVE_LIBRARY=/absolute/path/libcna_c_api.so python3 tools/native_ownership_stress.py --cycles 20
PYTHONPATH=/tmp/cna-python-build-tools python3 -m build --no-isolation
python3 tools/audit_package.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --sdist dist/cna_python-0.1.0.dev0.tar.gz
python3 tools/verify_consumer.py --wheel dist/cna_python-0.1.0.dev0-py3-none-any.whl --template ../cna-python-template --library /absolute/path/libcna_c_api.so
git diff --check
git -C ../cna-python-template diff --check
```

## Next exact work

Start with verifier type annotations and the dependency-complete Plane/Ray/
bounds/frustum pure group. Do not broaden native surface until each added value
family has checked overloads and corpus evidence. Then complete the input value
contracts and SpriteBatch/graphics-state dependencies before approaching real
ContentManager/XNB. BasicEffect must return only with EffectPass.Apply plus
vertex/index buffers and indexed drawing; never restore the deleted fake cube.

There are no confirmed unavailable CNA operations blocking the implemented
slice. The only upstream blocker recorded by this milestone is the current CNA
HEAD renderer-identity build assertion; it blocks producing a fresh library but
does not justify changing CNA from this repository.
