# Architecture

```text
Microsoft.Xna.Framework[.Graphics|.Input|.Content]
                         ↓
CNA.Framework[.Graphics|.Input|.Content]
                         ↓
CNA.Interop
                         ↓
CNA stable C ABI
                         ↓
CNA C++ core
```

The capitalized Python package tree intentionally mirrors CNA/XNA namespaces.
`Microsoft.Xna.Framework` is the compatibility surface; `CNA.Framework` is the
CNA-native surface. Aliasing is acceptable only for scaffold types whose
contracts are identical. Compatibility-specific behavior belongs in distinct
facade classes.

Only `CNA.Interop` may load or call the native library. It converts UTF-8,
results, callbacks, buffers, handles, ownership, GIL/threading, and shutdown.
C++ exceptions and Sharp Runtime types must never cross into Python.
