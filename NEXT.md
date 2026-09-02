# CNA-Python tactical handoff

Date: 2026-09-02

```text
ABI_GENERATION=0.21.0
STRICT_ZERO=true
ACTIONABLE_LOCAL=0
SELECTED_CNB_CNJ_ACTIONABLE_LOCAL=0
CNB_CNJ_UNREVIEWED=0
REPOSITORY_MODE=maintenance/platform-qualification/selected-extension-families
```

The selected XNA 4.0 Windows runtime projection is unchanged and still closed.
This session opened, built and closed one new extension family: CNA's own `.cnb`
compiled content format and its `.cnj` source documents. Every number below was
re-measured today; none is quoted from the previous handoff.

Do not open Net, wider GamerServices/Avatar, Content Pipeline, Xbox or Windows
Phone without a deliberate future-profile decision, and do not open the engine
layer, sensors and device services, or extended input without a deliberate
extension decision.

## The extension product decision

`cna.extensions.content` projects CNA's own compiled content format. The strict
`Microsoft.Xna.Framework.Content.ContentManager` is **unchanged**: still managed
Python, still reading `.xnb` and only `.xnb`, still keeping its own cache. There
is no format preference, no fallback in either direction, and no shared cache
identity. A test places a `.cnb` exactly where the strict manager looks for a
`.xnb` and asserts it is not read.

Engine layer, sensors and device services, extended input, Net, wider
GamerServices/Avatar, Content Pipeline, Xbox and Windows Phone all remain
unopened, each recorded in the census with its reason.

## Strict projection

```text
REFERENCE_TYPES=257            REFERENCE_MEMBERS=2964
EXPECTED_PYTHON_TYPES=257      EXPECTED_PYTHON_MEMBERS=2887
TARGET_TYPES=257               TARGET_MEMBERS=2423
TOTAL_DIAGNOSTICS=0            ZERO_DIAGNOSTIC_TYPES=257
MISSING_TYPE=0                 MISSING_MEMBER=0
UNEXPECTED_TYPE=0              UNEXPECTED_MEMBER=0
INTERNAL_TYPE_LEAK=0           RAW_HANDLE_LEAK=0
PUBLIC_NATIVE_FFI_LEAK=0       ALLOWLIST_ENTRIES=0
UNMEASURED_STRUCTURAL_CATEGORY=0
```

Normal, `--leak-only` and `--check` exit zero. Seven verifier self-tests pass.

## Native boundary

```text
                          BEFORE (this session)   AFTER
bound routes              765                     1048
compiler-verified protos  765                     1048
layout measurements       796                     1219
missing symbols           0                       0
ABI mismatches            0                       0
prototype conflicts       0                       0
```

The 283 new routes are 270 of `cnb.h`'s 272, plus two dependency slices. All 24
CNB structures and all 179 frozen wire constants are re-measured by a C probe
compiled against the canonical headers, because a `.cnb` file's values outlive
any single build. Measured on both artifacts.

## CNB/CNJ route scoreboard

```text
CNB_CNJ_ROUTES=285        CNB_CNJ_BOUND=283
CNB_CNJ_UNREVIEWED=0      SELECTED_CNB_CNJ_ACTIONABLE_LOCAL=0

by header       cnb.h 272    curve.h 11    content.h 2
by status       BOUND 283    DELIBERATE_NON_BINDING 2

BLOCKED_UPSTREAM=0        BLOCKED_PLATFORM=0
BLOCKED_HARDWARE=0        BLOCKED_FIXTURE=0
LANGUAGE_MAPPING_LIMITATION=0 (as a route status; see the capability row)
```

The two non-bound routes are `cna_cnb_checked_add` and
`cna_cnb_checked_multiply`, classified `NOT_USEFUL_FOR_PYTHON`: Python integers
are unbounded, so the computation is already exact and a call would narrow an
exact answer. The checks that matter happen where a value has to fit a native
width.

`docs/generated/cna-route-census.md` names all 285 with their reasons.

### The two dependency slices, not second decisions

- **`curve.h`, eleven routes.** `cna_cnb_encode_curve` takes a native `Curve`
  handle and `cna_cnb_decode_curve` produces one, so the codec is unreachable
  from a managed-only `Microsoft.Xna.Framework.Curve`. The native curve lives
  only inside those two functions. The strict `Curve` stays pure managed.
