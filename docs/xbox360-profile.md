# The `xna40-xbox360-runtime` surface profile

XNA 4.0 as the Xbox 360 declares it: 318 types, 3,577 CLR members, 2,986 mapped
Python members, zero diagnostics. Opened by product decision on 2026-09-02,
against the ten Xbox reference assemblies and the Compact Framework `mscorlib`
they were built for.

## What it is, and what it is not

It is a **surface**. Importing from `cna.profiles.xbox360` gives exactly the
names an Xbox build of XNA has, so a name that is Windows-only is an
`ImportError` there rather than a link error on a console nobody has. That is
what a developer can use on the machine in front of them.

It is **not an Xbox runtime**. There is no Xbox hardware in this repository and
CNA does not target one, so nothing here claims a platform result. Every result
in `tests/test_xbox360_profile.py` is labelled `XBOX_SURFACE_VERIFIED_ON_WINDOWS`
and never `XBOX_HARDWARE_VERIFIED`; running on a console is `BLOCKED_PLATFORM`
and the invalid-stop-reason list in the brief says so more clearly than this
paragraph can.

## The measurement the whole profile rests on

```text
Xbox types not in Windows(runtime + online)          0
Xbox members not in Windows(runtime + online)        0
Windows types not on Xbox                           13   (Microsoft.Xna.Framework.Design)
Windows members not on Xbox                         10   (.NET serialization)
Enum value differences                               0
Type shape differences (kind, base, sealed, flags)   0
```

Xbox 360 XNA is the Windows runtime and online surfaces together, minus thirteen
`Microsoft.Xna.Framework.Design` type converters -- which need
`System.ComponentModel` -- and minus ten members that exist only because the
Windows assemblies were built against the full .NET Framework. There is nothing
on Xbox that Windows does not have, and the test suite asserts that rather than
assuming it.

## So the projection is generated, not written

`tools/generate_xbox_profile.py` reads the Xbox contract and emits one package
per namespace under `cna.profiles.xbox360`, re-exporting the Windows
implementation of each type it has. Writing 316 re-exports by hand would be
writing the contract out a second time in a place nothing checks against the
first; `--check` regenerates into memory and reports whether anything would
change, and the test suite runs it.

Nine types are *generated* rather than re-exported, because their Xbox surface
really is different. Eight of them differ only by a constructor overload that
collapses onto the same Python `__init__`, so the Python surface is unchanged;
the ninth, `NetworkSessionJoinException`, also loses `GetObjectData`.

## How a member that is not there is spelled

`_RemovedOnPlatform` is a descriptor that raises `AttributeError` **on access**.
`hasattr` answers False, `getattr` with a default answers the default, and code
that asks before calling behaves the way it would on the console. Raising only
when the member was *called* would let all three of those lie.

It is a descriptor rather than a deletion because the narrowed type inherits
from the Windows one -- which is what keeps

```python
except NetworkException:
```

catching an Xbox `NetworkSessionJoinException` -- and inheritance has no way to
take something back.

The strict verifier treats a removed member as absent, which is what makes the
Xbox profile verify against its own contract. That would be a way to hide any
member, so it is checked: `tools/verify_profile_separation.py` requires every
removal to be a member the platform contract does **not** have and the Windows
contract does, and a planted removal that the platform's own contract
contradicts is reported.

## Keeping the profiles apart

`tools/verify_profile_separation.py`:

```text
DEFAULT_PROFILE_TYPES                     257
DEFAULT_PROFILE_MEMBERS                  2423
PLATFORM_LEAKS                              0
WINDOWS_ONLY_REACHABLE_FROM_PLATFORM        0
UNJUSTIFIED_REMOVALS                        0
DEFAULT_PROFILE_DRIFT                       0
```

* **`PLATFORM_LEAKS`** -- a platform's surface must never enlarge the default
  Windows one. Today there is nothing to find, because there is no Xbox-only
  type; the check exists for the day there is.
* **`WINDOWS_ONLY_REACHABLE_FROM_PLATFORM`** -- the direction that makes the
  profile useful. Every name any Xbox package exports is checked against the
  Windows-only set, wherever it came from, and a namespace the Xbox root has no
  package for is checked by *importing* it rather than by assuming.
* **`DEFAULT_PROFILE_DRIFT`** -- the numbers this repository has held since
  before any of the other profiles existed, read from the strict verifier
  itself. Asked for a different expected count, the gate objects; a test
  requires it to.

Each of the first three is planted and required to fail in
`tests/test_xbox360_profile.py`.

## The metadata difference that was nearly reported as a platform difference

The two `mscorlib`s encode `where T : struct` differently. .NET 4.5's records
the special constraint alone; the Compact Framework's records it **and** an
explicit `System.ValueType` type constraint. They say the same thing, and
counting the second one made twenty-odd identical graphics signatures --
`Texture2D.SetData<T>`, `GraphicsDevice.DrawUserPrimitives<T>` and their
relatives -- look different on the two platforms.

The verifier now drops a `System.ValueType` constraint that sits beside the
`struct` special constraint, in one helper both the name projection and the
bound comparison read. A profile comparison that reported an encoding as a
platform difference would be worse than none, and this is the one place it could
have.

The interface *closures* differ for the same reason and are not compared: the
Compact Framework has no `ISerializable`, no `_Exception`, no
`IReadOnlyList<T>`, no `IAsyncDisposable`. The eleven **direct** interface
differences are real and are all XNA's own internal `IGraphicsResource` and
`IDynamicGraphicsResource`, which the Xbox assemblies do not declare.
