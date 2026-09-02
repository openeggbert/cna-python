# `cna.extensions.devices`: sensors and device services

The fourth public CNA extension family, opened by explicit product decision on
2026-09-02. It projects `sensors.h` and `devices.h`: the four device sensors, the
camera, and the host services a game asks about.

## Product decision

Sensors and device services were a single blanket census rule --
"CNA-only capabilities outside the selected XNA profile and outside the selected
extension profile" -- covering 206 routes. That rule is gone, replaced by
eighteen per-sub-family rules with written reasons.

```text
DEVICES_ROUTES                      206
DEVICES_BOUND                       177
DEVICES_UNREVIEWED                    0
SELECTED_DEVICES_ACTIONABLE_LOCAL     0
```

The 29 unbound routes are decisions the census already made and this family did
not reopen: 22 CLR type-name routes (`NOT_USEFUL_FOR_PYTHON` -- Python names its
own types) and 7 value-structure initialisers (`MANAGED_BY_DESIGN` -- Python
builds those structures from their measured ctypes layout). The manifest reads
that refusal out of the census rather than restating it, so the two cannot
disagree.

## Why not `Microsoft.Xna.Framework`

XNA 4.0 on Windows has no accelerometer, no compass, no gyroscope, no fused
motion sensor, no camera, no clipboard, no locale list, no battery, no file
dialog, no message box, no system tray, and no controller vibration beyond
`GamePad.SetVibration`. A name in `Microsoft.Xna.Framework` is a claim about XNA,
and every one of these would be false. The extension gate asserts in a fresh
interpreter that importing the XNA namespace loads no `cna` module.

## Public surface

| Module | What it carries |
|---|---|
| `values` | `DateTimeOffset` and the six enumerations |
| `sensors` | `Accelerometer`, `Compass`, `Gyroscope`, `Motion`, five readings, subscriptions |
| `camera` | enumeration, `Camera`, frame acquisition into a `Texture2D` |
| `host` | clipboard, display metrics, device class, locales, power, system information, URL launcher |
| `dialogs` | file dialogs, message boxes, the system tray |
| `vibration` | support, intensity, two motors, duration, the test log |
| `errors` | the seven exceptions, separating four different kinds of "no" |
| `testing` | CNA's deterministic backends -- qualification only |

## Time is exact

Every timestamp and every duration is a 64-bit count of 100-nanosecond ticks and
stays a Python integer. A present-day timestamp is around 6.4e17 ticks, seventy
times 2**53, and the fixtures sit there on purpose: a test asserts that two
adjacent tick counts collapse to the *same* double, which is why nothing in this
family converts one.

`DateTimeOffset.to_datetime` is lossy by construction -- `datetime` resolves
microseconds and these ticks do not -- so `sub_microsecond_ticks` exposes the
0..9 ticks it cannot carry rather than dropping them. `offset` refuses rather
than rounds when the UTC offset is not a whole number of microseconds.

## Evidence

Everything is `SYNTHETIC_BACKEND_VERIFIED`. CNA supplies a deterministic backend
for every family that needs one, and the qualification uses it:

| Family | Backend | What it proves |
|---|---|---|
| Accelerometer, gyroscope | `inject_synthetic_update`, forced supported/started flags | the state machine, the unit conversion, callback delivery, dispatch to several sensors |
| Compass, motion | `set_test_backend` plus a whole injected reading | every field of a reading, calibration events |
| Camera | `create_with_test_backend`, `set_test_frame` | the frame protocol, pixel-for-pixel into a `Texture2D` |
| File dialog | `set_test_backend` | the exactly-once answer, cancellation as an empty result |
| Message box | `set_test_backend` | the chosen button, the call log |
| System tray | `create_with_test_backend`, `click_entry` | per-entry handlers, entry state |
| Vibration | `set_test_backend` | exact tick durations, the two motors, the call log |

The unit conversion is CNA's and is checked as such: CNA documents that an
accelerometer injection is in platform units and the reading is in g, so
injecting 9.80665 must read back as exactly 1. A pass-through fails.

**No result here is `PHYSICAL_HARDWARE_VERIFIED`.** No accelerometer was tilted,
no camera opened, no motor spun, and no window reached a desktop. What *is*
real-host evidence, and is marked as such, is the power state, the preferred
locale list, the CPU and memory counts, the clipboard round trip, and camera and
device enumeration -- all non-invasive.

## Two kinds of "not supported"

Every device route is exported in every CNA build, and the ones that need the
device-services layer answer `CNA_RESULT_NOT_SUPPORTED` when it was configured
out -- the same code a host without a battery gives. `device_services_available`
asks `cna_devices_ext_is_available` rather than assuming, and a build with no
layer raises `DeviceServicesUnavailableError` instead of the generic unsupported
error. The control artifact has no device-services layer; the OPENGLES3 one does.

## Falsifiability

31 defects planted in this family and the input family, 31 killed, 0 survivors.
Four survived the first run and were real test gaps, now closed: an oracle that
shared the implementation's ordering, a duration checked on only one route, a
trampoline release nothing exercised, and a guard whose refusal was
indistinguishable from CNA's own.
