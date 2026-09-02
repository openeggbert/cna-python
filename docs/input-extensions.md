# `cna.extensions.input`: extended input

The fifth public CNA extension family. It projects `input_text.h`,
`input_cursor.h`, `input_joystick.h`, `input_haptics.h` and `input_devices.h`.

```text
INPUT_ROUTES                      126
INPUT_BOUND                       119
INPUT_UNREVIEWED                    0
SELECTED_INPUT_ACTIONABLE_LOCAL     0
```

The 7 unbound routes are value-structure initialisers the census already decided
are `MANAGED_BY_DESIGN`.

## Why not `Microsoft.Xna.Framework`

XNA reads *keys*, not characters, and has nowhere for a composition update or an
IME candidate list to go. It knows one keyboard and one mouse. It exposes exactly
one thing about the cursor, `Game.IsMouseVisible`. Its vibration is two motors
with one strength each, where a haptic device has constant forces, periodic
waveforms, ramps, conditions, custom sample data, gain, autocentring, pause and
resume. And a raw joystick -- however many axes, buttons, hats and balls it
actually has -- is the unmapped device `GamePad` exists to hide.

## Three things this family gets right on purpose

**UTF-16 is not characters.** CNA delivers committed text one UTF-16 code unit at
a time, and a code point above U+FFFF arrives as two calls -- a high surrogate
then a low one -- exactly as the platform event does. Nothing here silently pairs
them: `TextInputAccumulator` is the one explicit, testable place a pair becomes a
character, and an unpaired surrogate is reported through `unpaired` rather than
replaced with U+FFFD, because a replacement character is a different string from
what was typed. The fixture `"Hé😀"` is three characters and four code units.

A composition update's `start` and `length` index code units in its own text,
which is what an editor must apply them to, and are not converted into anything.

**A hat position is an identity, not a bit set.** The canonical header says so in
as many words: `RIGHT_UP` is the identity 5, not `RIGHT | UP`. `JoystickHatPosition`
is therefore an `IntEnum`, and a test asserts it is not a `Flag` -- a flag
projection would make `Left | Up` produce 12, a position CNA never reports, and
would let `JoystickHatPosition(9)` exist.

**An index is not an id.** Joysticks and haptic devices enumerate by index and are
opened by instance id. Every function says which it takes, and `JoystickInfo`
carries the id so a caller can go from one to the other.

## The active cursor is borrowed

CNA states it: "the C API does not keep the cursor alive on the caller's behalf:
releasing it while it is the active cursor is the caller's responsibility to
avoid". So `MouseCursor.close()` refuses while the cursor is the active one, and
`close(force=True)` is the deliberate way out for the last cursor at shutdown --
there is no way to un-set an active cursor, so somebody eventually has to say
that this one is finished with.

## Absence is reported through the values

Two behaviours were measured rather than assumed, and both turned out to be CNA
being careful:

* Capturing the state of a joystick id nothing is plugged into **succeeds** and
  hands back an empty snapshot -- zero axes, zero buttons, zero hats -- and the
  capabilities say `is_connected=False` with an empty name.
* Opening a haptic device that is not there **succeeds** and hands back a real
  object whose `is_open` is False and whose every request reports "not applied".
  CNA documents this: "a failure to open is not an error".

Both are asserted, including that CNA's `-1` sentinels for an unknown battery
percentage and unknown effect limits arrive as `None`.

## Evidence

Text input, IME composition, candidate lists and hotplug are
`SYNTHETIC_BACKEND_VERIFIED` through CNA's raise routes. Device, joystick and
haptic enumeration are real host measurements and are non-invasive; an empty list
is a measurement, not a failure. Text input *becoming* active needs a real
window, so that claim is made by the windowed artifact and the non-windowed one
asserts the honest weaker answer rather than skipping.

CNA's own comparison for each value structure is exposed in
`cna.extensions.input.comparison`, so Python's field-wise equality has an
independent oracle rather than being the only answer.
