# CNA-Python tactical handoff

Date: 2026-09-02.

```text
STOP_CONDITION=held
COUNTERS_CHECKED=45
FAILURES=0
MEASURED_PROFILES=4
BLOCKED_PROFILES=1
GLOBAL_ACTIONABLE_LOCAL=0
GLOBAL_UNREVIEWED=0
CONTENT_PIPELINE_ACTIONABLE_LOCAL=0
DEFAULT_PROFILE_TYPES=257
DEFAULT_PROFILE_MEMBERS=2423
REPOSITORY_MODE=all-six-selected-scopes-closed
```

Every number below was re-measured today. One command reproduces the whole
scoreboard: `python3 tools/verify_stop_condition.py`.

## 1. What this session was asked for, and what happened

Six scopes were opened by product decision, and every previous
`DELIBERATE_OUT_OF_SCOPE`, `DELIBERATE_NON_BINDING`, `FUTURE_PROFILE` and
`PRODUCT_DECISION_REQUIRED` covering them was revoked. All six are closed.

| scope | outcome |
| --- | --- |
| 1. Sensors and device services | `cna.extensions.devices`, 206 routes, 177 bound |
| 2. Extended input | `cna.extensions.input`, 126 routes, 119 bound |
| 3. Net, GamerServices, Avatar | `xna40-windows-online`, a second strict profile |
| 4. XNA Content Pipeline | `xna40-windows-content-pipeline`, 128 types, no CNA route |
| 5. Xbox 360 | `xna40-xbox360-runtime`, a surface profile, generated |
| 6. Windows Phone | `BLOCKED_REFERENCE_ASSET`, measured, everything else done |

Five commits, all local, nothing pushed:

```text
dca69a3 feat: measure the Windows Phone block, and finish everything it does not block
434a2b9 feat: open the Xbox 360 surface profile, and keep the four profiles apart
9a44ed2 feat: project the whole XNA Content Pipeline, with no native boundary at all
ea3eb74 feat: open XNA's online runtime as a second strict profile
c0bd48f feat: finish cna.extensions.input with all 119 extended-input routes
```

## 2. The four measured profiles

| profile | reference | mapped | strict target | diagnostics |
| --- | --- | --- | --- | --- |
| `xna40-windows-runtime` | 257 / 2,964 | 257 / 2,887 | 257 / 2,423 | 0 |
| `xna40-windows-online` | 74 / 676 | 74 / 605 | 74 / 605 | 0 |
| `xna40-windows-content-pipeline` | 128 / 743 | 128 / 598 | 128 / 598 | 0 |
| `xna40-xbox360-runtime` | 318 / 3,577 | 318 / 2,986 | 318 / 2,986 | 0 |

Every contract is re-derived from its assemblies by
`tools/api_compat/extract_reference.py`, and a test runs `--check` on each.

**The default Windows runtime profile is unchanged**: 257 types, 2,423 members,
zero diagnostics, as it has been since before any of this. That is a gated
number now -- `DEFAULT_PROFILE_DRIFT` in
`tools/verify_profile_separation.py` -- and a planted change to it fails.

## 3. How four profiles share two packages without leaking

`Microsoft.Xna.Framework.GamerServices` and `.Net` hold both the runtime
profile's `GamerServicesComponent` and the online profile's other 74 types,
because XNA puts them in one namespace. The two profiles are **declared
siblings**: each verifies against its own contract, a name a sibling owns is out
of *this* profile rather than unexpected, and a name owned by neither is still
`UNEXPECTED_TYPE`. Their type sets are disjoint.

The Xbox profile cannot do that -- two profiles cannot both *be*
`Microsoft.Xna.Framework` in one interpreter -- so it lives under
`cna.profiles.xbox360` and declares a package-to-namespace map. The verifier
reads it, which is why the identities it checks are XNA's and the imports are
not.

