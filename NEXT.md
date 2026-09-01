# CNA-Python tactical handoff

Date: 2026-09-01

```text
ABI_GENERATION=0.21.0
STRICT_ZERO=true
ACTIONABLE_LOCAL=0
REPOSITORY_MODE=maintenance/platform-qualification/selected-extension-families
```

The selected XNA 4.0 Windows runtime projection is structurally complete, the
native boundary now speaks the current CNA generation, and a first CNA extension
profile is open. This does not qualify other XNA profiles, every platform, every
provider, or every backend. Do not open Net, wider GamerServices/Avatar, Content
Pipeline, Xbox, or Windows Phone without a deliberate future-profile decision,
and do not open another extension family without a deliberate one.

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

Every mapping-mismatch category is zero. Normal, `--leak-only` and `--check`
exit zero.

## Native boundary

```text
                          BEFORE (0.7.0)   AFTER (0.21.0)
ABI                       0x00000700       0x00001500
canonical routes          2861             4055
bound routes              744              765
compiler-verified protos  0                765
layout measurements       775              796
missing symbols           0                0
ABI mismatches            0                0
```

`HISTORICAL_ARTIFACT_AVAILABLE=false`. The `0.7.0` library the previous evidence
named no longer exists on this machine and was not recreated, so its numbers are
quoted only as the before side of the migration.

The migration was measured three ways rather than assumed: all 744 historical
symbols still exist; of 775 layout measurements exactly one differed, the ABI
version constant itself; and every imported prototype is now proven against the
canonical C declaration by the compiler. Fourteen planted ABI defects prove that
gate can fail.

Version policy is derived from CNA's contract, not hard-coded: `0.x` is
experimental and an incompatible change increments the minor, so one minor is
one compatibility generation. The loader accepts any patch inside the qualified
minor and rejects every other minor and major.

## Route census and reachability

```text
CANONICAL_ROUTES=4055     BOUND=765      UNREVIEWED=0
ACTIONABLE_LOCAL=0        RULE_CONTRADICTIONS=0

XNA_BACKING=1175          CNA_EXTENSION_CANDIDATE=1791
MANAGED_BY_DESIGN=566     OUT_OF_SELECTED_PROFILE=414
NOT_USEFUL_FOR_PYTHON=108 TOOLING_ONLY=1

DIRECT_CALL_SITE=671      OBSERVED_CALLED_AT_RUNTIME=506
REACHED_BY_NAME_TEMPLATE=15   ADMITTED_WITH_REASON=37
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE=0     STALE_ADMISSIONS=0
```

Purpose and binding status are separate questions. A capability CNA offers that
this product has not selected is a deliberate non-binding with its reason
recorded, not a backlog item.

## Qualified artifacts

```text
control  HEADLESS   does not rasterize   SDL3 mixer, dummy device
         94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d
gpu      OPENGLES3  Mesa GL ES 3.2 (llvmpipe), isolated Xvfb display
         65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9

cnanext           7712534d3d22c7e284714e0e87afebba3f3cb472
sharp-runtimenext 9cc96cd57cde394940cc24d58743edf9bf63d3fb
```

Windowed tests run on an isolated Xvfb display with `SDL_VIDEODRIVER=x11` and
`WAYLAND_DISPLAY` unset, so no test window reaches the desktop session. Audio
tests run in a subprocess with `SDL_AUDIODRIVER=dummy`, which is a real mixer
that never opens the machine's sound device.

## Runtime capabilities

```text
CAPABILITIES=119                    (schema 2, per artifact)
VERIFIED_NATIVE=86                  VERIFIED_MANAGED=11
BLOCKED_UPSTREAM=6                  BLOCKED_RENDERER=2
BLOCKED_PLATFORM=5                  BLOCKED_HARDWARE=2
BLOCKED_FIXTURE=4                   LANGUAGE_MAPPING_LIMITATION=2
DELIBERATE_OUT_OF_SCOPE=1           ACTIONABLE_LOCAL=0
```

Closed by measurement since the historical evidence:

- `DynamicVertexBuffer.SetData(offset, options)` — the combined route exists.
- `SoundEffectInstance.Apply3D(multiple listeners)` — any positive count.
- Video frame identity — a monotonic decode generation is now supplied.
- Bound render-target disposal — a clean refusal, no longer a process abort.
- Real visualization spectrum — a decoded tone drives it.
- Every draw path, SpriteBatch, render targets, Texture3D, TextureCube and
  Model produce their expected pixels on a renderer that rasterizes.
- Video decodes through the ordinary content path on both artifacts.
- Window resize is delivered on the windowed renderer.
- Microphone enumeration, state and capture plumbing are real.

Confirmed unchanged, each against the header line that says so: the dispatcher
still requires a Game, Present still takes only the device, XACT still accepts
and ignores renderer and look-ahead, storage still ignores FileShare, and the
resource-created event still carries no object identity.

## Extension profile

```text
EXTENSION_MODULES=3            PUBLIC_EXTENSION_NAMES=16
PUBLIC_CTYPES_LEAK=0           PRIVATE_NATIVE_LEAK=0
UNDOCUMENTED_PUBLIC=0          XNA_NAMESPACE_CONTAMINATION=0
EXTENSION_SURFACE_DIAGNOSTICS=0
```

`cna.extensions.graphics` reports renderer identity, availability, latching,
name parsing, preference, the fallback chain and the fallback history. Importing
the XNA namespace in a fresh interpreter never loads `cna`, which is asserted
rather than assumed.

## Verification

```text
COMPILEALL=PASS
UNITTESTS=194 on the control artifact, 194 on the windowed artifact,
          194 with no native library configured
STRICT_REPORT / LEAK_ONLY / STRICT_CHECK=PASS
VERIFIER_SELF_TESTS=7 PASS
BEHAVIOR_CORPUS=181 observations / 1004 assertions / 0 failures
ABI_AUDIT=PASS      PROTOTYPE_GATE=765 verified / 0 conflicts
ROUTE_CENSUS=PASS   ROUTE_REACHABILITY=PASS   EXTENSION_GATE=PASS
```

## Next work

Maintenance, further platform qualification, upstream blocker reconciliation,
packaging/release work, and real-game compatibility testing. Structural
expansion requires a separately selected future profile; another extension
family requires a separately selected extension decision. Both are recorded in
`docs/generated/cna-route-census.md` with their reasons.
