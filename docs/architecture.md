# Architecture

```text
Python game or tool
        ↓
cna (Pythonic public objects and values)
        ↓
cna._native (private extension/FFI layer)
        ↓
CNA stable C ABI
        ↓
CNA C++ core → Sharp Runtime, subsystems, renderers
```

The API uses Python properties, exceptions, inheritance, context managers, and
standard-library types. Small values and math stay in Python. Native resources
will provide explicit, idempotent `close()` and context-manager support; garbage
collection is only a last-resort safety net for GPU/audio resources.

The eventual native implementation may use a generated CPython extension,
`ctypes`, CFFI, or another mechanism. That choice remains private. The public
contract depends only on CNA's C ABI: opaque handles, fixed-width values, UTF-8,
version checks, structured errors, explicit ownership, callback/GIL rules,
snapshot input, and bulk transfers.

Sharp Runtime stays below the C ABI as a C++ implementation detail. Python must
never understand or expose its strings, collections, exceptions, tasks, or
ownership model.
