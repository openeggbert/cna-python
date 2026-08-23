# Architecture

The only execution architecture is:

```text
Python game
  -> Microsoft.Xna.Framework.* public projection
  -> private _cna_native ctypes implementation
  -> CNA canonical stable C ABI 0.7.0
  -> CNA C++
```

The binding does not link the CNA C++ ABI, pybind11, .NET, Java, Node, Rust, or
another language binding. ctypes was selected because ABI 0.7 uses fixed-width
POD structures, C callbacks, opaque `uint64_t` handles, and caller-owned UTF-8
buffers; the selected slice has no measured requirement for a compiled Python
extension.

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
children are released before the game. No finalizer enters CNA during
interpreter shutdown.

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

SoundEffect owns its native resource and weakly tracks its owned instance
children; each instance strongly retains the effect it depends on. AudioEngine
owns the XACT root. WaveBank and SoundBank are owned children, Cue is an owned
SoundBank child, and AudioCategory is a non-disposable value facade whose
private C handle is released before its engine. Microphones are stable,
non-owning index facades invalidated with their Game. No Audio finalizer enters
CNA, and every explicit failed creation leaves its output handle unpublished.

The strict verifier consumes SHA-256-pinned XNA-derived neutral metadata. Its
normal check is intentionally red while types are missing; unexpected/leak-only
mode is the zero-tolerance public hygiene gate.

Structural/API completeness is distinct from runtime capability. The
machine-readable `docs/runtime-capabilities.json` classifies native, managed,
upstream, backend, platform, asset, hardware, and Python implementation
status without turning HEADLESS command-path evidence into a rendering claim.
