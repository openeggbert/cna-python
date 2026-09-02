# Architecture

The only execution architecture is:

```text
Python game
  -> Microsoft.Xna.Framework.* public projection      (the selected XNA 4.0 profile)
  -> cna.extensions.*                                 (CNA-only capabilities, optional)
  -> private _cna_native ctypes implementation
  -> CNA canonical stable C ABI 0.21.0
  -> CNA C++
```

The binding does not link the CNA C++ ABI, pybind11, .NET, Java, Node, Rust, or
another language binding. ctypes was selected because the C ABI uses fixed-width
POD structures, C callbacks, opaque `uint64_t` handles, and caller-owned UTF-8
buffers; the selected slice has no measured requirement for a compiled Python
extension.

One ABI generation is supported at a time. CNA's contract makes a `0.x` minor a
compatibility generation, so the loader accepts any patch inside the qualified
minor and rejects every other minor and major rather than pretending one ctypes
manifest can be truthful for two generations permitted to differ incompatibly.

`Microsoft.Xna.Framework` is the selected XNA 4.0 Windows projection and nothing
else: a member CNA offers but XNA never had does not belong there, because a
name in that namespace is a claim about XNA. CNA-only capabilities live under
`cna.extensions`, which the XNA namespace never imports and does not depend on.

Three extension families are open. `cna.extensions.graphics` reports renderer
identity and selection. `cna.extensions.content` projects CNA's own `.cnb`
compiled content format and its `.cnj` source documents; the strict XNA
`ContentManager` is unchanged by it, still reads `.xnb` and only `.xnb`, and
keeps its own separate cache. `cna.extensions.engine` projects `engine_layer.h`
-- compute, physically based materials, shadows, post-processing, clustered
lighting, light probes, culling and instancing, and a debug line batch -- none of
which XNA ever had. The dependency runs extension -> strict only: the content
extension reuses `Curve`, `Rectangle`, `Vector3`, `Matrix` and `SurfaceFormat`,
and the engine extension reuses those plus `Color`, `BoundingBox`,
`BoundingSphere`, `BoundingFrustum`, `Effect`, `Texture2D`, `TextureCube`,
`RenderTarget2D` and `ModelMeshPart`, where each is exactly the natural
representation; a test in a fresh interpreter asserts that importing the XNA
namespace loads no `cna` module at all. See `docs/cnb-cnj-extensions.md` and
`docs/engine-extensions.md`.

Opening a family may require a small slice of another header, and that is a
dependency rather than a second decision: the CNB curve codec speaks in native
`Curve` handles, so eleven `curve.h` routes are imported and used only inside two
functions, and `cna_cnb_loader_invoke` requires a content manager, so exactly two
`content.h` routes are imported. The engine family needs three such slices --
five routes for PBR effects and materials, eight for the ASCII effect, and two
`models.h` routes to project a strict `ModelMeshPart` into the native handle
level-of-detail and instancing demand. Each carries its own census rule and its
own written reason, and none makes the header it came from public.

Public namespaces preserve XNA names. Private modules split math, geometry,
game hosting, component/services, display/presentation, graphics states,
resources, vertices/buffers, render targets, input, Audio/XACT, loader, ABI
declarations, errors, and ownership. The loader accepts only an absolute `CNA_NATIVE_LIBRARY`, an absolute
`CNA_NATIVE_DIR`, or an intentionally packaged native asset. No current-working-
directory search occurs and no native library is bundled in this milestone.

The game handle owns the native lifecycle. Textures, SpriteBatch, SpriteFont,
vertex declarations, vertex/index buffers, render targets, SoundEffects,
instances, dynamic instances, and AudioEngines/banks/cues are owned;
GraphicsDevice is borrowed and valid for native work only during an owner-thread
lifecycle callback. State descriptors are managed XNA facades copied into CNA
when bound. Device facades strongly retain bound resources, explicit buffer
disposal is rejected while bound, shutdown unbinds first, and all remaining
native children are strongly retained by the Game ownership root and released
before the game. This prevents a dropped Python wrapper from stranding its CNA
handle beyond the owning generation. No finalizer enters CNA during
interpreter shutdown.

A ctypes callback handed to CNA is rooted on the **owning native handle**, not on
the public facade that created it. CNA keeps the trampoline pointer until
unregistration or resource destruction, and the facade and its closure form a
reference cycle the collector may reclaim first, so rooting it on the facade is a
use-after-free waiting for the next event rather than a leak. For the same
reason the owning handle carries the facade's teardown as a pre-release hook:
shutdown releases handles through the owning generation, which would otherwise
free a handle while the views it owns are still live.

Lifecycle callback objects are strongly retained by the game host. ctypes
enters Python with the GIL. Every trampoline catches `BaseException`, records a
diagnostic for CNA, returns callback failure, and re-raises the original object
after the native call returns. Static input facades resolve the active game only
on the `Game.Run` owner thread.

CNA's C-owned game invokes the Python `Update` override and, only after a
successful return, runs the native base update containing the one canonical
`FrameworkDispatcher` pump. Python does not pump it a second time. CNA skips
that base pass after callback failure, so a throwing Update does not dispatch
queued framework work afterward. Canonical ABI documentation and native tests
establish that DynamicSoundEffectInstance and Microphone callbacks raised by
this pump run on the Game owner thread. Their minimal ctypes trampoline verifies
that identity, keeps the callback strongly rooted, catches every Python
exception before returning through C, and unregisters before resource or Game
destruction. An unexpected non-owner-thread delivery is contained as an error;
user code is never knowingly run on an uncontrolled audio thread.

