# Normative XNA 4.0 to Python mapping

This document defines the strict CNA-Python projection. It is a compatibility
contract, not a style guide. Public XNA identity wins over PEP 8; private
implementation uses ordinary Python conventions.

## Names and type identities

| CLR construct | Python projection |
| --- | --- |
| namespace | same dotted package, e.g. `Microsoft.Xna.Framework.Graphics` |
| class | same PascalCase class name |
| struct | mutable Python value class with boundary-copy behavior |
| interface | abstract/protocol-shaped public class when implemented |
| enum | `enum.IntEnum` with the exact signed value |
| flags enum | `enum.IntFlag` with the exact underlying bits |
| delegate | callable protocol; invocation follows the delegate signature |
| nested type | attribute of the projected declaring type |
| field | same name; mutable fixed-width fields narrow on assignment |
| property | same PascalCase descriptor and mutability |
| static property | class descriptor, accessed without `()`; setter retained when XNA has one |
| indexer | `__getitem__` and, when writable, `__setitem__` |
| event | same PascalCase descriptor using `+=` and `-=` |

`System.Type` service keys map to Python runtime class objects. Service lookup
is exact-keyed by that class, providers must be instances of it, and every
`Game` owns an isolated `GameServiceContainer`; no process-global registry is
part of the projection. CLR dictionary and collection base behavior maps to a
dedicated mutable mapping or sequence facade when its public behavior matters.
Their Python protocol members (`__getitem__`, `__setitem__`, iteration, length,
and sequence `insert`) are language projections rather than additional XNA
declared members.
`List<T>` maps to `list[T]`, `ReadOnlyCollection<T>` maps to `tuple[T, ...]`;
generic enumerable and enumerator results map to `Iterable[T]` and `Iterator[T]`
respectively. An XNA implicit conversion into a value wrapper maps to that
wrapper's constructor. Generic vertex-array methods use `TVertex`, bounded to
`IVertexType`; this keeps their explicit codec/declaration constraint distinct
from unconstrained `T` arrays.

`System.Char` maps to a one-code-unit BMP `str`. `System.Text.StringBuilder`
parameters map to their materialized immutable `str` value, so the String and
StringBuilder overloads collapse without introducing a non-XNA mutable-string type.

Python keywords receive a trailing underscore. This is the only routine public
identifier rewrite: CLR `None` becomes `None_`. The verifier records this as a
language rule, not an allowlist entry.

The one selected CLR/Python generic-name collision has an explicit machine-readable
rewrite: CLR `ContentTypeReader<T>` is exported as `ContentTypeReaderOfT[T]`, while
the non-generic CLR `ContentTypeReader` keeps the unsuffixed name. This preserves two
distinct public runtime identities without inventing a constructor or using a
runtime alias. A concrete Python subclass declares
`ContentTypeReaderOfT[ConcreteTarget]`; the base recovers that target deterministically.
An unresolved `TypeVar` fails construction instead of guessing a target type.

The public packages export only XNA identities. ctypes types, opaque handles,
private helpers, filesystem paths, and CNA implementation types are forbidden.

## Callables and overloads

A constructor overload set maps to one `__init__` dispatcher. A method overload
set maps to one PascalCase dispatcher. Dispatch first uses argument count, then
the mapped runtime types, and then the documented nullable distinctions. No
matching overload raises `TypeError`; ambiguous input also raises `TypeError`.
Names such as `Draw2` are forbidden.

Typing overloads in shipped `.pyi` files are the structural representation of
overload signatures. Until a family has checked stubs, verifier diagnostics for
that family remain red. Runtime methods carrying `__xna_arities__` are checked
against the same metadata so a permissive `*args` body cannot conceal a wrong
overload set.

The verifier parses stubs with `ast`; it does not use an implementation
function's erased `inspect.signature()` as the overload authority. Read-only
static properties use `Final[T]`, writable static properties use `ClassVar[T]`,
and instance property setters are explicit in the stub. Stub callables are
checked against the runtime object for existence and instance/static/class
shape. Strict runtime members missing from the stub and stub members missing
from runtime are both diagnostics.

`ref` input values are ordinary copied inputs. `out T` is removed from the
Python argument list and returned. A CLR `void M(ref A, out B)` therefore maps
to `M(a: A) -> B`; multiple outputs return a tuple in declaration order. When
this collapses onto an existing by-value overload, the one dispatcher and one
Python return shape serve both declarations. Value changes to a `ref` struct
are returned before `out` values.