The Content Pipeline needs neither: it is a subpackage of
`Microsoft.Xna.Framework.Content`, which is where XNA puts it, and Python
imports a subpackage only when something asks for it.

## 4. Route scoreboard

```text
CANONICAL_ROUTES        4055
STATUS_BOUND            2626
STATUS_UNREVIEWED          0
STATUS_ACTIONABLE_LOCAL    0
```

| family | routes | bound | unreviewed | actionable-local |
| --- | --- | --- | --- | --- |
| CNB/CNJ | 285 | 283 | 0 | 0 |
| engine layer | 870 | 867 | 0 | 0 |
| devices and sensors | 206 | 177 | 0 | 0 |
| extended input | 126 | 119 | 0 | 0 |
| online | 437 | 416 | 0 | 0 |

The Content Pipeline binds none: CNA declares no content-pipeline header, and a
content build reads files and writes files.

## 5. The native boundary

```text
BOUND_FUNCTIONS               2626
PROTOTYPES_COMPILER_VERIFIED  2626
C_LAYOUT_MEASUREMENTS         2518
MISSING_SYMBOLS                  0
PENDING_ROUTES                   1
PENDING_ROUTES_NOT_IN_HEADERS    0
STALE_PENDING_ROUTES             0
ABI_MISMATCHES                   0
```

`PENDING_ROUTES` is new and is the only thing about the boundary that changed.
See section 12.

## 6. Route reachability

```text
BOUND_ROUTES                        2626
DIRECT_CALL_SITE                    2529
OBSERVED_CALLED_AT_RUNTIME           506
REACHED_BY_NAME_TEMPLATE              18
ADMITTED_WITH_REASON                  37
UNJUSTIFIED_BOUND_WITHOUT_CALL_SITE    0
STALE_ADMISSIONS                       0
```

A hole was found and closed here: the gate's list of *declaration* modules was
hard-coded, so a generated manifest satisfied its own reachability and hid 247
routes. The list is derived now, and all 247 were closed with real consumers --
which is why the devices and input families changed in the online commit.

## 7. Content Pipeline coverage

```text
PROJECTED_MEMBERS                  667
IMPLEMENTED                        623
STATUS_ABSTRACT_BY_DESIGN           39
STATUS_IMPLEMENTED_ERROR_PATH        1
STATUS_BLOCKED_UPSTREAM              3
STATUS_BLOCKED_FIXTURE               1
UNREVIEWED                           0
STALE_DECISIONS                      0
CONTENT_PIPELINE_ACTIONABLE_LOCAL    0
```

`tools/verify_content_pipeline.py` reads every projected member's
implementation; one that can raise `NotImplementedError` must appear in
`tools/content-pipeline-decisions.json` with a status and a written reason. A
member that refuses and is not declared is `UNREVIEWED`; a declaration whose
member no longer refuses is `STALE`.

## 8. Profile separation

```text
DEFAULT_PROFILE_TYPES                 257
DEFAULT_PROFILE_MEMBERS              2423
PLATFORM_PROFILES                       1
DECLARED_REMOVALS                       1
PLATFORM_LEAKS                          0
WINDOWS_ONLY_REACHABLE_FROM_PLATFORM    0
UNJUSTIFIED_REMOVALS                    0
DEFAULT_PROFILE_DRIFT                   0
```

## 9. Blocked profiles

```text
BLOCKED_PROFILES        1
UNJUSTIFIED_BLOCK       0
BLOCK_WITHOUT_REASON    0
STALE_BLOCK             0
SEARCH_MISSING          0
```

The one blocked profile is Windows Phone, and the block is a measurement:
1,296,128 files examined across eight roots, thirty-six name matches, every one
identified, zero candidates. See `docs/windowsphone-profile.md`.

## 10. Extension surface

```text
EXTENSION_MODULES               61
PUBLIC_EXTENSION_NAMES        1126
XNA_NAMESPACE_CONTAMINATION      0
EXTENSION_SURFACE_DIAGNOSTICS    0
```