The public `FrameworkDispatcher.Update()` is an explicit second operation, not
another automatic mechanism: it resolves the unique live owner-thread Game
generation, invokes the same dispatcher route exactly once, drains the
shared owner queue, and re-raises a contained callback exception after native
control returns. CNA's dispatcher route takes a Game handle, unlike XNA's process
dispatcher, so it has nothing to pump without one; calls with no selectable live
Game report that limitation instead of silently doing nothing or fabricating a
dispatcher.

`GamerServicesComponent` is an ordinary `GameComponent` using the Game-owned
window and generation for the three canonical dispatcher routes. No broader
Gamer/Guide/Avatar/network object graph is projected. Touch static state also
uses the live Game generation and canonical touch routes; value snapshots and
`TouchCollection.Enumerator` contain no native identity.

Storage ownership is `Game -> StorageDevice lease -> StorageContainer ->
Storage stream`. Public async results are private one-shot leases until End
transfers the native handle into its public owner. Synchronous CNA completion is
reported honestly, while no user callback runs inside the ctypes completion
trampoline. DeviceChanged and other off-frame callbacks enqueue into the same
FrameworkDispatcher owner queue; there is no Storage dispatcher. Storage paths
are normalized and checked lexically and after resolution before CNA is called,
closing CNA's container traversal gap at the XNA semantic boundary.

`RenderTargetCube` reuses `TextureCube` ownership and ordinary render-target
bindings. A Python binding retains each bound target. Disposal of a bound target
is refused, the owned handle is preserved for a later legal owner-thread retry,
and the backbuffer is never silently restored. The historical generation aborted
the process here; the current one refuses cleanly with `INVALID_STATE`, and the
Python guard is kept as defence in depth rather than removed. Game shutdown
explicitly unbinds first. Both render-target kinds carry a real native
ContentLost subscription, released before their handle; CNA raises it only on
renderer families that can lose a device, and none is synthesized elsewhere.

SoundEffect owns its native resource and weakly tracks its owned instance
children; each instance strongly retains the effect it depends on. AudioEngine
owns the XACT root. WaveBank and SoundBank are owned children, Cue is an owned
SoundBank child, and AudioCategory is a non-disposable value facade whose
private C handle is released before its engine. Microphones are stable,
non-owning index facades invalidated with their Game. No Audio finalizer enters
CNA, and every explicit failed creation leaves its output handle unpublished.

Media has synchronized process state because XNA `MediaPlayer` is static. It
separates CNA process-global scalars from the current Game generation, event
registrations, one stable `MediaQueue` facade, identity domains, and queued
weak-generation work. Teardown unregisters callbacks, invokes native program
exit, destroys the queue, releases players before videos and catalog children
before their provider root, then permits Game destruction. Stale Media facades
reject native work deterministically.

`MediaLibrary`, its catalog objects, all seven collection handles, `Song`,
`Video`, and `VideoPlayer` are `OWNED`; the Video GraphicsDevice is `BORROWED`;
the native frame texture is `PARENT_OWNED`; `MediaPlayer` is `PROCESS_GLOBAL`;
`MediaQueue` is a process-global/current-generation view; `MediaSource` and
`VisualizationData` are managed generation/value facades. Provider-domain
native equality canonicalizes catalog identity, and queue access reuses the
exact Song facade supplied to Play. No second owner is created.

The private `VideoReader` uses the existing ContentManager reader table, cache,
path normalization, LZX framing, transactional recording, rollback, and
Unload. It resolves the content-relative file reference against the title
location before CNA sees it, because CNA opens the file itself and resolves a
relative path against the process working directory.

A player retains its selected content Video. `GetTexture` returns a real
`Texture2D` that borrows the runtime's frame: never owned, never destroyed,
carrying no per-frame native subscription, and not registered as a child of the
owning generation, which would accumulate one entry per read. CNA decodes into a
single texture and replaces it on the next call, so the wrapper validates the
decode generation before every native use and refuses with the reason the borrow
ended. No frame maps to `None`.

The strict verifier consumes SHA-256-pinned XNA-derived neutral metadata. The
selected XNA 4.0 Windows runtime projection is structurally complete at 257
types; normal and leak-only checks are both zero-tolerance green gates.

Structural/API completeness is distinct from runtime capability. The
machine-readable `docs/runtime-capabilities.json` classifies native, managed,
upstream, renderer, platform, fixture and hardware status per qualified
artifact, so command-path evidence from a backend that does not rasterize is
never presented as a rendering claim, and a rendering result is never
generalised to a backend that cannot produce it.

Four gates answer four different questions and none substitutes for another: the
strict verifier asks whether the XNA namespace is exactly the selected
projection; the extension gate asks whether CNA-only surface stays out of it and
keeps its own promises, including that no public signature *names* a handle or a
ctypes type; the ABI and prototype gates ask whether the native boundary is what
the headers declare; and the reachability gate asks whether every bound route is
actually called.

Each gate has been shown to fail. Planted defects prove it: a raw handle in a
public annotation, a wrong ctypes prototype, a wrong struct layout, a route
missing from the census, and a bound route whose only caller was removed. The
last of those found a real hole rather than confirming a guard, which is the
reason the plants are kept rather than run once.
