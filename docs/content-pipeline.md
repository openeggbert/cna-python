# The XNA 4.0 Content Pipeline

XNA's **design-time** half, opened by product decision on 2026-09-02. 128 types,
743 CLR members, 598 mapped Python members, zero diagnostics — and, unlike every
other scope in this repository, not a single CNA route.

## Why there is no native boundary here

A content build reads files and writes files. CNA declares no content-pipeline
header, and it does not need to: the pipeline's job is to turn what an artist
made into the `.xnb` a runtime loads, and the runtime is the only half that
needs a graphics device.

So this projection is pure Python, and that is a property rather than a
compromise:

* it runs on a build server with no display, no audio device and no CNA library;
* every decoder in it — PNG, BMP, TGA, DDS, RIFF/WAVE, MPEG headers, ASF
  headers, DirectX `.x` — is written here, so a content project needs nothing
  installed to build;
* and there is an *independent* oracle for the most important thing it does.

## The oracle

`Microsoft.Xna.Framework.Content.ContentManager`, in this same repository, reads
what the compiler writes. It was written for XNA's format long before any of
this existed and it refuses anything it does not recognise rather than guessing,
which makes it exactly the reader a written `.xnb` has to satisfy.

It found two real defects while this was written, and both were the kind no
amount of reading a specification would have caught:

* a `List<T>` reader named after the element's **reader** rather than its CLR
  **type**, so nothing resolved it;
* the element writer left out of the file's reader table, because no type index
  is written per element and it was not obvious that the table still needed it.

Thirteen value types, four list types, a texture and a model all round-trip
through it, and a model built from a `.x` file loads in a real `Game` with its
bones, its two mesh parts, its buffers and its two materials' colours intact.

## Import-time separation

`Microsoft.Xna.Framework.Content.Pipeline` is a subpackage of the runtime's
`Microsoft.Xna.Framework.Content`, which is where XNA puts it — and Python only
imports a subpackage when something asks for it. A game imports `Content` and
gets a `ContentManager`; a build imports `Content.Pipeline` and gets the
pipeline, and through it the runtime types it produces content for.

The dependency runs one way and two tests assert it, both in a fresh
interpreter: importing the runtime namespace loads no pipeline module, and
importing every pipeline package loads no CNA library.

## What is implemented

```text
PROJECTED_MEMBERS                  667
IMPLEMENTED                        623
ABSTRACT_BY_DESIGN                  39
IMPLEMENTED_ERROR_PATH               1
BLOCKED_UPSTREAM                     3
BLOCKED_FIXTURE                      1
CONTENT_PIPELINE_ACTIONABLE_LOCAL    0
UNREVIEWED                           0
```

`tools/verify_content_pipeline.py` produces that, and it works the way the route
census does: it reads every projected member's implementation, and a member that
can refuse must appear in `tools/content-pipeline-decisions.json` with a status
and a written reason. A member that refuses and is not declared is `UNREVIEWED`,
which the gate may not ship; a decision whose member no longer refuses is
`STALE`, which is how a blocker gets deleted when it is fixed rather than
lingering as a comment. `tests/test_content_pipeline_gate.py` plants both.

The 39 abstract members are XNA's own abstract members — a `ContentImporter`'s
`Import`, a `ContentProcessorContext`'s services, a `ContentTypeWriter`'s
`Write` — and the decision for each names what implements it here.

## The four blockers, each narrow and each cited

| member | why | unblocked by |
| --- | --- | --- |
| `EffectProcessor.Process` | there is no HLSL compiler. CNA's own `effects.h` says so at `cna_effect_create_compiled`: *"this runtime embeds no HLSL compiler and the XNA/FNA toolchain must compile it first"*. | a CNA route that takes effect source and answers bytecode |
| `FontDescriptionProcessor.Process` | rasterizing a named font needs a TrueType rasterizer, and neither Python's standard library nor CNA's C ABI has one — `sprite_font.h` reads a `SpriteFont`, it does not build one. | a CNA route that rasterizes a font file into glyphs |
| `FbxImporter.Import` | FBX has no public specification and its only complete reader is Autodesk's SDK, which this package may not bundle. | a CNA route that imports FBX |
| `BuildXact.Execute` (with content) | an `.xap` is compiled by Microsoft's XACT tool, which is Windows-only and not redistributable; CNA's `xact.h` *reads* banks. | a CNA route that compiles an XACT project |

Each is narrow, and each has a working path beside it: `FontTextureProcessor`
builds the same `SpriteFontContent` from a texture an artist drew, `XImporter`
reads the `.x` every FBX exporter can also write, and `SoundEffectProcessor`
builds ordinary sound effects. Everything up to the missing capability still
runs — `EffectProcessor` validates its input and parses `Defines` before it
refuses, and says how many it parsed.

`AudioContent.Data` for an MP3 or WMA source is the fifth, and it is a *value*
rather than a member: the container's format header is read and is exact, and
the decoded samples are not available. CNA can decode either into a playable
`SoundEffect` but declares no route that reads a decoded effect's PCM back out,
so the bytes cannot be recovered through it either.

