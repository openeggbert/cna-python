# CNB/CNJ: CNA's own compiled content, as a Python extension

Status: **open**. `cna.extensions.content` is the second selected public CNA
extension family, after `cna.extensions.graphics`.

Date: 2026-09-02. Every number below was measured on the artifacts named in
"Qualification"; none is quoted from an earlier session.

## What this is, and what it is not

`.cnb` is CNA's compiled content container, beside `.xnb`. `.cnj` is the
editable JSON source document a `.cnb` is compiled from. Neither has an XNA
counterpart at all, which is exactly why they live under `cna.extensions` and
not in `Microsoft.Xna.Framework.Content`: a name in that namespace is a claim
about XNA.

**The strict XNA `ContentManager` is untouched.** It is still managed Python, it
still reads `.xnb` and only `.xnb`, and it still keeps its own cache. There is
no "prefer `.cnb`" rule, no "fall back to `.cnb` when the `.xnb` is missing"
rule, and no shared cache identity. A test puts a `.cnb` exactly where the strict
manager looks for a `.xnb` and asserts it is not read.

CNA's `cnb.h` implementation is the format authority. There is **no second
Python parser or encoder** here that could disagree with CNA about what a byte
means. What Python adds is the typed projection: immutable value objects,
explicit lifetimes, checked integer widths, and errors that name CNA's own
category.

## The product decision

| Family | Decision |
|---|---|
| CNB/CNJ compiled content (`cnb.h`) | **Selected.** This document. |
| Native `ContentManager` (`content.h`, `content_readers.h`) | **Not opened**, beyond the two-route dependency below. |
| Engine layer (`engine_layer.h`) | Unopened future decision. |
| Sensors and device services | Unopened future decision. |
| Extended input | Unopened future decision. |
| Net, wider GamerServices/Avatar, XNA Content Pipeline, Xbox, Windows Phone | Unopened future profiles. |

## Route scoreboard

```text
cnb.h canonical routes            272
  bound                           270
  not useful for Python           2      cna_cnb_checked_add
                                         cna_cnb_checked_multiply
dependency slices bound            13    11 from curve.h, 2 from content.h
CNB_CNJ_ROUTES                    285
CNB_CNJ_BOUND                     283
CNB_CNJ_UNREVIEWED                  0
SELECTED_CNB_CNJ_ACTIONABLE_LOCAL   0
```

`docs/generated/cna-route-census.md` lists every one of the 285 by name with its
status and its reason.

### The two routes deliberately not bound

`cna_cnb_checked_add` and `cna_cnb_checked_multiply` exist so a C reader can
combine two file-declared 64-bit values without wrapping around. Python integers
are unbounded, so the same computation is already exact; calling them would turn
an exact answer into a narrower one. The bounds checks that *do* matter happen in
`_cna_native.cnb_support`, at the point where a value has to fit a native width,
and `ValueError` names the value rather than truncating it.

### The two dependency slices

Neither is a decision to open another header. Both are dependencies of the
selected family, measured rather than assumed.

**`curve.h`, eleven routes.** `cna_cnb_encode_curve` takes a *native* `Curve`
handle and `cna_cnb_decode_curve` produces one, so the codec is unreachable from
a managed-only `Microsoft.Xna.Framework.Curve`. The native curve exists only
inside those two functions and is destroyed before either returns; the strict
`Curve` stays pure managed and is not changed.

**`content.h`, two routes.** `cna_cnb_loader_invoke` takes a content manager and
refuses without one -- measured: passing no manager fails with an invalid-handle
error. Without it a registered loader could be resolved and never run, so the
registry would be surface with no capability behind it. Exactly
`cna_content_manager_create` and `cna_content_manager_destroy` are bound; no
load, cache, manifest or root-directory route is.

## The public API