- **`content.h`, two routes.** `cna_cnb_loader_invoke` requires a content
  manager -- measured: passing none is refused -- so without it a registered
  loader could be resolved and never run. Exactly `create` and `destroy`.

## Global route census and reachability

```text
CANONICAL_ROUTES=4055     BOUND=1048     UNREVIEWED=0
ACTIONABLE_LOCAL=0        RULE_CONTRADICTIONS=0

DIRECT_CALL_SITE=954      OBSERVED_CALLED_AT_RUNTIME=506
REACHED_BY_NAME_TEMPLATE=15   ADMITTED_WITH_REASON=37
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE=0     STALE_ADMISSIONS=0
```

The reachability gate had a hole this session found rather than confirmed: it
excluded the two existing manifest modules from counting a route name as a call
site but not the new `cnb_manifest`, so all 281 CNB routes were satisfying it
with their own declarations. Fixed, and it then correctly reported two genuinely
dead routes, which are now public API.

## Public extension surface

```text
EXTENSION_MODULES=18           PUBLIC_EXTENSION_NAMES=266
PUBLIC_CTYPES_LEAK=0           PRIVATE_NATIVE_LEAK=0
UNDOCUMENTED_PUBLIC=0          XNA_NAMESPACE_CONTAMINATION=0
PUBLIC_RAW_HANDLE_LEAK=0       PUBLIC_NATIVE_ANNOTATION_LEAK=0
EXTENSION_SURFACE_DIAGNOSTICS=0
```

`cna.extensions.content` publishes 163 names across 14 modules. The gate gained
two checks a runtime sweep cannot make: a public signature that *names* a handle
or a ctypes type, and a public attribute called `handle`. Both are diagnostics
now, and a planted defect proves each fails.

Importing the XNA namespace in a fresh interpreter loads no `cna` module at all;
importing the extension needs no native library, and calling into it without one
says so by name.

## Runtime capabilities

```text
CAPABILITIES=140                    (schema 2, per artifact)
VERIFIED_NATIVE=103                 VERIFIED_MANAGED=11
BLOCKED_UPSTREAM=7                  BLOCKED_RENDERER=2
BLOCKED_PLATFORM=5                  BLOCKED_HARDWARE=2
BLOCKED_FIXTURE=4                   LANGUAGE_MAPPING_LIMITATION=3
NOT_USEFUL_FOR_PYTHON=1             DELIBERATE_OUT_OF_SCOPE=2
ACTIONABLE_LOCAL=0
```

Twenty-one rows are new, all CNB/CNJ. `NOT_USEFUL_FOR_PYTHON` is a new status:
a capability CNA offers that Python already has exactly is a different answer
from "out of scope" and from "blocked", because nothing is missing and nothing
is deferred.

## Qualified artifacts

```text
control  HEADLESS   does not rasterize   SDL3 mixer, dummy device
         94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d
gpu      OPENGLES3  Mesa GL ES 3.2 (llvmpipe), isolated Xvfb display
         65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9

cnanext           5347b52eae1311fbea1f89955ae8a48c6843a88a
sharp-runtimenext 9cc96cd57cde394940cc24d58743edf9bf63d3fb
```

`cnanext` moved one commit since the previous handoff (`7712534d`), a change to
one audio test; `cnb.h` is unchanged. Neither dependency was modified by this
session.

Almost nothing in this family needs a renderer -- parsing, encoding, decoding,
compiling and the whole model graph are renderer-independent -- so both
artifacts run all 237 CNB tests with zero skips. Only loader invocation needs a
live `GraphicsDevice`, because a native content manager does.

## Verification