Generic types use `typing.Generic`; generic methods use `TypeVar` annotations.
Runtime dispatch never guesses a CLR generic argument from erased information.
Arrays map to typed Python sequences on input and new lists on return. An
in-place CLR array destination requires a mutable sequence and preserves its
length/range checks. CLR collections map to dedicated collection projections,
not arbitrary lists, when their behavior is public.

Interface projection is measured behaviorally: every mapped interface member
must be present in both runtime and stub, with `IEquatable<T>` and
`IDisposable` additionally requiring the corresponding equality and
context-manager language protocols. Generic TypeVar identity/order and
representable bounds are measured from stubs. A CLR relation without a defined
Python projection remains an unmeasured diagnostic; it is never silently
treated as compatible.

## Operators and object protocol

CLR `+`, `-`, `*`, `/`, unary `-`, `==`, and `!=` map to the corresponding
Python dunder methods. Named XNA methods such as `Add`, `Subtract`, `Multiply`,
and `Divide` remain present. Indexer and equality dunders are language-mapping
members, not CNA extensions. Unsupported operand types return `NotImplemented`;
invalid values accepted by the correct operand type raise the mapped exception.

`ToString`, `Equals`, and `GetHashCode` remain when present. `str`, equality,
and `hash` delegate to the same value semantics. A mutable XNA value can be
hashable only where the selected XNA contract defines hashing; callers must not
mutate it while used as a Python mapping key.

## Numeric contract

Python `float` is binary64; XNA `System.Single` is IEEE-754 binary32. Every
Single public field/property assignment and every behaviorally significant
primitive arithmetic step narrows with round-to-nearest, ties-to-even. NaN,
infinity, signed zero, overflow, and XNA evaluation order are preserved. The
binding does not replace NaN with zero or use higher precision as an
"improvement".

Python integers are arbitrary precision. CLR `Byte`, `Int16`, `UInt16`,
`Int32`, `UInt32`, `Int64`, and `UInt64` arguments and state validate their
exact ranges. Enum values use their declared fixed-width identity. Operations
whose CLR implementation wraps are implemented with explicit fixed-width
wrapping; validation paths do not silently wrap.

## Value types and copies

Python assignment aliases an object and cannot reproduce CLR struct
assignment-copy semantics. This is an explicit language limitation. Fresh
copies are nevertheless required at public/native boundaries, collection
insertion/extraction, mapped `ref`/`out`, and property getters/setters where CLR
would copy. `copy.copy` and `copy.deepcopy` produce value copies.

Static value properties such as `Vector2.Zero`, `Vector3.Up`, `Matrix.Identity`,
and `Color.White` use property syntax and return a fresh mutable value on every
access. A shared mutable singleton is forbidden.

## Nullability, strings, time, streams, and buffers

Nullable references and nullable values map to `T | None`; non-null arguments
reject `None`. CLR strings map to Python `str` and use strict UTF-8 only at the
CNA boundary. Embedded NUL is rejected when the native contract rejects it.
`TimeSpan` maps to `datetime.timedelta`; conversion uses 100-nanosecond ticks
and documents the sub-microsecond precision loss when values originate in
Python.

XNA metadata predates nullable-reference annotations. A reference member whose
documented runtime value is nullable therefore uses a contextual machine rule.
`Microphone.Default` maps to `Microphone | None`, including the ordinary
no-device result. The default values of the `AudioCategory` and
`RendererDetail` structs contain null backing strings, so `AudioCategory.Name`,
`RendererDetail.FriendlyName`, and `RendererDetail.RendererId` map to
`str | None`. Likewise, the input-shaped `Byte[] buffer` spelling on
`Microphone.GetData` is contextually mapped to `MutableSequence[int]` because
the method writes captured bytes into the caller's array. These exceptions are
encoded in `mapping-rules.json` and do not introduce support-framework types.

`Stream` maps by capability. Binary readers require `read()` returning bytes;
writers require `write(bytes)`. The binding neither closes a caller-owned
stream nor seeks without the selected overload's contract. Byte buffers accept
bytes-like inputs for immutable native copies and mutable buffers/sequences for
outputs. Native pointers never escape.