```text
PUBLIC_NAMES=163   MODULES=14   CLASSES=64   FUNCTIONS=61
PUBLIC_CTYPES_LEAK=0            PRIVATE_NATIVE_LEAK=0
PUBLIC_RAW_HANDLE_LEAK=0        PUBLIC_NATIVE_ANNOTATION_LEAK=0
UNDOCUMENTED_PUBLIC=0           XNA_NAMESPACE_CONTAMINATION=0
EXTENSION_SURFACE_DIAGNOSTICS=0
```

| Module | What it holds |
|---|---|
| `format` | The container's vocabulary: `AssetType`, `Compression`, `ChunkFlags`, `ContainerChunk`, `CnbReadLimits`, chunk identifiers, CRC-32C, compression. |
| `document` | `CnbDocument`, `CnbChunk`, `CnbMetadata`, `CnbExternalReference`. |
| `primitives` | `CnbReader`, `CnbByteWriter`, `CnbWriter`, `CnbKeyframe`. |
| `textures` | `CnbTextureData`, `TextureFormat`, `CnaSurfaceFormat`, the 2D/3D/cube codecs. |
| `audio` | `CnbSoundEffectData`, `AudioFormat`, the sound codec. |
| `fonts` | `CnbSpriteFontData`, `CnbGlyph`, the sprite-font codec. |
| `media` | `CnbSongData`, `CnbVideoData`, the two media codecs. |
| `curves` | The `Curve` codec, over the strict XNA value type. |
| `animation` | `CnbAnimationClip`, `CnbAnimationTrack`, `ClipTargetSpace`. |
| `model` | The whole compiled model graph, and `build_model_from_cnj`. |
| `importers` | PNG/JPEG, DDS and WAV, through CNA's own decoders. |
| `compiler` | `compile_cnj`, `CnjCompilation`. |
| `loaders` | `register_loader`, `CnbLoader`, `NativeContentManager`. |
| `errors` | Five exception categories over CNA's result codes. |

### Asset data, not runtime objects

Nothing here returns a `Microsoft.Xna.Framework.Graphics.Texture2D`, a
`SoundEffect`, a `Video` or a `Model`. Those are runtime objects that need a
graphics device or an audio device; a `.cnb` holds **compiled content data**, and
conflating the two would make the codecs untestable without a display. So the
codecs produce extension-owned data objects -- `CnbTextureData`,
`CnbSoundEffectData`, `CnbSpriteFontData`, `CnbModelData` -- and every one of
them is exercised on a non-rasterizing artifact with no sound device.

The one exception is `Curve`, and it is deliberate: the strict XNA `Curve`
already carries every field the `.cnb` schema stores, so a `CnbCurveData` beside
it would be a second spelling of the same value with nothing to add. `Rectangle`,
`Vector3` and `Matrix` are reused the same way. The dependency runs
extension -> strict only.

### The seven formats with no XNA counterpart

CNA defines 27 surface formats; the selected XNA 4.0 projection contains the
first 20. Seven `.cnb` texture formats therefore map to CNA identities XNA never
had -- `ColorBgraExt`, `ColorSrgbExt`, `Dxt5SrgbExt`, `Bc7Ext`, `Bc7SrgbExt`,
`ByteExt`, `UShortExt`. The extension names all 27 itself in `CnaSurfaceFormat`,
and `xna_surface_format` answers `None` for exactly those seven rather than
inventing a member of the strict enum or substituting a nearby format that would
change someone's pixels.

## Ownership

Every object holding a CNA handle has an explicit `close`, works as a context
manager, and refuses use after closing. Nothing relies on `__del__`.