```text
COMPILEALL=PASS
UNITTESTS=432 total
  no native library configured   122 executed, 310 skipped   OK
  control artifact               408 executed,  24 skipped   OK
  gpu artifact (Xvfb)            415 executed,  17 skipped   OK
CNB/CNJ subset                   237 executed, 0 skipped on both artifacts

STRICT_REPORT / LEAK_ONLY / STRICT_CHECK=PASS
VERIFIER_SELF_TESTS=7 PASS
BEHAVIOR_CORPUS=181 observations / 1004 assertions / 0 failures
ABI_AUDIT=PASS (both artifacts)   PROTOTYPE_GATE=1048 verified / 0 conflicts
ROUTE_CENSUS=PASS   ROUTE_REACHABILITY=PASS   EXTENSION_GATE=PASS

CNA_TOOL_CROSSCHECK=7 executed, 0 skipped
  cna_tool_cnj_to_cnb and this binding produce byte-identical output
  cna_tool_cnb_info validates and refuses exactly what this binding does

MUTATION: 35 planted / 35 killed / 0 survived / 0 equivalent
TOOLING MUTATION: 5 planted / 5 killed
```

Skips are reported, not counted as passes. The 24 skips on the control artifact
are the rendering tests that need a rasterizing renderer; the 17 on the GPU
artifact are hardware and platform rows.

## Package and consumers

```text
WHEEL_BYTE_REPRODUCIBLE=1     WHEEL_CONTENT_REPRODUCIBLE=1
SDIST_BYTE_REPRODUCIBLE=0     SDIST_CONTENT_REPRODUCIBLE=1
FORBIDDEN_WHEEL_ENTRIES=0     FORBIDDEN_SDIST_ENTRIES=0
BUNDLED_NATIVE_LIBRARIES=0    ABSOLUTE_DEVELOPER_PATH_LEAKS=0
MICROSOFT_OR_PROPRIETARY_CONTENT=0

installed-wheel consumer:
  IMPORT_PROBE=PASS   COMPILE_PROBE=PASS
  SMOKE_60=PASS       STABILITY_600=PASS
  EXTENSION_IMPORT=PASS   CNB_SMOKE=PASS
  ABSOLUTE_DEVELOPER_PATHS=0  SIBLING_SOURCE_DEPENDENCIES=0
  PYTHONPATH_SOURCE_DEPENDENCIES=0
```

The sdist's *files* are identical between builds; its *container* is not,
because setuptools stamps `PKG-INFO`, `setup.cfg` and every directory entry with
the wall clock regardless of `SOURCE_DATE_EPOCH`, and gzip records its own
timestamp. Nothing in this repository causes it and nothing here can fix it, so
it is measured and reported rather than claimed away.

`tools/verify_reproducibility.py` is new and makes that distinction a gate.

## Defects this session found

**In this binding, before it shipped.** Seven `.cnb` texture formats map to CNA
surface formats XNA 4.0 never had, so forcing the result into the strict
20-member enum raised a bare `ValueError`; the extension now names all 27 itself
and `xna_surface_format` answers `None` for exactly those seven. Three shape
rules CNA documents were enforceable only at encode time, where the diagnostic
names a file instead of the call that got it wrong. A hard-coded repository path
in the new mutation tool was caught by the path-leak audit.

**In the tooling.** The reachability gate did not exclude the new manifest
module, so every CNB route satisfied it with its own declaration.

**In the test suite.** Four mutation survivors were real gaps: a dead helper
with no caller, textures only ever read at representation 0, a bone transform
asserted only on its diagonal, and a colour-key fixture with no black pixel.

**Upstream, neither blocking.** `cnb.h`'s file comment says the document, byte
cursors and loader registry "are not published yet"; all 272 routes are declared
and exported, so it is stale. And `content_root` is documented as a resolution
base while the implementation uses it as a containment boundary; this binding
documents and tests the implementation.

## Git

```text
cna-python           develop, clean, pushed=no
cna-python-template  develop, clean, pushed=no
cnanext              unmodified by this session
sharp-runtimenext    unmodified by this session
```

## Next work

No selected-scope work remains. `SELECTED_CNB_CNJ_ACTIONABLE_LOCAL=0` and
`CNB_CNJ_UNREVIEWED=0`; the global census still has `UNREVIEWED=0` and
`ACTIONABLE_LOCAL=0`.

Maintenance, further platform qualification, upstream blocker reconciliation,
packaging and release work, and real-game compatibility testing. Structural
expansion of the XNA surface requires a separately selected future profile;
another extension family requires a separately selected extension decision. Both
are recorded in `docs/generated/cna-route-census.md` with their reasons.