`ContentReader` uses private composition/inheritance with `_BinaryReader` for the
selected `System.IO.BinaryReader` behavior. `_BinaryReader` is not a public CLR/XNA
projection and never appears in stubs. The verifier encodes this as the formal
`composition:_BinaryReader` base relation. CLR attribute bases map to ordinary
Python `object`; no synthetic public `System.Attribute` package is created.

`System.Resources.ResourceManager` maps to `object` at the strict constructor
boundary. `ResourceContentManager` accepts either a `Mapping[str, bytes | BinaryIO]`
or an object with `GetObject(str)`/`get_object(str)`. Byte values are copied into a
manager-owned `BytesIO`. Stream values are read into a manager-owned snapshot and
are not closed by the binding. Missing/`None` values become `ContentLoadException`.
No `System.Resources` package or XNA support type is projected.

`TitleContainer.OpenStream` is title-root relative and returns a fresh caller-owned
binary stream. The private `CNA_TITLE_ROOT` configuration must be absolute; otherwise
the title root is the application module directory (with deterministic embedded
Python fallbacks), never the process working directory. Relative `.`/`..` and mixed
separators are normalized, but absolute paths, drive paths, NULs, lexical escapes,
and symlink escapes are rejected. During a running `Game`, the same root is configured
through CNA's ABI-0.7 title-location route and bytes are read through CNA title storage.

`ContentManager.Load[T]` returns the object selected by the XNB root reader. Python
cannot recover the caller's erased method-level `T`, so caller-requested wrong-type
checking is a `LANGUAGE_MAPPING_LIMITATION`; reader-table identity, reader-declared
target shape, and all binary structure remain validated. Similarly,
`ContentReader.ReadRawObject[T]()` and its no-reader existing-instance overload raise
`NotImplementedError` when no current explicit reader token exists. Overloads with a
`ContentTypeReader`, and object reads carrying a stream reader index, remain fully
operational. This limitation does not permit inference from assignment context,
caller bytecode, asset names, or Python locals.

## Events and callbacks

One event descriptor implements all projected events. `+=` appends, including
duplicates. `-=` removes the first matching subscription and rejects a missing
subscription. Invocation uses a subscription snapshot in insertion order, so
self-removal affects the next invocation. The first exception stops delivery
and propagates. Descriptor assignment caused by augmented assignment is
accepted only for that same bound event.

CNA owner-thread lifecycle callbacks may invoke Python synchronously. A ctypes
trampoline catches `BaseException`, stores it, returns a valid callback failure,
and re-raises the original exception after control returns to `Game.Run` or the
other Python-controlled boundary. Arbitrary audio/media threads may never call
user Python directly; future such routes must queue to the owner-thread
dispatcher. Callback objects remain strongly alive through unregistration and
native game destruction.

## Disposal and ownership

XNA `Dispose()` remains PascalCase. Disposable resources also implement
`__enter__`/`__exit__`; both call the same idempotent path. Native handles are
classified privately as `OWNED`, `BORROWED`, or `PARENT_OWNED`. Two Python
objects may not own one handle, borrowed wrappers never destroy it, and parent
validity is checked before child use.

No Python finalizer calls CNA. Interpreter shutdown can unload the library
before object finalization; deterministic `Dispose` and context management are
therefore the supported cleanup mechanisms. `Finalize` metadata is deliberately
omitted from the Python projection and tracked as a normative language rule.

## Exceptions and unsupported native capability

Argument shape/type errors map to `TypeError`; invalid values/ranges to
`ValueError` or `OverflowError`; disposed access to `RuntimeError`; I/O keeps
the underlying Python exception where possible. CNA failures become private
implementation exceptions carrying operation, result, category, copied UTF-8
message, and context. An opaque CNA error pointer is forbidden.

An XNA member whose ABI route is absent may remain structurally declared only
when it validates arguments and raises an explicit native-capability error. It
must not drop arguments, call a weaker route, return fabricated hardware, or
perform a public no-op.

## Expected projection counts

The pinned seven-assembly Windows runtime profile contains 257 reference types
and 2,964 declared reference members. Python projects one type per reference
type. The declared-member baseline removes 49 enum backing fields named
`value__` and 28 CLR finalizers, producing:

```text
EXPECTED_PYTHON_TYPES=257
EXPECTED_PYTHON_MEMBERS=2887
```

Mapped dunders and context-manager methods are checked as language rules but do
not inflate the declared CLR member count. Missing surface is reported; it is
never allowlisted.
