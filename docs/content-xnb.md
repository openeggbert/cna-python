# Content and XNB architecture

CNA-Python implements XNA 4.0 Windows XNB version 5 as a managed object-graph
reader. It does not call another binding, bind CNA's C++ ABI, infer behavior from
asset names, or fabricate unsupported public resource types.

## Resolution and stream boundary

`TitleContainer.OpenStream` resolves one normalized relative name beneath a
deterministic application title root. During `Game`, the root is installed with
`cna_title_location_set_path_ext` and bytes are copied with
`cna_title_container_read_ext`; outside `Game`, the same policy uses a managed
whole-file read. Streams returned by either route are fresh caller-owned
`BytesIO` instances.

`ContentManager.OpenStream` combines `RootDirectory`, the normalized asset name,
and the XNA `.xnb` suffix through that same title boundary. `ResourceContentManager`
replaces only the stream source with the formally mapped Mapping/GetObject adapter.

## Container and reader graph

`ContentReader` validates the `XNB` magic, Windows target byte, version 5, flags,
declared file size, and compressed declared output size. Its private binary reader
uses explicit little-endian widths, exact reads, signed 7-bit Int32 decoding,
strict UTF-8 strings, and variable-width UTF-8 `System.Char` decoding.

The reader table stores one object per serialized entry and validates every
serialized reader version before initializing all readers in table order. Assembly
qualifications are removed structurally at every generic nesting level; resolver
matching is exact after normalization. Built-ins are private. Python custom readers
use the private `_register_content_type_reader(serialized_identity, reader_class)`
bridge, which returns an unregister callback. A registered class must construct a
real `ContentTypeReader`, may override `TypeVersion`, and is initialized through the
ordinary public reader-manager abstraction.

`ContentTypeReaderOfT[Target]` recovers `Target` from a concrete generic base. An
unresolved target is rejected. The non-generic reader remains separately exported
as `ContentTypeReader`.

## Object graph semantics

Object tags use the XNB 1-based reader index, with zero representing null. Raw reads
with an explicit reader contain no tag. Shared-resource references register deferred
callbacks; all declared shared objects are read first, then fixups execute by
resource index and registration order. Multiple callbacks retain the one shared
object identity, and callback failure enters the same failed-load rollback path.

External references resolve relative to the containing asset, normalize before the
cache boundary, and cannot escape the Content root. The manager's case-insensitive
normalized cache provides stable identity across root, shared, and external loads.
An in-progress stack detects circular external references.

Every disposable object created by a reader is recorded once by Python identity.
Successful loads commit their acquired objects to manager ownership. Failed loads
dispose only their uncommitted objects in reverse order. `Unload` atomically clears
cache/ownership state before reverse disposal, and `Dispose` remains idempotent even
after an earlier unload exception. Texture/font ownership order is font then atlas;
buffer ownership order is buffer then managed declaration.

## Built-in readers

Private readers are implemented for:

- Boolean, Byte/SByte, all 16/32/64-bit signed and unsigned integers, Single,
  Double, Char, String, and exactly representable TimeSpan values;
- Vector2/3/4, Quaternion, Matrix, Color, Point, and Rectangle;
- XNA ListReader, ArrayReader, and NullableReader over the implemented element
  identities;
- Texture2D, SpriteFont, VertexDeclaration, VertexBuffer, and IndexBuffer.

Texture2D validates the actual SurfaceFormat/dimensions/mip graph and every mip byte
count. CNA ABI 0.7's selected transfer path is faithful for `SurfaceFormat.Color`,
which is uploaded without re-labeling. Other formats are explicitly rejected; DXT
bytes are never decoded or presented as Color.

SpriteFont reads the real nested object graph: atlas, glyph rectangles, cropping,
character list, line spacing, spacing, kerning, and nullable default character. It
constructs the existing public/native SpriteFont through its legal private factory.

Vertex and index readers use their actual binary layouts and ordinary public/native
resource construction. Raw vertex bytes use the canonical CNA raw upload route;
index bytes are decoded at their declared 16/32-bit width and use the normal typed
transfer route.

Effect and Model readers are intentionally absent because their public XNA graphs
are not implemented. An XNB naming either reader fails with `ContentLoadException`.

## LZX

Compressed XNB uses one persistent 64 KiB managed LZX decoder across XNA frames.
Short and extended big-endian frame headers, 32 KiB maximum frame output, verbatim,
aligned, and uncompressed blocks, repeated offsets, canonical Huffman tables, exact
declared output, and optional zero end markers are validated. Truncated headers or
payloads, invalid block sizes/types/tables/matches, output underflow/overflow,
nonzero trailing data, and the non-XNA Intel E8 transform are rejected as chained
`ContentLoadException` failures.

Qualification covers single and persistent multi-frame synthetic streams, malformed
boundaries, two independent real compressed fixture/decompressed-byte pairs, and
compressed primitive, Texture2D, SpriteFont, vertex, index, shared, and external
resource graphs.

## Python generic limitations

`Load[T](assetName)` cannot observe the erased caller `T`; it returns the root object
selected and shape-validated by the XNB reader table. `ReadRawObject[T]()` without an
explicit reader likewise cannot recover arbitrary erased `T` and raises
`NotImplementedError`. These are recorded `LANGUAGE_MAPPING_LIMITATION` entries.
Explicit-reader raw overloads and object-tag overloads remain implemented. No caller
bytecode, assignment context, locals, asset-name convention, or fake reflection is
used.

