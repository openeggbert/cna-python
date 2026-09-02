# The `xna40-windows-online` strict profile

XNA's Net, GamerServices and Avatar runtime, opened by explicit product decision
on 2026-09-02. This is **strict XNA surface**, not a CNA extension: the names are
`Microsoft.Xna.Framework.Net` and `Microsoft.Xna.Framework.GamerServices`, and
they are measured against Microsoft's own metadata.

## Reference authority

```text
profile      xna40-windows-online
assemblies   Microsoft.Xna.Framework.GamerServices.dll  7c6effed97aa…
             Microsoft.Xna.Framework.Net.dll            39739dbf5f6b…
             Microsoft.Xna.Framework.Avatar.dll         b3c70bbe4690…
types        74
members      676 CLR, of which 605 map to a Python member
```

The gap between the two is mapping, not omission: every CLR member that does not
become a distinct Python member is a decision the strict verifier prints with
its reason, and `TOTAL_DIAGNOSTICS` counts anything that is not one.

The contract is generated from those three assemblies by
`tools/api_compat/extract_reference.py`, the same tool that re-derives the
already-accepted 257-type Windows runtime contract byte for byte.

## Why a separate profile rather than a bigger one

The Windows runtime profile is seven assemblies and 257 types, and it has been
green for the whole project. These three are *different assemblies of the same
platform*: a game that references them gets these names in namespaces it already
had, and one that does not is unaffected.

So they are a separate **profile** that shares two Python packages with the
runtime one, and the sharing is declared rather than assumed. Each profile
verifies against its own contract; a name a declared sibling owns is out of
*this* profile rather than unexpected; a name belonging to neither is still
`UNEXPECTED_TYPE`. That is what keeps "the Windows runtime profile is exact" a
real claim now that three more profiles exist.

```text
xna40-windows-runtime   257 types  2,423 members  TOTAL_DIAGNOSTICS=0
xna40-windows-online     74 types    605 members  TOTAL_DIAGNOSTICS=0
```

The two contracts share no type name: the runtime profile owns
`GamerServicesComponent` (declared by `Microsoft.Xna.Framework.Game.dll`) and
this one owns the other 51 GamerServices types and all 23 Net types.

## Route scoreboard

```text
ONLINE_ROUTES                     437
ONLINE_BOUND                      416
ONLINE_UNREVIEWED                   0
SELECTED_ONLINE_ACTIONABLE_LOCAL    0
```

The 21 unbound routes are decisions, each with a written reason: value-structure
initialisers and CLR type names the census already refused, five disposed-flag
routes (Python's ownership model is authoritative earlier than CNA's flag and
stays correct after the handle is released), the three dispatcher routes the
Windows runtime profile already imports, and CNA's canonical gamer-services
component -- creating one beside this projection's `GamerServicesComponent` would
pump the dispatcher twice.

## Nothing signs anyone in

Creating a session needs a signed-in gamer, which is *platform identity*. CNA has
a publication route a platform layer would call; this package never calls it, and
it lives in `cna.extensions.online` where a game will not reach for it by
accident. Every result the qualification obtains through it is labelled
`SYNTHETIC_SIGNED_IN_GAMER_VERIFIED` and never `REAL_PLATFORM_SIGN_IN_VERIFIED`.
No account signed in to anything, and no second machine was involved.

## What CNA adds, and where it lives

`cna.extensions.online` carries the CNA-only surface *around* the strict profile:
publishing gamers, filling a session's roster, delivering a packet as if a
transport had received it, reading and drawing the Guide's pending request,
naming an avatar's real animation clip. None of it is XNA, so none of it is in an
XNA namespace, and the extension gate asserts the dependency runs one way.

The Guide's pending request is worth naming: XNA's Guide draws itself, and on a
host with no platform overlay there is nothing to draw. CNA holds the request
instead -- the title, the text, the buttons, the focus button -- so a title can
draw it with its own `SpriteBatch` and font. That is a real capability rather
than a stub.

## Exactness where it is quiet

* **Ticks.** Achievement timestamps, leaderboard ratings, round-trip times and
  simulated latency are 64-bit integers throughout. A rating past 2**40 and a
  present-day timestamp both survive, and a planted double conversion is killed.
* **Nullable slots.** `NetworkSessionProperties` holds `int | None`. A slot
  nobody set is *absent*, not zero, because discovery matches on the slots that
  are set.
* **Typed columns.** `PropertyDictionary` asks CNA which CLR type a value really
  is and returns that Python type. A `bool` is refused rather than stored as an
  integer: XNA has no boolean column, and Python's `bool` being an `int` is
  exactly how one would get there.
* **One native subscription per event.** A session subscribes nine times and fans
  out in Python, so a second handler on `GamerLeft` does not add a second native
  subscription and the delivery order stays the event's.
* **Events arrive on `Update`.** Nothing is delivered while the session is not
  pumped, and everything is when it is -- which is XNA's contract, and both
  halves are asserted.

## Language-mapping limitations, named

* XNA has `Write(float)` and `Write(double)`, and Python has one floating type.
  `PacketWriter.Write` takes the wider one; the narrower route is private and the
  qualification proves it is narrower by writing 0.1 and reading back something
  that is not the double 0.1. `PropertyDictionary.SetValue` is the same shape.
* `SerializationInfo` and `StreamingContext` both map to `object`, so an
  exception's serialization constructor would be indistinguishable from
  `(message, innerException)`. It is not projected; `GetObjectData` is, because
  its two parameters are positional and it has a name of its own.

## Upstream

Five findings, each with a reproducer and a test that fails when it is fixed:
see `docs/online-upstream-findings.md`.
