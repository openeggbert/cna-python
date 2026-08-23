# Curve evidence

Foundation Milestone 7 completes `Curve`, `CurveContinuity`, `CurveKey`,
`CurveKeyCollection`, `CurveLoopType`, and `CurveTangent` as one pure managed
family. XNA 4.0 Windows metadata and reference IL/algorithms are authoritative.
No CNA ABI route or runtime-capability row was added.

## Keys and collection

CurveKey stores Position, Value, TangentIn, and TangentOut as binary32 and the
exact continuity enum. Position is constructor-fixed; the other scalar fields
remain mutable. CompareTo uses only Position with XNA's comparison branch
semantics, including its observable NaN behavior. Equality, hash, Clone,
operators, shallow copy, and deep copy are value-based.

CurveKeyCollection implements the full selected mutable collection surface.
Add and replacement maintain ascending Position order. A new equal-position key
is inserted after existing equal-position keys, preserving insertion order; the
same object may be added more than once. Contains/IndexOf/Remove use CurveKey
value equality. CopyTo preserves key references, and collection Clone creates
an independent ordered collection with the same key references, matching XNA's
shallow collection clone. Mutating a key's Position is impossible, so ordering
cannot silently decay after insertion.

## Evaluation, loops, and tangents

Evaluate covers empty and singleton curves, exact keys, duplicate positions,
Step continuity, Smooth cubic Hermite segments, and every pre/post loop mode:
Constant, Cycle, CycleOffset, Oscillate, and Linear. Cycle calculation preserves
the XNA negative-position decrement rule and exact-multiple behavior. A
zero-length total key range follows the deterministic reference edge path
instead of delegating to a generic spline library.

Hermite bases and final accumulation use the repository's binary32 helpers in
reference operation order. Segment fraction calculation follows the reference
double intermediate followed by binary32 narrowing; tangent and offset
arithmetic remains binary32. Signed zero and non-finite comparison behavior are
not normalized away.

ComputeTangent and ComputeTangents implement Flat, Linear, and Smooth modes for
first, middle, and last keys. Smooth tangents use actual non-uniform position
spacing and the XNA near-zero value-span check. Singleton and duplicate-position
edges remain explicit.

## Qualification

`tests/test_curve.py` contains ten focused methods covering enum/default state,
stable key ordering, duplicate objects/positions, replacement/removal/CopyTo,
shallow clone independence, key NaN semantics, Hermite/Step evaluation, every
loop mode, negative exact cycles, and all tangent modes. The behavior corpus
adds ten `PURE_XNA_DERIVED` Curve observations with exact binary32 bit strings.
All pass, and all six public types have zero local structural diagnostics.
