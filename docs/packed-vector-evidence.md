# PackedVector evidence

Foundation Milestone 7 completes the exact nineteen-type
`Microsoft.Xna.Framework.Graphics.PackedVector` family as pure managed Python.
The XNA 4.0 Windows metadata contract and reference algorithms are authoritative;
the CNA-CS/Java/Rust implementations were used only as corroborating engineering
evidence. No CNA symbol, ctypes declaration, native handle, or runtime-capability
row was added.

## Public identities and storage

CLR `IPackedVector` remains Python `IPackedVector`. The colliding generic CLR
identity `IPackedVector<TPacked>` is deterministically exported as
`IPackedVectorOfT[TPacked]`. These are distinct runtime classes, the TypeVar/base
relation is verifier-measured, and every concrete struct implements the typed
interface. There is no alias, allowlist, or extra XNA type.

Every `PackedValue` setter validates a non-Boolean Python integer against its
exact unsigned storage width and rejects negative or oversized values:

| Width | Concrete types |
| --- | --- |
| UInt8 | Alpha8 |
| UInt16 | Bgr565, Bgra4444, Bgra5551, HalfSingle, NormalizedByte2 |
| UInt32 | Byte4, HalfVector2, NormalizedByte4, NormalizedShort2, Rg32, Rgba1010102, Short2 |
| UInt64 | HalfVector4, NormalizedShort4, Rgba64, Short4 |

All seventeen structs implement their complete selected constructors and
conversion helpers, `PackedValue`, `PackFromVector4`, `ToVector4`, `Equals`,
`GetHashCode`, `ToString`, equality operators, and Python shallow/deep value
copy. Type-specific `ToAlpha`, `ToSingle`, `ToVector2`, and `ToVector3` members
are present where selected. Returned vectors are fresh values.

## Bit algorithms

Packing narrows each input/intermediate to binary32 in XNA operation order,
clamps before conversion, and applies reference nearest-even midpoint behavior.
The implementation preserves each exact mask, shift, lane order, alpha
position, BGR order, signed-short sign extension, and the reserved signed-normal
minimum. NaN follows the observed XNA zero-before-clamp path; positive and
negative infinity saturate at the corresponding bound.

The normalized families independently verify -1, 0, +1, out-of-range values,
reserved signed minima, and values adjacent to quantization boundaries. The
integer/color families independently verify 5/6/5, 4/4/4/4, 5/5/5/1,
8-bit lanes, 16-bit lanes, 10/10/10/2, 64-bit RGBA, and signed Short lane order.

## Historical half format

XNA's HalfSingle conversion is not IEEE binary16 and therefore does not use
Python `struct.pack("e")`. It has no encoded infinity/NaN class: exponent 31 is
finite, `0x7C00` expands to binary32 65536, and `0x7FFF` expands to 131008.
Overflow, infinity, and NaN saturate to signed `0x7FFF`; signed zero and gradual
subnormals are preserved. The explicit integer algorithm performs the XNA
mantissa tie adjustment and is shared by HalfSingle/HalfVector2/HalfVector4.

Tests cover ±0, smallest subnormal, subnormal/normal boundary, max finite,
overflow, both infinities, NaN, exponent-31 decoding, and nearest-even midpoint
cases. Exact stored bits, not approximate unpacked values, are the primary
oracle.

## Qualification

`tests/test_packed_vectors.py` contains ten focused test methods. The behavior
corpus has seventeen `PURE_XNA_DERIVED` PackedVector observations—one per
concrete type—with default zero, ordinary, boundary, clamp, round-trip,
PackedValue identity, and equality assertions. HalfSingle additionally records
subnormal/non-finite/exponent-31 results. All pass, and every one of the
nineteen public types has zero local structural diagnostics.