## Things that were tempting and are not done

* **A third-party imaging or font library.** Both are installed on this machine
  and neither is used. A design-time package that needs one is a package that
  does not run where the rest of this repository runs.
* **Compressed `.xnb` output.** Writing one needs an LZX *compressor* and this
  repository has the decompressor only. Uncompressed XNB is a complete, valid
  XNA 4.0 file that the `ContentManager` here loads, so nothing is unreachable
  — the files are larger, and the refusal says exactly that.
* **Guessing a vertex channel's element type.** `MeshBuilder.CreateVertexChannel`
  takes it as a keyword and requires it, as C# requires the type argument.
  Inferring it from the usage name would be right for the channels this
  repository happens to use and wrong for a three-component `TEXCOORD`.

## Decisions worth reading twice

**Premultiplied alpha comes before anything that averages.** The texture
processor colour-keys, *then* premultiplies, then resizes, then mipmaps, then
compresses. Averaging straight-alpha pixels pulls a transparent neighbour's
colour into the result, which is the dark fringe every un-premultiplied sprite
sheet has; a test measures it, on an image that is half opaque white and half
transparent black.

**The colour key becomes transparent *black*.** Not transparent magenta: a
filtered sample that mixed a key pixel with its neighbour would otherwise pull
magenta into the result even at zero alpha.

**DXT endpoints are found along the block's own colour axis**, not along its
widest single channel. The naive choice is visibly wrong on anything whose
colours vary in two channels at once. A collinear block — a greyscale ramp, a
fade, anything an artist paints into 4x4 pixels — comes back within the format's
own 5:6:5 quantisation, and a test asserts that bound rather than a comfortable
one. A hand-worked block checks the palette against the format written out by
hand: `170` and `85`, because the interpolation is defined on the 8-bit values.

**A `.x` file's normals use their own face list.** That is what lets a file
share positions between faces that do not share normals, and honouring it is the
difference between a faceted cube and a smooth one.

**A volume texture is one face per mipmap level.** `MipmapChainCollection` has
two dimensions and a volume has two things to store — slices and levels — so
this type uses them both, and says so. That is what makes `GenerateMipmaps` a
real operation: level *n+1* halves the width, the height *and* the depth, and
each voxel is the average of the eight it covers. A filter that averaged within
a slice only would give a volume sharp along *z* and blurred across it; a test
asserts the value that distinguishes them.

**A build is incremental, and a clean deletes only what it wrote.** The
dependency cache is what an importer's `AddDependency` feeds, so an effect that
includes a shared header is rebuilt when the header changes. `CleanContent`
removes what the cache recorded and nothing else — deleting `*.xnb` under the
output directory would delete another project's output, which is worse than
leaving a stale file behind.

**MSBuild's `ITaskItem` is not projected as an XNA name.** It belongs to
MSBuild, and a name XNA's assembly does not declare has no place in an XNA
namespace. `TaskItem` stands in for it, is not exported, and accepts a bare
string wherever an item is wanted — because most items are only a file name.

## Language-mapping decisions

* A generic method whose type argument appears in no parameter takes it as a
  **keyword**: `ReadConvertedContent(targetType=...)`,
  `GetConverter(sourceType=..., destinationType=...)`,
  `CreateVertexChannel(usage, elementType=...)`. The positional signature stays
  XNA's, and the type is named at the call the way C# names it. Which methods
  those are is data in `mapping-rules.json`, read by the stub generator and the
  verifier both, so the two cannot disagree about whether one is there.
* `MaterialContent` declares three `T`s with three different constraints. Python
  declares a TypeVar once per module, so the `struct`-constrained one is
  projected as `TValue` — the same mechanism XNA's `IVertexType` constraint
  already used here.
* `ContentCompiler.Compile` is `internal` in XNA and private here. A content
  project drives the compiler through `Tasks.BuildContent`; publishing it would
  be claiming a member XNA does not have.
* `ContentWriter`'s six typed writes are `Write` *overloads* in XNA, so they are
  one `Write` here and the halves are private.

## Improvements this scope made to the shared gates

Opening a profile with two-parameter generics, several indexers per type and
generic methods found four real gaps in the verifier, all fixed:

* `!N` (a declaring type's generic parameter) and `!!N` (a member's) were
  resolved against one list, which was accidentally right for every
  single-parameter generic seen until now and wrong for `ChildCollection<TParent,
  TChild>`.
* A type with two indexers had one of them checked and one of them missing from
  its stub. Five runtime types really do accept a string key and said they did
  not; their stubs now carry both overloads.
* An indexer is now readable/writable if *any* of its overloads is, which is what
  a single Python `__getitem__`/`__setitem__` pair actually provides.
* Arity now counts positional parameters only, which is what arity means.

The Windows runtime profile is unchanged: 257 types, 2,423 members, zero
diagnostics.