| Object | Ownership |
|---|---|
| `CnbDocument` | OWNED. Copies the file bytes. Refuses to close while a reader borrows it. |
| `CnbReader` from `open_chunk` | BORROWED. Keeps its document alive; must close first. |
| `CnbReader.over_bytes` | OWNED. Copies what it is given. |
| `CnbByteWriter`, `CnbWriter` | OWNED. |
| `CnbTextureData`, `CnbSoundEffectData`, `CnbSpriteFontData`, `CnbModelData`, `CnbAnimationClip` | OWNED. |
| `CnbSpriteFontData.atlas()` | OWNED, an independent copy. Closing it does not affect the font. |
| `CnjCompilation`, `CnbModelFromCnj` | OWNED. |
| `CnbModelFromCnj.take_model()` | TRANSFERRED_ON_SUCCESS, exactly once. A second call raises rather than producing a second owner. |
| `CnbLoader` | OWNED. A copy of the registry entry, so a later registration cannot invalidate it. |
| `LoaderRegistration` | PROCESS_GLOBAL. Outlives any content manager; withdrawn by `close`. |
| `NativeContentManager` | OWNED. Must be created and closed on the game creation thread, before its `Game`. |
| Bone, mesh, part, animation, light | PARENT_OWNED, reached by index. No node has a lifetime of its own. |
| The document inside a loader callback | TRANSIENT_VIEW. CNA invalidates it before the callback returns; the wrapper gives the handle up rather than freeing memory it does not own. |

## Buffers, strings and integers

CNA answers "how many bytes" and "copy them here" as separate calls. That
protocol is written once, in `_cna_native.cnb_support`, and never repeated at a
call site: a buffer is allocated at the size CNA reports, never at a "large
enough" guess, and the result is trimmed to the count the copy call wrote rather
than the count the size call predicted. `CNA_RESULT_BUFFER_TOO_SMALL` on the
sizing pass is the expected answer for a non-empty output, not a failure.

Text is decoded as UTF-8 strictly. A replacement character would turn a native
encoding defect into a plausible-looking name that later reaches a filesystem.
Two routes deliberately do *not* validate their input -- the external-reference
name check and the UTF-8 check -- because malformed UTF-8 is the verdict they
exist to report; those take raw bytes.

Python integers are unbounded and `.cnb` counts are not, so every value crossing
into a fixed-width parameter is range-checked and refused by name rather than
silently truncated by ctypes.

## Limits and untrusted bytes

`CnbReadLimits` is public. `CnbReadLimits.defaults()` reads CNA's own values and
`replace()` narrows any of them; `CnbDocument.parse`, `parse_file` and
`CnbReader.over_bytes` all take one, and `CnbWriter.set_limits` bounds a file so
it cannot exceed what a reader with those limits will open.

Parsing is an untrusted-byte boundary. The measured behaviour:

- Every byte of a small document is flipped, and every prefix length is parsed.
  Whatever still parses reports chunk sizes inside the file it came from.
- The header checksum catches every perturbation of the bytes it covers; each
  chunk's CRC-32C catches every perturbation of its payload.
- A non-zero reserved byte is refused, so the format's own extension room cannot
  be used by a file this build does not understand.
- The whole batch also runs in a child process, because an in-process assertion
  cannot tell a clean refusal from memory quietly scribbled on. It exits 0.

### One measured limit worth knowing

A flipped byte in a Zstandard frame is often refused, but **not always**: a frame
can still decode to exactly the declared length with different contents. The
exact-size rule is a bound on *allocation*, not an integrity check. What catches
content corruption is the chunk's own CRC-32C, which the container stores and
checks -- and a test perturbs every byte of a compressed chunk to prove it.

## `.cnj` compilation and sidecar containment

`compile_cnj` produces the finished `.cnb` bytes plus the two lists a build
system needs: `absorbed_files` (inputs; change one and the output is stale) and
`external_references` (logical asset names the loading side resolves).

**`content_root` is a containment boundary, not a resolution base.** `cnb.h`'s
prose says "directory sidecar references resolve against"; the implementation
joins the reference to the *referring document's* own directory and then requires
the result to stay inside the root. The two readings differ, and the measured one
is documented: the same `../` reference is refused under the default root and
accepted under a wider one.

Refused, each asserted rather than assumed: a parent traversal, a traversal that
would resolve to a file that exists, an absolute path, a missing sidecar, a
truncated sidecar. The wrapper adds no normalisation, no `..` collapsing and no
symlink resolution of its own, because any of those would widen the trust
boundary CNA defines rather than honour it.

