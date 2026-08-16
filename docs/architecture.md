# Architecture

```text
Microsoft.Xna.Framework compatibility packages
                       ↓
_cna_native (private extension/FFI boundary)
                       ↓
CNA stable C ABI
                       ↓
CNA C++: Microsoft::Xna::Framework
```

The public package tree mirrors XNA 4.0. `_cna_native` owns library loading,
UTF-8, native errors, handles, callbacks, GIL/thread rules, ownership, buffers,
and shutdown.

There is no public `CNA.Framework` layer because no corresponding
`CNA::Framework` namespace exists in CNA C++. Future `CNA` packages must mirror
specific real native extensions rather than duplicate XNA types.