`cna.extensions.graphics`, `.content`, `.engine`, `.devices`, `.input`,
`.online`. The dependency runs extension → strict, never the other way.

## 11. Tests

| artifact | tests | skipped | result |
| --- | --- | --- | --- |
| no CNA library | 1,592 | 1,022 | OK |
| `~/deps/cna-c-abi-0.21.0` (HEADLESS) | 1,592 | 644 | OK |
| `~/deps/cna-c-abi-0.21.0-opengl33` (OPENGL33, Xvfb `:171`) | 1,592 | 636 | OK |

`SDL_VIDEODRIVER=x11`, `WAYLAND_DISPLAY` unset for the rendering artifact.

## 12. The artifacts changed under this session

The two build trees this session began against --
`cnanext/cmake-build-headless` (sha256 `94078be9…`) and
`cmake-build-opengles3` (sha256 `65ce46a4…`), both built 2026-09-01 -- were
**removed by another agent's rebuild while this session was running**. The
online scope was qualified against them and those results stand; everything
after was re-qualified against the pinned artifacts named in section 11.

No artifact that remains exports
`cna_network_session_replace_session_properties`. Seven were measured and all
export 4,054 of the headers' 4,055 routes. The loader used to refuse any library
missing a bound symbol, which is right for drift and wrong for a route CNA has
declared and not yet built: it made the other 4,054 unusable. It now carries
`_cna_native.loader.PENDING_ROUTES` -- one entry, with the measurement written
into it -- and a route on that list binds to a stub that raises when *called*.
Every other missing symbol still refuses the library, and
`tests/test_pending_routes.py` requires that.

**Nothing in cnanext was built, modified or cleaned.** cnanext has another
agent's uncommitted changes to `Effect.cpp`, `EffectTests.cpp` and
`ThirdPartyFNA3D.cmake`, and building there would have compiled them.

## 13. Falsifiability

| suite | planted | killed | survived |
| --- | --- | --- | --- |
| `tools/mutation/cnb_mutations.py` | 35 | 35 | 0 |
| `tools/mutation/engine_mutations.py` | 47 | 47 | 0 |
| `tools/mutation/device_mutations.py` (devices, input, online) | 76 | 76 | 0 |
| `tools/mutation/pipeline_mutations.py` (pipeline, Xbox, phone) | 99 | 99 | 0 |

**257 planted defects, 257 killed.** Thirty-four survived a first run and were
real test gaps, every one closed. Three mutations were *withdrawn* as provably
equivalent, each with the measurement that proves it recorded beside it: CNA
rewinds a packet reader itself, swapping two equal DXT endpoints is a no-op, and
a power-of-two resize never averages two source pixels.

The device and input mutation suite needs a *rendering* artifact: run it with
`CNA_NATIVE_LIBRARY` pointing at the OpenGL 3.3 build and `DISPLAY=:171`. Run
without one it reports 28 false survivors, because the device layer is absent
and every device test skips.

## 14. Sensors and device services

206 routes, 177 bound, eight modules. Exact `DateTimeOffset` with integer ticks,
four sensors over one state machine, five reading structures built by CNA's own
`*_init_from_values` constructors, the camera, host services, non-modal dialogs,
vibration.

Every result is `SYNTHETIC_BACKEND_VERIFIED`. No sensor was tilted, no camera
opened, no motor spun, no window reached a desktop. `docs/device-extensions.md`.

## 15. Extended input

126 routes, 119 bound, ten modules: text input with surrogate pairing, cursors,
joysticks, haptics, device enumeration, clipboard, comparison.
`docs/input-extensions.md`.

## 16. The online profile

`xna40-windows-online`: 74 types, 605 members, zero diagnostics. 437 routes,
416 bound; the 21 that are not carry a written reason each.