No machine path reaches a compiled file: the absorbed list records the *authored*
reference text, the logical name defaults to the document's stem, and a test
asserts the build directory's own path appears nowhere in the output bytes.

## The loader registry, and the native ContentManager decision

A Python callable can be registered for a game-defined asset type and is invoked
by CNA. The whole chain is exercised inside one frame of a real `Game`: register,
resolve for a document, invoke through a native content manager, receive the very
object the loader returned -- by identity, not by value.

**How the object crosses.** CNA's loader contract hands back a `void*` the ABI
never dereferences, copies or frees. Python has no safe raw pointer to give it,
so the registry hands CNA an opaque **token**: a small integer that is a key into
a table in `cna.extensions.content.loaders`, never a Python object address. The
pointer is meaningless outside this process and nothing ever dereferences it.

**Callback safety.** The Python callable is held by a strong reference for the
registration's lifetime -- never a weak one, because CNA holds a raw function
pointer and a collected callable would be a dangling call. A mutation test
proves that: made weak, the loader tests fail. No Python exception unwinds
through a C frame; one raised inside a loader is captured, turned into a failed
load in CNA's own vocabulary, and re-raised on the Python side after CNA has
returned through its own frames, as the original exception.

**What a loader can return.** Only a loader registered from Python produces
something Python can hold. CNA's own built-in loaders construct C++ objects and
refuse to hand them across the C boundary at all, which `CnbLoader.invoke`
reports as `CnbUnsupportedError` rather than papering over. That is the same
boundary a caller-supplied `.xnb` reader has, from the other side, and the API
does not pretend to a generality it does not have.

**The native ContentManager decision.** Opened, minimally, because it is
*required*: `cna_cnb_loader_invoke` refuses without a manager. `NativeContentManager`
is a **separate cache domain** from `Microsoft.Xna.Framework.Content.ContentManager`
-- nothing is shared, neither falls back to the other, and a test asserts the
strict manager does not read a `.cnb` placed exactly where it looks for a `.xnb`.
Two routes are bound and no more.

## Supported asset types

| Type | Encode | Decode | Compile from `.cnj` | Import from source |
|---|---|---|---|---|
| `Texture2D` | yes | yes | yes | PNG/JPEG, with an optional colour key |
| `Texture3D` | yes | yes | yes | -- |
| `TextureCube` | yes | yes | yes | DDS, from a path or from memory |
| `SpriteFont` | yes | yes | yes | -- |
| `SoundEffect` | yes | yes | yes | WAV, from a path or from memory |
| `Curve` | yes | yes | yes | -- |
| `AnimationClip` | yes | yes | yes | -- |
| `Model` | yes | yes | yes | also `build_model_from_cnj` |
| `Song` | yes | yes | -- | -- |
| `Video` | yes | yes | -- | -- |
| `Effect` | -- | -- | -- | Identifier reserved, **no schema by design**: CNA has many renderers, so one API's shader bytecode would be useless on the others. |

Schema 1 encodes `Rgba8` textures and `Pcm16` audio; decoding accepts every
identifier the format names. The WAV importer accepts only the encodings that
convert to 16-bit PCM exactly -- 16-bit PCM as-is and 8-bit unsigned widened
exactly -- and refuses 24-bit, 32-bit, IEEE float and ADPCM by name rather than
resampling or truncating someone's audio.

## Contracts CNA states and this binding enforces earlier

Three shape rules `cnb.h` documents are applied by CNA when a file is *encoded*.
The wrapper checks them at the call that got them wrong, because by encode time
the diagnostic names a file rather than the mistake:

- a texture dimension below 1 (`cnb.h` says "must be at least 1"; the
  implementation accepts a zero and refuses later);
- a sound whose sample bytes do not match its declared frame count and channels;
- a model part whose vertex or index bytes do not match its declared stride and
  count.

Each raises `ValueError` naming both numbers. Nothing else is added to CNA's
contract.

## Copy behaviour

