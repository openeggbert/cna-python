# The Windows Phone profile: blocked on a file, and on nothing else

`xna40-windowsphone-runtime` is declared and not built.
`BLOCKED_REFERENCE_ASSET`, with the measurement below and an unblock condition
that is one directory.

## Why there is no contract

Every profile here is derived from Microsoft's own metadata. That is what makes
the other four exact — 257, 74, 128 and 318 types, each verified member by
member against the assemblies that declare them — and it is the reason this one
does not exist. A Windows Phone contract written from documentation, from
memory, or from what the Windows one happens to have would be a *guess wearing
the same clothes as a measurement*, and every number in this repository would be
worth less for it.

So: no contract file, no import root, and the profile descriptor says why.

## The measurement

`tools/find_reference_assemblies.py`, run on 2026-09-02:

```text
ASSEMBLIES_WANTED                7
ROOTS_SEARCHED                   8
FILES_EXAMINED           1,296,128
NAME_MATCHES                    36
PINNED_BY_ANOTHER_PROFILE       24
IDENTIFIED_AS_DESKTOP           30
CANDIDATES                       0
UNIDENTIFIED                     0
SDK_MARKERS_FOUND               15
```

Recorded in `docs/generated/windowsphone-assembly-search.json`.

Thirty-six files matched by *name*, which is the trap a file-name search walks
into: XNA ships `Microsoft.Xna.Framework.dll` on every platform it ever
targeted. So each hit is identified rather than counted:

* twenty-four are byte-for-byte assemblies another profile already pins — the
  Windows and Xbox 360 reference sets, and a decompilation working copy of the
  Windows ones;
* the rest are the XNA 4.0 *redistributable* in a Wine prefix's .NET GAC.

`tools/cli_assembly.py` reads the PE and CLI metadata and answers what each file
was compiled against, because that is what actually separates the platforms:

| assembly | references |
| --- | --- |
| Windows reference set | `mscorlib, Version=4.0.0.0` |
| Xbox 360 reference set | `mscorlib, Version=2.0.5.0` |
| the Wine GAC copies | `mscorlib, Version=4.0.0.0` |

Windows Phone 7 XNA references the 2.0.5.0 core library, like the Xbox one.
Nothing on this machine that is not already an Xbox assembly does. Fifteen
directories matched an SDK marker; fourteen are a game called
*WindowsPhoneSpeedyBlupi* and its build trees, and the fifteenth is the XNA 4.0
redistributable — no Game Studio reference assemblies, and no
`Reference Assemblies\Microsoft\Framework\WindowsPhone` tree anywhere.

The reader is checked against the two platforms this repository *does* have,
where the answer is known independently.

## The block has to keep earning it

`tools/verify_blocked_profiles.py` runs in the gate battery:

```text
BLOCKED_PROFILES      1
UNJUSTIFIED_BLOCK     0
BLOCK_WITHOUT_REASON  0
STALE_BLOCK           0
SEARCH_MISSING        0
```

* **`UNJUSTIFIED_BLOCK`** — a profile that names a contract, or has a contract
  file, is not blocked on being able to measure it.
* **`BLOCK_WITHOUT_REASON`** — a reason and an unblock condition, both written
  out. "It is not here" is not a finding.
* **`STALE_BLOCK`** — the recorded search found a candidate after all, so the
  descriptor is what is now wrong.
* **`SEARCH_MISSING`** — no recorded search, one run for a different profile,
  one that looked for a different assembly set, or one that left a file it could
  not identify.

Each is planted and required to fail in `tests/test_windowsphone_profile.py`.

## What was *not* blocked, and is done

A blocked profile does not excuse the work that does not depend on it.

* **The machinery.** `tools/generate_platform_profile.py` takes `--profile`. It
  is not named after Xbox because it is not about Xbox: the day the phone
  assemblies are under `~/deps/xna40-windowsphone-assemblies`, the profile is
  three commands — extract the contract, generate the root, generate the stubs
  — and the strict verifier then measures it like the other four. The Xbox 360
  profile is the proof that those three commands work, 316 re-exports and nine
  narrowed types of it.
* **Windows Phone is a content-pipeline target, today.**
  `TargetPlatform.WindowsPhone` writes its own platform byte — `m` — into the
  XNB header, and a test asserts it, along with this repository's Windows reader
  refusing a file built for another platform.
* **Windows Phone is Reach**, and Reach's limits are enforced and measured:
  2048-pixel textures, powers of two for compressed formats, no volume
  textures.
* **Touch and the accelerometer**, the two things a phone adds, are already
  projected. `Microsoft.Xna.Framework.Input.Touch` is in the Windows runtime
  profile because XNA puts it there; the accelerometer is CNA's, in
  `cna.extensions.devices`, with a synthetic backend and no hardware claim.

## What unblocking would *not* give

A surface. The Xbox 360 profile's own documentation says this and it is worth
repeating here: there is no phone in this repository and CNA does not target
one. A Windows Phone profile would let a developer check, on the machine in
front of them, that the names they used exist on the platform they are aiming
at. Running there stays `BLOCKED_PLATFORM`.