Nothing signs anyone in. Creating a session needs a signed-in gamer, which is
platform identity; CNA has a publication route a platform layer would call and
this package never calls it from shipping code. Every result is
`SYNTHETIC_SIGNED_IN_GAMER_VERIFIED`, never `REAL_PLATFORM_SIGN_IN_VERIFIED`.
`docs/online-profile.md`.

## 17. The Content Pipeline

128 types, 598 members, zero diagnostics, and no CNA route at all.

Every decoder it needs is written here: PNG (all five filters, palettes,
transparency), BMP, TGA (plain and RLE), DDS (uncompressed and DXT), RIFF/WAVE
with its `smpl` loop region, MPEG audio and ASF headers, DirectX `.x`. PIL and
fontTools are installed on this machine and neither is used.

The oracle is `Microsoft.Xna.Framework.Content.ContentManager`, in this
repository, reading what the compiler writes. Thirteen value types, four list
types, a texture and a whole model built from a `.x` file round-trip through it,
the model inside a running `Game`. `docs/content-pipeline.md`.

## 18. The Xbox 360 profile

318 types, 2,986 members, zero diagnostics. A **surface** profile: importing
from `cna.profiles.xbox360` gives exactly the names an Xbox build has, so a
Windows-only name is an `ImportError` there. It is not an Xbox runtime; results
are `XBOX_SURFACE_VERIFIED_ON_WINDOWS` and never `XBOX_HARDWARE_VERIFIED`.

Generated by `tools/generate_platform_profile.py` from the contract: 316
re-exports and nine narrowed types. `docs/xbox360-profile.md`.

## 19. Windows Phone

`BLOCKED_REFERENCE_ASSET`, and the block is measured rather than asserted. The
machinery is parameterised, so the day the assemblies are under
`~/deps/xna40-windowsphone-assemblies` the profile is three commands. Everything
that does not depend on them is done: the XNB platform byte, the Reach limits,
touch and the accelerometer. `docs/windowsphone-profile.md`.

## 20. Upstream findings

Five, in `docs/online-upstream-findings.md`, each with a reproducer and a test
that fails the day CNA fixes it:

1. A `Color` written into a packet cannot be read back: the writer packs four
   bytes and `cna_packet_reader_read_color` consumes sixteen.
2. `cna_avatar_description_create_random_for_body_type(MALE)` answers a Female
   description.
3. Network-gamer handles are rejected by every `cna_gamer_*` route, and
   `net_gamers.h` has no gamertag route.
4. A disposed session's handle can never be released.
5. No CNA artifact exports
   `cna_network_session_replace_session_properties` -- rewritten today with the
   seven-artifact measurement.

Eight further engine findings remain in `docs/engine-extensions.md`.

## 21. Blockers recorded this session

Each names what would unblock it, and each has a working path beside it.

| blocker | why | unblocked by |
| --- | --- | --- |
| `EffectProcessor.Process` | no HLSL compiler; CNA's `effects.h` says it embeds none | a CNA route from effect source to bytecode |
| `FontDescriptionProcessor.Process` | no TrueType rasterizer anywhere | a CNA route that rasterizes a font file |
| `FbxImporter.Import` | FBX has no public specification | a CNA route that imports FBX |
| `BuildXact.Execute` | the XACT tool is Windows-only and not redistributable | a CNA route that compiles an `.xap` |
| `AudioContent.Data` for MP3/WMA | CNA decodes to a `SoundEffect` and exposes no PCM read-back | any route that copies a decoded effect's samples |
| compressed XNB output | this repository has the LZX *decompressor* only | an LZX compressor |
| Windows Phone profile | reference assemblies measured absent | the assemblies |
| running on a console or a phone | no hardware, and CNA targets neither | hardware, and a CNA that targets it |

## 22. Improvements to the shared gates

Opening profiles with two-parameter generics, several indexers per type, generic
methods and a second mscorlib found six real gaps in machinery that had been
green for months:

1. `!N` (a declaring type's generic parameter) and `!!N` (a member's) were
   resolved against one list -- accidentally right for every single-parameter
   generic until `ChildCollection<TParent, TChild>`.
2. A type with two indexers had one checked and one missing from its stub. Five
   runtime types really do accept a string key and their stubs said otherwise.
3. An indexer's writability was read from one overload.
4. Arity counted a keyword standing in for a type argument.
5. `System.Collections.IList` had no interface projection.
6. The two mscorlibs encode `where T : struct` differently, and counting the
   difference made twenty-odd identical graphics signatures look platform
   specific.

## 23. New tools

| tool | what it answers |
| --- | --- |
| `tools/verify_stop_condition.py` | are the six scopes finished? one command, 45 counters |
| `tools/verify_content_pipeline.py` | does every projected member do something? |
| `tools/verify_profile_separation.py` | do the profiles leak into each other? |
| `tools/verify_blocked_profiles.py` | is a declared block still a block? |
| `tools/generate_platform_profile.py` | generates a platform import root from its contract |
| `tools/find_reference_assemblies.py` | are a profile's assemblies on this machine? |
| `tools/cli_assembly.py` | what platform is this managed assembly for? |

## 24. Qualification commands

```sh
export PYTHONPATH=$PWD/src:$PWD
CNA=/rv/data/development/github.com/openeggbert/cnanext

for p in xna40-windows-runtime xna40-windows-online \
         xna40-windows-content-pipeline xna40-xbox360-runtime; do
  python3 tools/api_compat/verify.py --profile "$p" --check
done
python3 tools/route_census.py --cna-root "$CNA" \
  --output docs/generated/cna-route-census.json \
  --markdown docs/generated/cna-route-census.md
python3 tools/verify_route_reachability.py --output docs/generated/route-reachability.json
python3 tools/verify_prototypes.py --cna-root "$CNA"
python3 tools/audit_cna_abi.py --cna-root "$CNA" \
  --library ~/deps/cna-c-abi-0.21.0/libcna_c_api.so \
  --output docs/generated/cna-abi-report.json
python3 tools/verify_extensions.py --output docs/generated/extension-surface-report.json
python3 tools/verify_stubs.py
python3 tools/verify_content_pipeline.py --output docs/generated/content-pipeline-coverage.json
python3 tools/verify_profile_separation.py --output docs/generated/profile-separation.json
python3 tools/verify_blocked_profiles.py --output docs/generated/blocked-profiles.json
python3 tools/verify_stop_condition.py --output docs/generated/stop-condition.json
```

## 25. Git

On `develop`, five commits ahead of `b384bf2`, working tree clean.
**Nothing has been pushed**, and no push instruction has been given.

## 26. What is left

There is no selected scope with outstanding work and no actionable-local route
or member anywhere. What remains is not this session's:

* **Waiting on CNA** -- the five online findings, the eight engine findings, the
  six blockers in section 21 that name a CNA route.
* **Waiting on hardware** -- a console, a phone, a device with real sensors.
  Every claim about them is refused rather than approximated.
* **Waiting on a file** -- the Windows Phone reference assemblies.
* **Ordinary maintenance** -- packaging and release qualification, real-game
  compatibility testing, re-qualification when a newer CNA artifact appears
  (which will also retire `PENDING_ROUTES`).

## 27. If you pick this up

Run `python3 tools/verify_stop_condition.py` first. If it says `held`, nothing
below the line has regressed and you can start wherever you like. If it does
not, it names the counter, the scope that owns it and the gate that wrote it.

Then read the scope documents rather than the code: `docs/device-extensions.md`,
`docs/input-extensions.md`, `docs/online-profile.md`,
`docs/content-pipeline.md`, `docs/xbox360-profile.md`,
`docs/windowsphone-profile.md`. Each one says what was decided, what was
measured, and what was deliberately not done.