Everything crossing this boundary is a copy of native memory, and **no zero-copy
claim is made anywhere**. Measured: each read is its own copy, a source buffer
can be overwritten immediately after being handed over, and cost per byte stays
flat -- roughly 4-5 ns/byte above 256 KB -- across a fourfold size increase,
which is what rules out the two-call protocol copying twice. `CnbSoundEffectData.samples`,
`CnjCompilation.cnb_bytes` and the model's geometry byte accessors say in their
own docstrings that they copy on each read.

## Qualification

Artifacts, both CNA ABI `0.21.0`:

```text
control  HEADLESS   does not rasterize   SDL3 mixer, dummy device
         94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d
gpu      OPENGLES3  Mesa GL ES 3.2 (llvmpipe), isolated Xvfb display
         65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9
```

Almost nothing in this family needs a renderer: parsing, encoding, decoding,
compiling and every model operation are renderer-independent, and the control
artifact runs them all. Only the loader-invocation tests need a live
`GraphicsDevice`, because a native content manager does.

```text
ABI_MISMATCHES=0             MISSING_SYMBOLS=0
PROTOTYPES_COMPILER_VERIFIED=1048    PROTOTYPE_CONFLICTS=0
C_LAYOUT_MEASUREMENTS=1219   CTYPES_LAYOUT_MEASUREMENTS=1219
```

Every one of the 24 CNB structures and all 179 frozen wire constants are
re-measured by a C probe compiled against the canonical headers, rather than
trusted from prose: a `.cnb` file's values outlive any single build.

### Independent oracles

An encoder/decoder pair is never its own oracle. Every codec is also checked
against the chunk structure the format specifies, read out of the document rather
than through the codec, and against hand-computed expectations: the block
rounding rule, each schema's own strides, and the published CRC-32C check value
for `"123456789"` (`0xE3069283`), which comes from the algorithm's specification
rather than from CNA.

CNA's own tools are the strongest of these. `cna_tool_cnj_to_cnb` and this
binding compile **byte-identical** output from the same `.cnj`, across two OS
processes that share no allocator state or warm heap. `cna_tool_cnb_info`
validates every file this binding writes, reports the same chunk table and the
same external references in the same order, and refuses exactly the corrupt files
this binding refuses.

### Falsifiability

```text
PLANTED=35   KILLED=35   SURVIVED=0   EQUIVALENT=0
```

Thirty-five plausible wrapper mistakes, planted one at a time, each required to
make a *focused* test fail. Five survived the first run and all five were real
gaps: a dead helper with no caller, textures only ever tested at representation
0, a bone transform asserted only on its diagonal (which a transpose leaves
alone), and a colour-key fixture with no black pixel. The campaign is kept in
`tools/mutation/cnb_mutations.py`.

The tooling is held to the same standard. A raw handle in a public annotation, a
wrong ctypes prototype, a wrong CNB struct layout, a `cnb.h` route missing from
classification and a bound route whose only caller was removed each make their
gate fail. The last of those found a real hole rather than confirming a guard:
the reachability gate had not been told to exclude the new manifest module, so
all 281 CNB routes were satisfying it with their own declarations.

## Current blockers

None in this family. Every `cnb.h` route is bound or carries a written reason,
and no route is blocked upstream, by platform, by hardware or by a missing
fixture.

Two upstream observations, neither blocking:

- `cnb.h`'s file-level comment says the document, the byte cursors and the loader
  registry "are separate families and are not published yet". They are published:
  all 272 routes are declared and exported. The comment is stale.
- `cnb.h`'s `content_root` parameter documentation describes a resolution base;
  the implementation uses it as a containment boundary. This binding documents
  and tests the implementation.

## What this does not claim

This qualifies the CNB/CNJ family on Linux x86-64 against CNA `0.21.0`, on the
two artifacts named above. It does not qualify other platforms, other CNA
generations, other renderers, or the asset types CNA has not implemented a schema
for. It says nothing about the unopened extension families, which remain
unopened.
