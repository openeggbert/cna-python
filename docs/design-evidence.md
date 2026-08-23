# Design converter evidence

Foundation Milestone 7 completes all thirteen public XNA Design types without
creating a public CLR component-model or reflection framework. XNA 4.0 Windows
metadata and converter IL/reference behavior are authoritative; completed
CNA-Java/Rust projections were used only as engineering corroboration.

## Formal Python projection

| CLR concept | Python projection |
| --- | --- |
| `System.Type` | `type` |
| `CultureInfo` | explicit deterministic culture-name `str`; `None` is invariant |
| `IDictionary` | insertion-ordered `Mapping[str, object]` |
| `PropertyDescriptorCollection` | immutable ordered snapshot mapping |
| `InstanceDescriptor` | `(constructor_or_factory, immutable_argument_tuple)` |
| `ExpandableObjectConverter` | private `_MathTypeConverterBase` composition/flattening |

`ITypeDescriptorContext` parameters and the MathTypeConverter `Attribute[]`
filter are formally omitted because the selected XNA IL does not independently
observe them. The verifier measures these rules. No `System.ComponentModel`
package, private-helper export, raw native object, allowlist entry, or synthetic
XNA support type exists. Duplicate mapping keys are unrepresentable by the
selected Python `Mapping` protocol; ordinary Python last-key-wins construction
occurs before a converter call.

## Conversion matrix

All converters support conversion to `str` and to the executable descriptor
pair. Direct string parsing is supported only by Point, Color, Quaternion,
Vector2, Vector3, and Vector4. BoundingBox, BoundingSphere, Matrix, Plane, Ray,
and Rectangle reject string input, even where the metadata declares a
ConvertFrom override that delegates to unsupported base behavior. Their string
output uses the corresponding XNA value `ToString` shape. Color parses and
formats byte-domain `R,G,B,A`; it has no named-color grammar.

Culture selection is explicit and thread-safe. `None`, invariant/root, and
en-US use `.` decimals with `,` list separators. de-DE uses `,` decimals with
`;` list separators and its observed infinity tokens. Formatting reproduces
legacy seven-significant-digit Single behavior, scientific thresholds,
two-digit exponents, signed-zero collapse to `0`, and NaN/infinity tokens. It
never calls `locale.setlocale`, `str(float)`, or `repr(float)` as an unverified
format oracle. Parsing narrows each scalar to binary32 and rejects malformed,
overflowing, wrong-culture, and wrong-component-count input.

## Properties and reconstruction

GetProperties returns immutable, insertion-ordered snapshots in these exact
orders:

- Point and Vector2: X, Y; Vector3: X, Y, Z;
- Vector4 and Quaternion: X, Y, Z, W;
- Rectangle: X, Y, Width, Height; Color: R, G, B, A;
- BoundingBox: Min, Max; BoundingSphere: Center, Radius;
- Plane: Normal, D; Ray: Position, Direction;
- Matrix: Translation first, then M11 through M44 in row-major field order.

Nested value properties are copied. CreateInstance performs explicit typed
lookups, rejects missing/None/wrong values, ignores unrelated extra keys, and
copies nested values. Matrix reconstruction consumes exactly the sixteen scalar
M fields; the descriptive Translation snapshot is not reapplied. Each
InstanceDescriptor is executable as `callable(*arguments)` and reconstructs an
XNA-equal independent value without general reflection.

## Qualification

`tests/test_design.py` contains ten focused methods covering every shape,
capability matrix, culture, parsing and rejection, exact property order and
snapshots, all CreateInstance paths, Matrix/Color fidelity, invalid inputs, and
all executable descriptors. The behavior corpus adds twenty-one
`PURE_XNA_DERIVED` Design observations. All pass, and all thirteen public types
have zero local structural diagnostics.
